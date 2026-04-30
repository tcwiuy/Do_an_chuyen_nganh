const CSVScanner = {
    onSuccessCallback: null,
    scannedData: [],

    // Mở hộp thoại chọn file
    open: function(callback) {
        this.onSuccessCallback = callback;
        
        // Tự động tạo thẻ input file ẩn nếu chưa có trong DOM
        let fileInput = document.getElementById('csvHiddenInput');
        if (!fileInput) {
            fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.id = 'csvHiddenInput';
            fileInput.accept = '.csv';
            fileInput.style.display = 'none';
            document.body.appendChild(fileInput);
        }

        // Bắt sự kiện khi người dùng chọn file xong
        fileInput.onchange = (e) => {
            const file = e.target.files[0];
            if (file) {
                this.handleCSVUpload(file);
            }
            fileInput.value = ''; // Reset input để có thể chọn lại file cũ nếu cần
        };

        fileInput.click();
    },

    // Gửi file CSV lên backend phân tích
    handleCSVUpload: async function(file) {
        const previewArea = document.getElementById('scan-preview-area');
        if (!previewArea) {
            if (window.showToast) showToast("Lỗi: Không tìm thấy thẻ #scan-preview-area trong index.html", "error");
            return;
        }

        // Hiển thị trạng thái chờ trong khi Agent phân tích
        previewArea.innerHTML = `
            <div style="text-align: center; color: var(--accent); padding: 30px;">
                <i class="fa-solid fa-spinner fa-spin fa-2x"></i>
                <p style="margin-top: 10px;">Đang phân tích và phân loại dữ liệu CSV...</p>
            </div>
        `;

        const formData = new FormData();
        formData.append('file', file);

        try {
            // Lấy token chuẩn của hệ thống
            const token = localStorage.getItem('token'); 
            
            // Gọi route scan-csv từ backend pandas
            const response = await fetch('/api/expenses/api/scan-csv', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`
                },
                body: formData
            });

            if (response.ok) {
                const result = await response.json();
                // Nhận mảng dữ liệu từ backend (chuẩn bị sẵn thuộc tính data)
                this.scannedData = result.data || [];
                this.displayCSVResults();
            } else {
                const error = await response.json();
                previewArea.innerHTML = '';
                if (window.showToast) showToast(`Lỗi: ${error.detail || 'Không thể đọc file CSV'}`, "error");
            }
        } catch (error) {
            previewArea.innerHTML = '';
            if (window.showToast) showToast("Lỗi kết nối đến máy chủ AI!", "error");
        }
    },

    // Hiển thị bảng để người dùng dò lại (Human-in-the-loop)
    displayCSVResults: function() {
        const previewArea = document.getElementById('scan-preview-area');
        if (!this.scannedData || this.scannedData.length === 0) {
            previewArea.innerHTML = '<p style="color: #ff4d4d; text-align: center;">Không tìm thấy giao dịch nào hợp lệ trong file.</p>';
            return;
        }

        // Tái sử dụng danh sách categories từ Frontend
        const categories = window.initialCategories || ["Ăn uống", "Đi lại", "Mua sắm", "Hóa đơn", "Giải trí", "Thu nhập", "Khác"];
        const categoryOptions = categories.map(cat => `<option value="${cat}">${cat}</option>`).join('');

        let html = `
            <div class="form-container" style="margin-top: 20px; border: 1px solid var(--accent); animation: fadeIn 0.4s; background-color: var(--bg-secondary);">
                <h3 style="color: var(--accent); text-align: center; margin-top: 0;"><i class="fa-solid fa-list-check"></i> Xác Nhận Dữ Liệu CSV</h3>
                <p style="text-align: center; color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 15px;">Bạn có thể chỉnh sửa trực tiếp các ô bên dưới trước khi lưu</p>
                
                <div style="overflow-x: auto;">
                    <table style="width: 100%; text-align: left; border-collapse: collapse; margin-bottom: 15px;">
                        <thead>
                            <tr style="border-bottom: 1px solid var(--border); color: var(--text-secondary);">
                                <th style="padding: 10px;">Ngày</th>
                                <th style="padding: 10px;">Mô tả</th>
                                <th style="padding: 10px;">Số tiền</th>
                                <th style="padding: 10px;">Danh mục</th>
                                <th style="padding: 10px; text-align: center;">Bỏ</th>
                            </tr>
                        </thead>
                        <tbody>
        `;

        this.scannedData.forEach((row, index) => {
            // Chuẩn hóa định dạng ngày (YYYY-MM-DD)
            let dateVal = row.date;
            if(dateVal && dateVal.includes('T')) {
                dateVal = dateVal.split('T')[0];
            }

            html += `
                <tr id="csv-row-${index}" style="border-bottom: 1px dashed var(--border);">
                    <td style="padding: 10px;"><input type="date" id="csv-date-${index}" value="${dateVal}" class="wizard-input" style="margin: 0; padding: 8px;"></td>
                    <td style="padding: 10px;"><input type="text" id="csv-name-${index}" value="${row.name}" class="wizard-input" style="margin: 0; padding: 8px;"></td>
                    <td style="padding: 10px;"><input type="number" id="csv-amount-${index}" value="${row.amount}" class="wizard-input" style="margin: 0; padding: 8px;"></td>
                    <td style="padding: 10px;">
                        <select id="csv-category-${index}" class="wizard-input" style="margin: 0; padding: 8px;">
                            ${categoryOptions}
                        </select>
                    </td>
                    <td style="padding: 10px; text-align: center;">
                        <button onclick="CSVScanner.removeRow(${index})" style="background: none; border: none; color: #ff4d4d; cursor: pointer; padding: 5px;"><i class="fa-solid fa-trash"></i></button>
                    </td>
                </tr>
            `;
        });

        html += `
                        </tbody>
                    </table>
                </div>
                <div style="display: flex; justify-content: flex-end; gap: 10px; padding-top: 10px;">
                    <button onclick="document.getElementById('scan-preview-area').innerHTML = ''" class="nav-button" style="background: transparent; border: 1px solid #ff4d4d; color: #ff4d4d;">Hủy bỏ</button>
                    <button onclick="CSVScanner.saveAll()" class="nav-button" style="background-color: #4ade80; color: #1a1a1a; font-weight: bold;"><i class="fa-solid fa-save"></i> Lưu </button>
                </div>
            </div>
        `;

        previewArea.innerHTML = html;

        // Chọn sẵn category do AI phân tích
        this.scannedData.forEach((row, index) => {
            const select = document.getElementById(`csv-category-${index}`);
            if (select) {
                let cat = row.category || "Khác";
                let options = Array.from(select.options).map(o => o.value);
                select.value = options.includes(cat) ? cat : "Khác";
            }
        });
    },

    removeRow: function(index) {
        const row = document.getElementById(`csv-row-${index}`);
        if (row) {
            row.remove();
        }
    },

    // Ghi toàn bộ dữ liệu đã xác nhận xuống Database
    saveAll: async function() {
        const token = localStorage.getItem('token');
        let successCount = 0;
        let errorCount = 0;

        const rows = document.querySelectorAll('[id^="csv-row-"]');
        
        if (rows.length === 0) {
            if (window.showToast) showToast("Không có dữ liệu để lưu!", "error");
            return;
        }

        const saveBtn = document.querySelector('#scan-preview-area button[onclick="CSVScanner.saveAll()"]');
        if (saveBtn) {
            saveBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang xử lý...';
            saveBtn.disabled = true;
        }

        // Gọi POST /api/expenses/ cho từng dòng được giữ lại
        for (let row of rows) {
            const index = parseInt(row.id.replace('csv-row-', ''));
            
            const date = document.getElementById(`csv-date-${index}`).value;
            const name = document.getElementById(`csv-name-${index}`).value;
            const amount = parseFloat(document.getElementById(`csv-amount-${index}`).value);
            const category = document.getElementById(`csv-category-${index}`).value;

            if (!name || isNaN(amount) || !date) {
                errorCount++;
                continue;
            }

            const isoDate = new Date(date + "T00:00:00Z").toISOString();

            const formData = {
                name: name,
                category: category,
                amount: amount,
                date: isoDate,
                tags: ["CSV Scan"],
                note: null,
                recurring_interval: null
            };

            try {
                const response = await fetch('/api/expenses/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${token}`
                    },
                    body: JSON.stringify(formData)
                });

                if (response.ok) {
                    successCount++;
                } else {
                    errorCount++;
                }
            } catch (error) {
                errorCount++;
            }
        }

        // Dọn dẹp giao diện sau khi xong
        document.getElementById('scan-preview-area').innerHTML = '';
        
        if (window.showToast) {
            if (successCount > 0) showToast(`Đã lưu thành công ${successCount} giao dịch từ CSV!`, "success");
            if (errorCount > 0) showToast(`Có ${errorCount} giao dịch bị lỗi.`, "error");
        }

        // Gọi callback load lại dữ liệu (chạy hàm initialize() của trang chủ)
        if (this.onSuccessCallback) {
            this.onSuccessCallback();
        }
    }
};