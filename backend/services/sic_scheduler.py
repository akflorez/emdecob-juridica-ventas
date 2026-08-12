"""
Scheduler diario para consultar actuaciones de casos SIC usando CapSolver.
Se ejecuta todos los días a las 9:00 AM (hora Colombia / America/Bogota).
Solo consume 1 token de CapSolver por caso consultado (~15 tokens/día).
"""
import asyncio
import logging
import time
import json
import hashlib
import os
import requests
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

CAPSOLVER_API_KEY = os.getenv("CAPSOLVER_API_KEY", "")
SIC_SITEKEY = "0x4AAAAAACGGiW1_wICMwND-"
SIC_PAGE_URL = "https://consultatramites.sic.gov.co/consulta-externa"
BOGOTA_TZ = pytz.timezone("America/Bogota")


def sha256_obj(obj):
    raw = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def get_capsolver_token() -> str | None:
    if not CAPSOLVER_API_KEY:
        logger.warning("[SIC-SCHEDULER] CAPSOLVER_API_KEY no configurada")
        return None
    try:
        res = requests.post("https://api.capsolver.com/createTask", json={
            "clientKey": CAPSOLVER_API_KEY,
            "task": {
                "type": "AntiTurnstileTaskProxyLess",
                "websiteURL": SIC_PAGE_URL,
                "websiteKey": SIC_SITEKEY
            }
        }, timeout=15).json()

        if res.get("errorId") != 0:
            logger.error(f"[SIC-SCHEDULER] CapSolver error: {res.get('errorDescription')}")
            return None

        task_id = res.get("taskId")
        for _ in range(20):
            time.sleep(2)
            val = requests.post("https://api.capsolver.com/getTaskResult", json={
                "clientKey": CAPSOLVER_API_KEY,
                "taskId": task_id
            }, timeout=10).json()
            if val.get("status") == "ready":
                return val.get("solution", {}).get("token")
            elif val.get("status") == "failed":
                logger.error("[SIC-SCHEDULER] CapSolver task failed")
                return None
    except Exception as e:
        logger.error(f"[SIC-SCHEDULER] Error CapSolver: {e}")
    return None


def parse_fecha(raw: str) -> str:
    if not raw:
        return ""
    raw = str(raw).strip().split()[0]
    if "/" in raw:
        parts = raw.split("/")
        if len(parts) == 3:
            year = parts[2] if len(parts[2]) == 4 else f"20{parts[2]}"
            return f"{year}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    if "-" in raw and len(raw) >= 10:
        return raw[:10]
    return raw


