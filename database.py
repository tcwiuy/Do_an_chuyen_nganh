from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Tạm thời dùng SQLite để test dễ dàng giống file JSON của tác giả, 
# sau này chuyển sang PostgreSQL chỉ cần đổi chuỗi URL này.
SQLALCHEMY_DATABASE_URL = "sqlite:///./expenseowl.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency để lấy database session cho từng request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()