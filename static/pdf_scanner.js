/**
 * =========================================
 * PDF SCANNER 
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
            pdfInput.click(); // Mở cửa sổ chọn file
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

                // Gọi tới Route PDF mới tạo ở Bước 2
                const response = await fetch('/api/expenses/scan-pdf', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const err = await response.json();
                    throw new Error(err.detail || 'Lỗi hệ thống khi quét PDF');
                }

                const result = await response.json();
                
                // Hiển thị form xác nhận (Bạn có thể tái sử dụng hàm gọi backend confirm của OCR vì data trả về y hệt nhau)
                this._confirmAndSave(result.data);

            } catch (error) {
                if (window.showToast) showToast(`❌ ${error.message}`, 'error');
            }
        },

        _confirmAndSave: async function(aiData) {
            // Bước này dùng Prompt Javascript đơn giản để xác nhận thay vì vẽ Modal phức tạp
            // Nhằm đảm bảo UI không trùng lặp với OCR.
            const confirmMsg = `AI tìm thấy:\n\n` +
                               `Tên: ${aiData.name}\n` +
                               `Số tiền: ${aiData.amount} VND\n` +
                               `Danh mục: ${aiData.category}\n` +
                               `Ngày: ${aiData.date}\n\n` +
                               `Bạn có muốn lưu giao dịch này không?`;
            
            if(confirm(confirmMsg)) {
                try {
                    // Tận dụng API confirm cũ vì chung chuẩn dữ liệu
                    const response = await fetch('/api/expenses/scan-receipt/confirm', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(aiData)
                    });
                    
                    if (!response.ok) throw new Error("Lỗi khi lưu giao dịch PDF");
                    const result = await response.json();
                    
                    if (window.showToast) showToast(`✅ Đã lưu từ PDF: ${result.transaction.name}`, 'success');
                    
                    if (typeof this._onSuccess === 'function') {
                        this._onSuccess(result.transaction);
                    }
                } catch(error) {
                     if (window.showToast) showToast(`❌ ${error.message}`, 'error');
                }
            }
        }
    };

    // Lắng nghe sự kiện chọn file
    pdfInput.addEventListener('change', function(e) {
        if (e.target.files.length > 0) {
            window.PDFScanner.processFile(e.target.files[0]);
            e.target.value = ''; // Reset input
        }
    });

})();