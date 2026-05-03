/**
 * =========================================
 * PDF SCANNER (Giao diện Bảng Nhiều Dòng giống CSV)
 * =========================================
 */
(function() {
    'use strict';

    const pdfInput = document.createElement('input');
    pdfInput.type = 'file';
    pdfInput.accept = 'application/pdf';
    pdfInput.style.display = 'none';
    document.body.appendChild(pdfInput);

    window.PDFScanner = {
        _onSuccess: null,
        _scannedData: [],

        open: function(onSuccessCallback) {
            this._onSuccess = onSuccessCallback;
            pdfInput.click();
        },

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
                
                // Lưu dữ liệu vào biến nội bộ và mở giao diện bảng
                this._scannedData = result.data;
                this._openReviewModal();

            } catch (error) {
                if (window.showToast) showToast(`❌ ${error.message}`, 'error');
            }
        },

        _openReviewModal: function() {
            const categories = window.userCategories || ['Ăn uống', 'Đi lại', 'Mua sắm', 'Hóa đơn', 'Giải trí', 'Lương', 'Khác'];

            // Style CSS thu gọn cho giao diện Bảng
            const style = `
                <style>
                    .pdf-modal-overlay { position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.7); display:flex; align-items:center; justify-content:center; z-index:9999; backdrop-filter: blur(4px); }
                    .pdf-modal-container { background:#1c223a; border-radius:12px; border: 1px solid rgba(138, 43, 226, 0.3); width:95%; max-width:900px; max-height:90vh; display:flex; flex-direction:column; box-shadow:0 15px 35px rgba(0,0,0,0.6); color:#fff; font-family:sans-serif; overflow:hidden;}
                    .pdf-modal-header { padding: 20px 25px; border-bottom: 2px solid rgba(138, 43, 226, 0.3); display: flex; justify-content: space-between; align-items: center;}
                    .pdf-modal-body { padding: 20px 25px; overflow-y: auto; flex: 1; }
                    .pdf-modal-footer { padding: 15px 25px; border-top: 1px solid rgba(255,255,255,0.05); display: flex; justify-content: flex-end; gap: 15px;}
                    
                    .pdf-table { width: 100%; border-collapse: collapse; text-align: left; }
                    .pdf-table th { padding: 12px 10px; color: #a0abc0; font-size: 0.9rem; font-weight: 500; border-bottom: 1px solid rgba(255,255,255,0.05); }
                    .pdf-table td { padding: 10px; border-bottom: 1px solid rgba(255,255,255,0.05); }
                    
                    .pdf-input { width:100%; padding:10px; border-radius:8px; border:1px solid #2d3755; background:#141829; color:#fff; box-sizing:border-box; outline:none; font-family:inherit; }
                    .pdf-input:focus { border-color: #8a2be2; }
                    .pdf-btn-del { background: transparent; border: none; color: #ff4d4f; cursor: pointer; padding: 5px; font-size: 1.1rem; transition: transform 0.2s;}
                    .pdf-btn-del:hover { transform: scale(1.1); }
                </style>
            `;

            let tableRows = '';
            this._scannedData.forEach((item, index) => {
                let catOptions = '';
                categories.forEach(c => {
                    catOptions += `<option value="${c}" ${c === item.category ? 'selected' : ''}>${c}</option>`;
                });

                tableRows += `
                    <tr id="pdf_row_${index}">
                        <td style="width:15%;"><input type="date" class="pdf-input pdf-date" data-index="${index}" value="${item.date || ''}"></td>
                        <td style="width:30%;"><input type="text" class="pdf-input pdf-name" data-index="${index}" value="${item.name || ''}" placeholder="Mô tả giao dịch"></td>
                        <td style="width:20%;"><input type="number" class="pdf-input pdf-amount" data-index="${index}" value="${item.amount || 0}"></td>
                        <td style="width:25%;">
                            <select class="pdf-input pdf-category" data-index="${index}">
                                ${catOptions}
                            </select>
                        </td>
                        <td style="width:10%; text-align:center;">
                            <button class="pdf-btn-del" onclick="window.PDFScanner._removeRow(${index})"><i class="fa fa-trash"></i></button>
                        </td>
                    </tr>
                `;
            });

            const modalHtml = `
            ${style}
            <div id="pdfReviewModal" class="pdf-modal-overlay">
                <div class="pdf-modal-container">
                    <div class="pdf-modal-header">
                        <div style="display:flex; align-items:center; gap: 15px;">
                            <div style="background: linear-gradient(135deg, #b27bf2 0%, #8a2be2 100%); width: 40px; height: 40px; border-radius: 10px; display: flex; align-items: center; justify-content: center;">
                                <i class="fa fa-file-pdf" style="font-size: 1.1rem; color: white;"></i>
                            </div>
                            <div>
                                <h3 style="margin:0; font-size:1.1rem; color:#fff; font-weight:600;">Xác Nhận Dữ Liệu PDF</h3>
                                <div style="font-size:0.8rem; color:#a0abc0; margin-top:2px;">Bạn có thể chỉnh sửa trực tiếp các ô bên dưới trước khi lưu</div>
                            </div>
                        </div>
                        <i id="pdfBtnCloseIcon" class="fa fa-times" style="color: #6b7a99; cursor:pointer; font-size:1.2rem; padding: 5px;"></i>
                    </div>

                    <div class="pdf-modal-body">
                        <table class="pdf-table">
                            <thead>
                                <tr>
                                    <th>Ngày</th>
                                    <th>Mô tả</th>
                                    <th>Số tiền</th>
                                    <th>Danh mục</th>
                                    <th style="text-align:center;">Bỏ</th>
                                </tr>
                            </thead>
                            <tbody id="pdfTableBody">
                                ${tableRows}
                            </tbody>
                        </table>
                    </div>

                    <div class="pdf-modal-footer">
                        <button id="pdfBtnCancel" style="padding:10px 20px; border-radius:8px; border:1px solid #3c4970; background:transparent; color:#a0abc0; cursor:pointer; font-weight:600;">Hủy bỏ</button>
                        <button id="pdfBtnSave" style="padding:10px 25px; border-radius:8px; border:none; background:#59319f; color:#fff; cursor:pointer; font-weight:600; box-shadow: 0 4px 15px rgba(89, 49, 159, 0.4);">
                            <i class="fa fa-save" style="margin-right: 5px;"></i> Lưu Giao Dịch
                        </button>
                    </div>
                </div>
            </div>
            `;

            document.body.insertAdjacentHTML('beforeend', modalHtml);

            const modal = document.getElementById('pdfReviewModal');
            const btnCancel = document.getElementById('pdfBtnCancel');
            const btnCloseIcon = document.getElementById('pdfBtnCloseIcon');
            const btnSave = document.getElementById('pdfBtnSave');

            const closeModal = () => {
                modal.remove();
                if (window.showToast) showToast('Đã hủy thao tác.', 'info');
            };
            btnCancel.onclick = closeModal;
            btnCloseIcon.onclick = closeModal;

            // Xử lý nút Lưu Hàng Loạt
            btnSave.onclick = async () => {
                // Thu thập dữ liệu từ tất cả các dòng còn lại trên bảng
                const finalData = [];
                const rows = document.querySelectorAll('#pdfTableBody tr');
                
                rows.forEach(row => {
                    const idx = row.querySelector('.pdf-date').getAttribute('data-index');
                    const originalData = this._scannedData[idx] || {}; // Lấy tags và notes cũ
                    
                    finalData.push({
                        date: row.querySelector('.pdf-date').value,
                        name: row.querySelector('.pdf-name').value.trim(),
                        amount: parseFloat(row.querySelector('.pdf-amount').value),
                        category: row.querySelector('.pdf-category').value,
                        tags: originalData.tags || ["PDF Scan"],
                        notes: originalData.notes || ""
                    });
                });

                if(finalData.length === 0) {
                    if (window.showToast) showToast('Không có giao dịch nào để lưu!', 'warning');
                    return;
                }

                // Validate nhẹ
                let isValid = true;
                finalData.forEach(d => {
                    if(!d.name || d.amount === 0 || isNaN(d.amount)) isValid = false;
                });

                if(!isValid) {
                    if (window.showToast) showToast('Vui lòng nhập tên và số tiền hợp lệ cho tất cả giao dịch!', 'warning');
                    return;
                }

                btnSave.innerText = "Đang lưu...";
                btnSave.disabled = true;

                try {
                    let successCount = 0;
                    // Lặp qua từng giao dịch và gọi API lưu
                    for (const data of finalData) {
                        const response = await fetch('/api/expenses/scan-receipt/confirm', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(data)
                        });
                        if (response.ok) successCount++;
                    }
                    
                    if (window.showToast) showToast(`✅ Đã lưu thành công ${successCount} giao dịch!`, 'success');
                    
                    modal.remove();
                    // Load lại toàn bộ danh sách
                    if (typeof this._onSuccess === 'function') {
                        this._onSuccess(); // Góp ý: Bạn nên sửa hàm callback gốc bên ngoài để fetch lại toàn bộ list
                    }
                    // Tự động reload lại trang để UI cập nhật bảng
                    setTimeout(() => window.location.reload(), 1500);

                } catch(error) {
                    btnSave.innerHTML = `<i class="fa fa-save"></i> Thử Lại`;
                    btnSave.disabled = false;
                    if (window.showToast) showToast(`❌ Có lỗi xảy ra trong quá trình lưu`, 'error');
                }
            };
        },

        // Hàm hỗ trợ xóa 1 dòng trên UI
        _removeRow: function(index) {
            const row = document.getElementById(`pdf_row_${index}`);
            if (row) {
                row.remove();
            }
        }
    };

    pdfInput.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            window.PDFScanner.processFile(e.target.files[0]);
            e.target.value = ''; 
        }
    });

})();