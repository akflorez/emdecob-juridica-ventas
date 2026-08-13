import pandas as pd

excel_files = ["RADICADOS ACTUALES ICARUS.xlsx", "radicados santiago.xlsx"]

for f in excel_files:
    try:
        df = pd.read_excel(f)
        print(f"\n=== FILE: {f} (Rows: {len(df)}) ===")
        print("Columns:", list(df.columns))
        print("First 10 radicados in raw Excel:")
        for idx, row in df.head(10).iterrows():
            print(f"  Row {idx+1}: {row.iloc[0]}")
    except Exception as e:
        print(f"Error reading {f}: {e}")
