from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time

def test_login_ui():
    """Test kịch bản: Robot tự động mở Chrome, nhập thông tin và bấm Đăng nhập"""
    
    # Tự động tải driver và mở Chrome
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service)

    try:
        print("\n🤖 Robot đang mở trang web...")
        # LƯU Ý: Phải đảm bảo server Uvicorn đang chạy ở port 8001
        driver.get("http://127.0.0.1:8001/login")
        time.sleep(2) # Đợi web load xong

        # Tìm ô nhập liệu trên giao diện (Đảm bảo ID khớp với file login.html)
        username_input = driver.find_element(By.ID, "username")
        password_input = driver.find_element(By.ID, "password")

        print("🤖 Robot đang điền thông tin...")
        # ĐIỀN THÔNG TIN USER CÓ THẬT TRONG MÁY BẠN VÀO ĐÂY
        username_input.send_keys("admin") 
        password_input.send_keys("pass123") 

        print("🤖 Robot đang bấm nút đăng nhập...")
        # Tìm nút có type='submit' và click
        login_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
        login_btn.click()

        time.sleep(3) # Đợi hệ thống chuyển trang sang Dashboard

        # KIỂM TRA KẾT QUẢ: Nếu URL không còn chữ 'login' nghĩa là đã vào trong thành công
        assert "login" not in driver.current_url
        print("✅ Frontend: Robot đăng nhập thành công và đã vào Dashboard!")

    except Exception as e:
        print(f"❌ Frontend Test thất bại. Lỗi: {e}")
        
    finally:
        # Tắt trình duyệt sau khi làm xong
        time.sleep(2)
        driver.quit()

if __name__ == "__main__":
    test_login_ui()