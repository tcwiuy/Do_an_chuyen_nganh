// ==========================================
// FILE: trend.js - BIỂU ĐỒ LỒNG NHAU & HIGHLIGHT CỘT & SỔ CHI TIẾT
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
var currentMetric = 'expense'; 
var currentAnchor = new Date(); 
var selectedBarIndex = null;
var lastBaseCategoryContext = { curTxns: [], prevTxns: [], period: 'month' };

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

function fmtDate(dateObj) {
    return `${String(dateObj.getDate()).padStart(2, '0')}/${String(dateObj.getMonth() + 1).padStart(2, '0')}/${dateObj.getFullYear()}`;
}

document.addEventListener('DOMContentLoaded', async () => {
    if (!document.getElementById('trendChart')) return;
    await loadCurrencyConfig();
    await fetchTransactionsForTrends();
    setupTrendEventListeners();
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

    document.getElementById('compareToggle')?.addEventListener('change', () => processAndRenderTrends(currentPeriod, currentAnchor));
    document.getElementById('prevPeriod')?.addEventListener('click', () => { moveAnchor(-1); });
    document.getElementById('nextPeriod')?.addEventListener('click', () => { moveAnchor(1); });

    const metricBtnIds = { income: 'btnMetricIncome', expense: 'btnMetricExpense', balance: 'btnMetricBalance' };
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

function escapeHtml(str) {
    return String(str).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;');
}

function getCssVar(name, fallback) {
    try {
        const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return v || fallback;
    } catch { return fallback; }
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

function moveAnchor(direction) {
    if (!currentAnchor) currentAnchor = new Date();
    const a = new Date(currentAnchor);
    if (currentPeriod === 'week') a.setDate(a.getDate() + (direction * 7));
    else if (currentPeriod === 'month') a.setMonth(a.getMonth() + direction);
    else a.setFullYear(a.getFullYear() + direction);
    currentAnchor = a;
    processAndRenderTrends(currentPeriod, currentAnchor);
}

// ==========================================
// TÍNH TOÁN DATA
// ==========================================
function processAndRenderTrends(period, anchorDate) {
    currentPeriod = period;
    const anchor = anchorDate ? new Date(anchorDate) : new Date();

    // 1. TÍNH TOÁN DỮ LIỆU GỐC CHO TỔNG BÊN TRÊN
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

    const curTxns = filterTxnsInRange(allTrendTransactions, cS, cE);
    const prevTxns = filterTxnsInRange(allTrendTransactions, pS, pE);

    // 2. TẠO CÁC CỤM THỜI GIAN ĐỂ VẼ BIỂU ĐỒ 
    const today = new Date();
    today.setHours(23, 59, 59, 999);
    
    const compareLabel = document.querySelector('.compare-inline');
    const compareToggle = document.getElementById('compareToggle');
    if (currentMetric === 'balance') {
        if (compareLabel) compareLabel.style.display = 'none';
        if (compareToggle) compareToggle.checked = false;
    } else {
        if (compareLabel) compareLabel.style.display = 'inline-flex';
    }
    const isCompareEnabled = currentMetric !== 'balance' && !!(compareToggle && compareToggle.checked);

    let buckets = [];
    let numBuckets = period === 'year' ? 5 : 6;

    for (let i = numBuckets - 1; i >= 0; i--) {
        let bS, bE, pBs, pBe;
        if (period === 'week') {
            let d = new Date(anchor); d.setDate(d.getDate() - i * 7);
            let dayOffset = d.getDay() === 0 ? -6 : 1 - d.getDay();
            bS = new Date(d.getFullYear(), d.getMonth(), d.getDate() + dayOffset); bS.setHours(0,0,0,0);
            bE = new Date(bS); bE.setDate(bS.getDate() + 6); bE.setHours(23,59,59,999);
            pBs = new Date(bS); pBs.setDate(pBs.getDate() - 7); pBs.setHours(0,0,0,0);
            pBe = new Date(bE); pBe.setDate(pBe.getDate() - 7); pBe.setHours(23,59,59,999);
        } else if (period === 'month') {
            bS = new Date(anchor.getFullYear(), anchor.getMonth() - i, 1); bS.setHours(0,0,0,0);
            bE = new Date(bS.getFullYear(), bS.getMonth() + 1, 0); bE.setHours(23,59,59,999);
            pBs = new Date(bS.getFullYear(), bS.getMonth() - 1, 1); pBs.setHours(0,0,0,0);
            pBe = new Date(pBs.getFullYear(), pBs.getMonth() + 1, 0); pBe.setHours(23,59,59,999);
        } else {
            bS = new Date(anchor.getFullYear() - i, 0, 1); bS.setHours(0,0,0,0);
            bE = new Date(bS.getFullYear(), 11, 31); bE.setHours(23,59,59,999);
            pBs = new Date(bS.getFullYear() - 1, 0, 1); pBs.setHours(0,0,0,0);
            pBe = new Date(pBs.getFullYear(), 11, 31); pBe.setHours(23,59,59,999);
        }

        // Logic "Cắt đến ngày hôm nay" để lồng vào trong biểu đồ
        let bCutoff = new Date(bE);
        if (isCompareEnabled) {
            if (period === 'week') {
                let daysPassed = today.getDay() === 0 ? 6 : today.getDay() - 1;
                bCutoff = new Date(bS); bCutoff.setDate(bS.getDate() + daysPassed);
            } else if (period === 'month') {
                let targetDate = Math.min(today.getDate(), new Date(bS.getFullYear(), bS.getMonth() + 1, 0).getDate());
                bCutoff = new Date(bS.getFullYear(), bS.getMonth(), targetDate);
            } else if (period === 'year') {
                let targetDate = Math.min(today.getDate(), new Date(bS.getFullYear(), today.getMonth() + 1, 0).getDate());
                bCutoff = new Date(bS.getFullYear(), today.getMonth(), targetDate);
            }
            bCutoff.setHours(23, 59, 59, 999);
        }

        let isCurrentPeriod = (today >= bS && today <= bE);
        let labelStr = "", titleStr = "";

        if (period === 'week') {
            let sStr = `${String(bS.getDate()).padStart(2,'0')}/${String(bS.getMonth()+1).padStart(2,'0')}`;
            let eStr = `${String(bE.getDate()).padStart(2,'0')}/${String(bE.getMonth()+1).padStart(2,'0')}`;
            labelStr = isCurrentPeriod ? 'Tuần này' : `${sStr} - ${eStr}`;
            titleStr = `${sStr} - ${eStr}`;
        } else if (period === 'month') {
            labelStr = isCurrentPeriod ? 'Tháng này' : `T${bS.getMonth()+1}`;
            titleStr = `Tháng ${bS.getMonth()+1}/${bS.getFullYear()}`;
        } else {
            labelStr = isCurrentPeriod ? 'Năm nay' : `${bS.getFullYear()}`;
            titleStr = `Năm ${bS.getFullYear()}`;
        }

        let sumFull = filterTxnsInRange(allTrendTransactions, bS, bE).reduce((acc, t) => acc + metricContribution(t.amount), 0);
        let sumCutoff = filterTxnsInRange(allTrendTransactions, bS, bCutoff).reduce((acc, t) => acc + metricContribution(t.amount), 0);

        buckets.push({ start: bS, end: bE, prevStart: pBs, prevEnd: pBe, cutoff: bCutoff, label: labelStr, title: titleStr, sumFull, sumCutoff });
    }

    const sum = (arr) => arr.reduce((acc, t) => ({ inc: acc.inc + (t.amount > 0 ? t.amount : 0), exp: acc.exp + (t.amount < 0 ? Math.abs(t.amount) : 0) }), { inc: 0, exp: 0 });
    
    updateTotalBlock(sum(curTxns), sum(prevTxns), period);
    updatePeriodLabel(period, anchor);
    lastBaseCategoryContext = { curTxns, prevTxns, period };
    selectedBarIndex = null;

    updateChartFromSeries(
        buckets.map(b => b.label),
        buckets.map(b => b.sumFull),
        buckets.map(b => b.sumCutoff),
        period,
        { segments: buckets },
        isCompareEnabled
    );
    renderTopCategories(curTxns, prevTxns, period, null);
}

const verticalLinePlugin = {
    id: 'verticalLine',
    afterDraw: chart => {
        if (chart.tooltip?._active?.length) {
            let activePoint = chart.tooltip._active[0];
            let ctx = chart.ctx;
            ctx.save();
            ctx.beginPath();
            ctx.moveTo(activePoint.element.x, activePoint.element.y);
            ctx.lineTo(activePoint.element.x, chart.scales.y.bottom);
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = '#cce3ff';
            ctx.setLineDash([4, 4]);
            ctx.stroke();
            ctx.restore();
        }
    }
};

// ==========================================
// VẼ BIỂU ĐỒ (HIGHLIGHT CỘT ĐƯỢC CHỌN)
// ==========================================
function updateChartFromSeries(labels, fullData, cutoffData, period, meta, isCompareEnabled) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    if (trendChartInstance) trendChartInstance.destroy();

    const themeAccent = getCssVar('--accent', '#69afde');
    const themeBorder = getCssVar('--border', '#1a365d');
    const themeTick = getCssVar('--text-secondary', '#b3b3b3');

    // MÀU GỐC
    const baseColorFull = currentMetric === 'expense' ? '#fca5a5' : currentMetric === 'income' ? '#86efac' : hexToRgba(themeAccent, 0.45);
    const baseColorCutoff = currentMetric === 'expense' ? '#ef4444' : currentMetric === 'income' ? '#22c55e' : themeAccent;

    // MÀU MỜ (KHI CÓ 1 CỘT KHÁC ĐANG ĐƯỢC CLICK)
    const fadedColorFull = currentMetric === 'expense' ? 'rgba(252, 165, 165, 0.3)' : currentMetric === 'income' ? 'rgba(134, 239, 172, 0.3)' : hexToRgba(themeAccent, 0.15);
    const fadedColorCutoff = currentMetric === 'expense' ? 'rgba(239, 68, 68, 0.3)' : currentMetric === 'income' ? 'rgba(34, 197, 94, 0.3)' : hexToRgba(themeAccent, 0.3);

    const datasets = [{
        label: 'Cả kỳ',
        data: fullData,
        backgroundColor: function(context) {
            // Logic Nổi bật: Nếu chưa chọn gì hoặc đang trúng cột được chọn => Hiển thị màu rõ
            if (selectedBarIndex === null || selectedBarIndex === context.dataIndex) return baseColorFull;
            return fadedColorFull; // Mờ đi
        },
        grouped: false, // Bắt buộc false để cột đè lên nhau cùng 1 tọa độ X
        order: 2, // Nằm Dưới
        barPercentage: 0.6, // BẰNG NHAU
        categoryPercentage: 0.8,
        borderRadius: { topLeft: 4, topRight: 4 },
        borderSkipped: false
    }];

    if (isCompareEnabled) {
        datasets.push({
            label: 'Đến ngày hiện tại',
            data: cutoffData,
            backgroundColor: function(context) {
                if (selectedBarIndex === null || selectedBarIndex === context.dataIndex) return baseColorCutoff;
                return fadedColorCutoff;
            },
            grouped: false,
            order: 1, // Nằm Đè Lên Trên
            barPercentage: 0.6, // BẰNG NHAU (Lồng khít)
            categoryPercentage: 0.8,
            borderRadius: { topLeft: 4, topRight: 4 },
            borderSkipped: false
        });
    }

    const maxAbs = Math.max(...fullData, ...(isCompareEnabled ? cutoffData : [0]));
    const scale = getScaleUnit(maxAbs);

    trendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: { labels: labels, datasets: datasets },
        plugins: [verticalLinePlugin],
        options: {
            // SỬ DỤNG SỰ KIỆN CHUẨN CỦA CHARTJS CHO CHÍNH XÁC 100%
            onClick: (evt, elements) => {
                // Bấm ra ngoài -> Hủy Chọn
                if (!elements || elements.length === 0) {
                    if (selectedBarIndex !== null) {
                        selectedBarIndex = null;
                        trendChartInstance.update();
                        renderTopCategories(lastBaseCategoryContext.curTxns, lastBaseCategoryContext.prevTxns, lastBaseCategoryContext.period, null);
                    }
                    return;
                }

                const idx = elements[0].index;
                
                // Bấm lại đúng cột đang chọn -> Hủy Chọn
                if (selectedBarIndex === idx) {
                    selectedBarIndex = null;
                    trendChartInstance.update();
                    renderTopCategories(lastBaseCategoryContext.curTxns, lastBaseCategoryContext.prevTxns, lastBaseCategoryContext.period, null);
                    return;
                }

                // CHỌN CỘT MỚI
                selectedBarIndex = idx;
                trendChartInstance.update(); // Làm mờ các cột khác
                
                const seg = meta.segments[idx];
                const segCur = filterTxnsInRange(allTrendTransactions, seg.start, seg.end);
                const segPrev = filterTxnsInRange(allTrendTransactions, seg.prevStart, seg.prevEnd);
                renderTopCategories(segCur, segPrev, period, seg.title);
            },
            responsive: true, maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: themeBorder, drawBorder: false },
                    ticks: { callback: (v) => formatScaledTick(v, scale.divisor), color: themeTick, font: { size: 11 } }
                },
                x: {
                    grid: { display: false, drawBorder: false },
                    ticks: { color: themeTick, font: { size: 11 } }
                }
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: 'white', titleColor: '#888', bodyColor: baseColorCutoff, borderColor: themeBorder, borderWidth: 1, padding: 10,
                    callbacks: {
                        title: (items) => meta.segments[items[0].dataIndex].title,
                        label: (ctx) => {
                            const seg = meta.segments[ctx.dataIndex];
                            if (ctx.datasetIndex === 0) {
                                return `Tổng cả kỳ: ${formatCurrencySafe(ctx.parsed.y)}`;
                            } else {
                                const dStr = `${String(seg.cutoff.getDate()).padStart(2,'0')}/${String(seg.cutoff.getMonth()+1).padStart(2,'0')}`;
                                return `Tính đến (${dStr}): ${formatCurrencySafe(ctx.parsed.y)}`;
                            }
                        }
                    }
                }
            }
        }
    });

    // Bỏ canvas.onclick để tránh xung đột với Chart.js click
    const canvas = document.getElementById('trendChart');
    if (canvas) { canvas.style.cursor = 'pointer'; }
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

    let curVal = 0; let prevVal = 0; let label = '';

    if (currentMetric === 'income') { curVal = cur.inc; prevVal = prev.inc; label = `Tổng thu ${periodText} này`; } 
    else if (currentMetric === 'expense') { curVal = cur.exp; prevVal = prev.exp; label = `Tổng chi ${periodText} này`; } 
    else { curVal = currentBalance; prevVal = previousBalance; label = `Tổng chênh lệch ${periodText} này`; }

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
        label = startMonth === endMonth ? `${startDay} - ${endDay} ${startMonth}` : `${startDay} ${startMonth} - ${endDay} ${endMonth}`;
    } else if (period === 'month') {
        label = `${a.toLocaleString(userCurrency.locale, { month: 'long', year: 'numeric' })}`;
    } else {
        label = `${a.getFullYear()}`;
    }
    el.innerHTML = `<strong>${label}</strong><br><span style="font-size:0.8rem; opacity:0.7;">So với cùng kỳ</span>`;
}

