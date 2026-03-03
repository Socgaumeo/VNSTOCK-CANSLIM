#!/usr/bin/env python3
"""
Run Full Pipeline với cả Claude và Gemini AI - OPTIMIZED VERSION

Cải tiến:
- Module 1 & 2: Tải data 1 lần, chỉ chạy AI analysis cho 2 provider
- Module 3: Chạy 1 lần với AI disabled, sau đó chạy AI ranking riêng

Performance: ~30-40 phút thay vì 60-80 phút
"""

import os
import sys
import time
import copy
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, Tuple

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

SCAN_ALL_SECTORS = True
ALL_SECTORS = ['VNFIN', 'VNREAL', 'VNMAT', 'VNIT', 'VNHEAL', 'VNCOND', 'VNCONS']

# ══════════════════════════════════════════════════════════════════════════════

from config import get_config, APIKeys
from module1_market_timing_v2 import MarketTimingAnalyzer, MarketTimingAIGenerator, create_config_from_unified as create_m1_config
from module2_sector_rotation_v3 import SectorRotationAnalyzer, SectorRotationAIGenerator, create_config_from_unified as create_m2_config
from module3_stock_screener_v1 import StockScreenerModule, StockAIAnalyzer, create_config_from_unified as create_m3_config
from history_manager import HistoryManager
from email_notifier import EmailNotifier


def _generate_minimal_report(results: dict, provider: str) -> str:
    """
    Fallback report generator when main generator fails.
    Creates a simple but functional report.
    """
    timestamp = results.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M"))
    market_report = results.get('market_report')
    sector_report = results.get('sector_report')
    screener_report = results.get('screener_report')

    content = f"""# 📊 CANSLIM REPORT [{provider.upper()}]
**Ngày:** {timestamp}

---

## 🎯 MODULE 1: MARKET TIMING

"""
    if market_report:
        content += f"""| Chỉ số | Giá trị |
|--------|---------|
| **Market Score** | {getattr(market_report, 'market_score', 'N/A')}/100 |
| **Market Color** | {getattr(market_report, 'market_color', 'N/A')} |
| **Trend** | {getattr(market_report, 'trend_status', 'N/A')} |

"""
        vni = getattr(market_report, 'vnindex', None)
        if vni:
            content += f"""| **VN-Index** | {getattr(vni, 'price', 0):,.0f} ({getattr(vni, 'change_1d', 0):+.2f}%) |
| **RSI(14)** | {getattr(vni, 'rsi_14', 0):.1f} |

"""
        ai_analysis = getattr(market_report, 'ai_analysis', '')
        if ai_analysis:
            content += f"""### AI Analysis
{ai_analysis}

"""

    content += """---

## 🏭 MODULE 2: SECTOR ROTATION

"""
    if sector_report and hasattr(sector_report, 'sectors') and sector_report.sectors:
        content += """| Rank | Ngành | RS Score |
|------|-------|----------|
"""
        for i, sector in enumerate(sector_report.sectors[:7], 1):
            name = getattr(sector, 'name', getattr(sector, 'code', 'N/A'))
            rs = getattr(sector, 'rs_rating', 0)
            content += f"| {i} | {name} | {rs} |\n"

        ai_analysis = getattr(sector_report, 'ai_analysis', '')
        if ai_analysis:
            content += f"""

### AI Analysis
{ai_analysis}

"""

    content += """---

## 📈 MODULE 3: STOCK SCREENER

"""
    if screener_report:
        content += f"""| Metric | Value |
|--------|-------|
| **Total Scanned** | {getattr(screener_report, 'total_scanned', 0)} |
| **Candidates** | {len(getattr(screener_report, 'candidates', []))} |

"""
        top_picks = getattr(screener_report, 'top_picks', [])
        if top_picks:
            content += """### Top Picks

| Rank | Symbol | Sector | Score |
|------|--------|--------|-------|
"""
            for i, stock in enumerate(top_picks[:10], 1):
                symbol = getattr(stock, 'symbol', 'N/A')
                sector = getattr(stock, 'sector_name', 'N/A')
                score = getattr(stock, 'ai_score', getattr(stock, 'score_total', 0))
                content += f"| {i} | {symbol} | {sector} | {score:.0f} |\n"

        ai_analysis = getattr(screener_report, 'ai_analysis', '')
        if ai_analysis:
            content += f"""

### AI Analysis
{ai_analysis}

"""

    content += f"""---

*Report generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
*Provider: {provider.upper()}*
"""
    return content


