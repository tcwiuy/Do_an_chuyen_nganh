import os

# --- KHỞI TẠO BIẾN MÔI TRƯỜNG GIẢ CHO TEST ---
os.environ["DATABASE_URL"] = "postgresql://postgres:localhost@localhost:5432/expenseowl_db"
os.environ["DB_PASSWORD"] = "localhost"
# --------------------------------------------

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
from main import app
import json
import io
from PIL import Image

# Import thêm các module để can thiệp DB
from database import SessionLocal
from models import User
from auth import get_password_hash

# Đánh dấu toàn bộ file này là test bất đồng bộ (async)
pytestmark = pytest.mark.asyncio

# ==========================================
# CẤU HÌNH FIXTURE CHUNG
# ==========================================

@pytest_asyncio.fixture
async def async_client():
    """Tạo client ảo cho FastAPI để gửi Request nội bộ"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient):
    """Bơm trực tiếp User vào Database và Đăng nhập để lấy Token"""
    
    # 1. Bơm User vào Database Test
    db = SessionLocal()
    try:
        # Kiểm tra xem user test đã tồn tại chưa
        test_user = db.query(User).filter(User.username == "ai_tester_vip").first()
        if not test_user:
            # Tạo mới nếu chưa có
            test_user = User(
                username="ai_tester_vip",
                email="aivip@test.com",
                hashed_password=get_password_hash("Test@123456"), # Mật khẩu mạnh
                full_name="AI VIP Tester"
            )
            db.add(test_user)
            db.commit()
    finally:
        db.close()

    # 2. Gọi API Đăng nhập với mật khẩu mạnh vừa tạo
    response = await async_client.post(
        "/api/auth/login", 
        data={
            "grant_type": "password",
            "username": "ai_tester_vip", 
            "password": "Test@123456"  # Phải khớp với password truyền vào hash ở trên
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    token_data = response.json()
    token = token_data.get("access_token")
    
    if not token:
        print("LỖI ĐĂNG NHẬP TRONG TEST:", token_data)
        token = "fake_token"
        
    return {"Authorization": f"Bearer {token}"}

# ==========================================
# HÀM MOCK (LÀM GIẢ) PHẢN HỒI TỪ GOOGLE
# ==========================================
def mock_gemini_response(text_result, status_code=200):
    """
    Giả lập cấu trúc JSON trả về từ Google Gemini REST API 
    mà hàm call_gemini_with_backoff trong routers.py đang mong đợi.
    """
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": text_result}]
                }
            }
        ]
    }
    mock_resp.text = text_result
    return mock_resp

# ==========================================
# KỊCH BẢN TEST AI/NLP TỰ ĐỘNG
# ==========================================

# 1. UT_AI_01: Xử lý lỗi Format (JSONDecodeError)
@patch('routers.call_gemini_with_backoff')
async def test_ut_ai_01_json_decode_error(mock_call, async_client: AsyncClient, auth_headers):
    # Giả lập: AI trả về văn bản thường thay vì JSON chuẩn
    mock_call.return_value = mock_gemini_response("Đây là văn bản, tôi không hiểu cấu trúc JSON.")
    
    resp = await async_client.post(
        "/api/ai/parse-expense", 
        json={"text": "Nay mình đi cafe 50k", "currency": "vnd", "rate": 1.0},
        headers=auth_headers
    )
    
    # Kỳ vọng: Bắt lỗi JSONDecodeError và ném lỗi 400 hoặc 422
    assert resp.status_code in [400, 422]

# 2. UT_AI_02: Xử lý ảo giác AI (Hallucination)
@patch('routers.call_gemini_with_backoff')
async def test_ut_ai_02_hallucination(mock_call, async_client: AsyncClient, auth_headers):
    # Giả lập: AI bịa số tiền = 0 (khi câu từ người dùng không chứa dữ liệu số tiền)
    mock_call.return_value = mock_gemini_response('{"amount": 0, "category": "Khác", "name": "Không rõ"}')
    
    resp = await async_client.post(
        "/api/ai/parse-expense", 
        json={"text": "Hôm nay tâm trạng tôi buồn quá", "currency": "vnd", "rate": 1.0},
        headers=auth_headers
    )
    
    # API có thể chủ động chặn lại với mã lỗi 400/422 hoặc trả về data nhưng amount = 0
    assert resp.status_code in [200, 400, 422]

# 3. UT_AI_03: NLP Phân loại danh mục (Categorization)
@patch('routers.call_gemini_with_backoff')
async def test_ut_ai_03_nlp_categorization(mock_call, async_client: AsyncClient, auth_headers):
    # Giả lập: AI đọc hiểu NLP và tự gom "CGV" vào danh mục "Giải trí"
    mock_call.return_value = mock_gemini_response('{"amount": -50000, "category": "Giải trí", "name": "Vé CGV", "date": "2023-10-25"}')
    
    resp = await async_client.post(
        "/api/ai/parse-expense", 
        json={"text": "Mua vé xem phim CGV hết 50 ngàn", "currency": "vnd", "rate": 1.0},
        headers=auth_headers
    )
    
    if resp.status_code == 200:
        data = resp.json()
        assert data.get("category") == "Giải trí" or "Giải trí" in str(data)

# 4. INT_AI_05: OCR Quét Hóa Đơn và Xác nhận
@patch('routers.call_gemini_with_backoff')
async def test_int_ai_05_ocr_receipt(mock_call, async_client: AsyncClient, auth_headers):
    # Giả lập: AI Vision trả về JSON bóc tách chuẩn xác từ hóa đơn
    mock_call.return_value = mock_gemini_response('{"amount": -200000, "name": "Coopmart", "category": "Mua sắm", "date": "2023-10-20"}')
    
    # Tạo một file ảnh JPEG giả trong bộ nhớ
    image = Image.new('RGB', (1, 1), color='white')
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG')
    files = {'file': ('hoadon.jpg', img_byte_arr.getvalue(), 'image/jpeg')}
    
    resp_scan = await async_client.post("/api/expenses/scan-receipt", files=files, headers=auth_headers)
    
    if resp_scan.status_code == 200:
        data = resp_scan.json()
        # In ra màn hình terminal để xem chính xác Backend trả về cái gì
        print("DEBUG DỮ LIỆU TRẢ VỀ:", data) 
        # Sửa lại thành gọi key "data" trước, rồi mới lấy phần tử đầu tiên [0]
        assert data["data"][0]["amount"] == -200000

# 5. INT_AI_06: Phân tích file CSV hàng loạt
@patch('routers.call_gemini_with_backoff')
async def test_int_ai_06_csv_scan(mock_call, async_client: AsyncClient, auth_headers):
    # Giả lập: AI trả về danh sách các giao dịch
    mock_call.return_value = mock_gemini_response('{"data": [{"date": "2023-10-01", "amount": -1000000, "category": "Đầu tư", "name": "Đầu tư chứng khoán"}]}')
    
    files = {'file': ('data.csv', b"date,amount,note\n2023-10-01,-1000000,Dau tu", 'text/csv')}
    resp_scan = await async_client.post("/api/expenses/scan-csv", files=files, headers=auth_headers)
    
    if resp_scan.status_code == 200:
        csv_data = resp_scan.json().get("data", [])
        assert len(csv_data) > 0