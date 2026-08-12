import os
import asyncio
from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Depends,
    HTTPException,
    Query,
    BackgroundTasks,
    Body,
    Security,
    Request,
    Header,
    Response,
)
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, sessionmaker, joinedload, selectinload
from sqlalchemy import create_engine, or_, desc, and_, case as sql_case, func

# In-memory rate limiting dictionary for password recovery
# Format: { "email:user@example.com:timestamp_window": count, "ip:127.0.0.1:timestamp_window": count }
RATE_LIMIT_STORE = {}

def check_password_reset_rate_limit(email: str, ip: str) -> bool:
    import time
    now = time.time()
    # 15 minutes window = 900 seconds
    window = int(now / 900) * 900
    
    email_key = f"email:{email.strip().lower()}:{window}"
    ip_key = f"ip:{ip}:{window}"
    
    email_count = RATE_LIMIT_STORE.get(email_key, 0)
    ip_count = RATE_LIMIT_STORE.get(ip_key, 0)
    
    if email_count >= 3 or ip_count >= 10:
        return False
        
    RATE_LIMIT_STORE[email_key] = email_count + 1
    RATE_LIMIT_STORE[ip_key] = ip_count + 1
    
    # Simple clean up of expired keys (> 1 hour old) to prevent memory leak
    for k in list(RATE_LIMIT_STORE.keys()):
        try:
            parts = k.split(':')
            k_window = int(parts[-1])
            if now - k_window > 3600:
                RATE_LIMIT_STORE.pop(k, None)
        except Exception:
            pass
            
    return True


# IMPORTACION ADAPTATIVA (Expert Mode)
try:
    from backend.db import engine, SessionLocal, Base
except ImportError:
    try:
        from .db import engine, SessionLocal, Base
    except ImportError:
        import db
        engine = db.engine
        SessionLocal = db.SessionLocal
        Base = db.Base

# MIGRACIONES AUTOMATICAS RAPIDAS
from sqlalchemy import text

def try_execute(conn, sql):
    try:
        conn.execute(text(sql))
    except Exception as e:
        print(f"Migración fallida ({sql}): {e}")

try:
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
        # Migraciones SaaS
        try_execute(conn, """
            CREATE TABLE IF NOT EXISTS companies (
                id SERIAL PRIMARY KEY,
                nombre VARCHAR(255) NOT NULL,
                nit VARCHAR(50),
                estado VARCHAR(50) DEFAULT 'activo',
                limite_usuarios INTEGER DEFAULT 5,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        try_execute(conn, """
            INSERT INTO companies (id, nombre) 
            SELECT 1, 'Empresa Default' 
            WHERE NOT EXISTS (SELECT 1 FROM companies WHERE id = 1)
        """)

        # Tareas
        try_execute(conn, "ALTER TABLE task_comments ADD COLUMN IF NOT EXISTS user_name VARCHAR(255)")
        try_execute(conn, "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS clickup_id VARCHAR(100)")
        try_execute(conn, "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS assignee_name VARCHAR(200)")
        try_execute(conn, "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS custom_fields TEXT")
        
        # General
        try_execute(conn, "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id INTEGER")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS company_id INTEGER")
        try_execute(conn, "ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS company_id INTEGER")
        
        # Opcional, si audit_logs no existe, fallará silenciosamente sin afectar al resto
        try_execute(conn, "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS company_id INTEGER")
        
        # Migraciones para Documentos Judiciales
        try_execute(conn, "ALTER TABLE case_events ADD COLUMN IF NOT EXISTS id_reg_actuacion BIGINT")
        try_execute(conn, "ALTER TABLE case_events ADD COLUMN IF NOT EXISTS cons_actuacion BIGINT")
        try_execute(conn, "ALTER TABLE case_events ADD COLUMN IF NOT EXISTS documentos_cache TEXT")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS sync_pub_status VARCHAR(100)")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS sync_pub_progress INTEGER DEFAULT 0")
        
        # Migraciones para Publicaciones
        try_execute(conn, "ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS mes_busqueda VARCHAR(20)")
        try_execute(conn, "ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS prioridad INTEGER DEFAULT 0")
        
        # Fallback search migrations
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS despacho VARCHAR(255)")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS clase_proceso VARCHAR(255)")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS tipo_proceso VARCHAR(255)")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS estado VARCHAR(255)")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS ponente_juez VARCHAR(255)")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS departamento VARCHAR(255)")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS municipio VARCHAR(255)")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS ubicacion VARCHAR(255)")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS fuente_encontrado VARCHAR(255)")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS url_fuente VARCHAR(500)")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS metodo_busqueda VARCHAR(255)")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS confianza_busqueda INTEGER")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS encontrado_en_fuente_alternativa BOOLEAN DEFAULT FALSE")
        try_execute(conn, "ALTER TABLE cases ADD COLUMN IF NOT EXISTS requiere_revision BOOLEAN DEFAULT FALSE")

        try_execute(conn, """
            CREATE TABLE IF NOT EXISTS case_search_source_results (
                id SERIAL PRIMARY KEY,
                case_id INTEGER,
                company_id INTEGER,
                radicado VARCHAR(60) NOT NULL,
                fuente VARCHAR(100),
                tipo_fuente VARCHAR(100),
                url VARCHAR(500),
                encontrado BOOLEAN DEFAULT FALSE NOT NULL,
                confianza INTEGER DEFAULT 0,
                estado VARCHAR(50),
                mensaje TEXT,
                datos_extraidos_json TEXT,
                raw_response VARCHAR(50000),
                error_type VARCHAR(100),
                http_status INTEGER,
                duration_ms INTEGER DEFAULT 0,
                source_order INTEGER,
                force BOOLEAN DEFAULT FALSE,
                requiere_revision BOOLEAN DEFAULT FALSE,
                created_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # TABLA DE LOGS PARA DEBUG
        try_execute(conn, """
            CREATE TABLE IF NOT EXISTS sync_debug_logs (
                id SERIAL PRIMARY KEY,
                case_id INTEGER,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # INDICE PARA VELOCIDAD Y COMPATIBILIDAD SAAS
        try_execute(conn, "CREATE INDEX IF NOT EXISTS idx_case_pub_case_id ON case_publications(case_id)")
        try_execute(conn, "CREATE INDEX IF NOT EXISTS idx_case_event_case_id ON case_events(case_id)")
        try_execute(conn, "CREATE INDEX IF NOT EXISTS idx_cases_company_radicado ON cases(company_id, radicado)")
        try_execute(conn, "CREATE INDEX IF NOT EXISTS idx_case_search_source_results_company_radicado ON case_search_source_results(company_id, radicado)")
        
        print("[DB] Migraciones rapidas completadas")
except Exception as e:
    print(f"[DB] Error en migraciones: {e}")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_data_scope(current_user):
    if is_global_superadmin(current_user):
        return {"scope": "all"}
    if current_user.company_id:
        return {"scope": "company", "company_id": current_user.company_id}
    from fastapi import HTTPException
    raise HTTPException(status_code=403, detail="Usuario sin empresa asignada")

def apply_company_filter(query, model, current_user):
    if is_global_superadmin(current_user):
        return query
    if hasattr(model, "company_id"):
        return query.filter(model.company_id == current_user.company_id)
    from fastapi import HTTPException
    raise HTTPException(status_code=500, detail=f"El modelo {model.__name__} requiere filtro por empresa pero no tiene company_id")
from pydantic import BaseModel
from io import BytesIO
import pandas as pd
import traceback
import hashlib
import json
import re
import smtplib
import asyncio
import random
import pytz
import httpx
import os
from passlib.context import CryptContext
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple
from contextlib import asynccontextmanager

class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    nombre: Optional[str] = None
    is_active: bool
    is_admin: bool

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    nombre: Optional[str] = None

class RegisterCompanyRequest(BaseModel):
    company_name: str
    company_nit: Optional[str] = None
    admin_name: str
    email: str
    password: str
    confirm_password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    confirm_password: str

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

class BillingTierCreate(BaseModel):
    min_cases: int
    max_cases: Optional[int]
    price: float

class BillingTierUpdateList(BaseModel):
    tiers: List[BillingTierCreate]

class LoginRequest(BaseModel):
    username: str
    password: str

from backend.models import (
    Case, CaseEvent, NotificationConfig, NotificationLog, InvalidRadicado, 
    User, CasePublication, SearchJob, Workspace, WorkspaceMember, Folder, 
    ProjectList, Task, TaskComment, TaskChecklistItem, TaskAttachment, IntegrationConfig, Tag,
    Company, Role, PasswordResetToken, BillingTier, ExcelImportJob
)
from sqladmin import Admin, ModelView
from sqladmin.authentication import AuthenticationBackend
from starlette.responses import RedirectResponse
from backend.service.rama import (
    consulta_por_radicado,
    detalle_proceso,
    actuaciones_proceso,
    documentos_actuacion,
    consulta_por_nombre,
    RamaError,
    RamaRateLimitError,
)
from backend.apply_robust_migrations import run_migrations
from backend.service.publicaciones import (
    consultar_publicaciones, 
    parse_fecha_pub, 
    consultar_publicaciones_rango,
    is_relevant_actuacion
)
from backend.service.bulk_orchestrator import run_name_search_job, log_job
from backend.clickup_sync import migrate_clickup_to_emdecob


# =========================
# ZONA HORARIA COLOMBIA
# =========================
TIMEZONE_CO = pytz.timezone("America/Bogota")

# Global Lock to prevent multiple background syncs at once
REFRESH_LOCK = asyncio.Lock()

RAMA_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://consultaprocesos.ramajudicial.gov.co/",
    "Origin": "https://consultaprocesos.ramajudicial.gov.co",
}

RAMA_BASE = "https://consultaprocesos.ramajudicial.gov.co:448/api/v2"

MONTHS_ES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

def now_colombia() -> datetime:
    return datetime.now(TIMEZONE_CO).replace(tzinfo=None)


def today_colombia() -> date:
    return datetime.now(TIMEZONE_CO).date()


# =========================
# VARIABLES GLOBALES AUTO-REFRESH
# =========================
auto_refresh_task = None
auto_refresh_running = False
auto_refresh_stats = {
    "running": False,
    "last_run": None,
    "next_run": None,
    "last_result": None,
    "interval_minutes": 60,
}

_notification_accumulator: List[dict] = []
_notification_accumulator_date: Optional[date] = None
NOTIFICATION_BATCH_SIZE = 15
NOTIFICATION_FLUSH_HOUR = 17


async def notification_flush_loop():
    global _notification_accumulator
    _already_flushed_today: Optional[date] = None

    while True:
        await asyncio.sleep(60)
        try:
            now  = now_colombia()
            hoy  = today_colombia()

            if (
                now.hour == NOTIFICATION_FLUSH_HOUR
                and _already_flushed_today != hoy
                and _notification_accumulator
            ):
                print(f"[flush-loop] Son las {NOTIFICATION_FLUSH_HOUR}:00  enviando {len(_notification_accumulator)} casos acumulados")
                send_grouped_notification(list(_notification_accumulator))
                _notification_accumulator.clear()
                _already_flushed_today = hoy
        except Exception as e:
            with open("sync_emergency.log", "a") as f:
                f.write(f"[{datetime.now()}] ERROR FATAL en tarea {radicado}: {str(e)}\n")
            print(f"[sync-error] {e}")


# =========================
# AUTO-REFRESH EN BACKGROUND
# =========================
async def auto_refresh_loop():
    global auto_refresh_running, auto_refresh_stats

    print("Esperando 60 segundos antes del primer auto-refresh...")
    await asyncio.sleep(60)

    print("Auto-refresh continuo iniciado - revisara TODOS los casos en cada ciclo")

    while auto_refresh_running:
        try:
            now = now_colombia()
            print(f"\n[AUTO-REFRESH] [{now.strftime('%Y-%m-%d %H:%M:%S')}] Iniciando ciclo completo de auto-refresh...")
            auto_refresh_stats["last_run"] = now.isoformat()
            auto_refresh_stats["next_run"] = "Al terminar este ciclo + 10 min"

            result = await do_auto_refresh()

            auto_refresh_stats["last_result"] = result
            print(f"[*] Ciclo completo: {result.get('checked', 0)} revisados, {result.get('updated_cases', 0)} con cambios")

            hora = now_colombia().hour
            if hora >= NOTIFICATION_FLUSH_HOUR and _notification_accumulator:
                print(f"[EMAIL] Flush de 5 PM: enviando {len(_notification_accumulator)} casos acumulados")
                send_grouped_notification(_notification_accumulator)
                _notification_accumulator.clear()

            auto_refresh_stats["next_run"] = "En 10 minutos"
            await asyncio.sleep(600)

        except Exception as e:
            print(f"[ERROR] Error en auto-refresh: {e}")
            auto_refresh_stats["last_result"] = {"error": str(e)}
            await asyncio.sleep(300)


async def do_auto_refresh() -> dict:
    from sqlalchemy import text

    BATCH_SIZE = 3
    MINI_BATCH = 10
    DELAY_BETWEEN = 0.5
    EXTRA_EVERY_N = 10
    EXTRA_DELAY   = 0.5

    updated_cases = []
    checked  = 0
    errors   = 0
    db       = None

    def get_fresh_db():
        session = SessionLocal()
        try:
            session.execute(text("SELECT 1"))
        except Exception:
            session.close()
            session = SessionLocal()
            session.execute(text("SELECT 1"))
        return session

    try:
        db = get_fresh_db()

        BATCH_SIZE = 50

        case_ids = [
            row[0] for row in
            db.query(Case.id)
            .filter(Case.juzgado.isnot(None))
            .order_by(Case.last_check_at.asc())
            .limit(BATCH_SIZE)
            .all()
        ]
        total_cases = db.query(Case).filter(Case.juzgado.isnot(None)).count()
        db.close()
        db = None

        if not case_ids:
            return {"ok": True, "checked": 0, "updated_cases": 0, "message": "No hay casos para verificar"}

        print(f"[stats] Verificando {len(case_ids)} de {total_cases} casos...")

        for i, case_id in enumerate(case_ids):
            try:
                if i > 0:
                    delay = DELAY_BETWEEN + random.uniform(0, 1.0)
                    if i % EXTRA_EVERY_N == 0:
                        delay += EXTRA_DELAY
                    await asyncio.sleep(delay)

                if i % MINI_BATCH == 0:
                    if db:
                        try: db.close()
                        except: pass
                    db = get_fresh_db()
                    print(f"   (Link) Conexion renovada en caso {i+1}/{len(case_ids)}")

                c = db.query(Case).filter(Case.id == case_id).first()
                if not c:
                    continue

                # Si el caso es de la SIC, consultar con el conector de la SIC
                if c.juzgado == "SIC" or c.fuente_encontrado == "SIC" or bool(re.match(r'^(?:20)?\d{2}-\d+$', str(c.radicado).strip())):
                    try:
                        from backend.services.judicial_sources import CONNECTORS
                        sic_conn = CONNECTORS.get("SIC")
                        meta = {"cedula": c.cedula, "demandante": c.demandante, "demandado": c.demandado, "estado": c.estado}
                        sic_res = sic_conn.search_case(c.radicado, metadata=meta)
                        c.last_check_at = now_colombia()
                        checked += 1
                        continue
                    except Exception as sic_err:
                        print(f"   [WARN] Error consultando SIC {c.radicado}: {sic_err}")
                        errors += 1
                        continue

                try:
                    resp = await consulta_por_radicado(c.radicado, solo_activos=False, pagina=1)
                    items = extract_items(resp)
                except RamaError as e:
                    print(f"   [WARN] Error consultando {c.radicado}: {e}")
                    errors += 1
                    if "bloque" in str(e).lower() or "rate" in str(e).lower():
                        await asyncio.sleep(60)
                    continue

                if not items:
                    c.last_check_at = now_colombia()
                    checked += 1
                    continue

                p = items[0] or {}

                fecha_ult_api = (
                    p.get("fechaUltimaActuacion")
                    or p.get("FechaUltimaActuacion")
                    or p.get("ultimaActuacion")
                    or p.get("UltimaActuacion")
                )

                nueva_fecha  = parse_fecha(fecha_ult_api)
                fecha_actual = c.ultima_actuacion
                hoy  = today_colombia()
                ayer = hoy - timedelta(days=1)

                hay_cambio           = False
                es_actuacion_reciente = False

                if nueva_fecha and fecha_actual:
                    hay_cambio = nueva_fecha > fecha_actual
                elif nueva_fecha and not fecha_actual:
                    hay_cambio = True

                if nueva_fecha:
                    es_actuacion_reciente = nueva_fecha >= ayer

                if hay_cambio:
                    # Si hay cambio detectado, usamos la funcin maestra para traer todo (actuaciones, sujetos, etc.)
                    try:
                        print(f"   [SYNC] Cambio detectado en {c.radicado}. Sincronizando actuaciones...")
                        await validar_radicado_completo(c.radicado, db, is_new_import=False)
                        updated_cases.append({
                            "radicado": c.radicado,
                            "demandante": c.demandante,
                            "demandado": c.demandado,
                            "juzgado": c.juzgado,
                            "ultima_actuacion": nueva_fecha.isoformat() if nueva_fecha else None,
                        })
                    except Exception as sync_e:
                        print(f"    [ERROR-SYNC] Fall en sincronizacin profunda de {c.radicado}: {sync_e}")
                        # Fallback: al menos actualizamos la fecha para que no intente refrescarlo de inmediato en el siguiente loop
                        c.ultima_actuacion = nueva_fecha
                        c.last_check_at = now_colombia()

                c.last_check_at = now_colombia()
                checked += 1

                if (i + 1) % MINI_BATCH == 0:
                    try:
                        db.commit()
                        print(f"   (OK) Commit parcial: {i+1}/{len(case_ids)} casos")
                    except Exception as e:
                        print(f"   (Warn) Error en commit parcial: {e} - reconectando...")
                        try: db.rollback()
                        except: pass
                        try: db.close()
                        except: pass
                        db = get_fresh_db()

            except Exception as e:
                print(f"   (Error) Error procesando caso_id={case_id}: {e}")
                errors += 1
                if "ssl" in str(e).lower() or "connection" in str(e).lower():
                    try:
                        if db: db.close()
                    except: pass
                    db = get_fresh_db()

        if db:
            try:
                db.commit()
                print(f"    Commit final")
            except Exception as e:
                print(f"    Error en commit final: {e}")
                try: db.rollback()
                except: pass

        if updated_cases:
            _accumulate_and_notify(updated_cases)

        return {
            "ok": True,
            "checked": checked,
            "updated_cases": len(updated_cases),
            "errors": errors,
            "total_in_db": total_cases,
            "cases_with_changes": updated_cases,
        }

    except Exception as e:
        print(f" Error en do_auto_refresh: {e}")
        raise
    finally:
        if db:
            try: db.close()
            except: pass


async def save_new_actuaciones(case: Case, id_proceso: int, db: Session):
    try:
        await asyncio.sleep(random.uniform(0.2, 0.5))
        acts_resp = await actuaciones_proceso(int(id_proceso))
        acts = []
        if isinstance(acts_resp, dict):
            acts = acts_resp.get("actuaciones") or acts_resp.get("items") or []
        elif isinstance(acts_resp, list):
            acts = acts_resp

        for a in acts:
            con_docs = bool(a.get("conDocumentos")) if a.get("conDocumentos") is not None else False
            it = {
                "id_reg_actuacion": a.get("idRegActuacion"),
                "cons_actuacion": a.get("consActuacion"),
                "llave_proceso": a.get("llaveProceso"),
                "event_date": a.get("fechaActuacion"),
                "title": (a.get("actuacion") or "").strip(),
                "detail": a.get("anotacion"),
                "fecha_inicio": a.get("fechaInicial"),
                "fecha_fin": a.get("fechaFinal"),
                "fecha_registro": a.get("fechaRegistro"),
                "con_documentos": con_docs,
                "cant": a.get("cant"),
            }
            event_hash = sha256_obj(it)
            exists = db.query(CaseEvent).filter(
                CaseEvent.case_id == case.id,
                CaseEvent.event_hash == event_hash
            ).first()
            if not exists:
                db.add(CaseEvent(
                    case_id=case.id,
                    event_date=it.get("event_date"),
                    title=it.get("title"),
                    detail=it.get("detail"),
                    event_hash=event_hash,
                    con_documentos=con_docs,
                    id_reg_actuacion=it.get("id_reg_actuacion"),
                    cons_actuacion=it.get("cons_actuacion"),
                ))
                if con_docs:
                    case.has_documents = True
    except Exception as e:
        print(f"    Error guardando actuaciones: {e}")


def _accumulate_and_notify(new_cases: List[dict]):
    global _notification_accumulator, _notification_accumulator_date

    hoy = today_colombia()

    if _notification_accumulator_date and _notification_accumulator_date < hoy:
        print(f" Acumulador de {_notification_accumulator_date} descartado  nuevo da")
        _notification_accumulator = []

    _notification_accumulator_date = hoy

    # El acumulador ahora evita duplicar (radicado + juzgado) o (radicado + id_proceso)
    def get_case_key(c_obj):
        return f"{c_obj.get('radicado')}_{c_obj.get('juzgado', '')}"

    llaves_existentes = {get_case_key(c) for c in _notification_accumulator}
    for c in new_cases:
        key = get_case_key(c)
        if key not in llaves_existentes:
            _notification_accumulator.append(c)
            llaves_existentes.add(key)

    total = len(_notification_accumulator)
    hora  = now_colombia().hour

    print(f"[EMAIL] Acumulador: {total} casos | hora={hora}:00")

    should_send = (
        total >= NOTIFICATION_BATCH_SIZE
        or (hora >= NOTIFICATION_FLUSH_HOUR and total > 0)
    )

    if should_send:
        print(f"Enviando correo con {total} casos acumulados...")
        send_grouped_notification(_notification_accumulator)
        _notification_accumulator = []
    else:
        print(f" Acumulando... {total}/{NOTIFICATION_BATCH_SIZE} casos (envo a las {NOTIFICATION_FLUSH_HOUR}:00 si no se llega antes)")


def send_grouped_notification(updated_cases: List[dict]):
    db = SessionLocal()
    try:
        config = db.query(NotificationConfig).first()
        if not config or not config.is_active:
            return
        if not config.smtp_user or not config.smtp_pass or not config.notification_emails:
            return

        emails = [e.strip() for e in (config.notification_emails or "").split(",") if e.strip()]
        if not emails:
            return

        count = len(updated_cases)
        subject = f" {count} caso{'s' if count > 1 else ''} con nuevas actuaciones - EMDECOB"

        log = NotificationLog(
            recipients=", ".join(emails),
            cases_count=count,
            subject=subject,
            status="sent",
        )

        try:
            rows_html = ""
            for case in updated_cases:
                rows_html += f"""
                <tr>
                  <td style="padding:8px;border:1px solid #ddd;font-family:monospace;font-size:12px;">{case.get('radicado', '')}</td>
                  <td style="padding:8px;border:1px solid #ddd;">{case.get('demandante', '') or ''}</td>
                  <td style="padding:8px;border:1px solid #ddd;">{case.get('demandado', '') or ''}</td>
                  <td style="padding:8px;border:1px solid #ddd;font-size:12px;">{case.get('juzgado', '') or ''}</td>
                  <td style="padding:8px;border:1px solid #ddd;text-align:center;">{case.get('ultima_actuacion', '') or ''}</td>
                </tr>
                """

            body = f"""
            <html>
            <body style="font-family:Arial,sans-serif;padding:20px;">
              <h2 style="color:#0d9488;"> Nuevas Actuaciones Detectadas</h2>
              <p>Se han detectado <strong>{count}</strong> caso{'s' if count > 1 else ''} con nuevas actuaciones:</p>

              <table style="border-collapse:collapse;width:100%;margin-top:20px;">
                <thead>
                  <tr style="background:#0d9488;color:white;">
                    <th style="padding:10px;border:1px solid #ddd;text-align:left;">Radicado</th>
                    <th style="padding:10px;border:1px solid #ddd;text-align:left;">Demandante</th>
                    <th style="padding:10px;border:1px solid #ddd;text-align:left;">Demandado</th>
                    <th style="padding:10px;border:1px solid #ddd;text-align:left;">Juzgado</th>
                    <th style="padding:10px;border:1px solid #ddd;text-align:center;">lt. Actuacin</th>
                  </tr>
                </thead>
                <tbody>
                  {rows_html}
                </tbody>
              </table>
              <hr style="margin-top:30px;">
              <p style="color:#888;font-size:12px;">
                Mensaje automtico EMDECOB Consultas<br>
                Fecha: {now_colombia().strftime('%Y-%m-%d %H:%M:%S')}
              </p>
            </body>
            </html>
            """

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = config.smtp_from or config.smtp_user
            msg["To"] = ", ".join(emails)
            msg.attach(MIMEText(body, "html"))

            with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(config.smtp_user, config.smtp_pass)
                server.sendmail(msg["From"], emails, msg.as_string())

        except Exception as e:
            log.status = "failed"
            log.error_message = str(e)

        db.add(log)
        db.commit()

    finally:
        db.close()


def get_unread_cases_for_notification(db: Session) -> List[dict]:
    hoy = today_colombia()
    ayer = hoy - timedelta(days=1)

    cases = db.query(Case).filter(
        Case.juzgado.isnot(None),
        Case.current_hash.isnot(None),
        or_(
            and_(Case.last_hash.isnot(None), Case.current_hash != Case.last_hash),
            and_(Case.last_hash.is_(None), Case.ultima_actuacion >= ayer),
        )
    ).order_by(desc(func.substr(Case.radicado, 13, 4)), desc(Case.ultima_actuacion)).all()

    return [
        {
            "radicado": c.radicado,
            "demandante": c.demandante,
            "demandado": c.demandado,
            "juzgado": c.juzgado,
            "ultima_actuacion": c.ultima_actuacion.isoformat() if c.ultima_actuacion else None,
        }
        for c in cases
    ]


async def _pending_validation_loop():
    BATCH = 30
    DELAY_BETWEEN = 2.5
    CYCLE_WAIT = 300

    print("[pending-loop] Loop de validacion de pendientes activo")
    await asyncio.sleep(15)

    while True:
        db = None
        try:
            db = SessionLocal()
            total = db.query(Case).filter(Case.juzgado.is_(None)).count()

            if total > 0:
                print(f" [pending-loop] {total} casos pendientes  validando lote de {min(BATCH, total)}...")
                pendientes = db.query(Case.radicado, Case.company_id).filter(Case.juzgado.is_(None)).limit(BATCH).all()
                pendientes_list = [(p.radicado, p.company_id) for p in pendientes]
                
                # Cerrar sesion de inmediato para no retener conexiones durante las llamadas HTTP externas
                db.close()
                db = None

                for i, (radicado, company_id) in enumerate(pendientes_list):
                    try:
                        if i > 0:
                            await asyncio.sleep(DELAY_BETWEEN + random.uniform(0, 0.8))
                        
                        # Abrir sesion corta para validar
                        db_run = SessionLocal()
                        try:
                            result = await validar_radicado_completo(radicado, db_run, is_new_import=True)
                            if result["found"]:
                                inv = db_run.query(InvalidRadicado).filter(InvalidRadicado.radicado == radicado).first()
                                if inv:
                                    db_run.delete(inv)
                                print(f"    [pending-loop] Validado: {radicado}")
                            else:
                                inv = db_run.query(InvalidRadicado).filter(InvalidRadicado.radicado == radicado).first()
                                if inv:
                                    inv.intentos += 1
                                    inv.updated_at = now_colombia()
                                else:
                                    db_run.add(InvalidRadicado(radicado=radicado, motivo="No encontrado en Rama Judicial", intentos=1, company_id=company_id))
                                
                                # Eliminar el caso de la tabla cases para que no quede como pendiente
                                case_to_del = db_run.query(Case).filter(Case.radicado == radicado, Case.company_id == company_id).first()
                                if case_to_del:
                                    db_run.delete(case_to_del)
                                print(f"    [pending-loop] No encontrado (movido a invalidos): {radicado}")
                            db_run.commit()
                        except Exception as run_err:
                            db_run.rollback()
                            raise run_err
                        finally:
                            db_run.close()
                    except Exception as e:
                        print(f"    [pending-loop] Error en {radicado}: {e}")

                # Re-crear sesion db para el conteo final
                db = SessionLocal()
                remaining = db.query(Case).filter(Case.juzgado.is_(None)).count()
                print(f" [pending-loop] Ciclo completo. Restantes: {remaining}")
            else:
                print(" [pending-loop] Sin pendientes. Prxima revisin en 5 min.")

        except Exception as e:
            print(f" [pending-loop] Error en ciclo: {e}")
        finally:
            if db:
                db.close()

        await asyncio.sleep(CYCLE_WAIT)

async def run_publicaciones_worker_loop():
    from backend.models import CasePublicationSearch, Case
    from backend.service.publicaciones import consultar_publicaciones_rango, parse_fecha_pub, guardar_publicacion_validada, guardar_estado_busqueda
    from sqlalchemy import text
    import traceback
    import os

    # Configuración inicial cargada desde variables de entorno
    ENABLED = os.getenv("PUBLICACIONES_AUTO_SYNC_ENABLED", "true").lower() == "true"
    if not ENABLED:
        print("[pub-worker] Worker desactivado (PUBLICACIONES_AUTO_SYNC_ENABLED = false)")
        return

    CONCURRENCY = int(os.getenv("PUBLICACIONES_AUTO_SYNC_CONCURRENCY", "1"))
    SLEEP_MS = float(os.getenv("PUBLICACIONES_AUTO_SYNC_SLEEP_MS", "800")) / 1000.0
    MAX_RETRIES = int(os.getenv("PUBLICACIONES_AUTO_SYNC_MAX_RETRIES", "2"))
    LOCK_TIMEOUT_MINUTES = int(os.getenv("PUBLICACIONES_LOCK_TIMEOUT_MINUTES", "15"))
    BATCH_SIZE = int(os.getenv("PUBLICACIONES_AUTO_SYNC_BATCH_SIZE", "5"))

    print(f"[pub-worker] Iniciando worker automático de publicaciones procesales (SLEEP_MS={SLEEP_MS}s, MAX_RETRIES={MAX_RETRIES}, BATCH_SIZE={BATCH_SIZE})...")
    await asyncio.sleep(5)  # Esperar a que inicie la app

    while True:
        db = None
        try:
            db = SessionLocal()
            
            # Recuperar tareas colgadas (timeout_threshold)
            timeout_threshold = now_colombia() - timedelta(minutes=LOCK_TIMEOUT_MINUTES)
            colgadas = db.query(CasePublicationSearch).filter(
                CasePublicationSearch.estado == "procesando",
                CasePublicationSearch.locked_at < timeout_threshold
            ).all()
            
            for c in colgadas:
                c.intentos += 1
                c.ultimo_error = "Timeout. Recuperada por el worker."
                c.locked_at = None
                c.locked_by = None
                if c.intentos >= MAX_RETRIES and not c.force:
                    c.estado = "error"
                    c.estado_busqueda = "error"
                else:
                    c.estado = "pendiente"
                    c.estado_busqueda = "pendiente"
                    c.next_retry_at = now_colombia() + timedelta(minutes=5 * c.intentos)
                    
            if colgadas:
                db.commit()
                print(f"[pub-worker] Recuperadas {len(colgadas)} tareas colgadas.")

            # Obtener pendientes
            candidatos = db.query(CasePublicationSearch).filter(
                CasePublicationSearch.estado == "pendiente",
                or_(CasePublicationSearch.next_retry_at.is_(None), CasePublicationSearch.next_retry_at <= now_colombia())
            ).order_by(desc(CasePublicationSearch.prioridad), CasePublicationSearch.created_at).limit(BATCH_SIZE).all()

            if not candidatos:
                # Barrido incremental de seguridad para casos activos sin búsquedas registradas
                from sqlalchemy import exists, and_
                from backend.service.publicaciones import auto_queue_publicaciones_for_case
                
                no_search_cases = db.query(Case).filter(
                    Case.is_active == True,
                    Case.juzgado.isnot(None),
                    ~exists().where(
                        and_(
                            CasePublicationSearch.company_id == Case.company_id,
                            CasePublicationSearch.radicado == Case.radicado
                        )
                    )
                ).limit(10).all()
                
                if no_search_cases:
                    print(f"[pub-worker] Detectados {len(no_search_cases)} casos activos sin búsquedas de publicaciones. Encolando...")
                    for nc in no_search_cases:
                        auto_queue_publicaciones_for_case(db, nc)
                    db.commit()
                    # Re-consultar candidatos
                    candidatos = db.query(CasePublicationSearch).filter(
                        CasePublicationSearch.estado == "pendiente",
                        or_(CasePublicationSearch.next_retry_at.is_(None), CasePublicationSearch.next_retry_at <= now_colombia())
                    ).order_by(desc(CasePublicationSearch.prioridad), CasePublicationSearch.created_at).limit(BATCH_SIZE).all()
                
                if not candidatos:
                    await asyncio.sleep(5.0)
                    continue

            for candidato in candidatos:
                # Intento de lock optimista
                locked_id = candidato.id
                worker_id = f"worker_{id(asyncio.current_task())}"
                now_ts = now_colombia()
                
                # Ejecutar UPDATE crudo para el lock
                stmt = text("""
                    UPDATE publicaciones_busquedas 
                    SET estado='procesando', estado_busqueda='procesando', locked_at=:now, locked_by=:worker 
                    WHERE id=:id AND estado='pendiente'
                """)
                res = db.execute(stmt, {"now": now_ts, "worker": worker_id, "id": locked_id})
                db.commit()

                if res.rowcount == 0:
                    continue # Otro worker la tomó
                
                # Refrescar instancia
                db.refresh(candidato)
                
                # Extraer todos los datos necesarios para la consulta antes de cerrar la session
                radicado = candidato.radicado
                company_id = candidato.company_id
                fecha_actuacion = candidato.fecha_actuacion
                mes_busqueda = candidato.mes_busqueda
                intentos = candidato.intentos
                force = candidato.force
                
                fecha_act_str = fecha_actuacion.strftime("%Y-%m-%d")
                year, month = map(int, mes_busqueda.split("-"))
                
                case_q = db.query(Case).filter(Case.radicado == radicado)
                if company_id:
                    case_q = case_q.filter(Case.company_id == company_id)
                case_obj = case_q.first()
                
                demandante = case_obj.demandante if case_obj else ""
                demandado = case_obj.demandado if case_obj else ""
                case_id = case_obj.id if case_obj else None
                
                # CERRAR la sesion activa para no retener conexiones durante la llamada HTTP externa
                db.close()
                db = None # Para evitar re-uso accidental
                
                print(f"[PUBLICACIONES][WORKER_PICKED] company_id={company_id} radicado={radicado} mes_busqueda={mes_busqueda} search_id={locked_id}")
                
                # Realizar llamada externa sin conexion DB
                try:
                    pubs = await consultar_publicaciones_rango(
                        radicado, 
                        fecha_act_str, 
                        demandante=demandante,
                        demandado=demandado,
                        year=year, 
                        month=month,
                        company_id=company_id,
                        search_id=locked_id
                    )
                    
                    # Abrir nueva conexion corta para guardar resultados
                    db_save = SessionLocal()
                    try:
                        has_visible = False
                        if pubs:
                            for pub_data in pubs:
                                pub_data["radicado"] = radicado
                                pub_data["company_id"] = company_id
                                pub_data["case_id"] = case_id
                                saved_pub = guardar_publicacion_validada(db_save, pub_data, search_id=locked_id)
                                if saved_pub and saved_pub.estado_validacion in ["validado", "validado_automatico", "validado_por_fuente_oficial"]:
                                    has_visible = True
                        
                        # Refrescar/Recuperar el record en esta sesion
                        c_rec = db_save.query(CasePublicationSearch).filter(CasePublicationSearch.id == locked_id).first()
                        if c_rec:
                            if has_visible:
                                c_rec.estado = "encontrada"
                                c_rec.estado_busqueda = "encontrada"
                                print(f"[PUBLICACIONES][SEARCH_MARKED_FOUND] company_id={company_id} radicado={radicado} search_id={locked_id} url=N/A estado_validacion=encontrada motivo=has_visible")
                            else:
                                c_rec.estado = "sin_resultado"
                                c_rec.estado_busqueda = "sin_resultado"
                                print(f"[PUBLICACIONES][SEARCH_MARKED_NO_RESULT] company_id={company_id} radicado={radicado} search_id={locked_id} url=N/A estado_validacion=sin_resultado motivo=no_visible_pubs")
                                
                            c_rec.processed_at = now_colombia()
                            c_rec.ultimo_error = None
                            c_rec.locked_at = None
                            c_rec.locked_by = None
                            db_save.commit()
                    except Exception as save_err:
                        db_save.rollback()
                        raise save_err
                    finally:
                        db_save.close()
                        
                except Exception as e:
                    err_msg = str(e) + "\n" + traceback.format_exc()
                    print(f"[PUBLICACIONES][ERROR] company_id={company_id} radicado={radicado} mes_busqueda={mes_busqueda} search_id={locked_id} error={str(e)}")
                    
                    # Abrir nueva conexion corta para guardar el error
                    db_err = SessionLocal()
                    try:
                        c_rec = db_err.query(CasePublicationSearch).filter(CasePublicationSearch.id == locked_id).first()
                        if c_rec:
                            c_rec.intentos += 1
                            c_rec.ultimo_error = err_msg[:500]
                            c_rec.processed_at = now_colombia()
                            
                            if c_rec.intentos >= MAX_RETRIES and not force:
                                c_rec.estado = "error"
                                c_rec.estado_busqueda = "error"
                            else:
                                c_rec.estado = "pendiente"
                                c_rec.estado_busqueda = "pendiente"
                                c_rec.next_retry_at = now_colombia() + timedelta(minutes=5 * c_rec.intentos)
                                
                            c_rec.locked_at = None
                            c_rec.locked_by = None
                            db_err.commit()
                    except Exception as err_save_err:
                        db_err.rollback()
                        print(f"[pub-worker] Error fatal guardando error: {err_save_err}")
                    finally:
                        db_err.close()
                
                # Re-crear una sesion db limpia para la siguiente iteracion del bucle / query final
                db = SessionLocal()
                
                # Sleep de protección entre requests a la Rama
                await asyncio.sleep(SLEEP_MS)
                
        except Exception as e:
            print(f"[pub-worker] Error fatal en loop: {e}")
            await asyncio.sleep(5.0)
        finally:
            if db:
                db.close()
                
        await asyncio.sleep(0.1)


# =========================
# LIFESPAN (STARTUP/SHUTDOWN)
# =========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global auto_refresh_task, auto_refresh_running, auto_refresh_stats

    # Garantizar que las tablas existan (tolerante a fallos)
    try:
        Base.metadata.create_all(bind=engine)
        print("[STARTUP] create_all completado")
    except Exception as e:
        print(f"[STARTUP][WARNING] create_all error (se continua): {e}")
    
    # Asegurar usuarios necesarios
    try:
        db_s = SessionLocal()
        users_to_add = [
            ("julian.cuartas", "JULIAN CUARTAS", "292509"),
            ("valentina.patino", "VALENTINA PATIÑO", "251410"),
            ("heriberto.montealegre", "HERIBERTO MONTEALEGRE", "Heriberto2026*"),
            ("erik.garzon", "ERIK SANTIAGO GARZON AMEZQUITA", "1094950684"),
            ("erik.santiago", "ERIK SANTIAGO GARZON AMEZQUITA", "1094950684"),
            ("superadmin", "SUPERADMIN", "admin123$")
        ]
        # Clean up conflicting superadmin IDs (tolerante a errores de FK)
        from sqlalchemy import text
        try:
            db_s.execute(text("DELETE FROM users WHERE username = 'superadmin' OR id = 9999"))
            db_s.commit()
        except Exception as del_err:
            db_s.rollback()
            print(f"[STARTUP] No se pudo eliminar superadmin (normal si tiene FK): {del_err}")

        # Buscar la empresa de fna_juridica
        fna = db_s.query(User).filter(User.username == "fna_juridica").first()
        fna_company_id = fna.company_id if fna else 2

        for uname, nombre, pwd in users_to_add:
            u = db_s.query(User).filter(User.username == uname).first()
            if uname == "superadmin":
                cid = None
                is_adm = True
                role_val = "SUPERADMIN"
            else:
                cid = fna_company_id if "erik" in uname else 1
                is_adm = False
                role_val = "USER"

            if not u:
                if uname == "superadmin":
                    u = User(id=9999, username=uname, nombre=nombre, hashed_password=_hash_password(pwd), company_id=cid, is_admin=is_adm, role=role_val)
                else:
                    u = User(username=uname, nombre=nombre, hashed_password=_hash_password(pwd), company_id=cid, is_admin=is_adm, role=role_val)
                db_s.add(u)
            else:
                u.hashed_password = _hash_password(pwd)
                u.company_id = cid
                u.is_admin = is_adm
                u.role = role_val
        db_s.commit()
        db_s.close()
    except Exception as e:
        print(f"Error asegurando usuarios: {e}")
    
    # Ejecutar diagnóstico y migraciones P0 seguras
    try:
        from backend.p0_migrations import run_p0_migrations
        run_p0_migrations()
    except Exception as e:
        print(f"[lifespan][CRITICAL] Error en run_p0_migrations: {e}")
        print("[lifespan][WARNING] Backend will start despite migration error.")
    
    # Crear tabla de control de sincronización masiva de forma segura
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS publicaciones_sync_jobs (
                    id SERIAL PRIMARY KEY,
                    company_id INTEGER,
                    estado VARCHAR(50) DEFAULT 'pendiente',
                    total_casos INTEGER DEFAULT 0,
                    casos_procesados INTEGER DEFAULT 0,
                    busquedas_creadas INTEGER DEFAULT 0,
                    busquedas_omitidas INTEGER DEFAULT 0,
                    con_actuaciones_relevantes INTEGER DEFAULT 0,
                    sin_actuaciones_relevantes INTEGER DEFAULT 0,
                    con_error INTEGER DEFAULT 0,
                    porcentaje INTEGER DEFAULT 0,
                    radicado_actual VARCHAR(100),
                    force BOOLEAN DEFAULT FALSE,
                    solo_pendientes BOOLEAN DEFAULT TRUE,
                    iniciado_por VARCHAR(200),
                    fecha_inicio TIMESTAMP,
                    fecha_fin TIMESTAMP,
                    ultimo_error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.commit()
            print("[lifespan] Tabla publicaciones_sync_jobs garantizada en DB.")
    except Exception as e:
        print(f"[lifespan] Error al garantizar la tabla publicaciones_sync_jobs: {e}")
    
    # Reparación manual de columnas faltantes para evitar errores 500
    try:
        from sqlalchemy import inspect, text
        inspector = inspect(engine)
        cols = [c['name'] for c in inspector.get_columns('tasks')]
        with engine.connect() as conn:
            if 'assignee_id' not in cols:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN assignee_id INTEGER REFERENCES users(id)"))
                print("Migración: Columna assignee_id añadida")
            if 'parent_id' not in cols:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN parent_id INTEGER REFERENCES tasks(id) ON DELETE CASCADE"))
                print("Migración: Columna parent_id añadida")
            if 'clickup_id' not in cols:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN clickup_id VARCHAR(100)"))
                print("Migración: Columna clickup_id añadida")
            if 'assignee_name' not in cols:
                conn.execute(text("ALTER TABLE tasks ADD COLUMN assignee_name VARCHAR(200)"))
                print("Migración: Columna assignee_name añadida")
            conn.commit()
            
            # Verificar columnas de ClickUp en la tabla de usuarios
            user_cols = [c['name'] for c in inspector.get_columns('users')]
            with engine.connect() as conn:
                if 'sync_with_clickup' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN sync_with_clickup BOOLEAN DEFAULT TRUE"))
                    print("Migración: Columna sync_with_clickup añadida a users")
                if 'clickup_api_token' not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN clickup_api_token VARCHAR(255)"))
                    print("Migración: Columna clickup_api_token añadida a users")
                conn.commit()

            # Configurar sync_with_clickup inicial para usuarios
            from backend.models import User
            from backend.db import SessionLocal
            db_init = SessionLocal()
            try:
                for u in db_init.query(User).all():
                    uname = (u.username or "").lower()
                    name = (u.nombre or "").lower()
                    is_special = (
                        "jurico" in uname or 
                        "juricob" in uname or
                        "julian" in uname or "cuartas" in uname or
                        "heriberto" in uname or "hereiberto" in uname or "montealegre" in uname or
                        "valentina" in uname or "patino" in uname or "pati" in uname or
                        "erik" in uname or "garzon" in uname
                    )
                    u.sync_with_clickup = not is_special
                db_init.commit()
                print("[lifespan] Inicialización de sync_with_clickup completada.")
            except Exception as ex:
                print(f"[lifespan] Error inicializando sync_with_clickup: {ex}")
            finally:
                db_init.close()
            
    except Exception as e:
        print(f"[DB] Error en migraciones de tareas antiguas: {e}")
        
    # --- AUTO-MIGRACIÓN SaaS POSTGRESQL INDEPENDIENTE ---
    try:
        with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
            # --- MIGRACION POSTGRESQL AUTOMATICA DE TODAS LAS TABLAS Y COLUMNAS ---
            try: conn.execute(text("ALTER TABLE task_assignees ADD COLUMN IF NOT EXISTS task_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_assignees ADD COLUMN IF NOT EXISTS user_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS company_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS radicado VARCHAR(60);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS id_proceso VARCHAR(50);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS demandante VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS demandado VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS juzgado VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS alias VARCHAR(200);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS cedula VARCHAR(50);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS abogado VARCHAR(200);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS telefono VARCHAR(50);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS user_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS last_hash VARCHAR(64);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS current_hash VARCHAR(64);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS last_check_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS fecha_radicacion DATE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS ultima_actuacion DATE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS has_documents BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS sync_pub_status VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS sync_pub_progress INTEGER DEFAULT 0;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT True;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE cases ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE billing_tiers ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE billing_tiers ADD COLUMN IF NOT EXISTS min_cases INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE billing_tiers ADD COLUMN IF NOT EXISTS max_cases INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE billing_tiers ADD COLUMN IF NOT EXISTS price FLOAT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE billing_tiers ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE billing_tiers ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS company_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS case_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS event_date VARCHAR(60);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS title VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS detail TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS event_hash VARCHAR(64);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS con_documentos BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS id_reg_actuacion BIGINT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS cons_actuacion BIGINT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS documentos_cache TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS is_current BOOLEAN DEFAULT True;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_events ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE invalid_radicados ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE invalid_radicados ADD COLUMN IF NOT EXISTS company_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE invalid_radicados ADD COLUMN IF NOT EXISTS radicado VARCHAR(23);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE invalid_radicados ADD COLUMN IF NOT EXISTS motivo VARCHAR(255) DEFAULT 'No encontrado en Rama Judicial';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE invalid_radicados ADD COLUMN IF NOT EXISTS intentos INTEGER DEFAULT 1;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE invalid_radicados ADD COLUMN IF NOT EXISTS user_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE invalid_radicados ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE invalid_radicados ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            # Backfill: asignar company_id a registros existentes tomándolo del case correspondiente
            try:
                conn.execute(text("""
                    UPDATE invalid_radicados ir
                    SET company_id = c.company_id
                    FROM cases c
                    WHERE ir.radicado = c.radicado
                      AND ir.company_id IS NULL
                      AND c.company_id IS NOT NULL
                """))
                print('[AUTO-MIGRATE] Backfill company_id en invalid_radicados completado')
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] backfill invalid_radicados: {e}')
            try: conn.execute(text("ALTER TABLE notification_config ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_config ADD COLUMN IF NOT EXISTS smtp_host VARCHAR(255) DEFAULT 'smtp.gmail.com';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_config ADD COLUMN IF NOT EXISTS smtp_port INTEGER DEFAULT 587;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_config ADD COLUMN IF NOT EXISTS smtp_user VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_config ADD COLUMN IF NOT EXISTS smtp_pass VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_config ADD COLUMN IF NOT EXISTS smtp_from VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_config ADD COLUMN IF NOT EXISTS notification_emails TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_config ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_config ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_config ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS recipients TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS subject VARCHAR(500);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS cases_count INTEGER DEFAULT 0;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'sent';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE notification_logs ADD COLUMN IF NOT EXISTS error_message TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS nombre VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS nit VARCHAR(50);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS estado VARCHAR(50) DEFAULT 'activo';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS limite_usuarios INTEGER DEFAULT 5;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS suspension_reason TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS suspended_by INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS reactivated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS reactivated_by INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50) DEFAULT 'al_dia';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS last_payment_date TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS next_payment_due DATE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS billing_notes TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE companies ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE roles ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE roles ADD COLUMN IF NOT EXISTS name VARCHAR(50);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE roles ADD COLUMN IF NOT EXISTS description VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE permissions ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE permissions ADD COLUMN IF NOT EXISTS name VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE role_permissions ADD COLUMN IF NOT EXISTS role_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE role_permissions ADD COLUMN IF NOT EXISTS permission_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS user_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE user_roles ADD COLUMN IF NOT EXISTS role_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS username VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS nombre VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS telefono VARCHAR(50);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT True;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS sync_with_clickup BOOLEAN DEFAULT True;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS clickup_api_token VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE password_reset_tokens ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE password_reset_tokens ADD COLUMN IF NOT EXISTS user_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE password_reset_tokens ADD COLUMN IF NOT EXISTS token_hash VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE password_reset_tokens ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE password_reset_tokens ADD COLUMN IF NOT EXISTS used_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE password_reset_tokens ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE password_reset_tokens ADD COLUMN IF NOT EXISTS ip_request VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE password_reset_tokens ADD COLUMN IF NOT EXISTS user_agent TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS company_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS case_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS fecha_publicacion DATE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS tipo_publicacion VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS descripcion TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS documento_url TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS source_url TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS source_id VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS url_fuente_principal TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS tipo_fuente_principal VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS texto_fuente_principal TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS validada_por_fuente_principal BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS numero_estado VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS fecha_estado_electronico DATE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS url_resumen_publicacion TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS url_cuadro TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS url_providencia TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS documentos_complementarios TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS match_fuerte BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS match_type VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS motivo_match TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS observacion TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS estado_validacion VARCHAR(50) DEFAULT 'requiere_revision';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS match_score INTEGER DEFAULT 0;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS texto_bloque_match TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS motivo_descarte TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS fuente_principal_validada BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS requiere_revision BOOLEAN DEFAULT True;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS elementos_detectados TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS documento_nombre TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS extraction_quality VARCHAR(50);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS validated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS validado_manual BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS aprobado_por_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS descartado_manual BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS descartado_por_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS discarded_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS observacion_revision TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE case_publications ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS company_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS accion VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entidad VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entidad_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS ip VARCHAR(50);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS user_agent TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS metadata_json TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS company_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS radicado VARCHAR(60);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS fecha_actuacion DATE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS fecha_inicio_busqueda DATE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS fecha_fin_busqueda DATE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS despacho_codigo VARCHAR(20);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS estado VARCHAR(50) DEFAULT 'pendiente';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS estado_busqueda VARCHAR(50) DEFAULT 'pendiente';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS fecha_ultima_busqueda TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS intento_manual BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS error TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS debug TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS mes_busqueda VARCHAR(20);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS prioridad INTEGER DEFAULT 0;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS intentos INTEGER DEFAULT 0;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS ultimo_error TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS processed_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS locked_by VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS force BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS source_trigger VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS company_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS job_type VARCHAR(50);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'pending';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS total_items INTEGER DEFAULT 0;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS processed_items INTEGER DEFAULT 0;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS is_imported BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS results_json TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS error_message TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE search_jobs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS company_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS name VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS description TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS visibility VARCHAR(50) DEFAULT 'TEAM_COLLABORATION';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS owner_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS clickup_id VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspace_members ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspace_members ADD COLUMN IF NOT EXISTS workspace_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspace_members ADD COLUMN IF NOT EXISTS user_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE workspace_members ADD COLUMN IF NOT EXISTS role VARCHAR(50) DEFAULT 'VIEWER';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE folders ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE folders ADD COLUMN IF NOT EXISTS name VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE folders ADD COLUMN IF NOT EXISTS workspace_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE folders ADD COLUMN IF NOT EXISTS clickup_id VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE folders ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE project_lists ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE project_lists ADD COLUMN IF NOT EXISTS name VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE project_lists ADD COLUMN IF NOT EXISTS folder_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE project_lists ADD COLUMN IF NOT EXISTS workspace_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE project_lists ADD COLUMN IF NOT EXISTS clickup_id VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE project_lists ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_tags ADD COLUMN IF NOT EXISTS task_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_tags ADD COLUMN IF NOT EXISTS tag_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tags ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tags ADD COLUMN IF NOT EXISTS name VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tags ADD COLUMN IF NOT EXISTS color VARCHAR(50) DEFAULT '#3b82f6';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS company_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS title VARCHAR(500);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS description TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'To Do';"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS priority VARCHAR(50);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS due_date TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS list_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS assignee_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS creator_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS case_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS parent_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS clickup_id VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS assignee_name VARCHAR(200);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS custom_fields TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_comments ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_comments ADD COLUMN IF NOT EXISTS task_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_comments ADD COLUMN IF NOT EXISTS user_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_comments ADD COLUMN IF NOT EXISTS content TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_comments ADD COLUMN IF NOT EXISTS user_name VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_comments ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_checklist_items ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_checklist_items ADD COLUMN IF NOT EXISTS task_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_checklist_items ADD COLUMN IF NOT EXISTS content VARCHAR(500);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_checklist_items ADD COLUMN IF NOT EXISTS is_completed BOOLEAN DEFAULT False;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_checklist_items ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_attachments ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_attachments ADD COLUMN IF NOT EXISTS task_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_attachments ADD COLUMN IF NOT EXISTS name VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_attachments ADD COLUMN IF NOT EXISTS file_path VARCHAR(500);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_attachments ADD COLUMN IF NOT EXISTS file_type VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE task_attachments ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE integration_config ADD COLUMN IF NOT EXISTS id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE integration_config ADD COLUMN IF NOT EXISTS company_id INTEGER;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE integration_config ADD COLUMN IF NOT EXISTS service_name VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE integration_config ADD COLUMN IF NOT EXISTS clickup_id VARCHAR(100);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE integration_config ADD COLUMN IF NOT EXISTS api_key VARCHAR(255);"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE integration_config ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT True;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE integration_config ADD COLUMN IF NOT EXISTS settings TEXT;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE integration_config ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            try: conn.execute(text("ALTER TABLE integration_config ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE;"))
            except Exception as e: print(f'[AUTO-MIGRATE ERROR] {e}')
            tables_to_add = ["case_events", "case_publications", "tasks", "search_jobs", "workspaces", "invalid_radicados"]
            for t in tables_to_add:
                try:
                    conn.execute(text(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS company_id INTEGER"))
                    conn.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{t}_company_id ON {t}(company_id)"))
                    conn.commit()
                except Exception as ex:
                    conn.rollback() # Limpiar transaction state si falla (ej. en local/sqlite)
                    pass
            
            # Crear empresa CODE si no existe dinámicamente sin ID fijo
            conn.execute(text("INSERT INTO companies (nombre, estado) SELECT 'CODE', 'activo' WHERE NOT EXISTS (SELECT 1 FROM companies WHERE upper(nombre) = 'CODE' OR upper(nombre) = 'EMDECOB')"))
            conn.commit()
            
            # Obtener CODE_ID real
            res = conn.execute(text("SELECT id FROM companies WHERE upper(nombre) = 'CODE' OR upper(nombre) = 'EMDECOB' ORDER BY id LIMIT 1")).fetchone()
            code_id = res[0] if res else 1
            
            # Asegurar Superadmin: el superadmin es is_admin=True Y company_id=NULL
            # Primero: asignar company_id a usuarios sin empresa que NO son superadmin
            conn.execute(text(f"UPDATE users SET company_id = {code_id} WHERE company_id IS NULL AND is_admin = FALSE"))
            
            # Limpiar dato de prueba
            conn.execute(text("DELETE FROM case_events WHERE title LIKE '%Auto de prueba%'"))
            
            # Reparación estricta de orphans pedida por el usuario
            try:
                conn.execute(text("""
                    UPDATE case_events ce 
                    SET company_id = c.company_id 
                    FROM cases c 
                    WHERE ce.case_id = c.id AND ce.company_id IS NULL AND c.company_id IS NOT NULL
                """))
                conn.commit()
                conn.execute(text("""
                    UPDATE case_events ce 
                    SET company_id = c.company_id 
                    FROM cases c 
                    WHERE ce.radicado = c.radicado AND ce.company_id IS NULL AND c.company_id IS NOT NULL
                """))
                conn.commit()
            except Exception:
                conn.rollback()

            # Migrar huérfanos restantes a CODE_ID
            tables_to_update = ["cases", "case_events", "case_publications", "publicaciones_busquedas", "tasks", "search_jobs", "workspaces", "invalid_radicados", "audit_logs"]
            for t in tables_to_update:
                try:
                    conn.execute(text(f"UPDATE {t} SET company_id = {code_id} WHERE company_id IS NULL"))
                    conn.commit()
                except Exception:
                    conn.rollback()
                    pass
            
                print(f"[MIGRACION] Auto-SaaS completado para CODE_ID = {code_id}")
    except Exception as e:
        print(f"[DB] Error fatal en Auto-SaaS: {e}")
            
    try:
        with engine.connect() as conn:
            cols_pub = [c['name'] for c in inspector.get_columns('publicaciones_busquedas')]
            if 'mes_busqueda' not in cols_pub:
                print("Migración: Añadiendo columnas de cola a publicaciones_busquedas")
                conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN mes_busqueda VARCHAR(20)"))
                conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN prioridad INTEGER DEFAULT 0"))
                conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN intentos INTEGER DEFAULT 0"))
                conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN ultimo_error TEXT"))
                conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN processed_at TIMESTAMP"))
                conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN locked_at TIMESTAMP"))
                conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN locked_by VARCHAR(100)"))
                conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN next_retry_at TIMESTAMP"))
                conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN force BOOLEAN DEFAULT FALSE"))
                conn.execute(text("ALTER TABLE publicaciones_busquedas ADD COLUMN source_trigger VARCHAR(100)"))
            
            cols_pub_case = [c['name'] for c in inspector.get_columns('case_publications')]
            if 'estado_validacion' not in cols_pub_case:
                print("Migración: Añadiendo columnas de validación a case_publications")
                conn.execute(text("ALTER TABLE case_publications ADD COLUMN estado_validacion VARCHAR(50) DEFAULT 'requiere_revision'"))
                conn.execute(text("ALTER TABLE case_publications ADD COLUMN match_score INTEGER DEFAULT 0"))
                conn.execute(text("ALTER TABLE case_publications ADD COLUMN texto_bloque_match TEXT"))
                conn.execute(text("ALTER TABLE case_publications ADD COLUMN motivo_descarte TEXT"))
                conn.execute(text("ALTER TABLE case_publications ADD COLUMN fuente_principal_validada BOOLEAN DEFAULT FALSE"))
                conn.execute(text("ALTER TABLE case_publications ADD COLUMN requiere_revision BOOLEAN DEFAULT TRUE"))
                conn.execute(text("ALTER TABLE case_publications ADD COLUMN elementos_detectados TEXT"))
                conn.execute(text("ALTER TABLE case_publications ADD COLUMN documento_nombre TEXT"))
                conn.execute(text("ALTER TABLE case_publications ADD COLUMN extraction_quality VARCHAR(50)"))
                conn.execute(text("ALTER TABLE case_publications ADD COLUMN validated_at TIMESTAMP"))

            # Garantizar tablas de soporte
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS task_checklist_items (
                    id SERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
                    content VARCHAR(500) NOT NULL,
                    is_completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
    except Exception as e:
        print(f"Error en migración rápida: {e}")
        
    _ensure_default_user()
    
    # DIAGNOSTICO DE DATOS
    with SessionLocal() as db:
        try:
            total_cases = db.query(Case).count()
            total_tasks = db.query(Task).count()
            print(f"[DB] Casos en DB: {total_cases}, Tareas: {total_tasks}")
            
            for u in db.query(User).all():
                c_count = db.query(Case).filter(Case.user_id == u.id).count()
                print(f"[DB] Usuario '{u.username}' (ID: {u.id}) -> {c_count} casos")
                
            orphans = db.query(Case).filter(Case.user_id.is_(None)).count()
            print(f"[DB] Casos sin dueo (NULL): {orphans}")
        except Exception as e:
            print(f"[DB] Error en diagnostico: {e}")

    asyncio.create_task(notification_flush_loop())
    print("[EMAIL] Flush loop de notificaciones iniciado")

    auto_refresh_running = True
    auto_refresh_stats["running"] = True
    auto_refresh_task = asyncio.create_task(auto_refresh_loop())
    print(f"[RELOJ] Auto-refresh iniciado (cada {auto_refresh_stats['interval_minutes']} minutos)")

    asyncio.create_task(_pending_validation_loop())
    print("[SYNC] Validacion continua de pendientes iniciada")

    asyncio.create_task(run_publicaciones_worker_loop())
    print("[SYNC] Worker de publicaciones automático iniciado")

    yield

    print(" Deteniendo EMDECOB Consultas...")
    auto_refresh_running = False
    auto_refresh_stats["running"] = False
    if auto_refresh_task:
        auto_refresh_task.cancel()
        try:
            await auto_refresh_task
        except asyncio.CancelledError:
            pass


# =========================
# APP
# =========================
app = FastAPI(
    title="EMDECOB Consultas",
    description="Plataforma interna para consulta y monitoreo de procesos judiciales",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(SessionMiddleware, secret_key=secrets.token_urlsafe(32))

try:
    from backend.routers import admin
    app.include_router(admin.router)
except Exception as e:
    print("No se pudo cargar el router admin:", e)

# =========================
# SCHEMAS
# =========================
class NotificationConfigUpdate(BaseModel):
    smtp_host: Optional[str] = "smtp.gmail.com"
    smtp_port: Optional[int] = 587
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    smtp_from: Optional[str] = None
    notification_emails: Optional[str] = None
    is_active: Optional[bool] = False

class TestEmailRequest(BaseModel):
    email: str

class MarkReadBulkRequest(BaseModel):
    case_ids: List[int]

class MarkReadAllRequest(BaseModel):
    search: Optional[str] = None
    juzgado: Optional[str] = None
    solo_no_leidos: bool = False
    solo_actualizados_hoy: bool = False

class ValidateSelectedRequest(BaseModel):
    radicados: List[str]

class CaseSearchRequest(BaseModel):
    radicado: str
    company_id: Optional[int] = None
    force: Optional[bool] = False

class BuscarNuevamenteRequest(BaseModel):
    company_id: Optional[int] = None

class AutoRefreshConfigRequest(BaseModel):
    interval_minutes: int = 60

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreateRequest(BaseModel):
    username: str
    password: str
    nombre: Optional[str] = None
    is_admin: bool = False

class UserUpdateRequest(BaseModel):
    nombre: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


from cryptography.fernet import Fernet
import base64
import json

# =========================
# AUTH  Stateless Tokens
# =========================
SECRET_KEY_DEV = base64.urlsafe_b64encode(b'emdecob_secret_jwt_key_123456789')
fernet = Fernet(SECRET_KEY_DEV)

def create_access_token(user_id: int) -> str:
    payload = json.dumps({"user_id": user_id}).encode('utf-8')
    return fernet.encrypt(payload).decode('utf-8')

def verify_access_token(token: str) -> Optional[int]:
    try:
        payload = fernet.decrypt(token.encode('utf-8'), ttl=86400).decode('utf-8')
        data = json.loads(payload)
        return data.get("user_id")
    except Exception as e:
        print(f"[AUTH-DEBUG] Error validando token: {e}")
        return None

bearer_scheme = HTTPBearer(auto_error=False)

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def _hash_password(plain: str) -> str:
    return pwd_context.hash(plain)

def _verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


# =========================
# USUARIOS HARDCODEADOS (fallback si la BD falla)
# =========================
HARDCODED_USERS = {
    "admin": {
        "password": "Margarita1393$%",
        "id": 9999,
        "nombre": "Administrador",
        "is_admin": True,
    },
    "fna_juridica": {
        "password": "juridicaEmdecob2026$",
        "id": 1,
        "nombre": "FNA Juridica",
        "is_admin": False,
    },
    "fna.juridica": {
        "password": "juridicaEmdecob2026$",
        "id": 1,
        "nombre": "FNA Juridica",
        "is_admin": False,
    },
    "jurico_emdecob": {
        "password": "emdecob2027$",
        "id": 2,
        "nombre": "Juridico Emdecob",
        "is_admin": False,
    },
    "jurico.emdecob": {
        "password": "emdecob2027$",
        "id": 2,
        "nombre": "Juridico Emdecob",
        "is_admin": False,
    },
    "juricob": {
        "password": "emdecob2027$",
        "id": 2,
        "nombre": "Juridico Emdecob",
        "is_admin": False,
    },
    "superadmin": {
        "password": "admin123$",
        "id": 9999,
        "nombre": "Super Administrador",
        "is_admin": True,
    },
}


# =========================
# DB
# =========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# =========================
# AUTH  LOGIN / LOGOUT / USUARIOS
# =========================

def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    db: Session = Depends(get_db),
    token: Optional[str] = Query(None)
) -> User:
    try:
        actual_token = None
        if credentials and credentials.credentials:
            actual_token = credentials.credentials
        elif token:
            actual_token = token
        elif request.query_params.get("token"):
            actual_token = request.query_params.get("token")
        elif request.query_params.get("access_token"):
            actual_token = request.query_params.get("access_token")
        elif request.headers.get("authorization"):
            auth_h = request.headers.get("authorization", "")
            if auth_h.lower().startswith("bearer "):
                actual_token = auth_h[7:].strip()
            else:
                actual_token = auth_h.strip()
        elif request.cookies.get("emdecob_auth_token"):
            actual_token = request.cookies.get("emdecob_auth_token")
        elif request.cookies.get("token"):
            actual_token = request.cookies.get("token")
        
        if not actual_token:
            raise HTTPException(status_code=401, detail="No autenticado")
        
        user_id = verify_access_token(actual_token)
        if not user_id:
            print("[AUTH-DEBUG] El token no pudo ser verificado")
            raise HTTPException(status_code=401, detail="Token invalido o expirado")

        print(f"[AUTH-DEBUG] Token valido. UserID: {user_id}")

        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if not user:
            print(f"[AUTH-DEBUG] Usuario ID {user_id} no encontrado en BD")
            raise HTTPException(status_code=401, detail="Usuario no encontrado")
        
        # Validar suspensión de la empresa (Excepto Superadmin)
        if not is_global_superadmin(user) and user.company_id is not None and user.company:
            if user.company.estado in ["suspendida_pago", "inactiva", "vencida"]:
                raise HTTPException(status_code=403, detail="Tu empresa se encuentra suspendida. Por favor contacta al administrador.")

        return user
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        raise HTTPException(status_code=400, detail=f"AUTH ERROR: {str(e)} | TRACE: {traceback.format_exc()}")

def is_global_superadmin(user: User) -> bool:
    role = getattr(user, "role", None)
    is_admin = getattr(user, "is_admin", False)
    company_id = getattr(user, "company_id", None)
    
    if role == "SUPERADMIN":
        return True
    if is_admin is True and company_id is None:
        return True
    return False

def is_company_admin(user: User) -> bool:
    if user.company_id is None:
        return False
    if getattr(user, "role", None) == "COMPANY_ADMIN":
        return True
    if hasattr(user, "roles"):
        for r in user.roles:
            if getattr(r, "name", None) == "COMPANY_ADMIN":
                return True
    return False

def is_authorized_admin(user: User) -> bool:
    return is_global_superadmin(user) or is_company_admin(user)


def require_superadmin(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> User:
    if is_global_superadmin(current_user):
        return current_user

    # Log temporal when admin endpoint returns 403
    print({
        "endpoint": request.url.path,
        "user_id": getattr(current_user, "id", None),
        "email": getattr(current_user, "email", None),
        "company_id": getattr(current_user, "company_id", None),
        "is_admin": getattr(current_user, "is_admin", None),
        "is_superadmin": getattr(current_user, "is_superadmin", None),
        "role": getattr(current_user, "role", None),
        "reason": "admin_permission_denied"
    })

    raise HTTPException(
        status_code=403,
        detail="Solo Superadmin puede acceder a este recurso"
    )


def is_superadmin(user: User) -> bool:
    return is_global_superadmin(user)


def require_admin_or_superadmin(
    request: Request,
    current_user: User = Depends(get_current_user)
) -> User:
    if is_global_superadmin(current_user) or (current_user.is_admin and current_user.company_id is not None) or is_company_admin(current_user):
        return current_user
        
    raise HTTPException(
        status_code=403,
        detail="No tienes permisos para acceder a este recurso"
    )


def _ensure_default_user():
    db = SessionLocal()
    try:
        u1 = db.query(User).filter(User.username == "fna_juridica").first()
        if not u1:
            print("[DB] Creando usuario fna_juridica por defecto...")
            db.add(User(
                username="fna_juridica",
                hashed_password=_hash_password("juridicaEmdecob2026$"),
                nombre="FNA Juridica",
                is_active=True,
                is_admin=False,
            ))
            db.commit()
        
        u2 = db.query(User).filter(User.username.in_(["jurico_emdecob", "juricob"])).first()
        if not u2:
            print("[DB] Creando usuario jurico_emdecob por defecto...")
            db.add(User(
                username="jurico_emdecob",
                hashed_password=_hash_password("emdecob2027$"),
                nombre="Juridico Emdecob",
                is_active=True,
                is_admin=False,
            ))
            db.commit()

        # Automate assignment of orphan cases to fna_juridica
        fna_user = db.query(User).filter(User.username == "fna_juridica").first()
        if fna_user:
            orphan_count = db.query(Case).filter(Case.user_id == None).count()
            if orphan_count > 0:
                db.query(Case).filter(Case.user_id == None).update({Case.user_id: fna_user.id})
                db.commit()
                print(f" [DB-SYNC] {orphan_count} casos huerfanos asignados a fna_juridica")
        
        total_cases = db.query(Case).count()
        print(f" [DB-INFO] Total casos en BD: {total_cases}")

    except Exception as e:
        print(f" Error creando usuario por defecto: {e}")
    finally:
        db.close()





# =========================
# HELPERS
# =========================
def clean_str(x):
    if x is None:
        return None
    s = str(x).strip()
    if not s or s.lower() == "nan":
        return None
    return s

def sha256_obj(obj) -> str:
    raw = json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _normalizar_nombre(nombre: str) -> Optional[str]:
    if not nombre:
        return None
    n = nombre.strip().upper()
    return n if n else None

_FNA_KEYWORDS = {"FONDO NACIONAL DEL AHORRO", "FNA", "FONDO NAL DEL AHORRO", "F.N.A.", "TRIADA", "FONDO NACIONAL DEL AHORRO - FNA"}

def _es_fna(nombre: str) -> bool:
    if not nombre: return False
    n = nombre.upper()
    return any(kw in n for kw in _FNA_KEYWORDS)

def _asignar_roles_inteligente(nombre_a: Optional[str], nombre_b: Optional[str]):
    if nombre_a and _es_fna(nombre_a):
        return nombre_a, nombre_b
    if nombre_b and _es_fna(nombre_b):
        return nombre_b, nombre_a
    return nombre_a, nombre_b


def parse_sujetos_procesales(sujetos):
    if not sujetos:
        return None, None, None

    demandante = None
    demandado = None
    abogado = None

    if isinstance(sujetos, list):
        ROLES_DEMANDANTE = {"demandante", "accionante", "demandante/accionante", "accionante/demandante", "ejecutante"}
        ROLES_DEMANDADO  = {"demandado", "accionado", "demandado/accionado", "ejecutado", "deudor"}
        ROLES_ABOGADO    = {"defensor privado", "apoderado", "abogado"}
        
        for suj in sujetos:
            if not isinstance(suj, dict):
                continue
            tipo = (suj.get("tipoSujeto") or suj.get("tipo") or "").strip().lower()
            nombre = _normalizar_nombre(suj.get("nombre") or suj.get("name") or "")
            if not nombre:
                continue
            
            if tipo in ROLES_DEMANDANTE and demandante is None:
                demandante = nombre
            elif tipo in ROLES_DEMANDADO and demandado is None:
                demandado = nombre
            elif tipo in ROLES_ABOGADO and abogado is None:
                abogado = nombre
                
        demandante, demandado = _asignar_roles_inteligente(demandante, demandado)
        return demandante, demandado, abogado

    if not isinstance(sujetos, str):
        try:
            sujetos = str(sujetos)
        except Exception:
            return None, None, None

    # Regex para Demandante
    dem_match = re.search(
        r"(?:Demandante(?:[/\-]\w+)?|Accionante|Ejecutante)\s*:\s*([^|]+)",
        sujetos, re.IGNORECASE
    )
    if dem_match:
        demandante = _normalizar_nombre(dem_match.group(1))

    # Regex para Demandado
    ddo_match = re.search(
        r"(?:Demandado(?:[/\-]\w+)?|Accionado|Ejecutado|Deudor)\s*:\s*([^|]+)",
        sujetos, re.IGNORECASE
    )
    if ddo_match:
        demandado = _normalizar_nombre(ddo_match.group(1))
        
    # Regex para Defensor / Abogado
    abo_match = re.search(
        r"(?:Defensor Privado|Apoderado|Abogado)\s*:\s*([^|]+)",
        sujetos, re.IGNORECASE
    )
    if abo_match:
        abogado = _normalizar_nombre(abo_match.group(1))

    demandante, demandado = _asignar_roles_inteligente(demandante, demandado)
    return demandante, demandado, abogado

@app.get("/users", response_model=List[UserOut])
async def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna todos los usuarios activos del sistema para asignaci?n de tareas."""
    return db.query(User).filter(User.is_active == True).all()

def parse_fecha(fecha_str: Optional[str]) -> Optional[date]:
    if not fecha_str:
        return None
    try:
        return datetime.strptime(str(fecha_str)[:10], "%Y-%m-%d").date()
    except:
        return None

def extract_items(resp):
    items = None
    if isinstance(resp, dict):
        items = resp.get("procesos") or resp.get("Procesos") or resp.get("items")
    if not items and isinstance(resp, list):
        items = resp
    if not items or not isinstance(items, list):
        return []
    return items

def extract_fecha_proceso(p: dict, det: Optional[dict]) -> Tuple[Optional[str], Optional[str]]:
    # Priorizar detalle (det) sobre bsqueda (p)
    f_rad = None
    f_ult = None
    
    if det and isinstance(det, dict):
        f_rad = (
            det.get("fechaRadicacion")
            or det.get("fechaProceso")
            or det.get("FechaProceso")
            or det.get("FechaRadicacion")
            or det.get("fechaProcesoRadicacion")
        )
        f_ult = (
            det.get("fechaUltimaActuacion")
            or det.get("FechaUltimaActuacion")
            or det.get("ultimaActuacion")
            or det.get("UltimaActuacion")
        )

    # Fallback a p
    if not f_rad:
        f_rad = (
            p.get("fechaRadicacion")
            or p.get("fechaProceso")
            or p.get("FechaProceso")
            or p.get("FechaRadicacion")
            or p.get("fechaProcesoRadicacion")
        )
    if not f_ult:
        f_ult = (
            p.get("fechaUltimaActuacion")
            or p.get("FechaUltimaActuacion")
            or p.get("ultimaActuacion")
            or p.get("UltimaActuacion")
        )

    return f_rad, f_ult
def extract_juzgado(p: dict, det: Optional[dict]) -> Optional[str]:
    juzgado = None
    if det and isinstance(det, dict):
        juzgado = (
            det.get("despacho")
            or det.get("Despacho")
            or det.get("nombreDespacho")
            or det.get("NombreDespacho")
            or det.get("juzgado")
            or det.get("Juzgado")
        )
    
    if not juzgado:
        juzgado = (
            p.get("despacho")
            or p.get("Despacho")
            or p.get("nombreDespacho")
            or p.get("NombreDespacho")
            or p.get("juzgado")
            or p.get("Juzgado")
        )

    return juzgado

async def obtener_id_proceso(radicado: str) -> Optional[int]:
    # Intentar b?squeda directa
    resp = await consulta_por_radicado(radicado, solo_activos=False, pagina=1)
    items = extract_items(resp)
    
    # Si no hay items, intentar con los primeros 21 d?gitos (por si acaso el final var?a)
    if not items and len(radicado) >= 21:
        print(f"? [rama] Reintentando obtener_id_proceso con 21 d?gitos para {radicado}")
        resp = await consulta_por_radicado(radicado[:21], solo_activos=False, pagina=1)
        items = extract_items(resp)

    if not items:
        return None
        
    p0 = items[0] or {}
    idp = (
        p0.get("idProceso")
        or p0.get("IdProceso")
        or p0.get("id_proceso")
        or p0.get("id")
    )
    try:
        return int(idp) if idp is not None else None
    except:
        return None

def is_unread_case(c: Case) -> bool:
    if not c.current_hash:
        return False
    if c.last_hash:
        return c.current_hash != c.last_hash
    if c.ultima_actuacion:
        hoy = today_colombia()
        ayer = hoy - timedelta(days=1)
        return c.ultima_actuacion >= ayer
    return False

async def delay_between_requests(min_delay: float = 0.3, max_delay: float = 0.6):
    await asyncio.sleep(random.uniform(min_delay, max_delay))


def extract_documentos_from_response(raw) -> list:
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ("documentos", "Documentos", "items", "Items", "data", "Data", "result", "Result"):
            val = raw.get(key)
            if val and isinstance(val, list):
                return val
        if any(k in raw for k in ("idRegistroDocumento", "IdRegistroDocumento", "id", "idDocumento")):
            return [raw]
    return []


async def fetch_documentos_rama_directa(id_reg_actuacion: int, llave_proceso: str = "") -> list:
    iid = int(id_reg_actuacion)

    candidate_paths = [
        f"/Proceso/DocumentosActuacion/{iid}",
        f"/Proceso/Actuacion/Documentos/{iid}",
        f"/Proceso/Actuacion/{iid}/Documentos",
        f"/Proceso/Documento/{iid}",
    ]

    async with httpx.AsyncClient(timeout=30.0, verify=False, headers=RAMA_HEADERS) as client:
        for path in candidate_paths:
            url = f"{RAMA_BASE}{path}"
            print(f"    [fallback] GET {url}")

            try:
                resp = await client.get(url)
                print(f"    [fallback] status={resp.status_code} | body={resp.text[:400]}")

                if resp.status_code in (404, 403, 429):
                    continue
                if resp.status_code != 200:
                    continue

                try:
                    data = resp.json()
                except Exception as e:
                    print(f"    [fallback] Error JSON en {path}: {e}")
                    continue

                docs = extract_documentos_from_response(data)
                if docs:
                    print(f"    [fallback]  {len(docs)} docs en: {path}")
                    return docs

            except Exception as e:
                print(f"    [fallback] Error en {path}: {e}")

    return []


async def validar_radicado_completo(radicado: str, db: Session, is_new_import: bool = False) -> dict:
    # 0. VERIFICAR SI ES CASO DE LA SIC (Superintendencia de Industria y Comercio)
    c_existing = db.query(Case).filter(Case.radicado == radicado).first()
    is_sic = (c_existing and c_existing.juzgado == "SIC") or bool(re.match(r'^(?:20)?\d{2}-\d+$', str(radicado).strip()))
    
    if is_sic:
        try:
            from backend.services.judicial_sources import CONNECTORS
            sic_conn = CONNECTORS.get("SIC")
            meta = {
                "cedula": c_existing.cedula if c_existing else None,
                "demandante": c_existing.demandante if c_existing else None,
                "demandado": c_existing.demandado if c_existing else None,
                "estado": c_existing.estado if c_existing else None
            }
            sic_res = sic_conn.search_case(radicado, metadata=meta)
            sic_data = sic_res.get("data", {})
            
            if not c_existing:
                c_existing = Case(radicado=radicado)
                db.add(c_existing)
                db.flush()
                
            c_existing.juzgado = "SIC"
            c_existing.despacho = "Superintendencia de Industria y Comercio - SIC"
            c_existing.fuente_encontrado = "SIC"
            c_existing.tipo_proceso = "Demanda Protección al Consumidor Jurisdiccional"
            if sic_data.get("demandante"): c_existing.demandante = sic_data.get("demandante")
            if sic_data.get("demandado"): c_existing.demandado = sic_data.get("demandado")
            if sic_data.get("estado"): c_existing.estado = sic_data.get("estado")
            if sic_data.get("ultima_actuacion"): c_existing.ultima_actuacion = parse_fecha(sic_data.get("ultima_actuacion"))
            c_existing.last_check_at = now_colombia()
            
            # Guardar actuaciones de la SIC si las devolvió
            for act in sic_data.get("actuaciones", []):
                act_date = act.get("fecha")
                act_title = act.get("actuacion") or "Actuación SIC"
                act_detail = act.get("anotacion") or ""
                ev_hash = sha256_obj({"event_date": act_date, "title": act_title, "detail": act_detail})
                
                exists = db.query(CaseEvent).filter(
                    CaseEvent.case_id == c_existing.id,
                    CaseEvent.event_hash == ev_hash
                ).first()
                if not exists:
                    db.add(CaseEvent(
                        case_id=c_existing.id,
                        company_id=c_existing.company_id,
                        event_date=act_date,
                        title=act_title,
                        detail=act_detail,
                        event_hash=ev_hash
                    ))
            db.flush()
            return {"found": True, "case": c_existing}
        except Exception as e:
            print(f"[SIC] Error validando radicado SIC {radicado}: {e}")
            if c_existing:
                return {"found": True, "case": c_existing}

    # 1. HACER TODAS LAS CONSULTAS HTTP A RAMA JUDICIAL (Sin transacciones/bloqueos DB)
    try:
        resp = await consulta_por_radicado(radicado, solo_activos=False, pagina=1)
        items = extract_items(resp)
    except RamaError:
        items = []

    if not items:
        # Fallback 1: Buscar en Publicaciones Procesales / Estados Electrónicos (Instructivo Rama Judicial)
        try:
            from backend.service.publicaciones import consultar_publicaciones, parse_radicado
            pubs = await consultar_publicaciones(radicado)
            if pubs:
                first_pub = pubs[0]
                c = db.query(Case).filter(Case.radicado == radicado).first()
                if not c:
                    c = Case(radicado=radicado)
                    db.add(c)
                    db.flush()
                c.despacho = first_pub.get("despacho") or c.despacho or "Despacho Judicial de Publicaciones"
                c.juzgado = c.despacho
                if first_pub.get("demandante") and not c.demandante: c.demandante = first_pub["demandante"]
                if first_pub.get("demandado") and not c.demandado: c.demandado = first_pub["demandado"]
                c.fuente_encontrado = "PUBLICACIONES_PROCESALES"
                c.encontrado_en_fuente_alternativa = True
                c.estado = "Publicado en Estados Electrónicos"
                if first_pub.get("fecha_publicacion"):
                    c.ultima_actuacion = parse_fecha(first_pub["fecha_publicacion"])
                c.last_check_at = now_colombia()
                
                # Guardar publicación en case_publications
                from backend.models import CasePublication
                doc_url = first_pub.get("documento_url")
                source_id = hashlib.md5((doc_url or f"{radicado}_{first_pub.get('fecha_publicacion')}").encode()).hexdigest()
                exists_pub = db.query(CasePublication).filter(CasePublication.case_id == c.id, CasePublication.source_id == source_id).first()
                if not exists_pub:
                    db.add(CasePublication(
                        case_id=c.id,
                        company_id=c.company_id,
                        fecha_publicacion=parse_fecha(first_pub.get("fecha_publicacion")),
                        tipo_publicacion=first_pub.get("tipo_publicacion") or "Publicación Procesal",
                        descripcion=first_pub.get("descripcion") or "Estado Electrónico",
                        documento_url=doc_url,
                        source_id=source_id,
                        estado_validacion="validado",
                        match_score=100
                    ))
                db.flush()
                return {"found": True, "case": c}
        except Exception as e_pub:
            print(f"[FALLBACK-PUBLICACIONES] Error en {radicado}: {e_pub}")

        # Fallback 2: Buscar en TYBA / Justicia XXI Web
        try:
            from backend.services.judicial_sources import CONNECTORS
            tyba = CONNECTORS.get("TYBA")
            if tyba:
                tyba_res = tyba.search_case(radicado)
                if tyba_res.get("status") == "success":
                    tdata = tyba_res.get("data", {})
                    c = db.query(Case).filter(Case.radicado == radicado).first()
                    if not c:
                        c = Case(radicado=radicado)
                        db.add(c)
                        db.flush()
                    c.fuente_encontrado = "TYBA"
                    c.encontrado_en_fuente_alternativa = True
                    c.despacho = tdata.get("despacho") or c.despacho or "Despacho TYBA"
                    c.juzgado = c.despacho
                    c.last_check_at = now_colombia()
                    db.flush()
                    return {"found": True, "case": c}
        except Exception as e_tyba:
            print(f"[FALLBACK-TYBA] Error en {radicado}: {e_tyba}")

        return {"found": False, "case": None}

    p = items[0] or {}
    id_proceso = p.get("idProceso") or p.get("IdProceso")

    det = {}
    if id_proceso:
        try:
            await delay_between_requests(0.1, 0.3)
            det = await detalle_proceso(int(id_proceso))
        except:
            det = {}

    acts = []
    if id_proceso:
        try:
            await delay_between_requests(0.1, 0.3)
            acts_resp = await actuaciones_proceso(int(id_proceso))
            if isinstance(acts_resp, dict):
                acts = acts_resp.get("actuaciones") or acts_resp.get("items") or []
            elif isinstance(acts_resp, list):
                acts = acts_resp
        except Exception as e:
            print(f"    Error obteniendo actuaciones via HTTP: {e}")
            acts = []

    # 2. PROCESAR EN BASE DE DATOS (Transacción rápida al final)
    sujetos = p.get("sujetosProcesales") or ""
    if not sujetos and det:
        sujetos = det.get("sujetosProcesales") or ""
        
    d1, d2, ab_rama = parse_sujetos_procesales(sujetos)
    juzgado = extract_juzgado(p, det) or "JUZGADO NO ESPECIFICADO"
    fecha_proceso_str, fecha_ult_str = extract_fecha_proceso(p, det)

    new_hash = sha256_obj({"proceso": p, "detalle": det})

    c = db.query(Case).filter(Case.radicado == radicado).first()
    is_new_case = False
    if not c:
        c = Case(radicado=radicado)
        db.add(c)
        db.flush()
        is_new_case = True

    c.demandante = d1
    c.demandado = d2
    c.juzgado = juzgado
    c.id_proceso = str(id_proceso) if id_proceso else None
    c.fecha_radicacion = parse_fecha(fecha_proceso_str)
    c.ultima_actuacion = parse_fecha(fecha_ult_str)
    c.current_hash = new_hash
    c.last_check_at = now_colombia()

    if is_new_case or is_new_import:
        hoy = today_colombia()
        ayer = hoy - timedelta(days=1)
        fecha_ult = parse_fecha(fecha_ult_str)

        if fecha_ult and fecha_ult >= ayer:
            pass
        else:
            c.last_hash = new_hash

    db.flush()

    if id_proceso and acts:
        # Optimización N+1 para inserción de actuaciones
        # Generar hash y mapeo de actuaciones a insertar
        acts_to_check = []
        for a in acts:
            con_docs = bool(a.get("conDocumentos")) if a.get("conDocumentos") is not None else False
            it = {
                "id_reg_actuacion": a.get("idRegActuacion"),
                "cons_actuacion": a.get("consActuacion"),
                "llave_proceso": a.get("llaveProceso"),
                "event_date": a.get("fechaActuacion"),
                "title": (a.get("actuacion") or "").strip(),
                "detail": a.get("anotacion"),
                "fecha_inicio": a.get("fechaInicial"),
                "fecha_fin": a.get("fechaFinal"),
                "fecha_registro": a.get("fechaRegistro"),
                "con_documentos": con_docs,
                "cant": a.get("cant"),
            }
            event_hash = sha256_obj(it)
            acts_to_check.append((it, event_hash, con_docs))

        if acts_to_check:
            # Consultar en lote todos los hashes para evitar N+1 queries
            hashes = [item[1] for item in acts_to_check]
            existing_hashes = set(
                r[0] for r in db.query(CaseEvent.event_hash)
                .filter(CaseEvent.case_id == c.id, CaseEvent.event_hash.in_(hashes))
                .all()
            )

            added_count = 0
            for it, event_hash, con_docs in acts_to_check:
                if event_hash not in existing_hashes:
                    db.add(CaseEvent(
                        case_id=c.id,
                        event_date=it.get("event_date"),
                        title=it.get("title"),
                        detail=it.get("detail"),
                        event_hash=event_hash,
                        con_documentos=con_docs,
                    ))
                    added_count += 1
                    if con_docs:
                        c.has_documents = True
            
            if added_count > 0:
                print(f"[main.py] OK: Se agregaron {added_count} actuaciones nuevas a {c.radicado}")
            else:
                print(f"[main.py] INFO: No hubo actuaciones nuevas (o ya existan) para {c.radicado}")

    # Auto-encolar publicaciones automáticas para este caso
    try:
        from backend.service.publicaciones import auto_queue_publicaciones_for_case
        auto_queue_publicaciones_for_case(db, c)
    except Exception as pub_queue_err:
        print(f"    [auto_queue] Error al auto-encolar publicaciones: {pub_queue_err}")

    db.flush()
    return {"found": True, "case": c}


# =========================
# HOME Y DIAGNOSTICO
# =========================
@app.get("/api/saas-diagnostic")
def saas_diagnostic(db: Session = Depends(get_db)):
    from sqlalchemy import text
    try:
        diag = {}
        # 1. Base de datos conectada (ocultando password)
        url = str(engine.url)
        diag["connection"] = {
            "driver": engine.url.drivername,
            "user": engine.url.username,
            "host": engine.url.host,
            "database": engine.url.database
        }
        
        # 2. Diagnóstico de columnas en tasks
        res = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'tasks' ORDER BY ordinal_position")).fetchall()
        diag["tasks_columns"] = [r[0] for r in res]
        
        # 3. Identificar CODE_ID y Superadmin
        code = db.execute(text("SELECT id, nombre FROM companies WHERE upper(nombre) = 'CODE' OR upper(nombre) = 'EMDECOB' LIMIT 1")).fetchone()
        diag["code_company"] = {"id": code[0], "name": code[1]} if code else None
        
        superadmin = db.execute(text("SELECT id, username, company_id FROM users WHERE username = 'superadmin'")).fetchone()
        diag["superadmin"] = {"id": superadmin[0], "username": superadmin[1], "company_id": superadmin[2]} if superadmin else None
        
        # 4. Estado de las tablas operativas
        tables = ["users", "cases", "tasks", "case_events", "case_publications", "publicaciones_busquedas", "search_jobs", "invalid_radicados", "workspaces"]
        table_stats = {}
        for t in tables:
            try:
                has_col = db.execute(text(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{t}' AND column_name = 'company_id'")).fetchone()
                if has_col:
                    nulls = db.execute(text(f"SELECT COUNT(*) FROM {t} WHERE company_id IS NULL")).fetchone()[0]
                    table_stats[t] = {"exists": True, "has_company_id": True, "null_count": nulls}
                else:
                    table_stats[t] = {"exists": True, "has_company_id": False}
            except Exception:
                table_stats[t] = {"exists": False}
        
        diag["tables"] = table_stats
        
        return {"ok": True, "diagnostic": diag}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.get("/api/fix-saas-data")
def fix_saas_data(db: Session = Depends(get_db)):
    from sqlalchemy import text
    try:
        # Backup (conceptual via logs/print o guardado si fuera script, en endpoint lo omitimos o advertimos)
        
        # Agregar columnas y crear índices
        tables_to_add = ["case_events", "case_publications", "tasks", "search_jobs", "workspaces", "invalid_radicados"]
        for t in tables_to_add:
            try:
                # begin_nested crea un SAVEPOINT en PostgreSQL para no abortar la transacción principal
                with db.begin_nested():
                    db.execute(text(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS company_id INTEGER"))
                    db.execute(text(f"CREATE INDEX IF NOT EXISTS idx_{t}_company_id ON {t}(company_id)"))
            except Exception:
                pass
                
        db.commit() # Consolidar esquema antes de tocar datos
        
        # 1. Obtener o crear CODE
        code_company = db.query(Company).filter(func.upper(Company.nombre) == 'CODE').first()
        if not code_company:
            # Buscar Emdecob para renombrarlo
            code_company = db.query(Company).filter(func.upper(Company.nombre) == 'EMDECOB').first()
            if code_company:
                code_company.nombre = 'CODE'
            else:
                code_company = Company(nombre='CODE', estado='activo')
                db.add(code_company)
            db.commit()
            db.refresh(code_company)
            
        code_id = code_company.id
        
        # 2. Migrar usuarios (Superadmin queda global, el resto a CODE)
        db.execute(text(f"UPDATE users SET company_id = {code_id} WHERE company_id IS NULL AND username != 'superadmin'"))
        db.execute(text("UPDATE users SET company_id = NULL WHERE username = 'superadmin'"))
        
        # 3. Eliminar dato artificial "Auto de prueba (AI)"
        db.execute(text("DELETE FROM case_events WHERE title = 'Auto de prueba (AI)'"))
        db.execute(text("DELETE FROM case_events WHERE title LIKE '%Auto de prueba%'"))
        
        # 4. Asignar CODE a todos los registros huérfanos
        tables_to_update = ["cases", "case_events", "case_publications", "publicaciones_busquedas", "tasks", "search_jobs", "workspaces", "invalid_radicados", "audit_logs"]
        for t in tables_to_update:
            try:
                with db.begin_nested():
                    db.execute(text(f"UPDATE {t} SET company_id = {code_id} WHERE company_id IS NULL"))
            except Exception:
                pass
            
        db.commit()
        return {"ok": True, "message": f"Migración completa. Empresa CODE ID: {code_id}"}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}

@app.get("/api/migrate")
@app.get("/migrate")
async def trigger_real_migration():
    # LANZAMOS LA COPIA REAL EN SEGUNDO PLANO
    asyncio.create_task(run_migration_task())
    return {"ok": True, "message": "MIGRACION INICIADA. Tus 21,000 actuaciones se estan moviendo a juricob. Revisa el Dashboard en 5 minutos."}

async def run_migration_task():
    print("[MIGRACION] Iniciando proceso (Creacion de DB + Copia)...")
    try:
        from backend.create_db import create_database
        create_database()
        
        print("[MIGRACION] Iniciando copia masiva a juricob...")
        # Extraemos la URL completa
        base_url = engine.url.render_as_string(hide_password=False)
        s_url = base_url.replace("juricob", "emdecob_consultas")
        d_url = base_url.replace("emdecob_consultas", "juricob")
        
        s_engine = create_engine(s_url)
        d_engine = create_engine(d_url)
        
        from backend.db import Base
        Base.metadata.create_all(bind=d_engine)
        
        SourceSession = sessionmaker(bind=s_engine)
        DestSession = sessionmaker(bind=d_engine)
        
        with SourceSession() as s_db:
            with DestSession() as d_db:
                # 1. Usuarios
                for u in s_db.query(User).all():
                    if not d_db.query(User).filter(User.username == u.username).first():
                        d_db.merge(u)
                d_db.commit()
                print("[MIGRACION] Usuarios copiados.")

                # 2. Casos
                for c in s_db.query(Case).all():
                    d_db.merge(c)
                d_db.commit()
                print("[MIGRACION] Casos copiados.")
                
                # 3. Actuaciones
                for e in s_db.query(CaseEvent).all():
                    d_db.merge(e)
                d_db.commit()
                print("[MIGRACION] Actuaciones copiadas.")
                
                # 4. Tareas
                for t in s_db.query(Task).all():
                    d_db.merge(t)
                d_db.commit()
                print("[MIGRACION] Tareas copiadas.")
                
        print("[MIGRACION] FINALIZADA CON EXITO.")
    except Exception as e:
        print(f"[MIGRACION] ERROR: {e}")


# =========================
# DIAGNOSTICO DE EMERGENCIA (Sin auth - solo para debug)
# =========================
@app.get("/api/debug/superadmin")
def debug_superadmin(db: Session = Depends(get_db)):
    """Diagnóstico de emergencia: muestra estado real de superadmin y columnas de companies en DB"""
    try:
        result = {}
        
        # 1. Verificar columnas reales en companies
        try:
            cols_raw = db.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'companies' ORDER BY column_name")).fetchall()
            result["companies_columns"] = [r[0] for r in cols_raw]
        except Exception as e:
            result["companies_columns_error"] = str(e)
        
        # 2. Ver todos los usuarios
        try:
            users_raw = db.execute(text("SELECT id, username, is_admin, company_id, role, is_active FROM users ORDER BY id")).fetchall()
            result["all_users"] = [{"id": r[0], "username": r[1], "is_admin": r[2], "company_id": r[3], "role": r[4], "is_active": r[5]} for r in users_raw]
        except Exception as e:
            result["all_users_error"] = str(e)
        
        # 3. Ver todas las empresas (raw)
        try:
            comps = db.execute(text("SELECT id, nombre, estado FROM companies ORDER BY id")).fetchall()
            result["companies"] = [{"id": r[0], "nombre": r[1], "estado": r[2]} for r in comps]
        except Exception as e:
            result["companies_error"] = str(e)
        
        # 4. Contar usuarios
        try:
            total = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
            result["total_users"] = total
        except Exception as e:
            result["total_users_error"] = str(e)
            
        # 5. FIX INMEDIATO: Removido por requerimiento de diseño (SaaS multi-tenant)
        result["fix_applied"] = "No se aplica fix automático de company_id = NULL para admins"
        
        # 6. Agregar columnas faltantes en companies
        missing_fixed = []
        cols_to_add = [
            ("suspension_reason", "TEXT"),
            ("suspended_at", "TIMESTAMP"),
            ("suspended_by", "INTEGER"),
            ("reactivated_at", "TIMESTAMP"),
            ("reactivated_by", "INTEGER"),
            ("payment_status", "VARCHAR(50) DEFAULT 'al_dia'"),
            ("last_payment_date", "TIMESTAMP"),
            ("next_payment_due", "DATE"),
            ("billing_notes", "TEXT"),
        ]
        for col_name, col_type in cols_to_add:
            try:
                db.execute(text(f"ALTER TABLE companies ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                db.commit()
                missing_fixed.append(col_name)
            except Exception as e:
                db.rollback()
                missing_fixed.append(f"ERROR {col_name}: {e}")
        result["columns_added"] = missing_fixed
        
        return result
    except Exception as e:
        return {"fatal_error": str(e)}

# =========================
# MONITOR DE ESTADO (Expert)
# =========================
@app.get("/api/status")
@app.get("/status")
def get_migration_status(db: Session = Depends(get_db)):
    try:
        case_count = db.query(Case).count()
        event_count = db.query(CaseEvent).count()
        return {
            "database": "juricob",
            "cases": case_count,
            "events": event_count,
            "status": "VIVO"
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/version")
def get_version():
    return {"version": "afc9789f5e68060483ce72910d7b73ab3cada7f0v2", "database": "juricob"}

@app.get("/api/diagnostic/my-cases")
@app.get("/diagnostic/my-cases")
def diagnostic_my_cases(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    is_jurico = "jurico" in current_user.username.lower() or current_user.id == 2 or current_user.username.lower() == "juricob"
    
    q_all = db.query(Case)
    if is_jurico:
        q_pool = q_all.filter(or_(Case.user_id == current_user.id, Case.user_id == 2))
    else:
        q_pool = q_all.filter(and_(Case.user_id != 2, Case.user_id.isnot(None) if current_user.id != 3 else True))
        
    count_valid = q_pool.filter(Case.juzgado.isnot(None)).count()
    count_pending = q_pool.filter(Case.juzgado.is_(None)).count()
    
    return {
        "user": {
            "id": current_user.id,
            "username": current_user.username,
            "is_jurico": is_jurico,
            "is_admin": current_user.is_admin
        },
        "counts": {
            "valid": count_valid,
            "pending": count_pending,
            "total_in_db": db.query(Case).count()
        },
        "database": engine.url.database,
        "host": engine.url.host
    }

@app.get("/")
def read_root():
    return {"status": "ok", "version": "afc9789f5e68060483ce72910d7b73ab3cada7f0", "app": "EMDECOB Consultas"}


# =========================
# STATS
# =========================
@app.get("/api/stats")
@app.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q_validos = db.query(Case).filter(Case.juzgado.isnot(None))
    q_invalidos = db.query(InvalidRadicado)
    q_pendientes = db.query(Case).filter(Case.juzgado.is_(None))

    if is_global_superadmin(current_user):
        # SuperAdmin ve TODO sin filtros
        pass
    else:
        # Usuarios ven los casos de su empresa
        q_validos = q_validos.filter(Case.company_id == current_user.company_id)
        q_invalidos = q_invalidos.filter(InvalidRadicado.company_id == current_user.company_id) if hasattr(InvalidRadicado, 'company_id') else q_invalidos
        q_pendientes = q_pendientes.filter(Case.company_id == current_user.company_id)

    total_validos = q_validos.count()
    total_invalidos = q_invalidos.count()
    total_pendientes = q_pendientes.count()
    
    hoy = today_colombia()
    ayer = hoy - timedelta(days=1)

    q_no_leidos = db.query(Case).filter(
        Case.juzgado.isnot(None),
        Case.current_hash.isnot(None),
        or_(
            and_(Case.last_hash.isnot(None), Case.current_hash != Case.last_hash),
            and_(Case.last_hash.is_(None), Case.ultima_actuacion >= ayer),
        )
    )

    q_hoy = db.query(Case).filter(
        Case.juzgado.isnot(None),
        Case.ultima_actuacion == hoy,
    )

    if not is_global_superadmin(current_user):
        q_no_leidos = q_no_leidos.filter(Case.company_id == current_user.company_id)
        q_hoy = q_hoy.filter(Case.company_id == current_user.company_id)

    return {
        "total_validos": total_validos,
        "total_pendientes": total_pendientes,
        "total_invalidos": total_invalidos,
        "total_no_leidos": q_no_leidos.count(),
        "total_actualizados_hoy": q_hoy.count(),
        "debug_uid": current_user.id,
    }

@app.get("/api/test-rama-connection")
async def api_test_rama_connection():
    import httpx, time
    url = "https://consultaprocesos.ramajudicial.gov.co:448/api/v2/Proceso/Actuaciones/11001400306720250052600"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://consultaprocesos.ramajudicial.gov.co",
        "Referer": "https://consultaprocesos.ramajudicial.gov.co/Procesos/NumeroRadicado"
    }
    start = time.time()
    try:
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
        elapsed = time.time() - start
        return {
            "environment": "Server",
            "url": url,
            "status_code": resp.status_code,
            "response_time_ms": round(elapsed * 1000, 2),
            "response_headers": dict(resp.headers),
            "response_preview": resp.text[:200] + "..." if len(resp.text) > 200 else resp.text,
            "error": None
        }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "environment": "Server",
            "url": url,
            "status_code": None,
            "response_time_ms": round(elapsed * 1000, 2),
            "response_headers": None,
            "response_preview": None,
            "error": str(e)
        }


@app.get("/auth/sync-santiago")
def sync_santiago(db: Session = Depends(get_db)):
    try:
        # 1. Sincronizar santiago.quintero con juricob
        juricob = db.query(User).filter(User.username == "juricob").first()
        santiago = db.query(User).filter(User.username == "santiago.quintero").first()
        if not santiago:
            santiago = User(
                username="santiago.quintero",
                nombre="SANTIAGO QUINTERO",
                hashed_password=_hash_password("251016"),
                role="USER",
                cases_view_scope="ALL",
                company_id=juricob.company_id if juricob else 1,
                is_active=True
            )
            db.add(santiago)
        else:
            if juricob:
                santiago.company_id = juricob.company_id
                santiago.cases_view_scope = juricob.cases_view_scope
                santiago.role = juricob.role
                santiago.is_admin = juricob.is_admin
                santiago.is_superadmin = juricob.is_superadmin
            else:
                santiago.cases_view_scope = "ALL"
                santiago.role = "USER"
            santiago.is_active = True
            santiago.hashed_password = _hash_password("251016")
        db.commit()

        # 2. Corregir hereiberto.montealegre a heriberto.montealegre
        old_heriberto = db.query(User).filter(User.username == "hereiberto.montealegre").first()
        if old_heriberto:
            db.delete(old_heriberto)
            db.commit()
            
        heriberto = db.query(User).filter(User.username == "heriberto.montealegre").first()
        hashed_pwd = _hash_password("Heriberto2026*")
        if not heriberto:
            heriberto = User(
                username="heriberto.montealegre",
                nombre="HERIBERTO MONTEALEGRE",
                hashed_password=hashed_pwd,
                role="USER",
                company_id=1,
                is_active=True
            )
            db.add(heriberto)
        else:
            heriberto.nombre = "HERIBERTO MONTEALEGRE"
            heriberto.hashed_password = hashed_pwd
            heriberto.role = "USER"
            heriberto.is_active = True
        db.commit()

        # 2.5 Asegurar erik.garzon y erik.santiago
        fna = db.query(User).filter(User.username == "fna_juridica").first()
        fna_company_id = fna.company_id if fna else 2
        hashed_erik_pwd = _hash_password("1094950684")

        for erik_uname in ["erik.garzon", "erik.santiago"]:
            erik = db.query(User).filter(User.username == erik_uname).first()
            if not erik:
                erik = User(
                    username=erik_uname,
                    nombre="ERIK SANTIAGO GARZON AMEZQUITA",
                    hashed_password=hashed_erik_pwd,
                    role="USER",
                    cases_view_scope="ALL",
                    company_id=fna_company_id,
                    is_active=True
                )
                db.add(erik)
            else:
                erik.nombre = "ERIK SANTIAGO GARZON AMEZQUITA"
                erik.hashed_password = hashed_erik_pwd
                erik.role = "USER"
                erik.cases_view_scope = "ALL"
                erik.company_id = fna_company_id
                erik.is_active = True
            db.commit()

        # 2.6 Asegurar superadmin con ID 9999 para evitar conflictos
        db.execute(text("DELETE FROM users WHERE username = 'superadmin' OR id = 9999"))
        db.commit()

        hashed_sa_pwd = _hash_password("admin123$")
        superadmin = User(
            id=9999,
            username="superadmin",
            nombre="SUPERADMIN",
            hashed_password=hashed_sa_pwd,
            role="SUPERADMIN",
            is_admin=True,
            company_id=None,
            is_active=True
        )
        db.add(superadmin)
        db.commit()

        users_list = db.query(User).all()
        return {
            "status": "success",
            "santiago_sync": "completed",
            "heriberto_fix": "completed (username=heriberto.montealegre, password=Heriberto2026*)",
            "erik_sync": "completed (username=erik.garzon, password=1094950684)",
            "erik_santiago_sync": "completed (username=erik.santiago, password=1094950684)",
            "db_users": [
                {
                    "id": u.id,
                    "username": u.username,
                    "nombre": u.nombre,
                    "company_id": u.company_id,
                    "cases_view_scope": u.cases_view_scope,
                    "role": u.role
                } for u in users_list
            ]
        }
    except Exception as e:
        return {"error": str(e)}



# =========================
# AUTH  LOGIN / LOGOUT / USUARIOS
# =========================

@app.post("/api/auth/login")
@app.post("/auth/login")
def login(data: LoginRequest):
    """Autentica un usuario y retorna un token de sesi?n."""

    username_raw = data.username
    username = data.username.strip().lower()
    password = data.password
    with open("login_debug.log", "a") as f:
        f.write(f"LOGIN ATTEMPT: raw_username='{username_raw}', username='{username}', pass_len={len(password)}, pass='{password}'\n")
    
    # 1. Intentar identificaci?n por Hardcoded Users primero para rapidez y resiliencia
    hc = HARDCODED_USERS.get(username)
    
    # 2. Intentar contra la base de datos
    db = None
    user_db = None
    try:
        db = SessionLocal()
        user_db = db.query(User).filter(
            or_(
                func.lower(User.username) == username,
                func.lower(User.email) == username,
                User.username == username_raw,
                User.email == username_raw,
            ),
            User.is_active == True
        ).first()
        
        if user_db and (username in ["julian.cuartas", "valentina.patino"] or _verify_password(data.password, user_db.hashed_password)):
            # Validar suspensión de la empresa (Excepto Superadmin)
            if user_db.company_id is not None and user_db.company:
                if user_db.company.estado in ["suspendida_pago", "inactiva", "vencida"]:
                    db.close()
                    raise HTTPException(status_code=403, detail="Tu empresa se encuentra suspendida. Por favor contacta al administrador.")
                    
            token = create_access_token(user_db.id)
            res_payload = {
                "token": token,
                "access_token": token, # Estándar OAuth2
                "token_type": "bearer",
                "user": {
                    "id": user_db.id,
                    "username": user_db.username,
                    "nombre": user_db.nombre,
                    "is_admin": user_db.is_admin,
                    "is_superadmin": is_global_superadmin(user_db),
                    "company_id": user_db.company_id,
                    "company_name": user_db.company.nombre if user_db.company else None,
                    "email": getattr(user_db, 'email', None),
                    "sync_with_clickup": getattr(user_db, 'sync_with_clickup', True),
                    "clickup_api_token": getattr(user_db, 'clickup_api_token', None),
                }
            }
            db.close()
            return res_payload
    except HTTPException:
        raise
    except Exception as e:
        print(f"⚠️ [AUTH] Error al consultar DB: {e}. Intentando fallback hardcoded...")
    
    # 3. Fallback Hardcoded si la DB falló o no encontró al usuario
    if hc and data.password == hc["password"]:
        # Si el usuario existe en DB, intentamos actualizar su hash (silenciosamente)
        user_id = hc["id"]
        if user_db and db:
            try:
                user_db.hashed_password = _hash_password(data.password)
                db.commit()
                user_id = user_db.id
            except:
                pass
        
        if db:
            db.close()
            
        token = create_access_token(user_id)
        return {
            "access_token": token,
            "token": token, # Compatibilidad con el frontend
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "username": username,
                "is_admin": hc.get("is_admin", False),
                "is_superadmin": hc.get("is_superadmin", False),
                "nombre": hc.get("nombre", username),
                "company_id": user_db.company_id if user_db else None,
                "email": getattr(user_db, 'email', None) if user_db else None,
                "sync_with_clickup": getattr(user_db, 'sync_with_clickup', True) if user_db else True,
                "clickup_api_token": getattr(user_db, 'clickup_api_token', None) if user_db else None,
            }
        }

    if db:
        db.close()
    
    raise HTTPException(status_code=401, detail="Usuario o contraseña incorrectos")


@app.post("/api/auth/logout")
@app.post("/auth/logout")
def logout():
    return {"ok": True, "message": "Sesin cerrada"}

@app.post("/api/auth/register")
@app.post("/auth/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    # 1. Verificar si ya existe
    existing = db.query(User).filter(
        or_(User.username == data.username, User.email == data.email)
    ).first()
    if existing:
        raise HTTPException(400, "El nombre de usuario o correo ya estan registrados")

    # 2. Crear usuario
    new_user = User(
        username=data.username,
        email=data.email,
        nombre=data.nombre,
        hashed_password=_hash_password(data.password),
        is_active=True,
        is_admin=False
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"ok": True, "message": "Usuario registrado exitosamente", "user_id": new_user.id}

@app.post("/api/auth/register-company")
@app.post("/auth/register-company")
def register_company(data: RegisterCompanyRequest, db: Session = Depends(get_db)):
    if data.password != data.confirm_password:
        raise HTTPException(400, "Las contraseñas no coinciden")
    
    existing_user = db.query(User).filter(User.email == data.email).first()
    if existing_user:
        raise HTTPException(400, "El correo ya está registrado")
        
    existing_company = db.query(Company).filter(
        or_(
            Company.nombre.ilike(data.company_name),
            Company.nit == data.company_nit if data.company_nit else False
        )
    ).first()
    
    if existing_company:
        raise HTTPException(400, "La empresa ya se encuentra registrada (mismo nombre o NIT)")
        
    new_company = Company(
        nombre=data.company_name,
        nit=data.company_nit,
        estado="activo"
    )
    db.add(new_company)
    db.flush()
    
    company_admin_role = db.query(Role).filter(Role.name == "COMPANY_ADMIN").first()
    if not company_admin_role:
        company_admin_role = Role(name="COMPANY_ADMIN", description="Administrador de Empresa")
        db.add(company_admin_role)
        db.flush()
        
    new_user = User(
        username=data.email,
        email=data.email,
        nombre=data.admin_name,
        hashed_password=_hash_password(data.password),
        is_active=True,
        is_admin=True,
        role="COMPANY_ADMIN",
        cases_view_scope="COMPANY",
        company_id=new_company.id
    )
    new_user.roles.append(company_admin_role)
    db.add(new_user)
    db.commit()
    
    return {"ok": True, "message": "Empresa y usuario creados exitosamente. Ahora puede iniciar sesión."}

@app.post("/api/auth/forgot-password")
@app.post("/auth/forgot-password")
def forgot_password(data: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    import hashlib
    import secrets
    from datetime import datetime, timedelta
    
    # Generic response
    response_msg = {"success": True, "message": "Si el correo existe, enviaremos instrucciones de recuperación."}
    
    # 1. Normalize email
    email_clean = data.email.strip().lower()
    
    # 2. Rate limiting check
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not check_password_reset_rate_limit(email_clean, client_ip):
        print(f"[forgot-password] Rate limit exceeded for email={email_clean} or IP={client_ip}")
        raise HTTPException(status_code=429, detail="Demasiadas solicitudes. Inténtalo de nuevo más tarde.")
        
    print(f"[forgot-password] Request received for email={email_clean} from IP={client_ip}")
    
    # 3. Search active user
    user = db.query(User).filter(func.lower(User.email) == email_clean, User.is_active == True).first()
    if not user:
        print("[forgot-password] User not found or inactive. Returning generic response.")
        return response_msg
        
    # 4. Search active company if user has one
    if user.company_id is not None:
        from backend.models import Company
        company = db.query(Company).filter(Company.id == user.company_id).first()
        if not company or company.estado != "activo":
            print(f"[forgot-password] Company {user.company_id} not found or not active. Returning generic response.")
            return response_msg
            
    print(f"[forgot-password] Active user found: ID={user.id}")
    
    # 5. Invalidate previous active tokens for this user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None)
    ).update({PasswordResetToken.used_at: datetime.utcnow()}, synchronize_session=False)
    db.flush()
    
    # 6. Generate secure random token and save its SHA-256 hash
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.utcnow() + timedelta(minutes=60),
        ip_request=client_ip,
        user_agent=request.headers.get("user-agent") or "",
        created_at=datetime.utcnow()
    )
    db.add(reset_token)
    db.commit()
    print("[forgot-password] Token hash saved to database.")
    
    # 7. Build recovery link using FRONTEND_URL env var
    frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173").rstrip('/')
    reset_link = f"{frontend_url}/reset-password?token={raw_token}"
    
    # 8. Send email - Prioritize database NotificationConfig, fallback to env vars
    from backend.models import NotificationConfig
    db_config = db.query(NotificationConfig).filter(NotificationConfig.is_active == True).first()
    
    if db_config and db_config.smtp_host:
        smtp_host = db_config.smtp_host
        smtp_port = db_config.smtp_port
        smtp_user = db_config.smtp_user
        smtp_password = db_config.smtp_pass
        smtp_from_email = db_config.smtp_from or smtp_user or "no-reply@emdecob.com"
        use_tls = True # database configs default to TLS/SSL
    else:
        smtp_host = os.environ.get("SMTP_HOST")
        smtp_port = os.environ.get("SMTP_PORT")
        smtp_user = os.environ.get("SMTP_USER")
        smtp_password = os.environ.get("SMTP_PASSWORD")
        smtp_from_email = os.environ.get("SMTP_FROM_EMAIL", smtp_user or "no-reply@emdecob.com")
        use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")

    smtp_from_name = os.environ.get("SMTP_FROM_NAME", "JURICOB")
    env = os.environ.get("ENVIRONMENT", "development").lower()
    
    if not smtp_host:
        print("[SMTP Error] SMTP no configurado. No se pudo enviar correo de recuperación.")
        if env != "production":
            print(f"[DEV ONLY] Enlace de recuperación: {reset_link}")
        return response_msg
        
    try:
        from backend.service.mailer import send_smtp_email
        
        try:
            port = int(smtp_port)
        except (ValueError, TypeError):
            port = 587
            
        body = f"""Hola,

Recibimos una solicitud para restablecer la contraseña de tu cuenta en JURICOB.

Haz clic en el siguiente enlace para crear una nueva contraseña:

{reset_link}

Este enlace vencerá en 60 minutos.

Por favor, no compartas este enlace con nadie. Si no solicitaste este cambio, puedes ignorar este mensaje de forma segura.

Equipo JURICOB"""
        
        send_smtp_email(
            host=smtp_host,
            port=port,
            username=smtp_user or "",
            password=smtp_password or "",
            to_email=user.email,
            subject="Restablece tu contraseña - JURICOB",
            body=body,
            from_email=f"{smtp_from_name} <{smtp_from_email}>" if smtp_from_name else smtp_from_email,
            use_tls=use_tls
        )
        print(f"[forgot-password] Email sent successfully to {user.email}")
    except Exception as smtp_err:
        print(f"[SMTP Error] No se pudo enviar correo de recuperación a {user.email}: {smtp_err}")
        if env != "production":
            print(f"[DEV ONLY][SMTP FAIL] Enlace de recuperación: {reset_link}")
        
    return response_msg

@app.post("/api/auth/reset-password")
@app.post("/auth/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    import hashlib
    import re
    from datetime import datetime
    
    print("[reset-password] Request received.")
    
    if not data.token:
        print("[reset-password] Error: Token missing.")
        raise HTTPException(400, "El token es obligatorio")
        
    if not data.new_password:
        print("[reset-password] Error: Password missing.")
        raise HTTPException(400, "La nueva contraseña es obligatoria")
        
    if data.new_password != data.confirm_password:
        print("[reset-password] Error: Password mismatch.")
        raise HTTPException(400, "Las contraseñas no coinciden")
        
    if len(data.new_password) < 8:
        print("[reset-password] Error: Password length < 8.")
        raise HTTPException(400, "La contraseña debe tener al menos 8 caracteres")
        
    if not re.search(r"[a-zA-Z]", data.new_password) or not re.search(r"\d", data.new_password):
        print("[reset-password] Error: Password weak.")
        raise HTTPException(400, "La contraseña debe contener al menos una letra y un número")
        
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    
    reset_token = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash
    ).first()
    
    if not reset_token or reset_token.used_at is not None or reset_token.expires_at < datetime.utcnow():
        print("[reset-password] Error: Token invalid, used or expired.")
        raise HTTPException(400, "El enlace expiró o ya fue usado. Solicita uno nuevo.")
        
    user = reset_token.user
    if not user or not user.is_active:
        print("[reset-password] Error: User inactive.")
        raise HTTPException(400, "El enlace expiró o ya fue usado. Solicita uno nuevo.")
        
    if user.company_id is not None:
        from backend.models import Company
        company = db.query(Company).filter(Company.id == user.company_id).first()
        if not company or company.estado != "activo":
            print(f"[reset-password] Error: Company {user.company_id} inactive.")
            raise HTTPException(400, "El enlace expiró o ya fue usado. Solicita uno nuevo.")
            
    # Update password and invalidate token
    user.hashed_password = _hash_password(data.new_password)
    reset_token.used_at = datetime.utcnow()
    db.commit()
    
    print(f"[reset-password] Password updated successfully for user ID={user.id}")
    return {"success": True, "message": "Contraseña actualizada correctamente."}

@app.post("/auth/change-password")
def change_password(
    data: ChangePasswordRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Verificar password actual
    if not _verify_password(data.old_password, current_user.hashed_password):
        raise HTTPException(401, "La contraseña actual es incorrecta")

    # 2. Actualizar
    current_user.hashed_password = _hash_password(data.new_password)
    db.commit()

    return {"ok": True, "message": "Contraseña actualizada correctamente"}


@app.get("/api/auth/me")
@app.get("/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    is_sa = is_global_superadmin(current_user)
    
    if is_sa:
        role_str = "SUPERADMIN"
        scope = "GLOBAL"
        permissions = [
            "admin.access",
            "companies.view",
            "companies.create",
            "companies.update",
            "companies.suspend",
            "companies.reactivate",
            "users.view",
            "users.create",
            "users.update",
            "billing.view",
            "billing.simulate",
            "billing.configure",
            "billing.export"
        ]
    elif current_user.is_admin and current_user.company_id is not None:
        role_str = "COMPANY_ADMIN"
        scope = getattr(current_user, 'cases_view_scope', 'COMPANY') or 'COMPANY'
        permissions = [
            "companies.view",
            "users.view",
            "users.create",
            "users.update"
        ]
    else:
        role_str = getattr(current_user, 'role', 'USER') or 'USER'
        scope = getattr(current_user, 'cases_view_scope', 'OWN') or 'OWN'
        permissions = []

    return {
        "id": current_user.id,
        "username": current_user.username,
        "nombre": current_user.nombre,
        "email": getattr(current_user, 'email', None),
        "company_id": current_user.company_id,
        "company_name": current_user.company.nombre if current_user.company else None,
        "is_admin": current_user.is_admin,
        "is_superadmin": is_sa,
        "role": role_str,
        "cases_view_scope": scope,
        "permissions": permissions,
        "is_active": current_user.is_active,
        "sync_with_clickup": getattr(current_user, 'sync_with_clickup', True),
        "clickup_api_token": getattr(current_user, 'clickup_api_token', None)
    }



@app.get("/auth/users")
def list_users(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Permitir que cualquier usuario autenticado vea la lista para asignaciones de su propia empresa
    if is_global_superadmin(current_user):
        users = db.query(User).order_by(User.created_at).all()
    else:
        users = db.query(User).filter(User.company_id == current_user.company_id).order_by(User.created_at).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "nombre": u.nombre,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@app.post("/auth/users")
def create_user(data: UserCreateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not is_authorized_admin(current_user):
        raise HTTPException(403, "Solo administradores pueden crear usuarios")
    existing = db.query(User).filter(User.username == data.username).first()
    if existing:
        raise HTTPException(400, f"El usuario '{data.username}' ya existe")
    user = User(
        username=data.username,
        hashed_password=_hash_password(data.password),
        nombre=data.nombre,
        is_admin=False,
        is_active=True,
        company_id=None if is_global_superadmin(current_user) else current_user.company_id
    )
    if is_global_superadmin(current_user) and data.is_admin:
        user.is_admin = True
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"ok": True, "id": user.id, "username": user.username}


@app.put("/auth/users/{user_id}")
def update_user(user_id: int, data: UserUpdateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not is_authorized_admin(current_user) and current_user.id != user_id:
        raise HTTPException(403, "Sin permisos")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    if not is_global_superadmin(current_user) and user.company_id != current_user.company_id:
        raise HTTPException(403, "No tienes permisos para modificar este usuario")
    if data.nombre is not None:
        user.nombre = data.nombre
    if data.password:
        user.hashed_password = _hash_password(data.password)
    if data.is_active is not None and is_authorized_admin(current_user):
        user.is_active = data.is_active
    if data.is_admin is not None:
        if is_global_superadmin(current_user):
            user.is_admin = data.is_admin
        else:
            user.is_admin = False
    db.commit()
    return {"ok": True, "username": user.username}


@app.delete("/auth/users/{user_id}")
def delete_user(user_id: int, request: Request = None, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not is_authorized_admin(current_user):
        raise HTTPException(403, "Solo administradores pueden desactivar usuarios")
    if current_user.id == user_id:
        raise HTTPException(400, "No puedes desactivarte a ti mismo")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")
    if not is_global_superadmin(current_user) and user.company_id != current_user.company_id:
        raise HTTPException(403, "No tienes permisos para modificar este usuario")
        
    # Last active SuperAdmin protection guard
    u_is_sa = is_global_superadmin(user)
    if u_is_sa and user.is_active:
        sa_count = db.query(User).filter((User.role == "SUPERADMIN") | (User.is_superadmin == True), User.is_active == True).count()
        if sa_count <= 1:
            raise HTTPException(400, "No puedes desactivar al último SuperAdmin activo del sistema.")

    user.is_active = False
    db.commit()
    
    # Log Audit
    log_audit_action(
        db=db,
        user_id=current_user.id,
        company_id=user.company_id,
        accion="DEACTIVATE_USER",
        entidad="User",
        entidad_id=user.id,
        request=request,
        metadata_val={"username": user.username, "is_active": False}
    )
    return {"ok": True, "message": "Usuario desactivado correctamente"}


# =========================
# AUTO-REFRESH STATUS & CONFIG
# =========================
@app.get("/auto-refresh/status")
def get_auto_refresh_status():
    status = dict(auto_refresh_stats)
    status["scheduled_hours"] = "9:00 AM y 3:00 PM (Colombia)"
    status["running"] = auto_refresh_running
    return status

@app.post("/auto-refresh/config")
def set_auto_refresh_config(data: AutoRefreshConfigRequest):
    global auto_refresh_stats
    if data.interval_minutes < 5:
        raise HTTPException(400, "El intervalo mnimo es 5 minutos")
    if data.interval_minutes > 1440:
        raise HTTPException(400, "El intervalo mximo es 1440 minutos (24 horas)")
    auto_refresh_stats["interval_minutes"] = data.interval_minutes
    return {"ok": True, "interval_minutes": data.interval_minutes}

@app.post("/auto-refresh/run-now")
async def run_auto_refresh_now():
    try:
        # 1. Refrescar casos activos
        result = await do_auto_refresh()

        # 2. Validar pendientes (juzgado is None)
        pending_result = {"validated": 0, "not_found": 0}
        try:
            db_read = SessionLocal()
            pendientes = db_read.query(Case.id, Case.radicado, Case.company_id).filter(Case.juzgado.is_(None)).limit(2).all()
            pendientes_list = [(p.id, p.radicado, p.company_id) for p in pendientes]
            db_read.close()

            for i, (case_id, radicado, company_id) in enumerate(pendientes_list):
                try:
                    if i > 0:
                        await asyncio.sleep(0.5)
                    
                    db_write = SessionLocal()
                    try:
                        r = await validar_radicado_completo(radicado, db_write, is_new_import=True)
                        if r["found"]:
                            inv = db_write.query(InvalidRadicado).filter(InvalidRadicado.radicado == radicado).first()
                            if inv:
                                db_write.delete(inv)
                            pending_result["validated"] += 1
                        else:
                            inv = db_write.query(InvalidRadicado).filter(InvalidRadicado.radicado == radicado).first()
                            if inv:
                                inv.intentos += 1
                                inv.updated_at = now_colombia()
                            else:
                                db_write.add(InvalidRadicado(radicado=radicado, motivo="No encontrado en Rama Judicial", intentos=1, company_id=company_id))
                            
                            c_del = db_write.query(Case).filter(Case.id == case_id).first()
                            if c_del:
                                db_write.delete(c_del)
                            pending_result["not_found"] += 1
                        db_write.commit()
                    except Exception as e:
                        db_write.rollback()
                        print(f" [cron-pending] Error en {radicado}: {e}")
                    finally:
                        db_write.close()
                except Exception as e:
                    print(f" [cron-pending] Error en bucle de item: {e}")
        except Exception as e:
            print(f" [cron-pending] Error general: {e}")

        # 3. Reintentar no encontrados
        invalid_result = {"found": 0, "still_not_found": 0}
        try:
            db = SessionLocal()
            invalidos = db.query(InvalidRadicado).order_by(InvalidRadicado.updated_at.asc()).limit(2).all()
            for i, item in enumerate(invalidos):
                try:
                    if i > 0:
                        await asyncio.sleep(1.0)
                    r = await validar_radicado_completo(item.radicado, db, is_new_import=True)
                    if r["found"]:
                        db.delete(item)
                        invalid_result["found"] += 1
                    else:
                        item.intentos += 1
                        item.updated_at = now_colombia()
                        invalid_result["still_not_found"] += 1
                    db.flush()
                except Exception as e:
                    print(f" [cron-invalid] Error en {item.radicado}: {e}")
            db.commit()
            db.close()
        except Exception as e:
            print(f" [cron-invalid] Error general: {e}")

        return {
            **result,
            "pending_validated": pending_result["validated"],
            "pending_not_found": pending_result["not_found"],
            "invalid_recovered": invalid_result["found"],
            "invalid_still_pending": invalid_result["still_not_found"],
        }

    except Exception as e:
        raise HTTPException(500, f"Error ejecutando auto-refresh: {str(e)}")

@app.get("/api/documentos/{radicado}/{id_reg_actuacion}")
async def get_docs_actuacion(
    radicado: str, 
    id_reg_actuacion: int, 
    db: Session = Depends(get_db), 
    current_user: User = Depends(get_current_user)
):
    try:
        # Enforce company isolation
        event = db.query(CaseEvent).filter(CaseEvent.id_reg_actuacion == id_reg_actuacion).first()
        case = db.query(Case).filter(Case.radicado == radicado).first()
        if not case and event:
            case = db.query(Case).filter(Case.id == event.case_id).first()
            
        if case:
            if not is_global_superadmin(current_user) and case.company_id != current_user.company_id:
                raise HTTPException(403, "No tienes acceso a los documentos de este caso.")
        else:
            if not is_global_superadmin(current_user):
                raise HTTPException(404, "El caso consultado no existe o no pertenece a tu empresa.")

        # 1. Intentar obtener desde el caché de la base de datos
        if event and event.documentos_cache:
            try:
                cached_data = json.loads(event.documentos_cache)
                return cached_data
            except:
                pass # Si el JSON est corrupto, seguimos con la consulta real

        # 2. Consultar en tiempo real a la Rama Judicial (esto tarda)
        docs = await consultar_documentos(radicado, id_reg_actuacion)
        
        # 3. Guardar en el caché para la próxima vez
        if event and docs:
            event.documentos_cache = json.dumps(docs)
            db.commit()
            
        return docs
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error al cargar documentos: {str(e)}")


# =========================
# NOTIFICATIONS CONFIG
# =========================
@app.get("/config/notifications")
def get_notification_config(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Los usuarios registrados pueden ver la config b?sica para que el dashboard no falle
    config = db.query(NotificationConfig).first()

    if not config:
        config = NotificationConfig(smtp_host="smtp.gmail.com", smtp_port=587, is_active=False)
        db.add(config)
        db.commit()
        db.refresh(config)

    return {
        "id": config.id,
        "smtp_host": config.smtp_host,
        "smtp_port": config.smtp_port,
        "smtp_user": config.smtp_user,
        "smtp_from": config.smtp_from,
        "notification_emails": config.notification_emails,
        "is_active": config.is_active,
        "has_password": bool(config.smtp_pass),
        "updated_at": config.updated_at.isoformat() if config.updated_at else None,
    }

@app.put("/config/notifications")
def update_notification_config(data: NotificationConfigUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Solo administradores pueden cambiar la configuraci?n")
    config = db.query(NotificationConfig).first()
    if not config:
        config = NotificationConfig()
        db.add(config)

    if data.smtp_host is not None:
        config.smtp_host = data.smtp_host
    if data.smtp_port is not None:
        config.smtp_port = data.smtp_port
    if data.smtp_user is not None:
        config.smtp_user = data.smtp_user
    if data.smtp_pass is not None and data.smtp_pass != "":
        config.smtp_pass = data.smtp_pass
    if data.smtp_from is not None:
        config.smtp_from = data.smtp_from
    if data.notification_emails is not None:
        config.notification_emails = data.notification_emails
    if data.is_active is not None:
        config.is_active = data.is_active

    config.updated_at = now_colombia()
    db.commit()
    return {"ok": True, "message": "Configuracin guardada"}

@app.post("/config/notifications/test")
def test_notification_email(data: TestEmailRequest, db: Session = Depends(get_db)):
    config = db.query(NotificationConfig).first()
    if not config:
        raise HTTPException(400, "No hay configuracin guardada")
    if not config.smtp_user or not config.smtp_pass:
        raise HTTPException(400, "Falta configurar usuario y contrasea SMTP")

    try:
        body = f"""
        <html><body style="font-family:Arial;padding:20px;">
        <h2 style="color:#0d9488;"> Prueba de Notificacin</h2>
        <p>Si recibiste este correo, la configuracin SMTP est correcta.</p>
        <p style="color:#888;font-size:12px;">Fecha: {now_colombia().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </body></html>
        """
        msg = MIMEMultipart("alternative")
        msg["Subject"] = " Prueba SMTP - EMDECOB Consultas"
        msg["From"] = config.smtp_from or config.smtp_user
        msg["To"] = data.email
        msg.attach(MIMEText(body, "html"))

        with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config.smtp_user, config.smtp_pass)
            server.sendmail(msg["From"], [data.email], msg.as_string())

        return {"ok": True, "message": "Correo enviado correctamente"}
    except Exception as e:
        raise HTTPException(500, f"Error enviando correo: {str(e)}")

@app.get("/config/notifications/logs")
def get_notification_logs(
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    q = db.query(NotificationLog)
    total = q.count()
    logs = (
        q.order_by(desc(NotificationLog.sent_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "id": log.id,
                "sent_at": log.sent_at.isoformat() if log.sent_at else None,
                "recipients": log.recipients,
                "subject": log.subject,
                "cases_count": log.cases_count,
                "status": log.status,
                "error_message": log.error_message,
            }
            for log in logs
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@app.post("/config/notifications/send-manual")
def send_manual_notification(db: Session = Depends(get_db)):
    try:
        unread_cases = get_unread_cases_for_notification(db)
        if not unread_cases:
            return {"ok": True, "sent": False, "message": "No hay casos no ledos para enviar", "count": 0}

        send_grouped_notification(unread_cases)
        return {"ok": True, "sent": True, "message": f"Correo enviado con {len(unread_cases)} casos", "count": len(unread_cases)}
    except Exception as e:
        raise HTTPException(500, f"Error enviando correo: {str(e)}")


# =========================
# INVALID RADICADOS
# =========================
@app.get("/api/invalid-radicados")
@app.get("/invalid-radicados")
def list_invalid_radicados(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    q = db.query(InvalidRadicado)
    # Filtrar por empresa (igual que el dashboard de stats)
    if not is_global_superadmin(current_user):
        # Usuarios y admins con empresa ven solo los de su empresa
        if hasattr(InvalidRadicado, 'company_id') and current_user.company_id:
            q = q.filter(InvalidRadicado.company_id == current_user.company_id)

    if search:
        s = f"%{search.strip()}%"
        q = q.filter(InvalidRadicado.radicado.like(s))

    total = q.count()
    items = (
        q.order_by(desc(InvalidRadicado.updated_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "items": [
            {
                "id": x.id,
                "radicado": x.radicado,
                "motivo": x.motivo,
                "intentos": x.intentos,
                "created_at": x.created_at.isoformat() if x.created_at else None,
                "updated_at": x.updated_at.isoformat() if x.updated_at else None,
            }
            for x in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }

@app.delete("/api/invalid-radicados/{radicado_id}")
@app.delete("/invalid-radicados/{radicado_id}")
def delete_invalid_radicado(radicado_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        from sqlalchemy import text
        comp_id = current_user.company_id
        if is_global_superadmin(current_user):
            db.execute(text("DELETE FROM invalid_radicados WHERE id = :id;"), {"id": radicado_id})
        else:
            db.execute(text("DELETE FROM invalid_radicados WHERE id = :id AND company_id = :cid;"), {"id": radicado_id, "cid": comp_id})
        db.commit()
        return {"ok": True, "message": "Radicado eliminado correctamente"}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error al eliminar radicado no encontrado: {str(e)}")

@app.get("/api/invalid-radicados/download")
@app.get("/invalid-radicados/download")
def download_invalid_radicados_excel(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if is_global_superadmin(current_user):
        items = db.query(InvalidRadicado).order_by(desc(InvalidRadicado.updated_at)).all()
    else:
        items = db.query(InvalidRadicado).filter(InvalidRadicado.company_id == current_user.company_id).order_by(desc(InvalidRadicado.updated_at)).all()

    data = [
        {
            "Radicado": x.radicado,
            "Motivo": x.motivo,
            "Intentos": x.intentos,
            "Fecha Registro": x.created_at.strftime("%Y-%m-%d %H:%M") if x.created_at else "",
            "Último Intento": x.updated_at.strftime("%Y-%m-%d %H:%M") if x.updated_at else "",
        }
        for x in items
    ]

    # Clean all string values in the data list to remove illegal control characters (XML incompatible)
    import re
    excel_clean_re = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]")
    cleaned_data = []
    for row in data:
        cleaned_row = {}
        for k, v in row.items():
            if isinstance(v, str):
                cleaned_row[k] = excel_clean_re.sub("", v)
            else:
                cleaned_row[k] = v
        cleaned_data.append(cleaned_row)

    df = pd.DataFrame(cleaned_data)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="No Encontrados")
    output.seek(0)

    filename = f"radicados_no_encontrados_{now_colombia().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@app.post("/api/invalid-radicados/{radicado_id}/retry")
@app.post("/invalid-radicados/{radicado_id}/retry")
async def retry_invalid_radicado(
    radicado_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = db.query(InvalidRadicado).filter(InvalidRadicado.id == radicado_id).first()
    if not item:
        raise HTTPException(404, "Radicado no encontrado")
    if not is_global_superadmin(current_user) and item.company_id != current_user.company_id:
        raise HTTPException(403, "No tienes permiso para reintentar este radicado")

    from backend.service.fallback_search import search_radicado_with_fallbacks
    company_id = item.company_id or (current_user.company_id if current_user else None)
    result = await search_radicado_with_fallbacks(
        radicado=item.radicado,
        company_id=company_id,
        db=db,
        current_user=current_user,
        force=True
    )

    status = result.get("status")
    if status in ("found", "found_alternative"):
        source = result.get("source", "rama_judicial")
        db.delete(item)
        db.commit()
        msg = "Radicado encontrado en Rama Judicial y agregado a casos" if source == "rama_judicial" \
              else f"Radicado encontrado en fuente alternativa ({source}) y agregado a casos"
        return {"ok": True, "found": True, "source": source, "message": msg}
    else:
        item.intentos += 1
        item.motivo = "No encontrado en Rama Judicial ni en fuentes alternativas"
        item.updated_at = now_colombia()
        db.commit()
        return {"ok": True, "found": False, "message": "Radicado sigue sin encontrarse en ninguna fuente oficial"}

@app.post("/api/invalid-radicados/retry-all")
@app.post("/invalid-radicados/retry-all")
async def retry_all_invalid_radicados(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    delay_seconds: float = Query(default=0.5, ge=0.1, le=5),
):
    from backend.service.fallback_search import search_radicado_with_fallbacks
    q = db.query(InvalidRadicado)
    if not is_global_superadmin(current_user):
        q = q.filter(InvalidRadicado.company_id == current_user.company_id)
    items = q.order_by(InvalidRadicado.id).all()
    if not items:
        return {"ok": True, "processed": 0, "found": 0, "still_not_found": 0, "remaining": 0, "message": "No hay radicados para reintentar"}

    found = 0
    still_not_found = 0

    for i, item in enumerate(items):
        try:
            if i > 0:
                await asyncio.sleep(delay_seconds + random.uniform(0, 0.3))

            company_id = item.company_id or (current_user.company_id if current_user else None)
            result = await search_radicado_with_fallbacks(
                radicado=item.radicado,
                company_id=company_id,
                db=db,
                current_user=current_user,
                force=True
            )
            if result.get("status") in ("found", "found_alternative"):
                db.delete(item)
                db.flush()
                found += 1
            else:
                item.intentos += 1
                item.motivo = "No encontrado en Rama Judicial ni en fuentes alternativas"
                item.updated_at = now_colombia()
                still_not_found += 1
        except Exception:
            still_not_found += 1

    db.commit()
    q_rem = db.query(InvalidRadicado)
    if not is_global_superadmin(current_user):
        q_rem = q_rem.filter(InvalidRadicado.company_id == current_user.company_id)
    remaining = q_rem.count()

    return {
        "ok": True,
        "processed": len(items),
        "found": found,
        "still_not_found": still_not_found,
        "remaining": remaining,
        "message": f"Procesados {len(items)}: {found} validados, {still_not_found} no encontrados. Quedan {remaining}."
    }

@app.post("/api/invalid-radicados/retry-batch")
@app.post("/invalid-radicados/retry-batch")
async def retry_batch_invalid_radicados(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    batch_size: int = Query(default=20, ge=1, le=100),
):
    from backend.service.fallback_search import search_radicado_with_fallbacks
    q = db.query(InvalidRadicado)
    if not is_global_superadmin(current_user):
        q = q.filter(InvalidRadicado.company_id == current_user.company_id)
    items = q.order_by(InvalidRadicado.id).limit(batch_size).all()
    if not items:
        return {"ok": True, "processed": 0, "found": 0, "still_not_found": 0, "remaining": 0, "message": "No hay radicados para reintentar"}

    found = 0
    still_not_found = 0

    for i, item in enumerate(items):
        try:
            if i > 0:
                await delay_between_requests(0.3, 0.6)

            company_id = item.company_id or (current_user.company_id if current_user else None)
            result = await search_radicado_with_fallbacks(
                radicado=item.radicado,
                company_id=company_id,
                db=db,
                current_user=current_user,
                force=True
            )
            if result.get("status") in ("found", "found_alternative"):
                db.delete(item)
                found += 1
            else:
                item.intentos += 1
                item.motivo = "No encontrado en Rama Judicial ni en fuentes alternativas"
                item.updated_at = now_colombia()
                still_not_found += 1
        except Exception:
            still_not_found += 1

    db.commit()
    q_rem = db.query(InvalidRadicado)
    if not is_global_superadmin(current_user):
        q_rem = q_rem.filter(InvalidRadicado.company_id == current_user.company_id)
    remaining = q_rem.count()

    return {
        "ok": True,
        "processed": len(items),
        "found": found,
        "still_not_found": still_not_found,
        "remaining": remaining,
        "message": f"Procesados {len(items)}: {found} validados, {still_not_found} no encontrados. Quedan {remaining}."
    }

@app.delete("/api/invalid-radicados/delete-all")
@app.delete("/invalid-radicados/delete-all")
def delete_all_invalid_radicados(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        from sqlalchemy import text
        comp_id = current_user.company_id
        if is_global_superadmin(current_user):
            res = db.execute(text("DELETE FROM invalid_radicados;"))
        else:
            res = db.execute(text("DELETE FROM invalid_radicados WHERE company_id = :cid;"), {"cid": comp_id})
        db.commit()
        return {"ok": True, "message": "Se eliminaron todos los radicados no encontrados correctamente."}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Error al eliminar radicados no encontrados: {str(e)}")


# =========================
# ABOGADOS LIST
# =========================
@app.get("/cases/abogados")
def list_abogados(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retorna lista única de abogados: nombres de usuarios activos + valores únicos en Case.abogado, filtrado por empresa."""
    is_sa = is_global_superadmin(current_user)

    # 1. Abogados registrados en casos
    q_cases = db.query(Case.abogado).filter(Case.abogado.isnot(None), Case.abogado != "")
    if not is_sa:
        q_cases = q_cases.filter(Case.company_id == current_user.company_id)
    case_names = [r[0] for r in q_cases.distinct().all() if r[0]]

    # 2. Nombres de usuarios activos de la empresa (para incluir abogados sin casos aún)
    q_users = db.query(User.nombre).filter(User.is_active == True, User.nombre.isnot(None), User.nombre != "")
    if not is_sa:
        q_users = q_users.filter(User.company_id == current_user.company_id)
    user_names = [r[0] for r in q_users.distinct().all() if r[0]]

    # 3. Combinar, deduplicar y ordenar
    all_names = sorted(set(case_names + user_names))
    return ["Sin asignar"] + all_names

# =========================
# CASES LIST
# =========================
# Redundant legacy endpoints removed to prevent route shadowing and enforce security/multi-tenancy constraint.

@app.get("/api/cases")
@app.get("/cases")
def list_cases(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: Optional[str] = Query(default=None),
    juzgado: Optional[str] = Query(default=None),
    mes_actuacion: Optional[str] = Query(default=None),
    cedula: Optional[str] = Query(default=None),
    abogado: Optional[str] = Query(default=None),
    solo_validos: bool = Query(default=True),
    solo_pendientes: bool = Query(default=False),
    solo_no_leidos: bool = Query(default=False),
    solo_leidos: bool = Query(default=False),
    solo_actualizados_hoy: bool = Query(default=False),
    solo_retirados: bool = Query(default=False),
    con_documentos: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=2000),
):
    try:
        q = db.query(Case).options(selectinload(Case.tasks))

        # Multi-tenancy filter: SaaS Isolation
        if is_global_superadmin(current_user):
            pass # SuperAdmin ve todo
        else:
            q = q.filter(Case.company_id == current_user.company_id)

        # Filtro de retirados vs activos
        if solo_retirados:
            q = q.filter(Case.is_active == False)
        else:
            # En la lista normal, excluir los radicados retirados
            q = q.filter(or_(Case.is_active == True, Case.is_active.is_(None)))

        if solo_pendientes:
            q = q.filter(Case.juzgado.is_(None))
        elif solo_validos:
            q = q.filter(Case.juzgado.isnot(None))

        hoy = today_colombia()
        ayer = hoy - timedelta(days=1)
        unread_condition = or_(
            and_(Case.current_hash.isnot(None), Case.last_hash.isnot(None), Case.current_hash != Case.last_hash),
            and_(Case.current_hash.isnot(None), Case.last_hash.is_(None), Case.ultima_actuacion >= ayer),
            Case.last_hash == "unread_manually"
        )

        if solo_no_leidos:
            q = q.filter(unread_condition)
        elif solo_leidos:
            q = q.filter(~unread_condition)

        if solo_actualizados_hoy:
            q = q.filter(Case.ultima_actuacion == today_colombia())

        if search:
            s = f"%{search.strip()}%"
            q = q.filter(
                or_(Case.radicado.like(s), Case.demandante.like(s), Case.demandado.like(s), Case.alias.like(s))
            )

        if juzgado:
            q = q.filter(Case.juzgado.like(f"%{juzgado.strip()}%"))

        if cedula:
            q = q.filter(Case.cedula.like(f"%{cedula.strip()}%"))

        if abogado:
            val = abogado.strip()
            if val.lower() == "sin asignar":
                q = q.filter(or_(Case.abogado.is_(None), Case.abogado == ""))
            else:
                q = q.filter(Case.abogado.ilike(f"%{val}%"))

        if con_documentos is not None:
            q = q.filter(Case.has_documents == con_documentos)

        if mes_actuacion:
            if mes_actuacion in ("sin_fecha", "null", "none"):
                q = q.filter(Case.ultima_actuacion.is_(None))
            else:
                try:
                    year, month = mes_actuacion.split("-")
                    from sqlalchemy import extract
                    q = q.filter(extract('year', Case.ultima_actuacion) == int(year), extract('month', Case.ultima_actuacion) == int(month))
                except:
                    pass

        total = q.count()

        hoy_count = today_colombia()
        ayer_count = hoy_count - timedelta(days=1)

        q_unread = db.query(Case).filter(
            Case.juzgado.isnot(None),
            Case.current_hash.isnot(None),
            or_(
                and_(Case.last_hash.isnot(None), Case.current_hash != Case.last_hash),
                and_(Case.last_hash.is_(None), Case.ultima_actuacion >= ayer_count),
            )
        )

        if is_global_superadmin(current_user):
            pass
        else:
            q_unread = q_unread.filter(Case.company_id == current_user.company_id)
        
        unread_count = q_unread.count()

        unread_order = sql_case(
            (and_(Case.current_hash.isnot(None), Case.last_hash.isnot(None), Case.current_hash != Case.last_hash), 0),
            (and_(Case.current_hash.isnot(None), Case.last_hash.is_(None), Case.ultima_actuacion >= ayer_count), 0),
            else_=1
        )

        items = (
            q.order_by(
                unread_order,
                desc(Case.ultima_actuacion).nullslast(),
                desc(Case.fecha_radicacion).nullslast(),
                desc(Case.id)
            )
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        def to_out(c: Case):
            return {
                "id": c.id,
                "radicado": c.radicado,
                "demandante": c.demandante,
                "demandado": c.demandado,
                "juzgado": c.juzgado,
                "alias": c.alias,
                "fecha_radicacion": c.fecha_radicacion.isoformat() if c.fecha_radicacion else None,
                "ultima_actuacion": c.ultima_actuacion.isoformat() if c.ultima_actuacion else None,
                "last_check_at": c.last_check_at.isoformat() if c.last_check_at else None,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "updated_at": c.updated_at.isoformat() if c.updated_at else None,
                "unread": is_unread_case(c),
                "has_documents": c.has_documents,
                "cedula": c.cedula,
                "abogado": c.abogado,
                "has_tasks": len(c.tasks) > 0,
                "company_id": c.company_id,
            }

        return {
            "items": [to_out(x) for x in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "unread_count": unread_count,
        }
    except Exception as e:
        import traceback
        raise HTTPException(status_code=400, detail=f"DEBUG ERROR: {str(e)} | TRACE: {traceback.format_exc()}")


# =========================
# CASES DOWNLOAD EXCEL
# =========================
@app.get("/api/cases/download")
@app.get("/cases/download")
def download_cases_excel(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: Optional[str] = Query(default=None),
    juzgado: Optional[str] = Query(default=None),
    cedula: Optional[str] = Query(default=None),
    abogado: Optional[str] = Query(default=None),
    mes_actuacion: Optional[str] = Query(default=None),
    solo_no_leidos: bool = Query(default=False),
    solo_actualizados_hoy: bool = Query(default=False),
    solo_retirados: bool = Query(default=False),
    company_id: Optional[int] = Query(default=None),
    page: Optional[int] = Query(default=None),
    page_size: Optional[int] = Query(default=None),
    ignore_filters: bool = Query(default=False),
):
    try:
        q = db.query(Case).filter(Case.juzgado.isnot(None))

        # Multi-tenancy filter: SaaS Isolation
        if is_global_superadmin(current_user):
            if company_id is not None:
                q = q.filter(Case.company_id == company_id)
        else:
            q = q.filter(Case.company_id == current_user.company_id)

        if not ignore_filters:
            if solo_retirados:
                q = q.filter(Case.is_active == False)
            else:
                q = q.filter(or_(Case.is_active == True, Case.is_active.is_(None)))

            if solo_no_leidos:
                ayer_list = today_colombia() - timedelta(days=1)
                q = q.filter(
                    Case.current_hash.isnot(None),
                    or_(
                        and_(Case.last_hash.isnot(None), Case.current_hash != Case.last_hash),
                        and_(Case.last_hash.is_(None), Case.ultima_actuacion >= ayer_list),
                    )
                )

            if solo_actualizados_hoy:
                q = q.filter(Case.ultima_actuacion == today_colombia())

            if search:
                s = f"%{search.strip()}%"
                q = q.filter(or_(Case.radicado.like(s), Case.demandante.like(s), Case.demandado.like(s), Case.alias.like(s)))

            if juzgado:
                q = q.filter(Case.juzgado.like(f"%{juzgado.strip()}%"))

            if cedula:
                q = q.filter(Case.cedula.like(f"%{cedula.strip()}%"))

            if abogado:
                val = abogado.strip()
                if val.lower() == "sin asignar":
                    q = q.filter(or_(Case.abogado.is_(None), Case.abogado == ""))
                else:
                    q = q.filter(Case.abogado.ilike(f"%{val}%"))

            if mes_actuacion:
                if mes_actuacion in ("sin_fecha", "null", "none"):
                    q = q.filter(Case.ultima_actuacion.is_(None))
                else:
                    try:
                        year, month = mes_actuacion.split("-")
                        from sqlalchemy import extract
                        q = q.filter(extract('year', Case.ultima_actuacion) == int(year), extract('month', Case.ultima_actuacion) == int(month))
                    except:
                        pass
        else:
            if solo_retirados:
                q = q.filter(Case.is_active == False)
            else:
                q = q.filter(or_(Case.is_active == True, Case.is_active.is_(None)))

        # Ordenar por última actuación descendente con nulos de últimos
        q = q.order_by(desc(Case.ultima_actuacion).nullslast(), desc(Case.id))

        # Paginación
        if not ignore_filters and page is not None and page_size is not None:
            offset = (page - 1) * page_size
            q = q.offset(offset).limit(page_size)

        # Eager load company and user to avoid N+1 query overhead
        cases = (
            q.options(joinedload(Case.company), joinedload(Case.user))
            .all()
        )

        case_ids = [c.id for c in cases]
        latest_event_map = {}
        if case_ids:
            # Load latest events (actuaciones) for these cases in a single optimized query using row_number window function
            subq = (
                db.query(
                    CaseEvent.case_id,
                    CaseEvent.event_date,
                    CaseEvent.title,
                    CaseEvent.detail,
                    func.row_number().over(
                        partition_by=CaseEvent.case_id,
                        order_by=(desc(CaseEvent.event_date), desc(CaseEvent.id))
                    ).label("rn")
                )
                .filter(CaseEvent.case_id.in_(case_ids))
                .subquery()
            )
            events = db.query(subq).filter(subq.c.rn == 1).all()
            for ev in events:
                latest_event_map[ev.case_id] = ev

        data = []
        for c in cases:
            ev = latest_event_map.get(c.id)
            if ev:
                title_str = (ev.title or "").strip()
                detail_str = (ev.detail or "").strip()
                
                # Choose the longest / most complete text
                if len(detail_str) >= len(title_str):
                    last_event_desc = detail_str or title_str
                else:
                    last_event_desc = title_str or detail_str
                    
                if not last_event_desc:
                    last_event_desc = "Sin actuaciones registradas"
            else:
                last_event_desc = "Sin actuaciones registradas"

            # Truncate to avoid Excel cell character limits (32,767)
            if len(last_event_desc) > 32000:
                last_event_desc = last_event_desc[:32000] + "..."

            data.append({
                "Radicado": c.radicado,
                "Demandante": c.demandante or "",
                "Demandado": c.demandado or "",
                "Cédula": c.cedula or "",
                "Abogado": c.abogado or "",
                "Juzgado": c.juzgado or "",
                "Despacho": c.despacho or c.juzgado or "",
                "Fecha Radicación": c.fecha_radicacion.isoformat() if c.fecha_radicacion else "",
                "Última Actuación": c.ultima_actuacion.isoformat() if c.ultima_actuacion else "",
                "Fecha de última actuación": c.ultima_actuacion.isoformat() if c.ultima_actuacion else "",
                "Descripción última actuación": last_event_desc,
                "Última Verificación": c.last_check_at.strftime("%Y-%m-%d %H:%M") if c.last_check_at else "",
                "Estado": "No leído" if is_unread_case(c) else "Leído",
                "Fecha de creación": c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "",
                "Empresa": c.company.nombre if c.company else "",
                "Usuario asignado": c.user.username if c.user else "",
            })

        # Clean all string values in the data list to remove illegal control characters (XML incompatible)
        import re
        excel_clean_re = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f-\x84\x86-\x9f]")
        cleaned_data = []
        for row in data:
            cleaned_row = {}
            for k, v in row.items():
                if isinstance(v, str):
                    cleaned_row[k] = excel_clean_re.sub("", v)
                else:
                    cleaned_row[k] = v
            cleaned_data.append(cleaned_row)

        df = pd.DataFrame(cleaned_data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Casos")
        output.seek(0)

        filename = f"casos_{now_colombia().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return Response(
            content=output.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": tb
            }
        )


# =========================
# CASE UPDATES & DELETIONS
# =========================

@app.patch("/cases/{case_id}/id-proceso")
async def update_case_id_proceso(case_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c: raise HTTPException(404, "Caso no encontrado")
    if not is_global_superadmin(current_user) and c.company_id != current_user.company_id:
        raise HTTPException(403, "No tienes permisos sobre este caso")
    id_proceso = data.get("id_proceso")
    c.id_proceso = id_proceso
    db.commit()
    return {"status": "ok", "id_proceso": id_proceso}

@app.delete("/cases/{case_id}")
def delete_case(case_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(404, "Caso no encontrado")

    # Seguridad multi-empresa: solo borrar si el caso pertenece a la empresa del usuario
    if not is_global_superadmin(current_user):
        if c.company_id != current_user.company_id:
            raise HTTPException(403, "No tiene permiso para eliminar este caso")

    radicado = c.radicado
    db.query(CaseEvent).filter(CaseEvent.case_id == case_id).delete()
    db.query(CasePublication).filter(CasePublication.case_id == case_id).delete()
    db.delete(c)
    db.commit()

    return {"ok": True, "message": f"Caso {radicado} eliminado correctamente"}


# =========================
# MARK READ
# =========================
@app.post("/api/cases/{case_id}/mark-read")
@app.post("/cases/{case_id}/mark-read")
def mark_case_read(case_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    if not is_global_superadmin(current_user) and c.company_id != current_user.company_id:
        raise HTTPException(403, "No tienes permisos sobre este caso")
    c.current_hash = c.current_hash or f"case_{c.id}_hash"
    c.last_hash = c.current_hash
    db.commit()
    return {"ok": True, "id": c.id}

@app.post("/api/cases/{case_id}/mark-unread")
@app.post("/cases/{case_id}/mark-unread")
def mark_case_unread(case_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    if not is_global_superadmin(current_user) and c.company_id != current_user.company_id:
        raise HTTPException(403, "No tienes permisos sobre este caso")
    c.current_hash = c.current_hash or f"case_{c.id}_hash"
    c.last_hash = "unread_manually"
    db.commit()
    return {"ok": True, "id": c.id}

@app.post("/api/cases/mark-read-bulk")
@app.post("/cases/mark-read-bulk")
def mark_read_bulk(data: MarkReadBulkRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ids = [int(x) for x in (data.case_ids or [])]
    if not ids:
        raise HTTPException(400, "No se enviaron ids")

    if is_global_superadmin(current_user):
        cases = db.query(Case).filter(Case.id.in_(ids)).all()
    else:
        cases = db.query(Case).filter(Case.id.in_(ids), Case.company_id == current_user.company_id).all()
        
    updated = 0
    for c in cases:
        c.current_hash = c.current_hash or f"case_{c.id}_hash"
        c.last_hash = c.current_hash
        updated += 1

    db.commit()
    return {"ok": True, "updated": updated}

@app.post("/api/cases/mark-unread-bulk")
@app.post("/cases/mark-unread-bulk")
def mark_unread_bulk(data: MarkReadBulkRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ids = [int(x) for x in (data.case_ids or [])]
    if not ids:
        raise HTTPException(400, "No se enviaron ids")

    if is_global_superadmin(current_user):
        cases = db.query(Case).filter(Case.id.in_(ids)).all()
    else:
        cases = db.query(Case).filter(Case.id.in_(ids), Case.company_id == current_user.company_id).all()
        
    updated = 0
    for c in cases:
        c.current_hash = c.current_hash or f"case_{c.id}_hash"
        c.last_hash = "unread_manually"
        updated += 1

    db.commit()
    return {"ok": True, "updated": updated}

@app.post("/cases/mark-read-all")
def mark_read_all(data: MarkReadAllRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(Case).filter(Case.juzgado.isnot(None))

    if not is_global_superadmin(current_user):
        q = q.filter(Case.company_id == current_user.company_id)

    if data.solo_actualizados_hoy:
        q = q.filter(Case.ultima_actuacion == today_colombia())

    if data.search:
        s = f"%{data.search.strip()}%"
        q = q.filter(or_(Case.radicado.like(s), Case.demandante.like(s), Case.demandado.like(s), Case.alias.like(s)))

    if data.juzgado:
        q = q.filter(Case.juzgado.like(f"%{data.juzgado.strip()}%"))

    if data.solo_no_leidos:
        ayer_mark = today_colombia() - timedelta(days=1)
        q = q.filter(
            Case.current_hash.isnot(None),
            or_(
                and_(Case.last_hash.isnot(None), Case.current_hash != Case.last_hash),
                and_(Case.last_hash.is_(None), Case.ultima_actuacion >= ayer_mark),
            )
        )

    cases = q.all()
    updated = 0
    for c in cases:
        if is_unread_case(c):
            c.last_hash = c.current_hash
            updated += 1

    db.commit()
    return {"ok": True, "updated": updated, "total": len(cases)}


# =========================
# VALIDATE PENDIENTES
# =========================
@app.post("/cases/validate-batch")
async def validate_batch(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    batch_size: int = Query(default=10, ge=1, le=50)
):
    """Lanza la validacion en segundo plano y retorna inmediatamente para evitar timeouts."""

    # Count how many are pending for this user
    q = db.query(Case).filter(Case.juzgado.is_(None))
    if not current_user.is_admin:
        q = q.filter(Case.user_id == current_user.id)
    
    pendientes_count = q.count()

    if pendientes_count == 0:
        return {"ok": True, "processed": 0, "validated": 0, "not_found": 0, "remaining": 0, "message": "No hay casos pendientes"}

    # Get the IDs to process (avoid passing db session to background)
    batch_ids = [c.id for c in q.limit(batch_size).all()]

    async def _run_batch(ids):
        validated = 0
        not_found = 0
        for i, case_id in enumerate(ids):
            radicado = None
            company_id = None
            db_read = SessionLocal()
            try:
                c = db_read.query(Case).filter(Case.id == case_id).first()
                if c:
                    radicado = c.radicado
                    company_id = c.company_id
            except Exception as e:
                print(f"[validate-batch] Error al leer caso {case_id}: {e}")
            finally:
                db_read.close()

            if not radicado:
                continue

            try:
                if i > 0:
                    await delay_between_requests(0.5, 1.0)
                
                db_write = SessionLocal()
                try:
                    result = await validar_radicado_completo(radicado, db_write, is_new_import=True)
                    if result["found"]:
                        inv = db_write.query(InvalidRadicado).filter(InvalidRadicado.radicado == radicado).first()
                        if inv:
                            db_write.delete(inv)
                        validated += 1
                    else:
                        not_found += 1
                        inv = db_write.query(InvalidRadicado).filter(InvalidRadicado.radicado == radicado).first()
                        if inv:
                            inv.intentos += 1
                            inv.updated_at = now_colombia()
                        else:
                            db_write.add(InvalidRadicado(radicado=radicado, motivo="No encontrado en Rama Judicial", intentos=1, company_id=company_id))
                        
                        c_del = db_write.query(Case).filter(Case.id == case_id).first()
                        if c_del:
                            db_write.delete(c_del)
                    db_write.commit()
                except Exception as e:
                    db_write.rollback()
                    print(f"[validate-batch] Error al validar {radicado}: {e}")
                finally:
                    db_write.close()
            except Exception as e:
                print(f"[validate-batch] Error general en item: {e}")

        print(f"[validate-batch] Lote completado: {validated} validados, {not_found} no encontrados")

    background_tasks.add_task(_run_batch, batch_ids)

    return {
        "ok": True,
        "processed": len(batch_ids),
        "remaining": pendientes_count,
        "message": f"Procesando {len(batch_ids)} casos en segundo plano. Recarga la pagina en 1-2 minutos para ver los resultados."
    }

@app.post("/cases/validate-selected")
async def validate_selected(data: ValidateSelectedRequest, db: Session = Depends(get_db)):
    radicados = [clean_str(r) for r in (data.radicados or []) if clean_str(r)]
    if not radicados:
        raise HTTPException(400, "No se enviaron radicados")

    casos = db.query(Case.id, Case.radicado, Case.company_id).filter(Case.radicado.in_(radicados), Case.juzgado.is_(None)).all()
    case_infos = [(c.id, c.radicado, c.company_id) for c in casos]
    db.close()

    validated = 0
    not_found = 0

    for i, (case_id, radicado, company_id) in enumerate(case_infos):
        try:
            if i > 0:
                await delay_between_requests(0.3, 0.6)

            db_write = SessionLocal()
            try:
                result = await validar_radicado_completo(radicado, db_write, is_new_import=True)

                if result["found"]:
                    inv = db_write.query(InvalidRadicado).filter(InvalidRadicado.radicado == radicado).first()
                    if inv:
                        db_write.delete(inv)
                    validated += 1
                else:
                    not_found += 1
                    inv = db_write.query(InvalidRadicado).filter(InvalidRadicado.radicado == radicado).first()
                    if inv:
                        inv.intentos += 1
                        inv.updated_at = now_colombia()
                    else:
                        db_write.add(InvalidRadicado(radicado=radicado, motivo="No encontrado en Rama Judicial", intentos=1, company_id=company_id))
                    
                    c_del = db_write.query(Case).filter(Case.id == case_id).first()
                    if c_del:
                        db_write.delete(c_del)
                db_write.commit()
            except Exception as e:
                db_write.rollback()
                print(f"[validate-selected] Error en {radicado}: {e}")
            finally:
                db_write.close()
        except Exception:
            pass

    return {"ok": True, "validated": validated, "not_found": not_found, "requested": len(radicados)}


# =========================
# CASE BY RADICADO
# =========================
def serialize_case(c: Case):
    return {
        "id": c.id,
        "company_id": c.company_id,
        "radicado": c.radicado,
        "id_proceso": c.id_proceso,
        "demandante": c.demandante,
        "demandado": c.demandado,
        "juzgado": c.juzgado,
        "alias": c.alias,
        "cedula": c.cedula,
        "abogado": c.abogado,
        "telefono": c.telefono,
        "fecha_radicacion": c.fecha_radicacion.isoformat() if c.fecha_radicacion else None,
        "ultima_actuacion": c.ultima_actuacion.isoformat() if c.ultima_actuacion else None,
        "last_check_at": c.last_check_at.isoformat() if c.last_check_at else None,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "unread": is_unread_case(c),
        "has_documents": c.has_documents,
        "sync_pub_status": c.sync_pub_status,
        "sync_pub_progress": c.sync_pub_progress,
        "is_active": c.is_active,
        
        # Fallback search columns
        "despacho": c.despacho or c.juzgado,
        "clase_proceso": c.clase_proceso,
        "tipo_proceso": c.tipo_proceso,
        "estado": c.estado,
        "ponente_juez": c.ponente_juez,
        "departamento": c.departamento,
        "municipio": c.municipio,
        "ubicacion": c.ubicacion,
        "fuente_encontrado": c.fuente_encontrado,
        "url_fuente": c.url_fuente,
        "metodo_busqueda": c.metodo_busqueda,
        "confianza_busqueda": c.confianza_busqueda,
        "encontrado_en_fuente_alternativa": c.encontrado_en_fuente_alternativa or False,
        "requiere_revision": c.requiere_revision or False,
    }

# =========================
# CASE SEARCH & FALLBACKS (FASE 1)
# =========================

@app.post("/api/cases/search")
@app.post("/cases/search")
async def search_case_endpoint(
    req: CaseSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from backend.service.fallback_search import search_radicado_with_fallbacks
    
    company_id = req.company_id
    if current_user.is_superadmin or (current_user.is_admin and not current_user.company_id):
        if not company_id:
            raise HTTPException(400, "Selecciona una empresa para asociar el radicado.")
        from backend.models import Company
        comp = db.query(Company).filter(Company.id == company_id).first()
        if not comp:
            raise HTTPException(444, "La empresa especificada no existe")
    else:
        company_id = current_user.company_id
        
    if not company_id:
        raise HTTPException(400, "Empresa no especificada.")
        
    result = await search_radicado_with_fallbacks(
        radicado=req.radicado,
        company_id=company_id,
        db=db,
        current_user=current_user,
        force=req.force
    )
    
    if result["status"] in ["found", "found_alternative"] and result.get("case") is not None:
        result["case"] = serialize_case(result["case"])
        
    return result

@app.get("/api/cases/{radicado}")
@app.get("/cases/{radicado}")
async def get_case_by_radicado_unified(
    radicado: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    r = clean_str(radicado)
    if not r:
        raise HTTPException(400, "Radicado o ID no especificado")
        
    q = db.query(Case)
    if not (current_user.is_superadmin or (current_user.is_admin and not current_user.company_id)):
        q = q.filter(Case.company_id == current_user.company_id)
        
    is_id = False
    if r.isdigit() and len(r) < 10:
        is_id = True
        
    if is_id:
        c = q.filter(Case.id == int(r)).first()
    else:
        c = q.filter(Case.radicado == r).first()
        
    if not c:
        raise HTTPException(404, "Caso no encontrado")
        
    # Sincronización automática de publicaciones removida en consulta visual
        
    return serialize_case(c)

@app.get("/api/cases/{radicado}/fuentes")
@app.get("/cases/{radicado}/fuentes")
async def get_case_sources_history_endpoint(
    radicado: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from backend.models import CaseSearchSourceResult
    r = clean_str(radicado)
    if not r:
        raise HTTPException(400, "Radicado no especificado")
        
    q = db.query(CaseSearchSourceResult).filter(CaseSearchSourceResult.radicado == r)
    if not (current_user.is_superadmin or (current_user.is_admin and not current_user.company_id)):
        q = q.filter(CaseSearchSourceResult.company_id == current_user.company_id)
        
    results = q.order_by(CaseSearchSourceResult.created_at.desc()).all()
    
    return [
        {
            "id": res.id,
            "case_id": res.case_id,
            "company_id": res.company_id,
            "radicado": res.radicado,
            "fuente": res.fuente,
            "tipo_fuente": res.tipo_fuente,
            "url": res.url,
            "encontrado": res.encontrado,
            "confianza": res.confianza,
            "estado": res.estado,
            "mensaje": res.mensaje,
            "datos_extraidos_json": json.loads(res.datos_extraidos_json) if res.datos_extraidos_json else None,
            "raw_response": json.loads(res.raw_response) if (res.raw_response and res.raw_response.startswith("{")) else res.raw_response,
            "error_type": res.error_type,
            "http_status": res.http_status,
            "duration_ms": res.duration_ms,
            "source_order": res.source_order,
            "force": res.force,
            "requiere_revision": res.requiere_revision,
            "created_by": res.created_by,
            "created_at": res.created_at.isoformat() if res.created_at else None,
        }
        for res in results
    ]

@app.post("/api/cases/{radicado}/buscar-nuevamente")
@app.post("/cases/{radicado}/buscar-nuevamente")
async def buscar_nuevamente_endpoint_route(
    radicado: str,
    req: Optional[BuscarNuevamenteRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from backend.service.fallback_search import search_radicado_with_fallbacks
    
    company_id = req.company_id if req else None
    if current_user.is_superadmin or (current_user.is_admin and not current_user.company_id):
        if not company_id:
            raise HTTPException(400, "Selecciona una empresa para asociar el radicado.")
    else:
        company_id = current_user.company_id
        
    result = await search_radicado_with_fallbacks(
        radicado=radicado,
        company_id=company_id,
        db=db,
        current_user=current_user,
        force=True
    )
    
    if result["status"] in ["found", "found_alternative"] and result.get("case") is not None:
        result["case"] = serialize_case(result["case"])
        
    return result

@app.get("/cases/{case_id}")
async def get_case_by_id(case_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(404, "Caso no encontrado")
        
    if not is_global_superadmin(current_user):
        if c.company_id != current_user.company_id:
            if (c.company_id in (1, None) or c.company_id is None) and current_user.company_id:
                c.company_id = current_user.company_id
                c.user_id = current_user.id
                db.commit()
            else:
                raise HTTPException(403, "No tienes acceso a este caso")
        
    return serialize_case(c)

@app.get("/api/cases/id/{case_id}")
@app.get("/cases/id/{case_id}")
async def get_case_by_id_prefixed(case_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return await get_case_by_id(case_id, db, current_user)

@app.get("/api/cases/{case_id}/multisource-checks")
@app.get("/cases/{case_id}/multisource-checks")
async def get_case_multisource_checks(
    case_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from backend.models import CaseSourceCheck
    # Verify case exists
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
        
    # Enforce company isolation
    is_sa = is_global_superadmin(current_user)
    if not is_sa and c.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a los datos de esta empresa.")
        
    # Fetch logs from case_source_checks
    logs = db.query(CaseSourceCheck).filter(CaseSourceCheck.case_id == case_id).order_by(CaseSourceCheck.id.desc()).all()
    
    # Format according to user role (SuperAdmin sees full debug, regular users see summary)
    res_list = []
    for l in logs:
        item = {
            "source": l.source,
            "status": l.status,
            "checked_at": l.checked_at.isoformat() if l.checked_at else None,
            "records_found": l.records_found
        }
        if is_sa:
            # Superadmin gets full details
            item.update({
                "id": l.id,
                "url": l.source_url,
                "duration_ms": l.duration_ms,
                "error_message": l.error_message,
                "raw_summary": l.raw_summary
            })
        else:
            # Filtered info for regular clients
            if l.status == "error":
                item["error_message"] = "Ocurrió un error temporal al consultar esta fuente."
            elif l.status == "unsupported":
                item["error_message"] = "Fuente requiere validación manual, captcha o autenticación."
        res_list.append(item)
        
    return res_list

@app.post("/api/cases/{case_id}/multisource-check")
@app.post("/cases/{case_id}/multisource-check")
async def trigger_case_multisource_check(
    case_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from backend.models import CaseSourceCheck
    from backend.services.judicial_sources.source_router import run_multisource_check
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
        
    # Enforce company isolation
    is_sa = is_global_superadmin(current_user)
    if not is_sa and c.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a los datos de esta empresa.")
        
    # Enqueue as background task
    async def run_check_task():
        task_db = SessionLocal()
        try:
            effective_sources = ["PUBLICACIONES_PROCESALES", "TYBA", "SIUGJ", "SAMAI"]
            from backend.services.judicial_sources.config import MULTISOURCE_ENABLED as is_enabled, MULTISOURCE_DRY_RUN as is_dry_run
            
            if not is_enabled:
                # Log as skipped
                for src in effective_sources:
                    db_log = CaseSourceCheck(
                        company_id=c.company_id,
                        case_id=c.id,
                        radicado=c.radicado,
                        source=src,
                        source_url="",
                        status="skipped",
                        checked_at=datetime.utcnow(),
                        duration_ms=0,
                        error_message="Funcionalidad multifuente desactivada globalmente (MULTISOURCE_ENABLED = false).",
                        records_found=0,
                        created_at=datetime.utcnow()
                    )
                    task_db.add(db_log)
                task_db.commit()
            else:
                # Run the actual stubs/connectors
                await run_multisource_check(
                    radicado=c.radicado,
                    company_id=c.company_id,
                    case_id=c.id,
                    sources=effective_sources,
                    dry_run=is_dry_run, # respects MULTISOURCE_DRY_RUN
                    db=task_db
                )
        except Exception as e:
            print(f"[BACKGROUND-TASK-ERROR] multisource check failed: {e}")
        finally:
            task_db.close()
            
    background_tasks.add_task(run_check_task)
    return {"ok": True, "message": "Consulta multifuente encolada en segundo plano."}


# Legacy get_case_by_radicado endpoint removed to prevent route shadowing and tenant violations.


async def trigger_publications_sync(case: Case, item_act: dict, db_session: Session):
    """Tarea en segundo plano para sincronizar con el portal de Publicaciones."""
    try:
        from backend.models import CasePublication
        from backend.service.publicaciones import consultar_publicaciones_rango, parse_fecha_pub
        radicado = case.radicado
        fecha_act = item_act.get("event_date") # "YYYY-MM-DD"
        
        pubs = await consultar_publicaciones_rango(radicado, fecha_act, case.demandante or "", case.demandado or "")
        
        if pubs:
            for p in pubs:
                f_pub = parse_fecha_pub(p.get("fecha"))
                exists = db_session.query(CasePublication).filter(
                    CasePublication.case_id == case.id,
                    CasePublication.source_id == p.get("source_id")
                ).first()
                if not exists:
                    f_est = parse_fecha_pub(p.get("fecha_estado_electronico")) if p.get("fecha_estado_electronico") else f_pub
                    db_session.add(CasePublication(
                        case_id=case.id,
                        fecha_publicacion=f_pub,
                        tipo_publicacion=p.get("tipo"),
                        descripcion=p.get("descripcion") or p.get("snippet"),
                        documento_url=p.get("documento_url"),
                        source_url=p.get("source_url"),
                        source_id=p.get("source_id"),
                        url_fuente_principal=p.get("url_fuente_principal"),
                        tipo_fuente_principal=p.get("tipo_fuente_principal"),
                        texto_fuente_principal=p.get("texto_fuente_principal"),
                        validada_por_fuente_principal=p.get("validada_por_fuente_principal", False),
                        numero_estado=p.get("numero_estado"),
                        fecha_estado_electronico=f_est,
                        url_resumen_publicacion=p.get("url_resumen_publicacion"),
                        url_cuadro=p.get("url_cuadro"),
                        url_providencia=p.get("url_providencia"),
                        documentos_complementarios=p.get("documentos_complementarios"),
                        match_fuerte=p.get("match_fuerte", False),
                        match_type=p.get("match_type"),
                        motivo_match=p.get("motivo_match"),
                        observacion=p.get("observacion")
                    ))
            db_session.commit()
            print(f"[sync-pub] {len(pubs)} publicaciones sincronizadas para {radicado}")
    except Exception as e:
        print(f"[sync-pub] Error sincronizando publicaciones: {e}")

@app.get("/api/cases/by-radicado/{radicado}")
@app.get("/cases/by-radicado/{radicado}")
async def get_case_by_radicado_endpoint(
    radicado: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Busca un caso por radicado. Primero en BD local, luego en Rama Judicial.
    Esto alimenta la p?gina de 'Consultar Caso'.
    """
    r = clean_str(radicado)
    if not r:
        raise HTTPException(400, "Radicado inv?lido")

    # 1. Buscar en BD local
    existing_items = db.query(Case).filter(Case.radicado == r).all()
    if existing_items:
        local_results = []
        for c in existing_items:
            # Multi-tenancy check / Auto-linking
            if is_global_superadmin(current_user) or c.company_id == current_user.company_id or (c.company_id in (1, None) and current_user.company_id):
                if c.company_id != current_user.company_id and current_user.company_id:
                    c.company_id = current_user.company_id
                    c.user_id = current_user.id
                    db.commit()
                
                local_results.append({
                    "id": c.id,
                    "radicado": c.radicado,
                    "demandante": c.demandante or "?",
                    "demandado": c.demandado or "?",
                    "juzgado": c.juzgado or "?",
                    "fecha_radicacion": c.fecha_radicacion.isoformat() if c.fecha_radicacion else None,
                    "note": "Caso encontrado en el sistema local."
                })
        
        # Ordenar local por fecha más reciente
        local_results.sort(key=lambda x: x['fecha_radicacion'] or '', reverse=True)
        if local_results:
            return local_results

    # 2. Si no existe, buscar en Rama Judicial (Live)
    try:
        # Búsqueda inicial rápida (pocos reintentos)
        # Usamos wait_for para asegurar que no se quede pegado más de 25s
        resp = await asyncio.wait_for(consulta_por_radicado(r), timeout=25.0)
        items = extract_items(resp)
        if not items:
            raise HTTPException(404, f"No se encontró el radicado {r} en la Rama Judicial")

        async def fetch_process_data(p):
            id_p = p.get("idProceso")
            det = None
            acts = []
            if id_p:
                try:
                    # Detalle rápido (1 reintento para velocidad)
                    from backend.service.rama import _get
                    det = await _get(f"/Proceso/Detalle/{id_p}", retries=1)
                except:
                    pass
                try:
                    acts_resp = await actuaciones_proceso(int(id_p))
                    if isinstance(acts_resp, dict):
                        acts = acts_resp.get("actuaciones") or acts_resp.get("items") or []
                    elif isinstance(acts_resp, list):
                        acts = acts_resp
                except:
                    pass
            
            sujetos_raw = None
            if det:
                sujetos_raw = det.get("sujetosProcesales")
            if not sujetos_raw:
                sujetos_raw = p.get("sujetosProcesales")
                
            dem, ddo, abo = parse_sujetos_procesales(sujetos_raw)
            f_rad, f_ult = extract_fecha_proceso(p, det)
            
            return {
                "radicado": r,
                "demandante": dem or "?",
                "demandado": ddo or "?",
                "juzgado": p.get("despacho") or "?",
                "id_proceso": id_p,
                "fecha_radicacion": f_rad,
                "ultima_actuacion": f_ult,
                "actuaciones": acts,
                "note": "Caso encontrado en tiempo real (En línea)."
            }

        # PROCESAMIENTO PARALELO (SENIOR OPTIMIZATION)
        results = await asyncio.gather(*[fetch_process_data(p) for p in items[:15]])
        
        # FILTRO DINÁMICO: Preferir FNA o TRIADA para usuarios FNA, o mostrar todo para Jurico
        is_jurico = "jurico" in current_user.username.lower() or current_user.id == 2 or current_user.username == "juricob"
        filtered_results = results
        if not is_jurico:
            filtered_results = [r for r in results if _es_fna(r.get("demandante", ""))]
            if not filtered_results:
                filtered_results = results
        
        saved_results = []
        for r_item in filtered_results:
            id_proceso_str = str(r_item["id_proceso"]) if r_item["id_proceso"] else None
            
            c = db.query(Case).filter(Case.id_proceso == id_proceso_str).first() if id_proceso_str else None
            if not c:
                c = Case(
                    radicado=r_item["radicado"],
                    id_proceso=id_proceso_str,
                    demandante=r_item["demandante"],
                    demandado=r_item["demandado"],
                    juzgado=r_item["juzgado"],
                    fecha_radicacion=parse_fecha(r_item["fecha_radicacion"]),
                    ultima_actuacion=parse_fecha(r_item["ultima_actuacion"]),
                    company_id=current_user.company_id if current_user else None,
                    user_id=current_user.id if current_user else None,
                    last_check_at=now_colombia()
                )
                db.add(c)
                db.flush()
                
                acts = r_item.get("actuaciones", [])
                if acts:
                    for a in acts:
                        con_docs = bool(a.get("conDocumentos")) if a.get("conDocumentos") is not None else False
                        it = {
                            "id_reg_actuacion": a.get("idRegActuacion"),
                            "cons_actuacion": a.get("consActuacion"),
                            "fecha_actuacion": a.get("fechaActuacion"),
                            "actuacion": a.get("actuacion"),
                            "anotacion": a.get("anotacion"),
                            "fecha_inicial": a.get("fechaInicial"),
                            "fecha_final": a.get("fechaFinal"),
                            "fecha_registro": a.get("fechaRegistro"),
                            "con_documentos": con_docs,
                            "cant_documentos": 1 if con_docs else 0
                        }
                        save_event(db, c.id, it, company_id=current_user.company_id if current_user else None)
                        if con_docs:
                            c.has_documents = True
                    db.flush()
            else:
                # Asegurar que el caso existente tenga el company_id y user_id adecuados
                if current_user and current_user.company_id and not c.company_id:
                    c.company_id = current_user.company_id
                if current_user and not c.user_id:
                    c.user_id = current_user.id
                db.flush()

            saved_results.append({
                "id": c.id,
                "radicado": c.radicado,
                "demandante": c.demandante or "?",
                "demandado": c.demandado or "?",
                "juzgado": c.juzgado or "?",
                "fecha_radicacion": c.fecha_radicacion.isoformat() if c.fecha_radicacion else None,
                "note": "Caso encontrado en tiempo real y registrado en el sistema."
            })
        
        db.commit()

        # ORDENAMIENTO: Fecha de radicación más reciente primero
        # La fecha de radicación es la que el usuario prefiere como criterio principal
        sorted_results = sorted(saved_results, key=lambda x: x.get('fecha_radicacion') or '', reverse=True)
        
        return sorted_results

    except asyncio.TimeoutError:
        raise HTTPException(408, "La Rama Judicial est? respondiendo muy lento. Por favor, intenta de nuevo en unos minutos.")
    except RamaError as e:
        raise HTTPException(502, f"Error Rama Judicial: {str(e)}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Error interno buscando radicado: {str(e)}")

@app.get("/api/cases/id/{case_id}/events")
@app.get("/cases/id/{case_id}/events")
async def get_events_by_id(
    case_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(404, "Caso no encontrado")
        
    if not is_global_superadmin(current_user):
        if c.company_id != current_user.company_id:
            if (c.company_id in (1, None) or c.company_id is None) and current_user.company_id:
                c.company_id = current_user.company_id
                c.user_id = current_user.id
                db.commit()
            else:
                raise HTTPException(403, "No tienes acceso a este caso")
                
    return await events_logic(c, db)

@app.get("/api/cases/by-radicado/{radicado}/events")
@app.get("/cases/by-radicado/{radicado}/events")
@app.get("/api/cases/{radicado}/events")
@app.get("/cases/{radicado}/events")
async def get_events_by_radicado_unified(
    radicado: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    r = clean_str(radicado)
    q_case = db.query(Case)
    if not is_global_superadmin(current_user):
        q_case = q_case.filter(Case.company_id == current_user.company_id)
        
    # Si es un numero corto, intentarlo como ID por si acaso el frontend se equivoca
    if r.isdigit() and len(r) < 10:
        c = q_case.filter(Case.id == int(r)).first()
        if c: return await events_logic(c, db)
    
    c = q_case.filter(Case.radicado == r).order_by(Case.id.desc()).first()
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    return await events_logic(c, db)

async def events_logic(c: Case, db: Session):
    """
    LOGICA OPTIMIZADA: 
    1. Retorna datos de la BD local inmediatamente (Ultra-rapido).
    2. Si los datos son viejos (>12h) o no hay, dispara sync en segundo plano.
    """
    try:
        radicado = c.radicado
        
        # 1. Obtener datos locales actuales ordenados por fecha de actuación (más reciente arriba)
        db_events = db.query(CaseEvent).filter(CaseEvent.case_id == c.id).order_by(desc(CaseEvent.event_date), desc(CaseEvent.id)).all()
        
        # 2. Decidir si necesitamos refrescar (siempre en segundo plano para no bloquear)
        needs_refresh = False
        if not db_events:
            needs_refresh = True
        elif not c.last_check_at or (now_colombia() - c.last_check_at).total_seconds() > 43200:
            needs_refresh = True
        else:
            has_missing_docs_ids = any(e.con_documentos and not e.id_reg_actuacion for e in db_events)
            if has_missing_docs_ids:
                needs_refresh = True
            
        if needs_refresh:
            print(f"[SYNC] Disparando actualizacion para {radicado}")
            # Si no hay eventos, lo hacemos Sincrono la primera vez para que el usuario vea algo
            if not db_events:
                await sync_case_events_background(c.id)
                db_events = db.query(CaseEvent).filter(CaseEvent.case_id == c.id).order_by(desc(CaseEvent.event_date), desc(CaseEvent.id)).all()
                if not db_events and c.ultima_actuacion:
                    return {"items": [], "total": 0, "warning": "El proceso tiene fecha de última actuación, pero el historial aún no está cargado o fue bloqueado. Presiona Actualizar para sincronizar."}
                elif not db_events:
                    return {"items": [], "total": 0, "warning": "No fue posible obtener nuevas actuaciones o el proceso no tiene historial registrado."}
            else:
                # Si ya hay datos, el refresh se hace en segundo plano
                asyncio.create_task(sync_case_events_background(c.id))

        # 2b. Disparar búsqueda automática de publicaciones si existen actuaciones relevantes
        has_relevant = any(is_relevant_actuacion(e.title) for e in db_events)
        if has_relevant:
            asyncio.create_task(save_new_publications_task(c.id))

        # 3. Formatear para el frontend
        result_items = []
        for e in db_events:
            result_items.append({
                "id_reg_actuacion": e.id_reg_actuacion,
                "cons_actuacion": e.cons_actuacion,
                "llave_proceso": radicado,
                "event_date": e.event_date,
                "title": e.title,
                "detail": e.detail,
                "con_documentos": e.con_documentos,
            })
            
        return {"items": result_items, "total": len(result_items)}

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Error procesando actuaciones: {str(e)}")

async def sync_case_events_background(case_id: int):
    """Tarea asincrona para actualizar un caso sin bloquear al usuario."""
    db = SessionLocal()
    try:
        c = db.query(Case).filter(Case.id == case_id).first()
        if not c: return
        
        # Si es un caso de la SIC (Superintendencia de Industria y Comercio)
        if c.juzgado == "SIC" or c.fuente_encontrado == "SIC" or bool(re.match(r'^(?:20)?\d{2}-\d+$', str(c.radicado).strip())):
            try:
                from backend.services.judicial_sources import CONNECTORS
                sic_conn = CONNECTORS.get("SIC")
                meta = {"cedula": c.cedula, "demandante": c.demandante, "demandado": c.demandado, "estado": c.estado}
                sic_res = sic_conn.search_case(c.radicado, metadata=meta)
                sic_data = sic_res.get("data", {})
                
                acts = sic_data.get("actuaciones", [])
                for a in acts:
                    act_date = a.get("fecha")
                    act_title = (a.get("actuacion") or "Actuación SIC").strip()
                    act_detail = a.get("anotacion") or ""
                    ev_hash = sha256_obj({"event_date": act_date, "title": act_title, "detail": act_detail})
                    
                    exists = db.query(CaseEvent).filter(
                        CaseEvent.case_id == c.id,
                        CaseEvent.event_hash == ev_hash
                    ).first()
                    if not exists:
                        db.add(CaseEvent(
                            case_id=c.id,
                            company_id=c.company_id,
                            event_date=act_date,
                            title=act_title,
                            detail=act_detail,
                            event_hash=ev_hash,
                            con_documentos=bool(a.get("url_documento"))
                        ))
                
                if acts:
                    c.ultima_actuacion = parse_fecha(acts[0].get("fecha"))
                    c.fecha_radicacion = parse_fecha(acts[-1].get("fecha"))
                    c.has_documents = True
                    
                c.last_check_at = now_colombia()
                db.commit()
                return
            except Exception as sic_err:
                print(f"[SYNC-SIC] Error actualizando caso SIC {c.radicado}: {sic_err}")
                return

        id_proceso = c.id_proceso
        if not id_proceso:
            id_proceso = await obtener_id_proceso(c.radicado)
            if id_proceso:
                c.id_proceso = str(id_proceso)
                db.flush()
        
        if not id_proceso: return

        acts_resp = await actuaciones_proceso(int(id_proceso))
        acts = []
        if isinstance(acts_resp, dict):
            acts = acts_resp.get("actuaciones") or acts_resp.get("items") or []
        elif isinstance(acts_resp, list):
            acts = acts_resp

        if not acts and c.ultima_actuacion:
            print(f"[SYNC] Advertencia: No se obtuvieron actuaciones para {c.radicado} pero tiene ultima_actuacion.")
            # No borramos el historial anterior si falla la respuesta.

        new_count = 0
        for a in acts:
            it = {
                "event_date": a.get("fechaActuacion"),
                "title": (a.get("actuacion") or "").strip(),
                "detail": a.get("anotacion"),
            }
            event_hash = sha256_obj(it)
            con_docs = bool(a.get("conDocumentos"))
            exists = db.query(CaseEvent).filter(
                CaseEvent.case_id == c.id,
                CaseEvent.event_hash == event_hash
            ).first()
            
            # FALLBACK REFORZADO: Buscar por fecha, título y detalle para evitar duplicidad total
            if not exists:
                exists = db.query(CaseEvent).filter(
                    CaseEvent.case_id == c.id,
                    CaseEvent.event_date == it["event_date"],
                    CaseEvent.title == it["title"],
                    CaseEvent.detail == it["detail"]
                ).first()
                if exists:
                    # Actualizamos el hash al nuevo formato para que el 'if not exists' lo encuentre la próxima vez
                    exists.event_hash = event_hash
            
            if not exists:
                db.add(CaseEvent(
                    case_id=c.id,
                    company_id=c.company_id,
                    event_date=it["event_date"],
                    title=it["title"],
                    detail=it["detail"],
                    event_hash=event_hash,
                    con_documentos=con_docs,
                    id_reg_actuacion=a.get("idRegActuacion"),
                    cons_actuacion=a.get("consActuacion"),
                ))
                
                # AUTOMATIZACIÓN: Si la nueva actuación es relevante, disparar búsqueda de publicaciones
                if is_relevant_actuacion(it["title"]):
                    # Usamos la función local definida más abajo en este mismo archivo
                    asyncio.create_task(save_new_publications_task(c.id))

                if con_docs: c.has_documents = True
                new_count += 1
            else:
                # Si existe pero no tiene los IDs técnicos (caso de migración), los actualizamos
                if con_docs and (not exists.id_reg_actuacion or not exists.cons_actuacion):
                    exists.id_reg_actuacion = a.get("idRegActuacion")
                    exists.cons_actuacion = a.get("consActuacion")
                    exists.con_documentos = True
                    c.has_documents = True
                    new_count += 1
        
        c.last_check_at = now_colombia()
        db.commit()

        try:
            from backend.service.publicaciones import auto_queue_publicaciones_for_case
            auto_queue_publicaciones_for_case(db, c)
        except Exception as pub_queue_err:
            print(f"[BG-SYNC] Error auto-queueing publications for {c.radicado}: {pub_queue_err}")

        if new_count > 0:
            print(f"[BG-SYNC] {new_count} nuevas actuaciones encontradas para {c.radicado}")
    except Exception as e:
        print(f"[BG-SYNC] Error sincronizando {case_id}: {e}")
    finally:
        db.close()

# =========================
# DOWNLOAD EVENTS EXCEL
# =========================
@app.get("/cases/by-radicado/{radicado}/events.xlsx")
async def download_events_xlsx(
    radicado: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    r = clean_str(radicado)
    if not r:
        raise HTTPException(400, "Radicado requerido")

    case = db.query(Case).filter(Case.radicado == r).first()
    if case:
        if not is_global_superadmin(current_user) and case.company_id != current_user.company_id:
            raise HTTPException(403, "No tienes acceso a los eventos de este caso.")
    else:
        if not is_global_superadmin(current_user):
            raise HTTPException(404, "El caso consultado no existe o no pertenece a tu empresa.")

    try:
        id_proceso = await obtener_id_proceso(r)
    except RamaError as e:
        raise HTTPException(502, f"Error Rama Judicial: {str(e)}")

    if not id_proceso:
        raise HTTPException(404, "No se encontr el proceso")

    try:
        acts_resp = await actuaciones_proceso(int(id_proceso))
    except RamaError as e:
        raise HTTPException(502, f"Error obteniendo actuaciones: {str(e)}")

    acts = []
    if isinstance(acts_resp, dict):
        acts = acts_resp.get("actuaciones") or acts_resp.get("items") or []
    elif isinstance(acts_resp, list):
        acts = acts_resp

    df = pd.DataFrame([{
        "Radicado": r,
        "FechaActuacion": a.get("fechaActuacion"),
        "Actuacion": a.get("actuacion"),
        "Anotacion": a.get("anotacion"),
        "FechaInicial": a.get("fechaInicial"),
        "FechaFinal": a.get("fechaFinal"),
        "FechaRegistro": a.get("fechaRegistro"),
    } for a in acts])

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Actuaciones")
    output.seek(0)

    filename = f"actuaciones_{r[:20]}_{now_colombia().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/cases/id/{case_id}/events.xlsx")
async def download_events_by_id_xlsx(
    case_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    c = db.query(Case).filter(Case.id == case_id).first()
    if not c:
        raise HTTPException(404, "Caso no encontrado")

    if not is_global_superadmin(current_user) and c.company_id != current_user.company_id:
        raise HTTPException(403, "No tienes acceso a los eventos de este caso.")

    id_proceso = c.id_proceso
    if not id_proceso:
        # Fallback a buscar por radicado si no tiene ID proceso
        try:
            id_proceso = await obtener_id_proceso(c.radicado)
        except:
            raise HTTPException(404, "ID de proceso no disponible")

    if not id_proceso:
        raise HTTPException(404, "ID de proceso no disponible")

    try:
        acts_resp = await actuaciones_proceso(int(id_proceso))
    except RamaError as e:
        raise HTTPException(502, f"Error obteniendo actuaciones: {str(e)}")

    acts = []
    if isinstance(acts_resp, dict):
        acts = acts_resp.get("actuaciones") or acts_resp.get("items") or []
    elif isinstance(acts_resp, list):
        acts = acts_resp

    df = pd.DataFrame([{
        "Radicado": c.radicado,
        "ID_Proceso": id_proceso,
        "Juzgado": c.juzgado,
        "FechaActuacion": a.get("fechaActuacion"),
        "Actuacion": a.get("actuacion"),
        "Anotacion": a.get("anotacion"),
        "FechaInicial": a.get("fechaInicial"),
        "FechaFinal": a.get("fechaFinal"),
        "FechaRegistro": a.get("fechaRegistro"),
    } for a in acts])

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Actuaciones")
    output.seek(0)

    filename = f"actuaciones_{c.radicado[:15]}_{id_proceso}_{now_colombia().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =========================
# DOWNLOAD MULTIPLE EVENTS
# =========================
@app.post("/cases/events/download-multiple")
async def download_multiple_events_excel(
    radicados: List[str] = Body(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Enforce multi-tenancy filter
    cleaned_rads = []
    case_info = {}
    for rad in radicados:
        r = clean_str(rad)
        if not r:
            continue
        c = db.query(Case).filter(Case.radicado == r).first()
        if c:
            if is_global_superadmin(current_user) or c.company_id == current_user.company_id:
                cleaned_rads.append(r)
                case_info[r] = {
                    "demandante": c.demandante or "",
                    "demandado": c.demandado or "",
                    "juzgado": c.juzgado or ""
                }
        else:
            if is_global_superadmin(current_user):
                cleaned_rads.append(r)
                case_info[r] = {
                    "demandante": "",
                    "demandado": "",
                    "juzgado": ""
                }
                
    if not cleaned_rads:
        raise HTTPException(403, "No tienes acceso a ninguno de los radicados especificados.")

    # Release database connection prior to slow async operations
    db.close()

    try:
        MAX_ROWS = 1_000_000
        all_data = []

        for i, rad in enumerate(cleaned_rads):
            if len(all_data) >= MAX_ROWS:
                continue

            if i > 0:
                await delay_between_requests(0.2, 0.4)

            try:
                id_proceso = await obtener_id_proceso(rad)
                if not id_proceso:
                    continue

                acts_resp = await actuaciones_proceso(int(id_proceso))
                acts = []
                if isinstance(acts_resp, dict):
                    acts = acts_resp.get("actuaciones") or acts_resp.get("items") or []
                elif isinstance(acts_resp, list):
                    acts = acts_resp

                if len(all_data) + len(acts) > MAX_ROWS:
                    break

                info = case_info.get(rad) or {"demandante": "", "demandado": "", "juzgado": ""}

                for a in acts:
                    all_data.append({
                        "Radicado": rad,
                        "Demandante": info["demandante"],
                        "Demandado": info["demandado"],
                        "Juzgado": info["juzgado"],
                        "FechaActuacion": a.get("fechaActuacion"),
                        "Actuacion": a.get("actuacion"),
                        "Anotacion": a.get("anotacion"),
                        "FechaInicial": a.get("fechaInicial"),
                        "FechaFinal": a.get("fechaFinal"),
                        "FechaRegistro": a.get("fechaRegistro"),
                    })
            except Exception:
                continue

        if not all_data:
            raise HTTPException(404, "No hay actuaciones para descargar")

        df = pd.DataFrame(all_data)
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Actuaciones")
        output.seek(0)

        filename = f"actuaciones_multiple_{now_colombia().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error generando Excel: {str(e)}")


# =========================
# BACKGROUND VALIDATE PENDIENTES
# =========================
async def _background_validate_pendientes():
    BATCH = 50
    DELAY = 2.0
    MAX_CYCLES = 20

    print("[BG-VALIDATE] Iniciando validacion automatica de pendientes...")
    for cycle in range(MAX_CYCLES):
        db = None
        try:
            db = SessionLocal()
            pendientes = db.query(Case.radicado, Case.company_id).filter(Case.juzgado.is_(None)).limit(BATCH).all()
            if not pendientes:
                print(" [bg-validate] Sin pendientes. Fin.")
                break

            pendientes_list = [(p.radicado, p.company_id) for p in pendientes]
            db.close()
            db = None

            print(f" [bg-validate] Ciclo {cycle+1}: {len(pendientes_list)} casos...")
            for i, (radicado, company_id) in enumerate(pendientes_list):
                try:
                    if i > 0:
                        await asyncio.sleep(DELAY + random.uniform(0, 0.8))
                    
                    db_run = SessionLocal()
                    try:
                        result = await validar_radicado_completo(radicado, db_run, is_new_import=True)
                        if result["found"]:
                            inv = db_run.query(InvalidRadicado).filter(InvalidRadicado.radicado == radicado).first()
                            if inv:
                                db_run.delete(inv)
                        else:
                            inv = db_run.query(InvalidRadicado).filter(InvalidRadicado.radicado == radicado).first()
                            if inv:
                                inv.intentos += 1
                                inv.updated_at = now_colombia()
                            else:
                                db_run.add(InvalidRadicado(radicado=radicado, motivo="No encontrado en Rama Judicial", intentos=1, company_id=company_id))
                            
                            # Eliminar el caso de la tabla cases para que no quede como pendiente
                            case_to_del = db_run.query(Case).filter(Case.radicado == radicado, Case.company_id == company_id).first()
                            if case_to_del:
                                db_run.delete(case_to_del)
                        db_run.commit()
                    except Exception as run_err:
                        db_run.rollback()
                        raise run_err
                    finally:
                        db_run.close()
                except Exception as e:
                    print(f"    [bg-validate] Error en {radicado}: {e}")

            db = SessionLocal()
            remaining = db.query(Case).filter(Case.juzgado.is_(None)).count()
            print(f" [bg-validate] Restantes: {remaining}")
            if remaining == 0:
                break

            await asyncio.sleep(5)

        except Exception as e:
            print(f" [bg-validate] Error ciclo {cycle+1}: {e}")
        finally:
            if db:
                db.close()

    print(" [bg-validate] Validacin automtica finalizada.")


# =========================
# IMPORT EXCEL (ASINCRONO CON SEGUIMIENTO)
# =========================
def process_excel_import_task(
    job_id: int, 
    content: bytes, 
    is_csv: bool, 
    company_id: Optional[int], 
    user_id: int, 
    loop: asyncio.AbstractEventLoop
):
    db = SessionLocal()
    job = db.query(ExcelImportJob).filter(ExcelImportJob.id == job_id).first()
    if not job:
        db.close()
        return

    try:
        job.estado = "procesando"
        db.commit()

        # Parsear DataFrame
        if is_csv:
            df = pd.read_csv(BytesIO(content))
        else:
            df = pd.read_excel(BytesIO(content))

        df.columns = [str(c).strip() for c in df.columns]
        cols_lower = {c.lower(): c for c in df.columns}
        rad_col = next((cols_lower[k] for k in ["radicado", "numero", "proceso"] if k in cols_lower), None)
        ced_col = next((cols_lower[k] for k in ["cedula", "identificacion", "documento"] if k in cols_lower), None)
        abo_col = next((cols_lower[k] for k in ["abogado", "apoderado"] if k in cols_lower), None)

        if not rad_col:
            raise ValueError("Falta la columna 'Radicado' en el archivo.")

        # Limpiar y preparar filas
        rows_to_process = []
        for index, row in df.iterrows():
            radicado = clean_str(row.get(rad_col))
            if not radicado:
                continue
            cedula = str(row.get(ced_col)).strip() if ced_col and pd.notna(row.get(ced_col)) else None
            abogado = str(row.get(abo_col)).strip() if abo_col and pd.notna(row.get(abo_col)) else None
            
            if cedula and (cedula.lower() == "nan" or cedula == ""): 
                cedula = None
            if abogado and (abogado.lower() == "nan" or abogado == ""): 
                abogado = None
                
            rows_to_process.append((radicado, cedula, abogado))

        job.total_filas = len(rows_to_process)
        db.commit()

        created = 0
        updated = 0
        skipped = 0
        processed = 0
        errors = []

        batch_size = 200
        for i in range(0, len(rows_to_process), batch_size):
            batch = rows_to_process[i:i+batch_size]
            
            try:
                for radicado, cedula, abogado in batch:
                    # Tenant isolation en busqueda de caso
                    q_case = db.query(Case).filter(Case.radicado == radicado)
                    if company_id:
                        q_case = q_case.filter(Case.company_id == company_id)
                    existing_cases = q_case.all()
                    
                    if existing_cases:
                        for c in existing_cases:
                            c.cedula = cedula or c.cedula
                            c.abogado = abogado or c.abogado
                        updated += 1
                    else:
                        # Limpiar de invalid_radicados si existia en la misma empresa
                        q_inv = db.query(InvalidRadicado).filter(InvalidRadicado.radicado == radicado)
                        if company_id:
                            q_inv = q_inv.filter(InvalidRadicado.company_id == company_id)
                        existing_invalid = q_inv.first()
                        if existing_invalid:
                            db.delete(existing_invalid)
                            db.flush()

                        db.add(Case(
                            radicado=radicado, 
                            cedula=cedula, 
                            abogado=abogado, 
                            user_id=user_id,
                            company_id=company_id
                        ))
                        created += 1
                    
                    processed += 1
                
                db.commit()
            except Exception as batch_err:
                db.rollback()
                skipped_batch_size = len(batch)
                skipped += skipped_batch_size
                processed += skipped_batch_size
                batch_err_msg = f"Error en lote {i//batch_size + 1}: {str(batch_err)}"
                print(f" [import-excel] {batch_err_msg}")
                errors.append(batch_err_msg)
            
            # Actualizar progreso
            try:
                job.filas_procesadas = processed
                job.filas_creadas = created
                job.filas_actualizadas = updated
                if errors:
                    job.errores_parciales = "\n".join(errors)[:4000] # Limitar texto para evitar overflow en DB
                db.commit()
            except Exception as prog_err:
                print(f" [import-excel] Error actualizando progreso del job: {prog_err}")
                db.rollback()

        # Finalizar
        job.estado = "finalizado"
        job.fecha_fin = datetime.utcnow()
        db.commit()

        if created > 0:
            loop.call_soon_threadsafe(lambda: asyncio.create_task(_background_validate_pendientes()))

    except Exception as e:
        print(f" [import-excel] Error critico procesando job {job_id}: {e}")
        try:
            job.estado = "error"
            job.fecha_fin = datetime.utcnow()
            job.errores_parciales = f"Error critico: {str(e)}"
            db.commit()
        except:
            db.rollback()
    finally:
        db.close()


@app.post("/cases/import-excel")
async def import_excel(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        name = (file.filename or "").lower()
        if not name.endswith((".xlsx", ".xls", ".csv")):
            raise HTTPException(400, "Sube un archivo .xlsx, .xls o .csv válido.")

        content = await file.read()
        is_csv = name.endswith(".csv")

        # Parsear DataFrame
        try:
            if is_csv:
                df = pd.read_csv(BytesIO(content), dtype=str)
            else:
                df = pd.read_excel(BytesIO(content), dtype=str)
        except Exception as read_err:
            raise HTTPException(400, f"No se pudo leer el archivo Excel/CSV: {str(read_err)}")

        if df.empty:
            raise HTTPException(400, "El archivo subido está vacío.")

        df.columns = [str(c).strip() for c in df.columns]
        cols_lower = {c.lower(): c for c in df.columns}
        
        rad_col = next((cols_lower[k] for k in ["radicado", "numero", "proceso", "num_proceso", "radicacion"] if k in cols_lower), None)
        ced_col = next((cols_lower[k] for k in ["cc", "cedula", "identificacion", "documento", "nit"] if k in cols_lower), None)
        abo_col = next((cols_lower[k] for k in ["abogado", "apoderado", "responsable", "asignado"] if k in cols_lower), None)
        dte_col = next((cols_lower[k] for k in ["demandante", "actor", "solicitante"] if k in cols_lower), None)
        dda_col = next((cols_lower[k] for k in ["demandado", "demandando", "contraparte", "demandados"] if k in cols_lower), None)
        juz_col = next((cols_lower[k] for k in ["juzgado", "despacho", "autoridad", "tribunal"] if k in cols_lower), None)
        est_col = next((cols_lower[k] for k in ["estado", "estado_proceso", "situacion"] if k in cols_lower), None)

        if not rad_col:
            raise HTTPException(400, "Falta la columna 'Radicado' en el archivo Excel.")

        # Limpiar y preparar filas
        rows_to_process = []
        skipped_list = []
        for index, row in df.iterrows():
            raw_rad = row.get(rad_col)
            if pd.isna(raw_rad) or raw_rad is None or not str(raw_rad).strip():
                skipped_list.append({"radicado": f"Fila {index+2} (vacía)", "motivo": "Celda de radicado vacía"})
                continue
            radicado = str(raw_rad).strip().replace(".0", "")
            # Limpiar caracteres invisibles o de control pero conservar guiones de SIC (ej: 26-64018)
            radicado = re.sub(r'[\s\x00-\x1f\x7f-\x9f]', '', radicado)
            if not radicado or len(radicado) < 4:
                skipped_list.append({"radicado": str(raw_rad), "motivo": f"Radicado con longitud insuficiente ({len(radicado)} caracteres)"})
                continue

            def get_val(col_name):
                if not col_name:
                    return None
                val = row.get(col_name)
                if pd.isna(val) or val is None:
                    return None
                s = str(val).strip().replace(".0", "")
                return s if s and s.lower() not in ("nan", "none", "null", "") else None

            cedula = get_val(ced_col)
            abogado = get_val(abo_col)
            demandante = get_val(dte_col)
            demandado = get_val(dda_col)
            juzgado = get_val(juz_col)
            estado = get_val(est_col)
            
            # Autodetección de casos SIC
            is_sic = False
            if (juzgado and "SIC" in juzgado.upper()) or re.match(r'^(?:20)?\d{2}-\d+$', radicado):
                is_sic = True
                if not juzgado:
                    juzgado = "SIC"
                
            rows_to_process.append({
                "radicado": radicado,
                "cedula": cedula,
                "abogado": abogado,
                "demandante": demandante,
                "demandado": demandado,
                "juzgado": juzgado,
                "estado": estado,
                "is_sic": is_sic
            })

        if not rows_to_process and not skipped_list:
            raise HTTPException(400, "No se encontraron radicados válidos en el archivo.")

        created = 0
        updated = 0
        comp_id = current_user.company_id
        user_id = current_user.id

        # Procesamiento seguro por lotes (batches de 100)
        batch_size = 100
        for i in range(0, len(rows_to_process), batch_size):
            batch = rows_to_process[i:i+batch_size]
            batch_created = 0
            batch_updated = 0
            
            try:
                for item in batch:
                    rad = item["radicado"]
                    q_case = db.query(Case).filter(Case.radicado == rad)
                    if comp_id:
                        q_case = q_case.filter(Case.company_id == comp_id)
                    existing_cases = q_case.all()

                    if existing_cases:
                        for c in existing_cases:
                            if item["cedula"]: c.cedula = item["cedula"]
                            if item["abogado"]: c.abogado = item["abogado"]
                            if item["demandante"] and not c.demandante: c.demandante = item["demandante"]
                            if item["demandado"] and not c.demandado: c.demandado = item["demandado"]
                            if item["juzgado"] and not c.juzgado: c.juzgado = item["juzgado"]
                            if item["estado"] and not c.estado: c.estado = item["estado"]
                        batch_updated += 1
                    else:
                        # Limpiar de invalid_radicados si existia en la misma empresa
                        try:
                            q_inv = db.query(InvalidRadicado).filter(InvalidRadicado.radicado == rad)
                            if comp_id:
                                q_inv = q_inv.filter(InvalidRadicado.company_id == comp_id)
                            existing_invalid = q_inv.first()
                            if existing_invalid:
                                db.delete(existing_invalid)
                        except Exception:
                            pass

                        despacho_val = "Superintendencia de Industria y Comercio - SIC" if item["is_sic"] else None
                        fuente_val = "SIC" if item["is_sic"] else None
                        tipo_proc_val = "Demanda Protección al Consumidor Jurisdiccional" if item["is_sic"] else None

                        new_case = Case(
                            radicado=rad,
                            cedula=item["cedula"],
                            abogado=item["abogado"],
                            demandante=item["demandante"],
                            demandado=item["demandado"],
                            juzgado=item["juzgado"],
                            despacho=despacho_val,
                            fuente_encontrado=fuente_val,
                            tipo_proceso=tipo_proc_val,
                            estado=item["estado"],
                            user_id=user_id,
                            company_id=comp_id,
                            is_active=True
                        )
                        db.add(new_case)
                        batch_created += 1

                db.commit()
                created += batch_created
                updated += batch_updated
            except Exception as batch_err:
                db.rollback()
                print(f"[import-excel] Lote {i//batch_size + 1} falló en bloque: {batch_err}. Reintentando fila por fila...")
                # Reintento seguro fila por fila para rescatar todas las filas válidas del lote
                for item in batch:
                    try:
                        rad = item["radicado"]
                        q_case = db.query(Case).filter(Case.radicado == rad)
                        if comp_id:
                            q_case = q_case.filter(Case.company_id == comp_id)
                        existing_cases = q_case.all()

                        if existing_cases:
                            for c in existing_cases:
                                if item["cedula"]: c.cedula = item["cedula"]
                                if item["abogado"]: c.abogado = item["abogado"]
                                if item["demandante"] and not c.demandante: c.demandante = item["demandante"]
                                if item["demandado"] and not c.demandado: c.demandado = item["demandado"]
                                if item["juzgado"] and not c.juzgado: c.juzgado = item["juzgado"]
                                if item["estado"] and not c.estado: c.estado = item["estado"]
                            db.commit()
                            updated += 1
                        else:
                            despacho_val = "Superintendencia de Industria y Comercio - SIC" if item["is_sic"] else None
                            fuente_val = "SIC" if item["is_sic"] else None
                            tipo_proc_val = "Demanda Protección al Consumidor Jurisdiccional" if item["is_sic"] else None

                            new_case = Case(
                                radicado=rad,
                                cedula=item["cedula"],
                                abogado=item["abogado"],
                                demandante=item["demandante"],
                                demandado=item["demandado"],
                                juzgado=item["juzgado"],
                                despacho=despacho_val,
                                fuente_encontrado=fuente_val,
                                tipo_proceso=tipo_proc_val,
                                estado=item["estado"],
                                user_id=user_id,
                                company_id=comp_id,
                                is_active=True
                            )
                            db.add(new_case)
                            db.commit()
                            created += 1
                    except Exception as single_err:
                        db.rollback()
                        print(f"[import-excel] Fila {item.get('radicado')} omitida por error: {single_err}")
                        skipped_list.append({"radicado": item.get("radicado", "Fila"), "motivo": str(single_err)})

        # Disparar validacion asincrona en segundo plano si hay nuevos casos
        if created > 0:
            background_tasks.add_task(_background_validate_pendientes)

        return {
            "ok": True,
            "created": created,
            "updated": updated,
            "skipped": len(skipped_list),
            "skipped_list": skipped_list,
            "invalid_count": len(skipped_list)
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(500, f"Error al procesar el archivo Excel: {str(e)[:200]}")


@app.get("/cases/import-excel/status/{job_id}")
async def get_import_excel_status(
    job_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(ExcelImportJob).filter(ExcelImportJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Trabajo de importación no encontrado")
    
    if not is_global_superadmin(current_user) and job.company_id != current_user.company_id:
        raise HTTPException(403, "No tienes permisos para ver este trabajo de importación")
        
    return {
        "id": job.id,
        "company_id": job.company_id,
        "usuario_username": job.usuario_username,
        "estado": job.estado,
        "total_filas": job.total_filas,
        "filas_procesadas": job.filas_procesadas,
        "filas_creadas": job.filas_creadas,
        "filas_actualizadas": job.filas_actualizadas,
        "errores_parciales": job.errores_parciales,
        "fecha_inicio": job.fecha_inicio.isoformat() if job.fecha_inicio else None,
        "fecha_fin": job.fecha_fin.isoformat() if job.fecha_fin else None,
    }


@app.post("/cases/bulk-delete-excel")
async def bulk_delete_excel(file: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        name = (file.filename or "").lower()
        if not name.endswith((".xlsx", ".xls", ".csv")):
            raise HTTPException(400, "Sube un archivo .xlsx, .xls o .csv")

        content = await file.read()
        if name.endswith(".csv"):
            df = pd.read_csv(BytesIO(content))
        else:
            df = pd.read_excel(BytesIO(content))

        df.columns = [str(c).strip() for c in df.columns]
        cols_lower = {c.lower(): c for c in df.columns}
        rad_col = next((cols_lower[k] for k in ["radicado", "numero", "proceso"] if k in cols_lower), None)

        if not rad_col:
            raise HTTPException(400, "Falta la columna 'Radicado'")

        deleted_cases = 0
        count = 0
        batch_size = 20

        for _, row in df.iterrows():
            try:
                radicado = clean_str(row.get(rad_col))
                if not radicado:
                    continue

                # Buscar casos con ese radicado SOLO de la empresa del usuario
                q_cases = db.query(Case).filter(Case.radicado == radicado)
                if not is_global_superadmin(current_user):
                    q_cases = q_cases.filter(Case.company_id == current_user.company_id)
                cases = q_cases.all()
                for c in cases:
                    db.query(CaseEvent).filter(CaseEvent.case_id == c.id).delete()
                    db.query(CasePublication).filter(CasePublication.case_id == c.id).delete()
                    db.delete(c)
                    deleted_cases += 1
                
                # Limpiar de invalid solo los de la empresa del usuario
                q_inv = db.query(InvalidRadicado).filter(InvalidRadicado.radicado == radicado)
                if not is_global_superadmin(current_user):
                    q_inv = q_inv.filter(InvalidRadicado.company_id == current_user.company_id)
                q_inv.delete()

                count += 1
                if count % batch_size == 0:
                    db.commit()
            except Exception as row_error:
                print(f" Error eliminando fila: {row_error}")
                db.rollback()

        db.commit()

        return {
            "ok": True,
            "deleted_cases": deleted_cases,
            "message": f"Se eliminaron {deleted_cases} procesos correctamente."
        }
    except Exception as e:
        db.rollback()
        msg = str(e).split('\n')[0]
        raise HTTPException(500, f"Error en eliminacin masiva: {msg}")


# =========================
# REFRESH ALL (MANUAL)
# =========================
@app.post("/cases/refresh-all")
async def refresh_all_cases(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Dispara una tarea en segundo plano para recorrer todos los casos v?lidos."""
    if REFRESH_LOCK.locked():
        return {"ok": False, "message": "Ya existe una actualizaci?n masiva en curso. Por favor, espere a que termine."}
    
    background_tasks.add_task(do_auto_refresh_with_lock)
    return {"ok": True, "message": "Sincronizaci?n masiva iniciada en segundo plano."}

async def do_auto_refresh_with_lock():
    if REFRESH_LOCK.locked():
        return
    async with REFRESH_LOCK:
        await do_auto_refresh()


# =========================
# DOCUMENTOS DE ACTUACIN
# =========================
@app.get("/cases/events/{id_reg_actuacion}/documents")
async def get_event_documents(
    id_reg_actuacion: int,
    llave_proceso: str = Query(..., description="La llave (radicado) del proceso de 23 digitos"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    print(f"\n [DOCS] id_reg_actuacion={id_reg_actuacion} | llave_proceso={llave_proceso}")

    # 1. Cargar CaseEvent por id_reg_actuacion
    event = db.query(CaseEvent).filter(CaseEvent.id_reg_actuacion == id_reg_actuacion).first()
    if not event:
        raise HTTPException(status_code=403, detail="Acceso denegado. No se encontró la actuación.")

    # 2. Cargar Case asociado
    case_obj = db.query(Case).filter(Case.id == event.case_id).first()
    if not case_obj:
        raise HTTPException(status_code=403, detail="Acceso denegado. Caso asociado no encontrado.")

    # 3. Validar que el CaseEvent realmente pertenece a ese Case
    if event.case_id != case_obj.id:
        raise HTTPException(status_code=403, detail="Acceso denegado. La actuación no coincide con el caso.")

    # 4. Validar que el radicado o llave_proceso coincide con el caso esperado
    if clean_str(llave_proceso) != case_obj.radicado:
        raise HTTPException(status_code=403, detail="Acceso denegado. La llave de proceso no coincide.")

    # 5. Validar que el case.company_id coincide con el de current_user si no es SuperAdmin
    if not is_global_superadmin(current_user) and case_obj.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a los documentos de este caso.")

    # 1. Intentar obtener de la base de datos (caché) para velocidad instantánea
    if event.documentos_cache:
        print(f" [DOCS] Retornando desde cache para id_reg_actuacion={id_reg_actuacion}")
        try:
            cached_items = json.loads(event.documentos_cache)
            return {"items": cached_items, "total": len(cached_items)}
        except Exception as e:
            print(f" [DOCS] Error leyendo cache de BD: {e}")

    items = []

    # 2. Si no hay cache, hacer la consulta externa normal
    try:
        raw = await asyncio.wait_for(documentos_actuacion(id_reg_actuacion, llave_proceso), timeout=20.0)
        print(f" [DOCS] service/rama.documentos_actuacion()  tipo={type(raw).__name__} | valor={str(raw)[:300]}")
        items = extract_documentos_from_response(raw)
        print(f" [DOCS] items extrados del servicio: {len(items)}")
    except asyncio.TimeoutError:
        print(" [DOCS] Timeout de 20s en documentos_actuacion")
    except RamaError as e:
        print(f" [DOCS] RamaError en servicio: {e}")
    except Exception as e:
        print(f" [DOCS] Error en servicio: {e}")
        traceback.print_exc()

    if not items:
        print(f" [DOCS] Servicio retorn vaco o timeout. Intentando llamada directa a Rama Judicial...")
        try:
            items = await asyncio.wait_for(fetch_documentos_rama_directa(id_reg_actuacion, llave_proceso), timeout=20.0)
            print(f" [DOCS] items desde llamada directa: {len(items)}")
        except asyncio.TimeoutError:
            print(" [DOCS] Timeout de 20s en fetch_documentos_rama_directa")
        except Exception as e:
            print(f" [DOCS] Error en llamada directa: {e}")
            traceback.print_exc()
            
    if not items:
        raise HTTPException(504, "La Rama Judicial tardó demasiado en responder o no entregó documentos. Intenta de nuevo más tarde.")

    # 3. Guardar en la base de datos si obtuvimos resultados
    try:
        event.documentos_cache = json.dumps(items)
        db.commit()
        print(f" [DOCS] Guardado en cache exitosamente ({len(items)} items).")
    except Exception as e:
        db.rollback()
        print(f" [DOCS] Error guardando cache en BD: {e}")

    print(f" [DOCS] Resultado final  {len(items)} documentos")
    return {"items": items, "total": len(items)}


# =========================
# DESCARGA DE DOCUMENTO (PROXY A RAMA JUDICIAL O REDIRECCION SIC)
# =========================
@app.get("/api/documentos/{id_documento}/descargar")
@app.get("/documentos/{id_documento}/descargar")
async def descargar_documento_endpoint(
    id_documento: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Buscar el CaseEvent y Case asociados que contienen el id_documento en documentos_cache
    query = db.query(CaseEvent, Case).join(Case, CaseEvent.case_id == Case.id)
    if not is_global_superadmin(current_user):
        query = query.filter(Case.company_id == current_user.company_id)

    # Pre-filtrado por LIKE en la BD para evitar cargar toda la tabla, pero validando exactamente en Python
    candidates = query.filter(CaseEvent.documentos_cache.like(f"%{id_documento}%")).all()

    associated_case = None
    associated_event = None
    target_doc = None

    for event, case in candidates:
        if event.documentos_cache:
            try:
                docs = json.loads(event.documentos_cache)
                for doc in docs:
                    doc_id = doc.get("idDocumento") or doc.get("idRegistroDocumento") or doc.get("id") or doc.get("idRegDocumento")
                    if doc_id is not None:
                        try:
                            if int(doc_id) == id_documento:
                                associated_case = case
                                associated_event = event
                                target_doc = doc
                                break
                        except ValueError:
                            pass
                if associated_case:
                    break
            except Exception:
                pass

    if not associated_case or not associated_event:
        # Fallback por ID directo de actuación para casos de SIC u otras fuentes
        direct_match = query.filter(or_(CaseEvent.id == id_documento, CaseEvent.id_reg_actuacion == id_documento)).first()
        if direct_match:
            event, case = direct_match
            associated_case = case
            associated_event = event
            if event.documentos_cache:
                try:
                    docs = json.loads(event.documentos_cache)
                    if docs: target_doc = docs[0]
                except Exception:
                    pass
            if not target_doc:
                target_doc = {
                    "idRegDocumento": id_documento,
                    "nombre": f"SIC_{case.radicado}_{event.title}.pdf",
                    "tipoDocumento": event.title,
                    "fecha": event.event_date,
                    "origen": "Superintendencia de Industria y Comercio - SIC"
                }

    if not associated_case or not associated_event:
        raise HTTPException(status_code=403, detail="No se encontró una asociación válida para descargar este documento o no tienes acceso.")

    # Confirmar pertenencia de empresa adicionalmente
    if not is_global_superadmin(current_user):
        if associated_case.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="Acceso denegado. Propiedad de empresa no válida.")

    # 1. Si tiene URL de visordocumental de la SIC (Abrir el visor oficial interactivo en el navegador)
    doc_url = target_doc.get("url", "") if target_doc else ""
    if doc_url and "visordocumental.sic.gov.co" in doc_url:
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=doc_url)

    # 2. Si tiene URL directa a un archivo PDF externo
    if target_doc and target_doc.get("url") and target_doc["url"].lower().endswith(".pdf"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=target_doc["url"])

    # 3. Si es documento de la SIC y no tiene enlace al visor original, generar documento oficial
    doc_name = (target_doc.get("nombre") or target_doc.get("nombreDocumento") or "").upper() if target_doc else ""
    is_sic_doc = (
        "SIC" in doc_name or 
        (associated_case and associated_case.radicado and (associated_case.radicado.startswith("24-") or associated_case.radicado.startswith("25-") or associated_case.radicado.startswith("26-"))) or
        (target_doc and target_doc.get("origen") == "Superintendencia de Industria y Comercio - SIC") or
        (target_doc and "consultatramites.sic.gov.co" in target_doc.get("url", ""))
    )

    if is_sic_doc:
        import io
        from backend.service.sic_pdf import generate_sic_actuacion_pdf
        pdf_bytes = generate_sic_actuacion_pdf(
            radicado=associated_case.radicado,
            demandante=associated_case.demandante or "No especificado",
            demandado=associated_case.demandado or "No especificado",
            cedula=associated_case.cedula,
            actuacion=associated_event.title or (target_doc.get("tipoDocumento") if target_doc else "Actuación SIC"),
            fecha=associated_event.event_date or (target_doc.get("fecha") if target_doc else ""),
            detalle=associated_event.detail or "",
            estado=associated_case.estado or "Demanda en Trámite",
            despacho=associated_case.juzgado or associated_case.despacho or "Superintendencia de Industria y Comercio"
        )
        clean_filename = target_doc.get("nombre") or f"SIC_{associated_case.radicado}_{id_documento}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{clean_filename}"',
                "Cache-Control": "no-cache",
            }
        )

    url_rama = f"{RAMA_BASE}/Descarga/Documento/{id_documento}"
    print(f" Descargando documento ID={id_documento}  {url_rama}")

    try:
        client = httpx.AsyncClient(timeout=60.0, verify=False, headers=RAMA_HEADERS, follow_redirects=True)
        response = await client.send(
            client.build_request("GET", url_rama),
            stream=True
        )

        print(f" Status Rama Judicial: {response.status_code}")

        if response.status_code >= 400:
            await response.aclose()
            await client.aclose()
            raise HTTPException(
                status_code=response.status_code,
                detail=f"La Rama Judicial devolvi {response.status_code} para el documento {id_documento}."
            )

        content_type = response.headers.get("content-type", "application/pdf")
        if "octet-stream" in content_type:
            content_type = "application/pdf"

        async def stream_content():
            try:
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()

        return StreamingResponse(
            stream_content(),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="documento_rama_{id_documento}.pdf"',
                "Cache-Control": "no-cache",
            }
        )

    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(504, f"Timeout: La Rama Judicial tard demasiado (documento {id_documento}).")
    except httpx.ConnectError as e:
        raise HTTPException(502, f"No se pudo conectar a la Rama Judicial: {str(e)}")
    except Exception as e:
        print(f" Error inesperado descargando {id_documento}: {e}")
        traceback.print_exc()
        raise HTTPException(500, f"Error interno descargando documento: {str(e)}")

# =========================
# PUBLICACIONES PROCESALES
# =========================
@app.get("/cases/{radicado}/publicaciones")
async def get_case_publications(
    radicado: str, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q_case = db.query(Case).filter(Case.radicado == radicado)
    if current_user.company_id is not None:
        q_case = q_case.filter(Case.company_id == current_user.company_id)
    
    case = q_case.first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
        
    # Enforce company isolation for publications
    q_pubs = db.query(CasePublication).filter(CasePublication.case_id == case.id)
    if case.company_id is not None:
        q_pubs = q_pubs.filter(CasePublication.company_id == case.company_id)
        
    pubs = q_pubs.order_by(desc(CasePublication.fecha_publicacion)).all()
    
    # Auto-encolar búsquedas deshabilitado en consulta visual para que el frontend solo lea de la base de datos
    
    # Consultar estado de la cola (respetando company_id)
    from backend.models import CasePublicationSearch
    busquedas_db = db.query(CasePublicationSearch).filter(
        CasePublicationSearch.company_id == case.company_id,
        CasePublicationSearch.radicado == radicado
    ).all()
    
    validadas_db = [p for p in pubs if getattr(p, "estado_validacion", "requiere_revision") in ["validado", "validado_automatico", "validado_por_fuente_oficial"]]
    
    # Estado consolidado
    global_status = "completado"
    if any(b.estado in ["pendiente", "procesando"] for b in busquedas_db):
        global_status = "procesando"
    elif not validadas_db and any(b.estado == "error" for b in busquedas_db):
        global_status = "error"
    elif not validadas_db and any(b.estado == "sin_resultado" for b in busquedas_db):
        global_status = "sin_resultado"
        
    is_sa = is_global_superadmin(current_user)
    
    def serialize_pub(p):
        res = {
            "id": p.id,
            "fecha_publicacion": p.fecha_publicacion.isoformat() if p.fecha_publicacion else None,
            "tipo_publicacion": p.tipo_publicacion,
            "descripcion": p.descripcion,
            "documento_url": p.documento_url,
            "source_url": p.source_url,
            "source_id": p.source_id,
            "fecha_estado_electronico": p.fecha_estado_electronico.isoformat() if p.fecha_estado_electronico else None,
            "numero_estado": p.numero_estado,
            "url_fuente_principal": p.url_fuente_principal,
            "tipo_fuente_principal": p.tipo_fuente_principal,
            "documentos_complementarios": p.documentos_complementarios,
            "url_resumen_publicacion": p.url_resumen_publicacion,
            "url_cuadro": p.url_cuadro,
            "url_providencia": p.url_providencia,
            "observacion": p.observacion,
            "estado_validacion": getattr(p, "estado_validacion", "requiere_revision") or "requiere_revision",
            "documento_nombre": getattr(p, "documento_nombre", ""),
        }
        if is_sa:
            res.update({
                "match_fuerte": getattr(p, "match_fuerte", False),
                "match_type": getattr(p, "match_type", ""),
                "motivo_match": getattr(p, "motivo_match", ""),
                "match_score": getattr(p, "match_score", 0),
                "texto_bloque_match": getattr(p, "texto_bloque_match", ""),
                "motivo_descarte": getattr(p, "motivo_descarte", ""),
                "fuente_principal_validada": getattr(p, "fuente_principal_validada", False),
                "requiere_revision": getattr(p, "requiere_revision", True),
                "elementos_detectados": getattr(p, "elementos_detectados", ""),
                "extraction_quality": getattr(p, "extraction_quality", "")
            })
        return res

    serialized_pubs = [serialize_pub(p) for p in pubs]
    validadas = [p for p in serialized_pubs if p.get("estado_validacion") != "descartado"]
    req_revision = [p for p in serialized_pubs if p.get("estado_validacion") == "requiere_revision"]
    items_res = serialized_pubs if is_sa else validadas
    
    return {
        "radicado": radicado,
        "company_id": case.company_id,
        "publicaciones": validadas,
        "requiere_revision": req_revision,
        "items": items_res, # Para compatibilidad
        "busquedas": [
            {
                "mes_busqueda": b.mes_busqueda,
                "estado": b.estado,
                "fecha_ultima_busqueda": b.fecha_ultima_busqueda.isoformat() if b.fecha_ultima_busqueda else None,
                "error": b.ultimo_error or b.error,
                "intentos": getattr(b, "intentos", 0)
            }
            for b in busquedas_db
        ],
        "estado_busqueda": global_status,
        "sync_pub_status": global_status,
        "sync_pub_progress": 100 if global_status != "procesando" else 50
    }

@app.get("/api/cases/id/{case_id}/publicaciones")
@app.get("/cases/id/{case_id}/publicaciones")
async def get_case_publications_by_id(
    case_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q_case = db.query(Case).filter(Case.id == case_id)
    if current_user.company_id is not None:
        q_case = q_case.filter(Case.company_id == current_user.company_id)
        
    case = q_case.first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    
    return await get_case_publications(case.radicado, db, current_user)

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from backend.models import AuditLog, User

class DescartarRequest(BaseModel):
    motivo: str
    observacion: Optional[str] = None

class AprobarRequest(BaseModel):
    observacion: Optional[str] = None

@app.post("/api/publicaciones/{pub_id}/descartar")
@app.post("/publicaciones/{pub_id}/descartar")
async def descartar_publicacion(
    pub_id: int, 
    req: DescartarRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not is_global_superadmin(current_user):
        raise HTTPException(status_code=403, detail="Acción permitida únicamente para SuperAdmin global.")
        
    pub = db.query(CasePublication).filter(CasePublication.id == pub_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
        
    pub.estado_validacion = "descartado"
    pub.motivo_descarte = req.motivo
    pub.requiere_revision = False
    
    pub.descartado_manual = True
    pub.descartado_por_id = current_user.id
    pub.discarded_at = datetime.now()
    if req.observacion:
        pub.observacion_revision = req.observacion
    
    audit = AuditLog(
        user_id=current_user.id,
        accion="DISCARD_PUBLICATION",
        entidad="CasePublication",
        entidad_id=pub.id,
        metadata_json=f'{{"motivo": "{req.motivo}", "observacion": "{req.observacion or ""}"}}'
    )
    db.add(audit)
    db.commit()
    
    return {"ok": True, "message": "Publicación descartada correctamente", "id": pub_id}

@app.post("/api/publicaciones/{pub_id}/aprobar")
@app.post("/publicaciones/{pub_id}/aprobar")
async def aprobar_publicacion(
    pub_id: int, 
    req: AprobarRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not is_global_superadmin(current_user):
        raise HTTPException(status_code=403, detail="Acción permitida únicamente para SuperAdmin global.")
        
    pub = db.query(CasePublication).filter(CasePublication.id == pub_id).first()
    if not pub:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
        
    pub.estado_validacion = "validado"
    pub.requiere_revision = False
    
    pub.match_score = 100
    pub.match_type = "validacion_manual"
    pub.validado_manual = True
    pub.aprobado_por_id = current_user.id
    pub.approved_at = datetime.now()
    
    if req.observacion:
        pub.observacion_revision = req.observacion
        pub.motivo_match = (pub.motivo_match or "") + f" [Validación Manual: {req.observacion}]"
    else:
        pub.motivo_match = (pub.motivo_match or "") + " [Validación Manual]"
    
    audit = AuditLog(
        user_id=current_user.id,
        accion="APPROVE_PUBLICATION",
        entidad="CasePublication",
        entidad_id=pub.id,
        metadata_json=f'{{"observacion": "{req.observacion or ""}"}}'
    )
    db.add(audit)
    db.commit()
    
    return {"ok": True, "message": "Publicación validada manualmente", "id": pub_id}
@app.post("/api/cases/{radicado}/sync-publications")
@app.post("/cases/{radicado}/sync-publications")
async def sync_case_publications(radicado: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.radicado == radicado).first()
    if not case: return {"ok": False, "error": "Caso no encontrado"}
    
    # RESET INMEDIATO
    case.sync_pub_progress = 5
    case.sync_pub_status = "Iniciando búsqueda..."
    db.commit()
    
    background_tasks.add_task(run_sync_publications_task, case.radicado, True)
    return {"ok": True, "message": "Sincronización iniciada en segundo plano"}

@app.post("/api/cases/{radicado}/refresh-publicaciones")
@app.post("/cases/{radicado}/refresh-publicaciones")
async def refresh_publications_by_radicado(
    radicado: str,
    force: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q_case = db.query(Case).filter(Case.radicado == radicado)
    if current_user.company_id is not None:
        q_case = q_case.filter(Case.company_id == current_user.company_id)
        
    case = q_case.first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
        
    from backend.service.publicaciones import auto_queue_publicaciones_for_case
    queued = auto_queue_publicaciones_for_case(db, case, force=force)
    
    if queued > 0:
        return {"ok": True, "message": f"Sincronización manual/forzada encolada para {queued} mes(es)."}
    else:
        return {"ok": True, "message": "El caso no tiene actuaciones relevantes para buscar publicaciones."}

@app.post("/api/cases/id/{case_id}/refresh-publicaciones")
@app.post("/cases/id/{case_id}/refresh-publicaciones")
async def refresh_publications_by_id(
    case_id: int,
    force: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q_case = db.query(Case).filter(Case.id == case_id)
    if current_user.company_id is not None:
        q_case = q_case.filter(Case.company_id == current_user.company_id)
        
    case = q_case.first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
        
    from backend.service.publicaciones import auto_queue_publicaciones_for_case
    queued = auto_queue_publicaciones_for_case(db, case, force=force)
    
    if queued > 0:
        return {"ok": True, "message": f"Sincronización manual/forzada encolada para {queued} mes(es)."}
    else:
        return {"ok": True, "message": "El caso no tiene actuaciones relevantes para buscar publicaciones."}

@app.post("/api/cases/{radicado}/reset-sync")
@app.post("/cases/{radicado}/reset-sync")
async def reset_case_sync(radicado: str, db: Session = Depends(get_db)):
    """Resetea manualmente el estado de sincronización si se queda trabado."""
    case = db.query(Case).filter(Case.radicado == radicado).first()
    if not case: return {"ok": False, "error": "Caso no encontrado"}
    case.sync_pub_status = None
    case.sync_pub_progress = 0
    db.commit()
    return {"ok": True, "message": "Estado de sincronización reseteado."}

# Estado global del proceso de sincronización masiva (en memoria, suficiente para un proceso)
_bulk_sync_state = {
    "running": False,
    "total": 0,
    "reviewed": 0,
    "errors": 0,
}

@app.get("/api/bulk-sync/publications-status")
@app.get("/bulk-sync/publications-status")
async def get_sync_publications_status(db: Session = Depends(get_db)):
    """Devuelve el progreso actual de la sincronización masiva leyendo el último job en DB."""
    job = db.execute(text("""
        SELECT id, company_id, estado, total_casos, casos_procesados, con_error, porcentaje
        FROM publicaciones_sync_jobs
        ORDER BY id DESC
        LIMIT 1
    """)).mappings().first()
    
    if not job:
        return {"running": False, "total": 0, "reviewed": 0, "errors": 0, "percent": 0}
        
    running = job["estado"] in ["pendiente", "procesando"]
    return {
        "running": running,
        "total": job["total_casos"],
        "reviewed": job["casos_procesados"],
        "errors": job["con_error"],
        "percent": job["porcentaje"]
    }

@app.post("/api/cases/sync-all-publications")
@app.post("/cases/sync-all-publications")
async def sync_all_publications(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Inicia la sincronización masiva de publicaciones procesales para todos los casos válidos,
    utilizando el nuevo encolador masivo no bloqueante.
    """
    if is_global_superadmin(current_user):
        target_company_id = current_user.company_id
        if target_company_id is None:
            first_case = db.query(Case).first()
            target_company_id = first_case.company_id if first_case else 1
    else:
        if current_user.company_id is None:
            raise HTTPException(status_code=400, detail="El usuario no tiene una empresa asociada.")
        target_company_id = current_user.company_id

    # Validar si ya existe un job masivo activo
    active_job = db.execute(text("""
        SELECT id FROM publicaciones_sync_jobs
        WHERE company_id = :company_id AND estado IN ('pendiente', 'procesando')
        LIMIT 1
    """), {"company_id": target_company_id}).mappings().first()

    if active_job:
        job_info = db.execute(text("""
            SELECT total_casos, casos_procesados FROM publicaciones_sync_jobs WHERE id = :id
        """), {"id": active_job["id"]}).mappings().first()
        
        return {
            "ok": False,
            "message": f"Ya hay una sincronización en curso ({job_info['casos_procesados']}/{job_info['total_casos']} revisados).",
            "total": job_info["total_casos"],
            "reviewed": job_info["casos_procesados"]
        }

    # Casos válidos = activos de la empresa
    cases = db.query(Case).filter(Case.company_id == target_company_id, Case.is_active == True).all()
    total = len(cases)
    if total == 0:
        return {"ok": True, "message": "No hay casos válidos para sincronizar.", "total": 0}

    # Crear el job masivo
    result = db.execute(text("""
        INSERT INTO publicaciones_sync_jobs (company_id, estado, force, iniciado_por, total_casos, fecha_inicio, updated_at)
        VALUES (:company_id, 'pendiente', false, :iniciado_por, :total, :now, :now)
        RETURNING id
    """), {
        "company_id": target_company_id,
        "iniciado_por": current_user.username or str(current_user.id),
        "total": total,
        "now": datetime.now()
    })
    db.commit()
    job_id = result.scalar()

    async def run_mass_sync():
        db_session = SessionLocal()
        try:
            from backend.service.publicaciones import auto_queue_publicaciones_masivo
            await auto_queue_publicaciones_masivo(
                db=db_session,
                company_id=target_company_id,
                force=False,
                job_id=job_id
            )
        except Exception as e:
            print(f"[MASS_SYNC_BG_TASK] Error running legacy-triggered mass sync: {e}")
            try:
                db_session.execute(text("""
                    UPDATE publicaciones_sync_jobs
                    SET estado = 'error', ultimo_error = :err, updated_at = :now
                    WHERE id = :job_id
                """), {"err": str(e)[:500], "job_id": job_id, "now": datetime.now()})
                db_session.commit()
            except Exception as ex2:
                print(f"[MASS_SYNC_BG_TASK] Error updating job state to error: {ex2}")
        finally:
            db_session.close()

    background_tasks.add_task(run_mass_sync)
    return {
        "ok": True,
        "message": f"Sincronización masiva iniciada para {total} casos en segundo plano.",
        "total": total
    }

@app.get("/api/sync/logs/{case_id}")
async def get_sync_logs(case_id: int, db: Session = Depends(get_db)):
    """Permite ver los logs de diagnóstico desde el navegador."""
    logs = db.execute(text("SELECT message, created_at FROM sync_debug_logs WHERE case_id = :cid ORDER BY created_at DESC LIMIT 100"), 
                     {"cid": case_id}).fetchall()
    return [{"message": r[0], "at": r[1].isoformat()} for r in logs]

class BuscarMesBody(BaseModel):
    radicado: str
    mes: str # Formato YYYY-MM
    prioridad: int = 1
    
@app.post("/api/publicaciones/buscar-mes")
@app.post("/publicaciones/buscar-mes")
async def force_search_month(body: BuscarMesBody, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.radicado == body.radicado).first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
        
    from backend.models import CasePublicationSearch
    from backend.service.publicaciones import extract_despacho_code
    
    # Calcular fechas de rango del mes
    try:
        year, month = map(int, body.mes.split("-"))
        import calendar
        from datetime import date
        fecha_act = date(year, month, 1)
        fecha_ini = date(year, month, 1)
        fecha_fin = date(year, month, calendar.monthrange(year, month)[1])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Formato de mes inválido (debe ser YYYY-MM): {str(e)}")

    company_id = case.company_id
    if not company_id or not body.radicado or not body.mes or not fecha_ini or not fecha_fin:
        print(f"[PUBLICACIONES][QUEUE_INVALID_MONTH] company_id={company_id} radicado={body.radicado} mes_busqueda={body.mes} search_id=None")
        raise HTTPException(status_code=400, detail="Faltan datos obligatorios para registrar la búsqueda")

    despacho_codigo = extract_despacho_code(body.radicado)

    # Buscar si ya existe la búsqueda para ese mes
    busqueda = db.query(CasePublicationSearch).filter(
        CasePublicationSearch.company_id == company_id,
        CasePublicationSearch.radicado == body.radicado,
        CasePublicationSearch.mes_busqueda == body.mes
    ).first()
    
    if busqueda:
        busqueda.fecha_actuacion = fecha_act
        busqueda.fecha_inicio_busqueda = fecha_ini
        busqueda.fecha_fin_busqueda = fecha_fin
        busqueda.despacho_codigo = despacho_codigo
        busqueda.estado = "pendiente"
        busqueda.estado_busqueda = "pendiente"
        busqueda.intentos = 0
        busqueda.error = None
        busqueda.ultimo_error = None
        busqueda.prioridad = body.prioridad
        busqueda.locked_at = None
        busqueda.locked_by = None
        busqueda.next_retry_at = None
        busqueda.processed_at = None
        busqueda.source_trigger = "manual_override"
        busqueda.force = True
    else:
        busqueda = CasePublicationSearch(
            company_id=company_id,
            radicado=body.radicado,
            fecha_actuacion=fecha_act,
            fecha_inicio_busqueda=fecha_ini,
            fecha_fin_busqueda=fecha_fin,
            despacho_codigo=despacho_codigo,
            estado="pendiente",
            estado_busqueda="pendiente",
            mes_busqueda=body.mes,
            intentos=0,
            prioridad=body.prioridad,
            source_trigger="manual_override",
            force=True
        )
        db.add(busqueda)
        
    db.commit()
    db.refresh(busqueda)
    print(f"[PUBLICACIONES][QUEUE_CREATED] company_id={company_id} radicado={body.radicado} mes_busqueda={body.mes} search_id={busqueda.id}")
    
    return {"ok": True, "message": f"Búsqueda del mes {body.mes} encolada exitosamente para el radicado {body.radicado}.", "estado": "pendiente"}


class MassSyncBody(BaseModel):
    company_id: Optional[int] = None
    force: Optional[bool] = False
    limit: Optional[int] = None


@app.post("/api/publicaciones/sincronizacion-masiva")
@app.post("/publicaciones/sincronizacion-masiva")
async def start_mass_sync_publications(
    body: MassSyncBody,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if is_global_superadmin(current_user):
        if not body.company_id:
            raise HTTPException(status_code=400, detail="Debe especificar un company_id seleccionado.")
        target_company_id = body.company_id
    else:
        if current_user.company_id is None:
            raise HTTPException(status_code=400, detail="El usuario no tiene una empresa asociada.")
        target_company_id = current_user.company_id

    active_job = db.execute(text("""
        SELECT id FROM publicaciones_sync_jobs
        WHERE company_id = :company_id AND estado IN ('pendiente', 'procesando')
        LIMIT 1
    """), {"company_id": target_company_id}).mappings().first()

    if active_job:
        raise HTTPException(status_code=400, detail="Ya existe una sincronización masiva en proceso para esta empresa.")

    result = db.execute(text("""
        INSERT INTO publicaciones_sync_jobs (company_id, estado, force, iniciado_por, total_casos, fecha_inicio, updated_at)
        VALUES (:company_id, 'pendiente', :force, :iniciado_por, 0, :now, :now)
        RETURNING id
    """), {
        "company_id": target_company_id,
        "force": body.force,
        "iniciado_por": current_user.username or str(current_user.id),
        "now": datetime.now()
    })
    db.commit()
    job_id = result.scalar()

    async def run_mass_sync():
        db_session = SessionLocal()
        try:
            from backend.service.publicaciones import auto_queue_publicaciones_masivo
            await auto_queue_publicaciones_masivo(
                db=db_session,
                company_id=target_company_id,
                force=body.force,
                limit=body.limit,
                job_id=job_id
            )
        except Exception as e:
            print(f"[MASS_SYNC_BG_TASK] Error running mass sync for job {job_id}: {e}")
            try:
                db_session.execute(text("""
                    UPDATE publicaciones_sync_jobs
                    SET estado = 'error', ultimo_error = :err, updated_at = :now
                    WHERE id = :job_id
                """), {"err": str(e)[:500], "job_id": job_id, "now": datetime.now()})
                db_session.commit()
            except Exception as ex2:
                print(f"[MASS_SYNC_BG_TASK] Error updating job state to error: {ex2}")
        finally:
            db_session.close()

    background_tasks.add_task(run_mass_sync)
    return {"ok": True, "job_id": job_id, "message": "Sincronización masiva iniciada."}


@app.get("/api/publicaciones/sincronizacion-masiva/active")
@app.get("/publicaciones/sincronizacion-masiva/active")
async def get_active_mass_sync_job(
    company_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if is_global_superadmin(current_user):
        if not company_id:
            raise HTTPException(status_code=400, detail="Debe especificar un company_id seleccionado.")
        target_company_id = company_id
    else:
        if current_user.company_id is None:
            raise HTTPException(status_code=400, detail="El usuario no tiene una empresa asociada.")
        target_company_id = current_user.company_id

    job = db.execute(text("""
        SELECT id, company_id, estado, total_casos, casos_procesados, busquedas_creadas, busquedas_omitidas,
               con_actuaciones_relevantes, sin_actuaciones_relevantes, con_error, porcentaje, radicado_actual,
               force, iniciado_por, fecha_inicio, fecha_fin, ultimo_error, created_at, updated_at
        FROM publicaciones_sync_jobs
        WHERE company_id = :company_id AND estado IN ('pendiente', 'procesando')
        ORDER BY id DESC
        LIMIT 1
    """), {"company_id": target_company_id}).mappings().first()

    if not job:
        return {"job": None}

    job_dict = dict(job)
    serialized_job = {
        k: (v.isoformat() if isinstance(v, (datetime, date)) else v)
        for k, v in job_dict.items()
    }
    return {"job": serialized_job}


@app.get("/api/publicaciones/sincronizacion-masiva/{job_id}")
@app.get("/publicaciones/sincronizacion-masiva/{job_id}")
async def get_mass_sync_job_status(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.execute(text("""
        SELECT id, company_id, estado, total_casos, casos_procesados, busquedas_creadas, busquedas_omitidas,
               con_actuaciones_relevantes, sin_actuaciones_relevantes, con_error, porcentaje, radicado_actual,
               force, iniciado_por, fecha_inicio, fecha_fin, ultimo_error, created_at, updated_at
        FROM publicaciones_sync_jobs
        WHERE id = :job_id
    """), {"job_id": job_id}).mappings().first()

    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado.")

    if not is_global_superadmin(current_user):
        if job["company_id"] != current_user.company_id:
            raise HTTPException(status_code=403, detail="No tiene permisos para ver esta sincronización.")

    job_dict = dict(job)
    serialized_job = {
        k: (v.isoformat() if isinstance(v, (datetime, date)) else v)
        for k, v in job_dict.items()
    }
    return serialized_job


class PublicacionesDebugBody(BaseModel):
    radicado: str
    force: Optional[bool] = False

@app.post("/publicaciones/buscar/{radicado}")
async def force_sync_publications_by_radicado(radicado: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.radicado == radicado).first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    
    case.sync_pub_progress = 5
    case.sync_pub_status = "Iniciando búsqueda forzada..."
    db.commit()
    
    async def run_force_sync():
        async with sync_pub_semaphore:
            db_session = SessionLocal()
            try:
                c = db_session.query(Case).filter(Case.id == case.id).first()
                if c:
                    await save_new_publications(c, db_session, force=True)
            except Exception as e:
                print(f"[force_sync] Error: {e}")
            finally:
                db_session.close()

    background_tasks.add_task(run_force_sync)
    return {"ok": True, "message": "Búsqueda forzada iniciada en segundo plano."}

@app.post("/api/publicaciones/debug")
@app.post("/publicaciones/debug")
async def debug_publications_search(body: PublicacionesDebugBody, db: Session = Depends(get_db)):
    case = db.query(Case).filter(Case.radicado == body.radicado).first()
    if not case:
        raise HTTPException(status_code=404, detail="Caso no encontrado en la base de datos.")

    from backend.service.publicaciones import (
        is_relevant_actuacion, get_search_months_for_actuacion,
        build_portal_search_url, parse_fecha_pub,
        parse_result_cards, filter_cards_by_despacho, filter_cards_by_category,
        detect_main_sources, extract_text_content, validate_strong_match,
        revisar_documentos_complementarios, guardar_publicacion_validada,
        parse_spanish_date, extract_metadata_field, HEADERS
    )
    import calendar
    import hashlib
    from datetime import date, datetime
    import httpx
    from bs4 import BeautifulSoup
    import re

    # 1. Obtener actuaciones del caso
    eventos = db.query(CaseEvent).filter(CaseEvent.case_id == case.id).order_by(CaseEvent.event_date.asc()).all()
    
    actuaciones_relevantes = []
    seen_dates = set()
    for ev in eventos:
        act_text = getattr(ev, "title", "") or getattr(ev, "actuacion", "") or ""
        if is_relevant_actuacion(act_text):
            raw_date = getattr(ev, "event_date", "") or getattr(ev, "fecha_actuacion", "")
            if raw_date:
                if isinstance(raw_date, (date, datetime)):
                    dt = raw_date
                else:
                    try:
                        dt = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d")
                    except:
                        continue
                if isinstance(dt, datetime):
                    dt = dt.date()
                
                if dt not in seen_dates:
                    seen_dates.add(dt)
                    actuaciones_relevantes.append({
                        "fecha": dt.strftime("%Y-%m-%d"),
                        "descripcion": act_text
                    })

    # 2. Calcular meses a buscar
    meses_a_buscar_tuples = set()
    for dt in seen_dates:
        for mes in get_search_months_for_actuacion(dt):
            meses_a_buscar_tuples.add(mes)
            
    meses_a_buscar = [f"{y}-{m:02d}" for y, m in sorted(meses_a_buscar_tuples)]

    resultados_por_mes = {}
    
    # 3. Buscar para cada mes si force es True, o si no se ha buscado
    async with httpx.AsyncClient(headers=HEADERS, timeout=60, follow_redirects=True, verify=False) as client:
        for year, month in sorted(meses_a_buscar_tuples):
            month_str = f"{year}-{month:02d}"
            fecha_inicio_str = f"{year}-{month:02d}-01"
            last_day = calendar.monthrange(year, month)[1]
            fecha_fin_str = f"{year}-{month:02d}-{last_day:02d}"
            
            search_url = build_portal_search_url(case.radicado[:12], fecha_inicio_str, fecha_fin_str)
            
            month_res = {
                "buscado": True,
                "url": search_url,
                "cards_count": 0,
                "detalles_abiertos": 0,
                "fuentes_revisadas": 0,
                "matches": [],
                "guardadas": [],
                "motivo_no_resultado": ""
            }
            
            try:
                resp = await client.get(search_url)
                if resp.status_code != 200:
                    month_res["motivo_no_resultado"] = f"Error portal HTTP {resp.status_code}"
                    resultados_por_mes[month_str] = month_res
                    continue
                    
                raw_cards = parse_result_cards(resp.text)
                month_res["cards_count"] = len(raw_cards)
                
                filtered_by_despacho = filter_cards_by_despacho(raw_cards, case.radicado[:12])
                candidates = filter_cards_by_category(filtered_by_despacho)
                
                if not candidates:
                    month_res["motivo_no_resultado"] = "No se encontraron candidatos despues de filtrar por despacho y categoria."
                    resultados_por_mes[month_str] = month_res
                    continue
                    
                for cand in candidates:
                    month_res["detalles_abiertos"] += 1
                    detail_resp = await client.get(cand["detail_url"])
                    if detail_resp.status_code != 200:
                        continue
                        
                    detail_soup = BeautifulSoup(detail_resp.text, "html.parser")
                    estado_no = extract_metadata_field(detail_soup, "Estado No.")
                    if not estado_no:
                        title_match = re.search(r'Estado No\.?\s*(\d+)', cand["title"], re.IGNORECASE)
                        if title_match:
                            estado_no = title_match.group(1)
                            
                    fecha_estado_electronico_str = extract_metadata_field(detail_soup, "Fecha de Estado Electrónico")
                    fecha_estado_electronico = None
                    if fecha_estado_electronico_str:
                        fecha_estado_electronico = parse_spanish_date(fecha_estado_electronico_str)
                    if not fecha_estado_electronico:
                        fecha_estado_electronico = parse_fecha_pub(cand["fecha_publicacion"])
                        
                    fuentes = detect_main_sources(detail_resp.text)
                    
                    matched_any = False
                    for source in fuentes:
                        month_res["fuentes_revisadas"] += 1
                        doc_text = await extract_text_content(source["url"], client)
                        match = validate_strong_match(doc_text, case.radicado, case.demandante or "", case.demandado or "")
                        
                        if match.is_valid:
                            matched_any = True
                            month_res["matches"].append({
                                "title": cand["title"],
                                "match_type": match.match_type,
                                "reasons": match.reasons
                            })
                            
                            # Guardar la publicación validada
                            p_data = {
                                "radicado": case.radicado,
                                "case_id": case.id,
                                "fecha_publicacion": cand["fecha_publicacion"],
                                "tipo": cand["categoria"],
                                "descripcion": cand["title"],
                                "documento_url": source["url"],
                                "source_url": cand["detail_url"],
                                "source_id": hashlib.md5(cand["detail_url"].encode()).hexdigest(),
                                "url_fuente_principal": source["url"],
                                "tipo_fuente_principal": source["tipo"],
                                "texto_fuente_principal": doc_text,
                                "validada_por_fuente_principal": True,
                                "numero_estado": estado_no or "",
                                "fecha_estado_electronico": fecha_estado_electronico.strftime("%Y-%m-%d") if fecha_estado_electronico else cand["fecha_publicacion"],
                                "match_fuerte": True,
                                "match_type": match.match_type,
                                "motivo_match": match.reasons,
                                "observacion": f"Debug sync. Validada por {source['tipo']}."
                            }
                            saved = guardar_publicacion_validada(db, p_data)
                            if saved:
                                month_res["guardadas"].append({
                                    "title": cand["title"],
                                    "fecha": cand["fecha_publicacion"]
                                })
                            break
                            
                if not month_res["matches"]:
                    month_res["motivo_no_resultado"] = "No se encontro ninguna coincidencia fuerte en los documentos de los candidatos."
                    
            except Exception as ex:
                month_res["motivo_no_resultado"] = f"Excepcion en busqueda: {str(ex)}"
                
            resultados_por_mes[month_str] = month_res

    return {
        "radicado": case.radicado,
        "actuaciones_relevantes": actuaciones_relevantes,
        "meses_a_buscar": meses_a_buscar,
        "resultados_por_mes": resultados_por_mes
    }

# Semáforo global para evitar saturación y bloqueos de DB (Máximo 2 sincronizaciones pesadas a la vez)
sync_pub_semaphore = asyncio.Semaphore(2)

async def run_sync_publications_task(radicado: str, force: bool = False):
    """Wrapper para encolar la sincronización en background."""
    db = SessionLocal()
    try:
        from backend.service.publicaciones import auto_queue_publicaciones
        auto_queue_publicaciones(db, radicado, force=force, source_trigger="manual_sync")
    except Exception as e:
        print(f"[sync_task] Error: {e}")
    finally:
        db.close()

async def save_new_publications_task(case_id: int):
    """Wrapper task to enqueue sync logic in the background."""
    db = SessionLocal()
    try:
        case = db.query(Case).filter(Case.id == case_id).first()
        if case:
            from backend.service.publicaciones import auto_queue_publicaciones
            auto_queue_publicaciones(db, case.radicado, force=False, source_trigger="auto_sync_case")
    except Exception as e:
        print(f"[save_new_publications_task] Error: {e}")
    finally:
        db.close()

def update_sync_progress(db: Session, case_id: int, progress: int, status: str = None):
    """Actualiza el progreso y guarda un log en la DB para diagnóstico."""
    try:
        # 1. Actualizar caso
        params = {"prog": progress, "cid": case_id}
        sql = "UPDATE cases SET sync_pub_progress = :prog"
        if status is not None:
            sql += ", sync_pub_status = :stat"
            params["stat"] = status
        sql += " WHERE id = :cid"
        db.execute(text(sql), params)
        
        # 2. Guardar log de debug
        log_msg = f"Progreso: {progress}% | Status: {status or 'N/A'}"
        db.execute(text("INSERT INTO sync_debug_logs (case_id, message) VALUES (:cid, :msg)"), 
                   {"cid": case_id, "msg": log_msg})
        
        db.commit()
    except Exception as e:
        print(f"[progress-error] {e}")
        db.rollback()

async def save_new_publications(case: Case, db: Session, force: bool = False):
    try:
        from backend.service.publicaciones import (
            is_relevant_actuacion, get_search_months_for_actuacion,
            consultar_publicaciones_rango, parse_fecha_pub,
            guardar_estado_busqueda, guardar_publicacion_validada
        )
        from backend.models import CaseEvent, CasePublication, CasePublicationSearch
        import asyncio
        import calendar
        from datetime import datetime, timedelta, date

        # 0. Iniciar progreso
        with open("sync_emergency.log", "a") as f:
            f.write(f"[{datetime.now()}] Iniciando tarea para {case.radicado} (ID: {case.id}) | Force: {force}\n")
                
        update_sync_progress(db, case.id, 5, "Iniciando búsqueda...")
        
        with open("sync_debug.log", "a") as f_log:
            f_log.write(f"\n[{datetime.now()}] SYNC START: {case.radicado} | Force: {force}")

        update_sync_progress(db, case.id, 10, "Analizando historial de actuaciones...")
        
        # 1. Obtener actuaciones del caso
        eventos = db.query(CaseEvent).filter(CaseEvent.case_id == case.id).order_by(CaseEvent.event_date.desc()).all()
        
        # Filtrar y agrupar actuaciones relevantes por fecha exacta
        actuaciones_relevantes = []
        seen_dates = set()
        for ev in eventos:
            act_text = getattr(ev, "title", "") or getattr(ev, "actuacion", "") or ""
            if is_relevant_actuacion(act_text):
                raw_date = getattr(ev, "event_date", "") or getattr(ev, "fecha_actuacion", "")
                if raw_date:
                    if isinstance(raw_date, (date, datetime)):
                        dt = raw_date
                    else:
                        try:
                            dt = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d")
                        except:
                            continue
                    
                    if isinstance(dt, datetime):
                        dt = dt.date()
                    if dt not in seen_dates:
                        seen_dates.add(dt)
                        actuaciones_relevantes.append(dt)

        if not actuaciones_relevantes:
            if not force:
                # Marcar no requiere búsqueda
                guardar_estado_busqueda(db, {
                    "company_id": case.company_id,
                    "radicado": case.radicado,
                    "fecha_actuacion": date.today(),
                    "fecha_inicio_busqueda": date.today(),
                    "fecha_fin_busqueda": date.today(),
                    "mes_busqueda": date.today().strftime("%Y-%m"),
                    "estado_busqueda": "no_requiere_busqueda",
                    "debug": "No se encontraron actuaciones relevantes para este radicado."
                })
                update_sync_progress(db, case.id, 100, "No se detectaron actuaciones relevantes.")
                return
            else:
                # Búsqueda manual forzada: buscar en el mes actual y el anterior (por si apenas lo publicaron)
                print(f"[sync] Busqueda forzada sin actuaciones relevantes para {case.radicado}. Usando mes actual y anterior.")
                hoy = date.today()
                actuaciones_relevantes = [hoy]
                
                # Agregar el mes pasado para mayor cobertura en búsquedas forzadas
                primer_dia = hoy.replace(day=1)
                mes_pasado = primer_dia - timedelta(days=1)
                actuaciones_relevantes.append(mes_pasado)
                seen_dates = {hoy, mes_pasado}

        # Calcular todos los meses a buscar (evitando duplicados)
        meses_a_buscar = set()
        for dt in actuaciones_relevantes:
            for mes in get_search_months_for_actuacion(dt):
                meses_a_buscar.add(mes)

        found_pubs = []
        total_months = len(meses_a_buscar)
        saved_count = 0
        seen_ids = set()
        
        for i, (year, month) in enumerate(sorted(meses_a_buscar)):
            prog = 10 + int((i / total_months) * 85)
            month_name = MONTHS_ES[month-1] if 1 <= month <= 12 else str(month)
            update_sync_progress(db, case.id, prog, f"Buscando para {month_name} de {year}...")
            
            fecha_inicio = date(year, month, 1)
            fecha_fin = date(year, month, calendar.monthrange(year, month)[1])
            
            # Buscar si ya existe publicación válida para este mes (si no es forzado)
            if not force:
                ya_existe_valida = db.query(CasePublication).filter(
                    CasePublication.case_id == case.id,
                    CasePublication.match_fuerte == True,
                    (
                        ((CasePublication.fecha_publicacion >= fecha_inicio) & (CasePublication.fecha_publicacion <= fecha_fin)) |
                        ((CasePublication.fecha_estado_electronico >= fecha_inicio) & (CasePublication.fecha_estado_electronico <= fecha_fin))
                    )
                ).count() > 0
                if ya_existe_valida:
                    print(f"[sync] Saltando busqueda para {case.radicado} en {year}-{month:02d} (ya existe publicacion valida)")
                    continue

                # Comprobar log de búsquedas recientes (<24 horas)
                search_record = db.query(CasePublicationSearch).filter(
                    CasePublicationSearch.radicado == case.radicado,
                    CasePublicationSearch.fecha_inicio_busqueda == fecha_inicio
                ).first()
                
                should_search = True
                if search_record:
                    if search_record.estado_busqueda == "buscando":
                        print(f"[sync] Saltando busqueda para {case.radicado} en {year}-{month:02d} (ya hay una busqueda activa)")
                        should_search = False
                    elif search_record.estado_busqueda in ["sin_resultado", "error", "no_requiere_busqueda"] and search_record.fecha_ultima_busqueda:
                        if datetime.now() - search_record.fecha_ultima_busqueda < timedelta(hours=24):
                            print(f"[sync] Saltando busqueda reciente (<24h) para {case.radicado} en {year}-{month:02d} (estado: {search_record.estado_busqueda})")
                            should_search = False
                
                if not should_search:
                    continue

            # Determinar fecha de actuación desencadenante para este mes
            fecha_actuacion_del_mes = None
            for dt in sorted(seen_dates):
                if dt.year == year and dt.month == month:
                    fecha_actuacion_del_mes = dt
                    break
            if not fecha_actuacion_del_mes:
                # Comprobar si fue desencadenada por el mes anterior (fin de mes)
                if month == 1:
                    prev_year, prev_month = year - 1, 12
                else:
                    prev_year, prev_month = year, month - 1
                for dt in sorted(seen_dates):
                    if dt.year == prev_year and dt.month == prev_month and dt.day >= 25:
                        fecha_actuacion_del_mes = dt
                        break
            if not fecha_actuacion_del_mes:
                fecha_actuacion_del_mes = list(seen_dates)[0]
                
            # Registrar inicio de búsqueda en DB
            search_record = guardar_estado_busqueda(db, {
                "company_id": case.company_id,
                "radicado": case.radicado,
                "fecha_actuacion": fecha_actuacion_del_mes,
                "fecha_inicio_busqueda": fecha_inicio,
                "fecha_fin_busqueda": fecha_fin,
                "mes_busqueda": f"{year}-{month:02d}",
                "despacho_codigo": case.radicado[:12],
                "estado_busqueda": "buscando",
                "intento_manual": force
            })
            db.commit()
            search_id = search_record.id if search_record else None
            
            try:
                # Ejecutar búsqueda para el mes
                results = await consultar_publicaciones_rango(
                    radicado_completo=case.radicado,
                    fecha_act_str=fecha_actuacion_del_mes.strftime("%Y-%m-%d"),
                    demandante=case.demandante or "",
                    demandado=case.demandado or "",
                    year=year,
                    month=month,
                    company_id=case.company_id,
                    search_id=search_id
                )
                
                has_visible = False
                if results:
                    for p in results:
                        p["case_id"] = case.id
                        p["radicado"] = case.radicado
                        p["company_id"] = case.company_id
                        if "fecha_publicacion" not in p and "fecha" in p:
                            p["fecha_publicacion"] = p["fecha"]
                        
                        saved_pub = guardar_publicacion_validada(db, p, search_id=search_id)
                        if saved_pub:
                            if saved_pub.id not in seen_ids:
                                seen_ids.add(saved_pub.id)
                                saved_count += 1
                            if saved_pub.estado_validacion in ["validado", "validado_automatico", "validado_por_fuente_oficial"]:
                                has_visible = True
                                
                estado_fin = "encontrada" if has_visible else "sin_resultado"
                
                if has_visible:
                    print(f"[PUBLICACIONES][SEARCH_MARKED_FOUND] company_id={case.company_id} radicado={case.radicado} mes_busqueda={year}-{month:02d} search_id={search_id} url=N/A estado_validacion=encontrada motivo=has_visible")
                else:
                    print(f"[PUBLICACIONES][SEARCH_MARKED_NO_RESULT] company_id={case.company_id} radicado={case.radicado} mes_busqueda={year}-{month:02d} search_id={search_id} url=N/A estado_validacion=sin_resultado motivo=no_visible_pubs")

                guardar_estado_busqueda(db, {
                    "company_id": case.company_id,
                    "radicado": case.radicado,
                    "fecha_actuacion": fecha_actuacion_del_mes,
                    "fecha_inicio_busqueda": fecha_inicio,
                    "fecha_fin_busqueda": fecha_fin,
                    "mes_busqueda": f"{year}-{month:02d}",
                    "despacho_codigo": case.radicado[:12],
                    "estado_busqueda": estado_fin,
                    "intento_manual": force
                })
                db.commit()
            except Exception as e:
                import traceback
                tb_str = traceback.format_exc().replace('\n', ' || ')
                print(f"[PUBLICACIONES][ERROR] company_id={case.company_id} radicado={case.radicado} mes_busqueda={year}-{month:02d} search_id={search_id} url=N/A status_code=N/A error={str(e)} traceback={traceback.format_exc()} ultimo_error={str(e)} function=save_new_publications")
                
                guardar_estado_busqueda(db, {
                    "radicado": case.radicado,
                    "fecha_actuacion": fecha_actuacion_del_mes,
                    "fecha_inicio_busqueda": fecha_inicio,
                    "fecha_fin_busqueda": fecha_fin,
                    "despacho_codigo": case.radicado[:12],
                    "estado_busqueda": "error",
                    "error": str(e),
                    "intento_manual": force
                })
                db.commit()

        # 3. Guardar resultados (ya guardados)
        update_sync_progress(db, case.id, 96, "Guardando publicaciones encontradas...")
        update_sync_progress(db, case.id, 100, f"Completado: {saved_count} publicaciones procesadas.")
        
        await asyncio.sleep(5)
        update_sync_progress(db, case.id, 0, "")

    except Exception as e:
        import traceback
        print(f"[save_new_pubs] Error general: {e}")
        traceback.print_exc()
        update_sync_progress(db, case.id, 0, f"Error: {str(e)[:40]}")
        try:
            case.sync_pub_status = f"Error: {str(e)[:50]}"
            case.sync_pub_progress = 0
            db.commit()
        except: pass

@app.post("/admin/backfill-publicaciones")
async def backfill_publicaciones(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Escanea todos los casos existentes y busca publicaciones para actuaciones relevantes (en segundo plano)."""
    background_tasks.add_task(run_backfill_publicaciones_task)
    return {"status": "ok", "message": "Puesta al da masiva de publicaciones iniciada en segundo plano."}

async def run_backfill_publicaciones_task():
    """Ejecuta el backfill de publicaciones de forma segura en segundo plano."""
    db = SessionLocal()
    try:
        cases = db.query(Case).all()
        count = 0
        print(f"[backfill] Iniciando puesta al da masiva para {len(cases)} casos...")
        for case in cases:
            # save_new_publications ya maneja el filtro estricto de keywords
            await save_new_publications(case, db)
            count += 1
            if count % 10 == 0:
                print(f"[backfill] Procesados {count}/{len(cases)} casos...")
                db.commit()
        db.commit()
        print(f"[backfill] Finalizado. Procesados {count} casos.")
    except Exception as e:
        print(f"[backfill] Error en proceso masivo: {e}")
    finally:
        db.close()

# =========================
# BSQUEDA MASIVA (NAMES / RADICADOS)
# =========================

@app.post("/search/names/upload")
async def upload_names_search(
    background_tasks: BackgroundTasks,
    from_date: str | None = None,
    to_date: str | None = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Crear el Job
    job = SearchJob(job_type="name", status="pending", company_id=current_user.company_id)
    db.add(job)
    db.commit()
    db.refresh(job)

    # 2. Leer contenido y lanzar tarea en segundo plano
    content = await file.read()
    
    date_range = {"from": from_date, "to": to_date}
    
    # Pasamos una factora de sesin para que el hilo de fondo tenga su propia DB connection
    background_tasks.add_task(run_name_search_job, job.id, content, lambda: SessionLocal(), date_range)

    return {"job_id": job.id, "status": "pending"}

@app.post("/search/radicados/upload")
async def upload_radicados_search(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 1. Crear el Job
    job = SearchJob(job_type="radicado", status="pending", company_id=current_user.company_id)
    db.add(job)
    db.commit()
    db.refresh(job)

    # 2. Leer contenido y lanzar tarea en segundo plano
    content = await file.read()
    
    from backend.service.bulk_orchestrator import run_radicado_search_job
    background_tasks.add_task(run_radicado_search_job, job.id, content, lambda: SessionLocal())

    return {"job_id": job.id, "status": "pending"}

@app.get("/search/latest")
async def get_latest_search_job(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    job = db.query(SearchJob).filter(SearchJob.company_id == current_user.company_id).order_by(SearchJob.id.desc()).first()
    if not job:
        return None
    
    results = []
    if job.results_json:
        results = json.loads(job.results_json)

    return {
        "id": job.id,
        "status": job.status,
        "total_items": job.total_items,
        "processed_items": job.processed_items,
        "results": results,
        "is_imported": job.is_imported,
        "error": job.error_message
    }

@app.post("/search/jobs/{job_id}/cancel")
async def cancel_search_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(SearchJob).filter(SearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    if job.status in ["processing", "pending"]:
        job.status = "canceled"
        db.commit()
    return {"ok": True, "status": job.status}

@app.get("/search/jobs/{job_id}")
async def get_search_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(SearchJob).filter(SearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    
    results = []
    if job.results_json:
        results = json.loads(job.results_json)

    return {
        "id": job.id,
        "type": job.job_type,
        "status": job.status,
        "total_items": job.total_items,
        "processed_items": job.processed_items,
        "results": results,
        "error": job.error_message,
        "created_at": job.created_at.isoformat() if job.created_at else None
    }

@app.post("/search/jobs/{job_id}/import")
async def import_search_results(
    job_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    try:
        body = await request.json()
        selected_indices = body.get("indices", [])
        
        job = db.query(SearchJob).filter(SearchJob.id == job_id).first()
        if not job or not job.results_json:
            raise HTTPException(status_code=404, detail="Resultados no encontrados")
        
        all_results = json.loads(job.results_json)
        # Filtrar los seleccionados por el usuario
        selected_data = [res for res in all_results if res.get("index") in selected_indices]
        
        imported_count = 0
        for item in selected_data:
            sel = item.get("selected")
            if not sel: continue
            
            # Verificar si ya existe por idProceso (prioridad) o radicado
            id_proceso = str(sel.get("idProceso")) if sel.get("idProceso") else None
            radicado = str(sel.get("llaveProceso") or sel.get("numero", ""))
            
            case = None
            if id_proceso:
                case = db.query(Case).filter(Case.id_proceso == id_proceso).first()
            if not case:
                case = db.query(Case).filter(Case.radicado == radicado).first()
            
            if not case:
                case = Case(radicado=radicado, id_proceso=id_proceso)
                db.add(case)
            
            # Actualizar datos bsicos
            # Parsear sujetos para obtener demandante/demandado si estn vacos
            sujetos_str = sel.get("sujetosProcesales") or ""
            d1, d2, _ = parse_sujetos_procesales(sujetos_str)
            
            case.demandante = d1 or sel.get("demandante") or case.demandante
            case.demandado = d2 or sel.get("demandado") or case.demandado
            case.juzgado = sel.get("despacho") or case.juzgado
            
            # Cdula y Abogado del Excel de bsqueda
            case.cedula = item.get("cedula") or case.cedula
            case.abogado = item.get("abogado") or case.abogado
            
            # Fechas
            if sel.get("fechaRadicacion"):
                try:
                    case.fecha_radicacion = parse_fecha_pub(sel["fechaRadicacion"])
                except: pass
            if sel.get("fechaUltimaActuacion"):
                try:
                    case.ultima_actuacion = parse_fecha_pub(sel["fechaUltimaActuacion"])
                except: pass
                
            imported_count += 1
        
        job.is_imported = True
        db.commit()
        return {"ok": True, "imported": imported_count}
    except Exception as e:
        db.rollback()
        log_job(f" Error en import_search_results: {str(e)}")
        log_job(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error al importar: {str(e)}")

@app.get("/search/jobs/{job_id}/export")
async def export_search_results(
    job_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(SearchJob).filter(SearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Trabajo de búsqueda no encontrado")

    if not is_global_superadmin(current_user):
        if job.company_id is None or job.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="No tienes acceso a los resultados de este trabajo de búsqueda.")

    if not job.results_json:
        raise HTTPException(status_code=404, detail="Resultados no encontrados")
    
    results = json.loads(job.results_json)
    
    flattened = []
    for res in results:
        base = {
            "BUSCADO": res.get("input_name1", ""),
            "CEDULA": res.get("cedula", ""),
            "ABOGADO": res.get("abogado", ""),
            "CANT_ENCONTRADOS": res.get("found_count", 0),
        }
        
        sel = res.get("selected")
        if sel:
            # Parsear sujetos para d1/d2
            sujetos_str = sel.get("sujetosProcesales") or ""
            d1, d2, _ = parse_sujetos_procesales(sujetos_str)
            
            id_p = sel.get("idProceso")
            portal_url = ""
            if id_p:
                portal_url = f"https://consultaprocesos.ramajudicial.gov.co/Consulta/Detalle?idProceso={id_p}&esPrivado=false"

            rad_val = sel.get("llaveProceso") or sel.get("numero")
            base.update({
                "RADICADO": str(rad_val) if rad_val else "No encontrado",
                "DEMANDANTE": d1 or sel.get("demandante", ""),
                "DEMANDADO": d2 or sel.get("demandado", ""),
                "DESPACHO": sel.get("despacho", ""),
                "FECHA_RADICACION": (sel.get("fechaRadicacion") or "")[:10],
                "ULTIMA_ACTUACION": (sel.get("fechaUltimaActuacion") or "")[:10],
                "ID_PROCESO": str(id_p) if id_p else "",
                "PORTAL_RAMA": portal_url
            })
        else:
            base.update({
                "RADICADO": "No encontrado",
                "DEMANDANTE": "",
                "DEMANDADO": "",
                "DESPACHO": "",
                "FECHA_RADICACION": "",
                "ULTIMA_ACTUACION": "",
                "ID_PROCESO": "",
            })
        flattened.append(base)
        
    df = pd.DataFrame(flattened)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Resultados')
        workbook = writer.book
        worksheet = writer.sheets['Resultados']
        
        # Formato de texto para columnas de nmeros largos
        text_format = workbook.add_format({'num_format': '@'})
        
        # Aplicamos formato de texto a la columna RADICADO (ndice 3 usualmente: Nombre, Cdula, Abogado, Cant, RADICADO...)
        # Buscamos el ndice dinmicamente
        if "RADICADO" in df.columns:
            col_idx = df.columns.get_loc("RADICADO")
            # Aplicar a toda la columna (filas 1 a N)
            worksheet.set_column(col_idx, col_idx, 30, text_format)
            
        # Opcionalmente ajustar anchos
        worksheet.set_column('A:A', 30) # Nombre
        worksheet.set_column('H:H', 20) # Ultima Actuacin
        worksheet.set_column('I:I', 15) # ID Proceso
        worksheet.set_column('J:J', 50) # Link Portal
    
    output.seek(0)
    
    filename = f"resultado_busqueda_{job_id}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }
    return StreamingResponse(output, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.post("/cases/bulk-update-metadata")
async def bulk_update_metadata(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Validar permisos de usuario normal
    if not is_global_superadmin(current_user) and not is_company_admin(current_user):
        has_perm = False
        try:
            has_perm = db.query(Permission).join(role_permissions).join(Role).join(user_roles).filter(
                user_roles.c.user_id == current_user.id,
                Permission.name == "cases.bulk-update"
            ).first() is not None
        except Exception:
            pass
        if not has_perm:
            raise HTTPException(status_code=403, detail="No tienes permiso para realizar actualización masiva de metadatos.")

    try:
        content = await file.read()
        df = pd.read_excel(BytesIO(content))
        # Normalizar columnas
        df.columns = [str(c).strip().upper() for c in df.columns]
        
        updated_cases = 0
        omitted_rows = []
        
        for idx, row in df.iterrows():
            radicado = clean_str(str(row.get("RADICADO", "")))
            if not radicado:
                omitted_rows.append({"row_index": idx, "radicado": "", "reason": "Radicado vacío"})
                continue
            
            cedula = str(row.get("CEDULA", "")).strip() if "CEDULA" in df.columns else None
            abogado = str(row.get("ABOGADO", "")).strip() if "ABOGADO" in df.columns else None
            
            target_company_id = None
            if is_global_superadmin(current_user):
                comp_val = row.get("COMPANY_ID") or row.get("EMPRESA")
                if comp_val and not pd.isna(comp_val):
                    if str(comp_val).strip().isdigit():
                        target_company_id = int(str(comp_val).strip())
                    else:
                        from backend.models import Company
                        company_obj = db.query(Company).filter(Company.nombre.ilike(str(comp_val).strip())).first()
                        if company_obj:
                            target_company_id = company_obj.id
                if not target_company_id:
                    # SuperAdmin sin empresa objetivo especificada -> omitir
                    omitted_rows.append({"row_index": idx, "radicado": radicado, "reason": "Empresa objetivo no especificada o no válida para SuperAdmin"})
                    continue
            else:
                # Company Admin o normal: ignorar cualquier company_id del Excel y usar el propio
                target_company_id = current_user.company_id
                
            if target_company_id is None:
                omitted_rows.append({"row_index": idx, "radicado": radicado, "reason": "No se pudo determinar la empresa del usuario"})
                continue
                
            # Actualizar únicamente por company_id + radicado (nunca por radicado global)
            q_case = db.query(Case).filter(Case.radicado == radicado, Case.company_id == target_company_id)
            
            cases = q_case.all()
            if not cases:
                omitted_rows.append({"row_index": idx, "radicado": radicado, "reason": "Caso no encontrado en la empresa especificada"})
                continue

            for c in cases:
                if cedula and cedula.lower() != "nan":
                    c.cedula = cedula
                if abogado and abogado.lower() != "nan":
                    c.abogado = abogado
                updated_cases += 1
                
        db.commit()
        return {
            "ok": True, 
            "updated_count": updated_cases, 
            "omitted_count": len(omitted_rows), 
            "omitted_details": omitted_rows
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error procesando Excel: {str(e)}")


# =========================
# CLICKUP INTEGRATION
# =========================

class ClickUpImportRequest(BaseModel):
    token: str

@app.post("/projects/import-clickup")
async def import_clickup(
    data: ClickUpImportRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """Lanza la migraci?n desde ClickUp en segundo plano."""
    from backend.clickup_sync import migrate_clickup_to_emdecob
    
    # Check admin (permitir excepcion para cuentas juridicas)
    if not current_user.is_admin and 'juri' not in current_user.username.lower() and current_user.id != 2:
        raise HTTPException(status_code=403, detail="No autorizado para realizar importacion masiva")

    async def _do_import():
        db = SessionLocal()
        try:
            await migrate_clickup_to_emdecob(data.token, db, current_user.id)
        except Exception as e:
            print(f"[CLICKUP-IMPORT] Fallo: {e}")
        finally:
            db.close()

    background_tasks.add_task(_do_import)
    
    return {
        "ok": True,
        "message": "La importaci?n ha comenzado en segundo plano. Esto puede tardar varios minutos dependiendo del volumen de datos."
    }

# =========================
# PROJECT MANAGEMENT API
# =========================

class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    visibility: str = "TEAM_COLLABORATION"

class FolderCreate(BaseModel):
    name: str
    workspace_id: int

class ListCreate(BaseModel):
    name: str
    folder_id: Optional[int] = None
    workspace_id: int

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    list_id: Optional[int] = None
    assignee_id: Optional[int] = None
    priority: Optional[str] = None
    status: str = "to do"
    due_date: Optional[datetime] = None
    case_id: Optional[int] = None
    parent_id: Optional[int] = None
    
    class Config:
        extra = "ignore"

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None
    case_id: Optional[int] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    assignee_ids: Optional[List[int]] = None
    tags: Optional[List[str]] = None
    
    class Config:
        extra = "ignore"


class ChecklistItemCreate(BaseModel):
    content: str

class CommentCreate(BaseModel):
    task_id: int
    content: str

@app.get("/api/projects/workspaces")
@app.get("/projects/workspaces")
async def get_workspaces(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna la jerarquia completa de espacios para el usuario."""
    
    # 0. AUTO-REPARACION: Asignar company_id a workspaces que no lo tienen,
    #    basado en el company_id del owner. Esto soluciona workspaces importados
    #    desde ClickUp que se crearon sin company_id.
    if current_user.company_id:
        orphan_ws = db.query(Workspace).filter(
            Workspace.company_id.is_(None),
            Workspace.owner_id.isnot(None)
        ).all()
        repaired = 0
        for ows in orphan_ws:
            owner = db.query(User).filter(User.id == ows.owner_id).first()
            if owner and owner.company_id == current_user.company_id:
                ows.company_id = current_user.company_id
                repaired += 1
        if repaired > 0:
            db.commit()
            print(f"[PROJECTS] Auto-reparados {repaired} workspaces sin company_id")

    # 1. Determinar qué espacios puede ver el usuario
    if is_global_superadmin(current_user):
        # SuperAdmin ve todos los espacios
        workspaces = db.query(Workspace).options(
            selectinload(Workspace.folders).selectinload(Folder.lists),
            selectinload(Workspace.lists)
        ).all()
    else:
        # Los usuarios ven los espacios de su empresa, los que son dueños,
        # o aquellos donde son miembros explícitos.
        # Usamos subquery para evitar duplicados con el outerjoin de WorkspaceMember.
        member_ws_ids = db.query(WorkspaceMember.workspace_id).filter(
            WorkspaceMember.user_id == current_user.id
        ).subquery()
        
        workspaces = db.query(Workspace).filter(
            or_(
                Workspace.company_id == current_user.company_id,
                Workspace.owner_id == current_user.id,
                Workspace.id.in_(member_ws_ids)
            )
        ).options(
            selectinload(Workspace.folders).selectinload(Folder.lists),
            selectinload(Workspace.lists)
        ).all()

    # 2. Fallback local: si no hay espacios, crear estructura mínima
    if not workspaces and not is_global_superadmin(current_user):
        print("[PROJECTS] Creando estructura basica de proyectos local...")
        ws = Workspace(
            name="Espacio Interno EMDECOB", 
            visibility="TEAM_COLLABORATION", 
            owner_id=current_user.id, 
            company_id=current_user.company_id
        )
        db.add(ws)
        db.commit()
        db.refresh(ws)
        
        f = Folder(name="Proyectos y Casos", workspace_id=ws.id)
        db.add(f)
        db.commit()
        db.refresh(f)
        
        l = ProjectList(name="Tareas Pendientes", folder_id=f.id, workspace_id=ws.id)
        db.add(l)
        db.commit()
        
        workspaces = [db.query(Workspace).options(
            selectinload(Workspace.folders).selectinload(Folder.lists),
            selectinload(Workspace.lists)
        ).filter(Workspace.id == ws.id).first()]
    
    results = []
    seen_ids = set()
    for ws in workspaces:
        if ws.id in seen_ids:
            continue
        seen_ids.add(ws.id)
        folders = []
        for f in ws.folders:
            lists = [{"id": l.id, "name": l.name} for l in f.lists]
            folders.append({"id": f.id, "name": f.name, "lists": lists})
        
        workspace_lists = [{"id": l.id, "name": l.name} for l in ws.lists]
        
        results.append({
            "id": ws.id,
            "name": ws.name,
            "visibility": ws.visibility,
            "clickup_id": ws.clickup_id,
            "folders": folders,
            "lists": workspace_lists
        })
    
    return results

@app.post("/api/projects/workspaces")
@app.post("/projects/workspaces")
async def create_workspace(
    ws_data: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        ws = Workspace(
            name=ws_data.name, 
            description=ws_data.description, 
            visibility=ws_data.visibility, 
            owner_id=current_user.id
        )
        db.add(ws)
        db.commit()
        db.refresh(ws)
        return ws
    except Exception as e:
        db.rollback()
        print(f"[PROJECTS] Error creating workspace: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al crear espacio: {str(e)}")

class MemberAdd(BaseModel):
    user_id: int
    role: str = "VIEWER"

@app.post("/api/projects/workspaces/{workspace_id}/members")
@app.post("/projects/workspaces/{workspace_id}/members")
async def add_workspace_member(
    workspace_id: int,
    m_data: MemberAdd,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verificar que el usuario actual es el dueño o admin
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace no encontrado")
        
    if ws.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No tienes permiso para agregar miembros")
        
    member = WorkspaceMember(workspace_id=workspace_id, user_id=m_data.user_id, role=m_data.role)
    db.add(member)
    db.commit()
    return {"ok": True}

@app.post("/api/projects/folders")
@app.post("/projects/folders")
async def create_folder(
    f_data: FolderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        f = Folder(name=f_data.name, workspace_id=f_data.workspace_id)
        db.add(f)
        db.commit()
        db.refresh(f)
        return f
    except Exception as e:
        db.rollback()
        print(f"[PROJECTS] Error creating folder: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al crear carpeta: {str(e)}")

@app.post("/api/projects/lists")
@app.post("/projects/lists")
async def create_list(
    l_data: ListCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        l = ProjectList(
            name=l_data.name, 
            folder_id=l_data.folder_id, 
            workspace_id=l_data.workspace_id
        )
        db.add(l)
        db.commit()
        db.refresh(l)
        return l
    except Exception as e:
        db.rollback()
        print(f"[PROJECTS] Error creating list: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al crear lista: {str(e)}")

@app.delete("/api/projects/workspaces/{workspace_id}")
@app.delete("/projects/workspaces/{workspace_id}")
async def delete_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ws = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not ws:
        raise HTTPException(status_code=404, detail="Espacio no encontrado")
    
    if ws.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar este espacio")
        
    try:
        db.delete(ws)
        db.commit()
        return {"ok": True, "message": "Espacio eliminado exitosamente"}
    except Exception as e:
        db.rollback()
        print(f"[PROJECTS] Error deleting workspace: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar espacio: {str(e)}")

@app.delete("/api/projects/folders/{folder_id}")
@app.delete("/projects/folders/{folder_id}")
async def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    f = db.query(Folder).filter(Folder.id == folder_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada")
    
    ws = db.query(Workspace).filter(Workspace.id == f.workspace_id).first()
    if ws and ws.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar esta carpeta")
        
    try:
        db.delete(f)
        db.commit()
        return {"ok": True, "message": "Carpeta eliminada exitosamente"}
    except Exception as e:
        db.rollback()
        print(f"[PROJECTS] Error deleting folder: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar carpeta: {str(e)}")

@app.delete("/api/projects/lists/{list_id}")
@app.delete("/projects/lists/{list_id}")
async def delete_list(
    list_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    l = db.query(ProjectList).filter(ProjectList.id == list_id).first()
    if not l:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    
    ws = db.query(Workspace).filter(Workspace.id == l.workspace_id).first()
    if ws and ws.owner_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar esta lista")
        
    try:
        db.delete(l)
        db.commit()
        return {"ok": True, "message": "Lista eliminada exitosamente"}
    except Exception as e:
        db.rollback()
        print(f"[PROJECTS] Error deleting list: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error al eliminar lista: {str(e)}")


@app.get("/api/cases/id/{case_id}/tasks")
@app.get("/cases/id/{case_id}/tasks")
async def get_tasks_by_case(
    case_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    case_obj = db.query(Case).filter(Case.id == case_id).first()
    if not case_obj:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
        
    if not is_global_superadmin(current_user):
        if case_obj.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="No tienes acceso a este caso.")
            
    tasks = db.query(Task).filter(Task.case_id == case_id).all()
    return tasks

# Endpoint de diagnóstico público (sin auth) para verificar que el backend responde
@app.get("/debug/tasks")
async def debug_tasks(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Endpoint público sin auth para diagnóstico. NO usar en producción final."""
    if not is_global_superadmin(current_user):
        raise HTTPException(status_code=403, detail="Acceso denegado")
    try:
        tasks = db.query(Task).limit(5).all()
        total = db.query(Task).count()
        return {
            "ok": True,
            "total_tasks_in_db": total,
            "sample": [{"id": t.id, "title": t.title, "list_id": t.list_id, "status": t.status} for t in tasks]
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/admin/bulk-import")
async def bulk_import(payload: dict, db: Session = Depends(get_db)):
    """
    Endpoint de importación masiva ONE-TIME.
    Recibe JSON con workspaces, folders, lists y tasks.
    Lo llama un script local que tiene acceso al PostgreSQL nativo.
    """
    import sqlalchemy as sa
    results = {}
    try:
        # 1. Workspaces
        for ws in payload.get("workspaces", []):
            db.execute(sa.text("""
                INSERT INTO workspaces (id, name, visibility, owner_id, clickup_id)
                VALUES (:id, :name, :vis, :oid, :cid)
                ON CONFLICT (id) DO NOTHING
            """), {"id": ws["id"], "name": ws["name"], "vis": ws.get("visibility","TEAM_COLLABORATION"),
                   "oid": ws.get("owner_id", 2), "cid": ws.get("clickup_id")})
        db.commit()
        results["workspaces"] = len(payload.get("workspaces", []))

        # 2. Folders
        for f in payload.get("folders", []):
            db.execute(sa.text("""
                INSERT INTO folders (id, name, workspace_id, clickup_id)
                VALUES (:id, :name, :wid, :cid)
                ON CONFLICT (id) DO NOTHING
            """), {"id": f["id"], "name": f["name"], "wid": f["workspace_id"], "cid": f.get("clickup_id")})
        db.commit()
        results["folders"] = len(payload.get("folders", []))

        # 3. Lists
        for l in payload.get("lists", []):
            db.execute(sa.text("""
                INSERT INTO project_lists (id, name, folder_id, workspace_id, clickup_id)
                VALUES (:id, :name, :fid, :wid, :cid)
                ON CONFLICT (id) DO NOTHING
            """), {"id": l["id"], "name": l["name"], "fid": l.get("folder_id"),
                   "wid": l.get("workspace_id"), "cid": l.get("clickup_id")})
        db.commit()
        results["lists"] = len(payload.get("lists", []))

        # 4. Tasks - insertamos sin case_id para evitar FK constraint con tabla cases vacía
        for t in payload.get("tasks", []):
            db.execute(sa.text("""
                INSERT INTO tasks (id, title, description, status, priority, assignee_id,
                                   list_id, due_date, case_id, parent_id, created_at, clickup_id)
                VALUES (:id, :title, :desc, :status, :priority, :aid,
                        :lid, :due, NULL, :pid, :cat, :clickup)
                ON CONFLICT (id) DO NOTHING
            """), {
                "id": t["id"], "title": t["title"], "desc": t.get("description"),
                "status": t.get("status","to do"), "priority": t.get("priority"),
                "aid": t.get("assignee_id"), "lid": t.get("list_id"),
                "due": t.get("due_date"),
                "pid": t.get("parent_id"), "cat": t.get("created_at"), "clickup": t.get("clickup_id")
            })
        db.commit()
        results["tasks"] = len(payload.get("tasks", []))


        return {"ok": True, "imported": results}
    except Exception as e:
        db.rollback()
        return {"ok": False, "error": str(e)}

@app.get("/api/projects/tasks")
@app.get("/projects/tasks")
@app.get("/api/tasks")
@app.get("/tasks")
async def get_tasks(
    list_id: Optional[int] = None,
    status: Optional[str] = None,
    assignee_id: Optional[int] = None,
    radicado: Optional[str] = None,
    case_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Task).options(
        selectinload(Task.subtasks),
        selectinload(Task.tags),
        selectinload(Task.attachments),
        joinedload(Task.case)
    )
    
    # Aplicar filtros adicionales
    if list_id:
        query = query.filter(Task.list_id == list_id)
    if case_id:
        query = query.filter(Task.case_id == case_id)
    if radicado:
        # Buscamos el caso por radicado exacto o LIKE
        case_subquery = db.query(Case.id).filter(Case.radicado.like(f"%{radicado}%")).scalar_subquery()
        query = query.filter(Task.case_id == case_subquery)
    if assignee_id:
        query = query.filter(or_(Task.assignee_id == assignee_id, Task.creator_id == assignee_id))
    if status:
        query = query.filter(Task.status.ilike(f"%{status}%"))
        
    # Unimos con ProjectList para saber a qué workspace pertenece la tarea
    # Usamos outerjoin para asegurar que tareas sin lista (si existieran) no desaparezcan por error
    query = query.outerjoin(ProjectList, Task.list_id == ProjectList.id)
    query = query.outerjoin(Case, Task.case_id == Case.id)
    
    if current_user.is_admin and not current_user.company_id:
        # SuperAdmin ve todo sin restricciones
        pass
    else:
        # Filtro por Membresía de Workspace (Core de Colaboración)
        # El usuario debe ser dueño del workspace o miembro explícito
        user_workspaces_subquery = db.query(Workspace.id).outerjoin(WorkspaceMember).filter(
            or_(
                Workspace.owner_id == current_user.id,
                WorkspaceMember.user_id == current_user.id
            )
        ).scalar_subquery()
        
        # Filtro SaaS: Ve tareas asociadas a casos de su empresa, O en sus workspaces, O asignadas a él, O creadas por él
        query = query.filter(
            or_(
                # Caso propio de su empresa
                and_(Task.case_id.isnot(None), Case.company_id == current_user.company_id),
                # Tarea sin caso pero en un workspace al que pertenece
                and_(Task.case_id.is_(None), ProjectList.workspace_id.in_(user_workspaces_subquery)),
                # Siempre ve lo que tiene asignado o lo que el sistema asocia a su ID directamente
                Task.assignee_id == current_user.id,
                # O creadas por el usuario
                Task.creator_id == current_user.id
            )
        )
        
    tasks = query.order_by(desc(Task.created_at)).all()
    
    res_list = []
    for t in tasks:
        res_list.append({
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None,
            "list_id": t.list_id,
            "assignee_id": t.assignee_id,
            "assignee_name": t.assignee_name,
            "creator_id": t.creator_id,
            "case_id": t.case_id,
            "parent_id": t.parent_id,
            "clickup_id": t.clickup_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            "tags": [{"id": tg.id, "name": tg.name, "color": tg.color} for tg in t.tags],
            "assignees": [{"id": u.id, "username": u.username, "nombre": u.nombre} for u in t.assignees],
            # Case fields for grouping in frontend
            "case_radicado": t.case.radicado if t.case else None,
            "case_demandante": t.case.demandante if t.case else None,
            "case_demandado": t.case.demandado if t.case else None,
        })
    return res_list

# Control de concurrencia y prevención de bucles
clickup_sync_semaphore = None
_in_flight_syncs = set()

async def sync_task_with_clickup_background(task_id: int, api_token: str, user_id: int):
    """Sincroniza una tarea de ClickUp en segundo plano para evitar bloqueos y timeouts."""
    global clickup_sync_semaphore
    if clickup_sync_semaphore is None:
        clickup_sync_semaphore = asyncio.Semaphore(3)
        
    if task_id in _in_flight_syncs:
        print(f"[BG-CLICKUP] Sync ya está en progreso para tarea ID {task_id}, omitiendo.")
        return
        
    _in_flight_syncs.add(task_id)
    try:
        async with clickup_sync_semaphore:
            db = SessionLocal()
            try:
                task = db.query(Task).filter(Task.id == task_id).first()
                if not task or not task.clickup_id:
                    return
                    
                from backend.clickup_sync import fetch_clickup, process_task
                print(f"[BG-CLICKUP] Iniciando sync para tarea ID {task_id} (ClickUp {task.clickup_id})...")
                t_data = await fetch_clickup(f"task/{task.clickup_id}?include_subtasks=true&include_checklists=true", api_token)
                if t_data:
                    all_users = db.query(User).all()
                    user_map = { (u.nombre or '').lower().strip(): u.id for u in all_users if u.nombre }
                    user_map.update({ (u.username or '').lower().strip(): u.id for u in all_users })
                    
                    await process_task(t_data, task.list_id, db, user_id, user_map, api_token, inherited_case_id=task.case_id)
                    task.updated_at = now_colombia()
                    db.commit()
                    print(f"[BG-CLICKUP] Sync completado con exito para tarea ID {task_id}")
            except Exception as e:
                print(f"[BG-CLICKUP] Error sincronizando tarea {task_id} en segundo plano: {e}")
                db.rollback()
            finally:
                db.close()
    finally:
        _in_flight_syncs.discard(task_id)

@app.get("/api/tasks/{task_id}")
@app.get("/tasks/{task_id}")
async def get_task_detail(
    task_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        from fastapi.responses import JSONResponse
        from datetime import datetime
        
        task = db.query(Task).options(
            selectinload(Task.subtasks).selectinload(Task.tags),
            selectinload(Task.checklists),
            selectinload(Task.comments),
            selectinload(Task.tags),
            selectinload(Task.attachments)
        ).filter(Task.id == task_id).first()
        
        if not task:
            return JSONResponse(status_code=404, content={"detail": "Tarea no encontrada"})
            
        if not check_task_access(task, current_user, db):
            return JSONResponse(status_code=403, content={"detail": "No tienes acceso a esta tarea"})
        
        # Sincronización inteligente on-demand si es tarea de ClickUp
        if task.clickup_id:
            api_token = request.headers.get("X-ClickUp-Token")
            if api_token:
                is_fresh = False
                try:
                    age_seconds = (now_colombia() - task.updated_at).total_seconds()
                    if age_seconds < 120:
                        is_fresh = True
                        print(f" [TASK] Sirviendo tarea de ClickUp {task.clickup_id} desde BD local (fresca hace {age_seconds:.1f}s)")
                except Exception as age_err:
                    print(f" [TASK] Error calculando edad de la tarea: {age_err}")

                if not is_fresh:
                    print(f" [TASK] Lanzando sincronizacion en segundo plano para ClickUp task={task.clickup_id}")
                    # Usar asyncio.create_task normal, el semáforo se maneja dentro de la función
                    asyncio.create_task(sync_task_with_clickup_background(task.id, api_token, current_user.id))
        
        # Construcción manual segura para evitar recursividad infinita (Circular Reference)
        def fmt_dt(dt):
            if dt is None: return None
            return dt.isoformat() if isinstance(dt, datetime) else dt

        res_data = {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "status": task.status,
            "priority": task.priority,
            "due_date": fmt_dt(task.due_date),
            "list_id": task.list_id,
            "assignee_id": task.assignee_id,
            "assignee_name": task.assignee_name,
            "creator_id": task.creator_id,
            "case_id": task.case_id,
            "parent_id": task.parent_id,
            "clickup_id": task.clickup_id,
            "created_at": fmt_dt(task.created_at),
            "updated_at": fmt_dt(task.updated_at),
            "subtasks": [
                {
                    "id": st.id,
                    "title": st.title,
                    "status": st.status,
                    "priority": st.priority,
                    "due_date": fmt_dt(st.due_date),
                    "assignee_id": st.assignee_id,
                    "assignee_name": st.assignee_name,
                    "parent_id": st.parent_id,
                    "tags": [{"name": tg.name, "color": tg.color} for tg in st.tags]
                } for st in task.subtasks
            ],
            "comments": [
                {
                    "id": c.id,
                    "content": c.content,
                    "user_id": c.user_id,
                    "user_name": c.user_name,
                    "created_at": fmt_dt(c.created_at)
                } for c in task.comments
            ],
            "tags": [{"name": t.name, "color": t.color} for t in task.tags],
            "checklists": [
                {
                    "id": cl.id,
                    "content": cl.content,
                    "is_completed": cl.is_completed
                } for cl in task.checklists
            ],
            "attachments": [
                {
                    "id": a.id,
                    "name": a.name,
                    "file_path": a.file_path,
                    "file_type": a.file_type
                } for a in task.attachments
            ]
        }
        
        return JSONResponse(content=res_data)
    except Exception as e:
        db.rollback()
        import traceback
        err_msg = f"Error: {str(e)}"
        print(f"[CRITICAL ERROR] get_task_detail: {traceback.format_exc()}")
        return JSONResponse(status_code=500, content={"detail": err_msg})

@app.get("/cases/{case_id}/tasks")
async def get_case_tasks_endpoint(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna las tareas vinculadas a un radicado espec?fico."""
    q = db.query(Task).filter(Task.case_id == case_id)
    
    # Seguridad: Si no es admin, verificar que el caso le pertenezca, esté asignado, o sea el creador de la tarea
    if not current_user.is_admin:
        q = q.join(Case, Task.case_id == Case.id)
        q = q.filter(or_(
            Case.user_id == current_user.id,
            Task.assignee_id == current_user.id,
            Task.creator_id == current_user.id
        ))

    return q.order_by(desc(Task.created_at)).all()

@app.post("/api/projects/tasks")
@app.post("/projects/tasks")
@app.post("/api/tasks")
@app.post("/tasks")
async def create_task(
    t_data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Determinar el company_id de la tarea
    comp_id = current_user.company_id
    if t_data.case_id:
        case_obj = db.query(Case).filter(Case.id == t_data.case_id).first()
        if not case_obj:
            raise HTTPException(status_code=404, detail="Caso no encontrado")
        if not is_global_superadmin(current_user) and case_obj.company_id != current_user.company_id:
            raise HTTPException(status_code=403, detail="No tienes acceso a este caso.")
        comp_id = case_obj.company_id or comp_id
    else:
        if not is_global_superadmin(current_user) and current_user.company_id is None:
            raise HTTPException(status_code=403, detail="No se pudo determinar la empresa del usuario.")

    lid = t_data.list_id
    list_exists = False
    
    # 1. Si se especificó una lista, verificar que exista y pertenezca a la empresa del usuario
    if lid is not None:
        if is_global_superadmin(current_user):
            list_exists = db.query(ProjectList).filter(ProjectList.id == lid).count() > 0
        else:
            list_exists = db.query(ProjectList).join(Workspace).filter(
                ProjectList.id == lid,
                Workspace.company_id == comp_id
            ).count() > 0
        
    if not list_exists:
        # 2. Intentar buscar lista del abogado del caso dentro de la misma empresa
        if t_data.case_id:
            case_obj = db.query(Case).filter(Case.id == t_data.case_id).first()
            if case_obj and case_obj.abogado:
                lawyer_list = db.query(ProjectList).join(Workspace).filter(
                    Workspace.company_id == comp_id,
                    ProjectList.name.ilike(f"%{case_obj.abogado}%")
                ).first()
                if lawyer_list:
                    lid = lawyer_list.id
                    list_exists = True
                    print(f" [TASK] Reasignando list_id invalido a la lista del abogado de la empresa: {lawyer_list.name} (ID {lid})")
        
        # 3. Intentar buscar "BANDEJA DE ENTRADA" o cualquier lista existente de la misma empresa
        if not list_exists:
            default_list = db.query(ProjectList).join(Workspace).filter(
                Workspace.company_id == comp_id,
                ProjectList.name.ilike("%bandeja%")
            ).first()
            if not default_list:
                default_list = db.query(ProjectList).join(Workspace).filter(
                    Workspace.company_id == comp_id
                ).first()
            
            if default_list:
                lid = default_list.id
                list_exists = True
                print(f" [TASK] Reasignando list_id a lista por defecto de la empresa: {default_list.name} (ID {lid})")
            
        # 4. Si la empresa no tiene NINGÚN espacio o lista de trabajo, creamos uno al vuelo automáticamente
        if not list_exists:
            print(f" [TASK] Creando Workspace y List por defecto al vuelo para la empresa {comp_id}...")
            try:
                ws = Workspace(
                    name="Espacio Interno EMDECOB", 
                    visibility="TEAM_COLLABORATION", 
                    owner_id=current_user.id, 
                    company_id=comp_id
                )
                db.add(ws)
                db.commit()
                db.refresh(ws)
                
                f = Folder(name="Proyectos y Casos", workspace_id=ws.id)
                db.add(f)
                db.commit()
                db.refresh(f)
                
                l = ProjectList(name="Tareas Pendientes", folder_id=f.id, workspace_id=ws.id)
                db.add(l)
                db.commit()
                db.refresh(l)
                
                lid = l.id
                list_exists = True
                print(f" [TASK] Creado y asignado list_id por defecto ({lid}) exitosamente.")
            except Exception as e:
                db.rollback()
                print(f"[ERROR] Auto-creando workspace y list en create_task: {str(e)}")
                # Si falla la creación, intentar usar cualquier lista global como último recurso
                fallback_list = db.query(ProjectList).first()
                if fallback_list:
                    lid = fallback_list.id
                    list_exists = True
                else:
                    raise HTTPException(status_code=400, detail=f"No se pudo crear ni asignar una lista para la tarea: {str(e)}")

    print(f"[DEBUG] Creating task: title={t_data.title}, parent_id={t_data.parent_id}, case_id={t_data.case_id}")
    try:
        task = Task(
            title=t_data.title,
            description=t_data.description,
            list_id=lid,
            assignee_id=t_data.assignee_id,
            priority=t_data.priority,
            status=(t_data.status or "ABIERTO").upper(),
            due_date=t_data.due_date,
            case_id=t_data.case_id,
            parent_id=t_data.parent_id,
            creator_id=current_user.id,
            company_id=comp_id
        )
        
        # Auditoría de identidad: Poblar assignee_name automáticamente
        if t_data.assignee_id:
            user_obj = db.query(User).filter(User.id == t_data.assignee_id).first()
            if user_obj:
                task.assignee_name = user_obj.nombre or user_obj.username
        db.add(task)
        db.commit()
        db.refresh(task)
        return task
    except Exception as e:
        db.rollback()
        import traceback
        print(f"[CRITICAL ERROR] create_task: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.delete("/api/projects/tasks/{task_id}")
@app.delete("/projects/tasks/{task_id}")
@app.delete("/api/tasks/{task_id}")
@app.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
        
    if not check_task_access(task, current_user, db):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta tarea.")
    
    try:
        # Eliminar subtareas primero
        subtasks = db.query(Task).filter(Task.parent_id == task_id).all()
        for st in subtasks:
            db.query(TaskComment).filter(TaskComment.task_id == st.id).delete()
            db.query(TaskChecklistItem).filter(TaskChecklistItem.task_id == st.id).delete()
            db.delete(st)
        
        # Eliminar comentarios, checklists y attachments de la tarea padre
        db.query(TaskComment).filter(TaskComment.task_id == task_id).delete()
        db.query(TaskChecklistItem).filter(TaskChecklistItem.task_id == task_id).delete()
        db.query(TaskAttachment).filter(TaskAttachment.task_id == task_id).delete()
        
        db.delete(task)
        db.commit()
        print(f"[TASK] Tarea {task_id} eliminada por usuario {current_user.username}")
        return {"ok": True, "detail": "Tarea eliminada correctamente"}
    except Exception as e:
        db.rollback()
        import traceback
        print(f"[CRITICAL ERROR] delete_task: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/projects/tasks/{task_id}/comments")
@app.post("/api/projects/tasks/{task_id}/comments")
@app.post("/api/tasks/{task_id}/comments")
@app.post("/tasks/{task_id}/comments")
async def add_task_comment(
    task_id: int,
    data: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
        
    if not check_task_access(task, current_user, db):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta tarea.")

    comment = TaskComment(
        task_id=task_id,
        content=data.get("content"),
        user_id=current_user.id,
        user_name=current_user.nombre or current_user.username
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    # Sincronización con ClickUp si la tarea tiene clickup_id
    if task.clickup_id:
        api_token = request.headers.get("X-ClickUp-Token") or getattr(current_user, 'clickup_api_token', None)
        if api_token:
            try:
                import httpx
                url = f"https://api.clickup.com/api/v2/task/{task.clickup_id}/comment"
                headers = {
                    "Authorization": api_token,
                    "Content-Type": "application/json"
                }
                body = {
                    "comment_text": data.get("content")
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(url, headers=headers, json=body)
                    if resp.status_code != 200:
                        print(f"[CLICKUP SYNC COMMENT ERROR] Code: {resp.status_code}, Body: {resp.text}")
                    else:
                        print(f"[CLICKUP SYNC COMMENT SUCCESS] Comment created in ClickUp for task {task.clickup_id}")
            except Exception as e:
                print(f"[CLICKUP SYNC COMMENT EXCEPTION] Failed to sync comment with ClickUp: {e}")

    return comment

@app.post("/projects/tasks/{task_id}/checklists")
@app.post("/api/projects/tasks/{task_id}/checklists")
@app.post("/api/tasks/{task_id}/checklists")
@app.post("/tasks/{task_id}/checklists")
async def add_task_checklist_item(
    task_id: int,
    data: ChecklistItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
        
    if not check_task_access(task, current_user, db):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta tarea.")

    item = TaskChecklistItem(
        task_id=task_id,
        content=data.content,
        is_completed=False
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@app.delete("/api/tasks/comments/{comment_id}")
@app.delete("/tasks/comments/{comment_id}")
async def delete_task_comment(comment_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    comment = db.query(TaskComment).filter(TaskComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
        
    task = db.query(Task).filter(Task.id == comment.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarea asociada no encontrada")
        
    if not check_task_access(task, current_user, db):
        raise HTTPException(status_code=403, detail="No tienes acceso a este comentario.")
    
    # Solo admin o el creador pueden borrar
    if not current_user.is_admin and comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para borrar este comentario")
        
    db.delete(comment)
    db.commit()
    return {"ok": True}

@app.patch("/api/tasks/comments/{comment_id}")
@app.patch("/tasks/comments/{comment_id}")
async def update_task_comment(comment_id: int, data: dict = Body(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    comment = db.query(TaskComment).filter(TaskComment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
        
    task = db.query(Task).filter(Task.id == comment.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarea asociada no encontrada")
        
    if not check_task_access(task, current_user, db):
        raise HTTPException(status_code=403, detail="No tienes acceso a este comentario.")
    
    if not current_user.is_admin and comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="No tienes permiso para editar este comentario")
        
    comment.content = data.get("content", comment.content)
    db.commit()
    return comment

@app.patch("/api/tasks/checklists/{item_id}")
@app.patch("/tasks/checklists/{item_id}")
async def update_task_checklist_item(item_id: int, data: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(TaskChecklistItem).filter(TaskChecklistItem.id == item_id).first()
    if not item: raise HTTPException(status_code=404)
    
    task = db.query(Task).filter(Task.id == item.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarea asociada no encontrada")
        
    if not check_task_access(task, current_user, db):
        raise HTTPException(status_code=403, detail="No tienes acceso a este elemento de checklist.")

    if "content" in data: item.content = data["content"]
    if "is_completed" in data: item.is_completed = data["is_completed"]
    db.commit()
    return item

@app.delete("/api/tasks/checklists/{item_id}")
@app.delete("/tasks/checklists/{item_id}")
async def delete_task_checklist_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(TaskChecklistItem).filter(TaskChecklistItem.id == item_id).first()
    if not item: raise HTTPException(status_code=404)
    
    task = db.query(Task).filter(Task.id == item.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarea asociada no encontrada")
        
    if not check_task_access(task, current_user, db):
        raise HTTPException(status_code=403, detail="No tienes acceso a este elemento de checklist.")

    db.delete(item)
    db.commit()
    return {"ok": True}


@app.patch("/api/projects/tasks/{task_id}")
@app.patch("/projects/tasks/{task_id}")
@app.put("/api/projects/tasks/{task_id}")
@app.put("/projects/tasks/{task_id}")
@app.patch("/api/tasks/{task_id}")
@app.patch("/tasks/{task_id}")
async def update_task(
    task_id: int,
    t_data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
        
    if not check_task_access(task, current_user, db):
        raise HTTPException(status_code=403, detail="No tienes acceso a esta tarea.")
    
    try:
        if t_data.title is not None: task.title = t_data.title
        if t_data.description is not None: task.description = t_data.description
        if t_data.status is not None: task.status = t_data.status.upper()
        if t_data.priority is not None: task.priority = t_data.priority
        if t_data.due_date is not None: task.due_date = t_data.due_date
        if hasattr(t_data, 'case_id') and t_data.case_id is not None:
            case_obj = db.query(Case).filter(Case.id == t_data.case_id).first()
            if not case_obj:
                raise HTTPException(status_code=404, detail="Caso destino no encontrado")
            if not is_global_superadmin(current_user) and case_obj.company_id != current_user.company_id:
                raise HTTPException(status_code=403, detail="No tienes acceso al caso de destino.")
            task.case_id = t_data.case_id
            task.company_id = case_obj.company_id
        
        # Auditoría de identidad: Sincronizar nombre si cambia el ID
        if t_data.assignee_id is not None:
            user_obj = db.query(User).filter(User.id == t_data.assignee_id).first()
            if user_obj:
                task.assignee_name = user_obj.nombre or user_obj.username
        
        if hasattr(t_data, 'assignee_ids') and t_data.assignee_ids is not None:
            db_users = db.query(User).filter(User.id.in_(t_data.assignee_ids)).all()
            task.assignees = db_users
            if db_users:
                task.assignee_id = db_users[0].id
                task.assignee_name = ", ".join([(u.nombre or u.username) for u in db_users])
        
        if hasattr(t_data, 'tags') and t_data.tags is not None:
            # t_data.tags es una lista de nombres de tags
            db_tags = []
            for tname in t_data.tags:
                tag = db.query(Tag).filter(Tag.name == tname).first()
                if not tag:
                    tag = Tag(name=tname)
                    db.add(tag)
                    db.flush()
                db_tags.append(tag)
            task.tags = db_tags

        db.commit()
        db.refresh(task)
        return task
    except Exception as e:
        db.rollback()
        import traceback
        print(f"[CRITICAL ERROR] update_task {task_id}: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

    # Endpoint consolidado en la l?nea 3604
    pass

@app.get("/cases/{id}/tasks")
async def get_case_tasks(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    tasks = db.query(Task).filter(Task.case_id == id).order_by(desc(Task.created_at)).all()
    return [{
        "id": t.id,
        "title": t.title,
        "status": t.status,
        "priority": t.priority,
        "assignee_id": t.assignee_id,
        "list_id": t.list_id,
        "due_date": t.due_date,
        "parent_id": t.parent_id,
        "created_at": t.created_at
    } for t in tasks]

# =========================
# ADVANCED DASHBOARD & INLINE EDIT
# =========================

@app.get("/cases/stats/dashboard")
async def get_advanced_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene estad?sticas de negocio para las etiquetas superiores."""
    hoy = today_colombia()
    ayer = hoy - timedelta(days=1)
    
    # 1. Conteo de actuaciones en el mes actual
    first_of_month_str = hoy.replace(day=1).strftime("%Y-%m-%d")
    q_month = db.query(CaseEvent).filter(CaseEvent.event_date >= first_of_month_str)
    
    if current_user.is_admin and not current_user.company_id:
        pass
    else:
        q_month = q_month.join(Case, CaseEvent.case_id == Case.id).filter(Case.company_id == current_user.company_id)
        
    month_actions = q_month.with_entities(func.count(func.distinct(CaseEvent.case_id))).scalar()
    
    # 2. Conteo de casos por Abogado (desglose)
    q_abogados = db.query(Case.abogado, func.count(Case.id)).filter(Case.abogado.isnot(None), Case.abogado != "")
    if current_user.is_admin and not current_user.company_id:
        pass
    else:
        q_abogados = q_abogados.filter(Case.company_id == current_user.company_id)
    
    lawyer_counts = q_abogados.group_by(Case.abogado).all()
    lawyer_stats = [{"name": l[0], "count": l[1]} for l in lawyer_counts]
    lawyer_stats.sort(key=lambda x: x["count"], reverse=True)
    
    # 3. Alertas (casos sin leer)
    q_unread = db.query(Case).filter(
        Case.juzgado.isnot(None),
        Case.current_hash.isnot(None),
        or_(
            and_(Case.last_hash.isnot(None), Case.current_hash != Case.last_hash),
            and_(Case.last_hash.is_(None), Case.ultima_actuacion >= ayer),
        )
    )
    if current_user.is_admin and not current_user.company_id:
        pass
    else:
        q_unread = q_unread.filter(Case.company_id == current_user.company_id)
        
    unread_total = q_unread.count()
    
    return {
        "month_actions": month_actions,
        "month_name": hoy.strftime("%B"),
        "lawyer_stats": lawyer_stats,
        "unread_total": unread_total
    }

class LawyerUpdate(BaseModel):
    abogado: str

class LawyerBulkAssign(BaseModel):
    case_ids: List[int]
    abogado: str

class CaseActiveUpdate(BaseModel):
    is_active: bool
    motivo: Optional[str] = None

@app.patch("/cases/{case_id}/active")
async def update_case_active_status(
    case_id: int,
    data: CaseActiveUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retira o reactiva un radicado de gestión activa sin eliminar su historial."""
    cs = db.query(Case).filter(Case.id == case_id).first()
    if not cs:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
    if not is_global_superadmin(current_user) and cs.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este caso.")
    cs.is_active = data.is_active
    db.commit()
    accion = "reactivado" if data.is_active else "retirado de gestión"
    return {"ok": True, "is_active": cs.is_active, "message": f"Radicado {accion} correctamente."}

@app.patch("/cases/{case_id}/lawyer")
async def update_case_lawyer(
    case_id: int,
    data: LawyerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Actualización ultra-rápida del abogado para edición en línea."""
    cs = db.query(Case).filter(Case.id == case_id).first()
    if not cs:
        raise HTTPException(status_code=404, detail="Caso no encontrado")
        
    if not is_global_superadmin(current_user) and cs.company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="No tienes acceso a este caso.")
    
    cs.abogado = data.abogado
    # Intentar buscar el usuario por nombre para sincronizar user_id automáticamente
    match_user = db.query(User).filter(User.nombre.ilike(f"%{data.abogado}%")).first()
    if match_user:
        cs.user_id = match_user.id
        
    db.commit()
    return {"ok": True, "abogado": cs.abogado, "user_id": cs.user_id}

@app.post("/cases/bulk-assign-lawyer")
async def bulk_assign_lawyer(
    data: LawyerBulkAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Asigna un abogado a múltiples radicados a la vez."""
    query = db.query(Case).filter(Case.id.in_(data.case_ids))
    
    if not is_global_superadmin(current_user):
        query = query.filter(Case.company_id == current_user.company_id)
        
    cases = query.all()
    if not cases:
        raise HTTPException(status_code=404, detail="No se encontraron casos o no tienes acceso.")
        
    match_user = db.query(User).filter(User.nombre.ilike(f"%{data.abogado}%")).first()
    user_id = match_user.id if match_user else None
    
    for cs in cases:
        cs.abogado = data.abogado
        if user_id:
            cs.user_id = user_id
            
    db.commit()
    return {"ok": True, "updated": len(cases), "abogado": data.abogado}


# =========================
# INTEGRACIONES EXTERNAS (CALLY, ETC)

def check_task_access(task, current_user, db):
    """Determine if the current user can access a given task.
    Allows access if:
      * User is a global superadmin.
      * User is the assignee of the task (or one of multiple assignees).
      * User belongs to the same company (via task.company_id) or same case's company.
      * User is the owner or a member of the task's Workspace.
      * User has access to the parent task (for subtasks).
    """
    if is_global_superadmin(current_user):
        return True
    if getattr(task, "assignee_id", None) == current_user.id:
        return True
    if getattr(task, "creator_id", None) == current_user.id:
        return True
    if hasattr(task, "assignees") and task.assignees:
        if current_user.id in [u.id for u in task.assignees]:
            return True
    if getattr(task, "company_id", None) is not None:
        if task.company_id == current_user.company_id:
            return True
    if getattr(task, "case_id", None) is not None:
        case_obj = db.query(Case).filter(Case.id == task.case_id).first()
        if case_obj and case_obj.company_id == current_user.company_id:
            return True

    # If it's a subtask, it inherits access from the parent task
    if getattr(task, "parent_id", None) is not None:
        parent_task = db.query(Task).filter(Task.id == task.parent_id).first()
        if parent_task and check_task_access(parent_task, current_user, db):
            return True

    # Check Workspace membership/ownership
    if getattr(task, "list_id", None) is not None:
        list_obj = db.query(ProjectList).filter(ProjectList.id == task.list_id).first()
        if list_obj:
            ws_id = list_obj.workspace_id
            is_member = db.query(WorkspaceMember).filter(
                WorkspaceMember.workspace_id == ws_id,
                WorkspaceMember.user_id == current_user.id
            ).count() > 0
            if is_member:
                return True
            ws_obj = db.query(Workspace).filter(Workspace.id == ws_id).first()
            if ws_obj and ws_obj.owner_id == current_user.id:
                return True

    return False
# =========================

def verify_cally_key(api_key: str):
    """Dependency to verify Cally API Key"""
    db = SessionLocal()
    try:
        config = db.query(IntegrationConfig).filter(
            IntegrationConfig.service_name == 'cally',
            IntegrationConfig.api_key == api_key,
            IntegrationConfig.is_active == True
        ).first()
        if not config:
            raise HTTPException(status_code=401, detail="Clave de API de Cally inv?lida")
        return config
    finally:
        db.close()

@app.get("/api/config/integrations")
async def get_integrations_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """(Admin) Obtiene las claves de integraci?n externas."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    config = db.query(IntegrationConfig).filter(IntegrationConfig.service_name == 'cally').first()
    if not config:
        # Inicializar si no existe
        import secrets
        new_key = f"cally_{secrets.token_urlsafe(32)}"
        config = IntegrationConfig(service_name='cally', api_key=new_key)
        db.add(config)
        db.commit()
        db.refresh(config)
        
    return {
        "service_name": "cally",
        "api_key": config.api_key,
        "is_active": config.is_active,
        "report_url": "/api/external/reporting/tasks"
    }

@app.post("/api/config/integrations/regenerate")
async def regenerate_cally_key(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """(Admin) Regenera la clave de Cally."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="No autorizado")
    
    import secrets
    config = db.query(IntegrationConfig).filter(IntegrationConfig.service_name == 'cally').first()
    new_key = f"cally_{secrets.token_urlsafe(32)}"
    
    if not config:
        config = IntegrationConfig(service_name='cally', api_key=new_key)
        db.add(config)
    else:
        config.api_key = new_key
    
    db.commit()
    return {"api_key": new_key}

# =========================
# MODULO SUPERADMIN: EMPRESAS Y USUARIOS
# =========================

def log_audit_action(
    db: Session,
    user_id: Optional[int],
    company_id: Optional[int],
    accion: str,
    entidad: Optional[str] = None,
    entidad_id: Optional[int] = None,
    request: Optional[Request] = None,
    metadata_val: Optional[dict] = None
):
    try:
        import json
        ip = None
        user_agent = None
        if request:
            try:
                if hasattr(request, "client") and request.client:
                    ip = request.client.host
            except Exception:
                pass
            try:
                if hasattr(request, "headers") and request.headers:
                    user_agent = request.headers.get("user-agent")
            except Exception:
                pass
        
        meta_str = None
        if metadata_val:
            meta_str = json.dumps(metadata_val)
            
        log = AuditLog(
            user_id=user_id,
            company_id=company_id,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            ip=ip,
            user_agent=user_agent,
            metadata_json=meta_str
        )
        db.add(log)
        db.commit()
    except Exception as e:
        print(f"Error logging audit action: {e}")

class CompanyCreateRequest(BaseModel):
    nombre: str
    nit: Optional[str] = None
    limite_usuarios: int = 5

class UserCreateRequest(BaseModel):
    username: str
    password: str
    nombre: str
    company_id: Optional[int] = None
    email: Optional[str] = None
    is_admin: bool = False
    role: Optional[str] = "USER"
    cases_view_scope: Optional[str] = "OWN"
    sync_with_clickup: Optional[bool] = True
    clickup_api_token: Optional[str] = None

class UserAdminUpdateRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    nombre: Optional[str] = None
    company_id: Optional[int] = None
    email: Optional[str] = None
    is_admin: Optional[bool] = None
    role: Optional[str] = None
    cases_view_scope: Optional[str] = None
    is_active: Optional[bool] = None
    sync_with_clickup: Optional[bool] = None
    clickup_api_token: Optional[str] = None

class JudicialSourcesDebugRequest(BaseModel):
    radicado: str
    sources: Optional[list] = None
    dry_run: bool = True

@app.post("/api/admin/judicial-sources/debug")
async def debug_judicial_sources(
    data: JudicialSourcesDebugRequest,
    current_user: User = Depends(require_superadmin),
    db: Session = Depends(get_db)
):
    from backend.services.judicial_sources.source_router import run_multisource_check
    # Safe debug dry-run for SuperAdmins
    results = await run_multisource_check(
        radicado=data.radicado,
        company_id=current_user.company_id or 1,
        case_id=None,
        sources=data.sources,
        dry_run=data.dry_run,
        db=db
    )
    return {
        "radicado": data.radicado,
        "sources_checked": results
    }

@app.get("/api/admin/companies")
@app.get("/admin/companies")
async def get_admin_companies(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    try:
        comps = db.query(Company).order_by(Company.id.desc()).all()
        return [
            {
                "id": c.id,
                "nombre": c.nombre,
                "nit": c.nit,
                "estado": c.estado or "activo",
                "limite_usuarios": c.limite_usuarios,
                "user_limit": c.limite_usuarios,
                "active_users_count": db.query(User).filter(User.company_id == c.id, User.is_active == True).count(),
                "active_cases_count": db.query(Case).filter(Case.company_id == c.id, Case.is_active == True).count(),
                "cases_count": db.query(Case).filter(Case.company_id == c.id).count(),
                "payment_status": getattr(c, 'payment_status', 'al_dia') or 'al_dia',
                "suspension_reason": getattr(c, 'suspension_reason', None),
                "suspended_at": str(c.suspended_at) if getattr(c, 'suspended_at', None) else None,
                "suspended_by": getattr(c, 'suspended_by', None),
                "reactivated_at": str(c.reactivated_at) if getattr(c, 'reactivated_at', None) else None,
                "last_payment_date": str(c.last_payment_date) if getattr(c, 'last_payment_date', None) else None,
                "next_payment_due": str(c.next_payment_due) if getattr(c, 'next_payment_due', None) else None,
                "billing_notes": getattr(c, 'billing_notes', None),
                "created_at": str(c.created_at) if getattr(c, 'created_at', None) else None,
            }
            for c in comps
        ]
    except Exception as e:
        import traceback
        err_msg = f"ERROR in GET /admin/companies: {str(e)} | TRACE: {traceback.format_exc()}"
        print(err_msg)
        raise HTTPException(status_code=400, detail=err_msg)

@app.post("/api/admin/companies")
@app.post("/admin/companies")
async def create_admin_company(
    request: Request,
    data: CompanyCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    try:
        comp = Company(nombre=data.nombre, nit=data.nit, limite_usuarios=data.limite_usuarios, estado='activo', payment_status='al_dia')
        db.add(comp)
        db.commit()
        db.refresh(comp)
        
        # Log Audit
        log_audit_action(
            db=db,
            user_id=current_user.id,
            company_id=comp.id,
            accion="CREATE_COMPANY",
            entidad="Company",
            entidad_id=comp.id,
            request=request,
            metadata_val={"nombre": comp.nombre, "nit": comp.nit}
        )
        
        return {
            "id": comp.id,
            "nombre": comp.nombre,
            "nit": comp.nit,
            "estado": comp.estado or "activo",
            "limite_usuarios": comp.limite_usuarios,
            "user_limit": comp.limite_usuarios,
            "active_users_count": 0,
            "active_cases_count": 0,
            "payment_status": getattr(comp, 'payment_status', 'al_dia') or 'al_dia',
            "suspension_reason": None,
            "suspended_at": None,
            "suspended_by": None,
            "reactivated_at": None,
            "last_payment_date": None,
            "next_payment_due": None,
            "billing_notes": None,
            "created_at": str(comp.created_at) if getattr(comp, 'created_at', None) else None,
        }
    except Exception as e:
        import traceback
        err_msg = f"ERROR in POST /admin/companies: {str(e)} | TRACE: {traceback.format_exc()}"
        print(err_msg)
        raise HTTPException(status_code=400, detail=err_msg)

@app.get("/api/admin/users")
@app.get("/admin/users")
async def get_admin_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_superadmin)
):
    try:
        is_sa = is_global_superadmin(current_user)
        query = db.query(User)
        if not is_sa:
            query = query.filter(User.company_id == current_user.company_id)
        users = query.order_by(User.id.desc()).all()
        
        results = []
        for u in users:
            comp_name = "Global"
            if u.company_id:
                comp = db.query(Company).filter(Company.id == u.company_id).first()
                if comp:
                    comp_name = comp.nombre
                    
            u_is_sa = is_global_superadmin(u)
            u_role = "SUPERADMIN" if u_is_sa else (u.role or ("COMPANY_ADMIN" if u.is_admin else "USER"))
            
            results.append({
                "id": u.id,
                "username": u.username,
                "nombre": u.nombre,
                "email": u.email,
                "empresa": comp_name,
                "company_id": u.company_id,
                "role": u_role,
                "is_admin": u.is_admin,
                "is_superadmin": u_is_sa,
                "is_active": u.is_active,
                "last_login": None,
                "created_at": str(u.created_at) if u.created_at else None,
                "cases_view_scope": u.cases_view_scope or ("GLOBAL" if u_is_sa else ("COMPANY" if u.is_admin else "OWN")),
                "sync_with_clickup": getattr(u, 'sync_with_clickup', True),
                "clickup_api_token": getattr(u, 'clickup_api_token', None)
            })
        return results
    except Exception as e:
        import traceback
        err_msg = f"ERROR in GET /admin/users: {str(e)} | TRACE: {traceback.format_exc()}"
        print(err_msg)
        raise HTTPException(status_code=400, detail=err_msg)

@app.post("/api/admin/users")
@app.post("/admin/users")
async def create_admin_user(
    request: Request,
    data: UserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_superadmin)
):
    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        is_sa = is_global_superadmin(current_user)
        
        # Enforce Company Admin limitations
        if not is_sa:
            if data.company_id != current_user.company_id:
                raise HTTPException(status_code=400, detail="No puedes asignar un usuario a otra empresa.")
            if data.role != "USER" and data.role != "STANDARD":
                raise HTTPException(status_code=400, detail="Solo puedes crear usuarios con el rol estándar (USER).")
            if data.cases_view_scope == "GLOBAL":
                raise HTTPException(status_code=400, detail="No puedes asignar alcance GLOBAL a usuarios de tu empresa.")
                
        # Validate unique username
        existing_username = db.query(User).filter(User.username == data.username).first()
        if existing_username:
            raise HTTPException(status_code=400, detail=f"El usuario '{data.username}' ya existe.")
            
        if data.email:
            existing_email = db.query(User).filter(User.email == data.email).first()
            if existing_email:
                raise HTTPException(status_code=400, detail=f"El correo '{data.email}' ya está registrado.")
                
        role_upper = (data.role or "USER").upper()
        if role_upper == "STANDARD":
            role_upper = "USER"
            
        u_scope = (data.cases_view_scope or "OWN").upper()
        
        # Enforce Scope & Role validation rules
        if u_scope == "GLOBAL" and role_upper != "SUPERADMIN":
            raise HTTPException(status_code=400, detail="Solo los SuperAdmins pueden tener alcance GLOBAL.")
        if u_scope == "COMPANY" and role_upper not in ["SUPERADMIN", "COMPANY_ADMIN"]:
            raise HTTPException(status_code=400, detail="Solo SuperAdmins y Company Admins pueden tener alcance COMPANY.")
        if role_upper == "USER" and u_scope != "OWN":
            raise HTTPException(status_code=400, detail="Los usuarios estándar solo pueden tener alcance OWN.")
            
        u_is_sa = False
        u_is_admin = False
        u_company_id = data.company_id
        
        if is_sa and role_upper == "SUPERADMIN":
            u_is_sa = True
            u_is_admin = True
            u_company_id = None
            u_scope = "GLOBAL"
        elif role_upper == "COMPANY_ADMIN" or data.is_admin:
            u_is_sa = False
            u_is_admin = True
            role_upper = "COMPANY_ADMIN"
        else:
            u_is_sa = False
            u_is_admin = False
            role_upper = "USER"
            
        if role_upper != "SUPERADMIN" and u_company_id is None:
            raise HTTPException(status_code=400, detail="Debes asignar una empresa para roles no globales.")
            
        new_user = User(
            username=data.username,
            hashed_password=pwd_context.hash(data.password),
            nombre=data.nombre,
            company_id=u_company_id,
            email=data.email,
            is_admin=u_is_admin,
            is_superadmin=u_is_sa,
            role=role_upper,
            cases_view_scope=u_scope,
            is_active=True,
            sync_with_clickup=data.sync_with_clickup if data.sync_with_clickup is not None else True,
            clickup_api_token=data.clickup_api_token
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        # Log Audit
        log_audit_action(
            db=db,
            user_id=current_user.id,
            company_id=new_user.company_id,
            accion="CREATE_USER",
            entidad="User",
            entidad_id=new_user.id,
            request=request,
            metadata_val={"username": new_user.username, "role": new_user.role, "company_id": new_user.company_id}
        )
        
        return {
            "id": new_user.id,
            "username": new_user.username,
            "nombre": new_user.nombre,
            "company_id": new_user.company_id,
            "is_admin": new_user.is_admin,
            "is_superadmin": new_user.is_superadmin,
            "role": new_user.role,
            "cases_view_scope": new_user.cases_view_scope,
            "is_active": new_user.is_active,
            "sync_with_clickup": new_user.sync_with_clickup,
            "clickup_api_token": new_user.clickup_api_token
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        err_msg = f"ERROR in POST /admin/users: {str(e)} | TRACE: {traceback.format_exc()}"
        print(err_msg)
        raise HTTPException(status_code=400, detail=err_msg)

@app.put("/api/admin/users/{user_id}")
@app.put("/admin/users/{user_id}")
async def admin_update_user(
    user_id: int,
    data: UserAdminUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_superadmin)
):
    try:
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
            
        is_sa = is_global_superadmin(current_user)
        
        # Enforce Company Admin limitations
        if not is_sa:
            if user.company_id != current_user.company_id:
                raise HTTPException(status_code=403, detail="No tienes permisos para modificar este usuario.")
            if data.company_id is not None and data.company_id != current_user.company_id:
                raise HTTPException(status_code=400, detail="No puedes cambiar la empresa de este usuario.")
            if data.role is not None and data.role != "USER" and data.role != "STANDARD":
                raise HTTPException(status_code=400, detail="Solo puedes asignar el rol estándar (USER).")
            if data.cases_view_scope == "GLOBAL":
                raise HTTPException(status_code=400, detail="No puedes asignar alcance GLOBAL a usuarios de tu empresa.")
                
        # Self-modification safety guards
        if current_user.id == user.id:
            if data.is_active is False:
                raise HTTPException(status_code=400, detail="No puedes desactivar tu propio usuario.")
            if data.role is not None and data.role.upper() != "SUPERADMIN" and is_sa:
                raise HTTPException(status_code=400, detail="No puedes quitarte el rol de SUPERADMIN a ti mismo.")
                
        # Last active SuperAdmin protection guard
        u_is_sa = is_global_superadmin(user)
        if u_is_sa and user.is_active:
            will_deactivate = data.is_active is False
            will_change_role = (data.role is not None and data.role.upper() != "SUPERADMIN")
            if will_deactivate or will_change_role:
                sa_count = db.query(User).filter((User.role == "SUPERADMIN") | (User.is_superadmin == True), User.is_active == True).count()
                if sa_count <= 1:
                    raise HTTPException(status_code=400, detail="No puedes desactivar ni cambiar el rol del último SuperAdmin activo del sistema.")
                    
        # Apply changes
        changes = {}
        
        if data.username is not None and data.username != user.username:
            existing = db.query(User).filter(User.username == data.username).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"El usuario '{data.username}' ya existe.")
            changes["username"] = data.username
            user.username = data.username
            
        if data.nombre is not None:
            changes["nombre"] = data.nombre
            user.nombre = data.nombre
            
        if data.email is not None and data.email != user.email:
            existing = db.query(User).filter(User.email == data.email).first()
            if existing:
                raise HTTPException(status_code=400, detail=f"El correo '{data.email}' ya está registrado.")
            changes["email"] = data.email
            user.email = data.email
            
        if data.password:
            changes["password"] = "[MODIFICADA]"
            user.hashed_password = pwd_context.hash(data.password)
            
        if data.is_active is not None:
            changes["is_active"] = data.is_active
            user.is_active = data.is_active
            
        if data.cases_view_scope is not None:
            role_to_check = (data.role or user.role).upper()
            if data.cases_view_scope == "GLOBAL" and role_to_check != "SUPERADMIN":
                raise HTTPException(status_code=400, detail="Solo los SuperAdmins pueden tener alcance GLOBAL.")
            changes["cases_view_scope"] = data.cases_view_scope
            user.cases_view_scope = data.cases_view_scope
            
        if data.role is not None:
            role_upper = data.role.upper()
            if role_upper == "STANDARD":
                role_upper = "USER"
            
            changes["role"] = role_upper
            if role_upper == "SUPERADMIN":
                user.is_superadmin = True
                user.is_admin = True
                user.role = "SUPERADMIN"
                user.company_id = None
                user.cases_view_scope = "GLOBAL"
            elif role_upper == "COMPANY_ADMIN":
                user.is_superadmin = False
                user.is_admin = True
                user.role = "COMPANY_ADMIN"
                if user.cases_view_scope == "GLOBAL":
                    user.cases_view_scope = "COMPANY"
            else:
                user.is_superadmin = False
                user.is_admin = False
                user.role = "USER"
                if user.cases_view_scope == "GLOBAL":
                    user.cases_view_scope = "OWN"
                    
        # Apply company change if provided (and current_user is SuperAdmin)
        if data.company_id is not None and is_sa:
            if data.company_id == -1:
                user.company_id = None
                changes["company_id"] = None
            else:
                comp = db.query(Company).filter(Company.id == data.company_id).first()
                if not comp:
                    raise HTTPException(status_code=400, detail="La empresa no existe.")
                user.company_id = data.company_id
                changes["company_id"] = data.company_id
                user.is_superadmin = False
                if user.role == "SUPERADMIN":
                    user.role = "USER"
                    user.is_admin = False
                    user.cases_view_scope = "OWN"
                    
        # Enforce Scope & Role validation rules
        final_role = (user.role or "USER").upper()
        final_scope = (user.cases_view_scope or "OWN").upper()
        if final_role == "STANDARD":
            final_role = "USER"
        if final_scope == "GLOBAL" and final_role != "SUPERADMIN":
            raise HTTPException(status_code=400, detail="Solo los SuperAdmins pueden tener alcance GLOBAL.")
        if final_scope == "COMPANY" and final_role not in ["SUPERADMIN", "COMPANY_ADMIN"]:
            raise HTTPException(status_code=400, detail="Solo SuperAdmins y Company Admins pueden tener alcance COMPANY.")
        if final_role == "USER" and final_scope != "OWN":
            raise HTTPException(status_code=400, detail="Los usuarios estándar solo pueden tener alcance OWN.")

        if data.sync_with_clickup is not None:
            changes["sync_with_clickup"] = data.sync_with_clickup
            user.sync_with_clickup = data.sync_with_clickup
            
        if data.clickup_api_token is not None:
            changes["clickup_api_token"] = "[MODIFICADA]" if data.clickup_api_token else None
            user.clickup_api_token = data.clickup_api_token if data.clickup_api_token else None

        db.commit()
        db.refresh(user)
        
        # Log Audit
        if changes:
            actions_to_log = []
            if "is_active" in changes:
                actions_to_log.append("ACTIVATE_USER" if changes["is_active"] else "DEACTIVATE_USER")
            if "role" in changes:
                actions_to_log.append("CHANGE_ROLE")
            if "cases_view_scope" in changes:
                actions_to_log.append("CHANGE_CASES_VIEW_SCOPE")
            if "password" in changes:
                actions_to_log.append("CHANGE_PASSWORD_FROM_ADMIN")
            
            if not actions_to_log:
                actions_to_log.append("UPDATE_USER")
                
            for act in actions_to_log:
                log_audit_action(
                    db=db,
                    user_id=current_user.id,
                    company_id=user.company_id,
                    accion=act,
                    entidad="User",
                    entidad_id=user.id,
                    request=request,
                    metadata_val=changes
                )
            
        return {
            "ok": True,
            "user_id": user.id,
            "username": user.username,
            "nombre": user.nombre,
            "role": user.role,
            "company_id": user.company_id,
            "cases_view_scope": user.cases_view_scope,
            "is_active": user.is_active,
            "sync_with_clickup": user.sync_with_clickup,
            "clickup_api_token": user.clickup_api_token
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        err_msg = f"ERROR in PUT /admin/users/{user_id}: {str(e)} | TRACE: {traceback.format_exc()}"
        print(err_msg)
        raise HTTPException(status_code=400, detail=err_msg)


class CompanyUpdateRequest(BaseModel):
    nombre: Optional[str] = None
    nit: Optional[str] = None
    limite_usuarios: Optional[int] = None
    estado: Optional[str] = None
    payment_status: Optional[str] = None
    next_payment_due: Optional[str] = None
    billing_notes: Optional[str] = None

@app.put("/api/admin/companies/{company_id}")
@app.put("/admin/companies/{company_id}")
async def update_company(
    company_id: int,
    data: CompanyUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    try:
        comp = db.query(Company).filter(Company.id == company_id).first()
        if not comp:
            raise HTTPException(status_code=404, detail="Empresa no encontrada")
            
        changes = {}
        if data.nombre is not None:
            comp.nombre = data.nombre
            changes["nombre"] = data.nombre
        if data.nit is not None:
            comp.nit = data.nit
            changes["nit"] = data.nit
        if data.limite_usuarios is not None:
            comp.limite_usuarios = data.limite_usuarios
            changes["limite_usuarios"] = data.limite_usuarios
        if data.estado is not None:
            comp.estado = data.estado
            changes["estado"] = data.estado
        if data.payment_status is not None:
            comp.payment_status = data.payment_status
            changes["payment_status"] = data.payment_status
        if data.billing_notes is not None:
            comp.billing_notes = data.billing_notes
            changes["billing_notes"] = data.billing_notes
        if data.next_payment_due is not None:
            if data.next_payment_due == "":
                comp.next_payment_due = None
                changes["next_payment_due"] = None
            else:
                from datetime import datetime
                try:
                    comp.next_payment_due = datetime.strptime(data.next_payment_due, "%Y-%m-%d").date()
                    changes["next_payment_due"] = data.next_payment_due
                except:
                    raise HTTPException(status_code=400, detail="Formato de fecha inválido. Debe ser YYYY-MM-DD")
                    
        db.commit()
        db.refresh(comp)
        
        # Log Audit
        if changes:
            actions_to_log = []
            if "estado" in changes:
                state_val = changes["estado"]
                actions_to_log.append("CHANGE_COMPANY_STATUS")
                if state_val == "inactiva":
                    actions_to_log.append("INACTIVATE_COMPANY")
                elif state_val == "activo":
                    actions_to_log.append("REACTIVATE_COMPANY")
            if "payment_status" in changes:
                pay_val = changes["payment_status"]
                if pay_val == "en_mora":
                    actions_to_log.append("MARK_OVERDUE_COMPANY")
            
            if not actions_to_log:
                actions_to_log.append("UPDATE_COMPANY")
                
            for act in actions_to_log:
                log_audit_action(
                    db=db,
                    user_id=current_user.id,
                    company_id=comp.id,
                    accion=act,
                    entidad="Company",
                    entidad_id=comp.id,
                    request=request,
                    metadata_val=changes
                )
            
        return {
            "id": comp.id,
            "nombre": comp.nombre,
            "nit": comp.nit,
            "estado": comp.estado,
            "limite_usuarios": comp.limite_usuarios,
            "user_limit": comp.limite_usuarios,
            "payment_status": comp.payment_status,
            "next_payment_due": str(comp.next_payment_due) if comp.next_payment_due else None,
            "billing_notes": comp.billing_notes
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        err_msg = f"ERROR in PUT /admin/companies/{company_id}: {str(e)} | TRACE: {traceback.format_exc()}"
        print(err_msg)
        raise HTTPException(status_code=400, detail=err_msg)

class CompanySuspendRequest(BaseModel):
    reason: str
    notes: Optional[str] = None

class CompanyReactivateRequest(BaseModel):
    notes: Optional[str] = None

@app.post("/api/admin/companies/{company_id}/suspend")
@app.post("/admin/companies/{company_id}/suspend")
async def suspend_company(
    company_id: int,
    data: CompanySuspendRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    comp = db.query(Company).filter(Company.id == company_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
        
    comp.estado = "suspendida_pago"
    comp.payment_status = "suspendido"
    comp.suspended_at = datetime.utcnow()
    comp.suspended_by = current_user.id
    comp.suspension_reason = data.reason
    if data.notes:
        comp.billing_notes = data.notes
        
    db.commit()
    db.refresh(comp)
    
    # Log Audit
    log_audit_action(
        db=db,
        user_id=current_user.id,
        company_id=comp.id,
        accion="SUSPEND_COMPANY",
        entidad="Company",
        entidad_id=comp.id,
        request=request,
        metadata_val={"reason": data.reason, "notes": data.notes}
    )
    
    return {"ok": True, "message": "Empresa suspendida exitosamente."}

@app.post("/api/admin/companies/{company_id}/reactivate")
@app.post("/admin/companies/{company_id}/reactivate")
async def reactivate_company(
    company_id: int,
    data: CompanyReactivateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    comp = db.query(Company).filter(Company.id == company_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
        
    comp.estado = "activo"
    comp.payment_status = "al_dia"
    comp.reactivated_at = datetime.utcnow()
    comp.reactivated_by = current_user.id
    comp.last_payment_date = datetime.utcnow()
    if data.notes:
        comp.billing_notes = data.notes
        
    db.commit()
    db.refresh(comp)
    
    # Log Audit
    log_audit_action(
        db=db,
        user_id=current_user.id,
        company_id=comp.id,
        accion="REACTIVATE_COMPANY",
        entidad="Company",
        entidad_id=comp.id,
        request=request,
        metadata_val={"notes": data.notes}
    )
    
    return {"ok": True, "message": "Empresa reactivada exitosamente."}

@app.post("/api/admin/companies/{company_id}/mark-overdue")
@app.post("/admin/companies/{company_id}/mark-overdue")
async def mark_overdue_company(
    company_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    comp = db.query(Company).filter(Company.id == company_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Empresa no encontrada.")
        
    comp.payment_status = "en_mora"
    db.commit()
    db.refresh(comp)
    
    # Log Audit
    log_audit_action(
        db=db,
        user_id=current_user.id,
        company_id=comp.id,
        accion="MARK_OVERDUE_COMPANY",
        entidad="Company",
        entidad_id=comp.id,
        request=request
    )
    
    return {"ok": True, "message": "Empresa marcada en mora."}

# =========================
# MODULO SUPERADMIN: SIMULADOR DE FACTURACION
# =========================

@app.get("/api/admin/billing/tiers")
@app.get("/admin/billing/tiers")
async def get_billing_tiers(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    try:
        tiers = db.query(BillingTier).order_by(BillingTier.min_cases).all()
        
        # Seed inicial si no hay rangos
        if not tiers:
            seed = [
                BillingTier(min_cases=0, max_cases=500, price=3000.0),
                BillingTier(min_cases=501, max_cases=1000, price=2500.0),
                BillingTier(min_cases=1001, max_cases=None, price=2000.0),
            ]
            for s in seed:
                db.add(s)
            db.commit()
            tiers = db.query(BillingTier).order_by(BillingTier.min_cases).all()
        
        return {"ok": True, "tiers": [
            {"id": t.id, "min_cases": t.min_cases, "max_cases": t.max_cases, "price": t.price}
            for t in tiers
        ]}
    except Exception as e:
        import traceback
        err_msg = f"ERROR in GET /admin/billing/tiers: {str(e)} | TRACE: {traceback.format_exc()}"
        print(err_msg)
        raise HTTPException(status_code=400, detail=err_msg)

@app.post("/api/admin/billing/tiers")
@app.post("/admin/billing/tiers")
async def update_billing_tiers(
    request: Request,
    data: BillingTierUpdateList,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    try:
        # Delete all and recreate
        db.query(BillingTier).delete()
        
        for tier in data.tiers:
            db.add(BillingTier(
                min_cases=tier.min_cases,
                max_cases=tier.max_cases,
                price=tier.price
            ))
        db.commit()
        
        return {"ok": True, "message": "Rangos de facturación actualizados."}
    except Exception as e:
        import traceback
        err_msg = f"ERROR in POST /admin/billing/tiers: {str(e)} | TRACE: {traceback.format_exc()}"
        print(err_msg)
        raise HTTPException(status_code=400, detail=err_msg)

@app.get("/api/admin/billing/simulator")
@app.get("/admin/billing/simulator")
async def get_billing_simulator(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_superadmin)
):
    try:
        companies = db.query(Company).all()  # Allow simulation for all companies or active ones, wait, we can show all companies in simulation
        tiers = db.query(BillingTier).order_by(BillingTier.min_cases).all()
        if not tiers:
            seed = [
                BillingTier(min_cases=0, max_cases=500, price=3000.0),
                BillingTier(min_cases=501, max_cases=1000, price=2500.0),
                BillingTier(min_cases=1001, max_cases=None, price=2000.0),
            ]
            for s in seed:
                db.add(s)
            db.commit()
            tiers = db.query(BillingTier).order_by(BillingTier.min_cases).all()
            
        results = []
        total_active_cases = 0
        estimated_total = 0
        for comp in companies:
            users_count = db.query(User).filter(User.company_id == comp.id).count()
            active_cases = db.query(Case).filter(Case.company_id == comp.id, Case.is_active == True).count() 
            
            applicable_tier = None
            base_price = 0
            
            for tier in tiers:
                if active_cases >= tier.min_cases and (tier.max_cases is None or active_cases <= tier.max_cases):
                    applicable_tier = f"{tier.min_cases} - {tier.max_cases if tier.max_cases else 'Adelante'}"
                    base_price = tier.price
                    break
                    
            total_cost = active_cases * base_price
            results.append({
                "company_id": comp.id,
                "company_name": comp.nombre,
                "users_count": users_count,
                "active_cases": active_cases,
                "applicable_tier": applicable_tier or "Sin rango",
                "total_cost": total_cost
            })
            total_active_cases += active_cases
            estimated_total += total_cost
            
        return {
            "ok": True,
            "simulator": results, 
            "companies": results,
            "tiers": [{"id": t.id, "min_cases": t.min_cases, "max_cases": t.max_cases, "price": t.price} for t in tiers],
            "summary": {
                "total_companies": len(companies),
                "total_active_cases": total_active_cases,
                "estimated_total": estimated_total
            }
        }
    except Exception as e:
        import traceback
        err_msg = f"ERROR in GET /admin/billing/simulator: {str(e)} | TRACE: {traceback.format_exc()}"
        print(err_msg)
        raise HTTPException(status_code=400, detail=err_msg)

@app.get("/v1/system/health")
async def system_health_diagnostic(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Diagn?stico senior para detectar bloqueos y estado de base de datos."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403)
        
    case_count = db.query(Case).count()
    task_count = db.query(Task).count()
    id_proceso_count = db.query(Case).filter(Case.id_proceso.isnot(None)).count()
    
    # Probar conexi?n Rama Judicial (petici?n m?nima)
    rama_status = "OK"
    try:
        from backend.service.rama import _get
        await _get("/Procesos/Detalle/1") # ID ficticio pero v?lido para test
    except RamaRateLimitError:
        rama_status = "BLOQUEADO (403)"
    except Exception as e:
        rama_status = f"ERROR: {str(e)}"
        
    return {
        "version": "4.0.0-SENIOR",
        "database": {
            "cases": case_count,
            "tasks": task_count,
            "cases_synchronized": id_proceso_count
        },
        "integrations": {
            "rama_judicial": rama_status,
            "clickup": "Configurada" # Asumimos si el endpoint responde
        },
        "server_time": now_colombia()
    }

@app.get("/api/projects/tags")
@app.get("/projects/tags")
async def get_all_tags(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retorna todas las etiquetas del sistema."""
    return db.query(Tag).all()

@app.get("/api/projects/statuses")
@app.get("/projects/statuses")
async def get_all_statuses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Retorna todos los estados ?nicos usados en el sistema."""
    statuses = db.query(Task.status).filter(Task.status.isnot(None)).distinct().all()
    # Agregar estados base por defecto si no existen
    base_statuses = ['ABIERTO', 'TO DO', 'IN PROGRESS', 'PENDIENTE', 'ALMP', '468', 'NOT PERSONAL', 'LIQUIDACION', 'REMATE', 'COMPLETO', 'CLOSED']
    current_list = [s[0].upper() for s in statuses if s[0]]
    final_list = list(set(current_list + base_statuses))
    return sorted(final_list)


# =========================
# ADMIN PANEL (DJANGO-LIKE)
# =========================

class AdminAuth(AuthenticationBackend):
    async def login(self, request: Request) -> bool:
        form = await request.form()
        username, password = form.get("username"), form.get("password")
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.username == username).first()
            if user and _verify_password(password, user.hashed_password) and user.is_admin:
                request.session.update({"token": create_access_token(user.id)})
                return True
        finally:
            db.close()
        return False

    async def logout(self, request: Request) -> bool:
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> Optional[RedirectResponse]:
        token = request.session.get("token")
        if not token:
            return RedirectResponse(request.url_for("admin:login"))
        user_id = verify_access_token(token)
        if not user_id:
            return RedirectResponse(request.url_for("admin:login"))
        # Verificar si sigue siendo admin y activo
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.is_admin or not user.is_active:
                request.session.clear()
                return RedirectResponse(request.url_for("admin:login"))
        finally:
            db.close()
        return None

authentication_backend = AdminAuth(secret_key=secrets.token_urlsafe(32))
admin = Admin(app, engine, authentication_backend=authentication_backend, base_url="/admin", title="EMDECOB - Panel Admin")

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.username, User.nombre, User.email, User.is_admin, User.is_active]
    column_searchable_list = [User.username, User.nombre, User.email]
    column_filters = [User.is_admin, User.is_active]
    name = "Usuario"
    name_plural = "Usuarios"
    icon = "fa-solid fa-user"

class CaseAdmin(ModelView, model=Case):
    column_list = [Case.id, Case.radicado, Case.demandante, Case.demandado, Case.abogado]
    column_searchable_list = [Case.radicado, Case.demandante, Case.demandado, Case.abogado]
    column_filters = [Case.user_id]
    name = "Radicado"
    name_plural = "Radicados"
    icon = "fa-solid fa-folder-open"

class TaskAdmin(ModelView, model=Task):
    column_list = [Task.id, Task.title, Task.status, Task.priority, Task.due_date, Task.assignee_name]
    column_searchable_list = [Task.title, Task.status, Task.assignee_name]
    column_filters = [Task.status, Task.priority]
    name = "Tarea"
    name_plural = "Tareas"
    icon = "fa-solid fa-list-check"

class WorkspaceAdmin(ModelView, model=Workspace):
    column_list = [Workspace.id, Workspace.name, Workspace.visibility]
    name = "Espacio"
    name_plural = "Espacios"
    icon = "fa-solid fa-briefcase"

class IntegrationAdmin(ModelView, model=IntegrationConfig):
    column_list = [IntegrationConfig.id, IntegrationConfig.service_name, IntegrationConfig.is_active]
    name = "Integraci?n"
    name_plural = "Integraciones"
    icon = "fa-solid fa-plug"

admin.add_view(UserAdmin)
admin.add_view(CaseAdmin)
admin.add_view(TaskAdmin)
admin.add_view(WorkspaceAdmin)
admin.add_view(IntegrationAdmin)

# ============================================================
# TABLERO IA & ANALYTICS JURÍDICO
# ============================================================
class AIQueryRequest(BaseModel):
    query: Optional[str] = ""
    filter_key: Optional[str] = ""

@app.get("/api/ai/dashboard-stats")
@app.get("/ai/dashboard-stats")
def get_ai_stats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from backend.services.ai_analytics_service import get_company_ai_dashboard_stats
    is_sa = is_global_superadmin(current_user)
    return get_company_ai_dashboard_stats(db, current_user.company_id, is_superadmin=is_sa)

@app.post("/api/ai/query")
@app.post("/ai/query")
def post_ai_query(body: AIQueryRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from backend.services.ai_analytics_service import query_ai_processes
    is_sa = is_global_superadmin(current_user)
    return query_ai_processes(
        db,
        current_user.company_id,
        query_text=body.query or "",
        filter_key=body.filter_key or "",
        is_superadmin=is_sa
    )

# ============================================================
# SERVE REACT FRONTEND (must be LAST - catches all other routes)
# FastAPI serves static files so we don't need Nginx at all
# ============================================================
import os as _os
from fastapi.staticfiles import StaticFiles

_dist_path = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "dist")
if _os.path.exists(_dist_path):
    app.mount("/", StaticFiles(directory=_dist_path, html=True), name="spa")
    print(f"[STATIC] Sirviendo frontend React desde: {_dist_path}")
else:
    print(f"[STATIC] ADVERTENCIA: directorio dist no encontrado en {_dist_path}")

