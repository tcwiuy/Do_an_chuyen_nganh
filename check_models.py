import requests

# Thay bằng API Key của bạn (có thể dùng cái cũ để test trước khi xóa)
API_KEY = "AIzaSyCLEQRJIKnGw8ZaUDjGdzkTfaEm3j9WJ1g" 
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={API_KEY}"

response = requests.get(url)
models = response.json().get('models', [])

print("🔍 DANH SÁCH CÁC MÔ HÌNH GOOGLE ĐANG MỞ KHÓA CHO BẠN:")
print("-" * 50)
for m in models:
    # Chỉ lọc những model hỗ trợ chat/tạo nội dung (generateContent)
    if 'generateContent' in m.get('supportedGenerationMethods', []):
        # Tách bỏ chữ 'models/' ở đầu để lấy đúng tên bỏ vào URL
        code_name = m['name'].replace('models/', '')
        display_name = m.get('displayName', 'Không rõ')
        print(f"✅ Bỏ vào Code: {code_name}  --- (Tên trên Web: {display_name})")
print("-" * 50)