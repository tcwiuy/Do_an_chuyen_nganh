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
var currentPeriod = 'month';
var currentMetric = 'expense'; // Lưu trạng thái nút đang chọn ('income', 'expense', 'balance')
var currentAnchor = new Date(); // reference date for the currently selected period

var userCurrency = { code: 'VND', locale: 'vi-VN', rate: 1.0 };

function getScaleUnit(maxAbs) {
    if (!isFinite(maxAbs) || maxAbs <= 0) return { divisor: 1, unit: '' };
    if (maxAbs >= 1_000_000_000) return { divisor: 1_000_000_000, unit: 'Tỷ' };
    if (maxAbs >= 1_000_000) return { divisor: 1_000_000, unit: 'Triệu' };
    if (maxAbs >= 1_000) return { divisor: 1_000, unit: 'Nghìn' };
    return { divisor: 1, unit: '' };
}

function formatScaledTick(value, divisor) {
    const v = Number(value) / (divisor || 1);
    const abs = Math.abs(v);
    const digits = abs >= 10 ? 0 : abs >= 1 ? 1 : 2;
    return v.toLocaleString(userCurrency.locale, { maximumFractionDigits: digits });
}

function getWeekdayLabel(date) {
    // vi: T2..T7, CN
    const d = date.getDay();
    if (d === 0) return 'CN';
    return `T${d + 1}`;
}

