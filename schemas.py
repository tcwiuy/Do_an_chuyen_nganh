from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional

# Base schema chứa các trường chung
class TransactionBase(BaseModel):
    name: str
    amount: float
    category: str
    date: datetime
    tags: Optional[List[str]] = []

# Schema dùng khi tạo mới (Create)
class TransactionCreate(TransactionBase):
    pass

# Schema dùng khi trả dữ liệu về (Response)
class TransactionResponse(TransactionBase):
    id: str
    user_id: int

    class Config:
        from_attributes = True # Cho phép Pydantic đọc dữ liệu từ SQLAlchemy Model

# --- SCHEMAS CHO GIAO DỊCH ĐỊNH KỲ ---
class RecurringTransactionBase(BaseModel):
    name: str
    amount: float
    category: str
    tags: Optional[List[str]] = []
    interval: str
    startDate: datetime
    occurrences: int

class RecurringTransactionCreate(RecurringTransactionBase):
    pass

class RecurringTransactionResponse(RecurringTransactionBase):
    id: str
    user_id: int

    class Config:
        from_attributes = True

# --- SCHEMAS CHO NGƯỜI DÙNG & ĐĂNG NHẬP ---
class UserCreate(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str