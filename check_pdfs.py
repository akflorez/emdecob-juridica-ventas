import sys
import os
import requests
import fitz  # PyMuPDF
sys.path.append(os.path.abspath('.'))
from backend.db import SessionLocal
from backend.models import Case, CasePublication

db = SessionLocal()
radicado = '63001400300720250031800'
case = db.query(Case).filter(Case.radicado == radicado).first()

pubs = db.query(CasePublication).filter(CasePublication.case_id == case.id).all()

radicado_short1 = '202500318'
radicado_short2 = '2025-00318'
radicado_short3 = '2025-318'
radicado_short4 = '2025 00318'

mismatched = []

for p in pubs:
    url = p.documento_url
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            doc = fitz.open(stream=response.content, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            
            found = False
            for r in [radicado, radicado_short1, radicado_short2, radicado_short3, radicado_short4]:
                if r in text:
                    found = True
                    break
                    
            if not found:
                print(f"Mismatch found: ID {p.id}, {p.descripcion}")
                mismatched.append(p.id)
            else:
                print(f"Match OK: ID {p.id}, {p.descripcion}")
        else:
            print(f"Failed to download ID {p.id}: {response.status_code}")
    except Exception as e:
        print(f"Error checking ID {p.id}: {e}")

print("Mismatched IDs:", mismatched)
