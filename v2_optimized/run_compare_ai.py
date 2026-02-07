#!/usr/bin/env python3
"""
Run Full Pipeline với cả Claude và Gemini AI
Tạo bảng so sánh kết quả giữa 2 AI
"""

import os
import sys
import time
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG - Tùy chỉnh phạm vi scan
# ══════════════════════════════════════════════════════════════════════════════

# Scan tất cả 7 ngành thay vì chỉ top sectors theo RS Rating
SCAN_ALL_SECTORS = True

# Danh sách tất cả 7 ngành hợp lệ
ALL_SECTORS = ['VNFIN', 'VNREAL', 'VNMAT', 'VNIT', 'VNHEAL', 'VNCOND', 'VNCONS']

# ══════════════════════════════════════════════════════════════════════════════

# Import modules
from config import get_config, APIKeys
from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified as create_m1_config
from module2_sector_rotation_v3 import SectorRotationModule, create_config_from_unified as create_m2_config
from module3_stock_screener_v1 import StockScreenerModule, create_config_from_unified as create_m3_config
from history_manager import HistoryManager
from email_notifier import EmailNotifier


def run_with_provider(provider: str, output_dir: str):
    """
    Chạy pipeline với một AI provider cụ thể
    """
    print(f"\n{'='*80}")
    print(f"🤖 RUNNING PIPELINE WITH {provider.upper()}")
    print(f"{'='*80}\n")
    
    # Set environment variable to override AI provider
    os.environ['AI_PROVIDER'] = provider
    
    # Get API key for the specific provider
    provider_keys = {
        'claude': APIKeys.CLAUDE,
        'gemini': APIKeys.GEMINI,
        'deepseek': APIKeys.DEEPSEEK,
        'groq': APIKeys.GROQ,
        'openai': APIKeys.OPENAI,
    }
    api_key = provider_keys.get(provider.lower(), '')
    
    if not api_key:
        print(f"⚠️ Không có API key cho {provider.upper()} trong config.py")
    else:
        print(f"✓ API key {provider.upper()}: {api_key[:20]}...")
    
    config = get_config()
    timestamp = datetime.now()
    
    # History context
    history_manager = HistoryManager(output_dir)
    history_context = history_manager.get_ai_context_v2()
    
    results = {
        'provider': provider,
        'timestamp': timestamp.strftime("%Y-%m-%d %H:%M"),
        'market_report': None,
        'sector_report': None,
        'screener_report': None
    }
    
    try:
        # === MODULE 1: MARKET TIMING ===
        print(f"[{provider}] Module 1: Market Timing...")
        m1_config = create_m1_config()
        m1_config.SAVE_REPORT = False
        m1_config.AI_PROVIDER = provider
        m1_config.AI_API_KEY = api_key  # Set API key!
            
        m1_module = MarketTimingModule(m1_config)
        results['market_report'] = m1_module.run(history_context)
        print(f"   ✓ Market Score: {results['market_report'].market_score}/100")
        print(f"   ✓ Market Color: {results['market_report'].market_color}")
        
        # === MODULE 2: SECTOR ROTATION ===
        print(f"[{provider}] Module 2: Sector Rotation...")
        m2_config = create_m2_config()
        m2_config.SAVE_REPORT = False
        m2_config.AI_PROVIDER = provider
        m2_config.AI_API_KEY = api_key  # Set API key!
            
        m2_module = SectorRotationModule(m2_config)
        results['sector_report'] = m2_module.run(
            market_context=results['market_report'].__dict__ if results['market_report'] else None,
            history_context=history_context
        )
        
        if hasattr(results['sector_report'], 'sectors') and results['sector_report'].sectors:
            top_sectors = [s.symbol if hasattr(s, 'symbol') else s.code for s in results['sector_report'].sectors[:3]]
            print(f"   ✓ Top 3 sectors: {top_sectors}")
        
        # === MODULE 3: STOCK SCREENER ===
        print(f"[{provider}] Module 3: Stock Screener...")

        # Quyết định target_sectors dựa trên config
        if SCAN_ALL_SECTORS:
            # Scan tất cả 7 ngành
            target_sectors = ALL_SECTORS.copy()
            print(f"   📊 SCAN_ALL_SECTORS=True → Scanning all 7 sectors")
        else:
            # Chỉ scan top sectors theo RS Rating từ Module 2
            target_sectors = []
            if hasattr(results['sector_report'], 'sectors') and results['sector_report'].sectors:
                for sector in results['sector_report'].sectors[:6]:
                    sector_code = getattr(sector, 'code', getattr(sector, 'symbol', None))
                    if sector_code:
                        target_sectors.append(sector_code)
            print(f"   📊 SCAN_ALL_SECTORS=False → Scanning top {len(target_sectors)} sectors by RS")
        
        m3_config = create_m3_config()
        m3_config.SAVE_REPORT = False
        m3_config.AI_PROVIDER = provider
        m3_config.AI_API_KEY = api_key  # Set API key!
            
        m3_module = StockScreenerModule(m3_config)
        results['screener_report'] = m3_module.run(
            target_sectors=target_sectors,
            market_context=results['market_report'].__dict__ if results['market_report'] else None,
            history_context=history_context
        )
        
        if hasattr(results['screener_report'], 'top_picks'):
            print(f"   ✓ Top 5 picks: {[c.symbol for c in results['screener_report'].top_picks[:5]]}")
        
        # === GENERATE INDIVIDUAL REPORT ===
        report_content = _generate_ai_report(results, provider)
        report_file = f"{output_dir}/canslim_report_{provider}_{timestamp.strftime('%Y%m%d_%H%M')}.md"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"   📄 Report saved: {report_file}")
        
        # Store for reference
        results['report_file'] = report_file
        results['report_content'] = report_content
        
        # === SEND EMAIL FOR THIS AI ===
        try:
            notifier = EmailNotifier()
            if notifier.config.ENABLED:
                print(f"   📧 Gửi email báo cáo {provider.upper()}...")
                # Temporarily modify subject to include AI name
                original_prefix = notifier.config.SUBJECT_PREFIX
                notifier.config.SUBJECT_PREFIX = f"[{provider.upper()}] CANSLIM REPORT"
                notifier.send_report(report_content, report_file)
                notifier.config.SUBJECT_PREFIX = original_prefix
        except Exception as e:
            print(f"   ⚠️ Lỗi gửi email {provider}: {e}")
        
        print(f"\n✅ [{provider.upper()}] Pipeline complete!")
        
    except Exception as e:
        print(f"❌ [{provider}] Error: {e}")
        import traceback
        traceback.print_exc()
        
    return results


