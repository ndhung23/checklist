import xlrd
import sys
from datetime import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

wb = xlrd.open_workbook("TL.DTL.1.xls")
sheet = wb.sheet_by_index(0)

print("--- Check times parsed in TL.DTL.1.xls ---")
for r in range(8, sheet.nrows):
    row_vals = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
    symbol = str(row_vals[1]).strip()
    content = str(row_vals[2]).strip()
    
    if not symbol or not content:
        continue
    
    if content.startswith("Nội dung lỗi") or content.startswith("内容"):
        break
        
    time_cell = sheet.cell(r, 0)
    time_val = time_cell.value
    time_type = time_cell.ctype
    
    print(f"Row {r:02d}: Symbol={symbol:<3} Content={repr(content[:30])} RawTime={repr(time_val)} Type={time_type}")
