from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import models
from database import engine
from routers import router as expenses_router, recurring_router, auth_router, ai_router
from routers import config_router
import routers
import uvicorn
from dotenv import load_dotenv
load_dotenv()

# Tạo bảng trong CSDL
#models.Base.metadata.drop_all(bind=engine)
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ExpenseOwl Python API")

@app.get("/health", tags=["Health Check"])
async def health_check():
    """
    Endpoint siêu nhẹ dùng để Render không bị sleep.
    Không gọi Database, không xử lý logic.
    """
    return {"status": "ok", "message": "Server is awake!"}

# 1. Cấu hình phục vụ file tĩnh (CSS, JS, Ảnh) ở đường dẫn /static/
app.mount("/static", StaticFiles(directory="static"), name="static")

# 2. Cấu hình thư mục chứa giao diện HTML
templates = Jinja2Templates(directory="templates")



# Nhúng API router
app.include_router(expenses_router)
app.include_router(recurring_router)
app.include_router(auth_router)
app.include_router(ai_router)
app.include_router(routers.planning_router)
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
@app.get("/index")
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

@app.get("/trends", response_class=HTMLResponse)
def render_trends(request: Request):
    return templates.TemplateResponse(request=request, name="trend.html")


@app.get("/planning", response_class=HTMLResponse)
async def read_planning(request: Request):
    return templates.TemplateResponse(request=request, name="planning.html")

# Mở trang Quên mật khẩu
@app.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse(request=request, name="forgot_password.html")

# Mở trang Đăng ký
@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request=request, name="register.html")
@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    # Đưa request ra ngoài làm tham số riêng
    return templates.TemplateResponse(request, "profile.html", {"request": request})

if __name__ == "__main__":
    # Đặt reload=True để server tự khởi động lại khi bạn sửa code
    uvicorn.run("main:app", host="127.0.0.1", port=8001, reload=True)