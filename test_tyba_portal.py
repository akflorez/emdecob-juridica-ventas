import requests
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

url = "https://procesojudicial.ramajudicial.gov.co/Justicia21/Administracion/Ciudadanos/frmConsulta.aspx?opcion=consulta"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9"
}

try:
    s = requests.Session()
    r = s.get(url, headers=headers, verify=False, timeout=15)
    print(f"Status: {r.status_code}")
    print("Cookies:", s.cookies.get_dict())
    
    soup = BeautifulSoup(r.text, 'html.parser')
    forms = soup.find_all('form')
    print(f"Forms found: {len(forms)}")
    
    inputs = soup.find_all(['input', 'select', 'button'])
    print(f"Inputs found: {len(inputs)}")
    for inp in inputs:
        name = inp.get('name') or inp.get('id')
        inp_type = inp.get('type')
        val = inp.get('value', '')
        if name and not name.startswith('__VIEWSTATE'):
            print(f"  Input: {name} (type={inp_type}, value={val[:30] if val else ''})")
            
    # Also check if there are scripts or API calls
    scripts = soup.find_all('script')
    for sc in scripts:
        src = sc.get('src')
        if src:
            print("  Script src:", src)
            
except Exception as e:
    print(f"Error testing TYBA: {e}")
