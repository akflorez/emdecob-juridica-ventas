from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    demo_cases = conn.execute(text("""
        SELECT id, radicado, demandante, demandado, juzgado, fuente_encontrado
        FROM cases 
        WHERE demandante ILIKE '%Demo%' OR demandado ILIKE '%Demo%' OR juzgado ILIKE '%Juzgado Administrativo de Despacho%';
    """)).fetchall()
    print(f"Total casos con datos Demo: {len(demo_cases)}")
    for c in demo_cases:
        events = conn.execute(text(f"SELECT id, event_date, title, detail FROM case_events WHERE case_id = {c[0]};")).fetchall()
        print(f"\nCaso {c[0]} (Radicado: {c[1]} | Demandante: {c[2]} | Juzgado: {c[4]}): {len(events)} actuaciones:")
        for ev in events:
            print("  ->", ev)
