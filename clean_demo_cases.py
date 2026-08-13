from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    # 1. Find the 9 cases with Demandante Demo
    demo_cases = conn.execute(text("""
        SELECT id, radicado, demandante, demandado, juzgado, abogado 
        FROM cases 
        WHERE demandante = 'Demandante Demo' OR demandado = 'Demandado Demo';
    """)).fetchall()
    print(f"Encontrados {len(demo_cases)} casos con datos Demo:")
    for dc in demo_cases:
        print("  -", dc)

    # 2. Reset those demo fields back to NULL
    if demo_cases:
        conn.execute(text("""
            UPDATE cases 
            SET demandante = NULL, demandado = NULL, juzgado = NULL, despacho = NULL, fuente_encontrado = NULL, metodo_busqueda = NULL
            WHERE demandante = 'Demandante Demo' OR demandado = 'Demandado Demo';
        """))
        conn.commit()
        print(f"¡Limpiados exitosamente los {len(demo_cases)} casos en la base de datos!")