document.addEventListener('DOMContentLoaded', async () => {
    if (!document.getElementById('trendChart')) return;
    await loadCurrencyConfig();
    await fetchTransactionsForTrends();
    setupTrendEventListeners();
    // initialize anchor and render default period
    currentAnchor = new Date();
    processAndRenderTrends('month', currentAnchor);
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
    // 1) Period tabs (Theo tuần / Theo tháng / Theo năm)
    const periodBtnIds = { week: 'btnWeek', month: 'btnMonth', year: 'btnYear' };
    const setActivePeriodBtn = (period) => {
        Object.values(periodBtnIds).forEach((id) => document.getElementById(id)?.classList.remove('active'));
        document.getElementById(periodBtnIds[period])?.classList.add('active');
    };

    Object.entries(periodBtnIds).forEach(([period, id]) => {
        document.getElementById(id)?.addEventListener('click', () => {
            currentPeriod = period;
            setActivePeriodBtn(period);
            processAndRenderTrends(period, currentAnchor);
        });
    });

    // Compare toggle lives in chart header
    document.getElementById('compareToggle')?.addEventListener('change', () => processAndRenderTrends(currentPeriod, currentAnchor));

    // Prev / Next navigation (move the current anchor by period)
    document.getElementById('prevPeriod')?.addEventListener('click', () => { moveAnchor(-1); });
    document.getElementById('nextPeriod')?.addEventListener('click', () => { moveAnchor(1); });

    // 2) Metric tabs (Thu nhập / Chi tiêu / Chênh lệch)
    const metricBtnIds = {
        income: 'btnMetricIncome',
        expense: 'btnMetricExpense',
        balance: 'btnMetricBalance'
    };
    const setActiveMetricBtn = (metric) => {
        Object.values(metricBtnIds).forEach((id) => document.getElementById(id)?.classList.remove('active'));
        document.getElementById(metricBtnIds[metric])?.classList.add('active');
    };

    Object.entries(metricBtnIds).forEach(([metric, id]) => {
        document.getElementById(id)?.addEventListener('click', () => {
            currentMetric = metric;
            setActiveMetricBtn(metric);
            processAndRenderTrends(currentPeriod, currentAnchor);
        });
    });

    // Ensure initial UI matches defaults
    setActivePeriodBtn(currentPeriod);
    setActiveMetricBtn(currentMetric);
}

function metricContribution(amount) {
    if (currentMetric === 'income') return amount > 0 ? amount : 0;
    if (currentMetric === 'expense') return amount < 0 ? Math.abs(amount) : 0;
    return amount;
}

function processAndRenderTrends(period, anchorDate) {
    currentPeriod = period;
    const anchor = anchorDate ? new Date(anchorDate) : new Date();
    let cS, cE, pS, pE;

    if (period === 'week') {
        const day = anchor.getDay();
        const diff = anchor.getDate() - day + (day === 0 ? -6 : 1);
        cS = new Date(anchor.getFullYear(), anchor.getMonth(), diff); cS.setHours(0, 0, 0, 0);
        cE = new Date(cS); cE.setDate(cE.getDate() + 6); cE.setHours(23, 59, 59, 999);
        pS = new Date(cS); pS.setDate(pS.getDate() - 7); pS.setHours(0, 0, 0, 0);
        pE = new Date(cE); pE.setDate(pE.getDate() - 7); pE.setHours(23, 59, 59, 999);
    } else if (period === 'month') {
        cS = new Date(anchor.getFullYear(), anchor.getMonth(), 1); cS.setHours(0, 0, 0, 0);
        cE = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0); cE.setHours(23, 59, 59, 999);
        pS = new Date(cS.getFullYear(), cS.getMonth() - 1, 1); pS.setHours(0, 0, 0, 0);
        pE = new Date(pS.getFullYear(), pS.getMonth() + 1, 0); pE.setHours(23, 59, 59, 999);
    } else {
        cS = new Date(anchor.getFullYear(), 0, 1); cS.setHours(0, 0, 0, 0);
        cE = new Date(anchor.getFullYear(), 11, 31); cE.setHours(23, 59, 59, 999);
        pS = new Date(cS.getFullYear() - 1, 0, 1); pS.setHours(0, 0, 0, 0);
        pE = new Date(cS.getFullYear() - 1, 11, 31); pE.setHours(23, 59, 59, 999);
    }

    const curTxns = allTrendTransactions.filter(t => {
        const d = new Date(t.date.split('T')[0] + 'T00:00:00');
        return d >= cS && d <= cE;
    });
    const prevTxns = allTrendTransactions.filter(t => {
        const d = new Date(t.date.split('T')[0] + 'T00:00:00');
        return d >= pS && d <= pE;
    });

    // Build labels and series depending on granularity
    let labels = [];
    let curSeries = [];
    let prevSeries = [];
    let tooltipTitles = null;

    if (period === 'week') {
        for (let i = 0; i < 7; i++) {
            const d = new Date(cS); d.setDate(cS.getDate() + i);
            labels.push(getWeekdayLabel(d));
        }
        const mapCur = {}; const mapPrev = {};
        curTxns.forEach(t => {
            const key = t.date.split('T')[0];
            mapCur[key] = (mapCur[key] || 0) + metricContribution(t.amount);
        });
        prevTxns.forEach(t => {
            const key = t.date.split('T')[0];
            mapPrev[key] = (mapPrev[key] || 0) + metricContribution(t.amount);
        });
        for (let i = 0; i < 7; i++) {
            const d = new Date(cS); d.setDate(cS.getDate() + i);
            const key = d.toISOString().slice(0, 10);
            curSeries.push(mapCur[key] || 0);

            const pd = new Date(pS); pd.setDate(pS.getDate() + i);
            const pkey = pd.toISOString().slice(0, 10);
            prevSeries.push(mapPrev[pkey] || 0);
        }
    } else if (period === 'month') {
        // MoMo-like month view: show recent months (default 6 bars) while totals still reflect the selected month
        const monthsToShow = 6;
        const monthAnchors = [];
        for (let i = monthsToShow - 1; i >= 0; i--) {
            monthAnchors.push(new Date(anchor.getFullYear(), anchor.getMonth() - i, 1));
        }

        labels = monthAnchors.map(d => `T${d.getMonth() + 1}`);
        tooltipTitles = monthAnchors.map(d => `${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`);

        const sumMetricInRange = (start, end) => {
            let total = 0;
            allTrendTransactions.forEach((t) => {
                const d = new Date(t.date.split('T')[0] + 'T00:00:00');
                if (d < start || d > end) return;
                total += metricContribution(t.amount);
            });
            return total;
        };

        monthAnchors.forEach((m0) => {
            const start = new Date(m0.getFullYear(), m0.getMonth(), 1); start.setHours(0, 0, 0, 0);
            const end = new Date(m0.getFullYear(), m0.getMonth() + 1, 0); end.setHours(23, 59, 59, 999);
            const prevStart = new Date(m0.getFullYear(), m0.getMonth() - 1, 1); prevStart.setHours(0, 0, 0, 0);
            const prevEnd = new Date(m0.getFullYear(), m0.getMonth(), 0); prevEnd.setHours(23, 59, 59, 999);

            curSeries.push(sumMetricInRange(start, end));
            prevSeries.push(sumMetricInRange(prevStart, prevEnd));
        });
    } else {
        for (let m = 0; m < 12; m++) labels.push(`T${m + 1}`);
        const mapCur = {}; const mapPrev = {};

        curTxns.forEach(t => {
            const d = new Date(t.date.split('T')[0] + 'T00:00:00');
            const key = d.getMonth();
            mapCur[key] = (mapCur[key] || 0) + metricContribution(t.amount);
        });
        prevTxns.forEach(t => {
            const d = new Date(t.date.split('T')[0] + 'T00:00:00');
            const key = d.getMonth();
            mapPrev[key] = (mapPrev[key] || 0) + metricContribution(t.amount);
        });
        for (let m = 0; m < 12; m++) {
            curSeries.push(mapCur[m] || 0);
            prevSeries.push(mapPrev[m] || 0);
        }
    }

    const sum = (arr) => arr.reduce((acc, t) => ({
        inc: acc.inc + (t.amount > 0 ? t.amount : 0),
        exp: acc.exp + (t.amount < 0 ? Math.abs(t.amount) : 0)
    }), { inc: 0, exp: 0 });
    const curSum = sum(curTxns);
    const prevSum = sum(prevTxns);

    updateTotalBlock(curSum, prevSum, period);
    updateChartFromSeries(labels, curSeries, prevSeries, period, { tooltipTitles });
    renderTopCategories(curTxns, prevTxns, period);
    updatePeriodLabel(period, anchor);
}

