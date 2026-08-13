import requests
from bs4 import BeautifulSoup
import re

url = "https://consultatramites.sic.gov.co/consulta-externa"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

r = requests.get(url, headers=headers)
soup = BeautifulSoup(r.text, 'html.parser')

scripts = [s.get('src') for s in soup.find_all('script') if s.get('src')]
print("Scripts found:", scripts)

for s in scripts:
    script_url = f"https://consultatramites.sic.gov.co/{s.lstrip('/')}"
    try:
        sr = requests.get(script_url, headers=headers)
        print(f"\nAnalyzing script: {script_url} (length: {len(sr.text)})")
        
        # Search for API URLs, endpoint paths, or service URLs
        endpoints = re.findall(r'["\'](https?://[^"\']+|/[a-zA-Z0-9_\-\/]+(?:api|consulta|tramite|radicado)[^"\']*)["\']', sr.text)
        print(f"Endpoints found in {s}:")
        for ep in set(endpoints[:30]):
            print("  *", ep)
    except Exception as e:
        print(f"Error fetching script {s}: {e}")
