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
            
            # Since PyMuPDF separates with newlines, check if 318 or 00318 is in text
            if '00318' in text or '0318' in text or '318' in text:
                print(f"Match OK: ID {p.id}, {p.descripcion}")
            else:
                print(f"Mismatch found: ID {p.id}, {p.descripcion}")
                mismatched.append(p)
        else:
            print(f"Failed to download ID {p.id}: {response.status_code}")
            mismatched.append(p)
    except Exception as e:
        print(f"Error checking ID {p.id}: {e}")
        mismatched.append(p)

print(f"Deleting {len(mismatched)} mismatched publications...")
for p in mismatched:
    db.delete(p)
db.commit()
print("Deletion complete.")