function getPeriodVietnamese(period) {
    if (period === 'week') return 'tuần';
    if (period === 'month') return 'tháng';
    return 'năm';
}

function updateTotalBlock(cur, prev, period) {
    const labelEl = document.getElementById('trendTotalLabel');
    const valueEl = document.getElementById('trendTotalValue');
    const pillEl = document.getElementById('trendDeltaPill');
    if (!labelEl || !valueEl || !pillEl) return;

    const periodText = getPeriodVietnamese(period);
    const currentBalance = cur.inc - cur.exp;
    const previousBalance = prev.inc - prev.exp;

    let curVal = 0;
    let prevVal = 0;
    let label = '';

    if (currentMetric === 'income') {
        curVal = cur.inc;
        prevVal = prev.inc;
        label = `Tổng thu ${periodText} này`;
    } else if (currentMetric === 'expense') {
        curVal = cur.exp;
        prevVal = prev.exp;
        label = `Tổng chi ${periodText} này`;
    } else {
        curVal = currentBalance;
        prevVal = previousBalance;
        label = `Tổng chênh lệch ${periodText} này`;
    }

    labelEl.textContent = label;
    valueEl.textContent = formatCurrencySafe(curVal);

    // Compare pill: show delta amount (absolute) and direction
    const rawDelta = curVal - prevVal;
    const deltaAbs = Math.abs(rawDelta);
    const isIncrease = rawDelta >= 0;
    const arrow = isIncrease ? '<i class="fa-solid fa-arrow-trend-up"></i>' : '<i class="fa-solid fa-arrow-trend-down"></i>';

    // Determine good/bad based on metric
    // - Income: increase is good
    // - Expense: decrease is good
    // - Balance: increase is good
    let isGood = true;
    if (currentMetric === 'expense') isGood = !isIncrease;
    else isGood = isIncrease;

    if (prevVal === 0 && curVal === 0) {
        pillEl.style.display = 'none';
        return;
    }

    pillEl.style.display = 'inline-flex';
    pillEl.className = `delta-pill ${isGood ? 'good' : 'bad'}`;

    const verb = isIncrease ? 'Tăng' : 'Giảm';
    const amountText = formatCurrencySafe(deltaAbs);
    pillEl.innerHTML = `${arrow} <span>${verb} ${amountText}</span> <span class="sub">so với cùng kỳ ${periodText} trước</span> <i class="fa-solid fa-circle-info" style="opacity:0.7;"></i>`;
}

// Helpers: aggregate and navigation
function aggregateByMetricForKey(value) {
    if (currentMetric === 'income') return Math.max(0, value);
    if (currentMetric === 'expense') return Math.abs(Math.min(0, value));
    return value; // balance
}

function moveAnchor(direction) {
    if (!currentAnchor) currentAnchor = new Date();
    const a = new Date(currentAnchor);
    if (currentPeriod === 'week') a.setDate(a.getDate() + (direction * 7));
    else if (currentPeriod === 'month') a.setMonth(a.getMonth() + direction);
    else a.setFullYear(a.getFullYear() + direction);
    currentAnchor = a;
    processAndRenderTrends(currentPeriod, currentAnchor);
}

