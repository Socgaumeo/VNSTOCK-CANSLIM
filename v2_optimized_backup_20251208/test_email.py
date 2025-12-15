#!/usr/bin/env python3
"""
Script kiểm tra cấu hình Email
"""
from email_notifier import EmailNotifier
from config import get_config

def test_email():
    print("📧 Đang kiểm tra cấu hình Email...")
    
    config = get_config().email
    print(f"   Enabled: {config.ENABLED}")
    print(f"   Server: {config.SMTP_SERVER}:{config.SMTP_PORT}")
    print(f"   Sender: {config.SENDER_EMAIL}")
    print(f"   Receiver: {config.RECEIVER_EMAIL}")
    
    if not config.ENABLED:
        print("\n⚠️ Email đang bị tắt (ENABLED=False) trong config.py")
        return
        
    if not config.SENDER_EMAIL or not config.SENDER_PASSWORD:
        print("\n⚠️ Chưa điền SENDER_EMAIL hoặc SENDER_PASSWORD trong config.py")
        return

    print("\n🚀 Đang gửi email test...")
    notifier = EmailNotifier()
    
    test_content = """
    # Test Email Notification
    
    Đây là email kiểm tra từ hệ thống **VNSTOCK-CANSLIM**.
    
    ## Trạng thái
    *   ✅ Kết nối SMTP: OK
    *   ✅ Định dạng HTML: OK
    
    | Item | Status |
    |------|--------|
    | Config | Valid |
    | Network | Connected |
    
    Vui lòng bỏ qua email này.
    """
    
    success = notifier.send_report(test_content)
    
    if success:
        print("\n✅ Gửi thành công! Hãy kiểm tra hộp thư đến (và Spam).")
    else:
        print("\n❌ Gửi thất bại. Vui lòng kiểm tra lại App Password và cấu hình.")

if __name__ == "__main__":
    test_email()
