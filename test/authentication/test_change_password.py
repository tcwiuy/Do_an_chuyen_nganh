import pytest
from fastapi.testclient import TestClient
import uuid

import sys
import os

root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(root_dir)

from main import app
client = TestClient(app)

# 🌟 FIXTURE NÀY TẠO TÀI KHOẢN MỚI CHO MỖI TEST CASE 
@pytest.fixture(scope="function")
def test_user():
    """
    Hàm này tự động tạo 1 User mới và Đăng nhập để lấy Token.
    Chạy lại từ đầu cho mỗi Test Case (để đảm bảo tính độc lập).
    """
    random_id = str(uuid.uuid4())[:8]
    username = f"user_pwd_{random_id}"
    old_password = "OldPassword123!"
    
    # 1. Đăng ký tài khoản
    client.post("/api/auth/register", json={
        "username": username,
        "email": f"{username}@example.com",
        "password": old_password,
        "full_name": "Người Dùng Đổi Mật Khẩu",
        "gender": "Nam",
        "dob": "2000-01-01"
    })
    
    # 2. Đăng nhập để lấy Access Token
    login_res = client.post("/api/auth/login", data={
        "username": username,
        "password": old_password
    })
    
    token = login_res.json()["access_token"]
    
    # Trả về các thông tin cần thiết cho Test Case sử dụng
    return {
        "username": username,
        "old_password": old_password,
        "token": token
    }

# ==========================================
# CÁC KỊCH BẢN KIỂM THỬ ĐỔI MẬT KHẨU
# ==========================================

def test_change_password_success(test_user):
    """Test Case 1: Đổi mật khẩu thành công (Happy Case)"""
    new_password = "NewPassword456!"
    
    headers = {"Authorization": f"Bearer {test_user['token']}"}
    payload = {
        "old_password": test_user["old_password"],
        "new_password": new_password
    }
    
    # Gửi API Đổi mật khẩu
    response = client.put("/api/auth/change-password", json=payload, headers=headers)
    
    assert response.status_code == 200
    assert response.json()["message"] == "Đổi mật khẩu thành công!"
    
    # [KIỂM TRA CHÉO]: Đăng nhập bằng Mật khẩu cũ phải thất bại
    login_old = client.post("/api/auth/login", data={
        "username": test_user["username"],
        "password": test_user["old_password"]
    })
    assert login_old.status_code == 401
    
    # [KIỂM TRA CHÉO]: Đăng nhập bằng Mật khẩu mới phải thành công
    login_new = client.post("/api/auth/login", data={
        "username": test_user["username"],
        "password": new_password
    })
    assert login_new.status_code == 200
    assert "access_token" in login_new.json()


def test_change_password_wrong_old_password(test_user):
    """Test Case 2: Đổi mật khẩu thất bại do nhập sai Mật khẩu cũ"""
    headers = {"Authorization": f"Bearer {test_user['token']}"}
    payload = {
        "old_password": "WrongPassword999!", # Cố tình nhập sai mật khẩu hiện tại
        "new_password": "NewPassword456!"
    }
    
    response = client.put("/api/auth/change-password", json=payload, headers=headers)
    
    # Đúng với logic code trong routers.py: raise HTTPException 400
    assert response.status_code == 400
    assert response.json()["detail"] == "Mật khẩu hiện tại không chính xác!"


def test_change_password_same_as_old(test_user):
    """Test Case 3: Đổi mật khẩu thất bại do Mật khẩu mới trùng Mật khẩu cũ"""
    headers = {"Authorization": f"Bearer {test_user['token']}"}
    payload = {
        "old_password": test_user["old_password"],
        "new_password": test_user["old_password"] # Cố tình lấy pass mới giống pass cũ
    }
    
    response = client.put("/api/auth/change-password", json=payload, headers=headers)
    
    # Đúng với logic code trong routers.py: raise HTTPException 400
    assert response.status_code == 400
    assert response.json()["detail"] == "Mật khẩu mới không được giống mật khẩu cũ!"


def test_change_password_unauthorized():
    """Test Case 4: Không thể đổi mật khẩu nếu không có Token (Chưa đăng nhập)"""
    # Không truyền headers chứa Authorization Bearer
    payload = {
        "old_password": "OldPassword123!",
        "new_password": "NewPassword456!"
    }
    
    response = client.put("/api/auth/change-password", json=payload)
    
    # Middleware của FastAPI sẽ chặn lại và ném ra lỗi 401
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"