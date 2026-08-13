from sqlalchemy import create_engine, text
from backend.models import InvalidRadicado

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    # 1. Count invalid_radicados
    invalids = conn.execute(text("SELECT id, radicado, company_id FROM invalid_radicados WHERE company_id = 3;")).fetchall()
    print(f"Total invalid_radicados for company 3: {len(invalids)}")
    
    # 2. Check foreign keys or constraints pointing to invalid_radicados
    fk_constraints = conn.execute(text("""
        SELECT
            tc.table_schema, 
            tc.constraint_name, 
            tc.table_name, 
            kcu.column_name, 
            ccu.table_schema AS foreign_table_schema,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name 
        FROM 
            information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
              AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
              AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY' AND ccu.table_name='invalid_radicados';
    """)).fetchall()
    print("Foreign keys pointing to invalid_radicados:", fk_constraints)
