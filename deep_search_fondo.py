from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    print("=== SEARCHING 'FONDO' IN ALL TABLES ===")
    
    # 1. Cases table: search any column containing FONDO or FNA
    cases_matches = conn.execute(text("""
        SELECT id, radicado, demandante, demandado, company_id, user_id
        FROM cases
        WHERE demandante ILIKE '%FONDO%' 
           OR demandado ILIKE '%FONDO%' 
           OR alias ILIKE '%FONDO%'
           OR juzgado ILIKE '%FONDO%'
           OR abogado ILIKE '%FONDO%';
    """)).fetchall()
    print(f"Cases table matches: {len(cases_matches)}")
    for cm in cases_matches:
        print("  -", cm)

    # 2. Check total cases in DB by company_id
    total_cases = conn.execute(text("SELECT company_id, count(*) FROM cases GROUP BY company_id;")).fetchall()
    print("\nTotal cases by company_id:", total_cases)

    # 3. Check what Diego Rincon's user sees when calling /cases API query!
    # Diego Rincon user_id = 5, company_id = 3, is_admin = True, is_superadmin = False, role = 'COMPANY_ADMIN'
    print("\n=== USER 5 DETAILS ===")
    u5 = conn.execute(text("SELECT id, username, email, role, is_admin, is_superadmin, company_id FROM users WHERE id = 5;")).fetchall()
    print(u5)

    # 4. Check case_publications or other tables
    pubs = conn.execute(text("SELECT count(*) FROM case_publications WHERE texto_fuente_principal ILIKE '%FONDO%' OR observacion ILIKE '%FONDO%';")).fetchone()
    print(f"\nPublications with 'FONDO': {pubs[0]}")

    # 5. Check invalid_radicados
    invs = conn.execute(text("SELECT id, radicado, demandante, company_id FROM invalid_radicados WHERE demandante ILIKE '%FONDO%';")).fetchall()
    print(f"\nInvalid radicados with 'FONDO': {len(invs)}")
    for inv in invs:
        print("  -", inv)
