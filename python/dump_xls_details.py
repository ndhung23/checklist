import xlrd
import sys
from datetime import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def dump_sheet(filename, sheet_index):
    wb = xlrd.open_workbook(filename)
    sheet = wb.sheet_by_index(sheet_index)
    print(f"\n--- DUMPING {filename} SHEET {sheet.name} ---")
    
    current_time_str = ""
    for r in range(sheet.nrows):
        # We want to find where the checklist items start
        # Usually from row index containing "Thời gian" or "時間"
        # Let's print rows that look like checklist items
        row_vals = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
        # Filter down to useful columns (0 to 5)
        trimmed = [str(x).strip() for x in row_vals[:6]]
        if any(trimmed):
            print(f"Row {r:02d}: {trimmed}")

print("=== SV.DSV.xls ===")
dump_sheet("SV.DSV.xls", 0) # VN
dump_sheet("SV.DSV.xls", 1) # JP

print("\n=== TL.DTL.1.xls ===")
dump_sheet("TL.DTL.1.xls", 0) # VN
dump_sheet("TL.DTL.1.xls", 1) # JP
