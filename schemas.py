from datetime import date, datetime
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, field_validator, Field, ConfigDict

# --- SCHEMAS CHO CẤU HÌNH NGƯỜI DÙNG ---
class CategoriesPayload(BaseModel):
    """Schema dùng để hứng dữ liệu 2 mảng Thu - Chi từ Frontend gửi lên"""
    expenseCategories: List[str] = Field(default_factory=list)
    incomeCategories: List[str] = Field(default_factory=list)

# --- SCHEMAS CHO GIAO DỊCH THÔNG THƯỜNG ---
class TransactionBase(BaseModel):
    name: str
    # Dùng Decimal thay cho float để giữ độ chính xác tuyệt đối cho tiền tệ/thuế
    amount: Decimal
    category: str
    date: datetime
    tags: Optional[List[str]] = Field(default_factory=list)
    
    note: Optional[str] = None
    recurring_interval: Optional[str] = ""

    # Chặn số tiền bằng 0 hoặc quá lớn
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, value: Decimal):
        if value == Decimal('0'):
            raise ValueError("Số tiền giao dịch không được bằng 0.")
        # ĐÃ SỬA: Nâng hạn mức lên 1,000 tỷ VNĐ để hỗ trợ ghi chép mua nhà/đất/xe
        if value > Decimal('1000000000000') or value < Decimal('-1000000000000'):  
            raise ValueError("Số tiền giao dịch quá lớn (vượt quá 1,000 tỷ VNĐ), hệ thống từ chối ghi nhận!")
        return value

    # Chặn tên giao dịch nhập cho có (VD: "A", "B")
    @field_validator('name')
    @classmethod
    def validate_name(cls, value):
        if len(value.strip()) < 2:
            raise ValueError("Tên giao dịch không hợp lệ (phải có ít nhất 2 ký tự).")
        return value

    # Chặn chọn nhầm năm quá xa trong tương lai
    @field_validator('date')
    @classmethod
    def validate_date(cls, value):
        if value.year > 2050:
            raise ValueError("Năm giao dịch vô lý (Không được vượt quá năm 2050).")
        return value

class TransactionCreate(TransactionBase):
    jar_id: Optional[int] = None
    pass


class TransactionResponse(TransactionBase):
    id: str
    model_config = ConfigDict(from_attributes=True)

# --- SCHEMAS CHO GIAO DỊCH ĐỊNH KỲ ---
class RecurringTransactionBase(BaseModel):
    name: str
    # Dùng Decimal cho tính toán tài chính
    amount: Decimal
    category: str
    tags: Optional[List[str]] = Field(default_factory=list) 
    interval: str
    startDate: datetime
    occurrences: int

    # Áp dụng các chốt chặn tương tự cho giao dịch định kỳ
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, value: Decimal):
        if value == Decimal('0'):
            raise ValueError("Số tiền giao dịch không được bằng 0.")
        if value > Decimal('1000000000000') or value < Decimal('-1000000000000'):  
            raise ValueError("Số tiền giao dịch quá lớn (vượt quá 1,000 tỷ VNĐ).")
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
    model_config = ConfigDict(from_attributes=True) 

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
    model_config = ConfigDict(from_attributes=True) 

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