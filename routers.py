from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import uuid
from fastapi.security import OAuth2PasswordRequestForm
import requests
import os
import time
from datetime import datetime
import json
import base64
from pydantic import BaseModel
from dotenv import load_dotenv
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from fastapi import APIRouter, HTTPException, Depends, Header
import re
from decimal import Decimal
load_dotenv()
import random
import models, schemas, auth
from database import get_db
from google import genai
from google.genai import types
from PIL import Image
import io
import base64
import threading
import csv
import io
import uuid
from datetime import datetime
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Union
import fitz
import pandas as pd
from sqlalchemy import func

_ai_cache = {}
_ai_cache_lock = threading.Lock()


# 💡 HÀM HELPER MỚI: TỰ ĐỘNG ÉP KIỂU DANH MỤC CŨ (LIST) VÀ MỚI (DICT) CHO AI HIỂU
def get_flat_categories(user_config):
    if user_config and user_config.categories:
        cats = user_config.categories
        if isinstance(cats, dict):
            # Cấu trúc mới: Trả về gộp cả mảng Thu và Chi
            return cats.get("expenseCategories", []) + cats.get("incomeCategories", [])
        elif isinstance(cats, list):
            # Cấu trúc cũ tương thích ngược
            return cats
    return ["Ăn uống", "Đi lại", "Mua sắm", "Hóa đơn", "Giải trí", "Thu nhập", "Lương", "Khác"]


# 1. Hàm tự động chia tiền vào 6 hũ khi có THU NHẬP (Số Dương)
def distribute_to_jars(db: Session, user_id: int, income_amount: float):
    user_jars = db.query(models.Jar).filter(models.Jar.user_id == user_id).order_by(models.Jar.id).all()
    if not user_jars:
        return

    for jar in user_jars:
        # Nếu jar.percent = 5, nó sẽ trích 5% thu nhập bỏ vào hũ này
        if jar.percent > 0:
            allocated_money = Decimal(str(income_amount)) * (jar.percent / Decimal('100'))
            jar.balance += allocated_money
    db.commit()


# 2. Hàm tự động trừ Ngân sách khi có CHI TIÊU (Số Âm)

def update_budget_spent(db: Session, user_id: int, category: str, spent_amount: float):
    # ĐÃ VÔ HIỆU HÓA: Không cần cộng/trừ thủ công nữa vì hệ thống đã tính toán động (Dynamic Calculation)
    pass


# 🌟 HÀM TỰ ĐỘNG XOAY VÒNG API KEY
def get_random_api_key():
    keys_str = os.getenv("GEMINI_API_KEY", "")
    # Tách các key bằng dấu phẩy và xóa khoảng trắng
    keys = [k.strip() for k in keys_str.split(",") if k.strip()]
    if not keys:
        return None
    return random.choice(keys)


def _cache_get(key):
    with _ai_cache_lock:
        item = _ai_cache.get(key)
        if not item:
            return None
        expires_at, value = item
        if time.time() > expires_at:
            del _ai_cache[key]
            return None
        return value


def _cache_set(key, value, ttl_seconds=1800):
    with _ai_cache_lock:
        _ai_cache[key] = (time.time() + ttl_seconds, value)


def call_gemini_with_backoff(url, payload, headers=None, timeout=30, retries=3):
    last_error = None
    headers = headers or {"Content-Type": "application/json"}
    for attempt in range(retries):
        try:
            response = requests.post(
                url, json=payload, headers=headers, timeout=timeout
            )

            # Handle transient rate-limit / overload with backoff
            if response.status_code == 429 or response.status_code == 503:
                # honor Retry-After if provided
                ra = response.headers.get("Retry-After")
                try:
                    sleep_for = (
                        float(ra) if ra is not None else (2**attempt) + random.random()
                    )
                except Exception:
                    sleep_for = (2**attempt) + random.random()
                if response.status_code == 429:
                    last_error = "Đã vượt giới hạn gọi AI tạm thời (quota/rate limit). Vui lòng thử lại sau ít phút."
                else:
                    last_error = (
                        "Máy chủ Gemini đang quá tải. Vui lòng thử lại sau 1 phút!"
                    )
                time.sleep(min(sleep_for, 30))
                continue

            if response.status_code >= 400:
                # Non-transient error: raise with existing handler
                _handle_gemini_http_status(response)

            return response

        except requests.exceptions.Timeout:
            last_error = "Gemini API timeout. Vui lòng thử lại."
            time.sleep((2**attempt) + random.random())
        except requests.exceptions.RequestException:
            last_error = "Không thể kết nối Gemini lúc này. Vui lòng thử lại sau."
            time.sleep((2**attempt) + random.random())

    # after retries
    raise HTTPException(
        status_code=502, detail=last_error or "Không thể liên hệ Gemini lúc này."
    )


def _handle_gemini_http_status(response):
    if response.status_code >= 400:
        # 1. Bắt Google khai ra toàn bộ thông tin
        error_msg = response.text

        # 2. In ra Terminal của VS Code để bạn đọc được
        print("\n" + "=" * 40)
        print("🚨 GOOGLE API ERROR 🚨")
        print(f"URL ĐANG GỌI: {response.url}")
        print(f"MÃ LỖI HTTP: {response.status_code}")
        print(f"CHI TIẾT: {error_msg}")
        print("=" * 40 + "\n")

        # 3. Trả lỗi về cho Frontend
        if response.status_code == 429:
            raise HTTPException(
                status_code=429, detail="Đã vượt giới hạn gọi AI. Vui lòng thử lại sau."
            )
        elif response.status_code == 503:
            raise HTTPException(status_code=503, detail=f"Lỗi 503: {error_msg}")
        else:
            raise HTTPException(
                status_code=502,
                detail=f"Lỗi từ Google ({response.status_code}): {error_msg}",
            )


# ---------------------------------------------------------
# ROUTER CHO GIAO DỊCH THÔNG THƯỜNG (EXPENSES)
# ---------------------------------------------------------
router = APIRouter(prefix="/api/expenses", tags=["Expenses"])
# client = genai.Client()


# ==========================================
# 1. API XUẤT DỮ LIỆU RA FILE CSV
# ==========================================
@router.get("/export/csv")
def export_csv(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == current_user.id)
        .order_by(models.Transaction.date.desc())
        .all()
    )

    output = io.StringIO()

    # THÊM ĐÚNG DÒNG NÀY ĐỂ FIX LỖI FONT TIẾNG VIỆT TRÊN EXCEL
    output.write("\ufeff")

    writer = csv.writer(output)
    writer.writerow(["Date", "Name", "Category", "Amount", "Tags"])

    for t in transactions:
        tags_str = ",".join(t.tags) if t.tags else ""
        date_str = t.date.strftime("%Y-%m-%d") if t.date else ""
        writer.writerow([date_str, t.name, t.category, t.amount, tags_str])

    output.seek(0)

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ExpenseOwl_Data.csv"},
    )


# ==========================================
# 2. API NHẬP DỮ LIỆU TỪ FILE CSV
# ==========================================
@router.post("/import/csv")
async def import_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not file.filename.endswith(".csv"):
        return {"error": "Vui lòng tải lên file định dạng .csv"}

    content = await file.read()
    decoded_content = content.decode("utf-8-sig").splitlines()
    reader = csv.DictReader(decoded_content)

    total_processed = 0
    imported = 0
    skipped = 0
    new_categories_set = set()

    user_config = (
        db.query(models.UserConfig)
        .filter(models.UserConfig.user_id == current_user.id)
        .first()
    )
    existing_categories = (
        set(user_config.categories)
        if user_config and user_config.categories
        else set(["Ăn uống", "Đi lại", "Mua sắm", "Hóa đơn", "Giải trí"])
    )

    for row in reader:
        total_processed += 1
        try:
            date_obj = datetime.strptime(row.get("Date", "").strip(), "%Y-%m-%d")
            name = row.get("Name", "-").strip()
            category = row.get("Category", "Khác").strip()
            amount = float(row.get("Amount", 0))
            raw_tags = row.get("Tags", "")
            tags = [t.strip() for t in raw_tags.split(",")] if raw_tags else []

            new_tx = models.Transaction(
                id=str(uuid.uuid4()),
                name=name,
                amount=amount,
                category=category,
                date=date_obj,
                tags=tags,
                user_id=current_user.id,
            )
            db.add(new_tx)

            if category not in existing_categories:
                new_categories_set.add(category)
                existing_categories.add(category)

            imported += 1
        except Exception as e:
            skipped += 1

    if new_categories_set and user_config:
        user_config.categories = list(existing_categories)

    db.commit()

    return {
        "total_processed": total_processed,
        "imported": imported,
        "skipped": skipped,
        "new_categories": list(new_categories_set),
    }


@router.get("/", response_model=List[schemas.TransactionResponse])
@router.get("/", response_model=List[schemas.TransactionResponse])
def get_transactions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    
    return (
        db.query(models.Transaction)
        .filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.amount != 0 
        )
        .all()
    )


@router.post("/", response_model=schemas.TransactionResponse)
def create_transaction(
    transaction: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    new_id = str(uuid.uuid4())
    db_transaction = models.Transaction(
        id=new_id,
        name=transaction.name,
        amount=transaction.amount,
        category=transaction.category,
        date=transaction.date,
        tags=transaction.tags if transaction.tags else ["Manual"],
        # --- THÊM 2 DÒNG NÀY ---
        note=transaction.note,
        recurring_interval=transaction.recurring_interval,
        # -----------------------
        user_id=current_user.id,
    )
    db.add(db_transaction)
    if transaction.amount > 0:
        # Nếu là Thu Nhập -> Chia tiền vào 6 Hũ
        distribute_to_jars(db, current_user.id, transaction.amount)
    elif transaction.amount < 0:
        if transaction.jar_id:
            jar = db.query(models.Jar).filter(models.Jar.id == transaction.jar_id, models.Jar.user_id == current_user.id).first()
            if jar: 
                # Chặn ngay nếu tiền trong Hũ ít hơn tiền định rút
                if jar.balance < abs(transaction.amount):
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Quỹ '{jar.name}' không đủ tiền! (Hiện chỉ còn {jar.balance:,.0f})"
                    )
                
                jar.balance -= Decimal(str(abs(transaction.amount)))
                db.add(jar)

        update_budget_spent(
            db, current_user.id, transaction.category, abs(transaction.amount)
        )
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


@router.put("/{transaction_id}", response_model=schemas.TransactionResponse)
def update_transaction(
    transaction_id: str,
    transaction_update: schemas.TransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_txn = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.id == transaction_id,
            models.Transaction.user_id == current_user.id,
        )
        .first()
    )
    if not db_txn:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")

    db_txn.name = transaction_update.name
    db_txn.amount = transaction_update.amount
    db_txn.category = transaction_update.category
    db_txn.date = transaction_update.date
    db_txn.tags = transaction_update.tags

    # --- THÊM 2 DÒNG NÀY ---
    db_txn.note = transaction_update.note
    db_txn.recurring_interval = transaction_update.recurring_interval
    # -----------------------

    db.commit()
    db.refresh(db_txn)
    return db_txn


@router.delete("/{transaction_id}")
def delete_transaction(
    transaction_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # Đảm bảo giao dịch thuộc về user hiện tại mới cho phép xóa
    db_txn = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.id == transaction_id,
            models.Transaction.user_id == current_user.id,
        )
        .first()
    )
    if not db_txn:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch")

    db.delete(db_txn)
    db.commit()
    return {"message": "Đã xóa thành công"}


# ---------------------------------------------------------
# ROUTER CHO GIAO DỊCH ĐỊNH KỲ (RECURRING EXPENSES)
# ---------------------------------------------------------
recurring_router = APIRouter(
    prefix="/api/recurring-expenses", tags=["Recurring Expenses"]
)


@recurring_router.get("", response_model=List[schemas.RecurringTransactionResponse])
@recurring_router.get("/", response_model=List[schemas.RecurringTransactionResponse])
def get_recurring_transactions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return (
        db.query(models.RecurringTransaction)
        .filter(models.RecurringTransaction.user_id == current_user.id)
        .all()
    )


@recurring_router.post("/", response_model=schemas.RecurringTransactionResponse)
def create_recurring_transaction(
    transaction: schemas.RecurringTransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
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
        user_id=current_user.id,  # LƯU VÀO ID THẬT
    )
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


