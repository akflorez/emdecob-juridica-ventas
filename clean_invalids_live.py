from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    res = conn.execute(text("DELETE FROM invalid_radicados WHERE company_id = 3;"))
    conn.commit()
    print(f"Deleted {res.rowcount} invalid_radicados for company_id = 3 from the live database!")
