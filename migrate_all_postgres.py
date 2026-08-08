import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

DB_URL = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"

def run_migration():
    print(f"Connecting to Coolify PostgreSQL at 84.247.130.122:5438...")
    conn = psycopg2.connect(DB_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    print("1. Creating companies table...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(255) NOT NULL,
            nit VARCHAR(50),
            estado VARCHAR(50) DEFAULT 'activo',
            limite_usuarios INTEGER DEFAULT 5,
            plan_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    print("2. Inserting Default Company...")
    cur.execute("SELECT id FROM companies WHERE nombre = 'EMDECOB' OR nombre = 'Empresa Principal' LIMIT 1;")
    row = cur.fetchone()
    if not row:
        cur.execute("INSERT INTO companies (nombre, nit, estado) VALUES ('EMDECOB', '901234567-1', 'activo') RETURNING id;")
        default_company_id = cur.fetchone()[0]
        print(f"   Created EMDECOB company ID: {default_company_id}")
    else:
        default_company_id = row[0]
        print(f"   Existing default company ID: {default_company_id}")

    print("3. Creating roles & permissions tables...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS roles (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) UNIQUE NOT NULL,
            description VARCHAR(255)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) UNIQUE NOT NULL
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
            permission_id INTEGER REFERENCES permissions(id) ON DELETE CASCADE,
            PRIMARY KEY (role_id, permission_id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
            PRIMARY KEY (user_id, role_id)
        );
    """)

    # Insert default roles
    default_roles = [
        ("SUPERADMIN", "Super Administrador del Sistema"),
        ("COMPANY_ADMIN", "Administrador de Empresa"),
        ("LAWYER", "Abogado / Gestor Juridico"),
        ("OPERATOR", "Operador de Monitoreo")
    ]
    for r_name, r_desc in default_roles:
        cur.execute("INSERT INTO roles (name, description) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING;", (r_name, r_desc))

    print("4. Adding missing columns to users table...")
    user_columns = [
        ("email", "VARCHAR(255)"),
        ("role", "VARCHAR(50) DEFAULT 'LAWYER'"),
        ("cases_view_scope", "VARCHAR(50) DEFAULT 'ALL'"),
        ("company_id", f"INTEGER REFERENCES companies(id) ON DELETE SET NULL"),
        ("sync_with_clickup", "BOOLEAN DEFAULT true"),
        ("clickup_api_token", "VARCHAR(255)")
    ]
    for col_name, col_type in user_columns:
        cur.execute(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col_name} {col_type};")

    # Set company_id for existing users
    cur.execute("UPDATE users SET company_id = %s WHERE company_id IS NULL;", (default_company_id,))

    print("5. Adding missing columns to cases table...")
    case_columns = [
        ("company_id", f"INTEGER REFERENCES companies(id) ON DELETE CASCADE"),
        ("despacho", "VARCHAR(255)"),
        ("clase_proceso", "VARCHAR(255)"),
        ("tipo_proceso", "VARCHAR(255)"),
        ("estado", "VARCHAR(255)"),
        ("ponente_juez", "VARCHAR(255)"),
        ("departamento", "VARCHAR(255)"),
        ("municipio", "VARCHAR(255)"),
        ("ubicacion", "VARCHAR(255)"),
        ("fuente_encontrado", "VARCHAR(255)"),
        ("url_fuente", "VARCHAR(500)"),
        ("metodo_busqueda", "VARCHAR(255)"),
        ("confianza_busqueda", "INTEGER"),
        ("encontrado_en_fuente_alternativa", "BOOLEAN DEFAULT FALSE"),
        ("requiere_revision", "BOOLEAN DEFAULT FALSE"),
        ("sync_pub_status", "VARCHAR(100)"),
        ("sync_pub_progress", "INTEGER DEFAULT 0"),
        ("is_active", "BOOLEAN DEFAULT TRUE")
    ]
    for col_name, col_type in case_columns:
        cur.execute(f"ALTER TABLE cases ADD COLUMN IF NOT EXISTS {col_name} {col_type};")

    # Set company_id for existing cases
    cur.execute("UPDATE cases SET company_id = %s WHERE company_id IS NULL;", (default_company_id,))

    print("6. Creating SaaS billing, tasks, and auxiliary tables...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS billing_tiers (
            id SERIAL PRIMARY KEY,
            min_cases INTEGER NOT NULL,
            max_cases INTEGER,
            price FLOAT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS company_plans (
            id SERIAL PRIMARY KEY,
            company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE,
            plan_type VARCHAR(50) DEFAULT 'pro',
            total_active_cases INTEGER DEFAULT 0,
            monthly_fee FLOAT DEFAULT 0,
            billing_day INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            case_id INTEGER REFERENCES cases(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            description TEXT,
            status VARCHAR(50) DEFAULT 'pending',
            due_date TIMESTAMP,
            created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS task_assignees (
            task_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            PRIMARY KEY (task_id, user_id)
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            action VARCHAR(100) NOT NULL,
            details TEXT,
            ip_address VARCHAR(45),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            token VARCHAR(255) UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            used BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    print("Checking created tables...")
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public';")
    tables = [t[0] for t in cur.fetchall()]
    print(f"Total tables in PostgreSQL: {len(tables)} -> {sorted(tables)}")

    cur.close()
    conn.close()
    print("MIGRATION COMPLETED SUCCESSFULLY!")

if __name__ == "__main__":
    run_migration()
