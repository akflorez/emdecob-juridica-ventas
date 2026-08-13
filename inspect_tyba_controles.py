import requests
import re
import urllib3
urllib3.disable_warnings()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Let's inspect Controles.js
url_controles = "https://procesojudicial.ramajudicial.gov.co/Justicia21/Scripts/Controles.js"
try:
    r = requests.get(url_controles, headers=headers, verify=False, timeout=10)
    print(f"Controles.js status: {r.status_code}, length: {len(r.text)}")
    
    # Search for PageMethods, ajax, or endpoints
    methods = re.findall(r'(\w+\.aspx/\w+|/Justicia21/[a-zA-Z0-9_\-\/]+)', r.text)
    print("Endpoints/WebMethods in Controles.js:", set(methods[:20]))
    
    # Search for functions
    funcs = re.findall(r'function\s+([a-zA-Z0-9_]+)\s*\(', r.text)
    print("Functions in Controles.js:", funcs[:20])
except Exception as e:
    print("Error:", e)
