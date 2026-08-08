import os
from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

raw_url = os.getenv("DATABASE_URL") or os.getenv("NEON_URL") or ""

def get_connection_url(url_str):
    if not url_str:
        return "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"

    clean_url = url_str.replace("${DB_USER:-emdecob}", "emdecob")
    clean_url = clean_url.replace("${DB_PASSWORD:-emdecob2026}", "emdecob2026")

    if clean_url.startswith("postgres://"):
        clean_url = clean_url.replace("postgres://", "postgresql://", 1)

    return clean_url

DATABASE_URL = get_connection_url(raw_url)

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=5,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10},  # TCP timeout: never hang at startup
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()