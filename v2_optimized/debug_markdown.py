
import markdown2
import os

report_path = "/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/v2_optimized/output/debate_20260105_1133/simultaneous_debate_20260105_1133.md"

if not os.path.exists(report_path):
    print("Report file not found")
    exit(1)

with open(report_path, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"Report length: {len(content)}")

try:
    html = markdown2.markdown(content, extras=["tables", "fenced-code-blocks", "cuddled-lists"])
    print(f"HTML length: {len(html)}")
    print("First 500 chars of HTML:")
    print(html[:500])
except Exception as e:
    print(f"Error converting: {e}")
