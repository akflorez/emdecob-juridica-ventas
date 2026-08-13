from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    # 1. Check how many FONDO cases exist
    fondo_cases = conn.execute(text("SELECT id, radicado, demandante, company_id FROM cases WHERE demandante ILIKE '%FONDO%'")).fetchall()
    print(f"Encontrados {len(fondo_cases)} casos del FONDO para eliminar:")
    for fc in fondo_cases[:5]:
        print("  -", fc)

    # 2. Delete related records first
    case_ids = [fc[0] for fc in fondo_cases]
    if case_ids:
        case_ids_str = ",".join(str(cid) for cid in case_ids)
        conn.execute(text(f"DELETE FROM case_events WHERE case_id IN ({case_ids_str})"))
        conn.execute(text(f"DELETE FROM case_publications WHERE case_id IN ({case_ids_str})"))
        conn.execute(text(f"DELETE FROM tasks WHERE case_id IN ({case_ids_str})"))
        conn.execute(text(f"DELETE FROM case_search_source_results WHERE case_id IN ({case_ids_str})"))
        conn.execute(text(f"DELETE FROM cases WHERE id IN ({case_ids_str})"))
        conn.commit()
        print(f"¡Eliminados exitosamente los {len(case_ids)} casos del FONDO y sus dependencias!")

    # 3. Check remaining cases for Aventuramotors (company_id=3)
    remaining = conn.execute(text("""
        SELECT demandante, count(*) 
        FROM cases 
        WHERE company_id = 3 
        GROUP BY demandante 
        ORDER BY count(*) DESC;
    """)).fetchall()
    print("\nCasos restantes en Aventuramotors (company_id=3):")
    for r in remaining:
        print("  -", r)
