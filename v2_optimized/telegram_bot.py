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

NEW - Historical Tracking:
- /foreign <mã> - Xem khối ngoại 20 ngày rolling
- /winrate - Xem win rate của recommendations
- /trades - Xem active trades đang hold
- /pending - Xem pending recommendations
- /backtest - Báo cáo backtest đầy đủ
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
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
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

# Historical Tracking imports
try:
    from historical_foreign_tracker import HistoricalForeignTracker, get_foreign_tracker
    from history_manager import RecommendationHistoryTracker, get_recommendation_tracker
    HAS_TRACKING = True
except ImportError as e:
    HAS_TRACKING = False
    print(f"⚠️ Historical Tracking modules not available: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

# Bot Configuration (đọc từ config → .env)
_cfg = get_config()
BOT_TOKEN = _cfg.telegram.BOT_TOKEN
ADMIN_USER_ID = _cfg.telegram.ADMIN_USER_ID

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
            InlineKeyboardButton("📈 Tracking", callback_data="menu_tracking"),
            InlineKeyboardButton("📢 Alert", callback_data="menu_alert"),
        ],
        [
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


def build_persistent_menu_keyboard():
    """Tạo menu cố định ở dưới (ReplyKeyboard)"""
    keyboard = [
        [KeyboardButton("📊 Menu"), KeyboardButton("🏆 Top Picks")],
        [KeyboardButton("🏛️ Thị trường"), KeyboardButton("📈 Tracking")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)


def parse_top_picks_from_ai_report() -> tuple:
    """Parse top picks từ file AI report (canslim_report_claude_*.md) mới nhất

    Returns:
        tuple: (list of picks, report_date, ai_source)
    """
    import re
    try:
        output_dir = Path(__file__).parent / "output"

        # Tìm file canslim_report mới nhất (ưu tiên Claude)
        claude_files = sorted(output_dir.glob("canslim_report_claude_*.md"), reverse=True)
        gemini_files = sorted(output_dir.glob("canslim_report_gemini_*.md"), reverse=True)

        latest_file = None
        ai_source = "Claude"

        if claude_files and gemini_files:
            # So sánh timestamp, chọn file mới nhất
            claude_time = claude_files[0].stat().st_mtime
            gemini_time = gemini_files[0].stat().st_mtime
            if claude_time >= gemini_time:
                latest_file = claude_files[0]
                ai_source = "Claude"
            else:
                latest_file = gemini_files[0]
                ai_source = "Gemini"
        elif claude_files:
            latest_file = claude_files[0]
            ai_source = "Claude"
        elif gemini_files:
            latest_file = gemini_files[0]
            ai_source = "Gemini"

        if not latest_file:
            return [], None, None

        # Parse filename để lấy ngày
        # Format: canslim_report_claude_20260208_1132.md
        filename = latest_file.name
        date_match = re.search(r'_(\d{8})_(\d{4})\.md$', filename)
        if date_match:
            date_str = date_match.group(1)
            time_str = date_match.group(2)
            report_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} {time_str[:2]}:{time_str[2:]}"
        else:
            report_date = "Unknown"

        # Đọc file và parse bảng Top Picks
        with open(latest_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Tìm bảng Top Picks
        # Format: | Rank | Symbol | Sector | Score | RS | Pattern | Vol✓ | Signal |
        picks = []

        # Pattern để match mỗi row trong bảng
        # | 1 | TCX | Tài chính | 98 | 91 | Cup & Handle | ✓ | ⭐⭐⭐ STRONG BUY |
        row_pattern = re.compile(
            r'\|\s*(\d+)\s*\|\s*([A-Z0-9]+)\s*\|\s*([^|]+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|'
        )

        for match in row_pattern.finditer(content):
            rank = int(match.group(1))
            if rank > 10:
                break

            picks.append({
                'rank': rank,
                'symbol': match.group(2).strip(),
                'sector': match.group(3).strip(),
                'score': int(match.group(4)),
                'rs_rating': int(match.group(5)),
                'pattern': match.group(6).strip(),
                'volume_ok': '✓' in match.group(7),
                'signal': match.group(8).strip(),
            })

        # Sort by rank
        picks = sorted(picks, key=lambda x: x['rank'])[:10]

        return picks, report_date, ai_source

    except Exception as e:
        logger.error(f"Error parsing AI report: {e}")
        return [], None, None


def parse_top_picks_from_json() -> list:
    """Parse top picks - ưu tiên AI report mới nhất, fallback về JSON cũ"""
    # Thử đọc từ AI report trước
    picks, report_date, ai_source = parse_top_picks_from_ai_report()
    if picks:
        return picks

    # Fallback: đọc từ stock_screening JSON
    try:
        output_dir = Path(__file__).parent / "output"
        json_files = sorted(output_dir.glob("stock_screening_*.json"), reverse=True)

        if not json_files:
            return []

        latest_file = json_files[0]
        with open(latest_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        candidates = data.get('candidates', [])
        # Sort by rank
        candidates = sorted(candidates, key=lambda x: x.get('rank', 999))

        picks = []
        for c in candidates[:10]:  # Top 10
            picks.append({
                'rank': c.get('rank', 0),
                'symbol': c.get('symbol', ''),
                'sector': c.get('sector', ''),
                'score': c.get('scores', {}).get('total', 0),
                'signal': c.get('signal', ''),
                'price': c.get('technical', {}).get('price', 0),
                'rs_rating': c.get('technical', {}).get('rs_rating', 0),
                'pattern': c.get('pattern', {}).get('type', 'N/A'),
            })

        return picks
    except Exception as e:
        logger.error(f"Error parsing top picks: {e}")
        return []


def build_tracking_menu_keyboard():
    """Tạo menu tracking/backtest"""
    keyboard = [
        [
            InlineKeyboardButton("📊 Win Rate", callback_data="tracking_winrate"),
            InlineKeyboardButton("💹 Active Trades", callback_data="tracking_trades"),
        ],
        [
            InlineKeyboardButton("⏳ Pending", callback_data="tracking_pending"),
            InlineKeyboardButton("📋 Backtest", callback_data="tracking_backtest"),
        ],
        [
            InlineKeyboardButton("🔙 Menu chính", callback_data="menu_main"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_foreign_stocks_keyboard():
    """Tạo keyboard các mã để xem khối ngoại"""
    # Top stocks to check foreign flow
    foreign_stocks = ["VCB", "FPT", "HPG", "MWG", "VNM", "TCB", "VHM", "MSN"]
    row1 = [InlineKeyboardButton(s, callback_data=f"foreign_{s}") for s in foreign_stocks[:4]]
    row2 = [InlineKeyboardButton(s, callback_data=f"foreign_{s}") for s in foreign_stocks[4:]]
    keyboard = [row1, row2, [InlineKeyboardButton("🔙 Tracking Menu", callback_data="menu_tracking")]]
    return InlineKeyboardMarkup(keyboard)


# ══════════════════════════════════════════════════════════════════════════════
# COMMAND HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /start"""
    user = update.effective_user
    welcome_text = f"""
👋 Chào {user.first_name}!

Tôi là *CANSLIM Stock Bot* - Trợ lý phân tích cổ phiếu Việt Nam với AI Claude Sonnet 4.

🔹 Bấm nút menu ở dưới để sử dụng
🔹 Hoặc gõ `/vn <mã>` để phân tích nhanh

💡 Ví dụ: `/vn FPT` hoặc `/compare VCB BID`
"""
    # Gửi persistent menu keyboard
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=build_persistent_menu_keyboard()
    )
    # Gửi inline menu
    await update.message.reply_text(
        "🏠 *MENU CHÍNH*\n\nChọn chức năng:",
        parse_mode='Markdown',
        reply_markup=build_main_menu_keyboard()
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /help"""
    help_text = """
📚 *Hướng dẫn sử dụng:*

*Phân tích cổ phiếu:*
• `/vn VCB` - Phân tích đầy đủ
• `/tech HPG` - Chỉ kỹ thuật
• `/fund MWG` - Chỉ cơ bản

*So sánh & Tổng hợp:*
• `/compare FPT CMG` - So sánh 2 mã
• `/top` - Top 10 picks
• `/market` - Thị trường
• `/sector` - Xếp hạng ngành

*Tracking & Backtest:*
• `/foreign VCB` - Khối ngoại 20d
• `/winrate` - Win rate recommendations
• `/trades` - Active trades
• `/pending` - Pending picks
• `/backtest` - Báo cáo backtest

*Alert:*
• `/alert on/off` - Bật/tắt alert

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
        # Lấy thông tin chi tiết từ AI report
        picks, report_date, ai_source = parse_top_picks_from_ai_report()

        if not picks:
            # Fallback về JSON
            picks = parse_top_picks_from_json()
            report_date = None
            ai_source = None

        if not picks:
            await update.message.reply_text("❌ Chưa có báo cáo hôm nay. Chạy `/market` để xem tình hình.", parse_mode='Markdown')
            return

        # Header với nguồn AI
        ai_icon = "🔵" if ai_source == "Claude" else "🟢" if ai_source == "Gemini" else "📊"
        ai_label = f"{ai_icon} {ai_source}" if ai_source else "📊 CANSLIM"

        text = f"""
🏆 *TOP PICKS* - {ai_label}
━━━━━━━━━━━━━━━━━━━━━━

"""
        for p in picks[:10]:
            rank = p['rank']
            symbol = p['symbol']
            score = p['score']
            rs = p.get('rs_rating', 0)
            pattern = p.get('pattern', 'N/A')
            signal = p.get('signal', '')
            signal_short = "⭐" if "STRONG" in signal else "✅" if "BUY" in signal else "👀"

            # Rút gọn pattern
            pattern_short = pattern[:12] + ".." if len(pattern) > 14 else pattern

            text += f"{rank}. *{symbol}* {signal_short} Sc:{score} RS:{rs}\n"
            text += f"   └ {pattern_short}\n"

        # Footer với thời gian report
        if report_date:
            text += f"""
━━━━━━━━━━━━━━━━━━━━━━
📅 Báo cáo: {report_date}
💡 Gõ `/vn <mã>` để phân tích chi tiết
"""
        else:
            text += f"""
━━━━━━━━━━━━━━━━━━━━━━
💡 Gõ `/vn <mã>` để phân tích chi tiết
⏰ Cập nhật: {datetime.now().strftime('%H:%M %d/%m')}
"""

        # Build keyboard với các mã top picks để quick access
        top_symbols = [p['symbol'] for p in picks[:8]]
        row1 = [InlineKeyboardButton(s, callback_data=f"stock_{s}") for s in top_symbols[:4]]
        row2 = [InlineKeyboardButton(s, callback_data=f"stock_{s}") for s in top_symbols[4:8]]
        keyboard = [row1, row2, [InlineKeyboardButton("🔙 Menu chính", callback_data="menu_main")]]

        await update.message.reply_text(
            text, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

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


# ══════════════════════════════════════════════════════════════════════════════
# HISTORICAL TRACKING COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

async def foreign_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /foreign <symbol> - Xem khối ngoại 20 ngày"""
    if not HAS_TRACKING:
        await update.message.reply_text("❌ Tính năng tracking chưa được cài đặt.")
        return

    if not context.args:
        await update.message.reply_text(
            "❌ Vui lòng nhập mã cổ phiếu!\nVí dụ: `/foreign VCB`",
            parse_mode='Markdown',
            reply_markup=build_foreign_stocks_keyboard()
        )
        return

    symbol = context.args[0].upper()
    await update.message.reply_text(f"⏳ Đang tải dữ liệu khối ngoại {symbol}...")

    try:
        tracker = get_foreign_tracker()
        analysis = tracker.calculate_rolling_metrics(symbol)

        if analysis:
            net_20d = analysis.net_value_20d / 1e9  # Convert to billions
            avg_daily = analysis.avg_daily_net_20d / 1e9
            coverage = analysis.data_coverage_pct

            trend_emoji = "🟢" if analysis.trend == "ACCUMULATING" else "🔴" if analysis.trend == "DISTRIBUTING" else "⚪"

            text = f"""
🌐 *KHỐI NGOẠI: {symbol}*
━━━━━━━━━━━━━━━━━━━━━━

*20 Ngày Rolling:*
• Net Value: {net_20d:+.1f} tỷ VND
• Avg Daily: {avg_daily:+.2f} tỷ/ngày
• Buy Days: {analysis.buy_days_count}
• Sell Days: {analysis.sell_days_count}

*Phân tích:*
• Trend: {trend_emoji} {analysis.trend}
• Intensity: {analysis.intensity_score:.0f}/100
• Data Coverage: {coverage:.0f}%

⏰ Cập nhật: {datetime.now().strftime('%H:%M %d/%m')}
"""
        else:
            text = f"❌ Chưa có dữ liệu khối ngoại cho {symbol}. Cần chạy scan để thu thập."

        await update.message.reply_text(text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in foreign command {symbol}: {e}")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


async def winrate_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /winrate - Xem win rate của recommendations"""
    if not HAS_TRACKING:
        await update.message.reply_text("❌ Tính năng tracking chưa được cài đặt.")
        return

    await update.message.reply_text("⏳ Đang tính toán win rate...")

    try:
        tracker = get_recommendation_tracker()
        win_rates = tracker.calculate_win_rates()

        overall = win_rates.get('overall_win_rate', 0) * 100
        total = win_rates.get('total_completed', 0)
        wins = win_rates.get('total_wins', 0)

        text = f"""
📊 *WIN RATE ANALYSIS*
━━━━━━━━━━━━━━━━━━━━━━

*Overall Performance:*
• Win Rate: {overall:.1f}%
• Completed Trades: {total}
• Winning Trades: {wins}

*By Signal Type:*
"""
        by_signal = win_rates.get('by_signal', {})
        for signal, stats in by_signal.items():
            wr = stats.get('win_rate', 0) * 100
            cnt = stats.get('count', 0)
            text += f"• {signal}: {wr:.0f}% ({cnt} trades)\n"

        text += f"\n⏰ Cập nhật: {datetime.now().strftime('%H:%M %d/%m')}"

        await update.message.reply_text(text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in winrate command: {e}")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


async def trades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /trades - Xem active trades đang hold"""
    if not HAS_TRACKING:
        await update.message.reply_text("❌ Tính năng tracking chưa được cài đặt.")
        return

    await update.message.reply_text("⏳ Đang tải active trades...")

    try:
        tracker = get_recommendation_tracker()
        master = tracker._load_tracking_master()

        # Filter triggered trades
        triggered = [t for t in master.get('trades', []) if t.get('status') == 'TRIGGERED']

        if not triggered:
            text = "📭 Không có trade nào đang active."
        else:
            text = f"""
💹 *ACTIVE TRADES ({len(triggered)})*
━━━━━━━━━━━━━━━━━━━━━━

"""
            for t in triggered[:10]:  # Top 10
                symbol = t.get('symbol', 'N/A')
                entry = t.get('price_at_recommendation', 0)
                pnl = t.get('profit_loss_pct', 0)
                pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                text += f"{pnl_emoji} *{symbol}*: Entry {entry:,.0f} | P&L: {pnl:+.1f}%\n"

        await update.message.reply_text(text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in trades command: {e}")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /pending - Xem pending recommendations"""
    if not HAS_TRACKING:
        await update.message.reply_text("❌ Tính năng tracking chưa được cài đặt.")
        return

    await update.message.reply_text("⏳ Đang tải pending recommendations...")

    try:
        tracker = get_recommendation_tracker()
        master = tracker._load_tracking_master()

        # Filter pending trades
        pending = [t for t in master.get('trades', []) if t.get('status') == 'PENDING']

        if not pending:
            text = "📭 Không có recommendation nào đang pending."
        else:
            text = f"""
⏳ *PENDING RECOMMENDATIONS ({len(pending)})*
━━━━━━━━━━━━━━━━━━━━━━

"""
            for t in pending[:10]:  # Top 10
                symbol = t.get('symbol', 'N/A')
                buy_point = t.get('buy_point', 0)
                stop_loss = t.get('stop_loss', 0)
                signal = t.get('signal', 'N/A')
                text += f"• *{symbol}* ({signal})\n  Buy: {buy_point:,.0f} | Stop: {stop_loss:,.0f}\n"

        await update.message.reply_text(text, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in pending command: {e}")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


async def backtest_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho /backtest - Báo cáo backtest đầy đủ"""
    if not HAS_TRACKING:
        await update.message.reply_text("❌ Tính năng tracking chưa được cài đặt.")
        return

    await update.message.reply_text("⏳ Đang tạo báo cáo backtest...")

    try:
        tracker = get_recommendation_tracker()
        report = tracker.generate_backtest_report()

        # Truncate if too long for Telegram
        if len(report) > 4000:
            report = report[:4000] + "\n\n... (truncated)"

        await update.message.reply_text(report, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in backtest command: {e}")
        await update.message.reply_text(f"❌ Lỗi: {str(e)[:100]}")


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


async def handle_text_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler cho persistent keyboard buttons"""
    text = update.message.text

    if text == "📊 Menu":
        await update.message.reply_text(
            "🏠 *MENU CHÍNH*\n\nChọn chức năng:",
            parse_mode='Markdown',
            reply_markup=build_main_menu_keyboard()
        )
    elif text == "🏆 Top Picks":
        await top_command(update, context)
    elif text == "🏛️ Thị trường":
        await market_command(update, context)
    elif text == "📈 Tracking":
        if HAS_TRACKING:
            await update.message.reply_text(
                "📈 *TRACKING & BACKTEST*\n\nTheo dõi hiệu suất:",
                parse_mode='Markdown',
                reply_markup=build_tracking_menu_keyboard()
            )
        else:
            await update.message.reply_text("❌ Tính năng tracking chưa được cài đặt.")
    else:
        # Có thể là mã cổ phiếu
        symbol = text.upper().strip()
        if len(symbol) == 3 and symbol.isalpha():
            # Likely a stock symbol
            context.args = [symbol]
            await analyze_stock_command(update, context)


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
            # Lấy thông tin chi tiết từ AI report
            picks, report_date, ai_source = parse_top_picks_from_ai_report()

            if not picks:
                # Fallback về JSON
                picks = parse_top_picks_from_json()
                report_date = None
                ai_source = None

            if picks:
                # Header với nguồn AI
                ai_icon = "🔵" if ai_source == "Claude" else "🟢" if ai_source == "Gemini" else "📊"
                ai_label = f"{ai_icon} {ai_source}" if ai_source else "📊 CANSLIM"

                text = f"""
🏆 *TOP PICKS* - {ai_label}
━━━━━━━━━━━━━━━━━━━━━━

"""
                for p in picks[:10]:
                    rank = p['rank']
                    symbol = p['symbol']
                    score = p['score']
                    rs = p.get('rs_rating', 0)
                    pattern = p.get('pattern', 'N/A')
                    signal = p.get('signal', '')
                    signal_short = "⭐" if "STRONG" in signal else "✅" if "BUY" in signal else "👀"

                    # Rút gọn pattern
                    pattern_short = pattern[:12] + ".." if len(pattern) > 14 else pattern

                    text += f"{rank}. *{symbol}* {signal_short} Sc:{score} RS:{rs}\n"
                    text += f"   └ {pattern_short}\n"

                # Footer với thời gian report
                if report_date:
                    text += f"\n📅 Báo cáo: {report_date}"
                else:
                    text += f"\n⏰ {datetime.now().strftime('%H:%M %d/%m')}"

                # Keyboard với top symbols
                top_symbols = [p['symbol'] for p in picks[:8]]
                row1 = [InlineKeyboardButton(s, callback_data=f"stock_{s}") for s in top_symbols[:4]]
                row2 = [InlineKeyboardButton(s, callback_data=f"stock_{s}") for s in top_symbols[4:8]]
                keyboard = [row1, row2, [InlineKeyboardButton("🔙 Menu chính", callback_data="menu_main")]]

                await query.edit_message_text(
                    text, parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.edit_message_text(
                    "❌ Chưa có báo cáo hôm nay. Chạy scan để tạo báo cáo.",
                    reply_markup=build_back_to_menu_keyboard()
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
• 📊 Phân tích → Chọn mã
• 🏆 Top Picks → Top picks
• 🏛️ Thị trường → VN-Index
• 📈 Tracking → Win rate, trades

*Gõ lệnh:*
• `/vn <mã>` - Phân tích đầy đủ
• `/foreign <mã>` - Khối ngoại
• `/winrate` - Win rate
• `/backtest` - Báo cáo backtest

*Ví dụ:*
`/vn VCB` `/foreign FPT`
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

    # ─── TRACKING MENU ───
    elif data == "menu_tracking":
        await query.edit_message_text(
            "📈 *TRACKING & BACKTEST*\n\n"
            "Theo dõi hiệu suất recommendations và khối ngoại:",
            parse_mode='Markdown',
            reply_markup=build_tracking_menu_keyboard()
        )

    elif data == "tracking_winrate":
        if not HAS_TRACKING:
            await query.edit_message_text(
                "❌ Tính năng tracking chưa được cài đặt.",
                reply_markup=build_back_to_menu_keyboard()
            )
            return

        await query.edit_message_text("⏳ Đang tính toán win rate...")
        try:
            tracker = get_recommendation_tracker()
            win_rates = tracker.calculate_win_rates()

            overall = win_rates.get('overall_win_rate', 0) * 100
            total = win_rates.get('total_completed', 0)
            wins = win_rates.get('total_wins', 0)

            text = f"""
📊 *WIN RATE ANALYSIS*
━━━━━━━━━━━━━━━━━━━━━━

*Overall Performance:*
• Win Rate: {overall:.1f}%
• Completed Trades: {total}
• Winning Trades: {wins}

*By Signal Type:*
"""
            by_signal = win_rates.get('by_signal', {})
            for signal, stats in by_signal.items():
                wr = stats.get('win_rate', 0) * 100
                cnt = stats.get('count', 0)
                text += f"• {signal}: {wr:.0f}% ({cnt} trades)\n"

            text += f"\n⏰ {datetime.now().strftime('%H:%M %d/%m')}"

            await query.edit_message_text(
                text, parse_mode='Markdown',
                reply_markup=build_tracking_menu_keyboard()
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Lỗi: {str(e)[:100]}",
                reply_markup=build_tracking_menu_keyboard()
            )

    elif data == "tracking_trades":
        if not HAS_TRACKING:
            await query.edit_message_text(
                "❌ Tính năng tracking chưa được cài đặt.",
                reply_markup=build_back_to_menu_keyboard()
            )
            return

        await query.edit_message_text("⏳ Đang tải active trades...")
        try:
            tracker = get_recommendation_tracker()
            master = tracker._load_tracking_master()

            triggered = [t for t in master.get('trades', []) if t.get('status') == 'TRIGGERED']

            if not triggered:
                text = "📭 *ACTIVE TRADES*\n━━━━━━━━━━━━━━━━━━━━━━\n\nKhông có trade nào đang active."
            else:
                text = f"""
💹 *ACTIVE TRADES ({len(triggered)})*
━━━━━━━━━━━━━━━━━━━━━━

"""
                for t in triggered[:8]:
                    symbol = t.get('symbol', 'N/A')
                    entry = t.get('price_at_recommendation', 0)
                    pnl = t.get('profit_loss_pct', 0)
                    pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"
                    text += f"{pnl_emoji} *{symbol}*: {entry:,.0f} | {pnl:+.1f}%\n"

            await query.edit_message_text(
                text, parse_mode='Markdown',
                reply_markup=build_tracking_menu_keyboard()
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Lỗi: {str(e)[:100]}",
                reply_markup=build_tracking_menu_keyboard()
            )

    elif data == "tracking_pending":
        if not HAS_TRACKING:
            await query.edit_message_text(
                "❌ Tính năng tracking chưa được cài đặt.",
                reply_markup=build_back_to_menu_keyboard()
            )
            return

        await query.edit_message_text("⏳ Đang tải pending recommendations...")
        try:
            tracker = get_recommendation_tracker()
            master = tracker._load_tracking_master()

            pending = [t for t in master.get('trades', []) if t.get('status') == 'PENDING']

            if not pending:
                text = "📭 *PENDING RECOMMENDATIONS*\n━━━━━━━━━━━━━━━━━━━━━━\n\nKhông có recommendation nào pending."
            else:
                text = f"""
⏳ *PENDING ({len(pending)})*
━━━━━━━━━━━━━━━━━━━━━━

"""
                for t in pending[:8]:
                    symbol = t.get('symbol', 'N/A')
                    buy_point = t.get('buy_point', 0)
                    signal = t.get('signal', 'N/A')
                    text += f"• *{symbol}* ({signal}): Buy {buy_point:,.0f}\n"

            await query.edit_message_text(
                text, parse_mode='Markdown',
                reply_markup=build_tracking_menu_keyboard()
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Lỗi: {str(e)[:100]}",
                reply_markup=build_tracking_menu_keyboard()
            )

    elif data == "tracking_backtest":
        if not HAS_TRACKING:
            await query.edit_message_text(
                "❌ Tính năng tracking chưa được cài đặt.",
                reply_markup=build_back_to_menu_keyboard()
            )
            return

        await query.edit_message_text("⏳ Đang tạo báo cáo backtest...")
        try:
            tracker = get_recommendation_tracker()
            report = tracker.generate_backtest_report()

            # Truncate for Telegram
            if len(report) > 3500:
                report = report[:3500] + "\n\n... (Gõ /backtest để xem đầy đủ)"

            await query.edit_message_text(
                report, parse_mode='Markdown',
                reply_markup=build_tracking_menu_keyboard()
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Lỗi: {str(e)[:100]}",
                reply_markup=build_tracking_menu_keyboard()
            )

    # ─── FOREIGN FLOW ───
    elif data.startswith("foreign_"):
        symbol = data.replace("foreign_", "")

        if not HAS_TRACKING:
            await query.edit_message_text(
                "❌ Tính năng tracking chưa được cài đặt.",
                reply_markup=build_back_to_menu_keyboard()
            )
            return

        await query.edit_message_text(f"⏳ Đang tải khối ngoại {symbol}...")
        try:
            tracker = get_foreign_tracker()
            analysis = tracker.calculate_rolling_metrics(symbol)

            if analysis:
                net_20d = analysis.net_value_20d / 1e9
                avg_daily = analysis.avg_daily_net_20d / 1e9
                coverage = analysis.data_coverage_pct

                trend_emoji = "🟢" if analysis.trend == "ACCUMULATING" else "🔴" if analysis.trend == "DISTRIBUTING" else "⚪"

                text = f"""
🌐 *KHỐI NGOẠI: {symbol}*
━━━━━━━━━━━━━━━━━━━━━━

*20 Ngày Rolling:*
• Net: {net_20d:+.1f} tỷ VND
• Avg: {avg_daily:+.2f} tỷ/ngày
• Buy Days: {analysis.buy_days_count}
• Sell Days: {analysis.sell_days_count}

*Phân tích:*
• Trend: {trend_emoji} {analysis.trend}
• Intensity: {analysis.intensity_score:.0f}/100
• Data: {coverage:.0f}%
"""
            else:
                text = f"❌ Chưa có data khối ngoại cho {symbol}."

            await query.edit_message_text(
                text, parse_mode='Markdown',
                reply_markup=build_foreign_stocks_keyboard()
            )
        except Exception as e:
            await query.edit_message_text(
                f"❌ Lỗi: {str(e)[:100]}",
                reply_markup=build_tracking_menu_keyboard()
            )


# ══════════════════════════════════════════════════════════════════════════════
# SCHEDULED SCAN JOB
# ══════════════════════════════════════════════════════════════════════════════

# Timezone Vietnam
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')


def is_market_holiday(date=None) -> tuple:
    """
    Kiểm tra ngày nghỉ lễ sàn chứng khoán Việt Nam
    Returns: (is_holiday: bool, reason: str)
    """
    if date is None:
        date = datetime.now(VN_TZ).date()

    # Ngày nghỉ lễ cố định hàng năm
    fixed_holidays = {
        (1, 1): "Tết Dương lịch",
        (4, 30): "Giải phóng miền Nam",
        (5, 1): "Quốc tế Lao động",
        (9, 2): "Quốc khánh",
    }

    # Ngày nghỉ Tết Nguyên Đán 2026
    # Mùng 1 Tết: 17/02/2026 (Thứ Ba)
    # Phiên giao dịch cuối: 13/02/2026 (Thứ Sáu)
    # Phiên giao dịch đầu tiên sau Tết: 23/02/2026 (Thứ Hai)
    tet_2026 = [
        (2026, 2, 14), (2026, 2, 15), (2026, 2, 16),
        (2026, 2, 17), (2026, 2, 18), (2026, 2, 19), (2026, 2, 20),
        (2026, 2, 21), (2026, 2, 22),
    ]

    # Ngày nghỉ bù
    extra_holidays_2026 = [
        (2026, 1, 2),   # Nghỉ bù Tết Dương lịch
        (2026, 4, 29),  # Nghỉ bù 30/4
        (2026, 5, 4),   # Nghỉ bù 1/5
        (2026, 9, 3),   # Nghỉ bù Quốc khánh
    ]

    # Kiểm tra Tết Nguyên Đán
    for y, m, d in tet_2026:
        if date.year == y and date.month == m and date.day == d:
            return True, "Tết Nguyên Đán"

    # Kiểm tra ngày nghỉ bù
    for y, m, d in extra_holidays_2026:
        if date.year == y and date.month == m and date.day == d:
            return True, "Nghỉ bù"

    # Kiểm tra ngày lễ cố định
    key = (date.month, date.day)
    if key in fixed_holidays:
        return True, fixed_holidays[key]

    return False, ""


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

    # Kiểm tra ngày nghỉ lễ
    is_holiday, holiday_name = is_market_holiday(now.date())
    if is_holiday:
        logger.info(f"Skipping scheduled scan - holiday: {holiday_name}")
        load_subscribers()
        for user_id in alert_subscribers:
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"📅 *Hôm nay nghỉ lễ: {holiday_name}*\n\nThị trường đóng cửa, không có scan.",
                    parse_mode='Markdown'
                )
            except:
                pass
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

    # Run the scan (use optimized V2 if available)
    try:
        # Prefer V2 (data 1x, AI parallel) - faster
        script_path = Path(__file__).parent / "run_compare_ai_v2.py"
        if not script_path.exists():
            script_path = Path(__file__).parent / "run_compare_ai.py"

        if script_path.exists():
            logger.info(f"Running: {script_path}")

            result = subprocess.run(
                [sys.executable, str(script_path)],
                cwd=str(Path(__file__).parent),
                capture_output=True,
                text=True,
                timeout=7200  # 2 hour timeout (scan all 7 sectors with 2 AI)
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
        logger.error("Scan timed out after 2 hours")
        status_msg = "⏰ Scan timeout sau 2 giờ"
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

    # Historical Tracking commands
    app.add_handler(CommandHandler("foreign", foreign_command))
    app.add_handler(CommandHandler("winrate", winrate_command))
    app.add_handler(CommandHandler("trades", trades_command))
    app.add_handler(CommandHandler("pending", pending_command))
    app.add_handler(CommandHandler("backtest", backtest_command))

    # Add callback handler for inline buttons
    app.add_handler(CallbackQueryHandler(button_callback))

    # Handle persistent keyboard text messages (Menu, Top Picks, etc.)
    menu_filter = filters.TEXT & filters.Regex(r'^(📊 Menu|🏆 Top Picks|🏛️ Thị trường|📈 Tracking)$')
    app.add_handler(MessageHandler(menu_filter, handle_text_menu))

    # Unknown command handler
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # ─── SETUP SCHEDULED JOBS ───
    job_queue = app.job_queue

    # Schedule daily scan at 16:00 Vietnam time (Monday-Friday)
    scan_time = dt_time(hour=16, minute=0, second=0, tzinfo=VN_TZ)
    job_queue.run_daily(
        scheduled_scan_job,
        time=scan_time,
        days=(0, 1, 2, 3, 4),  # Monday to Friday
        name="daily_canslim_scan"
    )

    # Schedule daily restart at 05:00 AM to prevent stale state
    async def daily_restart_job(context: ContextTypes.DEFAULT_TYPE):
        """Restart bot daily to prevent memory leaks and stale state"""
        logger.info("🔄 Daily restart triggered at 05:00 AM")
        try:
            # Notify admin
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text="🔄 Bot đang restart theo lịch 05:00 hàng ngày..."
            )
        except:
            pass

        # Restart the process
        import sys
        os.execv(sys.executable, [sys.executable] + sys.argv)

    restart_time = dt_time(hour=5, minute=0, second=0, tzinfo=VN_TZ)
    job_queue.run_daily(
        daily_restart_job,
        time=restart_time,
        days=(0, 1, 2, 3, 4, 5, 6),  # Every day
        name="daily_restart"
    )

    # Set bot commands menu
    async def post_init(application):
        await application.bot.set_my_commands([
            BotCommand("start", "🏠 Menu chính"),
            BotCommand("vn", "📊 Phân tích mã (VD: /vn VCB)"),
            BotCommand("top", "🏆 Top picks hôm nay"),
            BotCommand("market", "🏛️ Tình hình thị trường"),
            BotCommand("foreign", "🌐 Khối ngoại (VD: /foreign VCB)"),
            BotCommand("winrate", "📈 Win rate tracking"),
            BotCommand("backtest", "📋 Backtest report"),
            BotCommand("help", "❓ Hướng dẫn"),
        ])

    app.post_init = post_init

    print("\n✅ Bot started! Press Ctrl+C to stop.")
    print("📱 Open Telegram and send /start to your bot")
    print(f"⏰ Scheduled scan: 16:00 daily (Mon-Fri, Vietnam time)")
    print(f"🔄 Auto-restart: 05:00 daily (to prevent stale state)\n")

    # Run bot
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
