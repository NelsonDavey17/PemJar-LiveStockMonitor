const charts = {};

const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: 'index', intersect: false },
    plugins: { legend: { display: false } },
    scales: {
        x: { display: true, ticks: { maxTicksLimit: 8 } },
        y: { display: true, grace: '5%' }
    },
    elements: {
        line: { tension: 0.3, borderWidth: 2 },
        point: { radius: 0, hitRadius: 10 }
    },
    animation: false // Matikan animasi agar sejarah langsung muncul
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
}

function updateChart(symbol, timestamp, price) {
    const chart = charts[symbol];
    if (!chart) return;

    // Format waktu: Ambil HH:MM:SS saja
    const timeLabel = timestamp.split(' ')[1];

    // CEK DUPLIKASI: Jangan masukkan jika waktu sama dengan data terakhir
    const currentLabels = chart.data.labels;
    if (currentLabels.length > 0 && currentLabels[currentLabels.length - 1] === timeLabel) {
        return; 
    }

    chart.data.labels.push(timeLabel);
    chart.data.datasets[0].data.push(price);

    // Limit tampilan grafik agar tidak berat (scrolling)
    if (chart.data.labels.length > 50) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }

    chart.update('none');
}

// Fungsi Utama: Ambil Data Sejarah -> Lalu Dengarkan WebSocket
async function startApp() {
    initCharts(); // Siapkan kanvas kosong

    try {
        // 1. Ambil Data Sejarah dari Database via API
        console.log("Mengambil data sejarah...");
        const response = await fetch('/api/data');
        const data = await response.json();

        // Masukkan data sejarah ke grafik
        if (data.length > 0) {
            data.forEach(item => {
                updateChart(item.symbol, item.waktu, item.harga);
            });
            console.log(`Berhasil memuat ${data.length} data sejarah.`);
        } else {
            console.log("Database masih kosong/sedikit data.");
        }

        // 2. Setelah sejarah masuk, baru nyalakan WebSocket
        connectWebSocket();

    } catch (e) {
        console.error("Gagal memuat data:", e);
        // Tetap nyalakan WebSocket meski API gagal
        connectWebSocket();
    }
}

function connectWebSocket() {
    const socket = io({
        transports: ['polling'],
        upgrade: false
    });

    socket.on('connect', () => {
        console.log("✅ Terhubung ke WebSocket");
    });
    socket.on('connect_error', (err) => {
        console.error("❌ Gagal Konek:", err);
    });
    socket.on('update_grafik', (data) => {
        console.log("⚡ Data Baru:", data.symbol);
        updateChart(data.symbol, data.waktu, data.harga);
    });
}

// Jalankan aplikasi
startApp();