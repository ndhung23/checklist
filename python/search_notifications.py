import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

with open("routes/checklist_routes.py", "r", encoding="utf-8") as f:
    text = f.read()

import re
print("=== Search for Notification in checklist_routes.py ===")
for m in re.finditer(r"Notification", text):
    start = max(0, m.start() - 50)
    end = min(len(text), m.end() + 50)
    print(f"Match: {repr(text[start:end])}")
