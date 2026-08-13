import requests
import time
import json
import hashlib
import sys
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding='utf-8')

CAPSOLVER_API_KEY = "CAP-A9EC5C39CB189A4A8F023132ACDA7D269CA7972229D5B1FD86EB2354447EE429"
SIC_SITEKEY = "0x4AAAAAACGGiW1_wICMwND-"
SIC_PAGE_URL = "https://consultatramites.sic.gov.co/consulta-externa"

url_db = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url_db)

def sha256_obj(obj):
    raw = json.dumps(obj, sort_keys=True, default=str).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def get_capsolver_token():
    res = requests.post("https://api.capsolver.com/createTask", json={
        "clientKey": CAPSOLVER_API_KEY,
        "task": {
            "type": "AntiTurnstileTaskProxyLess",
            "websiteURL": SIC_PAGE_URL,
            "websiteKey": SIC_SITEKEY
        }
    }, timeout=15).json()
    
    if res.get("errorId") != 0:
        print(f"  ❌ CapSolver error: {res.get('errorDescription')}")
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
            return None
    return None

def parse_fecha(raw):
    if not raw:
        return ""
    raw = str(raw).strip().split()[0]
    if "/" in raw:
        parts = raw.split("/")
        if len(parts) == 3:
            if len(parts[2]) == 4:
                return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
            else:
                return f"20{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    if "-" in raw and len(raw) >= 10:
        return raw[:10]
    return raw

def fetch_and_save(case_id, radicado, anio, numero, cedula, comp_id):
    print(f"\n{'='*55}")
    print(f"🔄 Procesando: {radicado} (ID {case_id}) CC={cedula}")
    print(f"{'='*55}")

    print("  🔑 Obteniendo token Turnstile de CapSolver...")
    token = get_capsolver_token()
    if not token:
        print("  ❌ No se pudo obtener token")
        return 0

    print(f"  ✅ Token obtenido: {token[:30]}...")

    api_url = f"https://apiexternotramites.sic.gov.co/consulta-externa/v1/radicados/anio/{anio}/numeros/{numero}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://consultatramites.sic.gov.co",
        "Referer": "https://consultatramites.sic.gov.co/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
        "X-Turnstile-Token": token
    }
    
    params = {}
    if cedula:
        params = {"tipoDocumento": "CC", "numeroDocumento": cedula}

    r = requests.get(api_url, headers=headers, params=params, timeout=15)
    print(f"  HTTP {r.status_code}")
    
    if r.status_code != 200:
        print(f"  ⚠️ Respuesta: {r.text[:200]}")
        return 0

    data = r.json()
    if not data.get("success") or not data.get("data"):
        print(f"  ⚠️ Sin datos: {data.get('message', '')}")
        return 0

    items = data["data"].get("content", [])
    print(f"  🎉 ¡{len(items)} ACTUACIONES REALES OBTENIDAS!")

    acts = []
    for item in items:
        raw_fecha = str(item.get("fechaRadicado") or item.get("fecha") or "").strip()
        fecha_str = parse_fecha(raw_fecha)
        act_title = (item.get("actuacionRadicado") or item.get("actuacion") or "Actuación SIC").strip()
        tramite = (item.get("tramiteRadicado") or item.get("tramite") or "DEMANDA PROTECCIÓN CONSUMIDOR").strip()
        solicitante = (item.get("solicitanteDestinatario") or item.get("solicitante") or "").strip()
        tipo = (item.get("tipoRadicado") or item.get("tipo") or "").strip()
        anot_parts = [f"Trámite: {tramite}"]
        if tipo: anot_parts.append(f"Tipo: {tipo}")
        if solicitante: anot_parts.append(f"Sujeto: {solicitante}")
        acts.append({"fecha": fecha_str, "title": act_title, "detail": " | ".join(anot_parts)})

    acts.sort(key=lambda x: x["fecha"], reverse=True)

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM case_events WHERE case_id = :cid"), {"cid": case_id})
        for a in acts:
            ev_hash = sha256_obj(a)
            conn.execute(text("""
                INSERT INTO case_events (case_id, company_id, event_date, title, detail, event_hash, con_documentos)
                VALUES (:cid, :comp, :date, :title, :detail, :hash, false)
                ON CONFLICT (case_id, event_hash) DO NOTHING
            """), {"cid": case_id, "comp": comp_id, "date": a["fecha"], "title": a["title"], "detail": a["detail"], "hash": ev_hash})
        
        if acts:
            conn.execute(text("""
                UPDATE cases SET ultima_actuacion=:newest, fecha_radicacion=:oldest,
                has_documents=false, is_active=true, last_check_at=NOW() WHERE id=:cid
            """), {"newest": acts[0]["fecha"], "oldest": acts[-1]["fecha"], "cid": case_id})
        conn.commit()

    print(f"  ✨ ¡{len(acts)} actuaciones guardadas en PostgreSQL!")
    for idx, a in enumerate(acts[:3]):
        print(f"     [{idx+1}] {a['fecha']} | {a['title']}")
    return len(acts)

if __name__ == "__main__":
    with engine.connect() as conn:
        cases = conn.execute(text("""
            SELECT id, radicado, cedula, company_id
            FROM cases
            WHERE juzgado ILIKE '%SIC%' OR fuente_encontrado ILIKE '%SIC%'
               OR radicado ~ '^(24|25|26)-'
            ORDER BY id ASC
        """)).fetchall()

    print(f"🚀 Barrido automático CapSolver para {len(cases)} casos de la SIC\n")
    
    total_ok = 0
    for c in cases:
        rad = c.radicado or ""
        parts = rad.split("-") if "-" in rad else []
        if len(parts) < 2:
            print(f"⚠️ Radicado inválido: {rad}")
            continue
        anio = parts[0]
        numero = parts[1]
        cedula = str(c.cedula or "").replace(".0","").strip() if c.cedula else ""
        
        n = fetch_and_save(c.id, rad, anio, numero, cedula, c.company_id or 3)
        if n > 0:
            total_ok += 1
        time.sleep(3)  # pausa entre consultas

    print(f"\n{'='*55}")
    print(f"✨ BARRIDO COMPLETO: {total_ok}/{len(cases)} casos actualizados con actuaciones reales de la SIC")
    print(f"{'='*55}")