function updatePeriodLabel(period, anchor) {
    const el = document.getElementById('currentPeriodLabel'); if (!el) return;
    const a = new Date(anchor || new Date());
    let label = '';

    if (period === 'week') {
        const day = a.getDay();
        const diff = a.getDate() - day + (day === 0 ? -6 : 1);
        const start = new Date(a.getFullYear(), a.getMonth(), diff);
        const end = new Date(start); end.setDate(end.getDate() + 6);
        const startDay = start.getDate();
        const endDay = end.getDate();
        const startMonth = start.toLocaleString(userCurrency.locale, { month: 'short' });
        const endMonth = end.toLocaleString(userCurrency.locale, { month: 'short' });
        label = startMonth === endMonth
            ? `${startDay} - ${endDay} ${startMonth}`
            : `${startDay} ${startMonth} - ${endDay} ${endMonth}`;
    } else if (period === 'month') {
        label = `${a.toLocaleString(userCurrency.locale, { month: 'long', year: 'numeric' })}`;
    } else {
        label = `${a.getFullYear()}`;
    }
    el.innerHTML = `<strong>${label}</strong><br><span style="font-size:0.8rem; opacity:0.7;">So với cùng kỳ</span>`;
}

// CẬP NHẬT BIỂU ĐỒ TỪ DÃY SỐ LIỆU
function updateChartFromSeries(labels, curData, prevData, period, meta) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    if (trendChartInstance) trendChartInstance.destroy();

    const colorCur = currentMetric === 'expense' ? '#f87171' : currentMetric === 'income' ? '#4ade80' : '#8b5cf6';
    const colorPrev = currentMetric === 'expense' ? '#fca5a5' : currentMetric === 'income' ? '#86efac' : '#c4b5fd';

    const p = period || currentPeriod;
    const periodText = getPeriodVietnamese(p);
    const tooltipTitles = meta?.tooltipTitles || null;

    // Legend labels similar to mobile UI
    const labelCurrent = currentMetric === 'income'
        ? `Tổng thu nhập trong ${periodText}`
        : currentMetric === 'expense'
            ? `Tổng chi tiêu trong ${periodText}`
            : `Tổng chênh lệch trong ${periodText}`;
    const labelCompare = currentMetric === 'income'
        ? 'Thu nhập cùng kỳ'
        : currentMetric === 'expense'
            ? 'Chi tiêu cùng kỳ'
            : 'Chênh lệch cùng kỳ';

    const datasets = [{ label: labelCurrent, data: curData, backgroundColor: colorCur, borderRadius: 6, borderSkipped: false }];
    if (document.getElementById('compareToggle').checked) {
        datasets.push({ label: labelCompare, data: prevData, backgroundColor: colorPrev, borderRadius: 6, borderSkipped: false });
    }

    document.getElementById('chartTitle').textContent = 'Biến động';

    const compareEnabled = !!document.getElementById('compareToggle')?.checked;
    const maxAbs = Math.max(
        ...curData.map(v => Math.abs(v || 0)),
        ...(compareEnabled ? prevData.map(v => Math.abs(v || 0)) : [0])
    );
    const scale = getScaleUnit(maxAbs);

    // Improve axis readability
    const xMaxTicks = (p === 'month') ? 6 : (p === 'week' ? 7 : 12);

    trendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: { labels: labels, datasets: datasets },
        options: {
            responsive: true, maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: '#e5e5eb', drawBorder: false },
                    ticks: {
                        callback: (v) => formatScaledTick(v, scale.divisor),
                        color: '#6c6c77',
                        font: { size: 11 }
                    },
                    title: {
                        display: !!scale.unit,
                        text: scale.unit ? `(${scale.unit})` : '',
                        color: '#6c6c77',
                        font: { size: 11, weight: 'bold' }
                    }
                },
                x: {
                    grid: { display: false, drawBorder: false },
                    ticks: {
                        color: '#6c6c77',
                        font: { size: 11 },
                        maxTicksLimit: xMaxTicks
                    }
                }
            },
            plugins: {
                legend: {
                    labels: { color: '#6c6c77', font: { size: 11, weight: 'bold' }, padding: 15 },
                    position: 'bottom'
                },
                tooltip: {
                    callbacks: {
                        title: (items) => {
                            if (!items || items.length === 0) return '';
                            const idx = items[0].dataIndex;

                            if (p === 'month' && tooltipTitles) {
                                return tooltipTitles[idx] || items[0].label || '';
                            }
                            if (p !== 'week') return items[0].label || '';

                            const day = new Date(currentAnchor);
                            const anchorDay = day.getDay();
                            const diff = day.getDate() - anchorDay + (anchorDay === 0 ? -6 : 1);
                            const start = new Date(day.getFullYear(), day.getMonth(), diff);
                            start.setDate(start.getDate() + idx);
                            return start.toLocaleDateString('vi-VN');
                        },
                        label: (ctx) => {
                            const val = ctx.parsed?.y ?? 0;
                            return `${ctx.dataset.label}: ${formatCurrencySafe(val)}`;
                        }
                    }
                }
            }
        }
    });
}

