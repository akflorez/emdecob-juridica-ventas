from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    print("=== 33 VALIDATED CASES IN DB (juzgado is not null) ===")
    val_cases = conn.execute(text("""
        SELECT id, radicado, demandante, demandado, abogado, cedula, juzgado 
        FROM cases 
        WHERE juzgado IS NOT NULL;
    """)).fetchall()
    for vc in val_cases:
        print(vc)

    print("\n=== ALL LAWYERS IN DB ===")
    lawyers = conn.execute(text("""
        SELECT DISTINCT abogado, count(*) 
        FROM cases 
        GROUP BY abogado 
        ORDER BY count(*) DESC;
    """)).fetchall()
    for l in lawyers:
        print(l)