def fetch_sic_case(anio: str, numero: str, cedula: str = "") -> list | None:
    token = get_capsolver_token()
    if not token:
        return None

    base_url = f"https://apiexternotramites.sic.gov.co/consulta-externa/v1/radicados/anio/{anio}/numeros/{numero}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://consultatramites.sic.gov.co",
        "Referer": "https://consultatramites.sic.gov.co/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "X-Turnstile-Token": token
    }

    attempts = []
    if cedula:
        attempts.append({"tipoDocumento": "CC", "numeroDocumento": cedula})
    attempts.append({})

    try:
        for params in attempts:
            resp = requests.get(base_url, headers=headers, params=params, timeout=15)
            logger.info(f"[SIC-SCHEDULER] HTTP {resp.status_code} para {anio}-{numero}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("data"):
                    return data["data"].get("content", [])
                return []
            elif resp.status_code == 403:
                continue
    except Exception as e:
        logger.error(f"[SIC-SCHEDULER] Error consultando SIC: {e}")
    return None


def save_sic_actuations(engine, case_id: int, comp_id: int, items: list) -> int:
    from sqlalchemy import text

    acts = []
    for item in items:
        raw_fecha = str(item.get("fechaRadicado") or item.get("fecha") or "").strip()
        fecha_str = parse_fecha(raw_fecha)
        act_title = (item.get("actuacionRadicado") or item.get("actuacion") or "Actuación SIC").strip()
        tramite = (item.get("tramiteRadicado") or item.get("tramite") or "DEMANDA PROTECCIÓN CONSUMIDOR").strip()
        solicitante = (item.get("solicitanteDestinatario") or item.get("solicitante") or "").strip()
        tipo = (item.get("tipoRadicado") or item.get("tipo") or "").strip()

        anot_parts = [f"Trámite: {tramite}"]
        if tipo:
            anot_parts.append(f"Tipo: {tipo}")
        if solicitante:
            anot_parts.append(f"Sujeto: {solicitante}")

        acts.append({
            "fecha": fecha_str,
            "title": act_title,
            "detail": " | ".join(anot_parts)
        })

    acts.sort(key=lambda x: x["fecha"], reverse=True)

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM case_events WHERE case_id = :cid"), {"cid": case_id})
        for a in acts:
            ev_hash = sha256_obj(a)
            conn.execute(text("""
                INSERT INTO case_events (case_id, company_id, event_date, title, detail, event_hash, con_documentos)
                VALUES (:cid, :comp, :date, :title, :detail, :hash, false)
                ON CONFLICT (case_id, event_hash) DO NOTHING
            """), {"cid": case_id, "comp": comp_id, "date": a["fecha"],
                   "title": a["title"], "detail": a["detail"], "hash": ev_hash})

        if acts:
            conn.execute(text("""
                UPDATE cases SET ultima_actuacion=:newest, fecha_radicacion=:oldest,
                has_documents=false, is_active=true, last_check_at=NOW() WHERE id=:cid
            """), {"newest": acts[0]["fecha"], "oldest": acts[-1]["fecha"], "cid": case_id})
        conn.commit()

    return len(acts)


def run_sic_daily_sweep(engine):
    """Consulta todos los casos SIC y actualiza sus actuaciones."""
    from sqlalchemy import text

    logger.info("[SIC-SCHEDULER] ⏰ Iniciando barrido diario SIC (9 AM)...")

    with engine.connect() as conn:
        cases = conn.execute(text("""
            SELECT id, radicado, cedula, company_id
            FROM cases
            WHERE juzgado ILIKE '%SIC%' OR fuente_encontrado ILIKE '%SIC%'
               OR radicado ~ '^(24|25|26)-'
            ORDER BY id ASC
        """)).fetchall()

    logger.info(f"[SIC-SCHEDULER] {len(cases)} casos SIC encontrados")
    total_ok = 0

    for c in cases:
        rad = c.radicado or ""
        parts = rad.split("-") if "-" in rad else []
        if len(parts) < 2:
            continue

        anio = parts[0]
        numero = parts[1]
        cedula = str(c.cedula or "").replace(".0", "").strip()

        try:
            logger.info(f"[SIC-SCHEDULER] Consultando {rad}...")
            items = fetch_sic_case(anio, numero, cedula)
            if items is not None:
                n = save_sic_actuations(engine, c.id, c.company_id or 3, items)
                logger.info(f"[SIC-SCHEDULER] ✅ {rad}: {n} actuaciones guardadas")
                total_ok += 1
            else:
                logger.warning(f"[SIC-SCHEDULER] ⚠️ {rad}: no se obtuvieron datos")
        except Exception as e:
            logger.error(f"[SIC-SCHEDULER] ❌ Error en {rad}: {e}")

        time.sleep(3)  # Pausa entre casos para no sobrecargar la SIC

    logger.info(f"[SIC-SCHEDULER] ✨ Barrido completo: {total_ok}/{len(cases)} casos actualizados")


async def sic_daily_scheduler_loop(engine):
    """
    Bucle asíncrono que espera hasta las 9:00 AM Bogotá y ejecuta el barrido SIC.
    Corre indefinidamente cada 24h.
    """
    logger.info("[SIC-SCHEDULER] Programador diario SIC iniciado (9:00 AM hora Colombia)")

    while True:
        try:
            now = datetime.now(BOGOTA_TZ)
            # Calcular próximas 9:00 AM
            target = now.replace(hour=9, minute=0, second=0, microsecond=0)
            if now >= target:
                # Si ya pasaron las 9 AM de hoy, esperar hasta mañana
                from datetime import timedelta
                target = target + timedelta(days=1)

            wait_seconds = (target - now).total_seconds()
            logger.info(f"[SIC-SCHEDULER] Próxima consulta SIC en {wait_seconds/3600:.1f} horas ({target.strftime('%Y-%m-%d %H:%M')} Bogotá)")

            await asyncio.sleep(wait_seconds)

            # Ejecutar en thread separado para no bloquear el event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, run_sic_daily_sweep, engine)

        except asyncio.CancelledError:
            logger.info("[SIC-SCHEDULER] Programador SIC detenido")
            break
        except Exception as e:
            logger.error(f"[SIC-SCHEDULER] Error en el ciclo del scheduler: {e}")
            await asyncio.sleep(3600)  # Reintentar en 1 hora si hay error
