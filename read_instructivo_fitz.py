import fitz
import docx
import sys

# Ensure UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

print("=== READING INSTRUCTIVO PUBLICACIONES PROCESALES.PDF ===")
doc = fitz.open("Instructivo publicaciones procesales.pdf")
print(f"Total pages: {len(doc)}")
for i in range(len(doc)):
    page = doc[i]
    print(f"\n--- PAGE {i+1} ---")
    print(page.get_text())

print("\n\n=== READING PASO A PASO.DOCX ===")
try:
    doc_docx = docx.Document("paso a paso.docx")
    for i, p in enumerate(doc_docx.paragraphs):
        if p.text.strip():
            print(f"P{i+1}: {p.text}")
except Exception as e:
    print("Error reading docx:", e)
