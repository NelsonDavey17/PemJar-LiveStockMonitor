import sqlite3
import os
import time
import yfinance as yf
from flask import Flask, jsonify, render_template
from flask_socketio import SocketIO
from threading import Thread

# --- KONFIGURASI ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# EVENTLET MODE - Paling stabil untuk production
socketio = SocketIO(app, 
                    cors_allowed_origins="*", 
                    async_mode='eventlet',
                    logger=True,
                    engineio_logger=False)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_FOLDER = os.path.join(BASE_DIR, 'instance')
DB_PATH = os.path.join(INSTANCE_FOLDER, 'saham.db')
TARGET_SYMBOLS = ['BTC-USD', 'DOGE-USD', 'SOL-USD']

if not os.path.exists(INSTANCE_FOLDER):
    os.makedirs(INSTANCE_FOLDER)

# Global untuk tracking koneksi client
connected_clients = []

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
    """Simpan ke database dan emit ke semua client"""
    try:
        # 1. Simpan ke database
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO harga_saham (symbol, harga) VALUES (?, ?)", (symbol, harga))
        conn.commit()
        conn.close()
        
        waktu_sekarang = time.strftime('%Y-%m-%d %H:%M:%S')
        print(f"[✓] DB Saved: {symbol} -> ${harga:.2f}")
        
        # 2. Emit ke semua client yang terkoneksi
        if len(connected_clients) > 0:
            data_payload = {
                'symbol': symbol,
                'harga': float(harga),
                'waktu': waktu_sekarang
            }
            socketio.emit('update_grafik', data_payload)
            print(f"[✓] WebSocket emitted to {len(connected_clients)} client(s)")
        else:
            print(f"[!] No clients connected, skipping emit")
        
        return True
        
    except Exception as e:
        print(f"[!] Error dalam simpan_harga: {e}")
        import traceback
        traceback.print_exc()
        return False

def update_stock_price():
    """Background worker untuk fetch data"""
    print("\n[*] Background worker started, waiting 10 seconds...")
    socketio.sleep(10)  # Initial delay
    
    while True:
        print("\n[*] === Fetching new stock data ===")
        
        for symbol in TARGET_SYMBOLS:
            harga = None
            
            try:
                ticker = yf.Ticker(symbol)
                
                # Try 1: fast_info
                try:
                    if hasattr(ticker, 'fast_info') and ticker.fast_info:
                        harga = ticker.fast_info.last_price
                        if harga and harga > 0:
                            print(f"[✓] {symbol}: ${harga:.2f} (fast_info)")
                except Exception as e:
                    print(f"[!] fast_info failed for {symbol}: {str(e)[:50]}")
                
                # Try 2: history fallback
                if harga is None or harga == 0:
                    try:
                        data = ticker.history(period='1d', interval='1m')
                        if not data.empty:
                            harga = float(data['Close'].iloc[-1])
                            print(f"[✓] {symbol}: ${harga:.2f} (history)")
                    except Exception as e:
                        print(f"[!] history failed for {symbol}: {str(e)[:50]}")
                
                # Save if successful
                if harga is not None and harga > 0:
                    simpan_harga(symbol, harga)
                else:
                    print(f"[!] Failed to fetch {symbol}")
                    
            except Exception as e:
                print(f"[!] Error fetching {symbol}: {e}")
        
        print("[*] === Update cycle complete ===\n")
        socketio.sleep(30)  # Wait 30 seconds

def start_background_worker():
    """Start background thread"""
    def run_worker():
        with app.app_context():
            update_stock_price()
    
    worker = Thread(target=run_worker, daemon=True)
    worker.start()
    print("[+] Background worker thread started!")

# --- ROUTES ---
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
        print(f"[API] Returning {len(hasil_akhir)} records")
        return jsonify(hasil_akhir)
        
    except Exception as e:
        print(f"[!] API Error: {e}")
        return jsonify({'error': str(e)}), 500

# --- SOCKETIO EVENTS ---
@socketio.on('connect')
def handle_connect():
    from flask import request
    client_id = request.sid
    connected_clients.append(client_id)
    print(f"[+] Client connected: {client_id} | Total: {len(connected_clients)}")

@socketio.on('disconnect')
def handle_disconnect():
    from flask import request
    client_id = request.sid
    if client_id in connected_clients:
        connected_clients.remove(client_id)
    print(f"[-] Client disconnected: {client_id} | Total: {len(connected_clients)}")

# --- STARTUP ---
init_db()
start_background_worker()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)