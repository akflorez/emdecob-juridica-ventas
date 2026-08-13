import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

url = "https://procesojudicial.ramajudicial.gov.co/Justicia21/Administracion/Ciudadanos/frmConsulta.aspx?opcion=consulta"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Origin": "https://procesojudicial.ramajudicial.gov.co",
    "Referer": url
}

s = requests.Session()
r_get = s.get(url, headers=headers, verify=False, timeout=15)
soup = BeautifulSoup(r_get.text, 'html.parser')

viewstate = soup.find('input', {'id': '__VIEWSTATE'})['value'] if soup.find('input', {'id': '__VIEWSTATE'}) else ''
eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'})['value'] if soup.find('input', {'id': '__EVENTVALIDATION'}) else ''
viewstategen = soup.find('input', {'id': '__VIEWSTATEGENERATOR'})['value'] if soup.find('input', {'id': '__VIEWSTATEGENERATOR'}) else ''

print(f"ViewState length: {len(viewstate)}")
print(f"EventValidation length: {len(eventvalidation)}")

# Test with a radicado from Rama Judicial
test_radicado = "76001400301420250120900"

payload = {
    "__VIEWSTATE": viewstate,
    "__VIEWSTATEGENERATOR": viewstategen,
    "__EVENTVALIDATION": eventvalidation,
    "__EVENTTARGET": "",
    "__EVENTARGUMENT": "",
    "ctl00$MainContent$txttp": "1",
    "ctl00$MainContent$txtCodigoProceso": test_radicado,
    "ctl00$MainContent$btnConsultar": "Consultar",
    "recaptchaResponse": ""
}

r_post = s.post(url, data=payload, headers=headers, verify=False, timeout=15)
print(f"POST Status: {r_post.status_code}")
print(f"POST Response Length: {len(r_post.text)}")

soup_res = BeautifulSoup(r_post.text, 'html.parser')
tables = soup_res.find_all('table')
print(f"Tables in response: {len(tables)}")

# Check for table rows or results
for i, t in enumerate(tables):
    rows = t.find_all('tr')
    print(f"  Table {i}: {len(rows)} rows")
    for r in rows[:5]:
        print("   Row:", r.get_text(separator=' | ', strip=True)[:150])

# Check if there is any error alert or message
alerts = soup_res.find_all(class_=lambda x: x and ('alert' in x or 'error' in x or 'msg' in x))
for a in alerts:
    print("Alert:", a.get_text(strip=True))
