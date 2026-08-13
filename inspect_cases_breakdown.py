from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    print("=== TOTAL CASES BY COMPANY & DEMANDANTE ===")
    rows = conn.execute(text("""
        SELECT company_id, demandante, count(*) 
        FROM cases 
        GROUP BY company_id, demandante 
        ORDER BY company_id, count(*) DESC 
        LIMIT 30;
    """)).fetchall()
    for r in rows:
        print(r)
