import re

with open("deep_search_sic_js.py", "r") as f:
    pass

import requests
url = "https://consultatramites.sic.gov.co/main-MLEZUGQD.js"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
r = requests.get(url, headers=headers)
js = r.text

print("Searching for document viewing / download logic in SIC bundle...")
matches = re.finditer(r'getDocument[a-zA-Z0-9_]*|[a-zA-Z0-9_]*Document[a-zA-Z0-9_]*', js)
found_funcs = set([m.group(0) for m in matches])
print("Document functions found:", found_funcs)

# Let's inspect getDocumentUrl and surrounding code
pos = js.find("getDocumentUrl")
if pos != -1:
    print("\n--- getDocumentUrl Snippet ---")
    print(js[max(0, pos-200):min(len(js), pos+800)])

pos_view = js.find("verDocumento")
if pos_view != -1:
    print("\n--- verDocumento Snippet ---")
    print(js[max(0, pos_view-200):min(len(js), pos_view+800)])

pos_act = js.find("acciones")
if pos_act != -1:
    print("\n--- acciones Snippet ---")
    print(js[max(0, pos_act-200):min(len(js), pos_act+800)])
