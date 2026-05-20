import xlrd
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

def inspect_xls(filename):
    print(f"\n=== Inspecting {filename} ===")
    wb = xlrd.open_workbook(filename)
    print(f"Sheet names: {wb.sheet_names()}")
    for sname in wb.sheet_names():
        sheet = wb.sheet_by_name(sname)
        print(f"Sheet '{sname}': rows={sheet.nrows}, cols={sheet.ncols}")
        # Print first 15 rows where there is content
        for r in range(min(sheet.nrows, 20)):
            vals = [sheet.cell_value(r, c) for c in range(min(sheet.ncols, 10))]
            if any(vals):
                print(f"Row {r:02d}: {vals}")

inspect_xls("SV.DSV.xls")
inspect_xls("TL.DTL.1.xls")
