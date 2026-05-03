/**
 * =========================================
 * OCR RECEIPT SCANNER 
 * =========================================
 */

(function() {
    'use strict';

    // ─── HTML Template ────────────────────────────────────────────────
    const MODAL_HTML = `
    <div id="ocrModal" style="
        display: none; position: fixed; inset: 0; z-index: 10000;
        background: rgba(0,0,0,0.85); backdrop-filter: blur(4px);
        align-items: center; justify-content: center; padding: 16px;
    ">
        <div style="
            background: linear-gradient(160deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            border: 1px solid rgba(138,43,226,0.5);
            border-radius: 16px; width: 100%; max-width: 520px;
            max-height: 90vh; overflow-y: auto;
            box-shadow: 0 0 40px rgba(138,43,226,0.3);
            position: relative;
        ">
            <!-- Header -->
            <div style="
                padding: 20px 24px 16px;
                border-bottom: 1px solid rgba(138,43,226,0.3);
                display: flex; align-items: center; justify-content: space-between;
            ">
                <div style="display: flex; align-items: center; gap: 12px;">
                    <div style="
                        width: 40px; height: 40px; border-radius: 10px;
                        background: linear-gradient(135deg, #8a2be2, #d4a5ff);
                        display: flex; align-items: center; justify-content: center;
                        font-size: 20px;
                    ">📷</div>
                    <div>
                        <div style="font-weight: 600; color: #d4a5ff; font-size: 16px;">Quét Hóa Đơn</div>
                    </div>
                </div>
                <button id="ocrCloseBtn" style="
                    background: none; border: none; color: #7a7a9a;
                    cursor: pointer; font-size: 20px; padding: 4px 8px;
                    border-radius: 6px; transition: 0.2s;
                " onmouseover="this.style.color='#ff6b6b'" onmouseout="this.style.color='#7a7a9a'">✕</button>
            </div>

            <!-- Step Indicator -->
            <div style="padding: 16px 24px 0; display: flex; gap: 6px; align-items: center;">
                <div id="ocrStep1Indicator" class="ocr-step-dot" data-step="1" style="
                    height: 4px; flex: 1; border-radius: 2px;
                    background: #8a2be2; transition: 0.3s;
                "></div>
                <div id="ocrStep2Indicator" class="ocr-step-dot" data-step="2" style="
                    height: 4px; flex: 1; border-radius: 2px;
                    background: rgba(138,43,226,0.2); transition: 0.3s;
                "></div>
                <div id="ocrStep3Indicator" class="ocr-step-dot" data-step="3" style="
                    height: 4px; flex: 1; border-radius: 2px;
                    background: rgba(138,43,226,0.2); transition: 0.3s;
                "></div>
            </div>

            <!-- Body -->
            <div style="padding: 20px 24px 24px;">

                <!-- STEP 1: Upload -->
                <div id="ocrStep1">
                    <div style="color: #a0a0c0; font-size: 13px; margin-bottom: 16px; text-align: center;">
                        Bước 1 / 3 — Chọn ảnh hóa đơn
                    </div>

                    <!-- Drag & Drop Zone -->
                    <div id="ocrDropZone" style="
                        border: 2px dashed rgba(138,43,226,0.5);
                        border-radius: 12px; padding: 36px 20px;
                        text-align: center; cursor: pointer;
                        transition: 0.3s; background: rgba(138,43,226,0.05);
                        position: relative;
                    " onclick="document.getElementById('ocrFileInput').click()"
                       ondragover="OCRScanner._onDragOver(event)"
                       ondragleave="OCRScanner._onDragLeave(event)"
                       ondrop="OCRScanner._onDrop(event)">
                        <div style="font-size: 36px; margin-bottom: 12px; opacity: 0.7;">🖼️</div>
                        <div style="font-weight: 500; color: #d4a5ff; margin-bottom: 6px;">
                            Kéo thả ảnh vào đây
                        </div>
                        <div style="font-size: 13px; color: #6a6a8a;">
                            hoặc click để chọn file
                        </div>
                        <div style="font-size: 11px; color: #4a4a6a; margin-top: 8px;">
                            Hỗ trợ: JPG, PNG, WebP (tối đa 10MB)
                        </div>
                    </div>

                    <input type="file" id="ocrFileInput" accept="image/*" capture="environment"
                           style="display:none" onchange="OCRScanner._onFileSelected(event)">

                    <!-- Preview ảnh sau khi chọn -->
                    <div id="ocrImagePreview" style="display: none; margin-top: 16px;">
                        <div style="
                            position: relative; border-radius: 12px; overflow: hidden;
                            border: 1px solid rgba(138,43,226,0.4);
                        ">
                            <img id="ocrPreviewImg" style="width: 100%; max-height: 280px; object-fit: contain; display: block; background: #0a0a1a;">
                            <button onclick="OCRScanner._clearImage()" style="
                                position: absolute; top: 8px; right: 8px;
                                background: rgba(0,0,0,0.7); color: white;
                                border: none; border-radius: 6px; padding: 4px 10px;
                                cursor: pointer; font-size: 12px;
                            ">✕ Xóa</button>
                        </div>
                    </div>

                    <!-- Camera button for mobile -->
                    <div style="display: flex; gap: 10px; margin-top: 16px;">
                        <button onclick="OCRScanner._openCamera()" style="
                            flex: 1; padding: 12px; border: 1px solid rgba(138,43,226,0.4);
                            background: rgba(138,43,226,0.1); color: #d4a5ff;
                            border-radius: 8px; cursor: pointer; font-size: 13px; transition: 0.2s;
                        " onmouseover="this.style.background='rgba(138,43,226,0.25)'"
                           onmouseout="this.style.background='rgba(138,43,226,0.1)'">
                            📷 Chụp ảnh
                        </button>
                        <button onclick="OCRScanner._startScan()" id="ocrScanBtn" style="
                            flex: 2; padding: 12px;
                            background: linear-gradient(135deg, #8a2be2, #6a1cb2);
                            color: white; border: none; border-radius: 8px;
                            cursor: pointer; font-size: 14px; font-weight: 600;
                            transition: 0.2s; opacity: 0.5; pointer-events: none;
                        ">
                            🔍 Phân tích hóa đơn
                        </button>
                    </div>
                </div>

                <!-- STEP 2: Processing -->
                <div id="ocrStep2" style="display: none; text-align: center; padding: 20px 0;">
                    <div style="margin-bottom: 24px;">
                        <div id="ocrSpinner" style="
                            width: 64px; height: 64px; margin: 0 auto 20px;
                            border: 3px solid rgba(138,43,226,0.2);
                            border-top-color: #8a2be2;
                            border-radius: 50%;
                            animation: ocrSpin 0.8s linear infinite;
                        "></div>
                        <div style="font-size: 16px; color: #d4a5ff; font-weight: 500; margin-bottom: 8px;">
                            Cú Mèo đang đọc hóa đơn...
                        </div>
                        <div id="ocrProcessingStatus" style="font-size: 13px; color: #6a6a8a;">
                            Đang gửi ảnh đến Gemini AI Vision
                        </div>
                    </div>

                    <!-- Animated image preview nhỏ -->
                    <div style="
                        width: 120px; height: 120px; margin: 0 auto;
                        border-radius: 12px; overflow: hidden;
                        border: 2px solid rgba(138,43,226,0.5);
                        opacity: 0.8;
                    ">
                        <img id="ocrProcessingImg" style="width: 100%; height: 100%; object-fit: cover;">
                    </div>
                </div>

                <!-- STEP 3: Result & Edit -->
                <div id="ocrStep3" style="display: none;">
                    <div style="color: #4ade80; font-size: 13px; margin-bottom: 16px; text-align: center; display: flex; align-items: center; justify-content: center; gap: 6px;">
                        <span>✅</span>
                        <span>Phân tích thành công! Kiểm tra và xác nhận thông tin</span>
                    </div>

                    <div style="display: flex; gap: 16px;">
                        <!-- Thumbnail ảnh nhỏ -->
                        <div style="flex-shrink: 0;">
                            <img id="ocrResultImg" style="
                                width: 80px; height: 80px; object-fit: cover;
                                border-radius: 8px; border: 1px solid rgba(138,43,226,0.4);
                            ">
                        </div>

                        <!-- Form chỉnh sửa -->
                        <div style="flex: 1; display: flex; flex-direction: column; gap: 10px;">
                            <div>
                                <label style="font-size: 11px; color: #7a7a9a; display: block; margin-bottom: 4px;">Name</label>
                                <input id="ocrResultName" type="text" style="
                                    width: 100%; padding: 8px 10px;
                                    background: rgba(255,255,255,0.07);
                                    border: 1px solid rgba(138,43,226,0.3);
                                    border-radius: 6px; color: #e0e0e0; font-size: 14px; box-sizing: border-box;
                                    outline: none;
                                " onfocus="this.style.borderColor='#8a2be2'" onblur="this.style.borderColor='rgba(138,43,226,0.3)'">
                            </div>
                        </div>
                    </div>

                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px;">
                        <div>
                            <label style="font-size: 11px; color: #7a7a9a; display: block; margin-bottom: 4px;">Category</label>
                            <select id="ocrResultCategory" style="
                                width: 100%; padding: 8px 10px;
                                background: #1a1a2e;
                                border: 1px solid rgba(138,43,226,0.3);
                                border-radius: 6px; color: #e0e0e0; font-size: 14px; box-sizing: border-box;
                                outline: none; cursor: pointer;
                            "></select>
                        </div>
                        <div>
                            <label style="font-size: 11px; color: #7a7a9a; display: block; margin-bottom: 4px;">Amount</label>
                            <input id="ocrResultAmount" type="number" style="
                                width: 100%; padding: 8px 10px;
                                background: rgba(255,255,255,0.07);
                                border: 1px solid rgba(138,43,226,0.3);
                                border-radius: 6px; color: #e0e0e0; font-size: 14px; box-sizing: border-box;
                                outline: none;
                            " onfocus="this.style.borderColor='#8a2be2'" onblur="this.style.borderColor='rgba(138,43,226,0.3)'">
                        </div>
                        <div>
                            <label style="font-size: 11px; color: #7a7a9a; display: block; margin-bottom: 4px;">Date</label>
                            <input id="ocrResultDate" type="date" style="
                                width: 100%; padding: 8px 10px;
                                background: rgba(255,255,255,0.07);
                                border: 1px solid rgba(138,43,226,0.3);
                                border-radius: 6px; color: #e0e0e0; font-size: 14px; box-sizing: border-box;
                                outline: none;
                            " onfocus="this.style.borderColor='#8a2be2'" onblur="this.style.borderColor='rgba(138,43,226,0.3)'">
                        </div>
                        <div>
                            <label style="font-size: 11px; color: #7a7a9a; display: block; margin-bottom: 4px;">Tags</label>
                            <input id="ocrResultTags" type="text" placeholder="tag1, tag2" style="
                                width: 100%; padding: 8px 10px;
                                background: rgba(255,255,255,0.07);
                                border: 1px solid rgba(138,43,226,0.3);
                                border-radius: 6px; color: #e0e0e0; font-size: 14px; box-sizing: border-box;
                                outline: none;
                            " onfocus="this.style.borderColor='#8a2be2'" onblur="this.style.borderColor='rgba(138,43,226,0.3)'">
                        </div>
                    </div>

                    <!-- Ghi chú từ AI -->
                    <div id="ocrAiNotes" style="
                        display: none; margin-top: 10px; padding: 10px 12px;
                        background: rgba(138,43,226,0.1); border-left: 3px solid #8a2be2;
                        border-radius: 0 6px 6px 0; font-size: 12px; color: #b0a0d0;
                    "></div>

                    <!-- Buttons -->
                    <div style="display: flex; gap: 10px; margin-top: 20px;">
                        <button onclick="OCRScanner._resetToStep1()" style="
                            flex: 1; padding: 11px;
                            background: rgba(255,255,255,0.07);
                            color: #a0a0c0; border: 1px solid rgba(255,255,255,0.1);
                            border-radius: 8px; cursor: pointer; font-size: 13px; transition: 0.2s;
                        " onmouseover="this.style.background='rgba(255,255,255,0.12)'"
                           onmouseout="this.style.background='rgba(255,255,255,0.07)'">
                            ← Quét lại
                        </button>
                        <button onclick="OCRScanner._confirmSave()" id="ocrConfirmBtn" style="
                            flex: 2; padding: 11px;
                            background: linear-gradient(135deg, #22c55e, #16a34a);
                            color: white; border: none; border-radius: 8px;
                            cursor: pointer; font-size: 14px; font-weight: 600; transition: 0.2s;
                        ">
                            💾 Lưu giao dịch
                        </button>
                    </div>
                </div>

            </div>
        </div>
    </div>

    <style>
        @keyframes ocrSpin {
            to { transform: rotate(360deg); }
        }
        #ocrDropZone.ocr-drag-over {
            border-color: #8a2be2 !important;
            background: rgba(138,43,226,0.15) !important;
        }
    </style>
    `;

    // ─── OCRScanner Object ────────────────────────────────────────────
    window.OCRScanner = {
        _selectedFile: null,
        _onSuccess: null,
        _categories: [],

        // Khởi tạo modal vào DOM
        init: function() {
            if (document.getElementById('ocrModal')) return;
            document.body.insertAdjacentHTML('beforeend', MODAL_HTML);
            document.getElementById('ocrCloseBtn').addEventListener('click', () => this.close());
            document.getElementById('ocrModal').addEventListener('click', (e) => {
                if (e.target.id === 'ocrModal') this.close();
            });
        },

        // Mở scanner, nhận callback khi lưu thành công
        open: async function(onSuccessCallback) {
            this.init();
            this._onSuccess = onSuccessCallback;
            this._resetToStep1();
            document.getElementById('ocrModal').style.display = 'flex';

            // Load categories
            try {
                const res = await fetch('/api/config');
                const config = await res.json();
                this._categories = config.categories?.length 
                ? config.categories 
                : ['Food', 'Transport', 'Shopping', 'Bills', 'Entertainment',];
                const sel = document.getElementById('ocrResultCategory');
                sel.innerHTML = this._categories.map(c => `<option value="${c}">${c}</option>`).join('');
            } catch (e) {
                console.error('OCRScanner: không load được config', e);
            }
        },

        close: function() {
            const modal = document.getElementById('ocrModal');
            if (modal) modal.style.display = 'none';
        },

        _onDragOver: function(e) {
            e.preventDefault();
            document.getElementById('ocrDropZone').classList.add('ocr-drag-over');
        },

        _onDragLeave: function(e) {
            document.getElementById('ocrDropZone').classList.remove('ocr-drag-over');
        },

        _onDrop: function(e) {
            e.preventDefault();
            document.getElementById('ocrDropZone').classList.remove('ocr-drag-over');
            const file = e.dataTransfer.files[0];
            if (file && file.type.startsWith('image/')) {
                this._loadFile(file);
            } else {
                if (window.showToast) showToast('Chỉ hỗ trợ file ảnh!', 'error');
            }
        },

        _onFileSelected: function(e) {
            const file = e.target.files[0];
            if (file) this._loadFile(file);
        },

        _openCamera: function() {
            const input = document.getElementById('ocrFileInput');
            input.setAttribute('capture', 'environment');
            input.click();
        },

        _loadFile: function(file) {
            if (file.size > 10 * 1024 * 1024) {
                if (window.showToast) showToast('File quá lớn! Tối đa 10MB', 'error');
                return;
            }
            this._selectedFile = file;
            const reader = new FileReader();
            reader.onload = (e) => {
                const src = e.target.result;
                document.getElementById('ocrPreviewImg').src = src;
                document.getElementById('ocrImagePreview').style.display = 'block';
                document.getElementById('ocrDropZone').style.display = 'none';
                
                // Kích hoạt nút scan
                const scanBtn = document.getElementById('ocrScanBtn');
                scanBtn.style.opacity = '1';
                scanBtn.style.pointerEvents = 'auto';
            };
            reader.readAsDataURL(file);
        },

        _clearImage: function() {
            this._selectedFile = null;

            ['ocrPreviewImg','ocrProcessingImg','ocrResultImg'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.src = '';
            });

            document.getElementById('ocrImagePreview').style.display = 'none';
            document.getElementById('ocrDropZone').style.display = 'block';
            document.getElementById('ocrFileInput').value = '';

            const scanBtn = document.getElementById('ocrScanBtn');
            scanBtn.style.opacity = '0.5';
            scanBtn.style.pointerEvents = 'none';
        },

        _startScan: async function() {
            if (!this._selectedFile) {
                if (window.showToast) showToast('Vui lòng chọn ảnh trước!', 'error');
                return;
            }

            // Chuyển sang Step 2
            this._goToStep(2);
            document.getElementById('ocrProcessingImg').src = document.getElementById('ocrPreviewImg').src;

            const statusMessages = [
                'Đang gửi ảnh đến Gemini AI Vision...',
                'AI đang nhận diện văn bản...',
                'Đang trích xuất thông tin tài chính...',
                'Đang phân loại danh mục...'
            ];
            let msgIdx = 0;
            const statusEl = document.getElementById('ocrProcessingStatus');
            const statusInterval = setInterval(() => {
                msgIdx = (msgIdx + 1) % statusMessages.length;
                statusEl.textContent = statusMessages[msgIdx];
            }, 1200);

            try {
                const formData = new FormData();
                formData.append('file', this._selectedFile);

                const response = await fetch('/api/expenses/scan-receipt', {
                    method: 'POST',
                    body: formData
                });

                clearInterval(statusInterval);

                if (!response.ok) {
                    let errMsg = 'Lỗi hệ thống';
                    try {
                        const err = await response.json();
                        errMsg = err.detail || err.message || errMsg;
                    } catch (e) {
                        errMsg = await response.text();
                    }
                    throw new Error(errMsg);
                }

                const result = await response.json();
                this._populateForm(result.data);
                this._goToStep(3);

            } catch (error) {
                clearInterval(statusInterval);
                this._goToStep(1);
                if (window.showToast) showToast(`❌ ${error.message}`, 'error');
            }
        },

        _populateForm: function(data) {
            document.getElementById('ocrResultName').value = data.name || '';
            document.getElementById('ocrResultAmount').value = data.amount || 0;
            document.getElementById('ocrResultDate').value = data.date || new Date().toISOString().split('T')[0];
            
            const tagsArr = Array.isArray(data.tags) ? data.tags : [];
            document.getElementById('ocrResultTags').value = tagsArr.join(', ');

            // Set thumbnail
            document.getElementById('ocrResultImg').src = document.getElementById('ocrPreviewImg').src;

            // Set category
            const catSel = document.getElementById('ocrResultCategory');
            if (data.category) {
                for (let opt of catSel.options) {
                    if (opt.value.toLowerCase() === data.category.toLowerCase()) {
                        catSel.value = opt.value;
                        break;
                    }
                }
            }

            // Ghi chú từ AI
            if (data.notes) {
                const notesEl = document.getElementById('ocrAiNotes');
                notesEl.style.display = 'block';
                notesEl.textContent = `💡 Ghi chú AI: ${data.notes}`;
            }
        },

        _confirmSave: async function() {
            const btn = document.getElementById('ocrConfirmBtn');
            btn.disabled = true;
            btn.textContent = '⏳ Đang lưu...';

            const tagsRaw = document.getElementById('ocrResultTags').value;
            const tags = tagsRaw.split(',').map(t => t.trim()).filter(Boolean);
            const amountValue = parseFloat(document.getElementById('ocrResultAmount').value);

            const payload = {
                name: document.getElementById('ocrResultName').value,
                category: document.getElementById('ocrResultCategory').value,
                amount: isNaN(amountValue) ? 0 : amountValue,
                date: document.getElementById('ocrResultDate').value,
                tags: tags
            };

            try {
                const response = await fetch('/api/expenses/scan-receipt/confirm', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (!response.ok) {
                    let errMsg = 'Lỗi hệ thống';
                    try {
                        const err = await response.json();
                        errMsg = err.detail || err.message || errMsg;
                    } catch (e) {
                        errMsg = await response.text();
                    }
                    throw new Error(errMsg);
                }

                const result = await response.json();
                if (window.showToast) showToast(`✅ ${result.message}`, 'success');
                this.close();

                // Gọi callback để page tự reload dữ liệu
                if (typeof this._onSuccess === 'function') {
                    this._onSuccess(result.transaction);
                }

            } catch (error) {
                if (window.showToast) showToast(`❌ ${error.message}`, 'error');
            } finally {
                btn.disabled = false;
                btn.textContent = '💾 Lưu giao dịch';
            }
        },

        _goToStep: function(step) {
            [1, 2, 3].forEach(s => {
                document.getElementById(`ocrStep${s}`).style.display = s === step ? 'block' : 'none';
                const indicator = document.getElementById(`ocrStep${s}Indicator`);
                if (s < step) {
                    indicator.style.background = '#4ade80'; // done
                } else if (s === step) {
                    indicator.style.background = '#8a2be2'; // active
                } else {
                    indicator.style.background = 'rgba(138,43,226,0.2)'; // pending
                }
            });
        },

        _resetToStep1: function() {
            this._clearImage();
            this._goToStep(1);
            // Reset form fields
            ['ocrResultName', 'ocrResultAmount', 'ocrResultDate', 'ocrResultTags'].forEach(id => {
                const el = document.getElementById(id);
                if (el) el.value = '';
            });
            const notesEl = document.getElementById('ocrAiNotes');
            if (notesEl) notesEl.style.display = 'none';
        }
    };

})();
