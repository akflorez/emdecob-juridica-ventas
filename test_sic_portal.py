import requests
import json

url = "https://consultatramites.sic.gov.co/consulta-externa"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

try:
    r = requests.get(url, headers=headers, timeout=10)
    print(f"Status: {r.status_code}")
    print("Headers:", dict(r.headers))
    print("\nPage HTML snippet (first 1000 chars):")
    print(r.text[:1000])
except Exception as e:
    print("Error:", e)
