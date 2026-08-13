from sqlalchemy import create_engine, text

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)

with engine.connect() as conn:
    print("=== CASES TABLE COLUMNS ===")
    cols = conn.execute(text("""
        SELECT column_name, data_type, is_nullable, column_default 
        FROM information_schema.columns 
        WHERE table_name = 'cases'
        ORDER BY ordinal_position;
    """)).fetchall()
    for col in cols:
        print(col)

    print("\n=== CASES TABLE CONSTRAINTS & FKs ===")
    cons = conn.execute(text("""
        SELECT conname, contype, pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE conrelid = 'cases'::regclass;
    """)).fetchall()
    for con in cons:
        print(con)

    print("\n=== CASES TABLE SEQUENCES ===")
    seqs = conn.execute(text("""
        SELECT pg_get_serial_sequence('cases', 'id');
    """)).fetchall()
    print("Sequence:", seqs)
    
    # Try inserting a single test case to see the exact SQL error!
    print("\n=== TESTING TEST CASE INSERTION ===")
    try:
        conn.execute(text("""
            INSERT INTO cases (radicado, abogado, user_id, company_id, is_active)
            VALUES ('TEST_RADICADO_999', 'TEST ABOGADO', 5, 3, true)
            RETURNING id;
        """))
        conn.commit()
        print("Insert succeeded!")
        # Clean up test row
        conn.execute(text("DELETE FROM cases WHERE radicado = 'TEST_RADICADO_999'"))
        conn.commit()
    except Exception as e:
        print("Insert FAILED with error:", e)
