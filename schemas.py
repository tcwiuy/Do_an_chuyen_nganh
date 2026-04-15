from datetime import date
from pydantic import BaseModel, field_validator, Field
from datetime import datetime, date # Đã sửa lại import cho chuẩn
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


# --- SCHEMAS CHO GIAO DỊCH THÔNG THƯỜNG ---
class TransactionBase(BaseModel):
    name: str
    amount: float
    category: str
    date: datetime
    tags: Optional[List[str]] = Field(default_factory=list)

    # 1. Chặn số tiền bằng 0 hoặc lớn hơn 1 tỷ VNĐ
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, value):
        if value == 0:
            raise ValueError("Số tiền giao dịch không được bằng 0.")
        if value > 1000000000 or value < -1000000000:  
            raise ValueError("Số tiền giao dịch quá lớn (vượt quá 1 tỷ VNĐ), hệ thống từ chối ghi nhận!")
        return value

    # 2. Chặn tên giao dịch nhập cho có (VD: "A", "B")
    @field_validator('name')
    @classmethod
    def validate_name(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Tên giao dịch không hợp lệ (phải có ít nhất 2 ký tự).")
        return value

    # 3. Chặn chọn nhầm năm quá xa trong tương lai
    @field_validator('date')
    @classmethod
    def validate_date(cls, value):
        if value.year > 2050:
            raise ValueError("Năm giao dịch vô lý (Không được vượt quá năm 2050).")
        return value

class TransactionCreate(TransactionBase):
    pass

# Ở các class TransactionResponse, RecurringTransactionResponse, UserResponse
class TransactionResponse(TransactionBase):
    id: str
    
    # Xóa "class Config:" đi và thay bằng 1 dòng này:
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS CHO GIAO DỊCH ĐỊNH KỲ ---
class RecurringTransactionBase(BaseModel):
    name: str
    amount: float
    category: str
    tags: Optional[List[str]] = []
    interval: str
    startDate: datetime
    occurrences: int

    # Áp dụng các chốt chặn tương tự cho giao dịch định kỳ
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, value):
        if value == 0:
            raise ValueError("Số tiền giao dịch không được bằng 0.")
        if value > 1000000000 or value < -1000000000:  
            raise ValueError("Số tiền giao dịch quá lớn (vượt quá 1 tỷ VNĐ).")
        return value

    @field_validator('name')
    @classmethod
    def validate_name(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Tên giao dịch phải có ít nhất 2 ký tự.")
        return value

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
    full_name: str
    gender: str
    dob: date
    email: str

class UserResponse(BaseModel):
    id: int
    username: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class UserUpdatePassword(BaseModel):
    old_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, value):
        if len(value) < 6:
            raise ValueError("Mật khẩu mới phải có ít nhất 6 ký tự.")
        if len(value) > 72:
            raise ValueError("Mật khẩu mới quá dài! Vui lòng nhập dưới 72 ký tự.")
        return value