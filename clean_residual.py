from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    # Delete case 2441 or any case with FONDO
    conn.execute(text("DELETE FROM case_events WHERE case_id IN (SELECT id FROM cases WHERE demandante ILIKE '%FONDO%');"))
    conn.execute(text("DELETE FROM case_publications WHERE case_id IN (SELECT id FROM cases WHERE demandante ILIKE '%FONDO%');"))
    conn.execute(text("DELETE FROM cases WHERE demandante ILIKE '%FONDO%';"))
    conn.commit()
    print("Eliminados casos residuales del Fondo.")
