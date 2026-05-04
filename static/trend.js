// ==========================================
// FILE: trend.js - TỔNG HỢP: BIỂU ĐỒ LỒNG NHAU, HIGHLIGHT, CHI TIẾT & MÀU SẮC ĐỘNG
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
var compareAnchorIndex = null; // 💡 LƯU TRỮ CỘT LÀM MỐC KHI BẬT TÍNH NĂNG SO SÁNH
var userCurrency = { code: 'VND', locale: 'vi-VN', rate: 1.0 };

// BIẾN TOÀN CỤC CHỨA KHO DANH MỤC VÀ MÀU SẮC
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

function resetCompareState() {
    compareAnchorIndex = null;
    const toggle = document.getElementById('compareToggle');
    if (toggle) toggle.checked = false;
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
            resetCompareState(); // Reset trạng thái khi đổi tab
            processAndRenderTrends(period, currentAnchor);
        });
    });

    // 💡 LOGIC NÚT TOGGLE THÔNG MINH
    document.getElementById('compareToggle')?.addEventListener('change', (e) => {
        if (e.target.checked) {
            // Khi Bật: Lấy cột đang chọn làm mốc. Nếu chưa chọn cột nào, lấy cột cuối cùng.
            compareAnchorIndex = selectedBarIndex !== null ? selectedBarIndex : (currentPeriod === 'year' ? 4 : 5);
        } else {
            // Khi Tắt: Gỡ mốc
            compareAnchorIndex = null;
        }
        processAndRenderTrends(currentPeriod, currentAnchor);
    });

    document.getElementById('prevPeriod')?.addEventListener('click', () => { 
        resetCompareState(); 
        moveAnchor(-1); 
    });
    document.getElementById('nextPeriod')?.addEventListener('click', () => { 
        resetCompareState(); 
        moveAnchor(1); 
    });

    const metricBtnIds = { income: 'btnMetricIncome', expense: 'btnMetricExpense', balance: 'btnMetricBalance' };
    const setActiveMetricBtn = (metric) => {
        Object.values(metricBtnIds).forEach((id) => document.getElementById(id)?.classList.remove('active'));
        document.getElementById(metricBtnIds[metric])?.classList.add('active');
    };

    Object.entries(metricBtnIds).forEach(([metric, id]) => {
        document.getElementById(id)?.addEventListener('click', () => {
            currentMetric = metric;
            setActiveMetricBtn(metric);
            resetCompareState();
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

function getRelativeCutoffDate(bS, today, period) {
    let cutoff = new Date(bS);
    if (period === 'week') {
        let daysPassed = today.getDay() === 0 ? 6 : today.getDay() - 1; 
        cutoff.setDate(bS.getDate() + daysPassed);
    } else if (period === 'month') {
        let targetDate = Math.min(today.getDate(), new Date(bS.getFullYear(), bS.getMonth() + 1, 0).getDate());
        cutoff = new Date(bS.getFullYear(), bS.getMonth(), targetDate);
    } else if (period === 'year') {
        let targetDate = Math.min(today.getDate(), new Date(bS.getFullYear(), today.getMonth() + 1, 0).getDate());
        cutoff = new Date(bS.getFullYear(), today.getMonth(), targetDate);
    }
    cutoff.setHours(23, 59, 59, 999);
    return cutoff;
}

// ==========================================
// TÍNH TOÁN DATA VÀ CẮT THỜI GIAN (LOGIC PIN GHI NHỚ)
// ==========================================
function processAndRenderTrends(period, anchorDate) {
    currentPeriod = period;
    const anchor = anchorDate ? new Date(anchorDate) : new Date();
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
        let bS, bE;
        if (period === 'week') {
            let d = new Date(anchor); d.setDate(d.getDate() - i * 7);
            let dayOffset = d.getDay() === 0 ? -6 : 1 - d.getDay();
            bS = new Date(d.getFullYear(), d.getMonth(), d.getDate() + dayOffset); bS.setHours(0,0,0,0);
            bE = new Date(bS); bE.setDate(bS.getDate() + 6); bE.setHours(23,59,59,999);
        } else if (period === 'month') {
            bS = new Date(anchor.getFullYear(), anchor.getMonth() - i, 1); bS.setHours(0,0,0,0);
            bE = new Date(bS.getFullYear(), bS.getMonth() + 1, 0); bE.setHours(23,59,59,999);
        } else {
            bS = new Date(anchor.getFullYear() - i, 0, 1); bS.setHours(0,0,0,0);
            bE = new Date(bS.getFullYear(), 11, 31); bE.setHours(23,59,59,999);
        }

        let isCurrentBucket = (today >= bS && today <= bE);
        let labelStr = "", titleStr = "";

        if (period === 'week') {
            let sStr = `${String(bS.getDate()).padStart(2,'0')}/${String(bS.getMonth()+1).padStart(2,'0')}`;
            let eStr = `${String(bE.getDate()).padStart(2,'0')}/${String(bE.getMonth()+1).padStart(2,'0')}`;
            labelStr = isCurrentBucket ? 'Tuần này' : `${sStr} - ${eStr}`;
            titleStr = `${sStr} - ${eStr}`;
        } else if (period === 'month') {
            labelStr = isCurrentBucket ? 'Tháng này' : `T${bS.getMonth()+1}`;
            titleStr = `Tháng ${bS.getMonth()+1}/${bS.getFullYear()}`;
        } else {
            labelStr = isCurrentBucket ? 'Năm nay' : `${bS.getFullYear()}`;
            titleStr = `Năm ${bS.getFullYear()}`;
        }

        let sumFull = filterTxnsInRange(allTrendTransactions, bS, bE).reduce((acc, t) => acc + metricContribution(t.amount), 0);
        
        buckets.push({ 
            start: bS, end: bE, 
            isCurrent: isCurrentBucket,
            label: labelStr, title: titleStr, 
            sumFull: sumFull, sumCutoff: sumFull, cutoffDate: null
        });
    }

    // 💡 XÁC ĐỊNH MỐC CẮT XÉN THEO BIẾN `compareAnchorIndex` ĐÃ LƯU
    let anchorIdxForCutoff = compareAnchorIndex !== null ? compareAnchorIndex : (buckets.length - 1);
    let anchorBucketForCutoff = buckets[anchorIdxForCutoff];

    if (isCompareEnabled) {
        for (let j = 0; j < buckets.length; j++) {
            if (anchorBucketForCutoff && anchorBucketForCutoff.isCurrent) {
                // Rule 1: Mốc được ghim là Tháng Hiện Tại -> Cắt xén tất cả theo ngày hiện tại
                let cutoffDate = getRelativeCutoffDate(buckets[j].start, today, period);
                buckets[j].cutoffDate = cutoffDate;
                if (cutoffDate < buckets[j].end) {
                    buckets[j].sumCutoff = filterTxnsInRange(allTrendTransactions, buckets[j].start, cutoffDate).reduce((acc, t) => acc + metricContribution(t.amount), 0);
                } else {
                    buckets[j].sumCutoff = buckets[j].sumFull;
                }
            } else {
                // Rule 2: Mốc được ghim là Tháng Cũ -> So sánh nguyên kỳ (100% == 100%)
                buckets[j].cutoffDate = buckets[j].end;
                buckets[j].sumCutoff = buckets[j].sumFull;
            }
        }
    }

    let targetIdx = selectedBarIndex !== null ? selectedBarIndex : (buckets.length - 1);
    let targetBucket = buckets[targetIdx];

    let curTxns = filterTxnsInRange(allTrendTransactions, targetBucket.start, targetBucket.end);
    let prevTxns = [];
    let useCutoffForStats = false;
    
    if (targetIdx > 0) {
        let compareBucket = buckets[targetIdx - 1];
        if (isCompareEnabled) {
            // Khi compare bật, bảng thống kê bên dưới sẽ lấy dữ liệu dựa trên Rule cắt xén đã tính ở trên
            prevTxns = filterTxnsInRange(allTrendTransactions, compareBucket.start, compareBucket.cutoffDate);
            useCutoffForStats = true;
        } else {
            prevTxns = filterTxnsInRange(allTrendTransactions, compareBucket.start, compareBucket.end);
        }
    }

    const sum = (arr) => arr.reduce((acc, t) => ({ inc: acc.inc + (t.amount > 0 ? t.amount : 0), exp: acc.exp + (t.amount < 0 ? Math.abs(t.amount) : 0) }), { inc: 0, exp: 0 });
    
    updateTotalBlock(sum(curTxns), sum(prevTxns), period, useCutoffForStats);
    updatePeriodLabel(period, anchor);

    updateChartFromSeries(buckets, targetIdx, isCompareEnabled, period);
    renderTopCategories(curTxns, prevTxns, period, targetBucket.title, useCutoffForStats);
}

// ==========================================
// VẼ BIỂU ĐỒ (CỐ ĐỊNH TOOLTIP CHỐNG CHỚP TẮT)
// ==========================================
function updateChartFromSeries(buckets, targetIdx, isCompareEnabled, period) {
    const ctx = document.getElementById('trendChart').getContext('2d');
    if (trendChartInstance) trendChartInstance.destroy();

    const themeAccent = getCssVar('--accent', '#69afde');
    const themeBorder = getCssVar('--border', '#1a365d');
    const themeTick = getCssVar('--text-secondary', '#b3b3b3');

    const baseColorFull = currentMetric === 'expense' ? '#fca5a5' : currentMetric === 'income' ? '#86efac' : hexToRgba(themeAccent, 0.45);
    const baseColorCutoff = currentMetric === 'expense' ? '#ef4444' : currentMetric === 'income' ? '#22c55e' : themeAccent;

    const fadedColorFull = currentMetric === 'expense' ? 'rgba(252, 165, 165, 0.3)' : currentMetric === 'income' ? 'rgba(134, 239, 172, 0.3)' : hexToRgba(themeAccent, 0.15);

    let labels = buckets.map(b => b.label);
    let fullData = buckets.map(b => b.sumFull);
    let cutoffData = buckets.map(b => b.sumCutoff);

    const datasets = [{
        label: 'Cả kỳ',
        data: fullData,
        backgroundColor: function(context) {
            if (!isCompareEnabled) {
                return context.dataIndex === targetIdx ? baseColorCutoff : fadedColorFull;
            }
            return fadedColorFull; 
        },
        grouped: false,
        order: 2, 
        barPercentage: 0.6, 
        categoryPercentage: 0.8,
        borderRadius: { topLeft: 4, topRight: 4 },
        borderSkipped: false
    }];

    if (isCompareEnabled) {
        datasets.push({
            label: 'Đến thời điểm tương ứng',
            data: cutoffData,
            backgroundColor: baseColorCutoff, // Giữ màu Đậm liên tục cho lớp So sánh
            grouped: false,
            order: 1, 
            barPercentage: 0.6, 
            categoryPercentage: 0.8,
            borderRadius: { topLeft: 4, topRight: 4 },
            borderSkipped: false
        });
    }

    const maxAbs = Math.max(...fullData, ...(isCompareEnabled ? cutoffData : [0]));
    const scale = getScaleUnit(maxAbs);

    // 💡 PLUGIN TỰ VẼ BONG BÓNG TOOLTIP THÔNG MINH
    const customPersistentTooltipPlugin = {
        id: 'persistentTooltip',
        afterDraw: chart => {
            if (targetIdx === null) return;
            const ctx = chart.ctx;
            const metaFull = chart.getDatasetMeta(0);
            const barFull = metaFull.data[targetIdx];
            if (!barFull) return;

            const b = buckets[targetIdx];
            let anchorIdxForCutoff = compareAnchorIndex !== null ? compareAnchorIndex : (buckets.length - 1);
            let anchorBucketForCutoff = buckets[anchorIdxForCutoff];
            
            // Vẽ đường chỉ nam nét đứt
            ctx.save();
            ctx.beginPath();
            ctx.moveTo(barFull.x, barFull.y);
            ctx.lineTo(barFull.x, chart.scales.y.bottom);
            ctx.lineWidth = 1.5;
            ctx.strokeStyle = '#cce3ff';
            ctx.setLineDash([4, 4]);
            ctx.stroke();
            ctx.restore();

            // Setup văn bản Tooltip
            let lines = [];
            lines.push({ text: b.title, font: 'bold 13px sans-serif', color: '#555', isTitle: true });

            if (!isCompareEnabled) {
                lines.push({ text: `Tổng: ${formatCurrencySafe(b.sumFull)}`, font: '13px sans-serif', color: baseColorCutoff, boxColor: baseColorCutoff });
            } else {
                if (anchorBucketForCutoff && anchorBucketForCutoff.isCurrent) {
                    // Nếu ghim ở tháng hiện tại -> Hiển thị Tooltip Cắt xén
                    let cutoffText = `Tổng: ${formatCurrencySafe(b.sumCutoff)}`;
                    if (b.cutoffDate && b.cutoffDate < b.end) {
                        const dStr = `${String(b.cutoffDate.getDate()).padStart(2,'0')}/${String(b.cutoffDate.getMonth()+1).padStart(2,'0')}`;
                        cutoffText = `Đến (${dStr}): ${formatCurrencySafe(b.sumCutoff)}`;
                    }
                    lines.push({ text: cutoffText, font: 'bold 13px sans-serif', color: baseColorCutoff, boxColor: baseColorCutoff });
                    lines.push({ text: `Tổng cả kỳ: ${formatCurrencySafe(b.sumFull)}`, font: '13px sans-serif', color: '#666', boxColor: fadedColorFull });
                } else {
                    // 💡 NẾU GHIM Ở THÁNG CŨ -> HIỂN THỊ TOOLTIP THEO DẠNG NGUYÊN KỲ 100%
                    lines.push({ text: `Tổng: ${formatCurrencySafe(b.sumFull)}`, font: 'bold 13px sans-serif', color: baseColorCutoff, boxColor: baseColorCutoff });
                    lines.push({ text: `(So sánh nguyên kỳ)`, font: 'italic 12px sans-serif', color: '#888', boxColor: 'transparent' });
                }
            }

            // Tính toán vị trí bong bóng
            ctx.save();
            ctx.font = 'bold 13px sans-serif';
            let maxWidth = ctx.measureText(b.title).width;
            ctx.font = '13px sans-serif';
            for (let i=1; i<lines.length; i++) {
                let w = ctx.measureText(lines[i].text).width + (lines[i].boxColor === 'transparent' ? 0 : 20); 
                if (w > maxWidth) maxWidth = w;
            }
            
            const padding = 12;
            const lineH = 20;
            const boxWidth = maxWidth + padding * 2;
            const boxHeight = lines.length * lineH + padding;
            
            let boxX = barFull.x - boxWidth / 2;
            
            let highestY = barFull.y;
            if (isCompareEnabled && chart.getDatasetMeta(1)) {
                 const barCutoff = chart.getDatasetMeta(1).data[targetIdx];
                 if (barCutoff && barCutoff.y < highestY) highestY = barCutoff.y;
            }
            
            let boxY = highestY - boxHeight - 12; 
            let drawCaretDown = true;
            
            if (boxX < 0) boxX = 5;
            if (boxX + boxWidth > chart.width) boxX = chart.width - boxWidth - 5;
            if (boxY < 0) {
                boxY = highestY + 15; 
                drawCaretDown = false;
            }

            // Vẽ Bong Bóng
            ctx.fillStyle = '#ffffff';
            ctx.shadowColor = 'rgba(0, 0, 0, 0.15)';
            ctx.shadowBlur = 10;
            ctx.shadowOffsetY = 4;
            
            ctx.beginPath();
            if (ctx.roundRect) {
                ctx.roundRect(boxX, boxY, boxWidth, boxHeight, 8);
            } else {
                let r = 8; let x = boxX; let y = boxY; let w = boxWidth; let h = boxHeight;
                ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
                ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
                ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
                ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y); ctx.closePath();
            }
            ctx.fill();
            ctx.shadowColor = 'transparent'; 
            
            // Vẽ đuôi tam giác
            if (drawCaretDown && barFull.x > boxX && barFull.x < boxX + boxWidth) {
                ctx.fillStyle = '#ffffff';
                ctx.beginPath();
                ctx.moveTo(barFull.x - 7, boxY + boxHeight - 1);
                ctx.lineTo(barFull.x + 7, boxY + boxHeight - 1);
                ctx.lineTo(barFull.x, boxY + boxHeight + 6);
                ctx.fill();
            }

            // In chữ
            let currentY = boxY + padding + 12;
            lines.forEach((l) => {
                ctx.font = l.font;
                ctx.fillStyle = l.color;
                if (l.isTitle) {
                    ctx.fillText(l.text, boxX + padding, currentY);
                } else if (l.boxColor === 'transparent') {
                    ctx.fillText(l.text, boxX + padding, currentY);
                } else {
                    ctx.fillStyle = l.boxColor;
                    ctx.fillRect(boxX + padding, currentY - 10, 12, 12); 
                    ctx.fillStyle = l.color;
                    ctx.fillText(l.text, boxX + padding + 20, currentY); 
                }
                currentY += lineH;
            });
            ctx.restore();
        }
    };

    trendChartInstance = new Chart(ctx, {
        type: 'bar',
        data: { labels: labels, datasets: datasets },
        plugins: [customPersistentTooltipPlugin], 
        options: {
            onClick: (evt, elements) => {
                if (!elements || elements.length === 0) return;
                const idx = elements[0].index;
                // Bấm vào cột khác thì di chuyển ghim
                if (selectedBarIndex !== idx) {
                    selectedBarIndex = idx; 
                    processAndRenderTrends(currentPeriod, currentAnchor); 
                }
            },
            responsive: true, maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
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
                tooltip: { enabled: false } 
            }
        }
    });

    const canvas = document.getElementById('trendChart');
    if (canvas) { canvas.style.cursor = 'pointer'; }
}

function getPeriodVietnamese(period) {
    if (period === 'week') return 'tuần';
    if (period === 'month') return 'tháng';
    return 'năm';
}

function updateTotalBlock(cur, prev, period, useCutoffForTotal) {
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
    const timeText = useCutoffForTotal ? 'cùng thời điểm' : 'cùng kỳ';
    
    pillEl.innerHTML = `${arrow} <span>${verb} ${amountText}</span> <span class="sub">so với ${timeText} ${periodText} trước</span> <i class="fa-solid fa-circle-info" style="opacity:0.7;"></i>`;
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

function renderTopCategories(curTxns, prevTxns, period, titleSuffix, useCutoffForTotal) {
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

    const timeText = useCutoffForTotal ? 'cùng thời điểm' : 'cùng kỳ';

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
                <div style="margin-top: 2px; font-size: 0.85rem; color: var(--text-secondary); font-weight:700; text-align:right;">So với ${timeText} ${periodText} trước</div>`
            : '';

        const safeId = 'cat-detail-' + index;
        const catColor = categoryColors[name] || '#8a2be2';

        const detailsHtml = dataObj.txns.sort((a, b) => new Date(b.date) - new Date(a.date)).map(t => {
            const d = new Date(t.date);
            let noteHtml = '';
            if (t.note && t.note.trim() !== '') {
                noteHtml = `<div style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 2px;"><i class="fa-solid fa-align-left" style="opacity: 0.6; margin-right: 4px;"></i> ${escapeHtml(t.note)}</div>`;
            }

            return `<div style="display:flex; justify-content:space-between; align-items:center; padding: 12px 16px; border-top: 1px solid var(--border); font-size: 0.95rem;">
                        <div>
                            <div style="color: var(--text-primary); font-weight: 600;">${escapeHtml(t.name || 'Không có mô tả')}</div>
                            ${noteHtml}
                            <div style="color: var(--text-secondary); font-size: 0.8rem; margin-top: 4px;">${fmtDate(d)}</div>
                        </div>
                        <div style="font-weight: bold; color: var(--text-primary);">${formatCurrencySafe(toValue(t))}</div>
                    </div>`;
        }).join('');

        return `
        <div style="margin-bottom: 10px;">
            <div class="trend-category-item" style="cursor: pointer; margin-bottom: 0; border-left: 5px solid ${catColor};" onclick="toggleCategoryDetails('${safeId}')">
                <div style="flex:1; display:flex; align-items:flex-start; justify-content:space-between; gap: 12px;">
                    <div style="font-weight: 800; color: var(--text-primary); display: flex; align-items: center; gap: 10px;">
                        <div style="width: 12px; height: 12px; border-radius: 50%; background-color: ${catColor};"></div>
                        ${escapeHtml(name)}
                    </div>
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