#!/usr/bin/env python3
"""
Module gửi email báo cáo tự động
Hỗ trợ gửi nội dung HTML (convert từ Markdown) và đính kèm file
"""

import os
import smtplib
import markdown2  # Cần cài đặt: pip install markdown2
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from typing import List, Optional

from config import get_config


class EmailNotifier:
    """Gửi email báo cáo qua SMTP"""
    
    def __init__(self):
        self.config = get_config().email
        
    def send_report(self, 
                   report_content: str, 
                   attachment_path: Optional[str] = None) -> bool:
        """
        Gửi email báo cáo
        
        Args:
            report_content: Nội dung báo cáo (HTML/Markdown)
            attachment_path: Đường dẫn file đính kèm (Optional)
        """
        if not self.config.ENABLED:
            print("📧 Email notification is disabled.")
            return False
            
        if not self.config.SENDER_EMAIL or not self.config.SENDER_PASSWORD:
            print("   ⚠️ Email credentials missing. Please update config.py")
            return False
            
        try:
            # 1. Setup Email
            msg = MIMEMultipart()
            msg['From'] = self.config.SENDER_EMAIL
            msg['To'] = self.config.RECEIVER_EMAIL
            
            # Subject with Date
            date_str = datetime.now().strftime("%d/%m/%Y")
            msg['Subject'] = f"{self.config.SUBJECT_PREFIX} Report {date_str}"
            
            # 2. Body (Convert Markdown to HTML)
            try:
                html_content = markdown2.markdown(
                    report_content, 
                    extras=["tables", "fenced-code-blocks", "cuddled-lists"]
                )
            except ImportError:
                # Fallback nếu chưa cài markdown2
                html_content = f"<pre>{report_content}</pre>"
                print("   ⚠️ 'markdown2' not installed. Sending as plain text.")
            
            # Add styling for better look
            html_body = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                    h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
                    h2 {{ color: #2980b9; margin-top: 20px; }}
                    h3 {{ color: #16a085; }}
                    table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                    th {{ background-color: #f2f2f2; }}
                    tr:nth-child(even) {{ background-color: #f9f9f9; }}
                    code {{ background-color: #f4f4f4; padding: 2px 5px; border-radius: 3px; }}
                    .footer {{ margin-top: 30px; font-size: 0.8em; color: #7f8c8d; border-top: 1px solid #eee; padding-top: 10px; }}
                </style>
            </head>
            <body>
                {html_content}
                <div class="footer">
                    <p>Sent automatically by CANSLIM Scanner at {datetime.now().strftime('%H:%M:%S')}</p>
                </div>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_body, 'html'))
            
            # 3. Add Attachment (Original File)
            if attachment_path and os.path.exists(attachment_path):
                filename = os.path.basename(attachment_path)
                with open(attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=filename)
                part['Content-Disposition'] = f'attachment; filename="{filename}"'
                msg.attach(part)
                
            # 4. Send Email
            print(f"\n📧 Sending email to {self.config.RECEIVER_EMAIL}...")
            
            server = smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT)
            server.starttls()
            server.login(self.config.SENDER_EMAIL, self.config.SENDER_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            print("   ✅ Email sent successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Email Error: {e}")
            return False

if __name__ == "__main__":
    # Test script
    print("Testing Email Notifier...")
    notifier = EmailNotifier()
    
    # Mock content
    content = """
    # Test Report
    This is a **test** email from CANSLIM Scanner.
    
    | Column 1 | Column 2 |
    |----------|----------|
    | Value A  | Value B  |
    """
    
    notifier.send_report(content)
