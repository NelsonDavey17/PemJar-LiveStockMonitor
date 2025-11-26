import eventlet
eventlet.monkey_patch()
import sqlite3
import os
import time
from threading import Lock
import yfinance as yf
from flask import Flask, jsonify, render_template, request
from flask_socketio import SocketIO, emit

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_FOLDER = os.path.join(BASE_DIR, 'instance')
DB_PATH = os.path.join(INSTANCE_FOLDER, 'saham.db')
thread = None
thread_lock = Lock()
TARGET_SYMBOLS = ['BTC-USD', 'DOGE-USD', 'SOL-USD']

if not os.path.exists(INSTANCE_FOLDER):
    os.makedirs(INSTANCE_FOLDER)

def init_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS harga_saham (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                waktu TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                harga REAL NOT NULL
            )
        ''')
        conn.commit()
        conn.close()
        print("[+] Database siap.")
    except Exception as e:
        print(f"[!] Error init DB: {e}")

def simpan_harga(symbol, harga):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO harga_saham (symbol, harga) VALUES (?, ?)", (symbol, harga))
        conn.commit()
        conn.close()
        print(f"[✔] Broadcast: {symbol} -> {harga}")
        socketio.emit('update_grafik', {
            'symbol': symbol,
            'harga': harga,
            'waktu': time.strftime('%Y-%m-%d %H:%M:%S')
        })
    except Exception as e:
        print(f"[!] Gagal menyimpan: {e}")

def background_thread():
    """Fungsi ini berjalan di background"""
    print("--- [!!!] WORKER AKHIRNYA BERJALAN [!!!] ---")
    while True:
        print("[*] Mengambil data baru...")
        print("\n[*] Mengambil data baru...")
        for symbol in TARGET_SYMBOLS:
            harga = None
            try:
                ticker = yf.Ticker(symbol)
                try:
                    if ticker.fast_info and ticker.fast_info.last_price:
                        harga = ticker.fast_info.last_price
                except Exception:
                    pass 
                if harga is None:
                    data = ticker.history(period='1d', interval='1m')
                    if not data.empty:
                        harga = data['Close'].iloc[-1]
                if harga is not None:
                    simpan_harga(symbol, harga)
                else:
                    print(f"[!] Gagal total mengambil data {symbol} (Yahoo menolak)")
            except Exception as e:
                print(f"[!] Error sistem {symbol}: {e}")
        socketio.sleep(30)

@socketio.on('connect')
def connect():
    global thread
    print(f"[+] Client terhubung: {request.sid}")
    with thread_lock:
        if thread is None:
            print("[+] Memulai Background Thread untuk pertama kalinya...")
            thread = socketio.start_background_task(background_thread)

@socketio.on('disconnect')
def disconnect():
    print(f"[-] Client putus: {request.sid}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        hasil_akhir = []
        for symbol in TARGET_SYMBOLS:
            query = '''
                SELECT waktu, symbol, harga 
                FROM harga_saham 
                WHERE symbol = ? 
                ORDER BY id DESC 
                LIMIT 50
            '''
            c.execute(query, (symbol,))
            rows = c.fetchall()
            for row in reversed(rows):
                hasil_akhir.append({
                    'waktu': row['waktu'],
                    'symbol': row['symbol'],
                    'harga': row['harga']
                })
        conn.close()
        hasil_akhir.sort(key=lambda x: x['waktu'])
        return jsonify(hasil_akhir)
    except Exception as e:
        return jsonify({'error': str(e)})



init_db()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)