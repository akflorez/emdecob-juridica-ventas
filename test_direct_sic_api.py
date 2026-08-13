import requests
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = "https://apiexternotramites.sic.gov.co/consulta-externa/v1/radicados/anio/25/numeros/107449?tipoDocumento=CC&numeroDocumento=1004826465"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://consultatramites.sic.gov.co",
    "Referer": "https://consultatramites.sic.gov.co/"
}

res = requests.get(url, headers=headers)
print("HTTP Status:", res.status_code)
print("Response Body:", res.text[:500])
