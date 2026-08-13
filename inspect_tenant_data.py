from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    print("=== COMPANIES ===")
    companies = conn.execute(text("SELECT id, nombre, nit FROM companies;")).fetchall()
    for c in companies:
        print(c)

    print("\n=== USERS ===")
    users = conn.execute(text("SELECT id, username, email, role, is_admin, is_superadmin, company_id FROM users;")).fetchall()
    for u in users:
        print(u)

    print("\n=== CASES DISTRIBUTION BY COMPANY_ID ===")
    case_counts = conn.execute(text("SELECT company_id, count(*), count(CASE WHEN demandante LIKE '%FONDO%' THEN 1 END) as fondo_cases FROM cases GROUP BY company_id;")).fetchall()
    for cc in case_counts:
        print(cc)

    print("\n=== SAMPLE CASES WITH 'FONDO' IN DEMANDANTE ===")
    fondo_samples = conn.execute(text("SELECT id, radicado, demandante, company_id, user_id FROM cases WHERE demandante LIKE '%FONDO%' LIMIT 10;")).fetchall()
    for fs in fondo_samples:
        print(fs)

    print("\n=== SAMPLE CASES FOR COMPANY_ID = 3 ===")
    c3_samples = conn.execute(text("SELECT id, radicado, demandante, company_id, user_id FROM cases WHERE company_id = 3 LIMIT 10;")).fetchall()
    for c3 in c3_samples:
        print(c3)
