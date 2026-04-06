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



@auth_router.post("/login")
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Tên đăng nhập hoặc mật khẩu không đúng")
    
    access_token = auth.create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@auth_router.put("/change-password")
def change_password(passwords: schemas.UserUpdatePassword, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    # 1. Kiểm tra xem mật khẩu cũ nhập vào có đúng không
    if not auth.verify_password(passwords.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Mật khẩu hiện tại không chính xác!")
    
    # 2. Kiểm tra mật khẩu mới không được trùng mật khẩu cũ
    if auth.verify_password(passwords.new_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Mật khẩu mới không được giống mật khẩu cũ!")

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

# Schema mới cho API Chatbot
class ChatRequest(BaseModel):
    message: str
    history: list = []

# 1. API NHẬP LIỆU BẰNG NGÔN NGỮ TỰ NHIÊN 
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
        
        # Ép kiểu chuỗi chữ thành kiểu Ngày tháng (Date Object)
        parsed_date = datetime.strptime(data["date"], "%Y-%m-%d").date()
        
        # Lưu vào cơ sở dữ liệu
        new_id = str(uuid.uuid4())
        db_transaction = models.Transaction(
            id=new_id,
            name=data["name"],
            amount=data["amount"],
            category=data["category"],
            date=parsed_date,
            tags=["AI Assistant"],
            user_id=current_user.id
        )
        db.add(db_transaction)
        db.commit()
        db.refresh(db_transaction)
        
        return {"message": "AI đã phân tích và lưu thành công!", "transaction": db_transaction}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi AI: {str(e)}")

# ---------------------------------------------------------
# 2. API CHATBOT TRUY VẤN DỮ LIỆU CÓ TRÍ NHỚ (RAG + MEMORY)
# ---------------------------------------------------------

# Schema mới cho API Chatbot 
class ChatRequest(BaseModel):
    message: str
    history: list = [] # Mảng chứa lịch sử trò chuyện: [{"user": "...", "ai": "..."}, ...]

@ai_router.post("/chat")
def chat_with_data(req: ChatRequest, db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Chưa cấu hình GEMINI_API_KEY")

    # BƯỚC 1: Rút trích dữ liệu của riêng người dùng này từ Database
    transactions = db.query(models.Transaction).filter(models.Transaction.user_id == current_user.id).all()
    
    # BƯỚC 2: Ráp dữ liệu Database thành chuỗi văn bản cho AI đọc
    data_context = "DANH SÁCH GIAO DỊCH CỦA NGƯỜI DÙNG:\n"
    data_context += "Ngày | Tên giao dịch | Số tiền | Danh mục\n"
    data_context += "-" * 50 + "\n"
    
    if not transactions:
        data_context += "Hiện tại người dùng chưa có giao dịch nào.\n"
    else:
        for t in transactions:
            data_context += f"{t.date} | {t.name} | {t.amount} VND | {t.category}\n"

    # BƯỚC 3: Xử lý mảng lịch sử thành chuỗi văn bản
    history_text = ""
    if req.history:
        history_text = "LỊCH SỬ TRÒ CHUYỆN GẦN ĐÂY CỦA BẠN VÀ NGƯỜI DÙNG:\n"
        for turn in req.history:
            history_text += f"Người dùng hỏi: {turn.get('user', '')}\nCú Mèo trả lời: {turn.get('ai', '')}\n"
        history_text += "-" * 50 + "\n"

    # BƯỚC 4: Kỹ thuật Prompt Engineering định hình Chatbot (Nhồi Context + History)
    today_str = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""
    Bạn là "Cú Mèo" - một chuyên gia tư vấn tài chính cá nhân thông minh, tận tâm và vui tính của ứng dụng ExpenseOwl.
    Hôm nay là ngày {today_str}.
    
    Dưới đây là DỮ LIỆU TÀI CHÍNH THỰC TẾ của người dùng mà bạn đang trò chuyện (Lưu ý: Số tiền ÂM là chi tiêu, DƯƠNG là thu nhập):
    {data_context}
    
    {history_text}
    
    CÂU HỎI MỚI NHẤT CỦA NGƯỜI DÙNG: "{req.message}"
    
    NHIỆM VỤ CỦA BẠN:
    1. Trả lời trực tiếp, chính xác câu hỏi MỚI NHẤT của người dùng.
    2. QUAN TRỌNG: Nếu câu hỏi mới nhất của người dùng ám chỉ đến một thông tin cũ (Ví dụ: "Khoản đó là khoản nào?", "Nó diễn ra khi nào?"), hãy dựa vào LỊCH SỬ TRÒ CHUYỆN ở trên để hiểu "khoản đó", "nó" là gì.
    3. Nếu cần tính toán (tổng chi, tổng thu, tìm món đắt nhất...), hãy tự tính toán từ DỮ LIỆU TÀI CHÍNH và đưa ra con số cuối cùng (tính nhẩm cẩn thận).
    4. Trả lời bằng tiếng Việt, giọng điệu thân thiện, tự nhiên. Định dạng Markdown: Dùng in đậm (**chữ**) cho các con số quan trọng.
    5. Trả lời ngắn gọn, súc tích, không dài dòng giải thích quá trình tính toán trừ khi được hỏi.
    6. Nếu người dùng hỏi ngoài lề (không liên quan tài chính), hãy khéo léo nhắc họ quay lại chủ đề.
    """
    
    # BƯỚC 5: Gọi Gemini 2.5 Flash
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    
    try:
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status() 
        
        result_data = response.json()
        ai_reply = result_data["candidates"][0]["content"]["parts"][0]["text"]
        
        return {"reply": ai_reply}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi Chatbot AI: {str(e)}")

# ---------------------------------------------------------
# 3. API PHÂN TÍCH XU HƯỚNG VÀ PHÁT HIỆN BẤT THƯỜNG
# ---------------------------------------------------------
@ai_router.get("/analyze-trends")
def analyze_trends_and_anomalies(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="Chưa cấu hình GEMINI_API_KEY")

    # 1. Lấy toàn bộ giao dịch của người dùng
    transactions = db.query(models.Transaction).filter(models.Transaction.user_id == current_user.id).all()
    
    if not transactions:
        return {"reply": "Chưa có đủ dữ liệu giao dịch để phân tích. Bạn hãy ghi chép thêm nhé!"}

    # 2. Ráp dữ liệu thành bảng văn bản
    data_context = "DANH SÁCH GIAO DỊCH TRONG QUÁ KHỨ VÀ HIỆN TẠI:\nNgày | Tên giao dịch | Số tiền | Danh mục\n"
    data_context += "-" * 50 + "\n"
    for t in transactions:
        data_context += f"{t.date.strftime('%Y-%m-%d')} | {t.name} | {t.amount} | {t.category}\n"

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
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        response.raise_for_status() 
        result_data = response.json()
        ai_reply = result_data["candidates"][0]["content"]["parts"][0]["text"]
        return {"reply": ai_reply}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Lỗi AI phân tích: {str(e)}")
    

# ---------------------------------------------------------
# ROUTER CHO CẤU HÌNH NGƯỜI DÙNG (USER CONFIG)
# ---------------------------------------------------------
config_router = APIRouter(prefix="/api", tags=["User Config"])

@config_router.get("/config")
def get_config(db: Session = Depends(get_db), current_user: models.User = Depends(auth.get_current_user)):
    user_config = db.query(models.UserConfig).filter(models.UserConfig.user_id == current_user.id).first()
    
    # Nếu là người dùng mới chưa chỉnh Settings bao giờ, trả về bộ mặc định
    if not user_config:
        return {
            "currency": "usd",
            "startDate": 1,
            "categories": ["Food", "Transport", "Shopping", "Bills", "Entertainment"]
        }
        
    return {
        "currency": user_config.currency,
        "startDate": user_config.startDate,
        "categories": user_config.categories
    }

# 1. API Lưu Loại Tiền Tệ
from fastapi import Body

@config_router.post("/currency/edit")
def edit_currency(
    currency_code: str = Body(...),
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    try:
        user_config = db.query(models.UserConfig).filter(models.UserConfig.user_id == current_user.id).first()
        if not user_config:
            # Nếu chưa có cấu hình, tạo mới
            user_config = models.UserConfig(user_id=current_user.id, currency=currency_code.lower())
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
    current_user: models.User = Depends(auth.get_current_user)
):
    if start_date < 1 or start_date > 31:
        raise HTTPException(status_code=400, detail="Ngày bắt đầu phải từ 1 đến 31")
        
    try:
        user_config = db.query(models.UserConfig).filter(models.UserConfig.user_id == current_user.id).first()
        if not user_config:
            user_config = models.UserConfig(user_id=current_user.id, startDate=start_date)
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
    current_user: models.User = Depends(auth.get_current_user)
):
    if not categories:
        raise HTTPException(status_code=400, detail="Phải có ít nhất một danh mục")
        
    try:
        user_config = db.query(models.UserConfig).filter(models.UserConfig.user_id == current_user.id).first()
        if not user_config:
            user_config = models.UserConfig(user_id=current_user.id, categories=categories)
            db.add(user_config)
        else:
            user_config.categories = categories
            
        db.commit()
        return {"message": "Cập nhật danh mục thành công"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))