// ==========================================
// FILE: suggestions.js - GỢI Ý CẮT GIẢM TỪ AI CÚ MÈO
// ==========================================

function formatDirectCurrency(amount) {
    if (amount === undefined || amount === null) return '0';
    
    // Đảm bảo không bị lỗi nếu window.currentCurrency chưa kịp tải
    const cur = window.currentCurrency || 'usd';
    const behaviors = window.currencyBehaviors || {};
    const behavior = behaviors[cur] || { symbol: "$", useComma: false, useDecimals: true, useSpace: false, right: false };
    
    const isNegative = amount < 0;
    const absAmount = Math.abs(amount);
    const options = { minimumFractionDigits: behavior.useDecimals ? 2 : 0, maximumFractionDigits: behavior.useDecimals ? 2 : 0 };
    let formattedAmount = new Intl.NumberFormat(behavior.useComma ? "de-DE" : "en-US", options).format(absAmount);
    let result = behavior.right ? `${formattedAmount}${behavior.useSpace ? " " : ""}${behavior.symbol}` : `${behavior.symbol}${behavior.useSpace ? " " : ""}${formattedAmount}`;
    return isNegative ? `-${result}` : result;
}

function renderSuggestions(data) {
    const summaryEl = document.getElementById('suggestionsSummary');
    const listEl = document.getElementById('suggestionsList');

    const savedColors = JSON.parse(localStorage.getItem('customCategoryColors') || '{}');
    const localPalette = ['#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40', '#F7464A', '#8a2be2'];
    
    const getCategoryColor = (catName, index) => {
        if (!catName) return '#8a2be2';
        if (savedColors[catName]) return savedColors[catName];
        const foundKey = Object.keys(savedColors).find(k => k.toLowerCase() === catName.toLowerCase());
        if (foundKey) return savedColors[foundKey];
        return localPalette[index % localPalette.length];
    };

    summaryEl.style.display = 'block';
    
    let feasibilityHtml = '';
    if (data.feasibility === 'high') feasibilityHtml = '<span style="color:#4ade80; font-weight:bold;">🟢 Khả thi cao</span>';
    else if (data.feasibility === 'medium') feasibilityHtml = '<span style="color:#ffd166; font-weight:bold;">🟡 Khả thi trung bình (Cần nỗ lực)</span>';
    else feasibilityHtml = '<span style="color:#ff6b6b; font-weight:bold;">🔴 Khó khả thi (Mục tiêu quá cao)</span>';

    summaryEl.innerHTML = `
        <div style="border-bottom: 1px solid #3a3a50; padding-bottom: 15px; margin-bottom: 15px;">
            <h3 style="margin-top: 0; color: #d4a5ff;"><i class="fa-solid fa-chess-knight"></i> Chiến lược Tổng thể</h3>
            <p style="color: #e0e0e0; line-height: 1.6; margin-bottom: 10px;">${data.overall_strategy || 'Chưa có chiến lược.'}</p>
            <div style="display: flex; justify-content: space-between; flex-wrap: wrap; background: #151521; padding: 15px; border-radius: 8px; border: 1px solid #2a2a40; gap: 10px;">
                <div><span style="color: #a0a0b0;">Mức độ khả thi:</span> ${feasibilityHtml}</div>
                <div><span style="color: #a0a0b0;">Tiết kiệm mỗi tháng:</span> <strong style="color: #4ade80; font-size: 16px;">${formatDirectCurrency(data.monthly_savings_needed)}</strong></div>
            </div>
        </div>
        <h4 style="color: #ffffff; margin-bottom: 10px;"><i class="fa-solid fa-scissors"></i> Kế hoạch cắt giảm chi tiết</h4>
    `;

    const items = Array.isArray(data.category_plans) ? data.category_plans : [];
    if (!items.length) {
        listEl.innerHTML = `
            <div class="form-container" style="text-align: center; color: #a0a0b0;">
                Mọi thứ đều hoàn hảo, bạn không cần phải cắt giảm thêm khoản nào!
            </div>
        `;
        return;
    }

    listEl.innerHTML = items.map((item, idx) => {
        const catName = item.category || 'Khác';
        const catColor = getCategoryColor(catName, idx);

        return `
            <div class="form-container" style="border: 1px solid #2a2a40; border-left: 5px solid ${catColor}; background: linear-gradient(145deg, #1e1e2d, #252538); padding: 15px;">
                <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #3a3a50; padding-bottom: 10px; margin-bottom: 15px;">
                    <h3 style="margin: 0; color: ${catColor}; font-size: 16px;">${idx + 1}. Cắt giảm: ${catName}</h3>
                    <span style="background: rgba(74, 222, 128, 0.1); padding: 6px 12px; border-radius: 6px; color: #4ade80; font-weight: bold; border: 1px solid rgba(74, 222, 128, 0.3);">
                        Giảm <i class="fa-solid fa-arrow-down"></i> ${formatDirectCurrency(item.reduction_amount)}
                    </span>
                </div>
                
                <div style="display: flex; gap: 15px; margin-bottom: 15px; flex-wrap: wrap;">
                    <div style="flex: 1; background: #151521; padding: 12px; border-radius: 8px; text-align: center; border: 1px solid #2a2a40;">
                        <div style="color: #a0a0b0; font-size: 12px; margin-bottom: 5px;">Mức tiêu hiện tại (TB/tháng)</div>
                        <div style="color: #ff6b6b; font-weight: bold; font-size: 15px;">${formatDirectCurrency(item.current_avg_spend)}</div>
                    </div>
                    <div style="flex: 1; background: #151521; padding: 12px; border-radius: 8px; text-align: center; border: 1px solid #2a2a40;">
                        <div style="color: #a0a0b0; font-size: 12px; margin-bottom: 5px;">Mục tiêu sau khi cắt giảm</div>
                        <div style="color: #4ade80; font-weight: bold; font-size: 15px;">${formatDirectCurrency(item.target_spend)}</div>
                    </div>
                </div>

                <div style="background: ${catColor}1A; padding: 12px; border-radius: 8px; border-left: 4px solid ${catColor};">
                    <p style="margin: 0; color: #e8e8ff; line-height: 1.5;"><strong>Cách thực hiện:</strong> ${item.how_to_achieve || 'Không có'}</p>
                </div>
            </div>
        `;
    }).join('');
}