@recurring_router.delete("/delete")
def delete_recurring_transaction(
    id: str,
    removeAll: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_txn = (
        db.query(models.RecurringTransaction)
        .filter(
            models.RecurringTransaction.id == id,
            models.RecurringTransaction.user_id == current_user.id,
        )
        .first()
    )
    if not db_txn:
        raise HTTPException(status_code=404, detail="Không tìm thấy giao dịch định kỳ")

    db.delete(db_txn)
    db.commit()
    return {"message": "Đã xóa thành công"}


@recurring_router.put("/edit", response_model=schemas.RecurringTransactionResponse)
def update_recurring_transaction(
    id: str,
    updateAll: str,
    transaction: schemas.RecurringTransactionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    db_txn = (
        db.query(models.RecurringTransaction)
        .filter(
            models.RecurringTransaction.id == id,
            models.RecurringTransaction.user_id == current_user.id,
        )
        .first()
    )
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


@auth_router.post("/register")
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # 1. Kiểm tra trùng Tên đăng nhập
    existing_user = (
        db.query(models.User).filter(models.User.username == user.username).first()
    )
    if existing_user:
        raise HTTPException(status_code=400, detail="Tên đăng nhập đã tồn tại")

    # 2. Kiểm tra trùng Email
    existing_email = (
        db.query(models.User).filter(models.User.email == user.email).first()
    )
    if existing_email:
        raise HTTPException(status_code=400, detail="Email này đã được sử dụng")

    # 3. Mã hóa mật khẩu
    hashed_password = auth.get_password_hash(user.password)

    # 4. Lưu toàn bộ thông tin vào DB
    new_user = models.User(
        username=user.username,
        hashed_password=hashed_password,
        full_name=user.full_name,
        gender=user.gender,
        dob=user.dob,
        email=user.email,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "Đăng ký thành công"}


login_attempts = {}
MAX_ATTEMPTS = 5
LOCK_TIME_MINUTES = 1

@auth_router.post("/login")
def login_user(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    username = form_data.username
    now = datetime.now()

    # --- BƯỚC 1: KIỂM TRA TRẠNG THÁI KHÓA ---
    if username in login_attempts:
        attempt_info = login_attempts[username]
        # Nếu đang có lịch hẹn mở khóa
        if attempt_info.get("lock_until"):
            if now < attempt_info["lock_until"]:
                # Tính số phút còn lại
                remaining_time = int((attempt_info["lock_until"] - now).total_seconds() / 60)
                if remaining_time < 1: 
                    remaining_time = 1  # Báo tối thiểu là 1 phút để UX mượt hơn
                    
                raise HTTPException(
                    status_code=403, 
                    detail=f"Tài khoản bị tạm khóa. Vui lòng thử lại sau {remaining_time} phút."
                )
            else:
                # Đã qua thời gian khóa -> Reset lại bộ đếm về 0
                login_attempts[username] = {"count": 0, "lock_until": None}

    # --- BƯỚC 2: KIỂM TRA MẬT KHẨU NHƯ BÌNH THƯỜNG ---
    user = (
        db.query(models.User).filter(models.User.username == form_data.username).first()
    )
    
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        # Khởi tạo bộ đếm cho user này nếu là lần sai đầu tiên
        if username not in login_attempts:
            login_attempts[username] = {"count": 0, "lock_until": None}
        
        login_attempts[username]["count"] += 1
        
        # Nếu đã chạm ngưỡng 5 lần -> Kích hoạt khóa
        if login_attempts[username]["count"] >= MAX_ATTEMPTS:
            login_attempts[username]["lock_until"] = now + timedelta(minutes=LOCK_TIME_MINUTES)
            raise HTTPException(
                status_code=403,
                detail=f"Bạn đã nhập sai {MAX_ATTEMPTS} lần. Tài khoản bị khóa tạm thời {LOCK_TIME_MINUTES} phút."
            )
        
        # Nếu chưa tới 5 lần -> Báo lỗi và đếm ngược số lần còn lại
        remaining_attempts = MAX_ATTEMPTS - login_attempts[username]["count"]
        raise HTTPException(
            status_code=401, 
            detail=f"Tên đăng nhập hoặc mật khẩu không đúng. Bạn còn {remaining_attempts} lần thử."
        )

    # --- BƯỚC 3: ĐĂNG NHẬP THÀNH CÔNG ---
    # Xóa lịch sử nhập sai của user này để không bị cộng dồn vào lần sau
    if username in login_attempts:
        del login_attempts[username]

    # Cấp phát Token
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.put("/change-password")
def change_password(
    passwords: schemas.UserUpdatePassword,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # 1. Kiểm tra xem mật khẩu cũ nhập vào có đúng không
    if not auth.verify_password(passwords.old_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400, detail="Mật khẩu hiện tại không chính xác!"
        )

    # 2. Kiểm tra mật khẩu mới không được trùng mật khẩu cũ
    if auth.verify_password(passwords.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=400, detail="Mật khẩu mới không được giống mật khẩu cũ!"
        )

    # 3. Băm mật khẩu mới và lưu vào cơ sở dữ liệu
    current_user.hashed_password = auth.get_password_hash(passwords.new_password)
    db.commit()

    return {"message": "Đổi mật khẩu thành công!"}


class EmailSyncUpdate(BaseModel):
    is_enabled: bool
# ---------------------------------------------------------
# ROUTER CHO TRÍ TUỆ NHÂN TẠO (AI INTEGRATION)
# ---------------------------------------------------------
ai_router = APIRouter(prefix="/api/ai", tags=["AI Integration"])


# Schema cho API Nhập liệu
class AIRequest(BaseModel):
    text: str
    currency: str = "vnd"
    rate: float = 1.0


# Schema mới cho API Chatbot
class ChatRequest(BaseModel):
    message: str
    history: list = []
    currency: str = "vnd"
    rate: float = 1.0


class SpendingSuggestionRequest(BaseModel):
    month_window: int = 3
    goal_name: str | None = None
    goal_amount: float | None = None
    goal_months: int | None = None
    currency: str = "vnd"
    symbol: str = "₫"
    rate: float = 1.0


# 1. API NHẬP LIỆU BẰNG NGÔN NGỮ TỰ NHIÊN
@ai_router.post("/parse-expense")
def parse_expense_from_text(
    req: AIRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    api_key = get_random_api_key()
    if not api_key:
        raise HTTPException(
            status_code=500, detail="Chưa cấu hình GEMINI_API_KEY trong file .env"
        )

    # Lấy danh sách danh mục (Categories) hiện tại của người dùng từ Database
    user_config = (
        db.query(models.UserConfig)
        .filter(models.UserConfig.user_id == current_user.id)
        .first()
    )
    if user_config and user_config.categories:
        categories_str = ", ".join(user_config.categories)
    else:
        categories_str = "Ăn uống, Đi lại, Mua sắm, Hóa đơn, Giải trí, Thu nhập"

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Fix 2: Chuẩn hóa lại Prompt, dùng đúng biến req.currency và răn đe AI
    prompt = f"""
    Hôm nay là ngày {today_str}.
    Tôi có một câu mô tả dòng tiền: "{req.text}"
    Hãy trích xuất thông tin và trả về DUY NHẤT một chuỗi JSON hợp lệ.

    QUY TẮC TIỀN TỆ & TÍNH TOÁN (TỐI QUAN TRỌNG):
    - Hệ thống của người dùng hiện ĐANG CÀI ĐẶT TIỀN TỆ LÀ: {req.currency.upper()}
    - Lệnh 1: Nếu người dùng nhập một con số mà KHÔNG CÓ ĐƠN VỊ (VD: "mua bánh 15"), bạn BẮT BUỘC phải ngầm hiểu đó là 15 {req.currency.upper()}.
    - Lệnh 2: NẾU NGƯỜI DÙNG HOÀN TOÀN KHÔNG NHẬP SỐ TIỀN (VD: "tôi ăn cơm"), bạn BẮT BUỘC phải trả về "amount": 0. Tuyệt đối không được tự bịa ra số tiền.
    - Lệnh 3: TUYỆT ĐỐI KHÔNG ĐƯỢC than vãn hay hỏi lại người dùng tỷ giá. BẠN PHẢI TỰ LÀM TOÁN.
    - Lệnh 4: Dữ liệu lưu vào hệ thống ('amount') LUÔN LUÔN PHẢI LÀ VNĐ. Bạn hãy lấy con số người dùng nhập nhân với tỷ giá hiện tại là: {req.rate} (Đây là tỷ giá quy đổi từ 1 {req.currency.upper()} sang VNĐ). Tuyệt đối không được dùng con số nào khác.
    
    Định dạng JSON yêu cầu:
    {{
        "name": "Tên món đồ thật ngắn gọn",
        "amount": Số tiền (QUAN TRỌNG: KHÔNG ĐƯỢC BẰNG 0. Chi tiêu là số ÂM, Thu nhập là số DƯƠNG),
        "category": "Chọn 1 từ trong: {categories_str}",
        "date": "YYYY-MM-DD"
    }}
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = call_gemini_with_backoff(
            url,
            payload,
            headers={"Content-Type": "application/json"},
            timeout=90,
            retries=3,
        )
        _handle_gemini_http_status(response)

        result_data = response.json()
        ai_text = result_data["candidates"][0]["content"]["parts"][0]["text"]

        clean_text = ai_text.strip().replace("```json", "").replace("```", "")
        data = json.loads(clean_text)

        # Fix 3: KIỂM TRA SỐ TIỀN TẠI CHỖ (Ngăn số 0)
        try:
            amount = float(data.get("amount", 0))
        except (ValueError, TypeError):
            amount = 0

        if amount == 0:
            raise HTTPException(
                status_code=400,
                detail="Trợ lý AI không nhận diện được số tiền! Vui lòng nhập rõ con số nhé (VD: Ăn cơm 10).",
            )

        # Xử lý ngày
        try:
            parsed_date = datetime.strptime(
                data.get("date", today_str), "%Y-%m-%d"
            ).date()
        except ValueError:
            parsed_date = datetime.now().date()

        # Fix 4: CẤM LƯU DATABASE Ở ĐÂY, CHỈ TRẢ VỀ DỮ LIỆU JSON
        new_id = str(uuid.uuid4())
        return {
            "message": "AI đã phân tích thành công!",
            "transaction": {
                "id": new_id,
                "name": data.get("name", "Giao dịch AI"),
                "amount": amount,
                "category": data.get("category", "Khác"),
                "date": parsed_date.isoformat(),
                "tags": ["AI Assistant"],
            },
        }

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400, detail="AI trả về dữ liệu không hợp lệ. Vui lòng thử lại."
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Lỗi AI khi phân tích giao dịch.")


# ---------------------------------------------------------
# 2. API CHATBOT TRUY VẤN DỮ LIỆU CÓ TRÍ NHỚ (RAG + MEMORY + AUTO SAVE)
# ---------------------------------------------------------
@ai_router.post("/chat")
def chat_with_data(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    api_key = get_random_api_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="Chưa cấu hình GEMINI_API_KEY")

    # BƯỚC 1: Lấy Cấu hình, Danh mục và HỒ SƠ TÍNH CÁCH
    user_config = db.query(models.UserConfig).filter(models.UserConfig.user_id == current_user.id).first()
    cats = user_config.categories if user_config and user_config.categories else None
    allowed_categories = [] 
    
    if isinstance(cats, dict):
        exp_cats = cats.get("expenseCategories", ["Ăn uống", "Đi lại", "Mua sắm", "Hóa đơn", "Giải trí"])
        inc_cats = cats.get("incomeCategories", ["Lương", "Thưởng", "Đầu tư", "Khác"])
        categories_str = f"Chi tiêu gồm ({', '.join(exp_cats)}) | Thu nhập gồm ({', '.join(inc_cats)})"
        allowed_categories = exp_cats + inc_cats
    elif isinstance(cats, list):
        categories_str = ", ".join(cats)
        allowed_categories = cats
    else:
        categories_str = "Chi tiêu: Ăn uống, Đi lại, Mua sắm | Thu nhập: Lương, Thưởng"
        allowed_categories = ["Ăn uống", "Đi lại", "Mua sắm", "Lương", "Thưởng", "Khác"]

    if "Khác" not in allowed_categories: 
        allowed_categories.append("Khác")

    current_goal = user_config.financial_goal if user_config and user_config.financial_goal else "Chưa xác định"
    current_risk = user_config.risk_tolerance if user_config and user_config.risk_tolerance else "Cân bằng"

    # BƯỚC 2: Rút trích dữ liệu (RAG)
    all_txns = db.query(models.Transaction).filter(models.Transaction.user_id == current_user.id).all()
    total_income_all = sum(t.amount for t in all_txns if t.amount > 0)
    total_expense_all = sum(abs(t.amount) for t in all_txns if t.amount < 0)
    balance_all = total_income_all - total_expense_all
    
    current_month = datetime.now().month
    current_year = datetime.now().year
    txns_this_month = [t for t in all_txns if getattr(t.date, 'month', -1) == current_month and getattr(t.date, 'year', -1) == current_year]
    total_income_month = sum(t.amount for t in txns_this_month if t.amount > 0)
    total_expense_month = sum(abs(t.amount) for t in txns_this_month if t.amount < 0)
    balance_month = total_income_month - total_expense_month

    recent_txns = sorted(all_txns, key=lambda x: x.date, reverse=True)[:5]
    text_to_search = req.message
    if req.history and len(req.history) > 0:
        text_to_search += " " + req.history[-1].get("user", "")
        
    stop_words = {"bạn", "hãy", "ghi", "rõ", "lại", "là", "tháng", "ngày", "thứ", "cho", "tôi", "nhé", "vào", "của", "đã", "sửa", "thành", "nhầm"}
    keywords = [word for word in text_to_search.split() if len(word) > 2 and word.lower() not in stop_words]
    
    related_txns = []
    if keywords:
        search_filter = models.Transaction.name.ilike(f"%{keywords[0]}%")
        for kw in keywords[1:]:
            search_filter |= models.Transaction.name.ilike(f"%{kw}%")
        
        related_txns = db.query(models.Transaction).filter(
            models.Transaction.user_id == current_user.id,
            search_filter
        ).order_by(models.Transaction.date.desc()).limit(10).all()

    all_context_txns = list({t.id: t for t in (recent_txns + related_txns)}.values())
    data_context = "GIAO DỊCH LIÊN QUAN ĐỂ SỬA (ID là quan trọng nhất):\n"
    if not all_context_txns:
        data_context += "Trống.\n"
    else:
        for t in sorted(all_context_txns, key=lambda x: x.date, reverse=True):
            data_context += f"ID: {t.id} | Ngày: {t.date.strftime('%Y-%m-%d')} | Tên: {t.name} | Tiền: {t.amount} | Nhóm: {t.category}\n"

    # BƯỚC 3: Xử lý lịch sử Chat
    history_text = ""
    if req.history:
        history_text = "LỊCH SỬ CHAT:\n"
        for turn in req.history[-3:]:  
            history_text += f"User: {turn.get('user', '')}\nAI: {turn.get('ai', '')}\n"

    # BƯỚC 4: PROMPT TỐI ƯU HÓA
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_date = datetime.now().date()
    
    t_inc_all = float(total_income_all) / req.rate
    t_exp_all = float(total_expense_all) / req.rate
    t_bal_all = float(balance_all) / req.rate
    t_inc_month = float(total_income_month) / req.rate
    t_exp_month = float(total_expense_month) / req.rate
    t_bal_month = float(balance_month) / req.rate
    
    user_jars = db.query(models.Jar).filter(models.Jar.user_id == current_user.id).all()
    total_in_jars = sum(j.balance for j in user_jars)
    free_bal_all = float(balance_all - total_in_jars) / req.rate
    
    jars_context = "TRẠNG THÁI CÁC QUỸ (HŨ) HIỆN TẠI:\n"
    if not user_jars:
        jars_context += "- Chưa có hũ nào.\n"
    else:
        for j in user_jars:
            jars_context += f"- Quỹ '{j.name}': Đang có {(float(j.balance) / req.rate):,.0f} (Mục tiêu: {(float(j.goal_amount) / req.rate):,.0f})\n"

    active_budgets = db.query(models.Budget).filter(
        models.Budget.user_id == current_user.id,
        models.Budget.start_date <= today_date,
        models.Budget.end_date >= today_date
    ).all()
    
    budgets_context = "TRẠNG THÁI NGÂN SÁCH HIỆN TẠI (TRONG KỲ NÀY):\n"
    if not active_budgets:
        budgets_context += "- Chưa thiết lập ngân sách.\n"
    else:
        from sqlalchemy import func
        for b in active_budgets:
            spent = db.query(func.sum(models.Transaction.amount)).filter(
                models.Transaction.user_id == current_user.id,
                models.Transaction.category == b.category,
                models.Transaction.amount < 0,
                func.date(models.Transaction.date) >= b.start_date,
                func.date(models.Transaction.date) <= b.end_date
            ).scalar() or 0.0
            budgets_context += f"- Mục '{b.category}': Đã tiêu {(abs(float(spent)) / req.rate):,.0f} / Hạn mức {(float(b.limit_amount) / req.rate):,.0f}\n"

    prompt = f"""
    Bạn là "Cú Mèo" - Cố vấn tài chính cá nhân. Hôm nay: {today_str}.
    TIỀN TỆ: {req.currency.upper()} (Tỷ giá 1 {req.currency.upper()} = {req.rate} VNĐ).
    HỒ SƠ KHÁCH HÀNG: Mục tiêu: {current_goal} | Rủi ro: {current_risk}.
    
    🚨 CẤU TRÚC TÀI SẢN (QUAN TRỌNG NHẤT):
    - 🏦 TỔNG TÀI SẢN (Gồm tất cả tiền): {t_bal_all:,.0f}
    - 💰 SỐ DƯ KHẢ DỤNG (Tiền rảnh rỗi chưa cất vào hũ): {free_bal_all:,.0f}
    
    [THÁNG {current_month}/{current_year}] Tổng thu: {t_inc_month:,.0f} | Tổng chi: {t_exp_month:,.0f}
    
    {jars_context}
    {budgets_context}
    {data_context}
    {history_text}
    
    CÂU HỎI: "{req.message}"
    
    🚨 LUẬT THÉP CẦN TUÂN THỦ:
    1. LUẬT NẠP HŨ: Nạp hũ là LẤY TIỀN TỪ "SỐ DƯ KHẢ DỤNG" đưa vào hũ. Phải kiểm tra "SỐ DƯ KHẢ DỤNG" xem có đủ tiền nạp không.
    2. LUẬT CHI TIÊU HŨ: Khách hàng chi tiêu bình thường sẽ bị trừ ở "SỐ DƯ KHẢ DỤNG". Nếu khách nói rõ "tiêu từ hũ X", hãy đưa tên hũ X vào trường "jar_name".
    3. LUẬT CẢNH BÁO NGÂN SÁCH THEO MỨC ĐỘ: Khi ghi nhận khoản chi tiêu mới, bạn PHẢI tự nhẩm tính: Tỷ lệ % = (Đã tiêu + Khoản chi mới) / Hạn mức. Hãy phản hồi theo đúng 4 mức độ sau:
       - Mức Xanh (<75%): Khen ngợi.
       - Mức Vàng (75-89%): Nhắc nhở.
       - Mức Đỏ (90-100%): Cảnh báo sắp lố.
       - Lố ngân sách (>100%): Cảnh báo vượt giới hạn.

    QUY TẮC "ACTION":
    1. "save": Tạo mới giao dịch.
    2. "update": Sửa giao dịch.
    3. "update_profile": Đổi mục tiêu.
    4. "create_jar" / "delete_jar": Tạo / Xóa hũ.
    5. "jar_transfer": NẠP/RÚT/CHUYỂN tiền giữa các hũ.
    6. "chat": Trò chuyện bình thường.

    CẤU TRÚC JSON PHẢI TRẢ VỀ:
    {{
        "reply": "Câu trả lời của bạn",
        "action": "chat" | "save" | "update" | "update_profile" | "create_jar" | "delete_jar" | "jar_transfer",
        "transaction_id": "Mã ID" | null,
        "data": [
            {{ 
                "name": "Tên giao dịch (Tách riêng nếu người dùng nhập nhiều khoản cùng lúc)", 
                "amount": Số tiền (ÂM nếu chi, DƯƠNG nếu thu. CHỈ LẤY SỐ THEO ĐƠN VỊ {req.currency.upper()}, KHÔNG TỰ NHÂN TỶ GIÁ), 
                "category": "...", 
                "date": "YYYY-MM-DD",
                "jar_name": "Tên hũ (GHI ĐÚNG TÊN LÕI)"
            }}
        ] | null,
        "profile_update": {{ "financial_goal": "...", "risk_tolerance": "..." }} | null,
        "jar_data": {{ 
            "name": "Tên hũ", "target_name": "Tên hũ nhận", "goal_amount": Số,
            "type": "deposit" | "withdraw" | "internal" | null, "amount": Số 
        }} | null
    }}
    """

    # BƯỚC 5: Gọi Gemini
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }

    try:
        response = call_gemini_with_backoff(url, payload, timeout=30, retries=3)
        _handle_gemini_http_status(response)
        result_data = response.json()
        ai_text = result_data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi AI: {str(e)}")

    # BƯỚC 6: Xử lý KẾT QUẢ VÀ CẬP NHẬT DB NGẦM
    try:
        clean_text = ai_text.strip().replace("```json", "").replace("```", "")
        result_json = json.loads(clean_text)

        transaction_data = None
        final_action = result_json.get("action", "chat")

        # 6.1. TẠO MỚI GIAO DỊCH (HỖ TRỢ CHI TIÊU TỪ HŨ)
        if final_action == "save" and result_json.get("data"):
            raw_data = result_json["data"]
            data_list = raw_data if isinstance(raw_data, list) else [raw_data]
            saved_txns = []

            for data in data_list:
                if not isinstance(data, dict): continue 
                try: parsed_date = datetime.strptime(data.get("date", today_str), "%Y-%m-%d").date()
                except: parsed_date = datetime.now().date()
                
                # 💡 FIX LỖI TIỀN TỆ: AI trả về USD/Tiền hiển thị -> Backend nhân tỷ giá để lưu VNĐ vào DB
                new_amount_raw = float(data.get("amount", 0))
                new_amount = new_amount_raw * req.rate  
                
                # 💡 VÁ LỖI TÌM TÊN HŨ KHI CHI TIÊU
                jar_name_to_spend = str(data.get("jar_name", "")).strip().lower().replace("hũ ", "").replace("quỹ ", "").strip()
                target_jar = None
                
                if new_amount < 0 and jar_name_to_spend:
                    target_jar = db.query(models.Jar).filter(
                        models.Jar.user_id == current_user.id, 
                        models.Jar.name.ilike(f"%{jar_name_to_spend}%")
                    ).first()
                    
                    if target_jar:
                        if target_jar.balance < abs(new_amount):
                            final_action = "chat"
                            result_json["reply"] = f"Hũ '{target_jar.name}' chỉ còn {(float(target_jar.balance)/req.rate):,.0f}, không đủ tiền để chi trả khoản này đâu!"
                            return {"reply": result_json["reply"], "action": final_action, "transaction_data": None}
                    
                new_tx_id = str(uuid.uuid4())
                new_transaction = models.Transaction(
                    id=new_tx_id, name=str(data.get("name", "Giao dịch AI"))[:255],
                    amount=new_amount,
                    category=data.get("category") if data.get("category") in allowed_categories else "Khác",
                    date=parsed_date, tags=["AI Chatbot"], user_id=current_user.id,
                )
                
                if target_jar:
                    new_transaction.tags.append(str(target_jar.id))
                    
                db.add(new_transaction)

                if new_amount > 0: distribute_to_jars(db, current_user.id, new_amount)
                elif new_amount < 0: 
                    if target_jar:
                        target_jar.balance -= Decimal(str(abs(new_amount))) 
                    update_budget_spent(db, current_user.id, new_transaction.category, abs(new_amount))
                    
                db.commit()
                db.refresh(new_transaction)
                saved_txns.append({
                    "id": new_tx_id, "name": new_transaction.name, "amount": new_transaction.amount,
                    "category": new_transaction.category, "date": new_transaction.date.isoformat(), 
                    "tags": new_transaction.tags,
                })

            transaction_data = saved_txns[0] if saved_txns else None

        # 6.2. SỬA GIAO DỊCH HIỆN CÓ
        elif final_action == "update" and result_json.get("transaction_id") and result_json.get("data"):
            target_id = result_json["transaction_id"]
            raw_data = result_json["data"]
            data = raw_data[0] if isinstance(raw_data, list) and len(raw_data) > 0 else raw_data
            
            if isinstance(data, dict):
                tx_to_update = db.query(models.Transaction).filter(models.Transaction.id == target_id, models.Transaction.user_id == current_user.id).first()
                if tx_to_update:
                    old_amount = tx_to_update.amount
                    old_category = tx_to_update.category
                    
                    # 💡 FIX LỖI TIỀN TỆ KHI UPDATE
                    if "amount" in data:
                        new_amount = float(data["amount"]) * req.rate
                    else:
                        new_amount = old_amount

                    new_category = str(data.get("category", old_category)) if str(data.get("category", old_category)) in allowed_categories else "Khác"

                    if old_amount > 0: distribute_to_jars(db, current_user.id, -old_amount)
                    elif old_amount < 0: update_budget_spent(db, current_user.id, old_category, -abs(old_amount))
                    
                    if data.get("name"): tx_to_update.name = str(data.get("name"))[:255]
                    tx_to_update.category = new_category
                    tx_to_update.amount = new_amount
                    try: tx_to_update.date = datetime.strptime(data.get("date", str(tx_to_update.date)), "%Y-%m-%d").date()
                    except: pass

                    if new_amount > 0: distribute_to_jars(db, current_user.id, new_amount)
                    elif new_amount < 0: update_budget_spent(db, current_user.id, new_category, abs(new_amount))
                    db.commit()
                else: final_action = "chat" 

        # 6.3. ĐỔI HỒ SƠ TÀI CHÍNH
        elif final_action == "update_profile" and result_json.get("profile_update"):
            p_update = result_json["profile_update"]
            if user_config:
                if p_update.get("financial_goal"): user_config.financial_goal = str(p_update.get("financial_goal"))
                if p_update.get("risk_tolerance"): user_config.risk_tolerance = str(p_update.get("risk_tolerance"))
                db.commit()

        # 6.4. TẠO HŨ MỚI
        elif final_action == "create_jar" and result_json.get("jar_data"):
            j_data = result_json["jar_data"]
            jar_name = str(j_data.get("name", "Hũ mới"))[:50].strip()
            
            import re
            clean_goal_str = re.sub(r'[^\d.]', '', str(j_data.get("goal_amount", 0)))
            jar_goal = (float(clean_goal_str) if clean_goal_str else 0.0) * req.rate

            existing_jar = db.query(models.Jar).filter(
                models.Jar.user_id == current_user.id, 
                models.Jar.name.ilike(jar_name)
            ).first()

            if not existing_jar:
                new_jar = models.Jar(name=jar_name[0].upper() + jar_name[1:], percent=0, goal_amount=jar_goal, balance=0.0, color="#4ade80", icon="fa-bullseye", user_id=current_user.id)
                db.add(new_jar)
                db.commit()
            elif jar_goal > 0:
                existing_jar.goal_amount = jar_goal
                db.commit()

        # 6.5. XÓA HŨ
        elif final_action == "delete_jar" and result_json.get("jar_data"):
            # 💡 VÁ LỖI XÓA HŨ: Xóa chữ thừa và dùng ilike
            jar_name = str(result_json["jar_data"].get("name", "")).strip().lower().replace("hũ ", "").replace("quỹ ", "").strip()
            
            jar_to_delete = db.query(models.Jar).filter(
                models.Jar.user_id == current_user.id, 
                models.Jar.name.ilike(f"%{jar_name}%")
            ).first()
            
            if jar_to_delete:
                if jar_to_delete.balance > 0:
                    final_action = "chat"
                    result_json["reply"] = f"Hũ '{jar_to_delete.name}' vẫn còn tiền. Vui lòng rút hết ra Số dư khả dụng rồi mới xóa được nhé!"
                else:
                    db.delete(jar_to_delete)
                    db.commit()
            else:
                final_action = "chat"
                result_json["reply"] = f"Tôi không tìm thấy hũ nào tên là '{jar_name}' cả."

        # 6.6. NẠP / RÚT / CHUYỂN TIỀN QUỸ
        elif final_action == "jar_transfer" and result_json.get("jar_data"):
            j_data = result_json["jar_data"]
            t_type = j_data.get("type", "deposit")
            
            # 💡 VÁ LỖI TÌM TÊN HŨ KHI NẠP RÚT: Gọt bớt chữ "hũ", "quỹ" thừa thãi
            jar_name = str(j_data.get("name", "")).strip().lower().replace("hũ ", "").replace("quỹ ", "").strip()
            target_name = str(j_data.get("target_name", "")).strip().lower().replace("hũ ", "").replace("quỹ ", "").strip()
            
            import re
            clean_str = re.sub(r'[^\d.]', '', str(j_data.get("amount", 0)))
            transfer_amount = float(clean_str) * req.rate if clean_str else 0.0

            # 💡 VÁ LỖI BẰNG ILIKE: Tìm kiếm từ khóa chứa tên hũ thay vì so sánh tuyệt đối
            jar = db.query(models.Jar).filter(
                models.Jar.user_id == current_user.id, 
                models.Jar.name.ilike(f"%{jar_name}%")
            ).first()

            if not jar or transfer_amount <= 0:
                final_action = "chat"
                result_json["reply"] = "Có lỗi xảy ra, không tìm thấy hũ hoặc số tiền không hợp lệ."
            else:
                success = False
                history_name = ""
                tags = ["Quỹ", t_type]

                if t_type == "deposit":
                    if transfer_amount > float(free_bal_all * req.rate):
                        final_action = "chat"
                        result_json["reply"] = f"Số dư khả dụng của bạn không đủ tiền! Tối đa chỉ còn {free_bal_all:,.0f} {req.currency.upper()} để nạp vào hũ."
                    else:
                        jar.balance += Decimal(str(transfer_amount))
                        history_name = f"Nạp {(transfer_amount/req.rate):,.0f} {req.currency.upper()} TỪ SỐ DƯ KHẢ DỤNG vào hũ {jar.name}"
                        tags.append(str(jar.id))
                        success = True

                elif t_type == "withdraw":
                    if jar.balance < transfer_amount:
                        final_action = "chat"
                        result_json["reply"] = f"Hũ '{jar.name}' không đủ tiền để rút."
                    else:
                        jar.balance -= Decimal(str(transfer_amount))
                        history_name = f"Rút {(transfer_amount/req.rate):,.0f} {req.currency.upper()} từ hũ {jar.name} RA SỐ DƯ KHẢ DỤNG"
                        tags.append(str(jar.id))
                        success = True

                elif t_type == "internal":
                    # Tương tự cho hũ nhận tiền
                    target_jar = db.query(models.Jar).filter(
                        models.Jar.user_id == current_user.id, 
                        models.Jar.name.ilike(f"%{target_name}%")
                    ).first()
                    
                    if not target_jar:
                        final_action = "chat"
                        result_json["reply"] = f"Tôi không tìm thấy hũ nhận tiền có tên '{target_name}'."
                    elif jar.balance < transfer_amount:
                        final_action = "chat"
                        result_json["reply"] = f"Hũ '{jar.name}' không đủ tiền để chuyển."
                    else:
                        jar.balance -= Decimal(str(transfer_amount))
                        target_jar.balance += Decimal(str(transfer_amount))
                        history_name = f"Chuyển {(transfer_amount/req.rate):,.0f} {req.currency.upper()} từ hũ {jar.name} sang hũ {target_jar.name}"
                        tags.extend([str(jar.id), str(target_jar.id)])
                        success = True
                
                if success:
                    new_tx = models.Transaction(
                        id=str(uuid.uuid4()), name=history_name, amount=0.0,
                        category="Chuyển Quỹ", date=datetime.now(), tags=tags, user_id=current_user.id
                    )
                    db.add(new_tx)
                    db.commit()

        return {
            "reply": result_json.get("reply", "Cú Mèo đã ghi nhận yêu cầu của bạn!"),
            "action": final_action,
            "transaction_data": transaction_data
        }

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="AI trả về dữ liệu không hợp lệ.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý: {str(e)}")

# ---------------------------------------------------------
# 3. API PHÂN TÍCH XU HƯỚNG VÀ PHÁT HIỆN BẤT THƯỜNG
# ---------------------------------------------------------
@ai_router.get("/analyze-trends")
def analyze_trends_and_anomalies(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # SỬ DỤNG HÀM LẤY KEY RANDOM Ở ĐÂY
    api_key = get_random_api_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="Chưa cấu hình GEMINI_API_KEY")

    # 1. Lấy toàn bộ giao dịch của người dùng
    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == current_user.id)
        .all()
    )

    if not transactions:
        return {
            "reply": "Chưa có đủ dữ liệu giao dịch để phân tích. Bạn hãy ghi chép thêm nhé!"
        }

    # 2. Ráp dữ liệu thành bảng văn bản
    data_context = "DANH SÁCH GIAO DỊCH TRONG QUÁ KHỨ VÀ HIỆN TẠI:\nNgày | Tên giao dịch | Số tiền | Danh mục\n"
    data_context += "-" * 50 + "\n"
    for t in transactions:
        data_context += (
            f"{t.date.strftime('%Y-%m-%d')} | {t.name} | {t.amount} | {t.category}\n"
        )

    # 3. Viết Prompt yêu cầu phân tích
    today_str = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
    Hôm nay là ngày {today_str}.
    Bạn là "Cú Mèo", chuyên gia phân tích tài chính của ExpenseOwl.
    Dưới đây là lịch sử giao dịch (Số tiền ÂM là chi tiêu, DƯƠNG là thu nhập):
    
    {data_context}
    
    Hãy phân tích khối dữ liệu trên và xuất ra báo cáo bằng tiếng Việt, định dạng Markdown theo cấu trúc sau:
    Lưu ý quan trọng: Luôn định dạng số tiền theo chuẩn Đô la Mỹ, sử dụng dấu phẩy để phân cách hàng nghìn và đặt ký hiệu $ ở ngay phía trước số tiền (Ví dụ: $1,200.50 hoặc $50). Tuyệt đối không dùng chữ "VNĐ" hay "đơn vị tiền tệ".
    ###  Dự đoán xu hướng
    (Dự đoán tháng tới họ sẽ tiêu tốn nhiều nhất vào việc gì)
    ###  Phát hiện bất thường
    (Tìm ra khoản chi cao đột biến. Nếu mọi thứ bình thường, hãy khen ngợi)
    ###  Lời khuyên từ Cú Mèo
    (1 hành động cụ thể để tối ưu hóa dòng tiền)
    """

    # 4. Gọi API Gemini
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        response = call_gemini_with_backoff(
            url,
            payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
            retries=3,
        )
        _handle_gemini_http_status(response)
        result_data = response.json()
        ai_reply = result_data["candidates"][0]["content"]["parts"][0]["text"]
        return {"reply": ai_reply}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Lỗi AI phân tích.")


@ai_router.post("/spending-suggestions")
def get_spending_suggestions(
    req: SpendingSuggestionRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    api_key = get_random_api_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="Chưa cấu hình GEMINI_API_KEY")

    month_window = max(1, min(req.month_window or 3, 12))
    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == current_user.id)
        .all()
    )

    if not transactions:
        return {
            "feasibility": "low",
            "monthly_savings_needed": 0,
            "overall_strategy": "Bạn chưa có dữ liệu giao dịch nào. Hãy ghi chép chi tiêu để Cú Mèo có thể lập kế hoạch nhé!",
            "category_plans": [],
        }

    user_config = (
        db.query(models.UserConfig)
        .filter(models.UserConfig.user_id == current_user.id)
        .first()
    )
    categories_str = (
        ", ".join(user_config.categories)
        if user_config and user_config.categories
        else "Ăn uống, Đi lại, Mua sắm, Hóa đơn, Giải trí"
    )

    # Lấy thông tin tiền tệ từ Frontend gửi lên
    currency_code = req.currency.upper()
    symbol = req.symbol
    rate = req.rate if req.rate > 0 else 1.0

    expense_rows = []
    income_rows = []
    for t in transactions:
        # QUY TRÌNH MỚI: Đổi tiền VND trong DB sang tiền hiển thị ngay tại Backend
        # 💡 ÉP KIỂU SANG FLOAT ĐỂ PYTHON CHỊU LÀM TOÁN
        converted_amount = float(t.amount) / float(rate) 
        row = f"{t.date.strftime('%Y-%m-%d')} | {t.name} | {converted_amount:.2f} | {t.category}"
        if t.amount < 0:
            expense_rows.append(row)
        else:
            income_rows.append(row)

    data_context = (
        f"LỊCH SỬ DÒNG TIỀN ({currency_code}):\nNgày | Mô tả | Số tiền | Danh mục\n"
        + "-" * 50
        + "\n"
    )
    data_context += "\n".join(expense_rows + income_rows)

    goal_context = ""
    if req.goal_name and req.goal_amount and req.goal_months:
        goal_context = f"\nMỤC TIÊU CỦA NGƯỜI DÙNG: Tiết kiệm {req.goal_amount:.2f} {currency_code} trong {req.goal_months} tháng tới cho mục đích '{req.goal_name}'."
    else:
        goal_context = "\nMỤC TIÊU: Người dùng chưa nhập mục tiêu cụ thể. Hãy tự đề xuất một kế hoạch cắt giảm hoang phí chung để tối ưu tài chính."

    prompt = f"""
Bạn là chuyên gia tài chính của ExpenseOwl. Hôm nay là {datetime.now().strftime("%Y-%m-%d")}.
Phân tích dữ liệu chi tiêu trong {month_window} tháng qua.
TẤT CẢ DỮ LIỆU SỐ TIỀN DƯỚI ĐÂY ĐỀU ĐANG Ở ĐƠN VỊ: {currency_code} (Ký hiệu: {symbol}).
Danh mục hợp lệ: {categories_str}
{goal_context}
{data_context}

YÊU CẦU QUAN TRỌNG: 
1. Tuyệt đối KHÔNG nhắc đến "VND" hay "Việt Nam Đồng" trong câu trả lời. 
2. Mọi phân tích, đánh giá, số tiền trong đoạn văn bản (overall_strategy, how_to_achieve) BẮT BUỘC phải dùng đơn vị {currency_code} (kèm ký hiệu {symbol}).

Hãy trả về DUY NHẤT JSON hợp lệ theo schema sau (không markdown, không thêm text khác):
{{
  "feasibility": "high" hoặc "medium" hoặc "low",
  "monthly_savings_needed": <Số tiền cần cất đi mỗi tháng ({currency_code}, số)>,
  "overall_strategy": "Đoạn văn phân tích chiến lược tổng thể.",
  "category_plans": [
    {{
      "category": "Tên danh mục",
      "current_avg_spend": <Số tiền trung bình ĐANG tiêu ({currency_code}, số)>,
      "target_spend": <Số tiền mục tiêu NÊN tiêu ({currency_code}, số)>,
      "reduction_amount": <Số tiền cắt giảm ({currency_code}, số)>,
      "how_to_achieve": "1-2 hành động cụ thể"
    }}
  ]
}}
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }

    cache_key = f"plan:{current_user.id}:{month_window}:{req.goal_amount}:{req.goal_months}:{currency_code}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    try:
        response = call_gemini_with_backoff(
            url,
            payload,
            headers={"Content-Type": "application/json"},
            timeout=60,
            retries=3,
        )
        result_data = response.json()
        ai_text = result_data["candidates"][0]["content"]["parts"][0]["text"]

        clean_text = ai_text.strip().replace("```json", "").replace("```", "")
        parsed = json.loads(clean_text)

        result = {
            "feasibility": str(parsed.get("feasibility", "medium")).lower(),
            "monthly_savings_needed": max(
                0, float(parsed.get("monthly_savings_needed", 0))
            ),
            "overall_strategy": str(
                parsed.get("overall_strategy", "Chưa có chiến lược.")
            ),
            "category_plans": parsed.get("category_plans", []),
        }

        _cache_set(cache_key, result, ttl_seconds=30 * 60)
        return result

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=502, detail="AI trả về dữ liệu không hợp lệ. Vui lòng thử lại."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=502, detail=f"Không thể tạo kế hoạch lúc này: {str(e)}"
        )


# ---------------------------------------------------------
# ROUTER CHO CẤU HÌNH NGƯỜI DÙNG (USER CONFIG)
# ---------------------------------------------------------
config_router = APIRouter(prefix="/api", tags=["User Config"])


@config_router.get("/config")
def get_config(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    user_config = (
        db.query(models.UserConfig)
        .filter(models.UserConfig.user_id == current_user.id)
        .first()
    )

    # 1. NẾU KHÔNG CÓ CONFIG -> TÀI KHOẢN MỚI
    if not user_config:
        return {
            "is_new_user": True,
            "currency": "vnd",
            "startDate": 1,
            "expenseCategories": ["Ăn uống", "Đi lại", "Mua sắm", "Hóa đơn", "Giải trí"],
            "incomeCategories": ["Lương", "Thưởng", "Đầu tư", "Khác"],
            "is_email_sync_enabled": False, # <--- TRẠNG THÁI MẶC ĐỊNH LÀ TẮT
            "financial_goal": "Chưa xác định",
            "risk_tolerance": "Cân bằng"
        }

    cats = user_config.categories
    # Đọc trạng thái từ Database (Dùng getattr để chống lỗi nếu cột chưa có)
    is_sync = getattr(user_config, 'is_email_sync_enabled', False)
    
    # 💡 LẤY THÊM MỤC TIÊU VÀ RỦI RO ĐỂ GỬI VỀ CHO FRONTEND
    goal = getattr(user_config, 'financial_goal', "Chưa xác định")
    risk = getattr(user_config, 'risk_tolerance', "Cân bằng")

    # 2. NẾU CÓ CONFIG -> TÀI KHOẢN CŨ (Đã chia 2 mảng)
    if isinstance(cats, dict):
        return {
            "is_new_user": False,
            "currency": user_config.currency,
            "startDate": user_config.startDate,
            "expenseCategories": cats.get("expenseCategories", ["Ăn uống", "Đi lại", "Mua sắm"]),
            "incomeCategories": cats.get("incomeCategories", ["Lương", "Thưởng"]),
            "is_email_sync_enabled": is_sync,
            "financial_goal": goal, # 👈 ĐÃ BỔ SUNG
            "risk_tolerance": risk  # 👈 ĐÃ BỔ SUNG
        }
    else:
        # 3. TƯƠNG THÍCH NGƯỢC (Tài khoản tạo từ thời phiên bản cũ)
        return {
            "is_new_user": False,
            "currency": user_config.currency,
            "startDate": user_config.startDate,
            "expenseCategories": cats if cats else ["Ăn uống", "Đi lại"],
            "incomeCategories": ["Lương", "Thưởng", "Đầu tư", "Khác"],
            "is_email_sync_enabled": is_sync,
            "financial_goal": goal, # 👈 ĐÃ BỔ SUNG
            "risk_tolerance": risk  # 👈 ĐÃ BỔ SUNG
        }

# 1. API Lưu Loại Tiền Tệ
from fastapi import Body


@config_router.post("/currency/edit")
def edit_currency(
    currency_code: str = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        user_config = (
            db.query(models.UserConfig)
            .filter(models.UserConfig.user_id == current_user.id)
            .first()
        )
        if not user_config:
            # Nếu chưa có cấu hình, tạo mới
            user_config = models.UserConfig(
                user_id=current_user.id, currency=currency_code.lower()
            )
            db.add(user_config)
        else:
            user_config.currency = currency_code.lower()

        db.commit()
        return {"message": "Cập nhật loại tiền tệ thành công"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# 2. API Lưu Ngày Bắt Đầu Tháng
@config_router.post("/startdate/edit")
def edit_start_date(
    start_date: int = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if start_date < 1 or start_date > 31:
        raise HTTPException(status_code=400, detail="Ngày bắt đầu phải từ 1 đến 31")

    try:
        user_config = (
            db.query(models.UserConfig)
            .filter(models.UserConfig.user_id == current_user.id)
            .first()
        )
        if not user_config:
            user_config = models.UserConfig(
                user_id=current_user.id, startDate=start_date
            )
            db.add(user_config)
        else:
            user_config.startDate = start_date

        db.commit()
        return {"message": "Cập nhật ngày bắt đầu thành công"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@config_router.post("/email-sync/toggle")
def toggle_email_sync(
    payload: EmailSyncUpdate, # <-- Dùng khuôn mẫu vừa tạo
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    user_config = db.query(models.UserConfig).filter(models.UserConfig.user_id == current_user.id).first()
    
    if not user_config:
        user_config = models.UserConfig(user_id=current_user.id, is_email_sync_enabled=payload.is_enabled)
        db.add(user_config)
    else:
        user_config.is_email_sync_enabled = payload.is_enabled
        
    db.commit()
    return {"message": "Đã cập nhật trạng thái", "status": payload.is_enabled}

# 3. API Lưu Danh Mục Chi Tiêu (Categories)
@config_router.post("/categories/edit")
def edit_categories(
    categories: Union[dict, list] = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if not categories:
        raise HTTPException(status_code=400, detail="Phải có ít nhất một danh mục")

    try:
        user_config = (
            db.query(models.UserConfig)
            .filter(models.UserConfig.user_id == current_user.id)
            .first()
        )
        if not user_config:
            user_config = models.UserConfig(
                user_id=current_user.id, categories=categories
            )
            db.add(user_config)
        else:
            user_config.categories = categories

        db.commit()
        return {"message": "Cập nhật danh mục thành công"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# 4. API Lưu Hồ sơ tài chính (AI Profile)
@config_router.post("/profile/edit")
def edit_profile(
    profile_data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    try:
        user_config = (
            db.query(models.UserConfig)
            .filter(models.UserConfig.user_id == current_user.id)
            .first()
        )
        if not user_config:
            user_config = models.UserConfig(
                user_id=current_user.id,
                financial_goal=profile_data.get("goal", "Chưa xác định"),
                risk_tolerance=profile_data.get("risk", "Cân bằng"),
            )
            db.add(user_config)
        else:
            user_config.financial_goal = profile_data.get("goal", "Chưa xác định")
            user_config.risk_tolerance = profile_data.get("risk", "Cân bằng")

        db.commit()
        return {"message": "Cập nhật hồ sơ AI thành công"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================
# ROUTER OCR - QUÉT HÓA ĐƠN
# =============================================================
@router.post("/scan-receipt")
async def scan_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Bước 1: OCR hóa đơn bằng Gemini Vision → trả về data để user review.
    KHÔNG tự lưu DB. Frontend hiển thị để user xác nhận rồi mới gọi /confirm.
    """
    # SỬ DỤNG HÀM LẤY KEY RANDOM Ở ĐÂY
    api_key = get_random_api_key()
    if not api_key:
        raise HTTPException(
            status_code=500, detail="Chưa cấu hình GEMINI_API_KEY trong file .env"
        )

    # Lấy danh mục của user hiện tại
    user_config = (
        db.query(models.UserConfig)
        .filter(models.UserConfig.user_id == current_user.id)
        .first()
    )

    if user_config and user_config.categories:
        categories_str = ", ".join(user_config.categories)
    else:
        categories_str = "Ăn uống, ĐI lại, Mua sắm, Hóa đơn, Giải trí, Thu nhập"

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Kiểm tra MIME type hợp lệ
    content_type = file.content_type or "image/jpeg"
    allowed_types = [
        "image/jpeg",
        "image/jpg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/heic",
    ]
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Định dạng không hỗ trợ: {content_type}. Dùng JPG, PNG hoặc WebP.",
        )

    try:
        original_bytes = await file.read()
        img = Image.open(io.BytesIO(original_bytes))

        # Chuyển đổi sang RGB
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        # Thu nhỏ ảnh nếu quá lớn
        img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

        # Lưu ảnh đã nén vào cache
        output_buffer = io.BytesIO()
        img.save(output_buffer, format="JPEG", quality=85)
        compressed_bytes = output_buffer.getvalue()
        base64_image = base64.b64encode(compressed_bytes).decode("utf-8")
        mime_type = "image/jpeg"

        prompt = f"""Hôm nay là {today_str}.
Phân tích hóa đơn trong ảnh và trích xuất thông tin tài chính.
Danh mục hợp lệ của người dùng: {categories_str}

Trả về CHỈ một JSON object thuần túy (không có markdown, không có backtick ```):
{{
    "name": "Tên cửa hàng hoặc mô tả ngắn (tối đa 60 ký tự)",
    "category": "Chọn ĐÚNG MỘT danh mục từ danh sách: {categories_str}",
    "amount": số_âm_đại_diện_chi_tiêu (ví dụ -54000, vì đây là khoản chi),
    "date": "YYYY-MM-DD (ngày trên hóa đơn, nếu không thấy dùng {today_str})",
    "tags": ["OCR"],
    "notes": "ghi chú ngắn nếu cần hoặc chuỗi rỗng"
}}

Quy tắc quan trọng:
- amount PHẢI là số ÂM (khoản chi tiêu). Ví dụ tổng 54.000đ → amount = -54000
- Nếu là phiếu hoàn tiền/refund thì amount mới là số DƯƠNG
- Nếu không đọc được số tiền, đặt amount = -1
- Đơn vị là VND (Việt Nam Đồng), không cần dấu phẩy hay chấm phân cách"""

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": mime_type, "data": base64_image}},
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 600},
        }

        response = call_gemini_with_backoff(
            url,
            payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
            retries=3,
        )
        _handle_gemini_http_status(response)
        result_data = response.json()

        # Kiểm tra response có candidates không
        if not result_data.get("candidates"):
            raise HTTPException(
                status_code=422,
                detail="AI không thể đọc được hóa đơn này. Thử ảnh rõ hơn.",
            )

        ai_text = result_data["candidates"][0]["content"]["parts"][0]["text"]

        # Làm sạch markdown nếu Gemini trả về có backtick
        clean_text = ai_text.strip()
        if clean_text.startswith("```"):
            lines = clean_text.split("\n")
            # Bỏ dòng đầu (```json) và dòng cuối (```)
            inner = []
            for line in lines[1:]:
                if line.strip() == "```":
                    break
                inner.append(line)
            clean_text = "\n".join(inner).strip()
        clean_text = clean_text.replace("```json", "").replace("```", "").strip()

        extracted_data = json.loads(clean_text)

        # Validate và đảm bảo đủ fields
        name = str(extracted_data.get("name", "Hóa đơn")).strip()[:100]
        amount = float(extracted_data.get("amount", -1))
        date_str = str(extracted_data.get("date", today_str)).strip()
        category = str(
            extracted_data.get("category", categories_str.split(",")[0])
        ).strip()
        tags = extracted_data.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        if "OCR" not in tags:
            tags.append("OCR")
        notes = str(extracted_data.get("notes", "")).strip()

        # Validate ngày
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            date_str = today_str

        return {
            "status": "success",
            "data": {
                "name": name,
                "amount": amount,
                "date": date_str,
                "category": category,
                "tags": tags,
                "notes": notes,
            },
            "message": "Phân tích hóa đơn thành công! Vui lòng kiểm tra và xác nhận.",
        }

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail="AI trả về dữ liệu không hợp lệ. Thử chụp lại ảnh rõ hơn.",
        )
    except Exception:
        raise HTTPException(status_code=500, detail="Lỗi xử lý hóa đơn.")


