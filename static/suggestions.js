function formatVND(value) {
    const amount = Number(value || 0);
    return amount.toLocaleString('vi-VN') + ' VND';
}

function priorityLabel(priority) {
    const p = String(priority || 'medium').toLowerCase();
    if (p === 'high') return { text: 'Ưu tiên cao', color: '#ff6b6b' };
    if (p === 'low') return { text: 'Ưu tiên thấp', color: '#4ecdc4' };
    return { text: 'Ưu tiên vừa', color: '#ffd166' };
}

function renderSuggestions(data) {
    const summaryEl = document.getElementById('suggestionsSummary');
    const listEl = document.getElementById('suggestionsList');

    const summary = data.summary || 'AI chưa tạo được phần tóm tắt.';
    summaryEl.style.display = 'block';
    summaryEl.innerHTML = `
        <h3 style="margin-top: 0; color: #d4a5ff;">Tóm tắt từ AI</h3>
        <p style="margin-bottom: 0; color: #e0e0e0; line-height: 1.5;">${summary}</p>
    `;

    const items = Array.isArray(data.suggestions) ? data.suggestions : [];
    if (!items.length) {
        listEl.innerHTML = `
            <div class="form-container" style="text-align: center; color: #a0a0b0;">
                Chưa có gợi ý phù hợp. Hãy thêm giao dịch và thử lại.
            </div>
        `;
        return;
    }

    listEl.innerHTML = items.map((item, idx) => {
        const pr = priorityLabel(item.priority);
        return `
            <div class="form-container" style="border: 1px solid #2a2a40;">
                <div style="display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 10px;">
                    <h3 style="margin: 0; color: #ffffff;">${idx + 1}. ${item.title || 'Gợi ý'}</h3>
                    <span style="font-size: 12px; font-weight: bold; color: ${pr.color}; border: 1px solid ${pr.color}; padding: 4px 8px; border-radius: 999px;">${pr.text}</span>
                </div>
                <p style="margin: 0 0 8px 0; color: #cfcfe6;"><strong>Lý do:</strong> ${item.reason || 'Không có'}</p>
                <p style="margin: 0 0 8px 0; color: #e8e8ff;"><strong>Hành động:</strong> ${item.action || 'Không có'}</p>
                <p style="margin: 0; color: #4ade80;"><strong>Tiết kiệm ước tính:</strong> ${formatVND(item.estimated_saving_vnd)}</p>
                <p style="margin: 8px 0 0 0; color: #a0a0b0;"><strong>Danh mục:</strong> ${item.category || 'Khác'}</p>
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

    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang tạo...';
    loading.style.display = 'block';
    listEl.innerHTML = '';
    summaryEl.style.display = 'none';

    try {
        const response = await fetch('/api/ai/spending-suggestions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ month_window: monthWindow })
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || 'Không thể tạo gợi ý chi tiêu lúc này.');
        }

        renderSuggestions(data);
        if (window.showToast) {
            showToast('Đã cập nhật gợi ý chi tiêu từ AI!', 'success');
        }
    } catch (error) {
        listEl.innerHTML = `
            <div class="form-container" style="border: 1px solid #ff4d4d; color: #ffb3b3;">
                ${error.message || 'Có lỗi xảy ra khi gọi AI.'}
            </div>
        `;
        if (window.showToast) {
            showToast('AI đang bận hoặc lỗi kết nối. Vui lòng thử lại.', 'error');
        }
    } finally {
        loading.style.display = 'none';
        btn.disabled = false;
        btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Tạo gợi ý';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('btnGenerateSuggestions');
    if (btn) {
        btn.addEventListener('click', loadSuggestions);
    }

    //loadSuggestions();
});
