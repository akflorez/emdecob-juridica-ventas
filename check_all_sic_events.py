from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    sic_cases = conn.execute(text("""
        SELECT c.id, c.radicado, c.demandante, c.cedula, c.estado, count(e.id) as total_actuaciones
        FROM cases c
        LEFT JOIN case_events e ON e.case_id = c.id
        WHERE c.juzgado = 'SIC' OR c.fuente_encontrado = 'SIC'
        GROUP BY c.id, c.radicado, c.demandante, c.cedula, c.estado
        ORDER BY c.id;
    """)).fetchall()
    
    print(f"=== TOTAL CASOS SIC EN BD ({len(sic_cases)}) ===")
    for sc in sic_cases:
        print(f"ID: {sc[0]} | Radicado: {sc[1]} | Cédula: {sc[3]} | Actuaciones: {sc[5]} | Estado: {sc[4]}")
