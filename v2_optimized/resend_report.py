
from email_notifier import EmailNotifier
import os

report_path = "/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/v2_optimized/output/debate_20260105_1133/simultaneous_debate_20260105_1133.md"

if not os.path.exists(report_path):
    print(f"Report file not found: {report_path}")
    exit(1)

with open(report_path, 'r', encoding='utf-8') as f:
    report_content = f.read()

print(f"Loaded report: {len(report_content)} chars")

notifier = EmailNotifier()
print("Sending report...")
notifier.send_report(report_content, attachment_path=report_path)
print("Done.")
