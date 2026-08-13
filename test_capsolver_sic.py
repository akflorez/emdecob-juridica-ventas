import requests
import time
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

API_KEY = "CAP-A9EC5C39CB189A4A8F023132ACDA7D269CA7972229D5B1FD86EB2354447EE429"
SIC_SITEKEY = "0x4AAAAAACGGiW1_wICMwND-"
SIC_PAGE_URL = "https://consultatramites.sic.gov.co/consulta-externa"

def get_capsolver_token():
    print("🔑 Solicitando token Turnstile a CapSolver...")
    url = "https://api.capsolver.com/createTask"
    payload = {
        "clientKey": API_KEY,
        "task": {
            "type": "AntiTurnstileTaskProxyLess",
            "websiteURL": SIC_PAGE_URL,
            "websiteKey": SIC_SITEKEY
        }
    }
    res = requests.post(url, json=payload, timeout=15)
    data = res.json()
    print(f"  CreateTask response: {json.dumps(data, indent=2)}")
    
    if data.get("errorId") != 0:
        print(f"❌ Error CapSolver: {data.get('errorDescription')}")
        return None
    
    task_id = data.get("taskId")
    print(f"  Task ID: {task_id}")
    print("  Esperando resultado...")
    
    for i in range(20):
        time.sleep(2)
        res2 = requests.post("https://api.capsolver.com/getTaskResult", json={
            "clientKey": API_KEY,
            "taskId": task_id
        }, timeout=10)
        res_data = res2.json()
        status = res_data.get("status")
        print(f"  [{i+1}] Status: {status}")
        
        if status == "ready":
            token = res_data.get("solution", {}).get("token")
            print(f"✅ ¡TOKEN OBTENIDO EXITOSAMENTE! {token[:40]}...")
            return token
        elif status == "failed":
            print(f"❌ Task failed: {res_data}")
            return None
    
    print("⏰ Timeout esperando token")
    return None

def test_sic_with_token(token, anio, numero, cc):
    print(f"\n🌐 Consultando SIC API para {anio}-{numero}...")
    api_url = f"https://apiexternotramites.sic.gov.co/consulta-externa/v1/radicados/anio/{anio}/numeros/{numero}?tipoDocumento=CC&numeroDocumento={cc}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://consultatramites.sic.gov.co",
        "Referer": "https://consultatramites.sic.gov.co/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "X-Turnstile-Token": token
    }
    
    r = requests.get(api_url, headers=headers, timeout=15)
    print(f"  HTTP Status: {r.status_code}")
    data = r.json()
    
    if data.get("success") and data.get("data"):
        content = data["data"].get("content", [])
        print(f"🎉 ¡ÉXITO TOTAL! {len(content)} ACTUACIONES REALES OBTENIDAS DE LA SIC!")
        for idx, item in enumerate(content):
            print(f"   [{idx+1}] {item.get('fechaRadicado')} | {item.get('actuacionRadicado')}")
        return content
    else:
        print(f"❌ Sin datos: {json.dumps(data, indent=2)[:300]}")
        return []

if __name__ == "__main__":
    token = get_capsolver_token()
    if token:
        # Test con caso 26-231607 (CC 1053786300)
        test_sic_with_token(token, "26", "231607", "1053786300")
