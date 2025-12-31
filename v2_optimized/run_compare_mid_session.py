#!/usr/bin/env python3
"""
Run Mid-Session Pipeline with both Claude and Gemini AI
Create comparison table between the two AI providers for Market Timing and Sector Rotation.
"""

import os
import sys
import time
import json
from datetime import datetime

# Import modules
from config import get_config, APIKeys
from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified as create_m1_config
from module2_sector_rotation_v3 import SectorRotationModule, create_config_from_unified as create_m2_config
from history_manager import HistoryManagerV2 as HistoryManager
from module3_stock_screener_v1 import StockScreenerModule, create_config_from_unified as create_m3_config
from email_notifier import EmailNotifier


def run_mid_session_with_provider(provider: str, output_dir: str):
    """
    Run mid-session pipeline with a specific AI provider
    """
    print(f"\n{'='*80}")
    print(f"🤖 RUNNING MID-SESSION PIPELINE WITH {provider.upper()}")
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
        print(f"⚠️ No API key for {provider.upper()} in config.py")
    else:
        print(f"✓ API key {provider.upper()}: {api_key[:20]}...")
    
    timestamp = datetime.now()
    
    # History context
    history_manager = HistoryManager(output_dir)
    history_context = history_manager.get_ai_context_v2()
    
    results = {
        'provider': provider,
        'timestamp': timestamp.strftime("%Y-%m-%d %H:%M"),
        'market_report': None,
        'sector_report': None
    }
    
    try:
        # === MODULE 1: MARKET TIMING ===
        print(f"[{provider}] Module 1: Market Timing...")
        m1_config = create_m1_config()
        m1_config.SAVE_REPORT = False
        m1_config.AI_PROVIDER = provider
        m1_config.AI_API_KEY = api_key
        m1_config.IS_MID_SESSION = True
            
        m1_module = MarketTimingModule(m1_config)
        results['market_report'] = m1_module.run(history_context)
        print(f"   ✓ Market Score: {results['market_report'].market_score}/100")
        print(f"   ✓ Market Color: {results['market_report'].market_color}")
        
        # === MODULE 2: SECTOR ROTATION ===
        print(f"[{provider}] Module 2: Sector Rotation...")
        m2_config = create_m2_config()
        m2_config.SAVE_REPORT = False
        m2_config.AI_PROVIDER = provider
        m2_config.AI_API_KEY = api_key
        m2_config.IS_MID_SESSION = True
            
        m2_module = SectorRotationModule(m2_config)
        market_context_dict = results['market_report'].to_context() if hasattr(results['market_report'], 'to_context') else {}
        results['sector_report'] = m2_module.run(market_context=market_context_dict, history_context=history_context)
        
        # === MODULE 3: STOCK SCREENER ===
        print(f"[{provider}] Module 3: Stock Screener...")
        m3_config = create_m3_config()
        m3_config.SAVE_REPORT = False
        m3_config.AI_PROVIDER = provider
        m3_config.AI_API_KEY = api_key
        # Note: M3 doesn't have IS_MID_SESSION yet, but it will use the market context provided
            
        m3_module = StockScreenerModule(m3_config)
        results['screener_report'] = m3_module.run(market_context=market_context_dict, history_context=history_context)
        
        if hasattr(results['sector_report'], 'sectors') and results['sector_report'].sectors:
            top_sectors = [s.symbol if hasattr(s, 'symbol') else s.code for s in results['sector_report'].sectors[:3]]
            print(f"   ✓ Top 3 sectors: {top_sectors}")
        
        # === GENERATE INDIVIDUAL REPORT ===
        report_content = _generate_mid_session_ai_report(results, provider)
        report_file = f"{output_dir}/canslim_mid_session_{provider}_{timestamp.strftime('%Y%m%d_%H%M')}.md"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"   📄 Report saved: {report_file}")
        
        # === SEND EMAIL FOR THIS AI ===
        try:
            notifier = EmailNotifier()
            if notifier.config.ENABLED:
                print(f"   📧 Gửi email báo cáo {provider.upper()} (Mid-Session)...")
                # Temporarily modify subject
                original_prefix = notifier.config.SUBJECT_PREFIX
                notifier.config.SUBJECT_PREFIX = f"[MID-SESSION {provider.upper()}] CANSLIM REPORT"
                notifier.send_report(report_content, report_file)
                notifier.config.SUBJECT_PREFIX = original_prefix
        except Exception as e:
            print(f"   ⚠️ Lỗi gửi email {provider}: {e}")
        
        # Store for reference
        results['report_file'] = report_file
        results['report_content'] = report_content
        
        print(f"\n✅ [{provider.upper()}] Mid-session Pipeline complete!")
        
    except Exception as e:
        print(f"❌ [{provider}] Error: {e}")
        import traceback
        traceback.print_exc()
        
    return results


