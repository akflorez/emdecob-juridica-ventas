import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy.schema import CreateTable
from backend.db import engine, Base
from backend.models import *

DB_URL = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"

def sync():
    print("Conectando a PostgreSQL de produccion...")
    conn = psycopg2.connect(DB_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # 1. Crear todas las tablas que falten
    Base.metadata.create_all(bind=engine)
    print("create_all() completado.")

    # 2. Sincronizar columnas faltantes en tablas existentes
    for table_name, table in Base.metadata.tables.items():
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s;
        """, (table_name,))
        existing_cols = {row[0] for row in cur.fetchall()}

        for col in table.columns:
            if col.name not in existing_cols:
                # Determinar tipo SQL
                col_type = col.type.compile(engine.dialect)
                print(f"Agregando columna faltante: {table_name}.{col.name} ({col_type})")
                try:
                    cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type};")
                except Exception as e:
                    print(f"Error agregando {table_name}.{col.name}: {e}")

    cur.close()
    conn.close()
    print("Sincronizacion completa exitosa!")

if __name__ == "__main__":
    sync()
