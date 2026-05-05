# Sử dụng Python 3.10 (hoặc thay bằng phiên bản bạn đang dùng)
FROM python:3.10-slim

# Đặt thư mục làm việc trong container
WORKDIR /app

# Copy file requirements và cài đặt thư viện
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toàn bộ mã nguồn vào container
COPY . .

# Mở port 8000
EXPOSE 8000

# Lệnh khởi chạy ứng dụng (Sử dụng uvicorn cho FastAPI)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]