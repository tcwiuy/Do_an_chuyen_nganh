import pytest
import pytest_asyncio
import uuid 
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
import io
from PIL import Image
from main import app

pytestmark = pytest.mark.asyncio

@pytest_asyncio.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

@pytest_asyncio.fixture
async def auth_headers(async_client: AsyncClient):
    """Fixture: Tạo user mới hoàn toàn mỗi lần test để tránh bị khóa tài khoản"""
    
    import uuid
    unique_str = str(uuid.uuid4())[:8]
    test_user = f"test_{unique_str}"
    test_email = f"{test_user}@gmail.com"
    test_password = "SuperPassword123!"

    # Dữ liệu mô phỏng 
    register_payload = {
        "username": test_user,
        "email": test_email,
        "password": test_password,
        "full_name": "Người Dùng Test", 
        "gender": "Nam",                
        "dob": "2000-01-01"             
    }

    register_resp = await async_client.post("/api/auth/register", json=register_payload)
    
    if register_resp.status_code == 307:
        register_resp = await async_client.post("/api/auth/register/", json=register_payload)

    assert register_resp.status_code in [200, 201], f"Đăng ký thất bại: {register_resp.status_code} - {register_resp.text}"
    
    login_resp = await async_client.post(
        "/api/auth/login",
        data={"username": test_user, "password": test_password}
    )
    
    if login_resp.status_code == 307:
        login_resp = await async_client.post(
            "/api/auth/login/",
            data={"username": test_user, "password": test_password}
        )

    assert login_resp.status_code == 200, f"Đăng nhập thất bại: {login_resp.status_code} - {login_resp.text}"
    token = login_resp.json().get("access_token")
    return {"Authorization": f"Bearer {token}"}


# ==========================================
# INT_01: Xác thực và Truy cập
# ==========================================
async def test_int_01_auth_and_access(async_client: AsyncClient, auth_headers):
    # Dựa theo Swagger: GET /api/expenses/ (Có dấu / ở cuối)
    response = await async_client.get("/api/expenses/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

# ==========================================
# INT_02: Ghi giao dịch & Chia hũ
# ==========================================
async def test_int_02_income_and_jars(async_client: AsyncClient, auth_headers):
    payload = {
        "amount": 10000000, 
        "category": "Lương",       # Đã sửa: category_id -> category
        "name": "Lương tháng 10",  # Đã sửa: note -> name
        "date": "2023-10-10"
    }
    resp_add = await async_client.post("/api/expenses/", json=payload, headers=auth_headers)
    assert resp_add.status_code == 200, f"Lỗi 422 INT_02: {resp_add.text}"

    resp_jars = await async_client.get("/api/planning/jars", headers=auth_headers)
    assert resp_jars.status_code == 200

# ==========================================
# INT_03: Ghi giao dịch & Ngân sách
# ==========================================
async def test_int_03_expense_and_budget(async_client: AsyncClient, auth_headers):
    payload = {
        "amount": -500000, 
        "category": "Ăn uống",   # Đã sửa: category_id -> category
        "name": "Ăn Lẩu",        # Đã sửa: note -> name
        "date": "2023-10-15"
    }
    resp_add = await async_client.post("/api/expenses/", json=payload, headers=auth_headers)
    assert resp_add.status_code == 200, f"Lỗi 422 INT_03: {resp_add.text}"

    resp_budget = await async_client.get("/api/planning/budgets", headers=auth_headers)
    assert resp_budget.status_code == 200

# ---------------------------------------------------------
# INT_04: AI Chat
# ---------------------------------------------------------
@patch('google.genai.Client') 
async def test_int_04_ai_chat_and_save(mock_client_class, async_client: AsyncClient, auth_headers):
    mock_instance = mock_client_class.return_value
    mock_instance.models.generate_content.return_value.text = '{"action": "add_transaction", "data": {"amount": -50000, "note": "cafe", "category_id": 1}}'
    
    resp_chat = await async_client.post(
        "/api/ai/chat", 
        json={"message": "Nay mình đi cafe hết 50k"}, 
        headers=auth_headers
    )
    assert resp_chat.status_code == 200

# ---------------------------------------------------------
# INT_05: Quét Ảnh Hóa Đơn
# ---------------------------------------------------------
@patch('google.genai.Client')
async def test_int_05_ocr_and_confirm(mock_client_class, async_client: AsyncClient, auth_headers):
    import io
    from PIL import Image
    
    mock_instance = mock_client_class.return_value
    # Đã sửa cấu trúc JSON do AI trả về cho khớp với Backend (name, category)
    mock_instance.models.generate_content.return_value.text = '{"amount": -200000, "name": "Coopmart", "date": "2023-10-20", "category": "Mua sắm"}'
    
    image = Image.new('RGB', (1, 1), color = 'red')
    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='JPEG')
    img_bytes = img_byte_arr.getvalue()

    files = {'file': ('hoadon.jpg', img_bytes, 'image/jpeg')}
    resp_scan = await async_client.post("/api/expenses/scan-receipt", files=files, headers=auth_headers)
    assert resp_scan.status_code == 200, f"Lỗi Scan: {resp_scan.text}"
    
    extracted_data = resp_scan.json()
    
    # Đề phòng trường hợp API scan-receipt bọc kết quả trong {"data": {...}}
    payload = extracted_data.get("data", extracted_data)
    
    resp_confirm = await async_client.post("/api/expenses/scan-receipt/confirm", json=payload, headers=auth_headers)
    assert resp_confirm.status_code == 200, f"Lỗi xác nhận INT_05: {resp_confirm.text}"

# ---------------------------------------------------------
# INT_06: Quét File CSV
# ---------------------------------------------------------
@patch('google.genai.Client')
async def test_int_06_csv_and_categories(mock_client_class, async_client: AsyncClient, auth_headers):
    mock_instance = mock_client_class.return_value
    mock_instance.models.generate_content.return_value.text = '{"data": [{"date": "2023-10-01", "amount": -1000000, "category_id": 5, "note": "Đầu tư chứng khoán"}]}'
    
    files = {'file': ('data.csv', b"date,amount,note\n2023-10-01,-1000000,Dau tu", 'text/csv')}
    resp_scan = await async_client.post("/api/expenses/scan-csv", files=files, headers=auth_headers)
    assert resp_scan.status_code == 200
    
    csv_data = resp_scan.json().get("data", [])
    for row in csv_data:
        resp_save = await async_client.post("/api/expenses/", json=row, headers=auth_headers)
        assert resp_save.status_code == 200