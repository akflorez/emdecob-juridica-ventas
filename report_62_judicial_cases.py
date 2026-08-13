from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    # 1. Judicial cases validated in Rama Judicial (not SIC)
    rama_valid = conn.execute(text("""
        SELECT id, radicado, demandante, demandado, juzgado, ultima_actuacion
        FROM cases
        WHERE company_id = 3 AND (juzgado != 'SIC' AND (fuente_encontrado != 'SIC' OR fuente_encontrado IS NULL))
        ORDER BY id;
    """)).fetchall()
    
    print(f"=== CASOS JUDICIALES DE JUZGADOS VALIDADOS ({len(rama_valid)}) ===")
    for c in rama_valid:
        print(f"  [{c[1]}] {c[2]} VS {c[3]} | Juzgado: {c[4]} | Últ. Act: {c[5]}")

    # 2. Judicial cases pending in Rama Judicial
    rama_pending = conn.execute(text("""
        SELECT id, radicado, demandante, demandado, created_at
        FROM cases
        WHERE company_id = 3 AND juzgado IS NULL
        ORDER BY id;
    """)).fetchall()
    print(f"\n=== CASOS JUDICIALES PENDIENTES ({len(rama_pending)}) ===")
    for p in rama_pending:
        print(f"  [{p[1]}] {p[2] or 'Sin demandante'} VS {p[3] or 'Sin demandado'}")

    # 3. Judicial cases in No Encontrados
    invalids = conn.execute(text("""
        SELECT id, radicado, motivo, intentos, updated_at
        FROM invalid_radicados
        WHERE company_id = 3
        ORDER BY id;
    """)).fetchall()
    print(f"\n=== CASOS EN 'NO ENCONTRADOS' ({len(invalids)}) ===")
    for inv in invalids:
        print(f"  [{inv[1]}] Intentos: {inv[3]} | Motivo: {inv[2]}")
