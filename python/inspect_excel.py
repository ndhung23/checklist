import sys
import openpyxl

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

wb = openpyxl.load_workbook("S.d.t.ch.c.xlsx")
sheet = wb.active
print(f"Sheet name: {sheet.title}")
print(f"Dimensions: {sheet.dimensions}")

# print first 15 rows of S.d.t.ch.c.xlsx
for row in range(1, 40):
    vals = [sheet.cell(row, col).value for col in range(1, 10)]
    if any(vals):
        print(f"Row {row:02d}: {vals}")
