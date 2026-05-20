import xlrd
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

wb = xlrd.open_workbook("SV.DSV.xls")
sheet = wb.sheet_by_index(0)
print(f"SV VN Rows: {sheet.nrows}")
for r in range(sheet.nrows):
    row_vals = [sheet.cell_value(r, c) for c in range(min(sheet.ncols, 5))]
    trimmed = [str(x).strip() for x in row_vals]
    if any(trimmed):
        print(f"Row {r:02d}: {trimmed}")