@router.post("/scan-receipt/confirm")
async def confirm_scan_receipt(
    transaction_data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    """
    Bước 2: Lưu giao dịch đã được user xác nhận vào database.
    """
    try:
        # Parse và validate ngày
        date_str = str(transaction_data.get("date", "")).strip()
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
        except (ValueError, AttributeError):
            parsed_date = datetime.now().date()

        # Validate amount
        try:
            amount = float(transaction_data.get("amount", 0))
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="Số tiền không hợp lệ")

        if amount == 0:
            raise HTTPException(status_code=400, detail="Số tiền không được bằng 0")

        # Validate name
        name = str(transaction_data.get("name", "Hóa đơn")).strip()
        if len(name) < 1:
            name = "Hóa đơn"

        # Validate category
        category = str(transaction_data.get("category", "Shopping")).strip()

        # Tags
        tags = transaction_data.get("tags", ["OCR"])
        if not isinstance(tags, list):
            tags = [str(tags)] if tags else ["OCR"]
        note_text = str(transaction_data.get("notes", "")).strip()

        new_id = str(uuid.uuid4())
        db_transaction = models.Transaction(
            id=new_id,
            name=name[:255],
            amount=amount,
            category=category,
            date=parsed_date,
            tags=tags,
            note=note_text,
            user_id=current_user.id,
        )

        db.add(db_transaction)
        # Tự động trừ ngân sách hoặc chia hũ sau khi quét hóa đơn xong
        if amount > 0:
            distribute_to_jars(db, current_user.id, amount)
        elif amount < 0:
            update_budget_spent(db, current_user.id, category, abs(amount))
        db.commit()
        db.refresh(db_transaction)

        return {
            "status": "success",
            "message": f"Đã lưu: {db_transaction.name} ({abs(db_transaction.amount):,.0f} VND)",
            "transaction": {
                "id": db_transaction.id,
                "name": db_transaction.name,
                "amount": db_transaction.amount,
                "category": db_transaction.category,
                "date": db_transaction.date.isoformat(),
                "tags": db_transaction.tags,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Lỗi lưu giao dịch: {str(e)}")


# =============================================================
# ROUTER OCR - QUÉT HÓA ĐƠN TỪ FILE PDF
# =============================================================
@router.post("/scan-pdf")
async def scan_pdf_receipt(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    api_key = get_random_api_key()
    if not api_key:
        raise HTTPException(
            status_code=500, detail="Chưa cấu hình GEMINI_API_KEY trong file .env"
        )

    # 1. Kiểm tra định dạng file phải là PDF
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="Định dạng không hỗ trợ. Vui lòng tải lên file .pdf"
        )

    # 2. Lấy danh mục của user (giống logic OCR cũ)
    user_config = (
        db.query(models.UserConfig)
        .filter(models.UserConfig.user_id == current_user.id)
        .first()
    )
    categories_str = (
        ", ".join(user_config.categories)
        if user_config and user_config.categories
        else "Ăn uống, Đi lại, Mua sắm, Hóa đơn, Giải trí, Thu nhập"
    )
    today_str = datetime.now().strftime("%Y-%m-%d")

    try:
        # 3. Đọc file PDF và rút trích Text bằng PyMuPDF
        pdf_bytes = await file.read()

        # Kiểm tra dung lượng (tối đa 15MB cho PDF)
        if len(pdf_bytes) > 15 * 1024 * 1024:
            raise HTTPException(
                status_code=400, detail="File PDF quá lớn! Tối đa 15MB."
            )

        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        extracted_text = ""
        for page in doc:
            extracted_text += page.get_text()

        doc.close()

        if not extracted_text.strip():
            raise HTTPException(
                status_code=422,
                detail="Không thể đọc được chữ trong file PDF này. File có thể là ảnh quét mờ.",
            )

        # 4. Viết Prompt riêng cho dữ liệu Text (không dùng inline_data hình ảnh)
        prompt = f"""Hôm nay là {today_str}.
Dưới đây là nội dung văn bản được trích xuất từ một file PDF (có thể chứa nhiều hóa đơn/sao kê). 
Hãy phân tích và trích xuất tất cả các thông tin giao dịch tài chính.
Danh mục hợp lệ của người dùng: {categories_str}

NỘI DUNG PDF:
{extracted_text[:4000]} 

Trả về CHỈ một MẢNG JSON (Array of Objects), không dùng markdown hay backtick:
[
    {{
        "name": "Tên cửa hàng/dịch vụ (tối đa 60 ký tự)",
        "category": "Chọn ĐÚNG MỘT danh mục từ danh sách: {categories_str}",
        "amount": số_âm_nếu_chi_tiêu_hoặc_dương_nếu_thu_nhập (ví dụ -54000),
        "date": "YYYY-MM-DD",
        "tags": ["PDF Scan"],
        "notes": "ghi chú ngắn"
    }}
]
"""
        # 5. Gọi AI bằng hàm backoff có sẵn của bạn
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1},
        }

        response = call_gemini_with_backoff(
            url,
            payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
            retries=3,
        )
        _handle_gemini_http_status(response)
        result_data = response.json()

        if not result_data.get("candidates"):
            raise HTTPException(
                status_code=422, detail="AI không thể xử lý file PDF này."
            )

        ai_text = result_data["candidates"][0]["content"]["parts"][0]["text"]

        # Làm sạch JSON
        clean_text = ai_text.strip()
        if clean_text.startswith("```"):
            clean_text = "\n".join(clean_text.split("\n")[1:-1]).strip()
        clean_text = clean_text.replace("```json", "").replace("```", "").strip()

        extracted_data = json.loads(clean_text)
        
        # Đảm bảo dữ liệu trả về luôn là 1 mảng (dù chỉ có 1 hóa đơn)
        if not isinstance(extracted_data, list):
            extracted_data = [extracted_data]
            
        # Làm sạch và validate từng item trong mảng
        processed_data = []
        for item in extracted_data:
             processed_data.append({
                "name": str(item.get("name", "Hóa đơn PDF"))[:100],
                "amount": float(item.get("amount", 0)),
                "date": str(item.get("date", today_str)),
                "category": str(item.get("category", categories_str.split(",")[0])),
                "tags": item.get("tags", ["PDF Scan"]),
                "notes": str(item.get("notes", ""))
             })

        return {
            "status": "success",
            "data": processed_data, # Trả về mảng đã được làm sạch
            "message": f"Đọc PDF thành công {len(processed_data)} giao dịch! Vui lòng xác nhận.",
        }

    except HTTPException:
        raise
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=422,
            detail="AI trả về dữ liệu không hợp lệ. Vui lòng kiểm tra lại file PDF.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý file PDF: {str(e)}")


