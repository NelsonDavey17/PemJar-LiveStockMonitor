const charts = {};
let lastUpdateTime = {};

const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: { 
        legend: { display: false },
        tooltip: {
            callbacks: {
                label: function(context) {
                    return '$' + context.parsed.y.toFixed(2);
                }
            }
        }
    },
    scales: {
        x: { 
            display: true, 
            ticks: { maxTicksLimit: 8 }
        },
        y: { 
            display: true, 
            grace: '5%',
            ticks: {
                callback: function(value) {
                    return '$' + value.toFixed(2);
                }
            }
        }
    },
    elements: {
        line: { tension: 0.3, borderWidth: 2 },
        point: { radius: 0, hitRadius: 10 }
    },
    animation: false
};

function createChart(canvasId, color) {
    const ctx = document.getElementById(canvasId).getContext('2d');
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                data: [],
                borderColor: color,
                backgroundColor: color + '20',
                fill: true
            }]
        },
        options: commonOptions
    });
}

function initCharts() {
    charts['BTC-USD'] = createChart('chartBTC', '#F7931A'); 
    charts['DOGE-USD'] = createChart('chartDOGE', '#C2A633'); 
    charts['SOL-USD'] = createChart('chartSOL', '#9945FF');
    
    // Initialize last update tracking
    lastUpdateTime['BTC-USD'] = null;
    lastUpdateTime['DOGE-USD'] = null;
    lastUpdateTime['SOL-USD'] = null;
}

function updateChart(symbol, timestamp, price) {
    const chart = charts[symbol];
    if (!chart) {
        console.warn(`Chart not found for ${symbol}`);
        return;
    }

    // Format waktu: Ambil HH:MM:SS saja
    const timeLabel = timestamp.split(' ')[1] || timestamp;

    // CEK DUPLIKASI dengan toleransi - hanya cek apakah sama persis dengan entry terakhir
    const currentLabels = chart.data.labels;
    const currentData = chart.data.datasets[0].data;
    
    if (currentLabels.length > 0) {
        const lastLabel = currentLabels[currentLabels.length - 1];
        const lastPrice = currentData[currentData.length - 1];
        
        // Skip hanya jika waktu DAN harga sama persis (duplikasi murni)
        if (lastLabel === timeLabel && Math.abs(lastPrice - price) < 0.01) {
            console.log(`[SKIP] ${symbol}: Duplicate data`);
            return;
        }
    }

    // Tambahkan data baru
    chart.data.labels.push(timeLabel);
    chart.data.datasets[0].data.push(price);

    // Limit tampilan grafik (keep last 50 points)
    if (chart.data.labels.length > 50) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }

    // Update chart tanpa animasi untuk performa
    chart.update('none');
    
    // Track update
    lastUpdateTime[symbol] = new Date().toLocaleTimeString();
    console.log(`[UPDATE] ${symbol}: $${price.toFixed(2)} at ${timeLabel}`);
}

// Fungsi Utama: Ambil Data Sejarah -> Lalu Dengarkan WebSocket
async function startApp() {
    initCharts();

    try {
        console.log("📥 Mengambil data sejarah...");
        const response = await fetch('/api/data');
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const data = await response.json();

        if (data.error) {
            throw new Error(data.error);
        }

        // Masukkan data sejarah ke grafik
        if (data.length > 0) {
            data.forEach(item => {
                updateChart(item.symbol, item.waktu, item.harga);
            });
            console.log(`✅ Berhasil memuat ${data.length} data sejarah.`);
        } else {
            console.log("⚠️ Database masih kosong/sedikit data.");
        }

    } catch (e) {
        console.error("❌ Gagal memuat data sejarah:", e);
    }

    // Selalu nyalakan WebSocket (bahkan jika API gagal)
    connectWebSocket();
}

function connectWebSocket() {
    console.log("🔌 Menghubungkan ke WebSocket...");
    
    const socket = io({
        transports: ['websocket', 'polling'],
        upgrade: true,
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionAttempts: 10
    });

    socket.on('connect', () => {
        console.log("✅ Terhubung ke WebSocket (ID:", socket.id, ")");
    });

    socket.on('disconnect', (reason) => {
        console.log("❌ WebSocket terputus:", reason);
    });

    socket.on('connect_error', (error) => {
        console.error("❌ WebSocket error:", error.message);
    });

    socket.on('update_grafik', (data) => {
        console.log("⚡ Data Baru WebSocket:", data);
        
        if (data.symbol && data.harga && data.waktu) {
            updateChart(data.symbol, data.waktu, data.harga);
            
            // Visual feedback (optional)
            const chartBox = document.querySelector(`#chart${data.symbol.split('-')[0]}`);
            if (chartBox && chartBox.parentElement) {
                chartBox.parentElement.style.boxShadow = '0 4px 12px rgba(0,200,0,0.3)';
                setTimeout(() => {
                    chartBox.parentElement.style.boxShadow = '0 4px 6px rgba(0,0,0,0.05)';
                }, 500);
            }
        } else {
            console.warn("⚠️ Data tidak lengkap:", data);
        }
    });

    // Heartbeat untuk memastikan koneksi tetap hidup
    setInterval(() => {
        if (socket.connected) {
            console.log("💓 WebSocket still alive");
        } else {
            console.warn("⚠️ WebSocket disconnected, attempting reconnect...");
        }
    }, 60000); // Check every 60 seconds
}

// Jalankan aplikasi
startApp();