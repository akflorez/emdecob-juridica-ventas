from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    case = conn.execute(text("SELECT id, radicado, company_id FROM cases WHERE radicado = '26-64018';")).fetchone()
    if not case:
        print("Caso 26-64018 no encontrado")
        exit(1)
        
    case_id = case[0]
    radicado = case[1]
    company_id = case[2] or 3
    print(f"Poblando actuaciones oficiales SIC para caso id={case_id} (radicado={radicado}, company_id={company_id})...")
    
    actuaciones_sic = [
        {
            "fecha": "2026-03-16",
            "title": "DECISION - TRASLADO SECRETARIA GENERAL",
            "detail": "Trámite: DEMANDA PROTECCIÓN CONSUMIDOR JURISDICCIONAL | Tipo: TR | Destinatario: PEDRO ALEJANDRO NIÑO ROA, DECISION AUTO No. 28427 de Fecha 2026-03-13",
            "hash": "sic_26_64018_4"
        },
        {
            "fecha": "2026-03-13",
            "title": "CERTIFICADO / RUES",
            "detail": "Trámite: DEMANDA PROTECCIÓN CONSUMIDOR JURISDICCIONAL | Tipo: SA | Destinatario: GRUPO DE TRABAJO DE SECRETARIA",
            "hash": "sic_26_64018_3"
        },
        {
            "fecha": "2026-03-12",
            "title": "EXPEDIENTE INGRESÓ AL DESPACHO",
            "detail": "Trámite: DEMANDA PROTECCIÓN CONSUMIDOR JURISDICCIONAL | Tipo: SA | Destinatario: GRUPO DE TRABAJO DE SECRETARIA",
            "hash": "sic_26_64018_2"
        },
        {
            "fecha": "2026-02-26",
            "title": "MEMORIAL",
            "detail": "Trámite: DEMANDA PROTECCIÓN CONSUMIDOR JURISDICCIONAL | Tipo: EN | Solicitante: ERICA YOHANA RAMIREZ PEREA",
            "hash": "sic_26_64018_1"
        },
        {
            "fecha": "2026-02-20",
            "title": "PRESENTACION",
            "detail": "Trámite: DEMANDA PROTECCIÓN CONSUMIDOR JURISDICCIONAL | Tipo: EN | Solicitante: ERICA YOHANA RAMIREZ PEREA",
            "hash": "sic_26_64018_0"
        }
    ]
    
    conn.execute(text(f"DELETE FROM case_events WHERE case_id = {case_id};"))
    
    for act in actuaciones_sic:
        conn.execute(text("""
            INSERT INTO case_events (case_id, company_id, event_date, title, detail, event_hash, con_documentos, created_at)
            VALUES (:cid, :comp_id, :edate, :title, :detail, :ehash, true, now());
        """), {
            "cid": case_id,
            "comp_id": company_id,
            "edate": act["fecha"],
            "title": act["title"],
            "detail": act["detail"],
            "ehash": act["hash"]
        })
        
    conn.execute(text("""
        UPDATE cases 
        SET fecha_radicacion = '2026-02-20',
            ultima_actuacion = '2026-03-16',
            has_documents = true,
            juzgado = 'SIC',
            despacho = 'Superintendencia de Industria y Comercio - SIC',
            tipo_proceso = 'Demanda Protección al Consumidor Jurisdiccional'
        WHERE id = :cid;
    """), {"cid": case_id})
    
    conn.commit()
    print("¡5 Actuaciones SIC registradas y fechas actualizadas correctamente!")

    events = conn.execute(text(f"SELECT id, event_date, title, detail FROM case_events WHERE case_id = {case_id} ORDER BY event_date DESC;")).fetchall()
    print(f"\nActuaciones en BD para caso {case_id} ({len(events)}):")
    for ev in events:
        print("  *", ev)
