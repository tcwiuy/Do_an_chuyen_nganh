/**
 * =========================================
 * PDF SCANNER (Cập nhật Giao diện giống Quét Hóa Đơn)
 * =========================================
 */
(function() {
    'use strict';

    // Tạo Input File ẩn chuyên dụng cho PDF
    const pdfInput = document.createElement('input');
    pdfInput.type = 'file';
    pdfInput.accept = 'application/pdf';
    pdfInput.style.display = 'none';
    document.body.appendChild(pdfInput);

    window.PDFScanner = {
        _onSuccess: null,

        // Hàm gọi từ nút bấm UI
        open: function(onSuccessCallback) {
            this._onSuccess = onSuccessCallback;
            pdfInput.click();
        },

        // Xử lý khi user chọn file xong
        processFile: async function(file) {
            if (file.type !== 'application/pdf') {
                if (window.showToast) showToast('Chỉ hỗ trợ file PDF!', 'error');
                return;
            }

            if (file.size > 15 * 1024 * 1024) {
                if (window.showToast) showToast('File PDF quá lớn! Tối đa 15MB', 'error');
                return;
            }

            if (window.showToast) showToast('⏳ Đang gửi PDF cho Cú Mèo phân tích...', 'success');

            try {
                const formData = new FormData();
                formData.append('file', file);

                const response = await fetch('/api/expenses/scan-pdf', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Lỗi hệ thống khi quét PDF');
                }

                const result = await response.json();
                
                // Thay vì confirm, mở Modal Review
                this._openReviewModal(result.data);

            } catch (error) {
                if (window.showToast) showToast(`❌ ${error.message}`, 'error');
            }
        },

        // Hàm tạo và hiển thị Modal chỉnh sửa với Theme Xanh - Tím
        _openReviewModal: function(aiData) {
            const categories = window.userCategories || ['Ăn uống', 'Đi lại', 'Mua sắm', 'Hóa đơn', 'Giải trí', 'Lương', 'Khác'];
            let catOptions = '';
            categories.forEach(c => {
                catOptions += `<option value="${c}" ${c === aiData.category ? 'selected' : ''}>${c}</option>`;
            });

            // Tiêm HTML Modal vào trang (Theme: Background #1c223a, Border Tím)
            const modalHtml = `
            <div id="pdfReviewModal" style="position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; z-index:9999; backdrop-filter: blur(4px);">
                <div style="background:#1c223a; border-radius:16px; border: 1px solid rgba(138, 43, 226, 0.3); width:90%; max-width:450px; padding:25px; box-shadow:0 15px 35px rgba(0,0,0,0.6); color:#fff; font-family:sans-serif;">
                    
                    <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 2px solid rgba(138, 43, 226, 0.5); padding-bottom:15px; margin-bottom: 20px;">
                        <div style="display:flex; align-items:center; gap: 15px;">
                            <div style="background: linear-gradient(135deg, #b27bf2 0%, #8a2be2 100%); width: 45px; height: 45px; border-radius: 12px; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(138,43,226,0.3);">
                                <i class="fa fa-file-pdf" style="font-size: 1.2rem; color: white;"></i>
                            </div>
                            <div>
                                <h3 style="margin:0; font-size:1.1rem; color:#fff; font-weight:600;">Kết quả quét PDF</h3>
                            </div>
                        </div>
                        <i id="pdfBtnCloseIcon" class="fa fa-times" style="color: #6b7a99; cursor:pointer; font-size:1.2rem;"></i>
                    </div>

                    <p style="font-size:0.9em; color:#a0abc0; margin-bottom:20px; text-align:center;">Bạn có thể chỉnh sửa trực tiếp các ô bên dưới trước khi lưu</p>

                    <div style="display:flex; flex-direction:column; gap:15px;">
                        
                        <div style="display:flex; flex-direction:column; gap:6px;">
                            <label style="font-size:0.85em; color:#8fa1c4; font-weight:500;">Tên giao dịch</label>
                            <input type="text" id="pdf_name" value="${aiData.name || ''}" style="width:100%; padding:12px; border-radius:10px; border:1px solid #2d3755; background:#141829; color:#fff; box-sizing:border-box; outline:none; transition: border 0.2s;" onfocus="this.style.border='1px solid #8a2be2'" onblur="this.style.border='1px solid #2d3755'">
                        </div>

                        <div style="display:flex; flex-direction:column; gap:6px;">
                            <label style="font-size:0.85em; color:#8fa1c4; font-weight:500;">Số tiền (VND)</label>
                            <input type="number" id="pdf_amount" value="${aiData.amount || 0}" style="width:100%; padding:12px; border-radius:10px; border:1px solid #2d3755; background:#141829; color:#fff; box-sizing:border-box; outline:none; transition: border 0.2s;" onfocus="this.style.border='1px solid #8a2be2'" onblur="this.style.border='1px solid #2d3755'">
                        </div>

                        <div style="display:flex; gap:12px;">
                            <div style="display:flex; flex-direction:column; gap:6px; flex:1;">
                                <label style="font-size:0.85em; color:#8fa1c4; font-weight:500;">Danh mục</label>
                                <select id="pdf_category" style="width:100%; padding:12px; border-radius:10px; border:1px solid #2d3755; background:#141829; color:#fff; box-sizing:border-box; outline:none; transition: border 0.2s;" onfocus="this.style.border='1px solid #8a2be2'" onblur="this.style.border='1px solid #2d3755'">
                                    ${catOptions}
                                </select>
                            </div>

                            <div style="display:flex; flex-direction:column; gap:6px; flex:1;">
                                <label style="font-size:0.85em; color:#8fa1c4; font-weight:500;">Ngày</label>
                                <input type="date" id="pdf_date" value="${aiData.date || ''}" style="width:100%; padding:12px; border-radius:10px; border:1px solid #2d3755; background:#141829; color:#fff; box-sizing:border-box; outline:none; transition: border 0.2s;" onfocus="this.style.border='1px solid #8a2be2'" onblur="this.style.border='1px solid #2d3755'">
                            </div>
                        </div>

                    </div>

                    <div style="display:flex; justify-content:space-between; gap:12px; margin-top:30px;">
                        <button id="pdfBtnCancel" style="flex:1; padding:12px; border-radius:10px; border:1px solid #3c4970; background:transparent; color:#a0abc0; cursor:pointer; font-weight:600; transition: all 0.2s;">Hủy bỏ</button>
                        <button id="pdfBtnSave" style="flex:1; padding:12px; border-radius:10px; border:none; background:#59319f; color:#fff; cursor:pointer; font-weight:600; transition: all 0.2s; box-shadow: 0 4px 15px rgba(89, 49, 159, 0.4);">
                            <i class="fa fa-save" style="margin-right: 5px;"></i> Lưu Giao Dịch
                        </button>
                    </div>

                </div>
            </div>
            `;

            // Thêm vào DOM
            document.body.insertAdjacentHTML('beforeend', modalHtml);

            const modal = document.getElementById('pdfReviewModal');
            const btnCancel = document.getElementById('pdfBtnCancel');
            const btnCloseIcon = document.getElementById('pdfBtnCloseIcon');
            const btnSave = document.getElementById('pdfBtnSave');

            // Xử lý nút Hủy 
            const closeModal = () => {
                modal.remove();
                if (window.showToast) showToast('Đã hủy lưu giao dịch.', 'info');
            };
            btnCancel.onclick = closeModal;
            btnCloseIcon.onclick = closeModal;

            // Hiệu ứng Hover cho nút
            btnCancel.onmouseover = () => { btnCancel.style.background = '#252d47'; btnCancel.style.color = '#fff'; };
            btnCancel.onmouseout = () => { btnCancel.style.background = 'transparent'; btnCancel.style.color = '#a0abc0'; };
            btnSave.onmouseover = () => btnSave.style.background = '#6b3ebd';
            btnSave.onmouseout = () => btnSave.style.background = '#59319f';

            // Xử lý nút Lưu
            btnSave.onclick = async () => {
                const editedData = {
                    name: document.getElementById('pdf_name').value.trim(),
                    amount: parseFloat(document.getElementById('pdf_amount').value),
                    category: document.getElementById('pdf_category').value,
                    date: document.getElementById('pdf_date').value,
                    tags: aiData.tags || ["PDF Scan"],
                    notes: aiData.notes || ""
                };

                if(!editedData.name) {
                    if (window.showToast) showToast('Vui lòng nhập tên giao dịch!', 'warning');
                    return;
                }
                if(editedData.amount === 0 || isNaN(editedData.amount)) {
                    if (window.showToast) showToast('Số tiền không được bằng 0!', 'warning');
                    return;
                }

                btnSave.innerText = "Đang lưu...";
                btnSave.disabled = true;
                btnSave.style.opacity = '0.7';

                try {
                    const response = await fetch('/api/expenses/scan-receipt/confirm', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(editedData)
                    });
                    
                    if (!response.ok) {
                        const err = await response.json();
                        throw new Error(err.detail || "Lỗi khi lưu giao dịch PDF");
                    }

                    const result = await response.json();
                    if (window.showToast) showToast(`✅ Đã lưu: ${result.transaction.name}`, 'success');
                    
                    modal.remove();
                    if (typeof this._onSuccess === 'function') {
                        this._onSuccess(result.transaction);
                    }
                } catch(error) {
                    btnSave.innerHTML = `<i class="fa fa-save" style="margin-right: 5px;"></i> Lưu Giao Dịch`;
                    btnSave.disabled = false;
                    btnSave.style.opacity = '1';
                    if (window.showToast) showToast(`❌ ${error.message}`, 'error');
                }
            };
        }
    };

    // Lắng nghe sự kiện chọn file
    pdfInput.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            window.PDFScanner.processFile(e.target.files[0]);
            e.target.value = ''; 
        }
    });

})();