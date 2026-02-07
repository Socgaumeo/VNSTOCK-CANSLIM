#!/usr/bin/env python3
"""
CANSLIM Telegram Bot - Tra cứu phân tích cổ phiếu

Commands:
- /start - Giới thiệu bot
- /vn <mã> - Phân tích đầy đủ 1 mã
- /tech <mã> - Chỉ Technical
- /fund <mã> - Chỉ Fundamental
- /compare <mã1> <mã2> - So sánh 2 mã
- /top - Top 10 picks hôm nay
- /market - Tình hình thị trường
- /sector - Xếp hạng ngành
- /alert on/off - Bật/tắt alert 16h
"""

import os
import sys
import json
import asyncio
import logging
import subprocess
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Set
import pytz

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Add path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Telegram imports
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import (
        Application, CommandHandler, ContextTypes,
        MessageHandler, filters, CallbackQueryHandler
    )
    HAS_TELEGRAM = True
except ImportError:
    HAS_TELEGRAM = False
    print("❌ python-telegram-bot not installed!")
    print("Run: pip install python-telegram-bot")

# Project imports
from config import get_config


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

# Bot Configuration
BOT_TOKEN = "7058792437:AAHcArFXfdP-UOlw3Mnk_E_syhX_iPORJ5o"
ADMIN_USER_ID = 348988385

# Alert subscribers file
SUBSCRIBERS_FILE = Path(__file__).parent / "cache" / "telegram_subscribers.json"

# Global set of subscribers
alert_subscribers: Set[int] = set()


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def load_subscribers():
    """Load subscribers từ file"""
    global alert_subscribers
    if SUBSCRIBERS_FILE.exists():
        try:
            with open(SUBSCRIBERS_FILE, 'r') as f:
                data = json.load(f)
                alert_subscribers = set(data.get('subscribers', []))
        except:
            alert_subscribers = set()
    return alert_subscribers


def save_subscribers():
    """Save subscribers to file"""
    SUBSCRIBERS_FILE.parent.mkdir(exist_ok=True)
    with open(SUBSCRIBERS_FILE, 'w') as f:
        json.dump({'subscribers': list(alert_subscribers)}, f)


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram"""
    # For MarkdownV2, escape these characters
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in chars:
        text = text.replace(char, f'\\{char}')
    return text


# ══════════════════════════════════════════════════════════════════════════════
# KEYBOARD BUILDERS
# ══════════════════════════════════════════════════════════════════════════════

# Các mã phổ biến để quick access
POPULAR_STOCKS = ["VCB", "FPT", "HPG", "MWG", "VNM", "VIC", "TCB", "VHM", "MSN", "ACB"]

def build_main_menu_keyboard():
    """Tạo menu chính"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Phân tích mã", callback_data="menu_analyze"),
            InlineKeyboardButton("🏆 Top Picks", callback_data="action_top"),
        ],
        [
            InlineKeyboardButton("🏛️ Thị trường", callback_data="action_market"),
            InlineKeyboardButton("🏭 Xếp hạng ngành", callback_data="action_sector"),
        ],
        [
            InlineKeyboardButton("📢 Bật/Tắt Alert", callback_data="menu_alert"),
            InlineKeyboardButton("❓ Trợ giúp", callback_data="action_help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_popular_stocks_keyboard():
    """Tạo keyboard các mã phổ biến"""
    # Chia thành 2 hàng, mỗi hàng 5 mã
    row1 = [InlineKeyboardButton(s, callback_data=f"stock_{s}") for s in POPULAR_STOCKS[:5]]
    row2 = [InlineKeyboardButton(s, callback_data=f"stock_{s}") for s in POPULAR_STOCKS[5:]]
    keyboard = [row1, row2, [InlineKeyboardButton("🔙 Menu chính", callback_data="menu_main")]]
    return InlineKeyboardMarkup(keyboard)


def build_analysis_type_keyboard(symbol: str):
    """Tạo keyboard chọn loại phân tích"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Đầy đủ", callback_data=f"analyze_full_{symbol}"),
            InlineKeyboardButton("📉 Kỹ thuật", callback_data=f"analyze_tech_{symbol}"),
            InlineKeyboardButton("💼 Cơ bản", callback_data=f"analyze_fund_{symbol}"),
        ],
        [InlineKeyboardButton("🔙 Chọn mã khác", callback_data="menu_analyze")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_after_analysis_keyboard(symbol: str):
    """Tạo keyboard sau khi phân tích xong"""
    keyboard = [
        [
            InlineKeyboardButton("📉 Kỹ thuật", callback_data=f"analyze_tech_{symbol}"),
            InlineKeyboardButton("💼 Cơ bản", callback_data=f"analyze_fund_{symbol}"),
        ],
        [
            InlineKeyboardButton("📊 Phân tích mã khác", callback_data="menu_analyze"),
            InlineKeyboardButton("🏠 Menu chính", callback_data="menu_main"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_alert_keyboard(is_subscribed: bool):
    """Tạo keyboard bật/tắt alert"""
    if is_subscribed:
        keyboard = [
            [InlineKeyboardButton("🔕 Tắt Alert", callback_data="alert_off")],
            [InlineKeyboardButton("🔙 Menu chính", callback_data="menu_main")],
        ]
    else:
        keyboard = [
            [InlineKeyboardButton("🔔 Bật Alert (16h hàng ngày)", callback_data="alert_on")],
            [InlineKeyboardButton("🔙 Menu chính", callback_data="menu_main")],
        ]
    return InlineKeyboardMarkup(keyboard)


def build_back_to_menu_keyboard():
    """Keyboard quay về menu"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Menu chính", callback_data="menu_main")]])


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /start"""
    user = update.effective_user
    welcome_text = f"""
