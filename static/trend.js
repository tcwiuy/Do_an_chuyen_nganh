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

// chart interaction state
var selectedBarIndex = null;
var lastBaseCategoryContext = { curTxns: [], prevTxns: [], period: 'month' };

var userCurrency = { code: 'VND', locale: 'vi-VN', rate: 1.0 };

// 💡 BIẾN TOÀN CỤC CHỨA KHO DANH MỤC VÀ MÀU SẮC
let initialCategories = [];
let categoryColors = {};
const colorPalette = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#F7464A', '#8a2be2'];

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
            
            // 💡 1. NẠP KHO DANH MỤC MỚI TỪ BACKEND
            let expenseCategories = [];
            let incomeCategories = [];
            
            if (config.expenseCategories && config.incomeCategories) {
                expenseCategories = config.expenseCategories;
                incomeCategories = config.incomeCategories;
            } else if (config.categories) {
                expenseCategories = config.categories;
                incomeCategories = ["Lương", "Thưởng", "Đầu tư", "Khác"];
            }
            initialCategories = [...expenseCategories, ...incomeCategories];
        }
        
        const localeMap = { 'vnd': 'vi-VN', 'usd': 'en-US', 'eur': 'de-DE', 'jpy': 'ja-JP' };
        userCurrency.locale = localeMap[userCurrency.code] || 'en-US';
        const rateToVnd = window.exchangeRatesToVND[userCurrency.code] || 1;
        userCurrency.rate = 1 / rateToVnd;
    } catch (e) { console.warn("Dùng mặc định VND.", e); }
}