def _convert_json_to_markdown(text: str) -> str:
    """
    Convert JSON-formatted AI output to readable markdown.
    If the text contains a JSON block AND other text, it replaces the block.
    If the text is ONLY JSON, it converts the whole thing.
    """
    import json
    import re
    
    if not text:
        return text
    
    # helper for recursion
    def dict_to_markdown(d, level=0):
        md = ""
        if isinstance(d, dict):
            for key, value in d.items():
                key_formatted = key.replace('_', ' ').title()
                if isinstance(value, dict):
                    md += f"\n{'#' * (level + 2)} {key_formatted}\n"
                    md += dict_to_markdown(value, level + 1)
                elif isinstance(value, list):
                    md += f"\n**{key_formatted}:**\n"
                    for item in value:
                        if isinstance(item, dict):
                            for k, v in item.items():
                                md += f"- **{k}:** {v}\n"
                            md += "\n"
                        else:
                            md += f"- {item}\n"
                else:
                    md += f"- **{key_formatted}:** {value}\n"
        elif isinstance(d, list):
            for item in d:
                md += dict_to_markdown(item, level)
        else:
            md += str(d)
        return md

    # Try to find ```json ... ``` block
    json_block_match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if json_block_match:
        try:
            json_content = json_block_match.group(1)
            data = json.loads(json_content)
            converted = dict_to_markdown(data)
            # Replace ONLY the JSON block in the original text
            return text.replace(json_block_match.group(0), converted)
        except:
            return text
            
    # Try if whole text is JSON
    text_stripped = text.strip()
    if text_stripped.startswith('{') and text_stripped.endswith('}'):
        try:
            data = json.loads(text_stripped)
            return dict_to_markdown(data)
        except:
            return text
            
    return text


