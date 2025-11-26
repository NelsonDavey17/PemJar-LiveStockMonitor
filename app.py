# HAPUS SEMUA IMPORT EVENTLET DI SINI.
# Biarkan gunicorn_config.py yang menangani patching.

import sqlite3
import os
import time
import threading
import yfinance as yf
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
# Pastikan async_mode='eventlet' ditulis eksplisit
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_FOLDER = os.path.join(BASE_DIR, 'instance')
DB_PATH = os.path.join(INSTANCE_FOLDER, 'saham.db')
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
        
        # Kirim update realtime
        socketio.emit('update_grafik', {
            'symbol': symbol,
            'harga': harga,
            'waktu': time.strftime('%Y-%m-%d %H:%M:%S')
        })
        print(f"[✔] Broadcast: {symbol} -> {harga}")
    except Exception as e:
        print(f"[!] Gagal menyimpan: {e}")

def update_stock_price():
    """Worker mengambil data setiap 60 detik agar tidak kena rate limit"""
    print("--- Worker Memulai ---")
    socketio.sleep(5) # Tunggu server up dulu
    
    while True:
        print("\n[*] Mengambil data dari Yahoo...")
        for symbol in TARGET_SYMBOLS:
            try:
                ticker = yf.Ticker(symbol)
                # Coba fast_info dulu
                if hasattr(ticker, 'fast_info') and ticker.fast_info.last_price:
                    harga = ticker.fast_info.last_price
                else:
                    # Fallback history
                    data = ticker.history(period='1d')
                    if not data.empty:
                        harga = data['Close'].iloc[-1]
                    else:
                        print(f"[!] Data kosong: {symbol}")
                        continue
                
                simpan_harga(symbol, harga)
            except Exception as e:
                print(f"[!] Error {symbol}: {e}")
        
        # PENTING: Gunakan socketio.sleep agar tidak memblokir WebSocket
        socketio.sleep(60) 

def start_background_task():
    thread = threading.Thread(target=update_stock_price)
    thread.daemon = True
    thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/data')
def get_data():
    """Ambil 50 data terakhir per simbol untuk inisialisasi grafik"""
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

if __name__ == '__main__':
    # INI HANYA JALAN DI LOCALHOST
    # Di Railway, Gunicorn yang akan menjalankan app, blok ini diabaikan
    import eventlet
    eventlet.monkey_patch()
    init_db()
    start_background_task()
    print("[*] Server Local berjalan...")
    socketio.run(app, debug=True, use_reloader=False)
else:
    # INI JALAN DI RAILWAY (Saat diimport Gunicorn)
    # Kita panggil fungsi init dan worker di sini
    init_db()
    start_background_task()