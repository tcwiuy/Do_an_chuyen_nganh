// ==========================================
// WIDGET CHATBOT CÚ MÈO TOÀN CỤC (GLOBAL)
// Tích hợp Trí nhớ SessionStorage
// ==========================================

const chatbotHTML = `
    <div id="chat-bubble" onclick="toggleChat()" style="position: fixed; bottom: 20px; right: 20px; width: 60px; height: 60px; background: linear-gradient(145deg, #8a2be2, #d4a5ff); border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 4px 15px rgba(138,43,226,0.4); z-index: 9999; transition: transform 0.2s;">
        <i class="fa-solid fa-comment-dots" style="color: white; font-size: 24px;"></i>
    </div>

    <div id="chat-window" style="display: none; position: fixed; bottom: 90px; right: 20px; width: 350px; max-width: 90vw; height: 500px; max-height: 75vh; background-color: #1e1e2d; border: 1px solid #8a2be2; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.8); z-index: 9999; flex-direction: column; overflow: hidden;">
        
        <div style="background: linear-gradient(145deg, #2a2a40, #1e1e2d); padding: 15px; border-bottom: 1px solid #8a2be2; display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 35px; height: 35px; background-color: #8a2be2; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px;">🦉</div>
                <div>
                    <h4 style="margin: 0; color: #d4a5ff;">Cú Mèo AI</h4>
                    <span style="font-size: 11px; color: #4ade80;">● Đang trực tuyến</span>
                </div>
            </div>
            <button onclick="toggleChat()" style="background: none; border: none; color: #a0a0b0; cursor: pointer; font-size: 16px;"><i class="fa-solid fa-times"></i></button>
        </div>

        <div id="chat-messages" style="flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; background-color: #151521;">
            <div style="align-self: flex-start; max-width: 80%; background-color: #2a2a40; padding: 12px; border-radius: 0 15px 15px 15px; color: #e0e0e0; font-size: 14px; line-height: 1.5;">
                Xin chào! Tôi là trợ lý tài chính Cú Mèo. Bạn muốn hỏi gì về tình hình thu chi của mình nào?
            </div>
        </div>

        <div style="padding: 15px; background-color: #1e1e2d; border-top: 1px solid #2a2a40; display: flex; gap: 10px;">
            <input type="text" id="chatInput" placeholder="Hỏi tôi bất cứ điều gì..." style="flex: 1; padding: 10px 15px; border-radius: 20px; border: 1px solid #3a3a50; background-color: #151521; color: #ffffff; font-size: 14px; outline: none;">
            <button onclick="sendChatMessage()" id="chatSendBtn" style="background-color: #8a2be2; color: white; border: none; width: 40px; height: 40px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center; transition: 0.2s;">
                <i class="fa-solid fa-paper-plane"></i>
            </button>
        </div>
    </div>
`;

// 1. NẠP TRÍ NHỚ TỪ TRÌNH DUYỆT (Nếu không có thì tạo mảng rỗng)
let conversationMemory = JSON.parse(sessionStorage.getItem('expenseOwl_memory')) || [];

