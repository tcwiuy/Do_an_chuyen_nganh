// =========================================
// KIỂM TRA ĐĂNG NHẬP (AUTH GUARD)
// =========================================
if (!localStorage.getItem('token') && window.location.pathname !== '/login') {
    window.location.href = '/login';
}

function logout() {
    localStorage.removeItem('token');
    window.location.href = '/login';
}

const colorPalette = [
    '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', 
    '#FFBE0B', '#FF006E', '#8338EC', '#3A86FF', 
    '#FB5607', '#38B000', '#9B5DE5', '#F15BB5'
];

// =========================================
// 🌍 HỆ THỐNG TỶ GIÁ & CHUYỂN ĐỔI TIỀN TỆ 
// =========================================
// Quy ước: Database của bạn luôn lưu tiền gốc là VND. 
const exchangeRatesToVND = {
    vnd: 1,         // Việt Nam Đồng
    usd: 25400,     // Đô la Mỹ
    eur: 27500,     // Euro
    gbp: 32000,     // Bảng Anh
    jpy: 165,       // Yên Nhật
    cny: 3500,      // Nhân dân tệ (Trung Quốc)
    krw: 18.5,      // Won Hàn Quốc
    inr: 305,       // Rupee Ấn Độ
    rub: 275,       // Rúp Nga
    brl: 4900,      // Real Brazil
    zar: 1350,      // Rand Nam Phi
    aed: 6915,      // Dirham UAE
    aud: 16800,     // Đô la Úc
    cad: 18600,     // Đô la Canada
    chf: 28000,     // Franc Thụy Sĩ
    hkd: 3250,      // Đô la Hồng Kông
    bdt: 230,       // Taka Bangladesh
    sgd: 18800,     // Đô la Singapore
    thb: 690,       // Baht Thái
    try: 780,       // Lira Thổ Nhĩ Kỳ
    mxn: 1500,      // Peso Mexico
    php: 440,       // Peso Philippines
    pln: 6350,      // Zloty Ba Lan
    sek: 2350,      // Krona Thụy Điển
    nzd: 15300,     // Đô la New Zealand
    dkk: 3680,      // Krone Đan Mạch
    idr: 1.58,      // Rupiah Indonesia
    ils: 6750,      // Shekel Israel
    myr: 5350,      // Ringgit Malaysia
    mad: 2520       // Dirham Maroc
};

const currencyBehaviors = {
    usd: {symbol: "$", useComma: false, useDecimals: true, useSpace: false, right: false},
    eur: {symbol: "€", useComma: true, useDecimals: true, useSpace: false, right: false},
    gbp: {symbol: "£", useComma: false, useDecimals: true, useSpace: false, right: false},
    jpy: {symbol: "¥", useComma: false, useDecimals: false, useSpace: false, right: false},
    cny: {symbol: "¥", useComma: false, useDecimals: true, useSpace: false, right: false},
    krw: {symbol: "₩", useComma: false, useDecimals: false, useSpace: false, right: false},
    inr: {symbol: "₹", useComma: false, useDecimals: true, useSpace: false, right: false},
    rub: {symbol: "₽", useComma: true, useDecimals: true, useSpace: false, right: false},
    brl: {symbol: "R$", useComma: true, useDecimals: true, useSpace: false, right: false},
    zar: {symbol: "R", useComma: false, useDecimals: true, useSpace: true, right: true},
    aed: {symbol: "AED", useComma: false, useDecimals: true, useSpace: true, right: true},
    aud: {symbol: "A$", useComma: false, useDecimals: true, useSpace: false, right: false},
    cad: {symbol: "C$", useComma: false, useDecimals: true, useSpace: false, right: false},
    chf: {symbol: "Fr", useComma: false, useDecimals: true, useSpace: true, right: true},
    hkd: {symbol: "HK$", useComma: false, useDecimals: true, useSpace: false, right: false},
    bdt: {symbol: "৳", useComma: false, useDecimals: true, useSpace: false, right: false},
    sgd: {symbol: "S$", useComma: false, useDecimals: true, useSpace: false, right: false},
    thb: {symbol: "฿", useComma: false, useDecimals: true, useSpace: false, right: false},
    try: {symbol: "₺", useComma: true, useDecimals: true, useSpace: false, right: false},
    mxn: {symbol: "Mex$", useComma: false, useDecimals: true, useSpace: false, right: false},
    php: {symbol: "₱", useComma: false, useDecimals: true, useSpace: false, right: false},
    pln: {symbol: "zł", useComma: true, useDecimals: true, useSpace: true, right: true},
    sek: {symbol: "kr", useComma: false, useDecimals: true, useSpace: true, right: true},
    nzd: {symbol: "NZ$", useComma: false, useDecimals: true, useSpace: false, right: false},
    dkk: {symbol: "kr.", useComma: true, useDecimals: true, useSpace: true, right: true},
    idr: {symbol: "Rp", useComma: false, useDecimals: true, useSpace: true, right: true},
    ils: {symbol: "₪", useComma: false, useDecimals: true, useSpace: false, right: false},
    vnd: {symbol: "₫", useComma: true, useDecimals: true, useSpace: true, right: true},
    myr: {symbol: "RM", useComma: false, useDecimals: true, useSpace: false, right: false},
    mad: {symbol: "DH", useComma: false, useDecimals: true, useSpace: true, right: true},
};

