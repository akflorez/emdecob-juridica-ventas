import requests
import json

# Let's test the sample from user's screenshot:
# Año: 26 or 2026
# Numero: 64018
# Tipo Documento: CC / CEDULA DE CIUDADANIA / 1
# Numero Documento: 1143957035

base_urls = [
    "https://apiexternotramites.sic.gov.co/consulta-externa/v1/radicados/anio/26/numeros/64018",
    "https://apiexternotramites.sic.gov.co/consulta-externa/v1/radicados/anio/2026/numeros/64018",
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://consultatramites.sic.gov.co",
    "Referer": "https://consultatramites.sic.gov.co/"
}

params_options = [
    {"tipoDocumento": "CC", "numeroDocumento": "1143957035"},
    {"tipoDocumento": "CEDULA DE CIUDADANIA", "numeroDocumento": "1143957035"},
    {"numeroDocumento": "1143957035"}
]

for url in base_urls:
    for params in params_options:
        try:
            r = requests.get(url, params=params, headers=headers, timeout=10)
            print(f"URL: {url} | params: {params} => status={r.status_code}")
            print(f"Response: {r.text[:300]}\n")
        except Exception as e:
            print(f"Error: {e}")