document.addEventListener("DOMContentLoaded", () => {
    document.body.insertAdjacentHTML('beforeend', chatbotHTML);
    
    // 2. PHỤC HỒI TIN NHẮN CŨ LÊN MÀN HÌNH NẾU CÓ TRÍ NHỚ
    const messagesContainer = document.getElementById('chat-messages');
    if (conversationMemory.length > 0) {
        conversationMemory.forEach(turn => {
            // In tin nhắn User
            messagesContainer.innerHTML += `
                <div style="align-self: flex-end; max-width: 80%; background-color: #8a2be2; padding: 12px; border-radius: 15px 15px 0 15px; color: white; font-size: 14px; line-height: 1.5;">
                    ${turn.user}
                </div>
            `;
            // In tin nhắn AI (Có xử lý Markdown)
            let formattedReply = turn.ai.replace(/\*\*(.*?)\*\*/g, '<b style="color:#d4a5ff;">$1</b>').replace(/\n/g, '<br>');
            messagesContainer.innerHTML += `
                <div style="align-self: flex-start; max-width: 80%; background-color: #2a2a40; padding: 12px; border-radius: 0 15px 15px 15px; color: #ffffff; font-size: 14px; line-height: 1.5;">
                    ${formattedReply}
                </div>
            `;
        });
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    // Bắt sự kiện Enter để gửi
    document.getElementById('chatInput').addEventListener('keypress', function (e) {
        if (e.key === 'Enter') sendChatMessage();
    });
});

window.toggleChat = function() {
    const chatWin = document.getElementById('chat-window');
    if (chatWin.style.display === 'none') {
        chatWin.style.display = 'flex';
        document.getElementById('chatInput').focus();
    } else {
        chatWin.style.display = 'none';
    }
}

window.sendChatMessage = async function() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();
    const messagesContainer = document.getElementById('chat-messages');
    const sendBtn = document.getElementById('chatSendBtn');

    if (!message) return;

    // Hiển thị tin User
    messagesContainer.innerHTML += `
        <div style="align-self: flex-end; max-width: 80%; background-color: #8a2be2; padding: 12px; border-radius: 15px 15px 0 15px; color: white; font-size: 14px; line-height: 1.5;">
            ${message}
        </div>
    `;
    input.value = '';
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Hiển thị loading
    const loadingId = 'loading-' + Date.now();
    messagesContainer.innerHTML += `
        <div id="${loadingId}" style="align-self: flex-start; max-width: 80%; background-color: #2a2a40; padding: 12px; border-radius: 0 15px 15px 15px; color: #a0a0b0; font-size: 14px;">
            <i class="fa-solid fa-ellipsis fa-fade"></i> Cú Mèo đang tính toán và ghi chép...
        </div>
    `;
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    sendBtn.disabled = true;

    try {
        const currentRate = (typeof exchangeRatesToVND !== 'undefined') ? (exchangeRatesToVND[currentCurrency] || 1) : 1;
        
        const res = await fetch('/api/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, history: conversationMemory, currency: currentCurrency, rate: currentRate })
        });

        document.getElementById(loadingId).remove();

        if (res.ok) {
            const data = await res.json();
            
            // 1. CẬP NHẬT TRÍ NHỚ VÀ LƯU VÀO TRÌNH DUYỆT
            conversationMemory.push({ user: message, ai: data.reply });
            if (conversationMemory.length > 5) conversationMemory.shift(); 
            sessionStorage.setItem('expenseOwl_memory', JSON.stringify(conversationMemory));
            
            // 2. IN CÂU TRẢ LỜI CỦA CÚ MÈO LÊN MÀN HÌNH CHAT
            let formattedReply = data.reply.replace(/\*\*(.*?)\*\*/g, '<b style="color:#d4a5ff;">$1</b>').replace(/\n/g, '<br>');
            messagesContainer.innerHTML += `
                <div style="align-self: flex-start; max-width: 80%; background-color: #2a2a40; padding: 12px; border-radius: 0 15px 15px 15px; color: #ffffff; font-size: 14px; line-height: 1.5;">
                    ${formattedReply}
                </div>
            `;
            messagesContainer.scrollTop = messagesContainer.scrollHeight;

            // ==========================================
            // 🚦 3. KIỂM TRA BẤT THƯỜNG VÀ LƯU GIAO DỊCH (ĐÃ FIX TỶ GIÁ)
            // ==========================================
            if (data.action === "save" && data.transaction_data) {
                const parsedTxn = data.transaction_data;
                
                // LƯU Ý QUAN TRỌNG: AI ở Chatbot đã tự động quy đổi tiền ngoại tệ sang VND 
                // theo lịch sử Database. Do đó parsedTxn.amount lúc này CHẮC CHẮN LÀ VND.
                let amountInVND = Math.abs(parsedTxn.amount); 
                
                // 1. Xác định tỷ giá trên màn hình để "Dịch" ngược lại cho người dùng hiểu
                let rate = 1;
                let currencyName = 'VND';
                if (typeof exchangeRatesToVND !== 'undefined') {
                    const curr = typeof currentCurrency !== 'undefined' ? currentCurrency : 'usd';
                    rate = exchangeRatesToVND[curr] || 1;
                    currencyName = curr.toUpperCase(); 
                }
                
                let finalAmountToSave = parsedTxn.amount; // Giữ nguyên gửi DB (vì DB cũng lưu VND)
                let shouldSave = true;

                // 2. Kiểm tra bất thường
                if (parsedTxn.amount < 0) { 
                    let categoryAverageVND = 0;

                    if (typeof allExpenses !== 'undefined') {
                        const categoryExpenses = allExpenses.filter(exp => exp.amount < 0 && exp.category === parsedTxn.category);
                        if (categoryExpenses.length > 0) {
                            const totalCategory = categoryExpenses.reduce((sum, exp) => sum + Math.abs(exp.amount), 0);
                            categoryAverageVND = totalCategory / categoryExpenses.length;
                        }
                    }

                    // Mốc an toàn cố định 50 USD quy ra tiền Việt
                    let minAlertAmountVND = 50 * 25400; 
                    if (typeof exchangeRatesToVND !== 'undefined' && exchangeRatesToVND['usd']) {
                        minAlertAmountVND = 50 * exchangeRatesToVND['usd'];
                    }

                    if (categoryAverageVND > 0 && amountInVND > (categoryAverageVND * 3) && amountInVND > minAlertAmountVND) {
                        
                        // SỬA Ở ĐÂY: CHIA NGƯỢC LẠI TỶ GIÁ ĐỂ HIỂN THỊ ĐÚNG ĐƠN VỊ LÊN POPUP
                        let amountDisplay = amountInVND / rate;
                        let avgDisplay = categoryAverageVND / rate;
                        
                        let fmtAmount = amountDisplay.toLocaleString('vi-VN', { maximumFractionDigits: 2 }) + " " + currencyName;
                        let fmtAvg = avgDisplay.toLocaleString('vi-VN', { maximumFractionDigits: 2 }) + " " + currencyName;

                        const confirmMsg = `Cú Mèo phát hiện khoản chi RẤT LỚN!\n\nSố tiền bạn nhập (${fmtAmount}) lớn hơn GẤP NHIỀU LẦN mức trung bình của danh mục "${parsedTxn.category}" (${fmtAvg}).\n\nBạn có chắc chắn muốn lưu giao dịch này không?`;
                        
                        let userConfirmed = false;
                        if (typeof showCustomConfirm === 'function') {
                            userConfirmed = await showCustomConfirm(confirmMsg);
                        } else {
                            userConfirmed = confirm(confirmMsg);
                        }

                        if (!userConfirmed) {
                            shouldSave = false;
                            
                            // Tẩy não Cú Mèo
                            conversationMemory.pop();
                            sessionStorage.setItem('expenseOwl_memory', JSON.stringify(conversationMemory));

                            messagesContainer.innerHTML += `
                                <div style="align-self: flex-start; max-width: 80%; background-color: #3f1d1d; border: 1px solid #ff4d4d; padding: 12px; border-radius: 0 15px 15px 15px; color: #ff4d4d; font-size: 14px; line-height: 1.5;">
                                    ❌ Đã hủy lệnh lưu giao dịch! Cú Mèo cũng đã "quên" khoản tiền này.
                                </div>
                            `;
                            messagesContainer.scrollTop = messagesContainer.scrollHeight;
                        }
                    }
                }

                // 3. Gọi API lưu xuống Database
                if (shouldSave) {
                    try {
                        const saveRes = await fetch('/api/expenses/', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                name: parsedTxn.name,
                                category: parsedTxn.category,
                                amount: finalAmountToSave, 
                                date: parsedTxn.date, 
                                tags: parsedTxn.tags || ["AI Chatbot"]
                            })
                        });

                        if (saveRes.ok) {
                            if(window.showToast) showToast('Cú Mèo đã lưu giao dịch thành công!', 'success');
                            if (typeof initialize === "function") {
                                await initialize(); 
                            }
                        } else {
                            if(window.showToast) showToast('Có lỗi xảy ra khi Cú Mèo lưu dữ liệu.', 'error');
                        }
                    } catch (e) {
                        if(window.showToast) showToast('Lỗi kết nối khi lưu giao dịch.', 'error');
                    }
                }
            }

        } else {
            const errorData = await res.json().catch(() => ({}));
            const detail = errorData.detail || 'Lỗi kết nối AI.';
            messagesContainer.innerHTML += `<div style="align-self: flex-start; max-width: 80%; background-color: #3f1d1d; border: 1px solid #ff4d4d; padding: 12px; border-radius: 0 15px 15px 15px; color: #ff4d4d; font-size: 14px;">❌ ${detail}</div>`;
        }
    } catch (error) {
        document.getElementById(loadingId).remove();
        messagesContainer.innerHTML += `<div style="align-self: flex-start; background-color: #3f1d1d; padding: 12px; border-radius: 0 15px 15px 15px; color: #ff4d4d; font-size: 14px;">❌ Lỗi mạng hoặc máy chủ phản hồi quá chậm.</div>`;
    } finally {
        sendBtn.disabled = false;
        input.focus(); // Trả lại con trỏ chuột vào ô nhập
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

// Thêm container chứa Toast vào body
document.body.insertAdjacentHTML('beforeend', '<div id="toast-container"></div>');

// Hàm hiển thị Toast
window.showToast = function(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type === 'error' ? 'error' : ''}`;
    
    const icon = type === 'error' ? '<i class="fa-solid fa-circle-exclamation" style="color: #ff4d4d;"></i>' : '<i class="fa-solid fa-circle-check" style="color: #4ade80;"></i>';
    
    toast.innerHTML = `${icon} <span>${message}</span>`;
    container.appendChild(toast);

    // Hiệu ứng trượt vào
    setTimeout(() => toast.classList.add('show'), 10);

    // Tự động biến mất sau 3 giây
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300); // Đợi animation trượt ra rồi xóa
    }, 3000);
}