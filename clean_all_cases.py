from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    print("=== PURGING ALL CASES FOR COMPANY_ID = 3 (Aventuramotors) ===")
    
    # 1. Get all case IDs for company 3
    cases = conn.execute(text("SELECT id FROM cases WHERE company_id = 3")).fetchall()
    case_ids = [c[0] for c in cases]
    print(f"Total casos a eliminar en Aventuramotors: {len(case_ids)}")
    
    if case_ids:
        # Delete dependencies
        conn.execute(text("DELETE FROM case_events WHERE case_id IN (SELECT id FROM cases WHERE company_id = 3);"))
        conn.execute(text("DELETE FROM case_publications WHERE case_id IN (SELECT id FROM cases WHERE company_id = 3);"))
        conn.execute(text("DELETE FROM tasks WHERE company_id = 3 OR case_id IN (SELECT id FROM cases WHERE company_id = 3);"))
        conn.execute(text("DELETE FROM case_search_source_results WHERE company_id = 3;"))
        conn.execute(text("DELETE FROM invalid_radicados WHERE company_id = 3;"))
        conn.execute(text("DELETE FROM excel_import_jobs WHERE company_id = 3;"))
        conn.execute(text("DELETE FROM publicaciones_sync_jobs WHERE company_id = 3;"))
        
        # Delete cases
        deleted_count = conn.execute(text("DELETE FROM cases WHERE company_id = 3;")).rowcount
        conn.commit()
        print(f"¡Casos eliminados exitosamente: {deleted_count}!")

    # Verify total cases left in database
    total_left = conn.execute(text("SELECT company_id, count(*) FROM cases GROUP BY company_id;")).fetchall()
    print("\nEstado final de casos por empresa en DB:", total_left)
