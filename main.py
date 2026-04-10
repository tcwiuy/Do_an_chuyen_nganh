from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import models
from database import engine
from routers import router as expenses_router, recurring_router, auth_router, ai_router
from routers import config_router
import routers
from dotenv import load_dotenv
load_dotenv()

# Tạo bảng trong CSDL
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ExpenseOwl Python API")

# 1. Cấu hình phục vụ file tĩnh (CSS, JS, Ảnh) ở đường dẫn /static/
app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. Cấu hình thư mục chứa giao diện HTML
templates = Jinja2Templates(directory="templates")

# Nhúng API router
app.include_router(expenses_router)
app.include_router(recurring_router)
app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(routers.config_router, prefix="") 

# ---------------------------------------------------------
# ROUTER CHO GIAO DIỆN (FRONTEND)
# ---------------------------------------------------------

# THÊM ĐOẠN NÀY VÀO MAIN.PY
@app.get("/login")
def render_login(request: Request):
    # Trả về trang login.html
    return templates.TemplateResponse(request=request, name="login.html")

@app.get("/")
def render_dashboard(request: Request):
    # Trả về trang index.html
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/table")
def render_table(request: Request):
    return templates.TemplateResponse(request=request, name="table.html")

@app.get("/settings")
def render_settings(request: Request):
    # Trả về trang settings.html
    return templates.TemplateResponse(request=request, name="settings.html")

@app.get("/suggestions")
def render_suggestions(request: Request):
    # Trả về trang suggestions.html
    return templates.TemplateResponse(request=request, name="suggestions.html")

# MOCK API CONFIG (Thêm vào main.py)
@app.get("/api/config")
def get_config():
    return {
        "categories": ["Food", "Transport", "Shopping", "Bills", "Entertainment"],
        "currency": "usd",
        "startDate": 1
    }

