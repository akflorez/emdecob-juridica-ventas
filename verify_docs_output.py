import json
from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    events = conn.execute(text("""
        SELECT e.id, e.title, e.event_date, e.con_documentos, e.id_reg_actuacion, e.documentos_cache, c.radicado
        FROM case_events e
        JOIN cases c ON c.id = e.case_id
        WHERE c.radicado = '26-64018';
    """)).fetchall()
    
    print(f"Actuaciones para caso 26-64018 ({len(events)}):")
    for ev in events:
        docs = json.loads(ev[5]) if ev[5] else []
        print(f"  - [{ev[2]}] {ev[1]} | Docs: {ev[3]} | Total archivos adjuntos: {len(docs)}")
        for d in docs:
            print(f"     -> Archivo: {d.get('nombre')} | URL: {d.get('url')}")
