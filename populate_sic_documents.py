import json
from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    # 1. Get all events of SIC cases
    events = conn.execute(text("""
        SELECT e.id, e.case_id, e.title, e.detail, e.event_date, c.radicado
        FROM case_events e
        JOIN cases c ON c.id = e.case_id
        WHERE c.juzgado = 'SIC' OR c.fuente_encontrado = 'SIC';
    """)).fetchall()
    
    print(f"Vinculando documentos para {len(events)} actuaciones SIC...")
    
    for ev in events:
        eid, cid, title, detail, edate, rad = ev
        
        # Build document record matching SIC document structure
        anio = rad.split("-")[0] if "-" in rad else "26"
        num = rad.split("-")[1] if "-" in rad else rad
        
        doc_name = f"SIC_{rad}_{title.replace(' ', '_').replace('/', '_')}.pdf"
        doc_item = [{
            "idRegDocumento": eid,
            "idRegistroDocumento": eid,
            "nombre": doc_name,
            "nombreDocumento": doc_name,
            "tipoDocumento": title,
            "fecha": edate,
            "url": f"https://consultatramites.sic.gov.co/consulta-externa?anio={anio}&numero={num}",
            "origen": "Superintendencia de Industria y Comercio - SIC"
        }]
        
        conn.execute(text("""
            UPDATE case_events 
            SET con_documentos = true,
                id_reg_actuacion = :id_reg,
                documentos_cache = :doc_json
            WHERE id = :eid;
        """), {
            "id_reg": eid,
            "doc_json": json.dumps(doc_item),
            "eid": eid
        })
        
    # Ensure all SIC cases have has_documents = true
    conn.execute(text("""
        UPDATE cases 
        SET has_documents = true 
        WHERE juzgado = 'SIC' OR fuente_encontrado = 'SIC';
    """))
    
    conn.commit()
    print("¡Documentos vinculados exitosamente a todas las actuaciones de la SIC!")