# =============================================================
# ROUTER OCR - QUÉT FILE CSV
# =============================================================
@router.post("/scan-csv")
async def scan_csv_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    import pandas as pd
    import io
    import json

    # Lấy API Key (bạn tùy chỉnh logic lấy key đang dùng)
    api_key = get_random_api_key()
    if not api_key:
        raise HTTPException(status_code=500, detail="Chưa cấu hình API_KEY")

    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Vui lòng tải lên file .csv")

    user_config = (
        db.query(models.UserConfig)
        .filter(models.UserConfig.user_id == current_user.id)
        .first()
    )
    categories_str = (
        ", ".join(user_config.categories)
        if user_config and user_config.categories
        else "Ăn uống, Đi lại, Mua sắm, Hóa đơn, Giải trí, Thu nhập"
    )
    today_str = datetime.now().strftime("%Y-%m-%d")

    try:
        content = await file.read()

        # 1. Dùng pandas đọc CSV
        try:
            df = pd.read_csv(io.BytesIO(content))
            df.dropna(how="all", inplace=True)
            df = df.head(50)  # Tối đa 50 dòng để tiết kiệm token
            csv_text = df.to_csv(index=False)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Không thể đọc CSV: {str(e)}")

        if not csv_text.strip():
            raise HTTPException(status_code=422, detail="File CSV trống.")

        prompt = f"""Hôm nay là {today_str}.
Dưới đây là nội dung từ một file CSV giao dịch. 
Hãy phân tích và tự động gán cho nó 1 danh mục phù hợp từ: {categories_str}

NỘI DUNG CSV:
{csv_text}

YÊU CẦU: Trả về DUY NHẤT một MẢNG JSON. Mỗi phần tử là 1 giao dịch có cấu trúc:
[
    {{
        "name": "Tên cửa hàng",
        "category": "Danh mục",
        "amount": số_tiền (âm nếu là chi tiêu, dương nếu là thu nhập),
        "date": "YYYY-MM-DD"
    }}
]
"""
        # Gọi Gemini API
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1},
        }

        # Hàm gọi qua requests của bạn
        response = call_gemini_with_backoff(
            url,
            payload,
            headers={"Content-Type": "application/json"},
            timeout=45,
            retries=3,
        )
        _handle_gemini_http_status(response)
        result_data = response.json()

        if not result_data.get("candidates"):
            raise HTTPException(status_code=422, detail="AI không thể xử lý.")

        ai_text = result_data["candidates"][0]["content"]["parts"][0]["text"]

        # Làm sạch Markdown JSON
        clean_text = ai_text.strip()
        if clean_text.startswith("```"):
            clean_text = "\n".join(clean_text.split("\n")[1:-1]).strip()
        clean_text = clean_text.replace("```json", "").replace("```", "").strip()

        extracted_data = json.loads(clean_text)
        if not isinstance(extracted_data, list):
            extracted_data = [extracted_data]

        # Trả về chuẩn Data cho Frontend CSVScanner đọc
        return {
            "status": "success",
            "data": extracted_data,
            "message": f"Phân tích thành công {len(extracted_data)} giao dịch!",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------
# ROUTER CHO LẬP KẾ HOẠCH (BUDGETS & JARS)
# ---------------------------------------------------------
planning_router = APIRouter(prefix="/api/planning", tags=["Planning"])


@planning_router.get("/jars")
def get_jars(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return db.query(models.Jar).filter(models.Jar.user_id == current_user.id).order_by(models.Jar.id).all()

@planning_router.get("/jars/{jar_id}/history")
def get_jar_history(
    jar_id: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # Lấy lịch sử nạp rút trực tiếp từ DB mà không qua schemas.py khắt khe
    txs = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.amount == 0,
            models.Transaction.category == "Chuyển Quỹ"
        )
        .order_by(models.Transaction.date.desc())
        .all()
    )
    
    # Lọc danh sách an toàn bằng Python
    history = []
    for t in txs:
        if t.tags and str(jar_id) in t.tags:
            history.append({
                "id": t.id,
                "name": t.name,
                "date": t.date.isoformat()
            })
    return history

@planning_router.get("/jars/history/all")
def get_all_jar_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # Lấy 20 giao dịch nạp/rút gần nhất của tất cả các hũ
    txs = (
        db.query(models.Transaction)
        .filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.category == "Chuyển Quỹ"
        )
        .order_by(models.Transaction.date.desc())
        .limit(20)
        .all()
    )
    
    history = []
    for t in txs:
        history.append({
            "id": t.id,
            "name": t.name,
            "date": t.date.isoformat()
        })
    return history