function formatCurrency(amount) {
    if (amount === undefined || amount === null) return '0';

    const behavior = currencyBehaviors[currentCurrency] || {
        symbol: "$", useComma: false, useDecimals: true, useSpace: false, right: false
    };

    // Quy đổi từ VND sang tiền đang chọn
    const rate = exchangeRatesToVND[currentCurrency] || 1;
    const convertedAmount = amount / rate;

    const isNegative = convertedAmount < 0;
    const absAmount = Math.abs(convertedAmount);

    // --- LOGIC MỚI: XỬ LÝ SỐ TIỀN QUÁ NHỎ ---
    let minDecimals = behavior.useDecimals ? 2 : 0;
    let maxDecimals = behavior.useDecimals ? 2 : 0;

    // Nếu tiền có dùng số lẻ, và giá trị khác 0 nhưng lại nhỏ hơn 0.01
    // Tự động giãn phần thập phân ra 4 chữ số để không bị hiển thị 0.00
    if (behavior.useDecimals && absAmount > 0 && absAmount < 0.01) {
        maxDecimals = 4;
    }

    const options = {
        minimumFractionDigits: minDecimals,
        maximumFractionDigits: maxDecimals,
    };
    
    let formattedAmount = new Intl.NumberFormat(behavior.useComma ? "de-DE" : "en-US", options).format(absAmount);

    let result = behavior.right
        ? `${formattedAmount}${behavior.useSpace ? " " : ""}${behavior.symbol}`
        : `${behavior.symbol}${behavior.useSpace ? " " : ""}${formattedAmount}`;
        
    return isNegative ? `-${result}` : result;
}

// =========================================
// QUẢN LÝ THỜI GIAN & NGÀY THÁNG (BẢN CHUẨN UTC)
// =========================================
function getUserTimeZone() {
    return Intl.DateTimeFormat().resolvedOptions().timeZone;
}

function formatMonth(date) {
    return date.toLocaleDateString('vi-VN', {
        year: 'numeric',
        month: 'long',
        timeZone: getUserTimeZone()
    });
}

// BỎ getISODateWithLocalTime vì gây lệch múi giờ

// Chỉ đọc ngày UTC để hiển thị đồng nhất, không cho trình duyệt tự cộng giờ
function formatDateFromUTC(utcDateString) {
    if (!utcDateString) return '-';
    const safeDate = utcDateString.endsWith('Z') ? utcDateString : utcDateString + 'Z';
    const date = new Date(safeDate);
    
    const day = String(date.getUTCDate()).padStart(2, '0');
    const month = String(date.getUTCMonth() + 1).padStart(2, '0');
    const year = date.getUTCFullYear();
    return `${day}/${month}/${year}`;
}

function updateMonthDisplay() {
    const currentMonthEl = document.getElementById('currentMonth');
    if (currentMonthEl) {
        currentMonthEl.textContent = formatMonth(currentDate);
    }
}

