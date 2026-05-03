from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, JSON, Date, Numeric
from sqlalchemy.orm import relationship
from database import Base
import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Boolean

# Bảng User (Đã cập nhật thêm thông tin cá nhân)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    
    full_name = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    dob = Column(Date, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    
    transactions = relationship("Transaction", back_populates="owner")

# Bảng Transaction
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    # ĐÃ SỬA: Dùng Numeric(15, 2) thay cho Float (Tối đa 15 chữ số, 2 số thập phân)
    amount = Column(Numeric(15, 2))
    category = Column(String, index=True)
    date = Column(DateTime, default=datetime.datetime.utcnow)
    tags = Column(JSON) 
    note = Column(String, nullable=True)
    recurring_interval = Column(String, nullable=True)
    
    jar_id = Column(Integer, ForeignKey("jars.id"), nullable=True)
    
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="transactions")

# Bảng Giao dịch định kỳ
class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, index=True)
    # ĐÃ SỬA: Dùng Numeric(15, 2)
    amount = Column(Numeric(15, 2))
    category = Column(String, index=True)
    tags = Column(JSON)
    interval = Column(String) 
    startDate = Column(DateTime)
    occurrences = Column(Integer) 

    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User")

# Bảng cấu hình cá nhân
class UserConfig(Base):
    __tablename__ = "user_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, unique=True)
    currency = Column(String, default="usd")
    startDate = Column(Integer, default=1)
    categories = Column(JSON, default=["Food", "Transport", "Shopping", "Bills", "Entertainment"])

    financial_goal = Column(String, nullable=True, default="Chưa xác định")
    risk_tolerance = Column(String, nullable=True, default="Cân bằng")
    is_email_sync_enabled = Column(Boolean, default=False)

class Budget(Base):
    __tablename__ = "budgets"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String, index=True)
    
    # Hạn mức tối đa được phép chi
    limit_amount = Column(Numeric(15, 2)) 
    
    period_type = Column(String, default="month") # Lưu loại: "week", "month", "year", "custom"
    start_date = Column(Date) # Ngày bắt đầu ngân sách
    end_date = Column(Date)   # Ngày kết thúc ngân sách
    
    user_id = Column(Integer, ForeignKey("users.id"))

class Jar(Base):
    __tablename__ = "jars"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String) 
    # ĐÃ SỬA: Dùng Numeric(15, 2)
    balance = Column(Numeric(15, 2), default=0.0)
    percent = Column(Numeric(15, 2), default=0.0) 

    goal_amount = Column(Numeric(15, 2), default=0.0) # Mục tiêu hũ (VD: 20tr)
    color = Column(String, default="#8a2be2")         # Màu đại diện
    icon = Column(String, default="fa-piggy-bank")   # Icon định danh
    
    user_id = Column(Integer, ForeignKey("users.id"))