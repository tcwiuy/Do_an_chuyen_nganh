import requests
import random
import string
import json

# Cấu hình URL Backend của bạn (Sửa lại port nếu bạn chạy port khác)
BASE_URL = "https://do-an-chuyen-nganh-lvju.onrender.com/"

def generate_random_user():
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
    return {
        "username": f"tester_{suffix}",
        "password": "password123",
        "full_name": "QA Tester",
        "email": f"tester_{suffix}@gmail.com",
        "gender": "Nam",
        "dob": "2000-01-01"
    }

def print_step(step_num, title):
    print(f"\n[BƯỚC {step_num}] {title}")
    print("-" * 50)

def run_test():
    print("🚀 BẮT ĐẦU CHẠY BÀI TEST ĐỒNG BỘ FRONTEND & BACKEND SETUP WIZARD")
    print("=" * 60)
    
    user_data = generate_random_user()
    
    # ---------------------------------------------------------
    # BƯỚC 1: TẠO TÀI KHOẢN MỚI
    # ---------------------------------------------------------
    print_step(1, f"Đăng ký tài khoản mới: {user_data['username']}")
    res_reg = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
    if res_reg.status_code != 200:
        print("❌ LỖI: Không thể đăng ký tài khoản. Máy chủ trả về:", res_reg.text)
        return
    print("✅ Đăng ký thành công.")

    # ---------------------------------------------------------
    # BƯỚC 2: ĐĂNG NHẬP TRÊN THIẾT BỊ 1 (Giả lập Laptop)
    # ---------------------------------------------------------
    print_step(2, "Đăng nhập lần đầu (Giả lập môi trường Laptop)")
    res_login_1 = requests.post(f"{BASE_URL}/api/auth/login", data={"username": user_data['username'], "password": user_data['password']})
    token_1 = res_login_1.json().get("access_token")
    headers_1 = {"Authorization": f"Bearer {token_1}", "Content-Type": "application/json"}
    print("✅ Đăng nhập Laptop thành công. Đã lấy được Token.")

    # ---------------------------------------------------------
    # BƯỚC 3: FRONTEND KIỂM TRA TRẠNG THÁI SETUP BAN ĐẦU
    # ---------------------------------------------------------
    print_step(3, "Frontend gọi API /api/config để kiểm tra trạng thái Setup")
    res_cfg_1 = requests.get(f"{BASE_URL}/api/config", headers=headers_1)
    config_1 = res_cfg_1.json()
    
    is_new_user = config_1.get("is_new_user")
    print(f"   => Máy chủ báo cáo is_new_user: {is_new_user}")
    
    if is_new_user is True:
        print("✅ Frontend PASS: Máy chủ nhận diện đúng user mới. Frontend SẼ HIỂN THỊ bảng Setup Wizard.")
    else:
        print("❌ LỖI: Máy chủ không nhận diện được user mới.")
        return

    # ---------------------------------------------------------
    # BƯỚC 4: THỰC HIỆN SETUP WIZARD (Lưu dữ liệu xuống Backend)
    # ---------------------------------------------------------
    print_step(4, "Frontend gửi dữ liệu Setup Wizard xuống Backend")
    
    # 4.1 Lưu Danh mục
    cat_payload = {
        "expenseCategories": ["Ăn uống", "Đi lại", "Mua sắm", "Du lịch"],
        "incomeCategories": ["Lương", "Thưởng", "Lì xì"]
    }
    print("   -> Gửi API lưu Danh mục...")
    requests.post(f"{BASE_URL}/api/categories/edit", json=cat_payload, headers=headers_1)
    
    # 4.2 Lưu Hồ sơ AI (Mục tiêu, Rủi ro)
    profile_payload = {"goal": "Mua sắm tài sản lớn", "risk": "Mạo hiểm"}
    print("   -> Gửi API lưu Hồ sơ AI Cú Mèo...")
    requests.post(f"{BASE_URL}/api/profile/edit", json=profile_payload, headers=headers_1)

    print("✅ Đã mô phỏng xong thao tác bấm nút 'Hoàn tất' trên bảng Setup.")

    # ---------------------------------------------------------
    # BƯỚC 5: ĐĂNG NHẬP TRÊN THIẾT BỊ 2 (Giả lập Điện thoại)
    # ---------------------------------------------------------
    print_step(5, "Đăng nhập trên thiết bị KHÁC (Giả lập môi trường Điện thoại)")
    res_login_2 = requests.post(f"{BASE_URL}/api/auth/login", data={"username": user_data['username'], "password": user_data['password']})
    token_2 = res_login_2.json().get("access_token")
    headers_2 = {"Authorization": f"Bearer {token_2}", "Content-Type": "application/json"}
    print("✅ Đăng nhập Điện thoại thành công. Đã lấy được Token mới.")

    # ---------------------------------------------------------
    # BƯỚC 6: KIỂM TRA ĐỒNG BỘ TRÊN THIẾT BỊ 2
    # ---------------------------------------------------------
    print_step(6, "Điện thoại gọi API /api/config để load cấu hình (Kiểm tra Đồng bộ)")
    res_cfg_2 = requests.get(f"{BASE_URL}/api/config", headers=headers_2)
    config_2 = res_cfg_2.json()
    
    is_new_user_2 = config_2.get("is_new_user")
    print(f"   => Máy chủ báo cáo is_new_user: {is_new_user_2}")
    print(f"   => Danh mục Chi: {config_2.get('expenseCategories')}")
    print(f"   => Mục tiêu AI: {config_2.get('financial_goal')}")

    print("\n" + "=" * 60)
    print("🏆 KẾT QUẢ ĐÁNH GIÁ (TEST ASSERTIONS):")
    
    passed = True
    
    # Test 1: Cờ Setup đã tắt chưa?
    if is_new_user_2 is False:
        print("✅ Test 1 PASS: Cờ is_new_user đã chuyển thành False (Điện thoại sẽ KHÔNG hiện lại bảng Setup).")
    else:
        print("❌ Test 1 FAIL: Cờ is_new_user vẫn là True. Backend chưa tắt cờ hoặc Frontend lưu sai chỗ.")
        passed = False
        
    # Test 2: Dữ liệu danh mục có đồng bộ không?
    if config_2.get("expenseCategories") == cat_payload["expenseCategories"]:
        print("✅ Test 2 PASS: Danh mục chi tiêu đã được đồng bộ chính xác xuống điện thoại.")
    else:
        print("❌ Test 2 FAIL: Danh mục chi tiêu không khớp!")
        passed = False

    # Test 3: Hồ sơ AI có đồng bộ không?
    if config_2.get("financial_goal") == profile_payload["goal"]:
        print("✅ Test 3 PASS: Hồ sơ AI Cú Mèo đã được đồng bộ chính xác.")
    else:
        print("❌ Test 3 FAIL: Hồ sơ AI không khớp!")
        passed = False

    print("=" * 60)
    if passed:
        print("🎉 XUẤT SẮC! Cả Frontend và Backend đã giao tiếp và đồng bộ hoàn hảo với nhau qua mọi thiết bị!")
    else:
        print("⚠️ CÓ LỖI! Vui lòng kiểm tra lại code Backend phần lưu UserConfig.")

if __name__ == "__main__":
    run_test()