@planning_router.post("/jars/bulk")
def setup_jars_bulk(jars_data: list = Body(...), db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    # 1. Lấy danh sách hũ hiện có trong DB
    existing_jars = db.query(models.Jar).filter(models.Jar.user_id == current_user.id).all()
    existing_map = {j.id: j for j in existing_jars}
    
    new_jar_ids = []
    for j in jars_data:
        j_id = j.get("id")
        name = j.get("name", "Hũ mới")
        percent = Decimal(str(j.get("percent", 0)))
        goal = Decimal(str(j.get("goal_amount", 0)))
        color = j.get("color", "#8a2be2")
        icon = j.get("icon", "fa-piggy-bank")

        if j_id and j_id in existing_map:
            # CẬP NHẬT: Nếu hũ đã tồn tại, chỉ đổi thông tin, GIỮ NGUYÊN balance
            jar = existing_map[j_id]
            jar.name = name
            jar.percent = percent
            jar.goal_amount = goal
            jar.color = color
            jar.icon = icon
            new_jar_ids.append(jar.id)
        else:
            # TẠO MỚI: Nếu chưa có thì mới tạo hũ mới
            new_jar = models.Jar(
                name=name, percent=percent, goal_amount=goal,
                color=color, icon=icon, balance=0.0, user_id=current_user.id
            )
            db.add(new_jar)
            db.flush() # Để lấy ID mới
            new_jar_ids.append(new_jar.id)

    # XÓA: Những hũ không còn nằm trong danh sách gửi lên
    for old_id, old_jar in existing_map.items():
        if old_id not in new_jar_ids:
            if old_jar.balance > 0:
                raise HTTPException(status_code=400, detail=f"Hũ '{old_jar.name}' còn tiền, không thể xóa!")
            db.delete(old_jar)

    db.commit()
    return {"message": "Cấu hình hũ đã được cập nhật an toàn!"}

# API NẠP / RÚT / CHUYỂN TIỀN CHỦ ĐỘNG
@planning_router.post("/jars/transfer")
def transfer_jar_funds(payload: dict = Body(...), db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    t_type = payload.get("type") # "deposit", "withdraw", "internal"
    amount = Decimal(str(payload.get("amount", 0)))
    
    if amount <= 0: raise HTTPException(status_code=400, detail="Số tiền phải lớn hơn 0")

    # Hai biến để ghi lịch sử
    history_name = ""
    tags = ["Quỹ", t_type]

    if t_type == "deposit":
        # 1. TÍNH SỐ DƯ KHẢ DỤNG (Tiền rảnh rỗi)
        all_txs = db.query(models.Transaction).filter(
            models.Transaction.user_id == current_user.id, 
            models.Transaction.category != "Chuyển Quỹ"
        ).all()
        
        total_income = sum(t.amount for t in all_txs if t.amount > 0)
        total_expense = sum(abs(t.amount) for t in all_txs if t.amount < 0)
        total_wallet = total_income - total_expense 
        
        # Tính tổng tiền đang bị khóa trong các hũ
        all_jars = db.query(models.Jar).filter(models.Jar.user_id == current_user.id).all()
        total_in_jars = sum(j.balance for j in all_jars)
        
        free_balance = total_wallet - total_in_jars # Tiền rảnh rỗi có thể nạp
        
        # 💡 CHỐT CHẶN: Nếu nạp lố tiền rảnh rỗi thì văng lỗi ngay
        if amount > free_balance:
            raise HTTPException(status_code=400, detail=f"Không đủ tiền rảnh rỗi! Bạn chỉ còn tối đa {free_balance:,.0f} để nạp.")

        # Nếu hợp lệ thì mới cho nạp
        jar = db.query(models.Jar).filter(models.Jar.id == payload.get("to_id"), models.Jar.user_id == current_user.id).first()
        if jar: 
            jar.balance += amount
            history_name = f"Nạp {amount:,.0f}đ vào hũ {jar.name}"
            tags.append(str(jar.id))
    elif t_type == "withdraw":
        jar = db.query(models.Jar).filter(models.Jar.id == payload.get("from_id"), models.Jar.user_id == current_user.id).first()
        if not jar or jar.balance < amount: raise HTTPException(status_code=400, detail="Hũ không đủ số dư")
        jar.balance -= amount
        history_name = f"Rút {amount:,.0f}đ từ hũ {jar.name}"
        tags.append(str(jar.id))
    elif t_type == "internal":
        f_jar = db.query(models.Jar).filter(models.Jar.id == payload.get("from_id"), models.Jar.user_id == current_user.id).first()
        t_jar = db.query(models.Jar).filter(models.Jar.id == payload.get("to_id"), models.Jar.user_id == current_user.id).first()
        if f_jar and t_jar and f_jar.balance >= amount:
            f_jar.balance -= amount
            t_jar.balance += amount
            history_name = f"Chuyển {amount:,.0f}đ từ hũ {f_jar.name} sang hũ {t_jar.name}"
            tags.extend([str(f_jar.id), str(t_jar.id)])
        else: raise HTTPException(status_code=400, detail="Giao dịch không hợp lệ")

    # 💡 BÍ KÍP: Ghi log lịch sử vào bảng Transaction với amount = 0 để không phá hỏng Thống kê Thu/Chi
    new_tx = models.Transaction(
        id=str(uuid.uuid4()),
        name=history_name,
        amount=0.0,
        category="Chuyển Quỹ",
        date=datetime.now().date(),
        tags=tags,
        user_id=current_user.id
    )
    db.add(new_tx)
    
    db.commit()
    return {"message": "Giao dịch thành công!"}

@planning_router.delete("/jars/{jar_id}")
def delete_jar(
    jar_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # 1. Tìm hũ trong Database
    jar = db.query(models.Jar).filter(
        models.Jar.id == jar_id, 
        models.Jar.user_id == current_user.id
    ).first()
    
    if not jar:
        raise HTTPException(status_code=404, detail="Không tìm thấy hũ trong hệ thống")
    
    # 2. Chốt chặn an toàn: Không cho xóa nếu hũ còn tiền
    if jar.balance > 0:
        raise HTTPException(status_code=400, detail="Hũ còn tiền! Vui lòng chuyển hoặc rút hết tiền ra trước khi xóa.")
        
    # 3. Tiến hành xóa
    db.delete(jar)
    db.commit()
    return {"message": "Đã xóa hũ thành công"}

@planning_router.get("/budgets")
def get_budgets(
    start_date: str,
    end_date: str,
    period_type: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    start = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
    end = datetime.strptime(end_date[:10], "%Y-%m-%d").date()

    # 1. Tìm ngân sách ĐÚNG khoảng thời gian này
    budgets = db.query(models.Budget).filter(
        models.Budget.user_id == current_user.id,
        models.Budget.start_date == start,
        models.Budget.end_date == end,
        models.Budget.period_type == period_type
    ).all()

    # 2. AUTO-COPY (KẾ THỪA): Nếu tuần/tháng này trống, copy cấu hình gần nhất sang
    if not budgets:
        last_budgets = db.query(models.Budget).filter(
            models.Budget.user_id == current_user.id,
            models.Budget.period_type == period_type
        ).order_by(models.Budget.id.desc()).limit(20).all()
        
        if last_budgets:
            last_start = last_budgets[0].start_date
            valid_lasts = [b for b in last_budgets if b.start_date == last_start]
            
            for pb in valid_lasts:
                new_b = models.Budget(
                    category=pb.category,
                    limit_amount=pb.limit_amount,
                    period_type=period_type,
                    start_date=start,
                    end_date=end,
                    user_id=current_user.id
                )
                db.add(new_b)
                budgets.append(new_b)
            db.commit()

    # 3. TÍNH TOÁN ĐỘNG TỪ BẢNG GIAO DỊCH
    result = []
    for b in budgets:
        # Tự động quét bảng Transaction, lọc đúng khoảng ngày và cộng tiền
        spent = db.query(func.sum(models.Transaction.amount)).filter(
            models.Transaction.user_id == current_user.id,
            models.Transaction.category == b.category,
            models.Transaction.amount < 0,
            func.date(models.Transaction.date) >= start,
            func.date(models.Transaction.date) <= end
        ).scalar() or 0.0
        
        result.append({
            "id": b.id,
            "category": b.category,
            "limit_amount": float(b.limit_amount),
            "spent_amount": abs(float(spent)), # Ép thành số dương cho UI dễ vẽ
            "period_type": b.period_type,
            "start_date": b.start_date.isoformat(),
            "end_date": b.end_date.isoformat()
        })
    
    return result



@planning_router.post("/budgets")
def set_budget(
    category: str,
    limit_amount: float,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    now = datetime.now()

    # Kiểm tra xem tháng này đã đặt ngân sách cho mục này chưa
    budget = (
        db.query(models.Budget)
        .filter(
            models.Budget.user_id == current_user.id,
            models.Budget.category == category,
            models.Budget.month == now.month,
            models.Budget.year == now.year,
        )
        .first()
    )

    if budget:
        budget.limit_amount = limit_amount  # Cập nhật nếu đã có
    else:
        new_budget = models.Budget(
            category=category,
            limit_amount=limit_amount,
            spent_amount=0.0,
            month=now.month,
            year=now.year,
            user_id=current_user.id,
        )
        db.add(new_budget)

    db.commit()
    return {"message": "Đã thiết lập ngân sách thành công!"}


@planning_router.post("/sync")
def sync_old_data(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    now = datetime.now()

    # 1. KHÔNG XÓA HŨ (Không dùng .delete()), chỉ reset số dư tiền về 0 để tính lại
    user_jars = db.query(models.Jar).filter(models.Jar.user_id == current_user.id).order_by(models.Jar.id).all()
    for jar in user_jars:
        jar.balance = 0.0

    # Reset Ngân sách hiện tại về 0
    budgets = (
        db.query(models.Budget)
        .filter(
            models.Budget.user_id == current_user.id,
            models.Budget.month == now.month,
            models.Budget.year == now.year,
        )
        .all()
    )
    for b in budgets:
        b.spent_amount = 0.0
    db.commit()

    # 2. Quét lại toàn bộ lịch sử giao dịch để tính toán lại
    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == current_user.id)
        .all()
    )
    for tx in transactions:
        if tx.amount > 0:
            distribute_to_jars(db, current_user.id, tx.amount)
        elif tx.amount < 0:
            if (
                getattr(tx.date, "month", -1) == now.month
                and getattr(tx.date, "year", -1) == now.year
            ):
                update_budget_spent(db, current_user.id, tx.category, abs(tx.amount))

    # LƯU KẾT QUẢ VÀO DATABASE
    db.commit()

    return {"message": "Đã đồng bộ toàn bộ dữ liệu lịch sử thành công!"}


@planning_router.delete("/budgets/{category}")
def delete_budget(
    category: str,
    start_date: str,
    end_date: str,
    period_type: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    start = datetime.strptime(start_date[:10], "%Y-%m-%d").date()
    end = datetime.strptime(end_date[:10], "%Y-%m-%d").date()
    
    budget = db.query(models.Budget).filter(
        models.Budget.user_id == current_user.id,
        models.Budget.category == category,
        models.Budget.start_date == start,
        models.Budget.end_date == end,
        models.Budget.period_type == period_type
    ).first()

    if budget:
        db.delete(budget)
        db.commit()
        return {"message": "Đã xóa ngân sách thành công!"}
    return {"message": "Không tìm thấy ngân sách"}





from fastapi import Body





@planning_router.post("/budgets/bulk")
def setup_budgets_bulk(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    start = datetime.strptime(payload["start_date"][:10], "%Y-%m-%d").date()
    end = datetime.strptime(payload["end_date"][:10], "%Y-%m-%d").date()
    period_type = payload["period_type"]
    budgets_data = payload["budgets"]

    user_config = db.query(models.UserConfig).filter(models.UserConfig.user_id == current_user.id).first()
    valid_categories = []
    if user_config and user_config.categories:
        if isinstance(user_config.categories, dict):
            valid_categories = user_config.categories.get("expenseCategories", [])
        elif isinstance(user_config.categories, list):
            valid_categories = user_config.categories

    for item in budgets_data:
        category = str(item.get("category", "")).strip()
        limit = float(item.get("limit_amount", 0))

        if not category: continue
        if valid_categories and category not in valid_categories:
            raise HTTPException(status_code=400, detail=f"Danh mục '{category}' không hợp lệ!")
        if limit < 0 or limit > 100000000000:
            raise HTTPException(status_code=400, detail=f"Hạn mức cho mục {category} không hợp lệ!")

        existing = db.query(models.Budget).filter(
            models.Budget.user_id == current_user.id,
            models.Budget.category == category,
            models.Budget.start_date == start,
            models.Budget.end_date == end,
            models.Budget.period_type == period_type
        ).first()

        if limit == 0:
            if existing: db.delete(existing)
            continue

        if existing:
            existing.limit_amount = limit
        else:
            new_budget = models.Budget(
                category=category,
                limit_amount=limit,
                period_type=period_type,
                start_date=start,
                end_date=end,
                user_id=current_user.id,
            )
            db.add(new_budget)

    db.commit()
    return {"message": "Đã cập nhật ngân sách thành công!"}


@planning_router.get("/dashboard-summary")
def get_jar_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    jars = db.query(models.Jar).filter(models.Jar.user_id == current_user.id).all()
    
    if not jars:
        return {"total_balance": 0, "near_goal": None, "biggest_jar": None}

    # 1. Tổng tiền trong tất cả hũ
    total_balance = sum(j.balance for j in jars)

    # 2. Hũ gần đạt goal nhất (Dựa trên % tiến độ, loại bỏ hũ đã 100%)
    near_goal = None
    max_percent = -1
    for j in jars:
        if j.goal_amount > 0:
            percent = (j.balance / j.goal_amount) * 100
            if percent < 100 and percent > max_percent:
                max_percent = percent
                near_goal = {"name": j.name, "percent": round(percent, 1)}

    # 3. Hũ lớn nhất (Dựa trên số dư hiện có)
    biggest_jar = max(jars, key=lambda j: j.balance)
    
    return {
        "total_balance": float(total_balance),
        "near_goal": near_goal,
        "biggest_jar": {"name": biggest_jar.name, "balance": float(biggest_jar.balance)}
    }

class N8nWebhookPayload(BaseModel):
    source: str
    sender: str
    receiver: str
    raw_content: str

# Chìa khóa bảo mật
N8N_API_KEY = os.getenv("N8N_API_KEY", "")

def verify_api_key(x_api_key: str = Header(None)):
    if not N8N_API_KEY or x_api_key != N8N_API_KEY:
        raise HTTPException(status_code=401, detail="Webhook bị từ chối: Sai API Key")

# 💡 Đã sửa URL: Bỏ chữ /api đi vì router đã có sẵn prefix /api/expenses
@router.post("/webhooks/n8n-receipt", tags=["Webhooks"])
def receive_n8n_receipt(
    payload: N8nWebhookPayload, 
    db: Session = Depends(get_db),
    api_key_header: str = Depends(verify_api_key) 
):
    try:
        # 1. Lấy API Key
        api_key = get_random_api_key()
        if not api_key:
            raise HTTPException(status_code=500, detail="Chưa cấu hình GEMINI_API_KEY")


        prompt = f"""
        Bạn là Cú Mèo, một chuyên gia phân tích dữ liệu tài chính cá nhân siêu việt. Nhiệm vụ của bạn là đọc nội dung email, biên lai hoặc tin nhắn sau:
        {payload.raw_content}
        
        NHIỆM VỤ 1 - CHỐT CHẶN (GATEKEEPER):
        Hãy kiểm tra xem email này CÓ PHẢI là một biên lai/thông báo biến động số dư, thông báo mua hàng hay không.
        Nếu đây là email quảng cáo, bản tin, mã OTP, nhắc nợ, hoặc hoàn toàn không chứa giao dịch tiền tệ, hãy trả về ĐÚNG MỘT khối JSON như sau (Không giải thích thêm):
        {{
            "is_transaction": false
        }}

        NHIỆM VỤ 2 - PHÂN TÍCH CHUYÊN SÂU:
        Nếu ĐÚNG là email giao dịch, hãy áp dụng các QUY TẮC sau để trích xuất:
        1. BỎ QUA CỔNG THANH TOÁN: Nếu thấy thanh toán qua "ShopeePay", "VNPay", "ZaloPay", "Momo", tuyệt đối KHÔNG lấy đó làm tên giao dịch. Hãy tìm xem người dùng THỰC SỰ mua cái gì (Tên shop, Tên món hàng).
        2. XỬ LÝ E-COMMERCE (Shopee, Lazada, Tiktok): Tìm danh sách sản phẩm. Nếu có nhiều món, tóm tắt lại. VD: "Mua Áo thun, Tai nghe trên Shopee". Danh mục: "Mua sắm".
        3. XỬ LÝ GRAB/BE/GOJEK: Phân biệt rõ là đi xe hay đặt đồ ăn. 
           - Đi xe: "GrabBike đến Quận 1" -> Danh mục: "Đi lại".
           - Đặt đồ ăn: "ShopeeFood: Cơm tấm" -> Danh mục: "Ăn uống".
        4. XỬ LÝ NGÂN HÀNG: Lọc bỏ các mã giao dịch rác (VD: MBVCB.123456.FT). Lấy nội dung cốt lõi: "Chuyển tiền ăn trưa cho Nam".

        Trả về JSON hợp lệ (TUYỆT ĐỐI KHÔNG DÙNG MARKDOWN ```):
        {{
            "is_transaction": true,
            "name": "Mô tả ngắn gọn, thông minh theo các quy tắc trên",
            "amount": Số tiền (chỉ lấy số nguyên dương, ví dụ: 64000),
            "type": "income" (nếu là tiền nhận/hoàn tiền) hoặc "expense" (nếu là tiền chi ra/thanh toán),
            "category": "Chọn 1 từ phù hợp: Ăn uống, Đi lại, Mua sắm, Hóa đơn, Giải trí, Lương, Thưởng, Đầu tư, Khác",
            "date": "Ngày giờ giao dịch (chuẩn ISO 8601, ví dụ: 2026-04-25T12:31:00)"
        }}
        """
        
        # 3. GỌI AI THỰC TẾ
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={api_key}"
        ai_payload = {"contents": [{"parts": [{"text": prompt}]}]}

        response = call_gemini_with_backoff(
            url,
            ai_payload,
            headers={"Content-Type": "application/json"},
            timeout=45,
            retries=3,
        )
        _handle_gemini_http_status(response)

        # 4. Bóc tách JSON
        result_data = response.json()
        ai_text = result_data["candidates"][0]["content"]["parts"][0]["text"]
        clean_text = ai_text.strip().replace("```json", "").replace("```", "")
        ai_result = json.loads(clean_text)
        
        print("🤖 KẾT QUẢ AI TRẢ VỀ:", ai_result)

        # 5. CHỐT CHẶN: Bỏ qua nếu không phải giao dịch
        if not ai_result.get("is_transaction", False):
            print(f"Bỏ qua email từ {payload.sender} vì không phải giao dịch hợp lệ.")
            return {"status": "ignored", "message": "Email không chứa giao dịch."}
            
        # 6. Xử lý logic tiền âm/dương
        final_amount = float(ai_result.get("amount", 0))
        if ai_result.get("type") == "expense":
            final_amount = -abs(final_amount)
        else:
            final_amount = abs(final_amount)
            
        try:
            parsed_date = datetime.fromisoformat(ai_result.get("date", "").replace("Z", "+00:00"))
        except Exception:
            parsed_date = datetime.now()

        # 💡 THUẬT TOÁN ĐỊNH DANH USER (Khắc phục lỗi User ID = 1)
        # Quét xem email người gửi (VD: tangcamminh2000@gmail.com) khớp với User nào trong DB
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', payload.receiver)
        extracted_email = email_match.group(0).lower() if email_match else payload.receiver.lower()

        # Tìm User trong Database có email khớp với email nhận thư
        target_user = db.query(models.User).filter(models.User.email == extracted_email).first()

        if not target_user:
            return {"status": "ignored", "message": "Email người nhận không có trong hệ thống!"}
            
        # 🛡️ CHỐT CHẶN CẤP 2: KIỂM TRA XEM USER CÓ ĐANG BẬT CÔNG TẮC KHÔNG
        user_config = db.query(models.UserConfig).filter(models.UserConfig.user_id == target_user.id).first()
        if not user_config or getattr(user_config, 'is_email_sync_enabled', False) == False:
            print(f"❌ Từ chối: Tài khoản {target_user.full_name} đang TẮT đồng bộ Email.")
            return {"status": "ignored", "message": "Người dùng đã tắt tính năng đồng bộ."}
            
        user_id_to_save = target_user.id
        print(f"✅ Đã tìm thấy chủ nhân: ID {user_id_to_save} - {target_user.full_name}")

        # 7. Lưu Database
        new_expense = models.Transaction(
            id=str(uuid.uuid4()),
            name=ai_result.get("name", "Auto Receipt")[:255],
            category=ai_result.get("category", "Khác"),
            amount=final_amount,
            date=parsed_date,
            tags=["Auto-Gmail"],
            user_id=user_id_to_save 
        )
        db.add(new_expense)
        
        # Cập nhật Hũ/Ngân sách (Optional)
        if final_amount > 0:
            distribute_to_jars(db, user_id_to_save, final_amount)
        elif final_amount < 0:
            update_budget_spent(db, user_id_to_save, new_expense.category, abs(final_amount))

        db.commit()

        return {"status": "success", "message": "Biên lai đã được tự động lưu!"}

    except Exception as e:
        print(f"🚨 Webhook Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(e)}")
    

# API Lấy thông tin tài khoản đầy đủ
@auth_router.get("/me", response_model=schemas.UserOut)
def get_user_profile(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    # Lấy thông tin config để lấy Mục tiêu và Rủi ro từ Database
    user_config = db.query(models.UserConfig).filter(models.UserConfig.user_id == current_user.id).first()
    
    return {
        "id": current_user.id,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "email": current_user.email,
        "gender": current_user.gender,
        "dob": current_user.dob.isoformat() if current_user.dob else None, # Chuyển date sang string
        "financial_goal": getattr(user_config, 'financial_goal', "Chưa xác định"),
        "risk_tolerance": getattr(user_config, 'risk_tolerance', "Cân bằng")
    }

# API Cập nhật thông tin cá nhân cơ bản
@auth_router.put("/me/update")
def update_profile_info(
    req: schemas.UserUpdateProfile,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    current_user.full_name = req.full_name
    current_user.gender = req.gender
    if req.dob:
        try:
            current_user.dob = datetime.strptime(req.dob, "%Y-%m-%d").date()
        except ValueError:
            pass
    
    db.commit()
    return {"message": "Cập nhật thông tin cá nhân thành công!"}

    