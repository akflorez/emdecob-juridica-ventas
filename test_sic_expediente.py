import requests
import json

base_url = "https://apiexternotramites.sic.gov.co/consulta-externa/v1/radicados"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://consultatramites.sic.gov.co",
    "Referer": "https://consultatramites.sic.gov.co/"
}

# Testing consecutive 0, 1, 2, 3, 4 for radicado 26-64018
for consecutivo in [0, 1, 2, 3, 4]:
    url = f"{base_url}/anio/26/numeros/64018/consecutivos/{consecutivo}/expediente"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        print(f"URL: {url} => status={r.status_code}")
        print(f"Response: {r.text[:300]}\n")
    except Exception as e:
        print(f"Error {url}: {e}")
