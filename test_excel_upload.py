import pandas as pd
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

url = "postgresql://postgres:J1sAwYBgoV6nfilKy9bLB1fmkHZhh6ljFzN8syGWyPAZLJUgqAIuCHoxKDqUrslv@84.247.130.122:5438/postgres"
engine = create_engine(url)
Session = sessionmaker(bind=engine)

# Import models
from backend.models import Case, InvalidRadicado

db = Session()

# Read the excel file
excel_file = "RADICADOS ACTUALES ICARUS.xlsx"
df = pd.read_excel(excel_file)
print("Excel columns:", df.columns.tolist())
print(f"Total rows in Excel: {len(df)}")
print("Sample 3 rows:")
print(df.head(3))

# Let's test processing the rows with company_id=3 (Aventuramotors) and user_id=5 (Diego Rincon)
comp_id = 3
user_id = 5

cols_lower = {str(c).strip().lower(): c for c in df.columns}
rad_col = next((cols_lower[k] for k in ["radicado", "numero", "proceso"] if k in cols_lower), None)
ced_col = next((cols_lower[k] for k in ["cedula", "identificacion", "documento"] if k in cols_lower), None)
abo_col = next((cols_lower[k] for k in ["abogado", "apoderado"] if k in cols_lower), None)

print(f"Matched columns: rad_col={rad_col}, ced_col={ced_col}, abo_col={abo_col}")

# Let's see what happens when committing:
try:
    for idx, row in df.iterrows():
        rad = str(row.get(rad_col, "")).strip().replace(".0", "")
        if not rad or rad == "nan":
            continue
        ced = str(row.get(ced_col, "")).strip() if ced_col and pd.notna(row.get(ced_col)) else None
        abo = str(row.get(abo_col, "")).strip() if abo_col and pd.notna(row.get(abo_col)) else None
        
        c = Case(
            radicado=rad,
            cedula=ced,
            abogado=abo,
            user_id=user_id,
            company_id=comp_id
        )
        db.add(c)
    
    db.commit()
    print("SUCCESSFULLY COMMITTED ALL ROWS!")
except Exception as e:
    db.rollback()
    print("FAILED TO COMMIT:", type(e), e)
    import traceback
    traceback.print_exc()
finally:
    db.close()