👋 Chào {user.first_name}!

Tôi là *CANSLIM Stock Bot* - Trợ lý phân tích cổ phiếu Việt Nam với AI Claude Sonnet 4.

🔹 Bấm nút bên dưới để sử dụng
🔹 Hoặc gõ `/vn <mã>` để phân tích nhanh

💡 Ví dụ: `/vn FPT` hoặc `/compare VCB BID`
"""
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=build_main_menu_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /help"""
    help_text = """
📚 *Hướng dẫn sử dụng:*

*Phân tích cổ phiếu:*
• `/vn VCB` - Phân tích đầy đủ Vietcombank
• `/tech HPG` - Chỉ kỹ thuật HPG
• `/fund MWG` - Chỉ cơ bản MWG

*So sánh & Tổng hợp:*
• `/compare FPT CMG` - So sánh 2 mã
• `/top` - Top 10 cổ phiếu hôm nay
• `/market` - Tình hình thị trường
• `/sector` - Ngành mạnh nhất

*Alert:*
• `/alert on` - Nhận báo cáo lúc 16h
• `/alert off` - Tắt báo cáo

⚠️ Dữ liệu chỉ mang tính tham khảo!
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def analyze_stock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /vn <symbol>"""
    if not context.args:
        await update.message.reply_text("❌ Vui lòng nhập mã cổ phiếu!\nVí dụ: `/vn VCB`", parse_mode='Markdown')
        return

    symbol = context.args[0].upper()
    await update.message.reply_text(f"⏳ Đang phân tích {symbol}...")

    try:
        from stock_analyzer import get_stock_analyzer
        analyzer = get_stock_analyzer()
        summary = analyzer.get_quick_summary(symbol)
        await update.message.reply_text(summary)
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}")
        await update.message.reply_text(f"❌ Lỗi khi phân tích {symbol}: {str(e)[:100]}")


async def technical_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /tech <symbol>"""
    if not context.args:
        await update.message.reply_text("❌ Vui lòng nhập mã cổ phiếu!\nVí dụ: `/tech FPT`", parse_mode='Markdown')
        return

    symbol = context.args[0].upper()
    await update.message.reply_text(f"⏳ Đang phân tích kỹ thuật {symbol}...")

    try:
        from stock_analyzer import get_stock_analyzer
        analyzer = get_stock_analyzer()
        result = analyzer.analyze(symbol)

        if result.error:
            await update.message.reply_text(f"❌ {result.error}")
            return

        tech = result.technical
        text = f"""
📉 *TECHNICAL ANALYSIS: {symbol}*
━━━━━━━━━━━━━━━━━━━━━━

💰 Giá: {tech.price:,.0f} VND ({tech.change_1d_pct:+.1f}%)
📊 Score: {result.score_technical:.0f}/100

*Moving Averages:*
• MA20: {tech.ma20:,.0f} {'✅' if tech.above_ma20 else '❌'}
• MA50: {tech.ma50:,.0f} {'✅' if tech.above_ma50 else '❌'}
• MA200: {tech.ma200:,.0f} {'✅' if tech.above_ma200 else '❌'}

