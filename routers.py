from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import uuid
from fastapi.security import OAuth2PasswordRequestForm
import requests
import os
from datetime import datetime
import json
from pydantic import BaseModel

import models, schemas, auth
from database import get_db


# ---------------------------------------------------------
# ROUTER CHO GIAO DỊCH THÔNG THƯỜNG (EXPENSES)
# ---------------------------------------------------------
router = APIRouter(prefix="/api/expenses", tags=["Expenses"])

@router.get("/", response_model=List[schemas.TransactionResponse])
def get_transactions(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    # CHỈ LẤY giao dịch của user đang đăng nhập
    return db.query(models.Transaction).filter(models.Transaction.user_id == current_user.id).all()

@router.post("/", response_model=schemas.TransactionResponse)
def create_transaction(transaction: schemas.TransactionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    new_id = str(uuid.uuid4())
    db_transaction = models.Transaction(
        id=new_id,
        name=transaction.name,
        amount=transaction.amount,
        category=transaction.category,
        date=transaction.date,
        tags=transaction.tags,
        user_id=current_user.id # LƯU VÀO ID THẬT
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@router.put("/{transaction_id}", response_model=schemas.TransactionResponse)
def update_transaction(transaction_id: str, transaction_update: schemas.TransactionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    # Đảm bảo giao dịch thuộc về user hiện tại mới cho phép sửa
    db_txn = db.query(models.Transaction).filter(models.Transaction.id == transaction_id, models.Transaction.user_id == current_user.id).first()
    if not db_txn:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")
    
    db_txn.name = transaction_update.name
    db_txn.amount = transaction_update.amount
    db_txn.category = transaction_update.category
    db_txn.date = transaction_update.date
    db_txn.tags = transaction_update.tags
    
    db.commit()
    db.refresh(db_txn)
    return db_txn

@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: str, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    # Đảm bảo giao dịch thuộc về user hiện tại mới cho phép xóa
    db_txn = db.query(models.Transaction).filter(models.Transaction.id == transaction_id, models.Transaction.user_id == current_user.id).first()
    if not db_txn:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")
    
    db.delete(db_txn)
    db.commit()
    return {"message": "Đã xóa thành công"}

# ---------------------------------------------------------
# ROUTER CHO GIAO DỊCH ĐỊNH KỲ (RECURRING EXPENSES)
# ---------------------------------------------------------
recurring_router = APIRouter(prefix="/api/recurring-expenses", tags=["Recurring Expenses"])

@recurring_router.get("", response_model=List[schemas.RecurringTransactionResponse])
@recurring_router.get("/", response_model=List[schemas.RecurringTransactionResponse])
def get_recurring_transactions(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    return db.query(models.RecurringTransaction).filter(models.RecurringTransaction.user_id == current_user.id).all()

@recurring_router.post("/", response_model=schemas.RecurringTransactionResponse)
def create_recurring_transaction(transaction: schemas.RecurringTransactionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    new_id = str(uuid.uuid4())
    db_transaction = models.RecurringTransaction(
        id=new_id,
        name=transaction.name,
        amount=transaction.amount,
        category=transaction.category,
        tags=transaction.tags,
        interval=transaction.interval,
        startDate=transaction.startDate,
        occurrences=transaction.occurrences,
        user_id=current_user.id # LƯU VÀO ID THẬT
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

@recurring_router.delete("/delete")
def delete_recurring_transaction(id: str, removeAll: str, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_txn = db.query(models.RecurringTransaction).filter(models.RecurringTransaction.id == id, models.RecurringTransaction.user_id == current_user.id).first()
    if not db_txn:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch định kỳ")
    
    db.delete(db_txn)
    db.commit()
    return {"message": "Đã xóa thành công"}

@recurring_router.put("/edit", response_model=schemas.RecurringTransactionResponse)
def update_recurring_transaction(id: str, updateAll: str, transaction: schemas.RecurringTransactionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    db_txn = db.query(models.RecurringTransaction).filter(models.RecurringTransaction.id == id, models.RecurringTransaction.user_id == current_user.id).first()
    if not db_txn:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch định kỳ")
    
    db_txn.name = transaction.name
    db_txn.amount = transaction.amount
    db_txn.category = transaction.category
    db_txn.tags = transaction.tags
    db_txn.interval = transaction.interval
    db_txn.startDate = transaction.startDate
    db_txn.occurrences = transaction.occurrences
    
    db.commit()
    db.refresh(db_txn)
    return db_txn

# ---------------------------------------------------------
# ROUTER CHO XÁC THỰC NGƯỜI DÙNG (AUTH)
# ---------------------------------------------------------
auth_router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@auth_router.post("/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")
    
    hashed_password = auth.get_password_hash(user.password)
    new_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@auth_router.post("/login")
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không đúng")
    
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# ---------------------------------------------------------
# ROUTER CHO TRÍ TUỆ NHÂN TẠO (AI INTEGRATION)
# ---------------------------------------------------------
ai_router = APIRouter(prefix="/api/ai", tags=["AI Integration"])

class AIRequest(BaseModel):
    text: str

@ai_router.post("/parse-expense")
def parse_expense_from_text(req: AIRequest, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Chưa cấu hình GEMINI_API_KEY trong file .env")

    today_str = datetime.now().strftime("%Y-%m-%d")
    
    prompt = f"""
    Hôm nay là ngày {today_str}.
    Tôi có một câu mô tả chi tiêu tài chính: "{req.text}"
    Hãy trích xuất thông tin và trả về DUY NHẤT một chuỗi JSON hợp lệ, không có thêm bất kỳ văn bản, định dạng markdown hay dấu backtick (```) nào thừa.
    Định dạng JSON yêu cầu:
    {{
        "name": "Tên món đồ/dịch vụ thật ngắn gọn",
        "amount": Số tiền (Luôn là số ÂM nếu là chi tiêu, ví dụ -50000. Nếu thu vào thì số DƯƠNG),
        "category": "Chọn 1 trong các từ sau cho phù hợp nhất: Food, Transport, Shopping, Bills, Entertainment",
        "date": "YYYY-MM-DD"
    }}
    """
    
    # Gọi thẳng vào máy chủ của Google bằng HTTP Post
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status() # Bắt lỗi nếu Google từ chối
        
        # Bóc tách kết quả từ cấu trúc JSON trả về của Google
        result_data = response.json()
        ai_text = result_data["candidates"][0]["content"]["parts"][0]["text"]
        
        # Làm sạch chuỗi
        clean_text = ai_text.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean_text)
        
        # THÊM DÒNG NÀY: Ép kiểu chuỗi chữ thành kiểu Ngày tháng (Date Object)
        parsed_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
        
        # Lưu vào cơ sở dữ liệu
        new_id = str(uuid.uuid4())
        db_transaction = models.Transaction(
            id=new_id,
            name=data["name"],
            amount=data["amount"],
            category=data["category"],
            date=parsed_date, # ĐÃ SỬA: Truyền đối tượng thời gian vào đây
            tags=["AI Assistant"],
            user_id=current_user.id
        )
        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        
        return {"message": "AI đã phân tích và lưu thành công!", "transaction": db_transaction}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi AI: {str(e)}")