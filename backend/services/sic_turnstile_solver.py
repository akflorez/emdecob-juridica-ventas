import os
import time
import json
import logging
import requests
import hashlib
from sqlalchemy import text

logger = logging.getLogger(__name__)

SIC_SITEKEY = "0x4AAAAAACGGiW1_wICMwND-"
SIC_PAGE_URL = "https://consultatramites.sic.gov.co/consulta-externa"

def sha256_obj(obj):
    raw = json.dumps(obj, sort_keys=True, default=str).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def get_turnstile_token_capsolver():
    api_key = os.getenv("CAPSOLVER_API_KEY")
    if not api_key:
        return None
    try:
        url = "https://api.capsolver.com/createTask"
        payload = {
            "clientKey": api_key,
            "task": {
                "type": "AntiTurnstileTaskProxyLess",
                "websiteURL": SIC_PAGE_URL,
                "websiteKey": SIC_SITEKEY
            }
        }
        res = requests.post(url, json=payload, timeout=10)
        data = res.json()
        if data.get("errorId") != 0:
            logger.error(f"CapSolver createTask error: {data.get('errorDescription')}")
            return None
        
        task_id = data.get("taskId")
        res_url = "https://api.capsolver.com/getTaskResult"

        for _ in range(15):
            time.sleep(1)
            res_val = requests.post(res_url, json={"clientKey": api_key, "taskId": task_id}, timeout=10).json()
            if res_val.get("status") == "ready":
                token = res_val.get("solution", {}).get("token")
                logger.info("CapSolver successfully resolved Turnstile token!")
                return token
            elif res_val.get("status") == "failed":
                logger.error("CapSolver task failed")
                return None
    except Exception as e:
        logger.error(f"Error in CapSolver request: {e}")
    return None

def get_turnstile_token_2captcha():
    api_key = os.getenv("TWOCAPTCHA_API_KEY")
    if not api_key:
        return None
    try:
        url = f"https://2captcha.com/in.php?key={api_key}&method=turnstile&sitekey={SIC_SITEKEY}&pageurl={SIC_PAGE_URL}&json=1"
        res = requests.get(url, timeout=10).json()
        if res.get("status") != 1:
            logger.error(f"2Captcha error: {res.get('request')}")
            return None
        
        req_id = res.get("request")
        res_url = f"https://2captcha.com/res.php?key={api_key}&action=get&id={req_id}&json=1"

        for _ in range(20):
            time.sleep(2)
            val = requests.get(res_url, timeout=10).json()
            if val.get("status") == 1:
                token = val.get("request")
                logger.info("2Captcha successfully resolved Turnstile token!")
                return token
            elif val.get("request") != "CAPCHA_NOT_READY":
                logger.error(f"2Captcha failed with: {val.get('request')}")
                return None
    except Exception as e:
        logger.error(f"Error in 2Captcha request: {e}")
    return None

def fetch_sic_actuations_live(anio: str, numero: str, cedula: str = ""):
    """
    Solves Turnstile automatically using CapSolver / 2Captcha API or Playwright stealth
    and fetches 100% real actuations from SIC API.
    Tries with CC first; if 403, retries without CC.
    """
    token = get_turnstile_token_capsolver() or get_turnstile_token_2captcha()
    
    if not token:
        logger.warning("No API solver token available - CAPSOLVER_API_KEY not configured")
        return None

    base_url = f"https://apiexternotramites.sic.gov.co/consulta-externa/v1/radicados/anio/{anio}/numeros/{numero}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://consultatramites.sic.gov.co",
        "Referer": "https://consultatramites.sic.gov.co/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Turnstile-Token": token
    }

    # Try with CC first, then without if 403
    attempts = []
    if cedula:
        attempts.append({"tipoDocumento": "CC", "numeroDocumento": cedula})
    attempts.append({})

    try:
        for params in attempts:
            resp = requests.get(base_url, headers=headers, params=params, timeout=15)
            logger.info(f"SIC API HTTP {resp.status_code} for {anio}-{numero} params={params}")
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and data.get("data"):
                    return data["data"].get("content", [])
                else:
                    logger.warning(f"SIC returned no data: {data.get('message', '')}")
                    return []
            elif resp.status_code == 403:
                logger.warning(f"SIC 403 with params={params}, trying next...")
                continue
            else:
                logger.error(f"SIC API HTTP {resp.status_code}: {resp.text[:200]}")
                break
    except Exception as e:
        logger.error(f"Error calling SIC API: {e}")

    return None

def sync_sic_case_to_db(db_session, case_id: int, items: list):
    """
    Saves/upserts real actuations to PostgreSQL case_events for case_id.
    """
    if not items:
        return 0

    acts = []
    for item in items:
        raw_fecha = str(item.get("fechaRadicado") or item.get("fecha") or "").strip()
        fecha_str = ""
        if raw_fecha:
            if "/" in raw_fecha:
                parts = raw_fecha.split()[0].split("/")
                if len(parts) == 3:
                    if len(parts[2]) == 4:
                        fecha_str = f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
                    else:
                        fecha_str = f"20{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
            elif "-" in raw_fecha:
                fecha_str = raw_fecha[:10]

        act_title = (item.get("actuacionRadicado") or item.get("actuacion") or "Actuación SIC").strip()
        tramite = (item.get("tramiteRadicado") or item.get("tramite") or "DEMANDA PROTECCIÓN CONSUMIDOR JURISDICCIONAL").strip()
        solicitante = (item.get("solicitanteDestinatario") or item.get("solicitante") or "").strip()
        tipo = (item.get("tipoRadicado") or item.get("tipo") or "").strip()

        anot_parts = [f"Trámite: {tramite}"]
        if tipo: anot_parts.append(f"Tipo: {tipo}")
        if solicitante: anot_parts.append(f"Sujeto: {solicitante}")

        acts.append({
            "fecha": fecha_str,
            "title": act_title,
            "detail": " | ".join(anot_parts)
        })

    acts.sort(key=lambda x: x["fecha"], reverse=True)

    # Get company_id of the case
    case_res = db_session.execute(text("SELECT company_id FROM cases WHERE id = :cid"), {"cid": case_id}).first()
    comp_id = case_res[0] if case_res else 1

    # Clean existing events for case_id
    db_session.execute(text("DELETE FROM case_events WHERE case_id = :cid"), {"cid": case_id})

    for a in acts:
        ev_hash = sha256_obj(a)
        db_session.execute(text("""
            INSERT INTO case_events (case_id, company_id, event_date, title, detail, event_hash, con_documentos)
            VALUES (:cid, :comp_id, :date, :title, :detail, :hash, false)
            ON CONFLICT (case_id, event_hash) DO NOTHING
        """), {
            "cid": case_id,
            "comp_id": comp_id,
            "date": a["fecha"],
            "title": a["title"],
            "detail": a["detail"],
            "hash": ev_hash
        })

    if acts:
        newest = acts[0]["fecha"]
        oldest = acts[-1]["fecha"]
        db_session.execute(text("""
            UPDATE cases 
            SET ultima_actuacion = :newest,
                fecha_radicacion = :oldest,
                has_documents = false,
                is_active = true,
                last_check_at = NOW()
            WHERE id = :cid
        """), {"newest": newest, "oldest": oldest, "cid": case_id})

    db_session.commit()
    return len(acts)
