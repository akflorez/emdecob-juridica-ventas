import requests
import time
import sys
from sqlalchemy import create_engine, text

sys.stdout.reconfigure(encoding='utf-8')

CAPSOLVER_API_KEY = "CAP-A9EC5C39CB189A4A8F023132ACDA7D269CA7972229D5B1FD86EB2354447EE429"
SIC_SITEKEY = "0x4AAAAAACGGiW1_wICMwND-"
SIC_PAGE_URL = "https://consultatramites.sic.gov.co/consulta-externa"

url_db = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url_db)

# Ver datos exactos en BD
with engine.connect() as conn:
    row = conn.execute(text("""
        SELECT id, radicado, cedula, demandante, id_proceso, juzgado
        FROM cases WHERE id = 2577
    """)).fetchone()
    print(f"BD → ID: {row.id}")
    print(f"BD → Radicado: '{row.radicado}'")
    print(f"BD → Cédula: '{row.cedula}'")
    print(f"BD → Demandante: '{row.demandante}'")
    print(f"BD → ID Proceso: '{row.id_proceso}'")

def get_token():
    res = requests.post("https://api.capsolver.com/createTask", json={
        "clientKey": CAPSOLVER_API_KEY,
        "task": {"type": "AntiTurnstileTaskProxyLess", "websiteURL": SIC_PAGE_URL, "websiteKey": SIC_SITEKEY}
    }, timeout=15).json()
    if res.get("errorId") != 0:
        return None
    task_id = res.get("taskId")
    for _ in range(20):
        time.sleep(2)
        val = requests.post("https://api.capsolver.com/getTaskResult", json={
            "clientKey": CAPSOLVER_API_KEY, "taskId": task_id
        }, timeout=10).json()
        if val.get("status") == "ready":
            return val.get("solution", {}).get("token")
        elif val.get("status") == "failed":
            return None
    return None

print("\n🔑 Obteniendo token...")
token = get_token()
if not token:
    print("❌ Sin token")
    sys.exit(1)
print(f"✅ Token OK\n")

headers = {
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://consultatramites.sic.gov.co",
    "Referer": "https://consultatramites.sic.gov.co/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "X-Turnstile-Token": token
}

CC = "1053786300"

# Probar distintas variantes del numero de radicado con anio 26
numeros_a_probar = [
    ("26", "231607"),
    ("26", "0231607"),
    ("2026", "231607"),
    ("26", "231607"),   # sin cedula
    ("26", "23160"),    # truncado
    ("26", "2316070"),  # con 0 al final
]

base = "https://apiexternotramites.sic.gov.co/consulta-externa/v1/radicados/anio/{anio}/numeros/{num}"

for anio, num in numeros_a_probar:
    url = base.format(anio=anio, num=num)
    # Con cedula
    r = requests.get(url, headers=headers, params={"tipoDocumento": "CC", "numeroDocumento": CC}, timeout=15)
    print(f"anio={anio} num={num} CC={CC} → HTTP {r.status_code} | {r.json().get('message','')[:60] if r.status_code!=200 else '✅ DATOS!'}")
    if r.status_code == 200 and r.json().get("success"):
        items = r.json()["data"].get("content", [])
        print(f"  🎉 {len(items)} actuaciones encontradas!")
        for i in items[:3]:
            print(f"     {i.get('fechaRadicado')} | {i.get('actuacionRadicado')}")
        break
    # Sin cedula
    r2 = requests.get(url, headers=headers, timeout=15)
    print(f"  Sin CC → HTTP {r2.status_code} | {r2.json().get('message','')[:60] if r2.status_code!=200 else '✅ DATOS!'}")
