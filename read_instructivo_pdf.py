import pypdf
import os

pdf_path = "Instructivo publicaciones procesales.pdf"
print(f"Reading {pdf_path}...")

try:
    reader = pypdf.PdfReader(pdf_path)
    print(f"Total pages: {len(reader.pages)}")
    for i, page in enumerate(reader.pages):
        print(f"\n--- PAGE {i+1} ---")
        text = page.extract_text()
        print(text[:1500])
except Exception as e:
    print("Error reading with pypdf:", e)
