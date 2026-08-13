from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    # 1. Total cases in cases table for company_id = 3
    cases = conn.execute(text("""
        SELECT id, radicado, demandante, demandado, juzgado, is_active, last_check_at, created_at
        FROM cases
        WHERE company_id = 3
        ORDER BY id;
    """)).fetchall()
    
    print(f"=== TOTAL CASOS EN 'cases' (company_id=3): {len(cases)} ===")
    juzgado_not_null = [c for c in cases if c[4] is not None]
    juzgado_is_null = [c for c in cases if c[4] is None]
    print(f"  * Con juzgado (Validados): {len(juzgado_not_null)}")
    print(f"  * Sin juzgado (Pendientes de validar): {len(juzgado_is_null)}")
    
    # 2. Total invalid_radicados for company_id = 3
    invalids = conn.execute(text("""
        SELECT id, radicado, motivo, intentos, updated_at
        FROM invalid_radicados
        WHERE company_id = 3
        ORDER BY id;
    """)).fetchall()
    print(f"\n=== TOTAL INVALID_RADICADOS (company_id=3): {len(invalids)} ===")
    for inv in invalids[:15]:
        print(f"  [{inv[0]}] Radicado: {inv[1]} | Intentos: {inv[3]} | Motivo: {inv[2]}")
    if len(invalids) > 15:
        print(f"  ... y {len(invalids)-15} más.")

    # 3. Check cases in other companies or without company_id
    other_cases = conn.execute(text("""
        SELECT company_id, count(*) 
        FROM cases 
        GROUP BY company_id;
    """)).fetchall()
    print(f"\n=== CASOS POR EMPRESA ===")
    for oc in other_cases:
        print(f"  Company ID: {oc[0]} -> {oc[1]} casos")

    other_inv = conn.execute(text("""
        SELECT company_id, count(*) 
        FROM invalid_radicados 
        GROUP BY company_id;
    """)).fetchall()
    print(f"\n=== INVALID_RADICADOS POR EMPRESA ===")
    for oi in other_inv:
        print(f"  Company ID: {oi[0]} -> {oi[1]} invalidos")
