import requests
import re

url = "https://consultatramites.sic.gov.co/main-MLEZUGQD.js"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

r = requests.get(url, headers=headers)
text = r.text

print("Searching for API urls in JS...")
matches = re.findall(r'["\'](/api/[^"\']+|https?://[^"\']+|/consultatramites[^"\']*)["\']', text)
for m in set(matches):
    if not m.startswith("http://www.w3.org") and not m.startswith("https://fonts") and not m.startswith("https://challenges"):
        print("API URL:", m)

print("\nSearching for method names / search terms...")
terms = ["radicado", "tramite", "consultar", "turnstile", "numeroRadicado", "tipoDocumento", "numeroDocumento"]
for t in terms:
    occs = [m.start() for m in re.finditer(t, text, re.IGNORECASE)]
    print(f"Term '{t}': {len(occs)} occurrences")
    if occs:
        # print snippet around first occurrence
        pos = occs[0]
        snippet = text[max(0, pos-100):min(len(text), pos+200)]
        print(f"  Snippet: {snippet}\n")
