from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database import Base
import datetime
from sqlalchemy import Column, Integer, String, JSON

# Thêm bảng User (đề bài yêu cầu có đăng nhập)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    # Quan hệ 1-N với bảng Transaction
    transactions = relationship("Transaction", back_populates="owner")

# Bảng Transaction (Thay thế cho struct Expense trong Go)
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True) # Sửa thành primary_key
    name = Column(String, index=True)
    amount = Column(Float)
    category = Column(String, index=True)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    tags = Column(JSON) # Lưu list tags dưới dạng JSON
    
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="transactions")

# ... (giữ nguyên code cũ ở trên) ...

# Bảng Giao dịch định kỳ (Recurring Transaction)
class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    amount = Column(Float)
    category = Column(String, index=True)
    tags = Column(JSON)
    interval = Column(String) # daily, weekly, monthly, yearly
    startDate = Column(DateTime)
    occurrences = Column(Integer) # Số lần lặp lại (0 là vô hạn)

    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User")

class UserConfig(Base):
    __tablename__ = "user_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, unique=True) # ID của người dùng
    currency = Column(String, default="usd")
    startDate = Column(Integer, default=1)
    categories = Column(JSON, default=["Food", "Transport", "Shopping", "Bills", "Entertainment"])