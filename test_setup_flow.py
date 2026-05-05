import requests
import random
import string

# Cấu hình
BASE_URL = "https://do-an-chuyen-nganh-lvju.onrender.com/" # Sửa lại port nếu bạn dùng port khác

def generate_random_user():
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return {
        "username": f"testuser_{suffix}",
        "password": "password123",
        "full_name": "Test User",
        "email": f"test_{suffix}@gmail.com",
        "gender": "Nam",
        "dob": "2000-01-01"
    }

def run_test():
    print("🚀 BẮT ĐẦU TEST LUỒNG SETUP WIZARD CROSS-DEVICE\n" + "="*50)
    user_data = generate_random_user()
    
    # BƯỚC 1: Đăng ký tài khoản
    print(f"1. Đăng ký tài khoản mới: {user_data['username']}")
    res_reg = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
    if res_reg.status_code != 200:
        print("❌ Lỗi đăng ký:", res_reg.text)
        return

    # BƯỚC 2: Đăng nhập lần đầu (Giả lập trên Laptop)
    print("\n2. Đăng nhập lần đầu (Giả lập Laptop)...")
    res_login_1 = requests.post(f"{BASE_URL}/api/auth/login", data={"username": user_data['username'], "password": user_data['password']})
    token_1 = res_login_1.json().get("access_token")
    headers_1 = {"Authorization": f"Bearer {token_1}"}

    # BƯỚC 3: Kiểm tra config lần 1
    print("3. Kiểm tra Config trên Laptop...")
    res_cfg_1 = requests.get(f"{BASE_URL}/api/config", headers=headers_1)
    is_new_user_1 = res_cfg_1.json().get("is_new_user")
    print(f"   => Máy chủ báo cáo is_new_user: {is_new_user_1} (Mong đợi: True)")

    # BƯỚC 4: Thực hiện hoàn tất Setup Wizard (Gửi API tạo danh mục)
    print("\n4. Thực hiện Setup Wizard trên Laptop (Lưu danh mục xuống DB)...")
    setup_payload = {
        "expenseCategories": ["Ăn uống", "Đi lại"],
        "incomeCategories": ["Lương"]
    }
    requests.post(f"{BASE_URL}/api/categories/edit", json=setup_payload, headers=headers_1)
    
    print("5. Kiểm tra lại Config trên Laptop sau khi setup...")
    res_cfg_1_after = requests.get(f"{BASE_URL}/api/config", headers=headers_1)
    print(f"   => Máy chủ báo cáo is_new_user: {res_cfg_1_after.json().get('is_new_user')} (Mong đợi: False)")

    # ==========================================================
    # BƯỚC 6: ĐĂNG NHẬP TRÊN THIẾT BỊ KHÁC (Giả lập Điện thoại)
    # ==========================================================
    print("\n" + "="*50)
    print("6. Đăng nhập trên thiết bị MỚI (Giả lập Điện thoại)...")
    res_login_2 = requests.post(f"{BASE_URL}/api/auth/login", data={"username": user_data['username'], "password": user_data['password']})
    token_2 = res_login_2.json().get("access_token")
    headers_2 = {"Authorization": f"Bearer {token_2}"}

    print("7. Kiểm tra Config trên Điện thoại...")
    res_cfg_2 = requests.get(f"{BASE_URL}/api/config", headers=headers_2)
    is_new_user_2 = res_cfg_2.json().get("is_new_user")
    print(f"   => Máy chủ báo cáo is_new_user: {is_new_user_2}")

    # ĐÁNH GIÁ KẾT QUẢ
    print("\n" + "="*50)
    if is_new_user_1 == True and is_new_user_2 == False:
        print("✅ BACKEND HOẠT ĐỘNG HOÀN HẢO! Lỗi nằm ở Frontend (index.html) đang dùng localStorage thay vì đọc cờ 'is_new_user' từ máy chủ.")
    else:
        print("❌ BACKEND CÓ LỖI! Cờ 'is_new_user' không cập nhật đúng trạng thái.")

if __name__ == "__main__":
    run_test()