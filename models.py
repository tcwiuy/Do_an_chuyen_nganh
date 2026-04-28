from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Date
from sqlalchemy.orm import relationship
from database import Base
import datetime

# Bảng User (Đã cập nhật thêm thông tin cá nhân)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    # --- THÊM 4 CỘT THÔNG TIN MỚI Ở ĐÂY ---
    full_name = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    dob = Column(Date, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    # --------------------------------------
    
    # Quan hệ 1-N với bảng Transaction
    transactions = relationship("Transaction", back_populates="owner")

# Bảng Transaction (Thay thế cho struct Expense trong Go)
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    amount = Column(Float)
    category = Column(String, index=True)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    tags = Column(JSON) 
    note = Column(String, nullable=True)
    recurring_interval = Column(String, nullable=True)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="transactions")

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

# Bảng cấu hình cá nhân của người dùng
class UserConfig(Base):
    __tablename__ = "user_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, unique=True) # ID của người dùng
    currency = Column(String, default="usd")
    startDate = Column(Integer, default=1)
    categories = Column(JSON, default=["Ăn uống", "Đi lại", "Mua sắm", "Hóa đơn", "Giải trí"])

    financial_goal = Column(String, nullable=True, default="Chưa xác định")
    risk_tolerance = Column(String, nullable=True, default="Cân bằng")

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True)
    limit_amount = Column(Float) # Hạn mức thiết lập
    spent_amount = Column(Float, default=0.0) # Số tiền đã tiêu thực tế
    month = Column(Integer)
    year = Column(Integer)
    user_id = Column(Integer, ForeignKey("users.id"))

class Jar(Base):
    __tablename__ = "jars"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String) 
    balance = Column(Float, default=0.0)
    percent = Column(Float, default=0.0) 
    user_id = Column(Integer, ForeignKey("users.id"))