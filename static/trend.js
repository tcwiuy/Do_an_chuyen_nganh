// ==========================================
// FILE: trend.js - PHÂN TÍCH BIẾN ĐỘNG & BỘ LỌC TƯƠNG TÁC
// ==========================================

window.exchangeRatesToVND = window.exchangeRatesToVND || {
    vnd: 1, usd: 25400, eur: 27500, gbp: 32000, jpy: 165,
    cny: 3500, krw: 18.5, inr: 305, rub: 275, brl: 4900,
    zar: 1350, aed: 6915, aud: 16800, cad: 18600, chf: 28000,
    hkd: 3250, bdt: 230, sgd: 18800, thb: 690, try: 780,
    mxn: 1500, php: 440, pln: 6350, sek: 2350, nzd: 15300,
    dkk: 3680, idr: 1.58, ils: 6750, myr: 5350, mad: 2520
};

var allTrendTransactions = [];
var trendChartInstance = null;
var currentPeriod = 'week';
var currentMetric = 'expense'; // Lưu trạng thái nút đang chọn ('income', 'expense', 'balance')

var userCurrency = { code: 'VND', locale: 'vi-VN', rate: 1.0 };

document.addEventListener('DOMContentLoaded', async () => {
    if (!document.getElementById('trendChart')) return;
    await loadCurrencyConfig();
    await fetchTransactionsForTrends();
    setupTrendEventListeners();
    processAndRenderTrends('week');
});

async function loadCurrencyConfig() {
    try {
        const token = localStorage.getItem('token');
        const res = await fetch('/api/config', { headers: { 'Authorization': `Bearer ${token}` } });
        if (res.ok) {
            const config = await res.json();
            userCurrency.code = (config.currency || 'VND').toLowerCase();
        }
        const localeMap = { 'vnd': 'vi-VN', 'usd': 'en-US', 'eur': 'de-DE', 'jpy': 'ja-JP' };
        userCurrency.locale = localeMap[userCurrency.code] || 'en-US';
        const rateToVnd = window.exchangeRatesToVND[userCurrency.code] || 1;
        userCurrency.rate = 1 / rateToVnd;
    } catch (e) { console.warn("Dùng mặc định VND."); }
}

async function fetchTransactionsForTrends() {
    try {
        const token = localStorage.getItem('token');
        const response = await fetch('/api/expenses/', { headers: { 'Authorization': `Bearer ${token}` } });
        if (response.ok) {
            const rawTxns = await response.json();
            allTrendTransactions = rawTxns.map(t => ({ ...t, amount: t.amount * userCurrency.rate }));
        }
    } catch (e) { console.error("Lỗi tải dữ liệu:", e); }
}

function setupTrendEventListeners() {
    // 1. Lắng nghe nút thời gian
    const btns = { 'week': 'btnWeek', 'month': 'btnMonth', 'year': 'btnYear' };
    Object.entries(btns).forEach(([p, id]) => {
        document.getElementById(id)?.addEventListener('click', function() {
            Object.values(btns).forEach(bid => {
                document.getElementById(bid).style.background = 'transparent';
                document.getElementById(bid).style.borderColor = 'transparent';
            });
            this.style.background = '#8a2be2';
            this.style.borderColor = '#d4a5ff';
            processAndRenderTrends(p);
        });
    });

    document.getElementById('compareToggle')?.addEventListener('change', () => processAndRenderTrends(currentPeriod));

    // 2. LẮNG NGHE 3 THẺ TƯƠNG TÁC (Income, Expense, Balance)
    const cards = {
        'income': document.getElementById('cardIncome'),
        'expense': document.getElementById('cardExpense'),
        'balance': document.getElementById('cardBalance')
    };

    Object.entries(cards).forEach(([metric, el]) => {
        if(!el) return;
        el.addEventListener('click', () => {
            Object.values(cards).forEach(c => c.classList.remove('active'));
            el.classList.add('active');
            currentMetric = metric; // Cập nhật trạng thái
            processAndRenderTrends(currentPeriod); // Vẽ lại biểu đồ
        });
    });
}

function processAndRenderTrends(period) {
    currentPeriod = period;
    const now = new Date();
    let cS, cE, pS, pE;

    if (period === 'week') {
        let day = now.getDay();
        let diff = now.getDate() - day + (day === 0 ? -6 : 1);
        cS = new Date(now.setDate(diff)); cS.setHours(0,0,0,0);
        cE = new Date(cS); cE.setDate(cE.getDate() + 6); cE.setHours(23,59,59,999);
        pS = new Date(cS); pS.setDate(pS.getDate() - 7);
        pE = new Date(cE); pE.setDate(pE.getDate() - 7);
    } else if (period === 'month') {
        cS = new Date(now.getFullYear(), now.getMonth(), 1);
        cE = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);
        pS = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        pE = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59);
    } else {
        cS = new Date(now.getFullYear(), 0, 1);
        cE = new Date(now.getFullYear(), 11, 31, 23, 59, 59);
        pS = new Date(now.getFullYear() - 1, 0, 1);
        pE = new Date(now.getFullYear() - 1, 11, 31, 23, 59, 59);
    }

    const curTxns = allTrendTransactions.filter(t => {
        const d = new Date(t.date.split('T')[0] + "T00:00:00");
        return d >= cS && d <= cE;
    });
    const prevTxns = allTrendTransactions.filter(t => {
        const d = new Date(t.date.split('T')[0] + "T00:00:00");
        return d >= pS && d <= pE;
    });

    const sum = (arr) => arr.reduce((acc, t) => ({
        inc: acc.inc + (t.amount > 0 ? t.amount : 0),
        exp: acc.exp + (t.amount < 0 ? Math.abs(t.amount) : 0)
    }), { inc: 0, exp: 0 });

    const curSum = sum(curTxns);
    const prevSum = sum(prevTxns);

    updateCards(curSum, prevSum);
    updateChart(curSum, prevSum);
    renderTopCategories(curTxns);
}

