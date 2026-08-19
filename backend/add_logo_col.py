import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

raw_url = os.getenv("DATABASE_URL") or os.getenv("NEON_URL") or "postgresql://emdecob:emdecob2026@localhost:5432/juricob"
if raw_url and raw_url.startswith("postgres://"):
    raw_url = raw_url.replace("postgres://", "postgresql://", 1)

try:
    engine = create_engine(raw_url)
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE companies ADD COLUMN logo_base64 TEXT;"))
        conn.commit()
    print("Column logo_base64 added successfully.")
except Exception as e:
    print(f"Error (maybe column already exists): {e}")
