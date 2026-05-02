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

load_dotenv()
import random

import models, schemas, auth
from database import get_db

# OCR quét hóa đơn
from google import genai
from google.genai import types
from PIL import Image
import io
import base64

# Simple in-memory TTL cache for AI responses to reduce repeated GPT calls
import threading
import csv
import io
import uuid
from datetime import datetime
from fastapi import UploadFile, File
from fastapi.responses import StreamingResponse

# OCR cho PDF
import fitz
import pandas as pd

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
    # Lấy các hũ mà bạn ĐÃ TẠO trong DB
    user_jars = db.query(models.Jar).filter(models.Jar.user_id == user_id).all()

    if not user_jars:
        print("Chưa có hũ nào được thiết lập, không thể chia tiền!")
        return

    for jar in user_jars:
        # Chia tiền dựa trên cột percent bạn vừa thêm vào DB
        allocated_money = income_amount * (jar.percent / 100)
        jar.balance += allocated_money

    db.commit()


# 2. Hàm tự động trừ Ngân sách khi có CHI TIÊU (Số Âm)
def update_budget_spent(db: Session, user_id: int, category: str, spent_amount: float):
    now = datetime.now()
    # Tìm ngân sách của danh mục này trong tháng hiện tại
    budget = (
        db.query(models.Budget)
        .filter(
            models.Budget.user_id == user_id,
            models.Budget.category == category,
            models.Budget.month == now.month,
            models.Budget.year == now.year,
        )
        .first()
    )

    if budget:
        # Nếu user có thiết lập ngân sách cho mục này, thì cộng dồn tiền đã tiêu
        budget.spent_amount += spent_amount
        # (Bạn có thể ném ra cảnh báo ở đây nếu budget.spent_amount > budget.limit_amount)


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
def get_transactions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # CHỈ LẤY giao dịch của user đang đăng nhập
    return (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == current_user.id)
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
        # Nếu là Chi Tiêu -> Cập nhật số tiền đã xài vào Ngân sách tháng này
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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
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

    # BƯỚC 1: Lấy Cấu hình, Danh mục và HỒ SƠ TÍNH CÁCH hiện tại
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

    current_goal = (
        user_config.financial_goal
        if user_config and user_config.financial_goal
        else "Chưa xác định"
    )
    current_risk = (
        user_config.risk_tolerance
        if user_config and user_config.risk_tolerance
        else "Cân bằng"
    )

    # BƯỚC 2: Rút trích dữ liệu của riêng người dùng (RAG)
    transactions = (
        db.query(models.Transaction)
        .filter(models.Transaction.user_id == current_user.id)
        .all()
    )

    # 👇 THÊM ĐOẠN NÀY: CODE PYTHON TỰ TÍNH TOÁN SỐ DƯ 👇
    total_income = sum(t.amount for t in transactions if t.amount > 0)
    total_expense = sum(abs(t.amount) for t in transactions if t.amount < 0)
    current_balance_vnd = total_income - total_expense
    current_balance_display = current_balance_vnd / req.rate
    data_context = "GIAO DỊCH GẦN ĐÂY:\n"
    if not transactions:
        data_context += "Trống.\n"
    else:
        # Tối ưu: Chỉ lấy 30 giao dịch gần nhất để tránh tràn Token
        for t in sorted(transactions, key=lambda x: x.date, reverse=True)[:30]:
            data_context += f"{t.date.strftime('%Y-%m-%d')} | {t.name} | {t.amount} | {t.category}\n"

    # BƯỚC 3: Xử lý lịch sử Chat
    history_text = ""
    if req.history:
        history_text = "LỊCH SỬ CHAT:\n"
        for turn in req.history[-3:]:  # Tối ưu: Chỉ giữ 3 đoạn hội thoại gần nhất
            history_text += f"User: {turn.get('user', '')}\nAI: {turn.get('ai', '')}\n"

    # BƯỚC 4: PROMPT TỐI ƯU HÓA (Gọn gàng, mạnh mẽ, đa nhiệm)
    today_str = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
    Bạn là "Cú Mèo" - Cố vấn tài chính cá nhân của ExpenseOwl. Hôm nay: {today_str}.
    TIỀN TỆ HIỆN TẠI: {req.currency.upper()} (Tỷ giá 1 {req.currency.upper()} = {req.rate} VNĐ).

    HỒ SƠ KHÁCH HÀNG: Mục tiêu: {current_goal} | Khẩu vị rủi ro: {current_risk}.
    {data_context}
    {history_text}
    
    CÂU HỎI TỪ KHÁCH HÀNG: "{req.message}"
    
    NHIỆM VỤ: Trả về DUY NHẤT 1 KHỐI JSON TỰ THUẦN (Không kèm markdown ```).
    QUY TẮC BẮT BUỘC:
    1. "reply": Tư vấn thân thiện dựa trên HỒ SƠ KHÁCH HÀNG. Báo cáo số tiền bằng {req.currency.upper()} (Tự chia dữ liệu lịch sử cho {req.rate}. Tuyệt đối không nhắc tới VNĐ nếu tiền tệ khác VND).
    2. "action": Quyết định 1 trong 3 hành động sau:
       - "save": Nếu khách cung cấp ĐỦ Tên khoản VÀ Số tiền. (Thu=DƯƠNG, Chi=ÂM). Nếu khách nói số không đơn vị, ngầm hiểu là {req.currency.upper()}. Giá trị lưu 'amount' PHẢI nhân với {req.rate} để ra VNĐ.
       - "update_profile": CHỈ KHI khách có quyết định thay đổi mục tiêu DÀI HẠN (VD: "Tôi muốn đổi mục tiêu thành mua nhà", "Tôi đang gánh khoản nợ ngân hàng lớn cần lập kế hoạch"). TUYỆT ĐỐI KHÔNG thay đổi hồ sơ nếu đó chỉ là các khoản vay mượn lặt vặt, ngắn hạn (VD: nợ bạn bè vài đồng, khoản nợ trả trong ngày).
       - "chat": Nếu thiếu số tiền/tên khoản (hỏi lại khách), hoặc nhờ lập kế hoạch ngắn hạn, hoặc trò chuyện thông thường. KHÔNG tự bịa số tiền.
       
    CẤU TRÚC JSON:
    {{
        "reply": "Câu trả lời của Cú Mèo",
        "action": "chat" | "save" | "update_profile",
        "data": {{ "name": "...", "amount": ±VNĐ, "category": "Chọn 1: {categories_str}", "date": "YYYY-MM-DD" }} | null,
        "profile_update": {{ "financial_goal": "Mục tiêu mới", "risk_tolerance": "Rủi ro mới" }} | null
    }}
    """

    # BƯỚC 5: Gọi Gemini 2.5 Flash
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }

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
        ai_text = result_data["candidates"][0]["content"]["parts"][0]["text"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi AI: {str(e)}")

    # BƯỚC 6: Xử lý KẾT QUẢ VÀ CẬP NHẬT DB NGẦM
    try:
        clean_text = ai_text.strip().replace("```json", "").replace("```", "")
        result_json = json.loads(clean_text)

        transaction_data = None
        final_action = result_json.get("action", "chat")

        # 6.1. Đóng gói dữ liệu giao dịch (Nếu có)
        if final_action == "save" and result_json.get("data"):
            data = result_json["data"]
            try:
                parsed_date = datetime.strptime(
                    data.get("date", today_str), "%Y-%m-%d"
                ).date()
            except Exception:
                parsed_date = datetime.now()
            # 1. Tạo đối tượng Transaction để lưu vào DB
            new_tx_id = str(uuid.uuid4())
            new_transaction = models.Transaction(
                id=new_tx_id,
                name=str(data.get("name", "Giao dịch AI"))[:255],
                amount=float(data.get("amount", 0)),
                category=str(data.get("category", "Other")),
                date=parsed_date,
                tags=["AI Chatbot"],
                user_id=current_user.id,
            )
            db.add(new_transaction)

            # 2. Thực hiện logic tự động phân bổ Hũ hoặc trừ Ngân sách
            amount = new_transaction.amount
            if amount > 0:
                # Nếu là Thu Nhập -> Gọi hàm chia tiền vào 6 Hũ
                distribute_to_jars(db, current_user.id, amount)
            elif amount < 0:
                # Nếu là Chi Tiêu -> Gọi hàm trừ Ngân sách tháng này
                update_budget_spent(
                    db, current_user.id, new_transaction.category, abs(amount)
                )

            # 3. Lưu tất cả thay đổi vào Database
            db.commit()
            db.refresh(new_transaction)
            # ------------------------------------------

            # Đóng gói lại dữ liệu trả về Frontend để hiển thị thông báo
            transaction_data = {
                "id": new_tx_id,
                "name": new_transaction.name,
                "amount": new_transaction.amount,
                "category": new_transaction.category,
                "date": new_transaction.date.isoformat(),
                "tags": new_transaction.tags,
            }

        # 6.2. Tự động lưu Profile (Nếu AI phát hiện thay đổi)
        if result_json.get("profile_update"):
            p_data = result_json["profile_update"]
            new_goal = p_data.get("financial_goal")
            new_risk = p_data.get("risk_tolerance")

            if new_goal or new_risk:
                if user_config:
                    if new_goal:
                        user_config.financial_goal = new_goal
                    if new_risk:
                        user_config.risk_tolerance = new_risk
                else:
                    user_config = models.UserConfig(
                        user_id=current_user.id,
                        financial_goal=new_goal or "Chưa xác định",
                        risk_tolerance=new_risk or "Cân bằng",
                    )
                    db.add(user_config)
                db.commit()
                final_action = "update_profile"  # Báo cho Frontend biết để tiện xử lý

        return {
            "reply": result_json.get("reply", "Lỗi phản hồi"),
            "action": final_action,
            "transaction_data": transaction_data,
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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
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
        converted_amount = t.amount / rate
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

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
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

    if not user_config:
        return {
            "currency": "usd",
            "startDate": 1,
            "categories": ["Food", "Transport", "Shopping", "Bills", "Entertainment"],
        }

    return {
        "currency": user_config.currency,
        "startDate": user_config.startDate,
        "categories": user_config.categories,
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


# 3. API Lưu Danh Mục Chi Tiêu (Categories)
@config_router.post("/categories/edit")
def edit_categories(
    categories: list = Body(...),
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

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

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
Dưới đây là nội dung văn bản được trích xuất từ một file PDF hóa đơn/sao kê. 
Hãy phân tích và trích xuất thông tin tài chính.
Danh mục hợp lệ của người dùng: {categories_str}

NỘI DUNG PDF:
{extracted_text[:3000]} # Giới hạn 3000 ký tự đầu để tránh tràn token nếu file quá dài

Trả về CHỈ một JSON object thuần túy (không markdown):
{{
    "name": "Tên cửa hàng/dịch vụ (tối đa 60 ký tự)",
    "category": "Chọn ĐÚNG MỘT danh mục từ danh sách: {categories_str}",
    "amount": số_âm_đại_diện_chi_tiêu (ví dụ -54000),
    "date": "YYYY-MM-DD",
    "tags": ["PDF Scan"],
    "notes": "ghi chú ngắn"
}}
"""
        # 5. Gọi AI bằng hàm backoff có sẵn của bạn
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
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

        return {
            "status": "success",
            "data": {
                "name": str(extracted_data.get("name", "Hóa đơn PDF"))[:100],
                "amount": float(extracted_data.get("amount", -1)),
                "date": str(extracted_data.get("date", today_str)),
                "category": str(
                    extracted_data.get("category", categories_str.split(",")[0])
                ),
                "tags": extracted_data.get("tags", ["PDF Scan"]),
                "notes": str(extracted_data.get("notes", "")),
            },
            "message": "Đọc PDF thành công! Vui lòng xác nhận.",
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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
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
    return db.query(models.Jar).filter(models.Jar.user_id == current_user.id).all()


@planning_router.get("/budgets")
def get_current_month_budgets(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    now = datetime.now()
    budgets = (
        db.query(models.Budget)
        .filter(
            models.Budget.user_id == current_user.id,
            models.Budget.month == now.month,
            models.Budget.year == now.year,
        )
        .all()
    )
    return budgets


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
    user_jars = db.query(models.Jar).filter(models.Jar.user_id == current_user.id).all()
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
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    now = datetime.now()
    # Tìm ngân sách của tháng hiện tại theo danh mục
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
        db.delete(budget)
        db.commit()
        return {"message": "Đã xóa ngân sách thành công!"}
    return {"message": "Không tìm thấy ngân sách"}


@planning_router.post("/jars")
def create_jar(
    jar_data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    new_jar = models.Jar(
        name=jar_data["name"],
        percent=jar_data["percent"],
        user_id=current_user.id,
        balance=0.0,
    )
    db.add(new_jar)
    db.commit()
    return {"message": "Success"}


from fastapi import Body


@planning_router.post("/jars/bulk")
def setup_jars_bulk(
    jars_data: list = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    # 1. Kiểm tra tổng phần trăm
    total_percent = sum(float(j.get("percent", 0)) for j in jars_data)
    if total_percent != 100:
        raise HTTPException(
            status_code=400, detail="Tổng phần trăm phải đúng bằng 100%"
        )

    # 2. Xóa các hũ cũ của user này
    db.query(models.Jar).filter(models.Jar.user_id == current_user.id).delete()

    # 3. Thêm danh sách hũ mới (Số dư ban đầu là 0)
    for j in jars_data:
        new_jar = models.Jar(
            name=j["name"],
            percent=float(j["percent"]),
            balance=0.0,
            user_id=current_user.id,
        )
        db.add(new_jar)

    db.commit()
    return {"message": "Đã lưu cấu hình hũ thành công!"}


@planning_router.post("/budgets/bulk")
def setup_budgets_bulk(
    budgets_data: list = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    now = datetime.now()

    for item in budgets_data:
        category = item.get("category")
        limit = float(item.get("limit_amount", 0))

        # Tìm xem tháng này đã có ngân sách cho mục này chưa
        existing = (
            db.query(models.Budget)
            .filter(
                models.Budget.user_id == current_user.id,
                models.Budget.category == category,
                models.Budget.month == now.month,
                models.Budget.year == now.year,
            )
            .first()
        )

        if existing:
            existing.limit_amount = limit
        else:
            new_budget = models.Budget(
                category=category,
                limit_amount=limit,
                spent_amount=0.0,
                month=now.month,
                year=now.year,
                user_id=current_user.id,
            )
            db.add(new_budget)

    db.commit()
    return {"message": "Đã cập nhật ngân sách hàng loạt thành công!"}
