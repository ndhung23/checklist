import xlrd
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

wb = xlrd.open_workbook("TL.DTL.1.xls")
sheet = wb.sheet_by_index(0)

current_time_str = ""
item_idx = 1
for r in range(8, sheet.nrows):
    row_vals = [sheet.cell_value(r, c) for c in range(sheet.ncols)]
    symbol = str(row_vals[1]).strip()
    content = str(row_vals[2]).strip()
    
    if not symbol or not content:
        continue
    
    if content.startswith("Nội dung lỗi") or content.startswith("内容"):
        break
        
    # If the first column (time) has content, update current_time_str
    if row_vals[0]:
        current_time_str = str(row_vals[0]).strip().replace('\n', ' ')
    
    print(f"Item {item_idx:02d}: Symbol={symbol:<3} Time Group={repr(current_time_str)} Content={repr(content[:50])}")
    item_idx += 1
