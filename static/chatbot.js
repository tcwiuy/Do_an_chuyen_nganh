// ==========================================
// WIDGET CHATBOT CÚ MÈO TOÀN CỤC (GLOBAL)
// Tích hợp Trí nhớ SessionStorage
// ==========================================

const chatbotHTML = `
    <div id="chat-bubble" onclick="toggleChat()" style="position: fixed; bottom: 20px; right: 20px; width: 60px; height: 60px; background: linear-gradient(145deg, #8a2be2, #d4a5ff); border-radius: 50%; display: flex; align-items: center; justify-content: center; cursor: pointer; box-shadow: 0 4px 15px rgba(138,43,226,0.4); z-index: 9999; transition: transform 0.2s;">
        <i class="fa-solid fa-comment-dots" style="color: white; font-size: 24px;"></i>
    </div>

    <div id="chat-window" style="display: none; position: fixed; bottom: 90px; right: 20px; width: 350px; max-width: 90vw; height: 500px; max-height: 75vh; background-color: var(--surface); border: 1px solid #8a2be2; border-radius: 15px; box-shadow: 0 10px 25px rgba(0,0,0,0.8); z-index: 9999; flex-direction: column; overflow: hidden;">
        
        <div style="background: linear-gradient(145deg, var(--bg), var(--surface); padding: 15px; border-bottom: 1px solid #8a2be2; display: flex; justify-content: space-between; align-items: center;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <div style="width: 35px; height: 35px; background-color: #8a2be2; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 18px;">🦉</div>
                <div>
                    <h4 style="margin: 0; color: #d4a5ff;">Cú Mèo AI</h4>
                    <span style="font-size: 11px; color: #4ade80;">● Đang trực tuyến</span>
                </div>
            </div>
            <button onclick="toggleChat()" style="background: none; border: none; color: #a0a0b0; cursor: pointer; font-size: 16px;"><i class="fa-solid fa-times"></i></button>
        </div>

        <div id="chat-messages" style="flex: 1; padding: 15px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; background-color: var(--bg);">
            <div style="align-self: flex-start; max-width: 80%; background-color: var(--bg); padding: 12px; border-radius: 0 15px 15px 15px; color: var(--text); font-size: 14px; line-height: 1.5;">
                Xin chào! Tôi là trợ lý tài chính Cú Mèo. Bạn muốn hỏi gì về tình hình thu chi của mình nào?
            </div>
        </div>

        <div style="padding: 15px; background-color: var(--surface); border-top: 1px solid var(--bg); display: flex; gap: 10px;">
            <input type="text" id="chatInput" placeholder="Hỏi tôi bất cứ điều gì..." style="flex: 1; padding: 10px 15px; border-radius: 20px; border: 1px solid #3a3a50; background-color: var(--bg); color: var(--text); font-size: 14px; outline: none;">
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
                <div style="align-self: flex-start; max-width: 80%; background-color: var(--bg); padding: 12px; border-radius: 0 15px 15px 15px; color: var(--text); font-size: 14px; line-height: 1.5;">
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
        <div id="${loadingId}" style="align-self: flex-start; max-width: 80%; background-color: var(--bg); padding: 12px; border-radius: 0 15px 15px 15px; color: #a0a0b0; font-size: 14px;">
            <i class="fa-solid fa-ellipsis fa-fade"></i> Cú Mèo đang suy nghĩ...
        </div>
    `;
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
    sendBtn.disabled = true;

    try {
        const res = await fetch('/api/ai/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message, history: conversationMemory })
        });

        document.getElementById(loadingId).remove();

        if (res.ok) {
            const data = await res.json();
            
            // 3. CẬP NHẬT TRÍ NHỚ VÀ LƯU VÀO TRÌNH DUYỆT
            conversationMemory.push({ user: message, ai: data.reply });
            if (conversationMemory.length > 5) conversationMemory.shift(); 
            sessionStorage.setItem('expenseOwl_memory', JSON.stringify(conversationMemory)); // LƯU!
            
            let formattedReply = data.reply.replace(/\*\*(.*?)\*\*/g, '<b style="color:#d4a5ff;">$1</b>').replace(/\n/g, '<br>');

            messagesContainer.innerHTML += `
                <div style="align-self: flex-start; max-width: 80%; background-color: var(--bg); padding: 12px; border-radius: 0 15px 15px 15px; color: var(--text); font-size: 14px; line-height: 1.5;">
                    ${formattedReply}
                </div>
            `;
        } else {
            messagesContainer.innerHTML += `<div style="align-self: flex-start; max-width: 80%; background-color: #3f1d1d; border: 1px solid #ff4d4d; padding: 12px; border-radius: 0 15px 15px 15px; color: #ff4d4d; font-size: 14px;">❌ Lỗi kết nối AI.</div>`;
        }
    } catch (error) {
        document.getElementById(loadingId).remove();
        messagesContainer.innerHTML += `<div style="align-self: flex-start; background-color: #3f1d1d; padding: 12px; border-radius: 0 15px 15px 15px; color: #ff4d4d; font-size: 14px;">Lỗi mạng.</div>`;
    } finally {
        sendBtn.disabled = false;
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

