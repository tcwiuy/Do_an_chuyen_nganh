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
# TẠO USER, TOKEN VÀ MỘT GIAO DỊCH MẪU
# ==========================================
@pytest.fixture(scope="function")
def auth_and_transaction():
    """
    Tạo 1 User mới, đăng nhập lấy token, và tạo sẵn 1 giao dịch.
    Trả về token và ID của giao dịch vừa tạo để test xóa.
    """
    random_id = str(uuid.uuid4())[:8]
    username = f"del_user_{random_id}"
    password = "DelPassword123!"
    
    # 1. Đăng ký tài khoản ảo
    client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": password,
        "full_name": "Test Delete Transaction",
        "gender": "Nam",
        "dob": "2000-01-01"
    })
    
    # 2. Đăng nhập để lấy Access Token
    login_res = client.post("/api/auth/login", data={
        "username": username,
        "password": password
    })
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # 3. Thêm một giao dịch mẫu để tí nữa xóa
    tx_payload = {
        "name": "Tiền mạng tháng 11",
        "amount": -250000, 
        "category": "Hóa đơn",
        "date": "2023-11-15"
    }
    tx_res = client.post("/api/expenses/", json=tx_payload, headers=headers)
    transaction_id = tx_res.json()["id"]
    
    return {
        "headers": headers,
        "transaction_id": transaction_id
    }


# ==========================================
# CÁC TESTCASE XÓA GIAO DỊCH
# ==========================================

def test_delete_transaction_success(auth_and_transaction):
    """Test Case 1: Xóa thành công một giao dịch hợp lệ"""
    headers = auth_and_transaction["headers"]
    tx_id = auth_and_transaction["transaction_id"]
    
    response = client.delete(f"/api/expenses/{tx_id}", headers=headers)
    
    assert response.status_code == 200
    assert response.json()["message"] == "Đã xóa thành công"
    
    check_res = client.get("/api/expenses/", headers=headers)
    assert len(check_res.json()) == 0


def test_delete_transaction_not_found(auth_and_transaction):
    """Test Case 2: Xóa thất bại do truyền ID không tồn tại"""
    headers = auth_and_transaction["headers"]
    
    fake_id = "abcd1234_fake_id_khong_ton_tai"
    
    response = client.delete(f"/api/expenses/{fake_id}", headers=headers)
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Không tìm thấy giao dịch"


def test_delete_transaction_unauthorized(auth_and_transaction):
    """Test Case 3: Xóa thất bại do không có Token (Chưa đăng nhập)"""
    tx_id = auth_and_transaction["transaction_id"]
    
    response = client.delete(f"/api/expenses/{tx_id}")
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_delete_transaction_of_other_user(auth_and_transaction):
    """Test Case 4: Không thể xóa giao dịch của người khác (Bảo mật IDOR)"""
    tx_id_user_A = auth_and_transaction["transaction_id"]
    
    random_id = str(uuid.uuid4())[:8]
    username_B = f"hacker_user_{random_id}"
    password_B = "HackerPwd123!"
    
    client.post("/api/auth/register", json={
        "username": username_B,
        "email": f"{username_B}@example.com",
        "password": password_B,
        "full_name": "Kẻ Xấu Test IDOR",
        "gender": "Nam",
        "dob": "2000-01-01"
    })
    
    login_B = client.post("/api/auth/login", data={"username": username_B, "password": password_B})
    headers_B = {"Authorization": f"Bearer {login_B.json()['access_token']}"}
    
    response = client.delete(f"/api/expenses/{tx_id_user_A}", headers=headers_B)
    
    assert response.status_code == 404
    assert response.json()["detail"] == "Không tìm thấy giao dịch"