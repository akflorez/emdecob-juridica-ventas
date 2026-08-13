from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    # 1. Delete all fake demo events from case_events
    deleted_events = conn.execute(text("""
        DELETE FROM case_events 
        WHERE title = 'Auto de publicación de estado' 
           OR detail = 'Notificación por estado electrónico';
    """)).rowcount
    print(f"Eliminadas {deleted_events} actuaciones ficticias (demo).")

    # 2. Reset the 5 cases back to clean state
    updated_cases = conn.execute(text("""
        UPDATE cases 
        SET demandante = NULL, 
            demandado = NULL, 
            juzgado = NULL, 
            despacho = NULL, 
            fuente_encontrado = NULL, 
            metodo_busqueda = NULL, 
            ultima_actuacion = NULL,
            last_hash = NULL,
            current_hash = NULL
        WHERE demandante ILIKE '%Demo%' 
           OR demandado ILIKE '%Demo%' 
           OR juzgado ILIKE '%Juzgado Administrativo de Despacho%';
    """)).rowcount
    print(f"Limpiados {updated_cases} casos que tenían datos Demo.")
    
    # 3. Clean any fake search source results
    conn.execute(text("""
        DELETE FROM case_search_source_results 
        WHERE mensaje ILIKE '%Demo%' OR datos_extraidos_json ILIKE '%Demo%';
    """))
    conn.commit()
    print("¡Base de datos limpiada y sincronizada al 100%!")

    # 4. Verify valid cases left
    val_cases = conn.execute(text("""
        SELECT id, radicado, demandante, demandado, juzgado, ultima_actuacion 
        FROM cases 
        WHERE juzgado IS NOT NULL;
    """)).fetchall()
    print(f"\nCasos validados reales actuales ({len(val_cases)}):")
    for vc in val_cases:
        print("  -", vc)
