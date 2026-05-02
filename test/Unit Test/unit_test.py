import pytest
from pydantic import ValidationError
from auth import get_password_hash, verify_password
from schemas import TransactionCreate

# UT_01 & UT_02: Test Mã hóa và Kiểm tra mật khẩu
def test_password_hashing_and_verification():
    password = "123456"
    # UT_01: Mã hóa
    hashed_password = get_password_hash(password)
    assert hashed_password != password
    
    # UT_02: So khớp
    assert verify_password(password, hashed_password) is True
    assert verify_password("wrong_pass", hashed_password) is False

# UT_03: Test Validation Số tiền (Bằng 0)
def test_transaction_amount_zero():
    with pytest.raises(ValidationError) as exc_info:
        # Khởi tạo schema với amount = 0
        TransactionCreate(amount=0, category_id=1, note="Test", date="2023-10-01")
    assert "Số tiền giao dịch không được bằng 0" in str(exc_info.value)

# UT_04: Test Giới hạn số tiền cực đại
def test_transaction_amount_too_large():
    with pytest.raises(ValidationError) as exc_info:
        # 2 nghìn tỷ
        TransactionCreate(amount=2000000000000, category_id=1, note="Test", date="2023-10-01")
    assert "Số tiền giao dịch quá lớn" in str(exc_info.value)

# UT_05: Test Logic chia tiền vào hũ (Giả lập logic)
def test_distribute_to_jars():
    pass 

# UT_06: Test xử lý danh mục AI
def test_get_flat_categories():
    user_config = {
        "expenseCategories": ["Ăn"], 
        "incomeCategories": ["Lương"]
    }