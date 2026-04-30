import pytest
from fastapi.testclient import TestClient
import uuid
import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_dir)

from main import app
client = TestClient(app)

# Tạo một chuỗi ngẫu nhiên để không bị trùng lặp dữ liệu với các lần test trước
random_id = str(uuid.uuid4())[:8]
REG_USERNAME = f"reg_user_{random_id}"
REG_EMAIL = f"reg_{random_id}@example.com"
REG_PASSWORD = "StrongPassword123!"

def test_register_success():
    """Test Case 1: Đăng ký thành công với dữ liệu hợp lệ"""
    payload = {
        "username": REG_USERNAME,
        "email": REG_EMAIL,
        "password": REG_PASSWORD,
        "full_name": "Người Dùng Đăng Ký",
        "gender": "Nam",
        "dob": "2000-01-01"
    }
    response = client.post("/api/auth/register", json=payload)
    
    assert response.status_code == 200
    assert response.json()["message"] == "Đăng ký thành công"

def test_register_duplicate_username():
    """Test Case 2: Đăng ký thất bại do trùng Username"""
    payload = {
        "username": REG_USERNAME, 
        "email": f"new_{REG_EMAIL}",
        "password": REG_PASSWORD,
        "full_name": "Người Dùng Trùng Tên",
        "gender": "Nữ",
        "dob": "2000-01-01"
    }
    response = client.post("/api/auth/register", json=payload)
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Tên đăng nhập đã tồn tại"

def test_register_duplicate_email():
    """Test Case 3: Đăng ký thất bại do trùng Email"""
    # Cố tình sử dụng lại REG_EMAIL vừa đăng ký ở Test Case 1
    payload = {
        "username": f"new_{REG_USERNAME}",
        "email": REG_EMAIL, 
        "password": REG_PASSWORD,
        "full_name": "Người Dùng Trùng Email",
        "gender": "Nam",
        "dob": "2000-01-01"
    }
    response = client.post("/api/auth/register", json=payload)
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Email này đã được sử dụng"