def collect_all_data(output_dir: str) -> Tuple[any, any, any, str]:
    """
    Thu thập TẤT CẢ data 1 lần duy nhất (không chạy AI)

    Returns: (market_data, sector_data, stock_data, history_context)
    """
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    📊 PHASE 1: DATA COLLECTION                               ║
║                    (1 lần duy nhất, KHÔNG chạy AI)                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    # History context
    history_manager = HistoryManager(output_dir)
    history_context = history_manager.get_ai_context_v2()

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 1: Market Data
    # ═══════════════════════════════════════════════════════════════════════
    print(f"\n{'─'*60}")
    print("📊 Step 1: Market Timing Data")
    print(f"{'─'*60}")

    m1_config = create_m1_config()
    m1_config.SAVE_REPORT = False

    market_analyzer = MarketTimingAnalyzer(m1_config)
    market_data = market_analyzer.collect_data()
    market_data = market_analyzer.collect_technical_signals(market_data)

    print(f"   ✓ VN-Index: {market_data.vnindex.price:,.0f} ({market_data.vnindex.change_1d:+.2f}%)")
    print(f"   ✓ RSI: {market_data.vnindex.rsi_14:.1f}")
    print(f"   ✓ Key signals: {len(market_data.key_signals)}")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 2: Sector Data
    # ═══════════════════════════════════════════════════════════════════════
    print(f"\n{'─'*60}")
    print("📊 Step 2: Sector Rotation Data")
    print(f"{'─'*60}")

    m2_config = create_m2_config()
    m2_config.SAVE_REPORT = False

    sector_analyzer = SectorRotationAnalyzer(m2_config)
    sector_data = sector_analyzer.analyze(market_data.__dict__)

    if sector_data.sectors:
        top3 = [s.name for s in sector_data.sectors[:3]]
        print(f"   ✓ Top 3 sectors: {top3}")

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3: Stock Data (NO AI)
    # ═══════════════════════════════════════════════════════════════════════
    print(f"\n{'─'*60}")
    print("📊 Step 3: Stock Screening Data (NO AI)")
    print(f"{'─'*60}")

    m3_config = create_m3_config()
    m3_config.SAVE_REPORT = False
    m3_config.USE_AI_SELECTION = False  # DISABLE AI in this phase

    # Target sectors
    if SCAN_ALL_SECTORS:
        target_sectors = ALL_SECTORS.copy()
        print(f"   📋 Scanning all 7 sectors")
    else:
        target_sectors = []
        if sector_data and hasattr(sector_data, 'sectors'):
            for sector in sector_data.sectors[:6]:
                code = getattr(sector, 'code', getattr(sector, 'symbol', None))
                if code:
                    target_sectors.append(code)
        print(f"   📋 Scanning top {len(target_sectors)} sectors")

    # Run module 3 WITHOUT AI
    module3 = StockScreenerModule(m3_config)
    stock_data = module3.run(
        target_sectors=target_sectors,
        market_context=market_data.__dict__,
        history_context=history_context
    )

    print(f"   ✓ Scanned: {stock_data.total_scanned}")
    print(f"   ✓ Candidates: {len(stock_data.candidates)}")
    print(f"   ✓ Top picks (algorithm): {[c.symbol for c in stock_data.top_picks[:5]]}")

    return market_data, sector_data, stock_data, history_context


