from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    print("=== CASES IN DB RIGHT NOW ===")
    cases = conn.execute(text("SELECT id, radicado, demandante, demandado, abogado, cedula, created_at FROM cases WHERE company_id = 3 ORDER BY id DESC;")).fetchall()
    print(f"Total casos en DB para Aventuramotors: {len(cases)}")
    
    print("\n=== REPEATED RADICADOS ===")
    repeated = conn.execute(text("""
        SELECT radicado, count(*) 
        FROM cases 
        WHERE company_id = 3 
        GROUP BY radicado 
        HAVING count(*) > 1;
    """)).fetchall()
    print(f"Radicados repetidos: {len(repeated)}")
    for r in repeated[:10]:
        print("  -", r)

    print("\n=== DISTINCT RADICADOS ===")
    distinct_count = conn.execute(text("SELECT count(DISTINCT radicado) FROM cases WHERE company_id = 3;")).fetchone()
    print(f"Radicados únicos: {distinct_count[0]}")
    
    print("\n=== ALL RADICADOS LIST (first 20) ===")
    for c in cases[:20]:
        print(c)
