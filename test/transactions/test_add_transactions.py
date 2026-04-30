import pytest
from fastapi.testclient import TestClient
import uuid
import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_dir)

from main import app

client = TestClient(app)

# ==========================================
# TẠO USER VÀ LẤY TOKEN 
# ==========================================
@pytest.fixture(scope="module")
def auth_headers():
    random_id = str(uuid.uuid4())[:8]
    username = f"add_tx_user_{random_id}"
    password = "StrongPassword123!"
    
    # 1. Đăng ký tài khoản
    client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": password,
        "full_name": "Test Add Transaction",
        "gender": "Nam",
        "dob": "2000-01-01"
    })
    
    # 2. Đăng nhập để lấy Token
    login_res = client.post("/api/auth/login", data={
        "username": username,
        "password": password
    })
    
    token = login_res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

# ==========================================
# CÁC KỊCH BẢN KIỂM THỬ CHO CHỨC NĂNG THÊM GIAO DỊCH
# ==========================================

def test_add_expense_transaction_success(auth_headers):
    """Test Case 1: Thêm một khoản CHI TIÊU hợp lệ (Số Âm)"""
    payload = {
        "name": "Đổ xăng xe máy",
        "amount": -60000, 
        "category": "Đi lại",
        "date": "2023-11-01",
        "tags": ["cash", "travel"],
        "note": "Đổ đầy bình"
    }
    
    response = client.post("/api/expenses/", json=payload, headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Đổ xăng xe máy"
    assert data["amount"] == -60000
    assert data["category"] == "Đi lại"
    assert "id" in data 


def test_add_income_transaction_success(auth_headers):
    """Test Case 2: Thêm một khoản THU NHẬP hợp lệ (Số Dương)"""
    payload = {
        "name": "Nhận lương tháng 10",
        "amount": 15000000, 
        "category": "Thu nhập",
        "date": "2023-11-05",
        "note": "Lương công ty chuyển khoản"
    }
    
    response = client.post("/api/expenses/", json=payload, headers=auth_headers)
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Nhận lương tháng 10"
    assert data["amount"] == 15000000
    assert data["category"] == "Thu nhập"


def test_add_transaction_missing_fields(auth_headers):
    """Test Case 3: Thêm giao dịch nhưng bỏ trống dữ liệu bắt buộc (Pydantic Validation)"""
    payload = {
        "name": "Giao dịch lỗi",
        "category": "Mua sắm"
    }
    
    response = client.post("/api/expenses/", json=payload, headers=auth_headers)
    
    assert response.status_code == 422


def test_add_transaction_unauthorized():
    """Test Case 4: Cố gắng thêm giao dịch khi chưa đăng nhập (Không truyền Token)"""
    payload = {
        "name": "Hack giao dịch",
        "amount": 500000,
        "category": "Giải trí",
        "date": "2023-11-10"
    }
    
    response = client.post("/api/expenses/", json=payload)
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"