def _generate_ai_report(results: dict, provider: str) -> str:
    """Tạo báo cáo full pipeline cho từng AI"""
    timestamp = results.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M"))
    
    market_report = results.get('market_report')
    sector_report = results.get('sector_report')
    screener_report = results.get('screener_report')
    
    content = f"""# 📊 CANSLIM FULL REPORT [{provider.upper()}]
**Ngày:** {timestamp}

---

# 🎯 PHẦN 1: MARKET TIMING (Module 1)

## Tổng quan thị trường

"""
    
    if market_report:
        vni = getattr(market_report, 'vnindex', None)
        content += f"""| Chỉ số | Giá trị |
|--------|---------|
| **Market Color** | {market_report.market_color} |
| **Score** | {market_report.market_score}/100 |
| **VN-Index** | {vni.price:,.0f} ({vni.change_1d:+.2f}%) | 
| **RSI(14)** | {vni.rsi_14:.1f} |
| **Trend** | {getattr(market_report, 'trend_status', 'N/A')} |

"""
        # Include FULL AI Analysis (no truncation!) - Convert JSON to markdown if needed
        if hasattr(market_report, 'ai_analysis') and market_report.ai_analysis:
            ai_analysis = _convert_json_to_markdown(market_report.ai_analysis)
            content += f"""## 🤖 AI Analysis - Market Timing
{ai_analysis}

"""
    else:
        content += "⚠️ Không có dữ liệu Market Timing\n\n"
    
    content += """---

# 🏭 PHẦN 2: SECTOR ROTATION (Module 2)

## Bảng xếp hạng ngành

"""
    
    if sector_report and hasattr(sector_report, 'sectors') and sector_report.sectors:
        content += """| Rank | Ngành | Change 1D | RS Score |
|------|-------|-----------|----------|
"""
        for i, sector in enumerate(sector_report.sectors[:7], 1):
            code = getattr(sector, 'code', 'N/A')
            name = getattr(sector, 'name', code)
            rs = getattr(sector, 'rs_rating', 0)
            change_1d = getattr(sector, 'change_1d', 0)
            content += f"| {i} | {name} | {change_1d:+.2f}% | {rs} |\n"
        
        content += "\n"
        
        # Include FULL AI Analysis (no truncation!) - Convert JSON to markdown if needed
        if hasattr(sector_report, 'ai_analysis') and sector_report.ai_analysis:
            sector_ai = _convert_json_to_markdown(sector_report.ai_analysis)
            content += f"""## 🤖 AI Analysis - Sector Rotation
{sector_ai}

"""
    else:
        content += "⚠️ Không có dữ liệu Sector Rotation\n\n"
    
    content += """---

# 📈 PHẦN 3: STOCK SCREENER (Module 3)

"""
    
    if screener_report:
        # Stats
        content += f"""## Screening Stats

| Metric | Value |
|--------|-------|
| **Target Sectors** | {', '.join(screener_report.target_sectors) if screener_report.target_sectors else 'N/A'} |
| **Total Scanned** | {screener_report.total_scanned} |
| **Passed Technical** | {screener_report.passed_technical} |
| **Final Candidates** | {len(screener_report.candidates) if screener_report.candidates else 0} |

"""
        
        if screener_report.top_picks:
            content += """## 🏆 Top Picks

| Rank | Symbol | Sector | Score | RS | Pattern | Vol✓ | Signal |
|------|--------|--------|-------|----| --------|------|--------|
"""
            for i, stock in enumerate(screener_report.top_picks[:10], 1):
                symbol = getattr(stock, 'symbol', 'N/A')
                sector = getattr(stock, 'sector_name', 'N/A')
                
                # Get the correct score (ai_score first, then score_total)
                score = getattr(stock, 'ai_score', None)
                if score is None:
                    score = getattr(stock, 'score_total', 0)
                
                # Get RS from technical data
                technical = getattr(stock, 'technical', None)
                rs = 0
                if technical:
                    rs = getattr(technical, 'rs_rating', 0)
                
                # Get pattern name properly
                pattern_data = getattr(stock, 'pattern', None)
                pattern_str = "No Pattern"
                if pattern_data:
                    pattern_type = getattr(pattern_data, 'pattern_type', None)
                    if pattern_type:
                        pattern_str = getattr(pattern_type, 'value', str(pattern_type))
                
                # Get signal name properly
                signal = getattr(stock, 'signal', None)
                signal_str = "➖ NEUTRAL"
                if signal:
                    signal_str = getattr(signal, 'value', str(signal))
                
                # Volume confirmed
                vol_confirmed = "⭕"
                if pattern_data and getattr(pattern_data, 'volume_confirmed', False):
                    vol_confirmed = "✓"
                elif pattern_data and getattr(pattern_data, 'has_dryup', False):
                    vol_confirmed = "🚀"
                
                content += f"| {i} | {symbol} | {sector} | {score:.0f} | {rs} | {pattern_str} | {vol_confirmed} | {signal_str} |\n"
            
            # --- ADDED: Foreign Trade Summary Table (Mid-Session Parity) ---
            content += "\n### 💰 Khối ngoại (Session):\n"
            content += "| Symbol | Buy | Sell | Net (VND) |\n|---|---|---|---|\n"
            for stock in screener_report.top_picks[:10]:
                f_buy = getattr(stock.technical, 'foreign_buy_value', 0)
                f_sell = getattr(stock.technical, 'foreign_sell_value', 0)
                f_net = getattr(stock.technical, 'foreign_net_value', 0)
                f_icon = "🟢" if f_net > 0 else ("🔴" if f_net < 0 else "⚪")
                content += f"| **{stock.symbol}** | {f_buy/1e6:,.1f}M | {f_sell/1e6:,.1f}M | {f_icon} {f_net/1e6:+,.1f}M |\n"
            # -------------------------------------------------------------
            
            # Detail for each stock
            content += "\n## 📝 Chi tiết Top 5 Candidates\n\n"
            
            for i, stock in enumerate(screener_report.top_picks[:5], 1):
                symbol = getattr(stock, 'symbol', 'N/A')
                sector_name = getattr(stock, 'sector_name', 'N/A')
                
                # Technical data
                tech = getattr(stock, 'technical', None)
                price = tech.price if tech else 0
                rs = tech.rs_rating if tech else 0
                rsi = tech.rsi_14 if tech else 0
                vol_ratio = tech.volume_ratio if tech else 0
                above_ma50 = "✅ TRÊN MA50" if tech and tech.above_ma50 else "❌ DƯỚI MA50"
                
                # Fundamental data
                funda = getattr(stock, 'fundamental', None)
                roe = funda.roe if funda else 0
                roa = funda.roa if funda else 0
                eps_qoq = funda.eps_growth_qoq if funda else 0
                eps_yoy = funda.eps_growth_yoy if funda else 0
                eps_3y = funda.eps_growth_3y if funda else 0
                c_score = funda.c_score if funda else 0
                a_score = funda.a_score if funda else 0
                conf = funda.confidence_score if funda else 50
                
                # Pattern data
                pattern_data = getattr(stock, 'pattern', None)
                pattern_type = pattern_data.pattern_type.value if pattern_data and pattern_data.pattern_type else "No Pattern"
                pattern_quality = pattern_data.pattern_quality if pattern_data else 0
                vol_score = pattern_data.volume_score if pattern_data else 0
                has_shakeout = "✅ Shakeout detected" if pattern_data and pattern_data.has_shakeout else "⭕ No shakeout"
                has_dryup = "✅ Dry-up" if pattern_data and pattern_data.has_dryup else "⭕ No dry-up"
                breakout_ready = "✅ Ready for breakout" if pattern_data and pattern_data.breakout_ready else "⏳ Waiting for confirmation"
                
                # Scores
                score_funda = getattr(stock, 'score_fundamental', 0)
                score_tech = getattr(stock, 'score_technical', 0)
                score_pattern = getattr(stock, 'score_pattern', 0)
                score_news = getattr(stock, 'score_news', 0)
                score_total = getattr(stock, 'score_total', 0)
                
                # Signal
                signal = getattr(stock, 'signal', None)
                signal_str = signal.value if signal else "NEUTRAL"
                
                content += f"""### {i}. {symbol} - {sector_name}

**Scores:** Fundamental {score_funda:.0f} | Technical {score_tech:.0f} | Pattern {score_pattern:.0f} | News {score_news:.0f} | **Total: {score_total:.0f}**

**📊 Fundamental (V3 Enhanced):**
- ROE: {roe:.1f}% | ROA: {roa:.1f}%
- EPS Q/Q: {eps_qoq:+.1f}% | EPS Y/Y: {eps_yoy:+.1f}%
- EPS 3Y CAGR: {eps_3y:+.1f}%
- C Score: {c_score:.0f} | A Score: {a_score:.0f}
- Confidence: {conf:.0f}%

**📈 Technical:**
- Giá: {price:,.0f} | RS: {rs} | RSI: {rsi:.1f}
- MA: {above_ma50} | Volume Ratio: {vol_ratio:.2f}x
"""
                
                # VWAP (if available)
                if tech and hasattr(tech, 'vwap') and tech.vwap > 0:
                    vwap = tech.vwap
                    vwap_pos = getattr(tech, 'price_vs_vwap', 'N/A')
                    vwap_score = getattr(tech, 'vwap_score', 50)
                    content += f"- VWAP: {vwap:,.0f} | Vị thế: {vwap_pos} | VWAP Score: {vwap_score:.0f}/100\n"
                
                # ATR for trading plan
                atr_pct = getattr(tech, 'atr_pct', 3.0) if tech else 3.0
                content += f"- ATR(14): {atr_pct:.1f}% (biến động)\n"
                
                content += f"""
**Pattern:** {pattern_type} (Quality: {pattern_quality:.0f})
- 📊 Volume Score: {vol_score:.0f}/80
- {has_shakeout}
- {has_dryup}
- {breakout_ready}
"""
                
                # Foreign Trade Section
                f_buy = getattr(tech, 'foreign_buy_value', 0)
                f_sell = getattr(tech, 'foreign_sell_value', 0)
                f_net = getattr(tech, 'foreign_net_value', 0)
                f_icon = "🟢" if f_net > 0 else ("🔴" if f_net < 0 else "⚪")
                
                content += f"""
**💰 Khối ngoại (Session):**
- Mua: {f_buy/1e6:,.1f}M VND
- Bán: {f_sell/1e6:,.1f}M VND
- Net: {f_icon} {f_net/1e6:+,.1f}M VND
"""
                
                # News section (if available)
                news_data = getattr(stock, 'news', None)
                if news_data:
                    articles = getattr(news_data, 'articles', [])
                    sentiment = getattr(news_data, 'sentiment', 'neutral')
                    sentiment_score = getattr(news_data, 'sentiment_score', 0)
                    key_topics = getattr(news_data, 'key_topics', [])
                    
                    if articles:
                        sentiment_icon = "🟢" if sentiment_score > 0.1 else ("🔴" if sentiment_score < -0.1 else "🟡")
                        content += f"\n**📰 News ({len(articles)} bài):**\n"
                        for article in articles[:3]:
                            title = getattr(article, 'title', str(article)) if hasattr(article, 'title') else str(article)[:80]
                            url = getattr(article, 'url', '#') if hasattr(article, 'url') else '#'
                            content += f"- [{title[:80]}...]({url})\n"
                        content += f"- Sentiment: {sentiment_icon} {sentiment.upper()} ({sentiment_score:+.2f})\n"
                        if key_topics:
                            content += f"- Topics: {', '.join(key_topics[:5])}\n"
                
                # Trading Plan (dynamic based on ATR and pattern)
                buy_point = getattr(pattern_data, 'buy_point', price * 1.02) if pattern_data else price * 1.02
                buy_zone_high = buy_point * 1.05
                stop_loss_price = getattr(stock, 'stop_loss', 0)
                if stop_loss_price == 0:
                    stop_loss_price = buy_point * (1 - atr_pct/100)
                target_1 = buy_point * 1.10
                target_2 = buy_point * 1.15
                
                content += f"""
**📈 TRADING PLAN (Dynamic):**
| Level | Giá | % | Lý do |
|-------|-----|---|-------|
| 🎯 **Buy Point** | {buy_point:,.0f} | - | Breakout từ pattern |
| 🛒 **Buy Zone** | {buy_point:,.0f} - {buy_zone_high:,.0f} | +5% | Mua trong vùng này |
| 🛑 **Stop Loss** | {stop_loss_price:,.0f} | -{atr_pct:.1f}% | ATR-based |
| 💰 **Target 1** | {target_1:,.0f} | +10% | R:R ≥ 1:3 |
| 💰 **Target 2** | {target_2:,.0f} | +15% | Trailing stop sau T1 |
"""
                
                # AI Analysis for each stock (if available)
                stock_ai = getattr(stock, 'ai_analysis', None)
                if stock_ai and len(str(stock_ai)) > 50:
                    content += f"""
**🤖 AI Analysis:**
{stock_ai}
"""
                
                content += f"""
**Signal:** {signal_str}

---

"""
        
        # Include FULL AI Summary (no truncation!)
        if hasattr(screener_report, 'ai_analysis') and screener_report.ai_analysis:
            content += f"""## 🤖 AI Summary - Stock Screener
{screener_report.ai_analysis}

"""
    else:
        content += "⚠️ Không có dữ liệu Stock Screener\n\n"
    
    content += f"""---

# ⚠️ DISCLAIMER

*Báo cáo này được tạo tự động bởi hệ thống CANSLIM Scanner.*
*Thông tin chỉ mang tính chất tham khảo, không phải khuyến nghị đầu tư.*
*Nhà đầu tư tự chịu trách nhiệm với quyết định giao dịch của mình.*

---
**Generated by {provider.upper()} AI:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    
    return content


def generate_comparison(claude_results: dict, gemini_results: dict, output_dir: str):
    """
    Tạo bảng so sánh giữa Claude và Gemini
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    
    content = f"""# 🔬 SO SÁNH AI: CLAUDE vs GEMINI
**Ngày:** {datetime.now().strftime("%d/%m/%Y %H:%M")}

---

## 📊 TỔNG QUAN

| Metric | 🔵 Claude | 🟢 Gemini |
|--------|-----------|-----------|
| **Thời gian chạy** | {claude_results.get('timestamp', 'N/A')} | {gemini_results.get('timestamp', 'N/A')} |

---

## 🎯 MODULE 1: MARKET TIMING

| Chỉ số | Claude | Gemini | So sánh |
|--------|--------|--------|---------|
"""
    
    # Market Timing comparison
    claude_market = claude_results.get('market_report')
    gemini_market = gemini_results.get('market_report')
    
    if claude_market and gemini_market:
        content += f"| **Market Score** | {claude_market.market_score}/100 | {gemini_market.market_score}/100 | {'=' if claude_market.market_score == gemini_market.market_score else ('Claude>' if claude_market.market_score > gemini_market.market_score else 'Gemini>')} |\n"
        content += f"| **Market Color** | {claude_market.market_color} | {gemini_market.market_color} | {'✅ Đồng nhất' if claude_market.market_color == gemini_market.market_color else '⚠️ Khác'} |\n"
        
        # AI Analysis length
        claude_ai = claude_market.ai_analysis if hasattr(claude_market, 'ai_analysis') else ''
        gemini_ai = gemini_market.ai_analysis if hasattr(gemini_market, 'ai_analysis') else ''
        content += f"| **AI Analysis (ký tự)** | {len(claude_ai):,} | {len(gemini_ai):,} | - |\n"
    
        content += f"""
### 🔵 Claude AI Analysis (trích):
```
{claude_ai[:2000] if claude_ai else 'N/A'}...
```

### 🟢 Gemini AI Analysis (trích):
```
{gemini_ai[:2000] if gemini_ai else 'N/A'}...
```
"""
    
    content += """
---

## 🏭 MODULE 2: SECTOR ROTATION

| Chỉ số | Claude | Gemini |
|--------|--------|--------|
"""
    
    claude_sector = claude_results.get('sector_report')
    gemini_sector = gemini_results.get('sector_report')
    
    if claude_sector and gemini_sector:
        claude_top3 = [getattr(s, 'name', getattr(s, 'symbol', 'N/A')) for s in claude_sector.sectors[:3]] if hasattr(claude_sector, 'sectors') else []
        gemini_top3 = [getattr(s, 'name', getattr(s, 'symbol', 'N/A')) for s in gemini_sector.sectors[:3]] if hasattr(gemini_sector, 'sectors') else []
        content += f"| **Top 3 ngành** | {', '.join(claude_top3)} | {', '.join(gemini_top3)} |\n"
        
        claude_ai = claude_sector.ai_analysis if hasattr(claude_sector, 'ai_analysis') and claude_sector.ai_analysis else ''
        gemini_ai = gemini_sector.ai_analysis if hasattr(gemini_sector, 'ai_analysis') and gemini_sector.ai_analysis else ''
        content += f"| **AI Analysis (ký tự)** | {len(claude_ai):,} | {len(gemini_ai):,} |\n"
    
    content += """
---

## 📈 MODULE 3: STOCK SCREENER

### Top 10 Picks Comparison

| Rank | Claude | Gemini | Match? |
|------|--------|--------|--------|
"""
    
    claude_screener = claude_results.get('screener_report')
    gemini_screener = gemini_results.get('screener_report')
    
    claude_picks = []
    gemini_picks = []
    
    if claude_screener and hasattr(claude_screener, 'top_picks'):
        claude_picks = [c.symbol for c in claude_screener.top_picks[:10]]
    if gemini_screener and hasattr(gemini_screener, 'top_picks'):
        gemini_picks = [c.symbol for c in gemini_screener.top_picks[:10]]
    
    for i in range(10):
        c_symbol = claude_picks[i] if i < len(claude_picks) else '-'
        g_symbol = gemini_picks[i] if i < len(gemini_picks) else '-'
        match = '✅' if c_symbol == g_symbol else '❌'
        content += f"| {i+1} | {c_symbol} | {g_symbol} | {match} |\n"
    
    # Overlap calculation
    if claude_picks and gemini_picks:
        common = set(claude_picks) & set(gemini_picks)
        overlap_pct = len(common) / max(len(claude_picks), len(gemini_picks)) * 100
        
        content += f"""
### Phân tích overlap

| Metric | Giá trị |
|--------|---------|
| **Số mã trùng** | {len(common)}/10 |
| **Tỷ lệ overlap** | {overlap_pct:.0f}% |
| **Mã chung** | {', '.join(common) if common else 'Không có'} |
| **Chỉ có Claude** | {', '.join(set(claude_picks) - set(gemini_picks)) or '-'} |
| **Chỉ có Gemini** | {', '.join(set(gemini_picks) - set(claude_picks)) or '-'} |
"""

    if claude_picks and gemini_picks:
        # Add Foreign Trade comparison table
        content += "\n### 💰 Foreign Trade (Comparison)\n\n"
        content += "| Symbol | Claude (Net) | Gemini (Net) | Consensus |\n|--------|--------------|--------------|-----------|\n"
        
        # Extract all unique symbols from top picks of both
        all_symbols = sorted(list(set(claude_picks) | set(gemini_picks)))
        
        # Helper to get net value for a symbol from a screener report
        def get_net_val(report, symbol):
            if not report or not hasattr(report, 'candidates'):
                return None
            for c in report.candidates:
                if c.symbol == symbol:
                    return getattr(c.technical, 'foreign_net_value', 0)
            return None

        for sym in all_symbols:
            c_net = get_net_val(claude_screener, sym)
            g_net = get_net_val(gemini_screener, sym)
            
            c_str = f"{c_net/1e6:+,.1f}M" if c_net is not None else "-"
            g_str = f"{g_net/1e6:+,.1f}M" if g_net is not None else "-"
            
            # Consensus
            consensus = "⚪ Neutral"
            if c_net is not None and g_net is not None:
                if c_net > 0 and g_net > 0: consensus = "🟢 Both BUY"
                elif c_net < 0 and g_net < 0: consensus = "🔴 Both SELL"
                elif c_net * g_net < 0: consensus = "🟡 Mixed"
            elif c_net is not None:
                consensus = "🟢 BUY" if c_net > 0 else "🔴 SELL"
            elif g_net is not None:
                consensus = "🟢 BUY" if g_net > 0 else "🔴 SELL"
                
            content += f"| **{sym}** | {c_str} | {g_str} | {consensus} |\n"

    content += f"""
---

## 🎯 KẾT LUẬN

### Điểm mạnh mỗi AI:

| AI | Điểm mạnh | Điểm yếu |
|----|-----------|----------|
| 🔵 **Claude** | Phân tích chi tiết, reasoning tốt, ít hallucination | Chi phí cao hơn |
| 🟢 **Gemini** | Miễn phí, nhanh, phù hợp dùng hàng ngày | Có thể ít chi tiết hơn |

### Khuyến nghị sử dụng:

- **Phân tích hàng ngày:** Gemini (free tier)
- **Báo cáo quan trọng:** Claude (chất lượng cao)
- **Xác nhận kết quả:** Chạy cả 2 và so sánh

---
*Report generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""
    
    # Save to file
    output_file = f"{output_dir}/ai_comparison_{timestamp}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n📄 Comparison saved to: {output_file}")
    return output_file, content


def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🔬 AI COMPARISON: CLAUDE vs GEMINI                        ║
║              Chạy full pipeline với cả 2 AI và so sánh kết quả               ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    config = get_config()
    output_dir = config.output.OUTPUT_DIR
    
    start_time = time.time()
    
    # Run with Claude
    claude_results = run_with_provider('claude', output_dir)
    
    # Small delay to avoid rate limiting
    print("\n⏳ Chờ 30s trước khi chạy Gemini...")
    time.sleep(30)
    
    # Run with Gemini
    gemini_results = run_with_provider('gemini', output_dir)
    
    # Generate comparison
    output_file, content = generate_comparison(claude_results, gemini_results, output_dir)
    
    elapsed = time.time() - start_time
    
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         🎉 HOÀN THÀNH SO SÁNH!                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  📄 Output: {output_file:<52} ║
║  ⏱️  Thời gian: {elapsed/60:.1f} phút                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Send Email Notification for AI Comparison
    try:
        notifier = EmailNotifier()
        if notifier.config.ENABLED:
            print("\n📧 Gửi email báo cáo AI Comparison...")
            # Use specific subject for comparison
            original_prefix = notifier.config.SUBJECT_PREFIX
            notifier.config.SUBJECT_PREFIX = "[AI COMPARISON] CLAUDE vs GEMINI"
            notifier.send_report(content, output_file)
            notifier.config.SUBJECT_PREFIX = original_prefix
    except Exception as e:
        print(f"⚠️ Lỗi gửi email: {e}")
    
    return output_file


if __name__ == "__main__":
    main()
