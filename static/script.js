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
}

function updateChart(symbol, timestamp, price) {
    const chart = charts[symbol];
    if (!chart) return;
    const timeLabel = timestamp.split(' ')[1];
    const lastLabel = chart.data.labels[chart.data.labels.length - 1];
    if (lastLabel === timeLabel) return;
    chart.data.labels.push(timeLabel);
    chart.data.datasets[0].data.push(price);
    if (chart.data.labels.length > 50) {
        chart.data.labels.shift();
        chart.data.datasets[0].data.shift();
    }
    chart.update('none');
}

async function fetchData() {
    try {
        const response = await fetch('/api/data');
        const data = await response.json();
        data.forEach(item => {
            updateChart(item.symbol, item.waktu, item.harga);
        });
        console.log("Data sejarah berhasil dimuat:", data.length, "poin data");
    } catch (e) {
        console.error("Gagal ambil history:", e);
    }
}

const socket = io();
socket.on('connect', () => {
    console.log("Terhubung ke WebSocket Server");
});
socket.on('update_grafik', (data) => {
    console.log("Data Baru:", data.symbol, data.harga);
    updateChart(data.symbol, data.waktu, data.harga);
});
initCharts();
fetchData();