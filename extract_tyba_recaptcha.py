import requests
from bs4 import BeautifulSoup
import re
import urllib3
urllib3.disable_warnings()

url = "https://procesojudicial.ramajudicial.gov.co/Justicia21/Administracion/Ciudadanos/frmConsulta.aspx?opcion=consulta"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

r = requests.get(url, headers=headers, verify=False)
text = r.text

print("Searching for reCAPTCHA sitekey or scripts...")
matches = re.findall(r'(?:grecaptcha|recaptcha|sitekey|render)[^\n;]*', text, re.IGNORECASE)
for m in matches[:15]:
    print("  *", m)

sitekeys = re.findall(r'["\'](6L[a-zA-Z0-9_-]{38})["\']', text)
print("Sitekeys found:", set(sitekeys))