def _convert_json_to_markdown(text: str) -> str:
    """Same as in run_compare_ai.py"""
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


def _generate_mid_session_ai_report(results: dict, provider: str) -> str:
    """Tạo báo cáo mid-session cho từng AI"""
    timestamp = results.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M"))
    market_report = results.get('market_report')
    sector_report = results.get('sector_report')
    screener_report = results.get('screener_report')
    
    content = f"""# 📊 CANSLIM MID-SESSION REPORT [{provider.upper()}]
**Ngày:** {timestamp}

---

# 🎯 PHẦN 1: MARKET TIMING (Module 1)

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
        if hasattr(market_report, 'ai_analysis') and market_report.ai_analysis:
            ai_analysis = _convert_json_to_markdown(market_report.ai_analysis)
            content += f"## 🤖 AI Analysis - Market Timing\n{ai_analysis}\n\n"
    else:
        content += "⚠️ Không có dữ liệu Market Timing\n\n"
    
    content += "---\n\n# 🏭 PHẦN 2: SECTOR ROTATION (Module 2)\n\n"
    if sector_report and hasattr(sector_report, 'sectors') and sector_report.sectors:
        content += "| Rank | Ngành | Change 1D | RS Score |\n|------|-------|-----------|----------|\n"
        for i, sector in enumerate(sector_report.sectors[:10], 1):
            name = getattr(sector, 'name', getattr(sector, 'code', 'N/A'))
            rs = getattr(sector, 'rs_rating', 0)
            change_1d = getattr(sector, 'change_1d', 0)
            content += f"| {i} | {name} | {change_1d:+.2f}% | {rs} |\n"
        
        if hasattr(sector_report, 'ai_analysis') and sector_report.ai_analysis:
            sector_ai = _convert_json_to_markdown(sector_report.ai_analysis)
            content += f"\n## 🤖 AI Analysis - Sector Rotation\n{sector_ai}\n\n"
    content += "---\n\n# 📈 PHẦN 3: STOCK SCREENER (Module 3)\n\n"
    if screener_report:
        content += f"| Metric | Value |\n|--------|-------|\n"
        content += f"| **Total Scanned** | {screener_report.total_scanned} |\n"
        content += f"| **Passed Tech** | {screener_report.passed_technical} |\n"
        content += f"| **Final Candidates** | {len(screener_report.candidates)} |\n\n"
        
        if screener_report.top_picks:
            content += "### 🏆 Top Picks\n\n"
            content += "| Rank | Symbol | Score | RS | Signal |\n|------|--------|-------|----|--------|\n"
            for i, stock in enumerate(screener_report.top_picks[:5], 1):
                content += f"| {i} | {stock.symbol} | {stock.ai_score if hasattr(stock, 'ai_score') and stock.ai_score else stock.score_total:.0f} | {stock.technical.rs_rating} | {stock.signal.value} |\n"
            
            content += "\n### 💰 Foreign Trade (Top Picks)\n"
            content += "| Symbol | Buy | Sell | Net (VND) |\n|---|---|---|---|\n"
            for stock in screener_report.top_picks[:5]:
                f_buy = getattr(stock.technical, 'foreign_buy_value', 0)
                f_sell = getattr(stock.technical, 'foreign_sell_value', 0)
                f_net = getattr(stock.technical, 'foreign_net_value', 0)
                f_icon = "🟢" if f_net > 0 else ("🔴" if f_net < 0 else "⚪")
                content += f"| **{stock.symbol}** | {f_buy/1e6:,.1f}M | {f_sell/1e6:,.1f}M | {f_icon} {f_net/1e6:+,.1f}M |\n"
            
            if hasattr(screener_report, 'ai_analysis') and screener_report.ai_analysis:
                content += f"\n## 🤖 AI Analysis - Stock Screener\n{screener_report.ai_analysis}\n\n"
    else:
        content += "⚠️ Không có dữ liệu Stock Screener\n\n"
        
    content += f"""---
# ⚠️ DISCLAIMER
*Báo cáo này được tạo tự động bởi hệ thống CANSLIM Scanner (Mid-Session).*
**Generated by {provider.upper()} AI:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""
    return content