// Tính khoảng tháng theo đúng 00:00:00 UTC
function getMonthBounds(date) {
    const d = new Date(date);
    const year = d.getUTCFullYear();
    const month = d.getUTCMonth();

    if (startDate === 1) {
        const start = new Date(Date.UTC(year, month, 1, 0, 0, 0));
        const end = new Date(Date.UTC(year, month + 1, 0, 23, 59, 59, 999));
        return { start, end };
    }
    
    let start, end;
    if (d.getUTCDate() < startDate) {
        start = new Date(Date.UTC(year, month - 1, startDate, 0, 0, 0));
        end = new Date(Date.UTC(year, month, startDate - 1, 23, 59, 59, 999));
    } else {
        start = new Date(Date.UTC(year, month, startDate, 0, 0, 0));
        end = new Date(Date.UTC(year, month + 1, startDate - 1, 23, 59, 59, 999));
    }
    return { start, end };
}

function getMonthExpenses(expenses) {
    const { start, end } = getMonthBounds(currentDate);
    return expenses.filter(exp => {
        const safeDateString = exp.date.endsWith('Z') ? exp.date : exp.date + 'Z';
        const expDate = new Date(safeDateString);
        return expDate >= start && expDate <= end;
    }).sort((a, b) => new Date(b.date) - new Date(a.date));
}

// =========================================
// THỦ THUẬT FETCH INTERCEPTOR (GẮN TOKEN)
// =========================================
const originalFetch = window.fetch;
window.fetch = async (...args) => {
    let [resource, config] = args;

    if (typeof resource === 'string' && resource.startsWith('/api/') && !resource.includes('/auth/')) {
        config = config || {};

        const token = localStorage.getItem('token');

        if (token) {
            config.headers = {
                ...config.headers,
                'Authorization': `Bearer ${token}`
            };
        }

        args[1] = config;
    }

    try {
        const response = await originalFetch(...args);

        if (response.status === 401) {
            logout();
        }

        return response;

    } catch (err) {
        console.error("FETCH ERROR:", err);
        throw err;
    }
};

// =========================================
// HỆ THỐNG TOAST NOTIFICATION
// =========================================
document.addEventListener("DOMContentLoaded", () => {
    if (!document.getElementById('toast-container')) {
        document.body.insertAdjacentHTML('beforeend', '<div id="toast-container"></div>');
    }
});

window.showToast = function(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast ${type === 'error' ? 'error' : ''}`;
    
    const icon = type === 'error' 
        ? '<i class="fa-solid fa-circle-exclamation" style="color: #ff4d4d; font-size: 18px;"></i>' 
        : '<i class="fa-solid fa-circle-check" style="color: #4ade80; font-size: 18px;"></i>';
    
    toast.innerHTML = `${icon} <span>${message}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400); 
    }, 3000);
};

// =========================================
// TRỢ LÝ AI (PHÂN TÍCH XU HƯỚNG)
// =========================================
let aiAbortController = null;

function closeAiModal() {
    document.getElementById('aiModal').style.display = 'none';
    if (aiAbortController) {
        aiAbortController.abort();
        aiAbortController = null;
    }
}

window.addEventListener('click', function(event) {
    const modal = document.getElementById('aiModal');
    if (event.target === modal) {
        closeAiModal();
    }
}); 

async function analyzeTrends() {
    const modal = document.getElementById('aiModal');
    const loadingText = document.getElementById('aiLoading');
    const contentBox = document.getElementById('aiContent');
    const btn = document.getElementById('btnAnalyze');

    modal.style.display = 'flex';
    loadingText.style.display = 'block';
    contentBox.innerHTML = '';
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang xử lý...';

    aiAbortController = new AbortController();

    try {
        const token = localStorage.getItem('token'); 
        const response = await fetch('/api/ai/analyze-trends', {
            method: 'GET',
            headers: { 'Authorization': 'Bearer ' + token },
            signal: aiAbortController.signal
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Lỗi khi gọi API');
        
        let formattedReply = data.reply
            .replace(/### (.*?)\n/g, '<h3 style="color:#d4a5ff; margin-top: 15px; margin-bottom:5px;">$1</h3>')
            .replace(/\*\*(.*?)\*\*/g, '<strong style="color: #fff;">$1</strong>')
            .replace(/\n/g, '<br>');

        contentBox.innerHTML = formattedReply;

    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Tiến trình AI đã bị ngắt vì người dùng đóng cửa sổ.');
        } else {
            contentBox.innerHTML = `<span style="color:#ff4d4d;">Lỗi: ${error.message || 'Không thể kết nối với Cú Mèo lúc này. Hãy thử lại sau!'}</span>`;
        }
    } finally {
        loadingText.style.display = 'none';
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Phân Tích AI';
    }
}