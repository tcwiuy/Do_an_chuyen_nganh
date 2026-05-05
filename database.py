import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Tải các biến môi trường từ file .env (Dành cho lúc bạn test code ở máy cá nhân)
load_dotenv()

# 2. Lấy TOÀN BỘ chuỗi kết nối từ biến môi trường
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

# Kiểm tra an toàn: Đảm bảo đã lấy được URL
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("Không tìm thấy DATABASE_URL. Hãy kiểm tra lại biến môi trường!")

# Fix lỗi tương thích của SQLAlchemy (Bắt buộc phải là postgresql:// thay vì postgres://)
if SQLALCHEMY_DATABASE_URL.startswith("postgres://"):
    SQLALCHEMY_DATABASE_URL = SQLALCHEMY_DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 3. Khởi tạo engine kết nối
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()