import os
import urllib.parse
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 1. Tải các biến môi trường từ file .env lên hệ thống
load_dotenv()

# 2. Lấy mật khẩu từ file .env (Không còn lộ trên code nữa)
my_password = os.getenv("DB_PASSWORD")

# Kiểm tra an toàn: Đảm bảo đã lấy được mật khẩu
if not my_password:
    raise ValueError("Không tìm thấy DB_PASSWORD trong file .env")

# 3. Tự động mã hóa mật khẩu an toàn
encoded_password = urllib.parse.quote_plus(my_password)

# 4. Gắn vào chuỗi URL
SQLALCHEMY_DATABASE_URL = f"postgresql://postgres:{encoded_password}@localhost:5432/expenseowl_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()