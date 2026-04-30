import pytest
from fastapi.testclient import TestClient
import uuid
from main import app

client = TestClient(app)

# Tạo dữ liệu ngẫu nhiên cho file test login
random_id = str(uuid.uuid4())[:8]
LOGIN_USERNAME = f"login_user_{random_id}"
LOGIN_EMAIL = f"login_{random_id}@example.com"
LOGIN_PASSWORD = "ValidPassword123!"


@pytest.fixture(autouse=True, scope="module")
def setup_user_for_login():
    """
    Hàm này tự động chạy TRƯỚC KHI các test case bên dưới bắt đầu.
    Nó đóng vai trò 'mồi' dữ liệu: Tự động gọi API Đăng ký để lưu LOGIN_USERNAME vào Database.
    Nhờ vậy, khi test Đăng nhập sẽ không bao giờ bị lỗi 401 do user không tồn tại.
    """
    client.post("/api/auth/register", json={
        "username": LOGIN_USERNAME,
        "email": LOGIN_EMAIL,
        "password": LOGIN_PASSWORD,
        "full_name": "Tài Khoản Test Login",
        "gender": "Nam",
        "dob": "1999-01-01"
    })

def test_login_success():
    """Test Case 1: Đăng nhập thành công"""
    payload = {
        "username": LOGIN_USERNAME,
        "password": LOGIN_PASSWORD
    }
    response = client.post("/api/auth/login", data=payload)
    
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"

def test_login_wrong_password():
    """Test Case 2: Đăng nhập thất bại do sai mật khẩu"""
    payload = {
        "username": LOGIN_USERNAME,
        "password": "WrongPassword999!" # Cố tình nhập sai mật khẩu
    }
    response = client.post("/api/auth/login", data=payload)
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Tên đăng nhập hoặc mật khẩu không đúng"

def test_login_nonexistent_user():
    """Test Case 3: Đăng nhập thất bại do user hoàn toàn không tồn tại"""
    payload = {
        "username": "taikhoan_ma_khong_ton_tai_404",
        "password": LOGIN_PASSWORD
    }
    response = client.post("/api/auth/login", data=payload)
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Tên đăng nhập hoặc mật khẩu không đúng"