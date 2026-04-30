from fastapi.testclient import TestClient
from main import app  # Import app từ file main.py của bạn
import random
import time

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

def test_create_and_fetch_expense():
    # 1. Đăng nhập để lấy "giấy phép" (Token)
    # Lưu ý: Thay "minh" và "123456" bằng tài khoản test của bạn nhé
    login_response = client.post("/api/auth/login", data={"username": "a", "password": "123"})
    assert login_response.status_code == 200, "Đăng nhập thất bại"
    
    token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Gửi API tạo một khoản chi tiêu mới
    new_expense = {
        "name": "Trà sữa trân châu (Test)",
        "amount": -45000,
        "category": "Food",
        "date": "2026-04-15"
    }
    create_response = client.post("/api/expenses/", json=new_expense, headers=headers)
    assert create_response.status_code == 200, "Lỗi API thêm chi tiêu"
    assert create_response.json()["name"] == "Trà sữa trân châu (Test)"

    # 3. Gửi API lấy danh sách chi tiêu về xem có khoản vừa thêm không
    get_response = client.get("/api/expenses/", headers=headers)
    assert get_response.status_code == 200
    expenses = get_response.json()
    assert len(expenses) > 0
    
    print("\n✅ Backend: Test API Thêm và Đọc chi tiêu thành công!")

def test_ai_chatbot_response():
    # 1. Đăng nhập để lấy "giấy phép" (Token)
    # LƯU Ý: Đảm bảo tài khoản "minh" và pass "123456" là đúng nhé
    login_response = client.post("/api/auth/login", data={"username": "a", "password": "123"})
    assert login_response.status_code == 200, "Đăng nhập thất bại"
    
    token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    # Cho hệ thống nghỉ 5 giây để Google API xả trạm
    print("\n⏳ Đang cho hệ thống nghỉ 5s để tránh nghẽn mạng Google...")
    time.sleep(5)

    # 2. Gửi một tin nhắn bằng ngôn ngữ tự nhiên cho Cú Mèo
    chat_payload = {
        "message": "Cú Mèo ơi, hôm nay tôi vừa tiêu 55k để uống trà đào cam sả nhé",
        "history": []
    }
    
    print("\n🦉 Đang gọi Cú Mèo (Xin đợi vài giây để AI suy nghĩ)...")
    chat_response = client.post("/api/ai/chat", json=chat_payload, headers=headers)
    
    # 3. Kiểm tra xem Cú Mèo có trả lời không
    assert chat_response.status_code == 200, f"Lỗi gọi AI: {chat_response.text}"
    reply_data = chat_response.json()
    
    assert "reply" in reply_data, "AI không trả về câu trả lời"
    print(f"✅ Backend: Cú Mèo trả lời thành công: \"{reply_data['reply'][:60]}...\"")

    # 4. Kiểm tra xem Cú Mèo có tự động LƯU khoản 55k đó vào Database không!
    get_response = client.get("/api/expenses/", headers=headers)
    expenses = get_response.json()
    
    # Tìm xem có giao dịch nào 55k do AI tự lưu không (AI luôn lưu số âm cho chi tiêu)
    ai_saved_expense = next((exp for exp in expenses if exp["amount"] == -55000), None)
    
    assert ai_saved_expense is not None, "Cú Mèo đã trả lời nhưng QUÊN lưu vào Database!"
    print("✅ Backend: Trí tuệ nhân tạo đã tự động bóc tách và LƯU giao dịch 55,000đ thành công!")

def test_update_and_delete_expense():
    # 1. Đăng nhập lấy Token
    login_response = client.post("/api/auth/login", data={"username": "a", "password": "123"})
    token = login_response.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Tạo một giao dịch nháp để chuẩn bị test
    new_expense = {"name": "Đồ ăn vặt (Nháp)", "amount": -15000, "category": "Food", "date": "2026-04-15"}
    create_res = client.post("/api/expenses/", json=new_expense, headers=headers)
    item_id = create_res.json()["id"]

    # 3. TEST UPDATE (Sửa giao dịch)
    updated_expense = {"name": "Ăn trưa (Đã sửa)", "amount": -40000, "category": "Food", "date": "2026-04-15", "tags": ["Đã update"]}
    update_res = client.put(f"/api/expenses/{item_id}", json=updated_expense, headers=headers)
    
    assert update_res.status_code == 200, "Lỗi API cập nhật"
    assert update_res.json()["name"] == "Ăn trưa (Đã sửa)", "Tên không được cập nhật"
    assert update_res.json()["amount"] == -40000, "Số tiền không được cập nhật"
    print("\n✅ Backend: Test API Cập nhật (Sửa) chi tiêu thành công!")

    # 4. TEST DELETE (Xóa giao dịch)
    delete_res = client.delete(f"/api/expenses/{item_id}", headers=headers)
    assert delete_res.status_code == 200, "Lỗi API xóa"

    # 5. Xác minh xem đã thực sự bay màu khỏi Database chưa
    get_res = client.get("/api/expenses/", headers=headers)
    expenses = get_res.json()
    found = any(exp["id"] == item_id for exp in expenses)
    assert found is False, "Giao dịch vẫn còn tồn tại sau khi xóa!"
    print("✅ Backend: Test API Xóa chi tiêu dứt điểm thành công!")