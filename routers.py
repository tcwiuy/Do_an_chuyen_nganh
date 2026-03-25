from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List # Thêm thư viện này cho Python 3.8
import uuid
import models, schemas
from database import get_db

router = APIRouter(prefix="/api/expenses", tags=["Expenses"])

# Đổi list[...] thành List[...] (chữ L viết hoa)
@router.get("/", response_model=List[schemas.TransactionResponse])
def get_transactions(db: Session = Depends(get_db)):
    # Tạm thời lấy tất cả. Sau này có chức năng Login sẽ filter theo user_id
    transactions = db.query(models.Transaction).all()
    return transactions

# 2. API Thêm giao dịch mới
@router.post("/", response_model=schemas.TransactionResponse)
def create_transaction(transaction: schemas.TransactionCreate, db: Session = Depends(get_db)):
    new_id = str(uuid.uuid4())
    
    db_transaction = models.Transaction(
        id=new_id,
        name=transaction.name,
        amount=transaction.amount,
        category=transaction.category,
        date=transaction.date,
        tags=transaction.tags,
        user_id=1 # Tạm gán user_id = 1 để test
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

# 3. API Xóa giao dịch
@router.delete("/{transaction_id}")
def delete_transaction(transaction_id: str, db: Session = Depends(get_db)):
    db_txn = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
    if not db_txn:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")
    
    db.delete(db_txn)
    db.commit()
    return {"message": "Đã xóa thành công"}

# API Cập nhật giao dịch
@router.put("/{transaction_id}", response_model=schemas.TransactionResponse)
def update_transaction(transaction_id: str, transaction_update: schemas.TransactionCreate, db: Session = Depends(get_db)):
    db_txn = db.query(models.Transaction).filter(models.Transaction.id == transaction_id).first()
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

# ---------------------------------------------------------
# ROUTER CHO GIAO DỊCH ĐỊNH KỲ (RECURRING EXPENSES)
# ---------------------------------------------------------
recurring_router = APIRouter(prefix="/api/recurring-expenses", tags=["Recurring Expenses"])

# 1. Lấy danh sách giao dịch định kỳ
@recurring_router.get("", response_model=List[schemas.RecurringTransactionResponse])
@recurring_router.get("/", response_model=List[schemas.RecurringTransactionResponse])
def get_recurring_transactions(db: Session = Depends(get_db)):
    return db.query(models.RecurringTransaction).all()

# 2. Thêm giao dịch định kỳ mới
@recurring_router.post("/", response_model=schemas.RecurringTransactionResponse)
def create_recurring_transaction(transaction: schemas.RecurringTransactionCreate, db: Session = Depends(get_db)):
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
        user_id=1 # Tạm gán user_id = 1
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction

# 3. Xóa giao dịch định kỳ
@recurring_router.delete("/delete")
def delete_recurring_transaction(id: str, removeAll: str, db: Session = Depends(get_db)):
    db_txn = db.query(models.RecurringTransaction).filter(models.RecurringTransaction.id == id).first()
    if not db_txn:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch định kỳ")
    
    db.delete(db_txn)
    db.commit()
    return {"message": "Đã xóa thành công"}

# 4. Sửa giao dịch định kỳ
@recurring_router.put("/edit", response_model=schemas.RecurringTransactionResponse)
def update_recurring_transaction(id: str, updateAll: str, transaction: schemas.RecurringTransactionCreate, db: Session = Depends(get_db)):
    db_txn = db.query(models.RecurringTransaction).filter(models.RecurringTransaction.id == id).first()
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