*Indicators:*
• RSI(14): {tech.rsi:.0f} ({tech.rsi_signal})
• RS Rating: {tech.rs_rating}/100
• Volume: {tech.volume_ratio:.1f}x ({tech.volume_signal})

*52 Week:*
• High: {tech.high_52w:,.0f}
• Low: {tech.low_52w:,.0f}
• Distance: {tech.distance_from_high:.1f}%

*Volume Profile:*
• POC: {tech.poc:,.0f}
• VAH: {tech.vah:,.0f}
• VAL: {tech.val:,.0f}
"""
        await update.message.reply_text(text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in technical analysis {symbol}: {e}")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


async def fundamental_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /fund <symbol>"""
    if not context.args:
        await update.message.reply_text("❌ Vui lòng nhập mã cổ phiếu!\nVí dụ: `/fund MWG`", parse_mode='Markdown')
        return

    symbol = context.args[0].upper()
    await update.message.reply_text(f"⏳ Đang phân tích cơ bản {symbol}...")

    try:
        from stock_analyzer import get_stock_analyzer
        analyzer = get_stock_analyzer()
        result = analyzer.analyze(symbol)

        if result.error:
            await update.message.reply_text(f"❌ {result.error}")
            return

        fund = result.fundamental
        text = f"""
💼 *FUNDAMENTAL ANALYSIS: {symbol}*
━━━━━━━━━━━━━━━━━━━━━━

📊 Score: {result.score_fundamental:.0f}/100

*EPS Growth:*
• Q/Q: {fund.eps_growth_qoq:+.1f}%
• Y/Y: {fund.eps_growth_yoy:+.1f}%

*Revenue Growth:*
• Q/Q: {fund.revenue_growth_qoq:+.1f}%
• Y/Y: {fund.revenue_growth_yoy:+.1f}%

*Profitability:*
• ROE: {fund.roe:.1f}%
• ROA: {fund.roa:.1f}%

*Valuation:*
• P/E: {fund.pe:.1f}
• P/B: {fund.pb:.1f}

*Cash Flow:*
• OCF/Profit: {fund.ocf_to_profit:.1f}x
• Quality: {fund.cf_quality}

*CANSLIM Scores:*
• C (Current EPS): {fund.c_score:.0f}
• A (Annual EPS): {fund.a_score:.0f}
"""
        await update.message.reply_text(text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in fundamental analysis {symbol}: {e}")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /compare <symbol1> <symbol2>"""
    if len(context.args) < 2:
        await update.message.reply_text("❌ Cần 2 mã để so sánh!\nVí dụ: `/compare VCB BID`", parse_mode='Markdown')
        return

    symbol1 = context.args[0].upper()
    symbol2 = context.args[1].upper()

    await update.message.reply_text(f"⏳ Đang so sánh {symbol1} vs {symbol2}...")

    try:
        from stock_analyzer import get_stock_analyzer
        analyzer = get_stock_analyzer()

        r1 = analyzer.analyze(symbol1)
        r2 = analyzer.analyze(symbol2)

        text = f"""
⚔️ *SO SÁNH: {symbol1} vs {symbol2}*
━━━━━━━━━━━━━━━━━━━━━━

| Metric | {symbol1} | {symbol2} |
|--------|--------|--------|
| Score | {r1.score_total:.0f} | {r2.score_total:.0f} |
| Signal | {r1.signal} | {r2.signal} |
| Price | {r1.technical.price:,.0f} | {r2.technical.price:,.0f} |
| RSI | {r1.technical.rsi:.0f} | {r2.technical.rsi:.0f} |
| RS Rating | {r1.technical.rs_rating} | {r2.technical.rs_rating} |
| PE | {r1.fundamental.pe:.1f} | {r2.fundamental.pe:.1f} |
| ROE | {r1.fundamental.roe:.1f}% | {r2.fundamental.roe:.1f}% |
| EPS Q/Q | {r1.fundamental.eps_growth_qoq:+.1f}% | {r2.fundamental.eps_growth_qoq:+.1f}% |

🏆 *Winner:* {symbol1 if r1.score_total > r2.score_total else symbol2} ({max(r1.score_total, r2.score_total):.0f} pts)
"""
        await update.message.reply_text(text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error comparing {symbol1} vs {symbol2}: {e}")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


async def top_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /top - Top picks hôm nay"""
    await update.message.reply_text("⏳ Đang tải top picks...")

    try:
        # Tìm báo cáo mới nhất
        output_dir = Path(__file__).parent / "output"
        report_files = sorted(output_dir.glob("canslim_report_claude_*.md"), reverse=True)

        if not report_files:
            await update.message.reply_text("❌ Chưa có báo cáo hôm nay. Chạy `/market` để xem tình hình.")
            return

        latest_report = report_files[0]

        # Parse top picks từ file (simplified)
        with open(latest_report, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extract top 10 section (simplified parsing)
        text = f"""
🏆 *TOP PICKS HÔM NAY*
━━━━━━━━━━━━━━━━━━━━━━

📄 Báo cáo: {latest_report.name}

💡 Xem chi tiết từng mã:
`/vn <mã>` để phân tích

📧 Báo cáo đầy đủ đã gửi qua email lúc 16h
"""
        await update.message.reply_text(text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error loading top picks: {e}")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


async def market_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /market - Tình hình thị trường"""
    await update.message.reply_text("⏳ Đang tải dữ liệu thị trường...")

    try:
        from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified

        config = create_config_from_unified()
        config.AI_PROVIDER = ""  # Disable AI for quick response

        module = MarketTimingModule(config)
        report = module.run()

        if report:
            vnindex = report.vnindex
            # EnhancedStockData uses 'price' not 'close'
            price = getattr(vnindex, 'price', 0) or getattr(vnindex, 'close', 0)
            change = getattr(vnindex, 'change_1d', 0) or getattr(vnindex, 'change_pct', 0)
            rsi = getattr(vnindex, 'rsi_14', 0) or getattr(vnindex, 'rsi', 0)

            text = f"""
🏛️ *TÌNH HÌNH THỊ TRƯỜNG*
━━━━━━━━━━━━━━━━━━━━━━

📊 *VN-Index:* {price:,.2f} ({change:+.2f}%)

*Market Score:* {report.market_score}/100 {report.market_color}

*Technical:*
• RSI: {rsi:.0f}
• Trend: {getattr(report, 'trend', 'N/A')}
• MA Status: {getattr(vnindex, 'ma_status', 'N/A')}

*Breadth:*
• Advances: {report.breadth.advances if report.breadth else 'N/A'}
• Declines: {report.breadth.declines if report.breadth else 'N/A'}

*Volume Profile:*
• POC: {getattr(vnindex, 'poc', 0):,.0f}
• VAH: {getattr(vnindex, 'vah', 0):,.0f}
• VAL: {getattr(vnindex, 'val', 0):,.0f}

⏰ Cập nhật: {datetime.now().strftime('%H:%M %d/%m')}
"""
            await update.message.reply_text(text, parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Không thể tải dữ liệu thị trường")

    except Exception as e:
        logger.error(f"Error in market command: {e}")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


async def sector_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /sector - Xếp hạng ngành"""
    await update.message.reply_text("⏳ Đang tải dữ liệu ngành...")

    try:
        # Load từ báo cáo gần nhất
        output_dir = Path(__file__).parent / "output"
        sector_files = sorted(output_dir.glob("sector_rotation_*.json"), reverse=True)

        if sector_files:
            with open(sector_files[0], 'r', encoding='utf-8') as f:
                data = json.load(f)

            sectors = data.get('sectors', [])[:7]

            lines = ["🏭 *XẾP HẠNG NGÀNH*", "━━━━━━━━━━━━━━━━━━━━━━", ""]

            for i, s in enumerate(sectors, 1):
                name = s.get('name', s.get('symbol', 'N/A'))
                rs = s.get('rs_rating', 0)
                change = s.get('change_1m', 0)
                phase = s.get('phase', 'N/A')

                emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                lines.append(f"{emoji} *{name}*")
                lines.append(f"   RS: {rs} | 1M: {change:+.1f}% | {phase}")
                lines.append("")

            await update.message.reply_text("\n".join(lines), parse_mode='Markdown')
        else:
            await update.message.reply_text("❌ Chưa có dữ liệu ngành. Chạy scan trước.")

    except Exception as e:
        logger.error(f"Error in sector command: {e}")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /alert on/off"""
    user_id = update.effective_user.id

    if not context.args:
        status = "ON ✅" if user_id in alert_subscribers else "OFF ❌"
        await update.message.reply_text(f"📢 Alert status: {status}\n\nDùng `/alert on` hoặc `/alert off`", parse_mode='Markdown')
        return

    action = context.args[0].lower()

    if action == 'on':
        alert_subscribers.add(user_id)
        save_subscribers()
        await update.message.reply_text("✅ Đã bật alert! Bạn sẽ nhận báo cáo lúc 16h hàng ngày.")
    elif action == 'off':
        alert_subscribers.discard(user_id)
        save_subscribers()
        await update.message.reply_text("❌ Đã tắt alert.")
    else:
        await update.message.reply_text("❓ Dùng `/alert on` hoặc `/alert off`", parse_mode='Markdown')


async def scan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /scan - Chỉ admin mới được dùng"""
    user_id = update.effective_user.id

    if user_id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Chỉ admin mới được sử dụng lệnh này.")
        return

    await update.message.reply_text(
        "🚀 *Bắt đầu chạy scan CANSLIM thủ công...*\n\n"
        "⏳ Quá trình có thể mất 10-15 phút.",
        parse_mode='Markdown'
    )

    # Trigger the scheduled job manually
    await scheduled_scan_job(context)


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho command không nhận diện"""
    await update.message.reply_text("❓ Không hiểu command. Gõ `/help` để xem hướng dẫn.", parse_mode='Markdown')


# ══════════════════════════════════════════════════════════════════════════════
# ALERT FUNCTION (called by scheduler)
# ══════════════════════════════════════════════════════════════════════════════

async def send_daily_alert(app: Application, report_path: str = None):
    """Gửi alert hàng ngày cho subscribers"""
    load_subscribers()

    if not alert_subscribers:
        logger.info("No subscribers for daily alert")
        return

    # Load report summary
    message = f"""
📊 *BÁO CÁO CANSLIM {datetime.now().strftime('%d/%m/%Y')}*

✅ Scan hoàn tất lúc 16h
📧 Chi tiết đã gửi qua email

💡 Gõ `/top` để xem top picks
💡 Gõ `/vn <mã>` để phân tích chi tiết
"""

    for user_id in alert_subscribers:
        try:
            await app.bot.send_message(chat_id=user_id, text=message, parse_mode='Markdown')
            logger.info(f"Sent alert to {user_id}")
        except Exception as e:
            logger.error(f"Failed to send alert to {user_id}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACK HANDLERS (for inline buttons)
# ══════════════════════════════════════════════════════════════════════════════

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho tất cả inline button callbacks"""
    query = update.callback_query
    await query.answer()  # Acknowledge the callback

    data = query.data
    user_id = query.from_user.id

    # ─── MENU NAVIGATION ───
    if data == "menu_main":
        await query.edit_message_text(
            "🏠 *MENU CHÍNH*\n\nChọn chức năng bên dưới:",
            parse_mode='Markdown',
            reply_markup=build_main_menu_keyboard()
        )

    elif data == "menu_analyze":
        await query.edit_message_text(
            "📊 *PHÂN TÍCH CỔ PHIẾU*\n\n"
            "Chọn mã phổ biến hoặc gõ `/vn <mã>` để phân tích mã bất kỳ:",
            parse_mode='Markdown',
            reply_markup=build_popular_stocks_keyboard()
        )

    elif data == "menu_alert":
        is_subscribed = user_id in alert_subscribers
        status = "✅ Đang BẬT" if is_subscribed else "❌ Đang TẮT"
        await query.edit_message_text(
            f"📢 *CÀI ĐẶT ALERT*\n\n"
            f"Trạng thái: {status}\n\n"
            f"Alert sẽ gửi báo cáo tổng hợp lúc 16h hàng ngày.",
            parse_mode='Markdown',
            reply_markup=build_alert_keyboard(is_subscribed)
        )

    # ─── ACTIONS ───
    elif data == "action_top":
        await query.edit_message_text("⏳ Đang tải top picks...")
        try:
            output_dir = Path(__file__).parent / "output"
            report_files = sorted(output_dir.glob("canslim_report_claude_*.md"), reverse=True)

            if report_files:
                text = f"""
🏆 *TOP PICKS HÔM NAY*
━━━━━━━━━━━━━━━━━━━━━━

📄 Báo cáo: {report_files[0].name}

💡 Bấm phân tích để xem chi tiết từng mã
📧 Báo cáo đầy đủ đã gửi qua email
"""
            else:
                text = "❌ Chưa có báo cáo hôm nay."

            await query.edit_message_text(
                text, parse_mode='Markdown',
                reply_markup=build_popular_stocks_keyboard()
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Lỗi: {str(e)[:100]}",
                reply_markup=build_back_to_menu_keyboard()
            )

    elif data == "action_market":
        await query.edit_message_text("⏳ Đang tải dữ liệu thị trường...")
        try:
            from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified

            config = create_config_from_unified()
            config.AI_PROVIDER = ""

            module = MarketTimingModule(config)
            report = module.run()

            if report:
                vnindex = report.vnindex
                # EnhancedStockData uses 'price' not 'close', and 'change_1d' not 'change_pct'
                price = getattr(vnindex, 'price', 0) or getattr(vnindex, 'close', 0)
                change = getattr(vnindex, 'change_1d', 0) or getattr(vnindex, 'change_pct', 0)
                rsi = getattr(vnindex, 'rsi_14', 0) or getattr(vnindex, 'rsi', 0)
                poc = getattr(vnindex, 'poc', 0)
                vah = getattr(vnindex, 'vah', 0)
                val = getattr(vnindex, 'val', 0)

                text = f"""
🏛️ *TÌNH HÌNH THỊ TRƯỜNG*
━━━━━━━━━━━━━━━━━━━━━━

📊 *VN-Index:* {price:,.2f} ({change:+.2f}%)

*Market Score:* {report.market_score}/100 {report.market_color}

*Technical:*
• RSI: {rsi:.0f}
• Trend: {getattr(report, 'trend', 'N/A')}
• MA Status: {getattr(vnindex, 'ma_status', 'N/A')}

*Volume Profile:*
• POC: {poc:,.0f}
• VAH: {vah:,.0f}
• VAL: {val:,.0f}

⏰ {datetime.now().strftime('%H:%M %d/%m/%Y')}
"""
            else:
                text = "❌ Không thể tải dữ liệu thị trường"

            await query.edit_message_text(
                text, parse_mode='Markdown',
                reply_markup=build_back_to_menu_keyboard()
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Lỗi: {str(e)[:100]}",
                reply_markup=build_back_to_menu_keyboard()
            )

    elif data == "action_sector":
        await query.edit_message_text("⏳ Đang tải dữ liệu ngành...")
        try:
            output_dir = Path(__file__).parent / "output"
            sector_files = sorted(output_dir.glob("sector_rotation_*.json"), reverse=True)

            if sector_files:
                with open(sector_files[0], 'r', encoding='utf-8') as f:
                    sector_data = json.load(f)

                sectors = sector_data.get('sectors', [])[:7]
                lines = ["🏭 *XẾP HẠNG NGÀNH*", "━━━━━━━━━━━━━━━━━━━━━━", ""]

                for i, s in enumerate(sectors, 1):
                    name = s.get('name', s.get('symbol', 'N/A'))
                    rs = s.get('rs_rating', 0)
                    change = s.get('change_1m', 0)
                    emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                    lines.append(f"{emoji} *{name}* - RS: {rs} | {change:+.1f}%")

                text = "\n".join(lines)
            else:
                text = "❌ Chưa có dữ liệu ngành."

            await query.edit_message_text(
                text, parse_mode='Markdown',
                reply_markup=build_back_to_menu_keyboard()
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Lỗi: {str(e)[:100]}",
                reply_markup=build_back_to_menu_keyboard()
            )

    elif data == "action_help":
        help_text = """
❓ *HƯỚNG DẪN SỬ DỤNG*
━━━━━━━━━━━━━━━━━━━━━━

*Bấm nút:*
• 📊 Phân tích mã → Chọn mã phổ biến
• 🏆 Top Picks → Xem top cổ phiếu
• 🏛️ Thị trường → VN-Index
• 🏭 Ngành → Xếp hạng ngành

*Gõ lệnh:*
• `/vn <mã>` - Phân tích đầy đủ
• `/tech <mã>` - Chỉ kỹ thuật
• `/fund <mã>` - Chỉ cơ bản
• `/compare <mã1> <mã2>` - So sánh

*Ví dụ:*
`/vn VCB` `/compare FPT CMG`
"""
        await query.edit_message_text(
            help_text, parse_mode='Markdown',
            reply_markup=build_back_to_menu_keyboard()
        )

    # ─── STOCK SELECTION ───
    elif data.startswith("stock_"):
        symbol = data.replace("stock_", "")
        await query.edit_message_text(
            f"📊 *Phân tích {symbol}*\n\nChọn loại phân tích:",
            parse_mode='Markdown',
            reply_markup=build_analysis_type_keyboard(symbol)
        )

    # ─── ANALYSIS ───
    elif data.startswith("analyze_full_"):
        symbol = data.replace("analyze_full_", "")
        await query.edit_message_text(f"⏳ Đang phân tích đầy đủ {symbol} với AI Claude...")
        try:
            from stock_analyzer import get_stock_analyzer
            analyzer = get_stock_analyzer()
            summary = analyzer.get_quick_summary(symbol)
            await query.edit_message_text(
                summary,
                reply_markup=build_after_analysis_keyboard(symbol)
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Lỗi khi phân tích {symbol}: {str(e)[:100]}",
                reply_markup=build_back_to_menu_keyboard()
            )

    elif data.startswith("analyze_tech_"):
        symbol = data.replace("analyze_tech_", "")
        await query.edit_message_text(f"⏳ Đang phân tích kỹ thuật {symbol}...")
        try:
            from stock_analyzer import get_stock_analyzer
            analyzer = get_stock_analyzer()
            result = analyzer.analyze(symbol)

            if result.error:
                text = f"❌ {result.error}"
            else:
                tech = result.technical
                text = f"""
📉 *TECHNICAL: {symbol}*
━━━━━━━━━━━━━━━━━━━━━━

💰 Giá: {tech.price:,.0f} VND ({tech.change_1d_pct:+.1f}%)
📊 Score: {result.score_technical:.0f}/100

*Moving Averages:*
• MA20: {tech.ma20:,.0f} {'✅' if tech.above_ma20 else '❌'}
• MA50: {tech.ma50:,.0f} {'✅' if tech.above_ma50 else '❌'}
• MA200: {tech.ma200:,.0f} {'✅' if tech.above_ma200 else '❌'}

*Indicators:*
• RSI(14): {tech.rsi:.0f} ({tech.rsi_signal})
• RS Rating: {tech.rs_rating}/100
• Volume: {tech.volume_ratio:.1f}x

*Volume Profile:*
• POC: {tech.poc:,.0f}
"""

            await query.edit_message_text(
                text, parse_mode='Markdown',
                reply_markup=build_after_analysis_keyboard(symbol)
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Lỗi: {str(e)[:100]}",
                reply_markup=build_back_to_menu_keyboard()
            )

    elif data.startswith("analyze_fund_"):
        symbol = data.replace("analyze_fund_", "")
        await query.edit_message_text(f"⏳ Đang phân tích cơ bản {symbol}...")
        try:
            from stock_analyzer import get_stock_analyzer
            analyzer = get_stock_analyzer()
            result = analyzer.analyze(symbol)

            if result.error:
                text = f"❌ {result.error}"
            else:
                fund = result.fundamental
                text = f"""
💼 *FUNDAMENTAL: {symbol}*
━━━━━━━━━━━━━━━━━━━━━━

📊 Score: {result.score_fundamental:.0f}/100

*EPS Growth:*
• Q/Q: {fund.eps_growth_qoq:+.1f}%
• Y/Y: {fund.eps_growth_yoy:+.1f}%

*Revenue Growth:*
• Q/Q: {fund.revenue_growth_qoq:+.1f}%
• Y/Y: {fund.revenue_growth_yoy:+.1f}%

*Profitability:*
• ROE: {fund.roe:.1f}%
• ROA: {fund.roa:.1f}%

*Valuation:*
• P/E: {fund.pe:.1f}
• P/B: {fund.pb:.1f}

*Cash Flow:*
• Quality: {fund.cf_quality}
"""

            await query.edit_message_text(
                text, parse_mode='Markdown',
                reply_markup=build_after_analysis_keyboard(symbol)
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Lỗi: {str(e)[:100]}",
                reply_markup=build_back_to_menu_keyboard()
            )

    # ─── ALERT TOGGLE ───
    elif data == "alert_on":
        alert_subscribers.add(user_id)
        save_subscribers()
        await query.edit_message_text(
            "✅ *Đã bật Alert!*\n\nBạn sẽ nhận báo cáo CANSLIM lúc 16h hàng ngày.",
            parse_mode='Markdown',
            reply_markup=build_back_to_menu_keyboard()
        )

    elif data == "alert_off":
        alert_subscribers.discard(user_id)
        save_subscribers()
        await query.edit_message_text(
            "🔕 *Đã tắt Alert*\n\nBạn sẽ không nhận báo cáo tự động nữa.",
            parse_mode='Markdown',
            reply_markup=build_back_to_menu_keyboard()
        )


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULED SCAN JOB
# ══════════════════════════════════════════════════════════════════════════════

# Timezone Vietnam
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

async def scheduled_scan_job(context):
    """
    Job chạy tự động lúc 16h hàng ngày (thứ 2-6)
    - Chạy run_compare_ai.py
    - Gửi alert cho subscribers
    """
    now = datetime.now(VN_TZ)
    weekday = now.weekday()

    # Chỉ chạy thứ 2-6 (0-4)
    if weekday > 4:
        logger.info(f"Skipping scheduled scan - weekend (weekday={weekday})")
        return

    logger.info("=" * 50)
    logger.info("🚀 STARTING SCHEDULED SCAN AT 16:00")
    logger.info("=" * 50)

    load_subscribers()

    if not alert_subscribers:
        logger.info("No subscribers - skipping scan")
        return

    # Notify subscribers that scan is starting
    for user_id in alert_subscribers:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="⏳ *Đang chạy scan CANSLIM 16h...*\n\nVui lòng chờ khoảng 10-15 phút.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Failed to notify {user_id}: {e}")

    # Run the scan
    try:
        script_path = Path(__file__).parent / "run_compare_ai.py"

        if script_path.exists():
            logger.info(f"Running: {script_path}")

            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(Path(__file__).parent),
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )

            if result.returncode == 0:
                logger.info("✅ Scan completed successfully!")
                status_msg = "✅ Scan hoàn tất!"
            else:
                logger.error(f"Scan failed with code {result.returncode}")
                logger.error(f"stderr: {result.stderr[:500]}")
                status_msg = f"⚠️ Scan hoàn tất với lỗi (code: {result.returncode})"
        else:
            logger.error(f"Script not found: {script_path}")
            status_msg = "❌ Không tìm thấy script scan"

    except subprocess.TimeoutExpired:
        logger.error("Scan timed out after 1 hour")
        status_msg = "⏰ Scan timeout sau 1 giờ"
    except Exception as e:
        logger.error(f"Scan error: {e}")
        status_msg = f"❌ Lỗi: {str(e)[:50]}"

    # Send completion alert to subscribers
    message = f"""
📊 *BÁO CÁO CANSLIM {now.strftime('%d/%m/%Y')}*
━━━━━━━━━━━━━━━━━━━━━━

{status_msg}

💡 Gõ `/top` để xem top picks
💡 Bấm nút để phân tích chi tiết

📧 Chi tiết đã gửi qua email
"""

    for user_id in alert_subscribers:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='Markdown',
                reply_markup=build_main_menu_keyboard()
            )
            logger.info(f"Sent completion alert to {user_id}")
        except Exception as e:
            logger.error(f"Failed to send alert to {user_id}: {e}")

    logger.info("=" * 50)
    logger.info("SCHEDULED SCAN COMPLETED")
    logger.info("=" * 50)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Start bot"""
    if not HAS_TELEGRAM:
        print("❌ python-telegram-bot not installed!")
        print("Run: pip install 'python-telegram-bot>=21.0'")
        return

    print("🤖 Starting CANSLIM Telegram Bot...")
    print(f"   Token: {BOT_TOKEN[:20]}...")
    print(f"   Admin: {ADMIN_USER_ID}")

    # Load subscribers
    load_subscribers()
    print(f"   Subscribers: {len(alert_subscribers)}")

    # Create application
    app = Application.builder().token(BOT_TOKEN).build()

    # Add command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("vn", analyze_stock_command))
    app.add_handler(CommandHandler("tech", technical_command))
    app.add_handler(CommandHandler("fund", fundamental_command))
    app.add_handler(CommandHandler("compare", compare_command))
    app.add_handler(CommandHandler("top", top_command))
    app.add_handler(CommandHandler("market", market_command))
    app.add_handler(CommandHandler("sector", sector_command))
    app.add_handler(CommandHandler("alert", alert_command))
    app.add_handler(CommandHandler("scan", scan_command))  # Admin only

    # Add callback handler for inline buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    # Unknown command handler
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # ─── SETUP SCHEDULED JOB (16:00 daily) ───
    job_queue = app.job_queue

    # Schedule daily scan at 16:00 Vietnam time (Monday-Friday)
    scan_time = dt_time(hour=16, minute=0, second=0, tzinfo=VN_TZ)
    job_queue.run_daily(
        scheduled_scan_job,
        time=scan_time,
        days=(0, 1, 2, 3, 4),  # Monday to Friday
        name="daily_canslim_scan"
    )

    print("\n✅ Bot started! Press Ctrl+C to stop.")
    print("📱 Open Telegram and send /start to your bot")
    print(f"⏰ Scheduled scan: 16:00 daily (Mon-Fri, Vietnam time)\n")

    # Run bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
