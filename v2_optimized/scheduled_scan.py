#!/usr/bin/env python3
"""
Scheduled CANSLIM Scanner - Chạy bởi cron lúc 16h hàng ngày

Crontab (add with: crontab -e):
0 16 * * 1-5 cd /Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/v2_optimized && /Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/v2_optimized/.venv/bin/python scheduled_scan.py >> logs/cron.log 2>&1

Hoặc chạy thủ công:
python scheduled_scan.py

Tính năng:
- Chạy full pipeline (run_compare_ai.py)
- Gửi email báo cáo
- Gửi Telegram alert cho subscribers
- Log kết quả
"""

import os
import sys
import json
import subprocess
import asyncio
from datetime import datetime
from pathlib import Path

# Đường dẫn cố định
PROJECT_DIR = Path(__file__).parent
LOG_DIR = PROJECT_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
CACHE_DIR = PROJECT_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# Telegram config (đọc từ config → .env)
sys.path.insert(0, str(PROJECT_DIR))
from config import get_config
_cfg = get_config()
BOT_TOKEN = _cfg.telegram.BOT_TOKEN
ADMIN_USER_ID = _cfg.telegram.ADMIN_USER_ID
SUBSCRIBERS_FILE = CACHE_DIR / "telegram_subscribers.json"


def log(message: str):
    """Log với timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)


def is_trading_day() -> bool:
    """Kiểm tra có phải ngày giao dịch không (thứ 2-6)"""
    today = datetime.now()
    # Monday = 0, Sunday = 6
    return today.weekday() < 5


def load_subscribers() -> set:
    """Load subscribers từ file"""
    subscribers = {ADMIN_USER_ID}  # Luôn gửi cho admin

    if SUBSCRIBERS_FILE.exists():
        try:
            with open(SUBSCRIBERS_FILE, 'r') as f:
                data = json.load(f)
                subscribers.update(data.get('subscribers', []))
        except Exception as e:
            log(f"Warning: Could not load subscribers: {e}")

    return subscribers


def run_pipeline() -> tuple[int, str]:
    """Chạy run_compare_ai_v2.py (optimized)"""
    log("Starting CANSLIM pipeline (V2 optimized)...")

    # Prefer V2 (data 1x, AI parallel) - faster
    script_path = PROJECT_DIR / "run_compare_ai_v2.py"
    if not script_path.exists():
        script_path = PROJECT_DIR / "run_compare_ai.py"
        log("V2 not found, falling back to V1")

    if not script_path.exists():
        log(f"ERROR: Script not found: {script_path}")
        return 1, "Script not found"

    log(f"Running: {script_path.name}")

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            timeout=7200  # 2 hour timeout (scan all 7 sectors with 2 AI)
        )

        if result.returncode == 0:
            log("Pipeline completed successfully!")
            return 0, "Success"
        else:
            log(f"Pipeline failed with code: {result.returncode}")
            log(f"stderr: {result.stderr[:500] if result.stderr else 'None'}")
            return result.returncode, f"Failed with code {result.returncode}"

    except subprocess.TimeoutExpired:
        log("ERROR: Pipeline timed out after 2 hours")
        return 1, "Timeout after 2 hours"
    except Exception as e:
        log(f"ERROR: {e}")
        return 1, str(e)[:50]


async def send_telegram_alerts(success: bool, status_msg: str):
    """Gửi alert qua Telegram"""
    log("Sending Telegram alerts...")

    try:
        # Check if telegram bot package is available
        try:
            from telegram import Bot
        except ImportError:
            log("WARNING: python-telegram-bot not installed, skipping Telegram alerts")
            log("Install with: pip install python-telegram-bot")
            return

        # Load subscribers
        subscribers = load_subscribers()
        log(f"Found {len(subscribers)} subscribers")

        if not subscribers:
            log("No Telegram subscribers")
            return

        # Create bot instance
        bot = Bot(token=BOT_TOKEN)

        # Status emoji
        status_emoji = "✅" if success else "⚠️"

        # Message
        message = f"""
📊 *BÁO CÁO CANSLIM {datetime.now().strftime('%d/%m/%Y')}*
━━━━━━━━━━━━━━━━━━━━━━

{status_emoji} {status_msg}

📧 Chi tiết đã gửi qua email

💡 Gõ `/top` để xem top picks
💡 Gõ `/vn <mã>` để phân tích chi tiết
💡 Bấm nút Menu trong bot để xem thêm

⏰ Scan time: {datetime.now().strftime('%H:%M:%S')}
"""

        # Send to all subscribers
        sent_count = 0
        for user_id in subscribers:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode='Markdown'
                )
                log(f"  ✓ Sent alert to {user_id}")
                sent_count += 1
            except Exception as e:
                log(f"  ✗ Failed to send to {user_id}: {e}")

        log(f"Telegram alerts sent to {sent_count}/{len(subscribers)} subscribers")

    except Exception as e:
        log(f"ERROR sending Telegram alerts: {e}")


async def send_start_notification():
    """Thông báo bắt đầu scan"""
    try:
        from telegram import Bot
        bot = Bot(token=BOT_TOKEN)

        subscribers = load_subscribers()
        message = f"⏳ *Đang chạy scan CANSLIM {datetime.now().strftime('%d/%m/%Y')} lúc 16h...*\n\nVui lòng chờ khoảng 10-15 phút."

        for user_id in subscribers:
            try:
                await bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
            except:
                pass
    except ImportError:
        pass
    except Exception as e:
        log(f"Could not send start notification: {e}")


def main():
    """Main entry point"""
    log("=" * 60)
    log("🚀 SCHEDULED CANSLIM SCANNER")
    log("=" * 60)

    # Check if trading day
    if not is_trading_day():
        log("📅 Not a trading day (weekend), skipping...")
        return 0

    log(f"📅 Today is a trading day: {datetime.now().strftime('%A %d/%m/%Y')}")

    # Send start notification
    try:
        asyncio.run(send_start_notification())
    except Exception as e:
        log(f"Could not send start notification: {e}")

    # Run pipeline
    exit_code, status_msg = run_pipeline()
    success = exit_code == 0

    # Send Telegram alerts
    try:
        if success:
            asyncio.run(send_telegram_alerts(True, "Scan hoàn tất thành công!"))
        else:
            asyncio.run(send_telegram_alerts(False, f"Scan có lỗi: {status_msg}"))
    except Exception as e:
        log(f"WARNING: Could not send Telegram alerts: {e}")

    log("=" * 60)
    log(f"Scheduled scan completed with exit code: {exit_code}")
    log("=" * 60)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