function updateCards(cur, prev) {
    document.getElementById('trendIncomeVal').textContent = formatCurrencySafe(cur.inc);
    document.getElementById('trendExpenseVal').textContent = formatCurrencySafe(cur.exp);
    document.getElementById('trendBalanceVal').textContent = formatCurrencySafe(cur.inc - cur.exp);

    const setBadge = (id, cV, pV, isE) => {
        const el = document.getElementById(id);
        if (pV === 0) { el.className = 'badge neutral'; el.textContent = 'Mới'; return; }
        const p = ((cV - pV) / pV) * 100;
        el.className = `badge ${p > 0 ? (isE ? 'bad' : 'good') : (isE ? 'good' : 'bad')}`;
        el.innerHTML = `<i class="fa-solid fa-arrow-trend-${p > 0 ? 'up' : 'down'}"></i> ${Math.abs(p).toFixed(1)}%`;
    };
    setBadge('trendIncomeBadge', cur.inc, prev.inc, false);
    setBadge('trendExpenseBadge', cur.exp, prev.exp, true);
}

// CẬP NHẬT BIỂU ĐỒ THEO THẺ ĐANG CHỌN
function updateChart(cur, prev) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    if (trendChartInstance) trendChartInstance.destroy();
    
    let labels = [];
    let curData = []; let prevData = [];
    let curBg = []; let prevBg = [];
    let title = "";

    // Gán dữ liệu tùy theo thẻ đang bấm
    if (currentMetric === 'income') {
        title = "Tương quan Thu Nhập";
        labels = ['Thu Nhập']; curData = [cur.inc]; prevData = [prev.inc];
        curBg = ['#4ade80']; prevBg = ['#4ade8040'];
    } else if (currentMetric === 'expense') {
        title = "Tương quan Chi Tiêu";
        labels = ['Chi Tiêu']; curData = [cur.exp]; prevData = [prev.exp];
        curBg = ['#f87171']; prevBg = ['#f8717140'];
    } else if (currentMetric === 'balance') {
        title = "Tương quan Chênh Lệch";
        labels = ['Chênh Lệch']; curData = [cur.inc - cur.exp]; prevData = [prev.inc - prev.exp];
        curBg = ['#d4a5ff']; prevBg = ['#d4a5ff40'];
    }

    document.getElementById('chartTitle').textContent = title;

    const datasets = [{ 
        label: 'Kỳ này', data: curData, backgroundColor: curBg, borderRadius: 6,
        maxBarThickness: 100 // Ép biểu đồ không bị phình to khi chỉ có 1 cột
    }];
    
    if (document.getElementById('compareToggle').checked) {
        datasets.push({ 
            label: 'Kỳ trước', data: prevData, backgroundColor: prevBg, borderRadius: 6,
            maxBarThickness: 100
        });
    }

    trendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: { 
                y: { ticks: { callback: v => formatCurrencySafe(v), color: '#a1a1aa' }, grid: { color: '#2a2a40' } },
                x: { ticks: { color: '#fff' }, grid: { display: false } }
            },
            plugins: { legend: { labels: { color: '#fff' } } }
        }
    });
}

// CẬP NHẬT TOP DANH MỤC THEO THẺ ĐANG CHỌN
function renderTopCategories(txns) {
    const container = document.getElementById('topCategoriesContainer');
    const titleEl = document.getElementById('topCategoriesTitle');
    const cats = {};
    let total = 0;
    
    // Nếu bấm Thu nhập -> Lọc tiền Dương. Chi tiêu/Chênh lệch -> Lọc tiền Âm
    let isIncomeMode = (currentMetric === 'income');
    
    if (isIncomeMode) {
        titleEl.innerHTML = '<i class="fa-solid fa-ranking-star" style="color: #4ade80;"></i> Top nguồn thu nhập';
        txns.filter(t => t.amount > 0).forEach(t => {
            cats[t.category] = (cats[t.category] || 0) + t.amount;
            total += t.amount;
        });
    } else {
        titleEl.innerHTML = '<i class="fa-solid fa-fire" style="color: #f87171;"></i> Top danh mục tiêu xài';
        txns.filter(t => t.amount < 0).forEach(t => {
            cats[t.category] = (cats[t.category] || 0) + Math.abs(t.amount);
            total += Math.abs(t.amount);
        });
    }

    const sorted = Object.entries(cats).sort((a, b) => b[1] - a[1]).slice(0, 5);
    
    container.innerHTML = sorted.map(([n, v]) => {
        const p = total > 0 ? (v / total * 100).toFixed(1) : 0;
        const color = isIncomeMode ? '#4ade80' : '#f87171';
        return `<div class="category-item"><div style="flex:1">
            <div style="display:flex; justify-content:space-between; color:#fff; margin-bottom: 5px;">
                <span style="font-weight: 500;">${n}</span><span style="color:#a1a1aa; font-size: 0.9rem;">${p}%</span>
            </div>
            <div style="color:${color}; font-weight:bold">${formatCurrencySafe(v)}</div>
            <div class="progress-bar-bg"><div class="progress-bar-fill" style="width:${p}%; background: ${color}"></div></div>
        </div></div>`;
    }).join('') || `<div style="text-align:center; color:#a1a1aa">Không có dữ liệu trong khoảng thời gian này</div>`;
}

function formatCurrencySafe(amount) {
    return new Intl.NumberFormat(userCurrency.locale, { style: 'currency', currency: userCurrency.code.toUpperCase() }).format(amount);
}