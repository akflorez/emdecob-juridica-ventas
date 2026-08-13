import sys

modules = ["pypdf", "pypdf2", "pdfminer", "fitz", "pdfplumber", "docx"]
for m in modules:
    try:
        __import__(m)
        print(f"Module {m} is available!")
    except ImportError:
        print(f"Module {m} NOT available")