async function fetchTransactionsForTrends() {
    try {
        const token = localStorage.getItem('token');
        const response = await fetch('/api/expenses/', { headers: { 'Authorization': `Bearer ${token}` } });
        if (response.ok) {
            const rawTxns = await response.json();
            
            // 💡 2. THUẬT TOÁN TỰ ĐỘNG ÉP KIỂU CHỮ HOA/THƯỜNG (AUTO-HEAL)
            allTrendTransactions = rawTxns.map(t => {
                let catName = t.category || 'Khác';
                const exactMatch = initialCategories.find(c => c === catName);
                if (!exactMatch) {
                    const lowerMatch = initialCategories.find(c => c.toLowerCase() === catName.toLowerCase());
                    if (lowerMatch) {
                        catName = lowerMatch;
                    }
                }
                return { ...t, amount: t.amount * userCurrency.rate, category: catName };
            });
            
            // 💡 3. NẠP BẢNG MÀU TỪ LOCALSTORAGE
            const savedColors = JSON.parse(localStorage.getItem('customCategoryColors') || '{}');
            const uniqueCategories = [...new Set(allTrendTransactions.map(exp => exp.category))];
            initialCategories.forEach(c => { if(!uniqueCategories.includes(c)) uniqueCategories.push(c); });
            
            uniqueCategories.forEach((category, index) => {
                if (savedColors[category]) { 
                    categoryColors[category] = savedColors[category]; 
                } else {
                    const foundKey = Object.keys(savedColors).find(k => k.toLowerCase() === category.toLowerCase());
                    if (foundKey) {
                        categoryColors[category] = savedColors[foundKey];
                    } else if (!categoryColors[category]) { 
                        categoryColors[category] = colorPalette[index % colorPalette.length] || "#8a2be2"; 
                    }
                }
            });
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

function filterTxnsInRange(txns, start, end) {
    const s = start.getTime();
    const e = end.getTime();
    return (txns || []).filter((t) => {
        const d = new Date(t.date.split('T')[0] + 'T00:00:00').getTime();
        return d >= s && d <= e;
    });
}

function formatMonthYear(date) {
    const d = new Date(date);
    return `${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;
}

function escapeHtml(str) {
    return String(str)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function getCssVar(name, fallback) {
    try {
        const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return v || fallback;
    } catch {
        return fallback;
    }
}

function hexToRgba(hex, alpha) {
    const h = String(hex || '').trim();
    const m = h.match(/^#?([0-9a-f]{6})$/i);
    if (!m) return h;
    const int = parseInt(m[1], 16);
    const r = (int >> 16) & 255;
    const g = (int >> 8) & 255;
    const b = int & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
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
    let segments = [];

    if (period === 'week') {
        for (let i = 0; i < 7; i++) {
            const d = new Date(cS); d.setDate(cS.getDate() + i);
            labels.push(getWeekdayLabel(d));
            const segStart = new Date(d); segStart.setHours(0, 0, 0, 0);
            const segEnd = new Date(d); segEnd.setHours(23, 59, 59, 999);

            const pd = new Date(pS); pd.setDate(pS.getDate() + i);
            const prevStart = new Date(pd); prevStart.setHours(0, 0, 0, 0);
            const prevEnd = new Date(pd); prevEnd.setHours(23, 59, 59, 999);

            segments.push({
                start: segStart,
                end: segEnd,
                prevStart,
                prevEnd,
                title: segStart.toLocaleDateString('vi-VN')
            });
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

            segments.push({
                start,
                end,
                prevStart,
                prevEnd,
                title: formatMonthYear(start)
            });
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

            const start = new Date(anchor.getFullYear(), m, 1); start.setHours(0, 0, 0, 0);
            const end = new Date(anchor.getFullYear(), m + 1, 0); end.setHours(23, 59, 59, 999);
            const prevStart = new Date(anchor.getFullYear() - 1, m, 1); prevStart.setHours(0, 0, 0, 0);
            const prevEnd = new Date(anchor.getFullYear() - 1, m + 1, 0); prevEnd.setHours(23, 59, 59, 999);

            segments.push({
                start,
                end,
                prevStart,
                prevEnd,
                title: formatMonthYear(start)
            });
        }
    }

    const sum = (arr) => arr.reduce((acc, t) => ({
        inc: acc.inc + (t.amount > 0 ? t.amount : 0),
        exp: acc.exp + (t.amount < 0 ? Math.abs(t.amount) : 0)
    }), { inc: 0, exp: 0 });
    const curSum = sum(curTxns);
    const prevSum = sum(prevTxns);

    updateTotalBlock(curSum, prevSum, period);
    // Base context for category list (when no bar selected)
    lastBaseCategoryContext = { curTxns, prevTxns, period };
    selectedBarIndex = null;

    updateChartFromSeries(labels, curSeries, prevSeries, period, { tooltipTitles, segments });
    renderTopCategories(curTxns, prevTxns, period, null);
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

    const rawDelta = curVal - prevVal;
    const deltaAbs = Math.abs(rawDelta);
    const isIncrease = rawDelta >= 0;
    const arrow = isIncrease ? '<i class="fa-solid fa-arrow-trend-up"></i>' : '<i class="fa-solid fa-arrow-trend-down"></i>';

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

function aggregateByMetricForKey(value) {
    if (currentMetric === 'income') return Math.max(0, value);
    if (currentMetric === 'expense') return Math.abs(Math.min(0, value));
    return value; 
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

function updateChartFromSeries(labels, curData, prevData, period, meta) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    if (trendChartInstance) trendChartInstance.destroy();

    const themeAccent = getCssVar('--accent', '#69afde');
    const themeBorder = getCssVar('--border', '#1a365d');
    const themeTick = getCssVar('--text-secondary', '#b3b3b3');

    const colorCur = currentMetric === 'expense' ? '#f87171' : currentMetric === 'income' ? '#4ade80' : themeAccent;
    const colorPrev = currentMetric === 'expense' ? '#fca5a5' : currentMetric === 'income' ? '#86efac' : hexToRgba(themeAccent, 0.45);

    const p = period || currentPeriod;
    const periodText = getPeriodVietnamese(p);
    const tooltipTitles = meta?.tooltipTitles || null;
    const segments = meta?.segments || [];

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

    const xMaxTicks = (p === 'month') ? 6 : (p === 'week' ? 7 : 12);

    const handleClick = (evt) => {
        if (!trendChartInstance) return;
        const nativeEvt = (evt && evt.native) ? evt.native : evt;
        let points = trendChartInstance.getElementsAtEventForMode(nativeEvt, 'nearest', { intersect: true }, true);

        if ((!points || points.length === 0) && nativeEvt && nativeEvt.clientX != null && nativeEvt.clientY != null) {
            const rect = trendChartInstance.canvas?.getBoundingClientRect?.();
            if (rect) {
                const x = nativeEvt.clientX - rect.left;
                const y = nativeEvt.clientY - rect.top;
                points = trendChartInstance.getElementsAtEventForMode({ native: nativeEvt, x, y }, 'nearest', { intersect: true }, true);
            }
        }

        if (!points || points.length === 0) {
            if (selectedBarIndex !== null) {
                selectedBarIndex = null;
                renderTopCategories(lastBaseCategoryContext.curTxns, lastBaseCategoryContext.prevTxns, lastBaseCategoryContext.period, null);
            }
            return;
        }

        const idx = points[0].index;

        if (selectedBarIndex === idx) {
            selectedBarIndex = null;
            renderTopCategories(lastBaseCategoryContext.curTxns, lastBaseCategoryContext.prevTxns, lastBaseCategoryContext.period, null);
            return;
        }

        selectedBarIndex = idx;
        const seg = segments[idx];
        if (!seg) return;

        const segCur = filterTxnsInRange(allTrendTransactions, seg.start, seg.end);
        const segPrev = filterTxnsInRange(allTrendTransactions, seg.prevStart, seg.prevEnd);
        renderTopCategories(segCur, segPrev, p, seg.title || labels[idx] || null);
    };

    trendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: { labels: labels, datasets: datasets },
        options: {
            onClick: handleClick,
            responsive: true, maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: themeBorder, drawBorder: false },
                    ticks: {
                        callback: (v) => formatScaledTick(v, scale.divisor),
                        color: themeTick,
                        font: { size: 11 }
                    },
                    title: {
                        display: !!scale.unit,
                        text: scale.unit ? `(${scale.unit})` : '',
                        color: themeTick,
                        font: { size: 11, weight: 'bold' }
                    }
                },
                x: {
                    grid: { display: false, drawBorder: false },
                    ticks: {
                        color: themeTick,
                        font: { size: 11 },
                        maxTicksLimit: xMaxTicks
                    }
                }
            },
            plugins: {
                legend: {
                    labels: { color: themeTick, font: { size: 11, weight: 'bold' }, padding: 15 },
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

    const canvas = document.getElementById('trendChart');
    if (canvas) {
        canvas.style.cursor = 'pointer';
        canvas.onclick = handleClick;
    }
}

// CẬP NHẬT TOP DANH MỤC (ĐÃ SỬA LẠI ĐỂ ĐỌC MÀU SẮC CHUẨN XÁC)
function renderTopCategories(curTxns, prevTxns, period, titleSuffix) {
    const container = document.getElementById('topCategoriesContainer');
    const titleEl = document.getElementById('topCategoriesTitle');
    if (!container || !titleEl) return;

    const compareEnabled = !!document.getElementById('compareToggle')?.checked;
    const periodText = getPeriodVietnamese(period || currentPeriod);

    let baseTitle = '';
    if (currentMetric === 'income') baseTitle = 'Danh mục (Thu nhập)';
    else if (currentMetric === 'expense') baseTitle = 'Danh mục (Chi tiêu)';
    else baseTitle = 'Danh mục (Chênh lệch)';

    if (titleSuffix) {
        titleEl.innerHTML = `${baseTitle} <span style="font-size: 0.85rem; color: var(--text-secondary); font-weight:700;">— ${escapeHtml(titleSuffix)}</span>`;
    } else {
        titleEl.innerHTML = baseTitle;
    }

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
        container.innerHTML = `<div style="text-align:center; color: var(--text-secondary); padding:15px;">Không có dữ liệu trong khoảng thời gian này</div>`;
        return;
    }

    container.innerHTML = entries.map(([name, curVal]) => {
        const prevVal = prevMap[name] || 0;
        const rawDelta = curVal - prevVal;
        const deltaAbs = Math.abs(rawDelta);
        const isIncrease = rawDelta >= 0;

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
                <div style="margin-top: 2px; font-size: 0.85rem; color: var(--text-secondary); font-weight:700; text-align:right;">So với cùng kỳ ${periodText} trước</div>`
            : '';

        // 💡 Lấy màu sắc chuẩn xác từ categoryColors (Hoặc màu mặc định nếu không có)
        const catColor = categoryColors[name] || '#8a2be2';

        return `<div class="trend-category-item" style="border-left: 5px solid ${catColor};">
            <div style="flex:1; display:flex; align-items:flex-start; justify-content:space-between; gap: 12px;">
                <div style="font-weight: 800; color: var(--text-primary); display: flex; align-items: center; gap: 10px;">
                    <div style="width: 12px; height: 12px; border-radius: 50%; background-color: ${catColor};"></div>
                    ${name}
                </div>
                <div style="text-align:right; min-width: 120px;">
                    <div style="font-weight: 900; color: var(--text-primary);">${formatCurrencySafe(curVal)}</div>
                    ${deltaLine}
                </div>
            </div>
        </div>`;
    }).join('');
}

function formatCurrencySafe(amount) {
    return new Intl.NumberFormat(userCurrency.locale, { style: 'currency', currency: userCurrency.code.toUpperCase() }).format(amount);
}