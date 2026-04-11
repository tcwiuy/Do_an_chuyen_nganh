from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time
from selenium.webdriver.support.ui import Select

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

if __name__ == "__main__":
    test_frontend_flow()