from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
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
#models.Base.metadata.drop_all(bind=engine)
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

@app.get("/login", response_class=HTMLResponse)
def get_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request})

@app.get("/register", response_class=HTMLResponse)
def get_register(request: Request):
    return templates.TemplateResponse(request=request, name="register.html", context={"request": request})

@app.get("/")
def render_dashboard(request: Request):
    # Trả về trang index.html
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/history")
def render_history(request: Request):
    return templates.TemplateResponse(request=request, name="history.html")

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