// CẬP NHẬT TOP DANH MỤC THEO THẺ ĐANG CHỌN
function renderTopCategories(curTxns, prevTxns, period) {
    const container = document.getElementById('topCategoriesContainer');
    const titleEl = document.getElementById('topCategoriesTitle');
    if (!container || !titleEl) return;

    const compareEnabled = !!document.getElementById('compareToggle')?.checked;
    const periodText = getPeriodVietnamese(period || currentPeriod);

    // Title
    if (currentMetric === 'income') titleEl.innerHTML = 'Danh mục (Thu nhập)';
    else if (currentMetric === 'expense') titleEl.innerHTML = 'Danh mục (Chi tiêu)';
    else titleEl.innerHTML = 'Danh mục (Chênh lệch)';

    const toValue = (t) => {
        if (currentMetric === 'income') return t.amount > 0 ? t.amount : 0;
        if (currentMetric === 'expense') return t.amount < 0 ? Math.abs(t.amount) : 0;
        return t.amount;
    };

    const sumByCategory = (txns) => {
        const map = {};
        (txns || []).forEach((t) => {
            const v = toValue(t);
            const key = t.category || 'Khác';
            map[key] = (map[key] || 0) + v;
        });
        return map;
    };

    const curMap = sumByCategory(curTxns);
    const prevMap = sumByCategory(prevTxns);

    const entries = Object.entries(curMap);
    entries.sort((a, b) => {
        if (currentMetric === 'balance') return Math.abs(b[1]) - Math.abs(a[1]);
        return b[1] - a[1];
    });

    if (entries.length === 0) {
        container.innerHTML = `<div style="text-align:center; color:#6c6c77; padding:15px;">Không có dữ liệu trong khoảng thời gian này</div>`;
        return;
    }

    container.innerHTML = entries.map(([name, curVal]) => {
        const prevVal = prevMap[name] || 0;
        const rawDelta = curVal - prevVal;
        const deltaAbs = Math.abs(rawDelta);
        const isIncrease = rawDelta >= 0;

        // good/bad coloring depending on metric
        let isGood = true;
        if (currentMetric === 'expense') isGood = !isIncrease;
        else isGood = isIncrease;

        const deltaColor = isGood ? '#1f9d55' : '#d97706';
        const arrow = isIncrease ? 'up' : 'down';

        const deltaLine = compareEnabled
            ? `<div style="margin-top: 6px; font-weight: 800; color: ${deltaColor}; display:flex; align-items:center; gap:8px; justify-content:flex-end;">
                    <i class="fa-solid fa-arrow-trend-${arrow}"></i>
                    <span>${formatCurrencySafe(deltaAbs)}</span>
                </div>
                <div style="margin-top: 2px; font-size: 0.85rem; color:#6c6c77; font-weight:700; text-align:right;">So với cùng kỳ ${periodText} trước</div>`
            : '';

        return `<div class="category-item">
            <div style="flex:1; display:flex; align-items:flex-start; justify-content:space-between; gap: 12px;">
                <div style="font-weight: 800; color:#2f2f36;">${name}</div>
                <div style="text-align:right; min-width: 120px;">
                    <div style="font-weight: 900; color:#2f2f36;">${formatCurrencySafe(curVal)}</div>
                    ${deltaLine}
                </div>
            </div>
        </div>`;
    }).join('');
}

function formatCurrencySafe(amount) {
    return new Intl.NumberFormat(userCurrency.locale, { style: 'currency', currency: userCurrency.code.toUpperCase() }).format(amount);
}