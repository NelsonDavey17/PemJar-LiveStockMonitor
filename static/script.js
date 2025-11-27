const charts = {}; //inisialisasi objek untuk menyimpan grafik

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
    animation: false
};
//fungsi untuk buat grafik baru berdasarkan simbol saham
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
        //menggunakan opsi umum untuk semua grafik (commonOptions)
        options: commonOptions
    });
}
//dipanggil saat inisialisasi aplikasi, untuk buat grafik kosong
function initCharts() {
    //panggil createChart untuk tiap simbol saham
    charts['BTC-USD'] = createChart('chartBTC', '#F7931A'); 
    charts['DOGE-USD'] = createChart('chartDOGE', '#C2A633'); 
    charts['SOL-USD'] = createChart('chartSOL', '#9945FF');
    charts['DAX P'] = createChart('chartDAX', '#45ff5eff');
}

function updateChart(symbol, timestamp, price) {
    const chart = charts[symbol];
    if (!chart) return;
    const timeLabel = timestamp.split(' ')[1];
    const currentLabels = chart.data.labels;
    if (currentLabels.length > 0 && currentLabels[currentLabels.length - 1] === timeLabel) {
        return; 
    }
    chart.data.labels.push(timeLabel);
    chart.data.datasets[0].data.push(price);
    if (chart.data.labels.length > 50) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }

    chart.update('none');
}
//inisialisasi aplikasi
async function startApp() {
    //panggil inisialisasi grafik untuk pertama kali
    initCharts();
    try {
        console.log("Mengambil data sejarah...");
        //mengambil data sejarah dari server
        const response = await fetch('/api/data');
        //mengonversi respons ke format JSON
        const data = await response.json();
        if (data.length > 0) {
            data.forEach(item => {
                //manggil updateChart untuk tiap data sejarah/update baru
                updateChart(item.symbol, item.waktu, item.harga);
            });
            console.log(`Berhasil memuat ${data.length} data sejarah.`);
        } else {
            console.log("Database masih kosong/sedikit data.");
        }
        connectWebSocket();
    } catch (e) {
        console.error("Gagal memuat data:", e);
        connectWebSocket();
    }
}
//fungsi untuk menghubungkan ke WebSocket
function connectWebSocket() {
    const socket = io();
    socket.on('connect', () => {
        console.log("Terhubung ke WebSocket");
    });
    socket.on('update_grafik', (data) => {
        console.log("Data Baru:", data.symbol);
        updateChart(data.symbol, data.waktu, data.harga);
    });
}

// Jalankan aplikasi
startApp();