// KHAI BÁO BIẾN TOÀN CỤC ĐỂ TOGGLE SỔ DANH SÁCH CHI TIẾT
window.toggleCategoryDetails = function(categoryNameId) {
    const detailDiv = document.getElementById(categoryNameId);
    if (detailDiv) {
        if (detailDiv.style.display === 'none') {
            detailDiv.style.display = 'block';
        } else {
            detailDiv.style.display = 'none';
        }
    }
};

// ==========================================
// GIAO DIỆN DANH MỤC CÓ TÍNH NĂNG CLICK ĐỂ SỔ RA CHI TIẾT
// ==========================================
function renderTopCategories(curTxns, prevTxns, period, titleSuffix) {
    const container = document.getElementById('topCategoriesContainer');
    const titleEl = document.getElementById('topCategoriesTitle');
    if (!container || !titleEl) return;

    const periodText = getPeriodVietnamese(period || currentPeriod);

    let baseTitle = '';
    if (currentMetric === 'income') baseTitle = 'Danh mục (Thu nhập)';
    else if (currentMetric === 'expense') baseTitle = 'Danh mục (Chi tiêu)';
    else baseTitle = 'Danh mục (Chênh lệch)';

    if (titleSuffix) {
        titleEl.innerHTML = `${baseTitle} <span style="font-size: 0.85rem; color: var(--text-secondary); font-weight:700;">— Đang xem: ${escapeHtml(titleSuffix)}</span>`;
    } else {
        titleEl.innerHTML = baseTitle;
    }

    const toValue = (t) => {
        if (currentMetric === 'income') return t.amount > 0 ? t.amount : 0;
        if (currentMetric === 'expense') return t.amount < 0 ? Math.abs(t.amount) : 0;
        return t.amount;
    };

    // Nhóm giao dịch và lưu chi tiết để Sổ Ra
    const categoryGroups = {};
    const prevMap = {};

    (curTxns || []).forEach(t => {
        const v = toValue(t);
        if (v === 0) return;
        const key = t.category || 'Khác';
        if (!categoryGroups[key]) categoryGroups[key] = { total: 0, txns: [] };
        categoryGroups[key].total += v;
        categoryGroups[key].txns.push(t);
    });

    (prevTxns || []).forEach(t => {
        const v = toValue(t);
        if (v === 0) return;
        const key = t.category || 'Khác';
        prevMap[key] = (prevMap[key] || 0) + v;
    });

    const entries = Object.entries(categoryGroups);
    entries.sort((a, b) => {
        if (currentMetric === 'balance') return Math.abs(b[1].total) - Math.abs(a[1].total);
        return b[1].total - a[1].total;
    });

    if (entries.length === 0) {
        container.innerHTML = `<div style="text-align:center; color: var(--text-secondary); padding:15px;">Không có dữ liệu trong khoảng thời gian này</div>`;
        return;
    }

    container.innerHTML = entries.map(([name, dataObj], index) => {
        const curVal = dataObj.total;
        const prevVal = prevMap[name] || 0;
        const rawDelta = curVal - prevVal;
        const deltaAbs = Math.abs(rawDelta);
        const isIncrease = rawDelta >= 0;

        let isGood = true;
        if (currentMetric === 'expense') isGood = !isIncrease;
        else isGood = isIncrease;

        const deltaColor = isGood ? '#1f9d55' : '#d97706';
        const arrow = isIncrease ? 'up' : 'down';

        const deltaLine = (curVal !== 0 || prevVal !== 0)
            ? `<div style="margin-top: 6px; font-weight: 800; color: ${deltaColor}; display:flex; align-items:center; gap:8px; justify-content:flex-end;">
                    <i class="fa-solid fa-arrow-trend-${arrow}"></i>
                    <span>${formatCurrencySafe(deltaAbs)}</span>
                </div>
                <div style="margin-top: 2px; font-size: 0.85rem; color: var(--text-secondary); font-weight:700; text-align:right;">So với cùng kỳ ${periodText} trước</div>`
            : '';

        const safeId = 'cat-detail-' + index;

        // Render các giao dịch chi tiết (Ẩn mặc định)
        const detailsHtml = dataObj.txns.sort((a, b) => new Date(b.date) - new Date(a.date)).map(t => {
            const d = new Date(t.date);
            return `<div style="display:flex; justify-content:space-between; align-items:center; padding: 12px 16px; border-top: 1px solid var(--border); font-size: 0.95rem;">
                        <div>
                            <div style="color: var(--text-primary); font-weight: 600;">${escapeHtml(t.note || 'Không có ghi chú')}</div>
                            <div style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 4px;">${fmtDate(d)}</div>
                        </div>
                        <div style="font-weight: bold; color: var(--text-primary);">${formatCurrencySafe(toValue(t))}</div>
                    </div>`;
        }).join('');

        return `
        <div style="margin-bottom: 10px;">
            <div class="trend-category-item" style="cursor: pointer; margin-bottom: 0;" onclick="toggleCategoryDetails('${safeId}')">
                <div style="flex:1; display:flex; align-items:flex-start; justify-content:space-between; gap: 12px;">
                    <div style="font-weight: 800; color: var(--text-primary);">${escapeHtml(name)}</div>
                    <div style="text-align:right; min-width: 120px;">
                        <div style="font-weight: 900; color: var(--text-primary);">${formatCurrencySafe(curVal)}</div>
                        ${deltaLine}
                    </div>
                </div>
            </div>
            <div id="${safeId}" style="display: none; background: var(--bg-primary); border: 1px solid var(--border); border-top: none; border-radius: 0 0 16px 16px; margin-top: -8px; padding-top: 8px;">
                ${detailsHtml}
            </div>
        </div>`;
    }).join('');
}

function formatCurrencySafe(amount) {
    return new Intl.NumberFormat(userCurrency.locale, { style: 'currency', currency: userCurrency.code.toUpperCase() }).format(amount);
}