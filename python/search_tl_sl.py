import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

with open("routes/checklist_routes.py", "r", encoding="utf-8") as f:
    text = f.read()

# find all matches of TL_SL
import re
matches = re.finditer(r"TL_SL", text)
for m in matches:
    start = max(0, m.start() - 50)
    end = min(len(text), m.end() + 50)
    print(f"Match: {text[start:end]}")
