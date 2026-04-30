from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def test_frontend_flow():
    """Test kịch bản: Robot tự động Đăng nhập -> Sang trang Table -> Thêm giao dịch mới"""
    
    # Tự động tải driver và mở Chrome
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)

    try:
        # ==========================================
        # BƯỚC 1: ĐĂNG NHẬP
        # ==========================================
        print("\n🤖 Robot đang mở trang web...")
        # LƯU Ý: Phải đảm bảo server Uvicorn đang chạy ở port 8001
        driver.get("http://127.0.0.1:8001/login")
        time.sleep(2) # Đợi web load xong

        # Tìm ô nhập liệu trên giao diện
        username_input = driver.find_element(By.ID, "username")
        password_input = driver.find_element(By.ID, "password")

        print("🤖 Robot đang điền thông tin...")
        # NHỚ SỬA LẠI TÀI KHOẢN VÀ MẬT KHẨU CÓ THẬT CỦA BẠN NẾU CẦN
        username_input.send_keys("a") 
        password_input.send_keys("123") 

        print("🤖 Robot đang bấm nút đăng nhập...")
        login_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_btn.click()

        time.sleep(3) # Đợi hệ thống chuyển trang sang Dashboard

        # KIỂM TRA ĐĂNG NHẬP
        assert "login" not in driver.current_url, "Lỗi: Đăng nhập thất bại. Sai tài khoản hoặc pass!"
        print("✅ Frontend: Robot đăng nhập thành công và đã vào Dashboard!")

        # ==========================================
        # BƯỚC 2: THÊM GIAO DỊCH MỚI
        # ==========================================
        print("🤖 Robot đang chuyển sang trang Quản lý (Table)...")
        driver.get("http://127.0.0.1:8001/table")
        time.sleep(2) # Đợi trang load dữ liệu

        print("🤖 Robot đang tự động nhập hóa đơn...")
        # Tìm ô nhập liệu và điền chữ
        driver.find_element(By.ID, "name").send_keys("Cà phê tự động chạy bằng Code")
        driver.find_element(By.ID, "amount").send_keys("35")
        driver.find_element(By.ID, "date").send_keys("04/15/2026") # Nhập ngày

        # Chọn danh mục Food từ menu thả xuống
        category_select = Select(driver.find_element(By.ID, "category"))
        category_select.select_by_value("Food")

        # Bấm nút Thêm
        # Bấm nút Thêm (Tìm theo XPath vì nút không có ID)
        submit_btn = driver.find_element(By.XPATH, "//form[@id='expenseForm']//button[@type='submit']")
        submit_btn.click()
        time.sleep(2) # Đợi hệ thống xử lý và tải lại bảng

        # Kiểm tra xem giao dịch đã thực sự hiện lên bảng chưa
        assert "Cà phê tự động chạy bằng Code" in driver.page_source, "Lỗi: Không tìm thấy giao dịch vừa thêm trên màn hình!"
        print("✅ Frontend: Robot đã thêm chi tiêu mới và xác nhận thành công!")

        # Tạm dừng 3 giây cho bạn ngắm thành quả trước khi tắt trình duyệt
        time.sleep(3)

    except Exception as e:
        print(f"❌ Frontend Test thất bại. Lỗi: {e}")
        
    finally:
        # Tắt trình duyệt sau khi làm xong
        print("🤖 Robot đang dọn dẹp và đóng trình duyệt...")
        time.sleep(2)
        driver.quit()

def test_frontend_advanced():
    """Test kịch bản: Robot xóa giao dịch và test trang Lập Kế Hoạch AI"""
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)

    try:
        # 1. ĐĂNG NHẬP NHANH
        print("\n🤖 Robot đang đăng nhập để test luồng nâng cao...")
        driver.get("http://127.0.0.1:8001/login")
        time.sleep(1)
        driver.find_element(By.ID, "username").send_keys("a")
        driver.find_element(By.ID, "password").send_keys("123")
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(2)

        # 2. VÀO BẢNG VÀ XÓA 1 GIAO DỊCH
        print("🤖 Robot đang test tính năng Xóa có Popup cảnh báo...")
        driver.get("http://127.0.0.1:8001/table")
        time.sleep(2)
        
        # Tìm nút xóa đầu tiên trong bảng và bấm
        delete_btns = driver.find_elements(By.CLASS_NAME, "delete-button")
        if delete_btns:
            delete_btns[0].click()
            time.sleep(1) # Đợi modal hiện lên
            # Bấm nút Confirm Delete màu đỏ
            driver.find_element(By.XPATH, "//button[contains(@class, 'confirm')]").click()
            time.sleep(1)
            print("✅ Frontend: Robot đã test Popup và Xóa thành công!")
        else:
            print("⚠️ Bảng trống, bỏ qua bước test xóa.")

        # 3. SANG TRANG GỢI Ý AI VÀ LẬP KẾ HOẠCH
        print("🤖 Robot đang chuyển sang trang AI Suggestions...")
        driver.get("http://127.0.0.1:8001/suggestions")
        time.sleep(2)

        # Điền form mục tiêu
        driver.find_element(By.ID, "goalName").send_keys("Mua Laptop mới")
        driver.find_element(By.ID, "goalAmount").send_keys("15000000")
        driver.find_element(By.ID, "goalMonths").send_keys("6")
        
        print("🤖 Robot đang ra lệnh cho AI lập kế hoạch...")
        driver.find_element(By.ID, "btnGenerateSuggestions").click()

        print("🤖 Robot đang kiên nhẫn đợi AI tính toán (tối đa 60 giây)...")
        # Sử dụng WebDriverWait để chờ cho đến khi khung kết quả xuất hiện chữ "Chiến lược Tổng thể"
        wait = WebDriverWait(driver, 60)
        wait.until(EC.text_to_be_present_in_element((By.ID, "suggestionsSummary"), "Chiến lược Tổng thể"))
        
        print("✅ Frontend: Robot đã ép AI lập kế hoạch Mua Laptop thành công rực rỡ!")

        time.sleep(3)

    except Exception as e:
        print(f"❌ Frontend Test nâng cao thất bại. Lỗi: {e}")
        
    finally:
        print("🤖 Robot đang dọn dẹp...")
        driver.quit()

if __name__ == "__main__":
    #test_frontend_flow()
    test_frontend_advanced()