def generate_mid_session_comparison(claude_results: dict, gemini_results: dict, output_dir: str):
    """
    Tạo bảng so sánh mid-session giữa Claude và Gemini
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    
    content = f"""# 🔬 SO SÁNH AI MID-SESSION: CLAUDE vs GEMINI
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
    
    claude_market = claude_results.get('market_report')
    gemini_market = gemini_results.get('market_report')
    
    if claude_market and gemini_market:
        content += f"| **Market Score** | {claude_market.market_score}/100 | {gemini_market.market_score}/100 | {'=' if claude_market.market_score == gemini_market.market_score else ('Claude>' if claude_market.market_score > gemini_market.market_score else 'Gemini>')} |\n"
        content += f"| **Market Color** | {claude_market.market_color} | {gemini_market.market_color} | {'✅ Đồng nhất' if claude_market.market_color == gemini_market.market_color else '⚠️ Khác'} |\n"
        
        claude_ai = claude_market.ai_analysis if hasattr(claude_market, 'ai_analysis') else ''
        gemini_ai = gemini_market.ai_analysis if hasattr(gemini_market, 'ai_analysis') else ''
        content += f"| **AI Analysis (ký tự)** | {len(claude_ai):,} | {len(gemini_ai):,} | - |\n"
        
        content += f"""
### 🔵 Claude Market Analysis (trích):
```
{claude_ai[:1000] if claude_ai else 'N/A'}...
```

### 🟢 Gemini Market Analysis (trích):
```
{gemini_ai[:1000] if gemini_ai else 'N/A'}...
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

| Chỉ số | Claude | Gemini |
|--------|--------|--------|
"""
    claude_screener = claude_results.get('screener_report')
    gemini_screener = gemini_results.get('screener_report')
    
    if claude_screener and gemini_screener:
        claude_picks = [c.symbol for c in claude_screener.top_picks[:5]] if hasattr(claude_screener, 'top_picks') else []
        gemini_picks = [c.symbol for c in gemini_screener.top_picks[:5]] if hasattr(gemini_screener, 'top_picks') else []
        content += f"| **Top 5 Picks** | {', '.join(claude_picks)} | {', '.join(gemini_picks)} |\n"
        
        common = set(claude_picks) & set(gemini_picks)
        content += f"| **Overlap** | {len(common)}/5 | - |\n"

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
## 🎯 KẾT LUẬN MID-SESSION

- **Sự đồng thuận:** {'Cao' if claude_market and gemini_market and claude_market.market_color == gemini_market.market_color else 'Cần lưu ý'}
- **Đánh giá Claude:** {claude_market.market_score if claude_market else 'N/A'}/100
- **Đánh giá Gemini:** {gemini_market.market_score if gemini_market else 'N/A'}/100

---
*Report generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""
    
    output_file = f"{output_dir}/ai_comparison_mid_session_{timestamp}.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n📄 Comparison saved to: {output_file}")
    return output_file, content


def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                🔬 MID-SESSION AI COMPARISON: CLAUDE vs GEMINI                ║
║      Chạy Market Timing & Sector Rotation với cả 2 AI và so sánh             ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    config = get_config()
    output_dir = config.output.OUTPUT_DIR
    start_time = time.time()
    
    # Run with Claude
    claude_results = run_mid_session_with_provider('claude', output_dir)
    
    # Small delay to avoid rate limiting
    print("\n⏳ Chờ 15s trước khi chạy Gemini...")
    time.sleep(15)
    
    # Run with Gemini
    gemini_results = run_mid_session_with_provider('gemini', output_dir)
    
    # Generate comparison
    output_file, content = generate_mid_session_comparison(claude_results, gemini_results, output_dir)
    
    elapsed = time.time() - start_time
    
    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                     🎉 HOÀN THÀNH SO SÁNH GIỮA PHIÊN!                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  📄 Output: {output_file:<52} ║
║  ⏱️  Thời gian: {elapsed/60:.1f} phút                                            ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Send Email Notification
    try:
        notifier = EmailNotifier()
        if notifier.config.ENABLED:
            print("\n📧 Gửi email báo cáo Mid-Session AI Comparison...")
            original_prefix = notifier.config.SUBJECT_PREFIX
            notifier.config.SUBJECT_PREFIX = "[MID-SESSION AI COMPARISON] CLAUDE vs GEMINI"
            notifier.send_report(content, output_file)
            notifier.config.SUBJECT_PREFIX = original_prefix
    except Exception as e:
        print(f"⚠️ Lỗi gửi email: {e}")
    
    return output_file


if __name__ == "__main__":
    main()
