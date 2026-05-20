import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

with open("routes/checklist_routes.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print("=== SEARCH FOR TEMPLATE IN CHECKLIST_ROUTES.PY ===")
for i, line in enumerate(lines):
    if "template" in line or "shift" in line or "dashboard" in line:
        # print line and line number
        if i < 150 or "template" in line:
            print(f"Line {i+1:03d}: {line.strip()}")