def run_ai_for_provider(
    provider: str,
    market_data: any,
    sector_data: any,
    stock_data: any,
    history_context: str,
    output_dir: str
) -> Dict:
    """
    Chạy AI analysis cho 1 provider (Claude hoặc Gemini)
    Sử dụng data đã collect, CHỈ chạy AI
    """
    print(f"\n{'═'*60}")
    print(f"🤖 AI ANALYSIS: {provider.upper()}")
    print(f"{'═'*60}")

    start_time = time.time()

    # Get API key
    provider_keys = {
        'claude': APIKeys.CLAUDE,
        'gemini': APIKeys.GEMINI,
    }
    api_key = provider_keys.get(provider.lower(), '')

    if not api_key:
        print(f"   ⚠️ No API key for {provider}")
        return {'provider': provider, 'error': 'No API key'}

    results = {
        'provider': provider,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M"),
        'market_report': None,
        'sector_report': None,
        'screener_report': None
    }

    try:
        # ═══════════════════════════════════════════════════════════════════
        # MODULE 1: Market AI Analysis
        # ═══════════════════════════════════════════════════════════════════
        print(f"   [{provider}] Module 1: Market AI Scoring + Analysis...")

        m1_config = create_m1_config()
        m1_config.AI_PROVIDER = provider
        m1_config.AI_API_KEY = api_key

        # Copy data and run AI
        market_report = copy.deepcopy(market_data)
        ai_gen1 = MarketTimingAIGenerator(m1_config)

        # AI scoring
        ai_score = ai_gen1.score_market(market_report, history_context)
        market_report.market_score = ai_score['score']
        market_report.market_color = ai_score['color']
        market_report.trend_status = ai_score['trend']

        # AI analysis
        market_report.ai_analysis = ai_gen1.generate(market_report, history_context)
        results['market_report'] = market_report

        print(f"      ✓ Score: {market_report.market_score}/100 | Color: {market_report.market_color}")

        # ═══════════════════════════════════════════════════════════════════
        # MODULE 2: Sector AI Analysis
        # ═══════════════════════════════════════════════════════════════════
        print(f"   [{provider}] Module 2: Sector AI Analysis...")

        m2_config = create_m2_config()
        m2_config.AI_PROVIDER = provider
        m2_config.AI_API_KEY = api_key

        sector_report = copy.deepcopy(sector_data)
        ai_gen2 = SectorRotationAIGenerator(m2_config)

        sector_report.ai_analysis = ai_gen2.generate(sector_report, history_context)
        results['sector_report'] = sector_report

        ai_chars = len(sector_report.ai_analysis) if sector_report.ai_analysis else 0
        print(f"      ✓ AI analysis: {ai_chars} chars")

        # ═══════════════════════════════════════════════════════════════════
        # MODULE 3: Stock AI Selection
        # ═══════════════════════════════════════════════════════════════════
        print(f"   [{provider}] Module 3: Stock AI Selection...")

        m3_config = create_m3_config()
        m3_config.AI_PROVIDER = provider
        m3_config.AI_API_KEY = api_key
        m3_config.USE_AI_SELECTION = True

        screener_report = copy.deepcopy(stock_data)

        # Log original top_picks before AI processing
        original_picks = [c.symbol for c in screener_report.top_picks[:10]] if hasattr(screener_report, 'top_picks') and screener_report.top_picks else []
        print(f"      📋 Original algorithm picks: {original_picks}")

        # Create AI analyzer for this provider
        ai_analyzer = StockAIAnalyzer(m3_config)

        # Run AI selection on candidates
        if screener_report.candidates and ai_analyzer.ai:
            ai_picks = ai_analyzer.ai_select_top_stocks(
                screener_report.candidates,
                market_context=market_report.__dict__,
                history_context=history_context,
                top_n=10
            )

            if ai_picks:
                # Map AI picks (dicts) back to original StockCandidate objects
                candidate_map = {c.symbol: c for c in screener_report.candidates}
                mapped_picks = []

                for pick in ai_picks:
                    symbol = pick.get('symbol', '').upper().strip()
                    if symbol in candidate_map:
                        candidate = copy.deepcopy(candidate_map[symbol])
                        # Add AI score and reason to the candidate
                        candidate.ai_score = pick.get('score', candidate.score_total)
                        candidate.ai_reason = pick.get('reason', '')
                        candidate.rank = pick.get('rank', len(mapped_picks) + 1)
                        mapped_picks.append(candidate)

                if mapped_picks:
                    screener_report.top_picks = mapped_picks
                    print(f"      ✓ Mapped {len(mapped_picks)} AI picks to StockCandidate objects")

                screener_report.ai_analysis = ai_analyzer.generate_report_summary(screener_report, history_context)

        results['screener_report'] = screener_report

        # Log final top_picks after AI processing
        final_picks = []
        if hasattr(screener_report, 'top_picks') and screener_report.top_picks:
            for c in screener_report.top_picks[:10]:
                if hasattr(c, 'symbol'):
                    final_picks.append(c.symbol)
                elif isinstance(c, dict):
                    final_picks.append(c.get('symbol', '?'))
        print(f"      ✓ Final Top 10: {final_picks}")

        # ═══════════════════════════════════════════════════════════════════
        # Generate & Save Report
        # ═══════════════════════════════════════════════════════════════════
        print(f"   [{provider}] Generating report...")

        # Ensure required fields exist (defensive)
        if not hasattr(screener_report, 'target_sectors') or screener_report.target_sectors is None:
            screener_report.target_sectors = []
        if not hasattr(screener_report, 'top_picks') or screener_report.top_picks is None:
            screener_report.top_picks = []
        if not hasattr(screener_report, 'candidates') or screener_report.candidates is None:
            screener_report.candidates = []

        try:
            from run_compare_ai import _generate_ai_report
            report_content = _generate_ai_report(results, provider)
        except Exception as report_error:
            print(f"      ⚠️ Report generation error: {report_error}")
            import traceback
            traceback.print_exc()
            # Fallback: create minimal report
            report_content = _generate_minimal_report(results, provider)

        report_file = f"{output_dir}/canslim_report_{provider}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"

        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report_content)

        results['report_file'] = report_file
        results['report_content'] = report_content

        print(f"      ✓ Report saved: {report_file}")

        # Send email
        try:
            notifier = EmailNotifier()
            if notifier.config.ENABLED:
                original_prefix = notifier.config.SUBJECT_PREFIX
                notifier.config.SUBJECT_PREFIX = f"[{provider.upper()}] CANSLIM REPORT"
                notifier.send_report(report_content, report_file)
                notifier.config.SUBJECT_PREFIX = original_prefix
                print(f"      ✓ Email sent")
        except Exception as e:
            print(f"      ⚠️ Email error: {e}")

        elapsed = time.time() - start_time
        print(f"   ✅ [{provider.upper()}] Complete in {elapsed:.0f}s")

    except Exception as e:
        print(f"   ❌ [{provider}] Error: {e}")
        import traceback
        traceback.print_exc()

        # Even on error, try to create a minimal report
        if 'report_file' not in results or not results.get('report_file'):
            print(f"   [{provider}] Attempting fallback report generation...")
            try:
                report_content = _generate_minimal_report(results, provider)
                report_file = f"{output_dir}/canslim_report_{provider}_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
                with open(report_file, 'w', encoding='utf-8') as f:
                    f.write(report_content)
                results['report_file'] = report_file
                results['report_content'] = report_content
                print(f"      ✓ Fallback report saved: {report_file}")

                # Try to send fallback email
                try:
                    notifier = EmailNotifier()
                    if notifier.config.ENABLED:
                        notifier.config.SUBJECT_PREFIX = f"[{provider.upper()}] CANSLIM REPORT (PARTIAL)"
                        notifier.send_report(report_content, report_file)
                        print(f"      ✓ Fallback email sent")
                except Exception as email_err:
                    print(f"      ⚠️ Fallback email error: {email_err}")

            except Exception as fallback_err:
                print(f"      ❌ Fallback report also failed: {fallback_err}")

    return results


