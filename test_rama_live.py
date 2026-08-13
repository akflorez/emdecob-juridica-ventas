import requests
import json

radicados = [
    '63001400300320203997184',
    '17380408900420200562688',
    '63130400300120196251648',
    '76113408900120203755520',
    '73001418900220202188800'
]

print("=== CONSULTANDO RAMA JUDICIAL OFICIAL ===")
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*"
}

for rad in radicados:
    url = f"https://consultaprocesos.ramajudicial.gov.co:448/api/v2/Procesos/Consulta/NumeroRadicacion?numero={rad}&SoloActivos=false&pagina=1"
    try:
        r = requests.get(url, headers=headers, timeout=12)
        print(f"Radicado {rad}: status={r.status_code}")
        if r.status_code == 200:
            data = r.json()
            procesos = data.get("procesos", [])
            print(f"  Procesos encontrados: {len(procesos)}")
            for p in procesos:
                print(f"  -> Sujetos: {p.get('sujetosProcesales')} | Despacho: {p.get('despacho')}")
        else:
            print("  Respuesta:", r.text[:150])
    except Exception as e:
        print(f"  Error consultando {rad}: {e}")
