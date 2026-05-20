import sys

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

with open("templates/dashboard.html", "r", encoding="utf-8") as f:
    text = f.read()

# Let's find some keywords like "ca", "shift", "template"
import re
print("=== Keywords in dashboard.html ===")
for m in re.finditer(r"(ca|shift|thay đổi|chọn)", text, re.IGNORECASE):
    start = max(0, m.start() - 40)
    end = min(len(text), m.end() + 40)
    print(f"Match: {repr(text[start:end])}")
