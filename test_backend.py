from fastapi.testclient import TestClient
from main import app  # Import app từ file main.py của bạn
import random

# Tạo một "khách giả" để gọi API
client = TestClient(app)

def test_register_and_login():
    """Test kịch bản: Đăng ký một user mới, sau đó dùng user đó đăng nhập"""
    
    # Tạo số ngẫu nhiên để username không bị trùng khi chạy test nhiều lần
    test_username = f"minh_test_{random.randint(1000, 9999)}"
    test_password = "password123"

    # 1. TEST ĐĂNG KÝ
    res_register = client.post("/api/auth/register", json={
        "username": test_username,
        "password": test_password
    })
    # Kì vọng: Trả về mã 200 (Thành công)
    assert res_register.status_code == 200
    assert res_register.json() == {"message": "Đăng ký thành công"}

    # 2. TEST ĐĂNG NHẬP
    res_login = client.post("/api/auth/login", data={
        "username": test_username,
        "password": test_password
    })
    # Kì vọng: Trả về mã 200 và có chứa access_token
    assert res_login.status_code == 200
    assert "access_token" in res_login.json()
    print("\n✅ Backend: Test Đăng ký & Đăng nhập thành công!")