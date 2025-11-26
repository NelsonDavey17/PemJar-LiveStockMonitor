import sqlite3
import os
import time
import yfinance as yf
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO
from apscheduler.schedulers.background import BackgroundScheduler

# --- KONFIGURASI ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# Mode Threading dengan Polling (Lebih stabil untuk Render)
socketio = SocketIO(app, 
                    cors_allowed_origins="*", 
                    async_mode='threading',
                    logger=True,
                    engineio_logger=True,
                    ping_timeout=60,
                    ping_interval=25)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_FOLDER = os.path.join(BASE_DIR, 'instance')
DB_PATH = os.path.join(INSTANCE_FOLDER, 'saham.db')
TARGET_SYMBOLS = ['BTC-USD', 'DOGE-USD', 'SOL-USD']

if not os.path.exists(INSTANCE_FOLDER):
    os.makedirs(INSTANCE_FOLDER)

# --- FUNGSI DATABASE ---
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
        
        waktu_sekarang = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[✓] Saved & Broadcasting: {symbol} -> ${harga:.2f} at {waktu_sekarang}")
        
        # Emit dengan namespace default dan broadcast=True
        socketio.emit('update_grafik', {
            'symbol': symbol,
            'harga': float(harga),
            'waktu': waktu_sekarang
        }, namespace='/', broadcast=True)
        
        return True
    except Exception as e:
        print(f"[!] Gagal menyimpan: {e}")
        return False

def update_stock_price():
    """Fungsi yang dipanggil scheduler setiap 30 detik"""
    print("\n[*] === Mengambil data baru ===")
    
    for symbol in TARGET_SYMBOLS:
        harga = None
        
        try:
            ticker = yf.Ticker(symbol)
            
            # Percobaan 1: fast_info
            try:
                if hasattr(ticker, 'fast_info') and ticker.fast_info:
                    harga = ticker.fast_info.last_price
                    print(f"[✓] {symbol}: ${harga:.2f} (fast_info)")
            except Exception as e:
                print(f"[!] fast_info failed for {symbol}: {e}")
            
            # Percobaan 2: history (fallback)
            if harga is None or harga == 0:
                try:
                    data = ticker.history(period='1d', interval='1m')
                    if not data.empty:
                        harga = float(data['Close'].iloc[-1])
                        print(f"[✓] {symbol}: ${harga:.2f} (history)")
                except Exception as e:
                    print(f"[!] history failed for {symbol}: {e}")
            
            # Simpan jika berhasil
            if harga is not None and harga > 0:
                simpan_harga(symbol, harga)
            else:
                print(f"[!] Gagal total mengambil data {symbol}")
                
        except Exception as e:
            print(f"[!] Error sistem {symbol}: {e}")
    
    print("[*] === Selesai update cycle ===\n")

# --- SCHEDULER SETUP ---
scheduler = BackgroundScheduler()
scheduler.add_job(func=update_stock_price, trigger="interval", seconds=30, id='stock_updater')

# --- ROUTE ---
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
                    'harga': float(row['harga'])
                })
        
        conn.close()
        hasil_akhir.sort(key=lambda x: x['waktu'])
        return jsonify(hasil_akhir)
    except Exception as e:
        print(f"[!] API Error: {e}")
        return jsonify({'error': str(e)}), 500

# --- SOCKETIO EVENTS ---
@socketio.on('connect')
def handle_connect():
    print(f"[+] Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    print(f"[-] Client disconnected")

# --- STARTUP ---
init_db()

# Start scheduler
if not scheduler.running:
    scheduler.start()
    print("[*] Scheduler started!")
    # Jalankan update pertama setelah 5 detik
    time.sleep(5)
    update_stock_price()

# Blok ini hanya jalan di Localhost
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)