def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║               🚀 AI COMPARISON V2: OPTIMIZED PIPELINE                        ║
║                                                                              ║
║    Flow: Data Collection (1x) → AI Analysis (Claude + Gemini parallel)       ║
║    Expected time: ~30-40 phút (vs 60-80 phút trước đây)                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    config = get_config()
    output_dir = config.output.OUTPUT_DIR

    total_start = time.time()

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 1: DATA COLLECTION (1 lần duy nhất)
    # ═══════════════════════════════════════════════════════════════════════

    data_start = time.time()
    market_data, sector_data, stock_data, history_context = collect_all_data(output_dir)
    data_elapsed = time.time() - data_start

    print(f"\n⏱️  Data collection complete: {data_elapsed/60:.1f} phút")

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 2: AI ANALYSIS (Claude + Gemini in parallel)
    # ═══════════════════════════════════════════════════════════════════════

    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🤖 PHASE 2: AI ANALYSIS (PARALLEL)                        ║
║                    Claude và Gemini chạy đồng thời                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    ai_start = time.time()

    # Run Claude and Gemini in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(
                run_ai_for_provider,
                'claude', market_data, sector_data, stock_data, history_context, output_dir
            ): 'claude',
            executor.submit(
                run_ai_for_provider,
                'gemini', market_data, sector_data, stock_data, history_context, output_dir
            ): 'gemini'
        }

        results = {}
        for future in as_completed(futures):
            provider = futures[future]
            try:
                results[provider] = future.result()
            except Exception as e:
                print(f"❌ {provider} failed: {e}")
                results[provider] = {'provider': provider, 'error': str(e)}

    ai_elapsed = time.time() - ai_start
    print(f"\n⏱️  AI analysis complete: {ai_elapsed/60:.1f} phút")

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 3: COMPARISON REPORT
    # ═══════════════════════════════════════════════════════════════════════

    claude_results = results.get('claude', {})
    gemini_results = results.get('gemini', {})

    from run_compare_ai import generate_comparison
    output_file, content = generate_comparison(claude_results, gemini_results, output_dir)

    total_elapsed = time.time() - total_start

    # Calculate savings
    old_time = 70  # minutes (estimated old runtime)
    savings = max(0, old_time - total_elapsed/60)

    print(f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🎉 HOÀN THÀNH (OPTIMIZED V2)!                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  📊 Data collection:  {data_elapsed/60:>5.1f} phút                                        ║
║  🤖 AI analysis:      {ai_elapsed/60:>5.1f} phút (parallel Claude + Gemini)              ║
║  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ ║
║  ⏱️  TOTAL:           {total_elapsed/60:>5.1f} phút                                        ║
║  💰 Time saved:       ~{savings:.0f} phút so với phiên bản cũ                          ║
║                                                                              ║
║  📄 Reports:                                                                 ║
║     • {claude_results.get('report_file', 'N/A'):<58} ║
║     • {gemini_results.get('report_file', 'N/A'):<58} ║
║     • {output_file:<58} ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)

    # Send comparison email
    try:
        notifier = EmailNotifier()
        if notifier.config.ENABLED:
            print("📧 Gửi email AI Comparison...")
            original_prefix = notifier.config.SUBJECT_PREFIX
            notifier.config.SUBJECT_PREFIX = "[AI COMPARISON] CLAUDE vs GEMINI"
            notifier.send_report(content, output_file)
            notifier.config.SUBJECT_PREFIX = original_prefix
            print("✓ Email sent")
    except Exception as e:
        print(f"⚠️ Email error: {e}")

    return output_file


if __name__ == "__main__":
    main()
