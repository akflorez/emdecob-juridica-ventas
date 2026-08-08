# -*- coding: utf-8 -*-
"""AUDITORIA COMPLETA DEL BACKEND"""
import sys
import os
import subprocess
import importlib

sys.stdout.reconfigure(encoding='utf-8')

print(f"Python: {sys.version}")

# Check packages
packages = [
    "fastapi", "uvicorn", "sqlalchemy", "pymysql", "pandas",
    "openpyxl", "requests", "bs4", "cryptography",
    "passlib", "pytz", "httpx", "psycopg2", "dotenv",
    "xlsxwriter", "itsdangerous", "sqladmin", "wtforms", "starlette",
    "fitz"
]

print("\n=== PACKAGES ===")
missing = []
for pkg in packages:
    try:
        importlib.import_module(pkg)
        print(f"  OK: {pkg}")
    except ImportError as e:
        print(f"  FALTA: {pkg} -> {e}")
        missing.append(pkg)

# DB connection
print("\n=== CONEXION DB ===")
try:
    os.environ.setdefault("DATABASE_URL", "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres")
    from sqlalchemy import create_engine, text
    url = os.environ["DATABASE_URL"]
    eng = create_engine(url, connect_args={"connect_timeout": 10})
    with eng.connect() as conn:
        row = conn.execute(text("SELECT current_database()")).fetchone()
        print(f"  OK: DB={row[0]}")
except Exception as e:
    print(f"  ERROR: {e}")

# Syntax check
print("\n=== SINTAXIS main.py ===")
result = subprocess.run(
    [sys.executable, "-m", "py_compile", "backend/main.py"],
    capture_output=True, text=True
)
if result.returncode == 0:
    print("  OK: Sintaxis correcta")
else:
    print(f"  ERROR: {result.stderr}")

# Full import test
print("\n=== IMPORT backend.main ===")
try:
    sys.path.insert(0, os.getcwd())
    import backend.main as app_module
    print("  OK: Import exitoso")
    print(f"  App: {app_module.app.title}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