async function loadSuggestions() {
    const btn = document.getElementById('btnGenerateSuggestions');
    const loading = document.getElementById('suggestionsLoading');
    const listEl = document.getElementById('suggestionsList');
    const summaryEl = document.getElementById('suggestionsSummary');
    
    const monthWindow = Number(document.getElementById('monthWindow').value || 3);
    const goalName = document.getElementById('goalName').value.trim();
    // Lột bỏ dấu phẩy an toàn
    const goalAmountRaw = Number(document.getElementById('goalAmount').value.replace(/,/g, '')) || 0;
    const goalMonths = Number(document.getElementById('goalMonths').value) || 0;

    const currentInputData = { monthWindow, goalName, goalAmountRaw, goalMonths };
    sessionStorage.setItem('ai_suggestion_inputs', JSON.stringify(currentInputData));

    const cur = window.currentCurrency || 'usd';
    const rates = window.exchangeRatesToVND || {};
    const behaviors = window.currencyBehaviors || {};

    let rate = rates[cur] || 1;
    const behavior = behaviors[cur] || { symbol: "$" };

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang lập kế hoạch...';
    loading.style.display = 'block';
    listEl.innerHTML = '';
    summaryEl.style.display = 'none';

    try {
        const response = await fetch('/api/ai/spending-suggestions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                month_window: monthWindow,
                goal_name: goalName,
                goal_amount: goalAmountRaw, 
                goal_months: goalMonths,
                currency: cur,
                symbol: behavior.symbol,
                rate: rate
            })
        });

        // 💡 CHỐT CHẶN: Kiểm tra nếu Backend trả về HTML lỗi 500 thay vì JSON
        const contentType = response.headers.get("content-type");
        let data;
        
        if (contentType && contentType.includes("application/json")) {
            data = await response.json();
        } else {
            const errorText = await response.text();
            throw new Error("Lỗi máy chủ nội bộ (500). Vui lòng thử lại sau.");
        }

        if (!response.ok) {
            throw new Error(data.detail || 'Không thể tạo kế hoạch lúc này.');
        }

        sessionStorage.setItem('ai_suggestion_result', JSON.stringify(data));
        
        renderSuggestions(data);
        if (window.showToast) {
            showToast('Đã lập kế hoạch thành công!', 'success');
        }
    } catch (error) {
        listEl.innerHTML = `
            <div class="form-container" style="border: 1px solid #ff4d4d; color: #ffb3b3;">
                ${error.message || 'Có lỗi xảy ra khi gọi AI.'}
            </div>
        `;
        if (window.showToast) showToast('Gặp lỗi khi tải dữ liệu từ máy chủ.', 'error');
    } finally {
        loading.style.display = 'none';
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Lập kế hoạch';
    }
}

async function initSuggestionsPage() {
    try {
        const res = await fetch('/api/config');
        if (res.ok) {
            const config = await res.json();
            window.currentCurrency = config.currency || 'usd';
        }

        const savedInputs = sessionStorage.getItem('ai_suggestion_inputs');
        if (savedInputs) {
            const inputs = JSON.parse(savedInputs);
            document.getElementById('monthWindow').value = inputs.monthWindow || 3;
            document.getElementById('goalName').value = inputs.goalName || '';
            
            if (inputs.goalAmountRaw) {
                let formatted = inputs.goalAmountRaw.toString();
                let parts = formatted.split('.');
                parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
                document.getElementById('goalAmount').value = parts.join('.');
            }
            
            document.getElementById('goalMonths').value = inputs.goalMonths || '';
        }

        const savedResult = sessionStorage.getItem('ai_suggestion_result');
        if (savedResult) {
            const data = JSON.parse(savedResult);
            renderSuggestions(data);
        }

    } catch (e) {
        console.error('Lỗi tải dữ liệu Suggestion', e);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initSuggestionsPage();
    const btn = document.getElementById('btnGenerateSuggestions');
    if (btn) btn.addEventListener('click', loadSuggestions);
});