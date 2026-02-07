#!/usr/bin/env python3
"""
SIMULTANEOUS DEBATE PIPELINE
----------------------------
Protocol: Bull (Gemini) vs Bear (DeepSeek), Judge (Claude)

Flow:
1. Step 0: Create Dossier (Data standardization)
2. Step 1: Parallel Bull/Bear analysis (don't see each other)
3. Step 2: Cross-examination (each attacks the other)
4. Step 3: Judge verdict (Claude)
"""

import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import APIKeys
import pandas as pd

# Import Modules
from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified as create_m1_config
from module2_sector_rotation_v3 import SectorRotationModule, create_config_from_unified as create_m2_config
from module3_stock_screener_v1 import StockScreenerModule, create_config_from_unified as create_m3_config
from ai_providers import AIProvider, AIConfig
from ai_debate_prompts import (
    BULL_SYSTEM_PROMPT, BULL_ROUND1_PROMPT, BULL_ROUND2_PROMPT,
    BEAR_SYSTEM_PROMPT, BEAR_ROUND1_PROMPT, BEAR_ROUND2_PROMPT,
    JUDGE_SYSTEM_PROMPT, JUDGE_VERDICT_PROMPT,
    DOSSIER_CREATION_PROMPT
)
from email_notifier import EmailNotifier


def create_dossier(market_report, sector_report, screener_report):
    """
    Step 0: Create standardized Dossier from raw data
    Returns structured data string for all AIs
    """
    # Build comprehensive dossier from all reports
    
    # === MARKET DATA ===
    vni = market_report.vnindex
    vn30 = market_report.vn30
    
    market_section = f"""
═══════════════════════════════════════════════════════════════
A. TỔNG QUAN THỊ TRƯỜNG (MARKET CONTEXT)
═══════════════════════════════════════════════════════════════

📊 VN-INDEX:
   - Giá: {vni.price:,.0f} | Thay đổi: {vni.change_1d:+.2f}%
   - OHLC: O={vni.open:,.0f} H={vni.high:,.0f} L={vni.low:,.0f} C={vni.price:,.0f}
   - MA20: {vni.ma20:,.0f} | MA50: {vni.ma50:,.0f}
   - VỊ TRÍ: {"TRÊN MA20" if vni.price > vni.ma20 else "DƯỚI MA20"}, {"TRÊN MA50" if vni.price > vni.ma50 else "DƯỚI MA50"}
   - RSI(14): {vni.rsi_14:.1f}
   - MACD Histogram: {vni.macd_hist:+.2f}
   - ADX: {vni.adx:.1f}
   - Volume Ratio: {vni.volume_ratio:.2f}x

📊 VOLUME PROFILE (20 ngày):
   - POC: {vni.poc:,.0f}
   - Value Area: {vni.val:,.0f} - {vni.vah:,.0f}
   - Giá vs POC: {vni.price_vs_poc}
   - Giá vs VA: {vni.price_vs_va}

📊 VN30: {vn30.price:,.0f} ({vn30.change_1d:+.2f}%)

📊 ĐỘ RỘNG: Tăng={market_report.breadth.advances} | Giảm={market_report.breadth.declines} | A/D={market_report.breadth.ad_ratio:.2f}

💰 DÒNG TIỀN:
   - Khối ngoại: {market_report.money_flow.foreign_net:+.1f} tỷ

🚦 MARKET STATUS: {market_report.market_color} | Score: {market_report.market_score}/100

🧠 CLAUDE ANALYSIS:
{market_report.ai_analysis}
"""

    # === SECTOR DATA ===
    sector_section = f"""
═══════════════════════════════════════════════════════════════
B. NGÀNH (SECTOR ROTATION)
═══════════════════════════════════════════════════════════════

📊 ROTATION CLOCK: {sector_report.rotation.current_clock.name} (Confidence: {sector_report.rotation.confidence:.0f}%)

🏆 TOP 3 NGÀNH MẠNH:
"""
    for i, s in enumerate(sector_report.sectors[:3], 1):
        sector_section += f"   {i}. {s.name}: RS={s.rs_rating} | 1D={s.change_1d:+.2f}% | 1M={s.change_1m:+.2f}% | Trend={s.rs_trend}\n"
    
    sector_section += "\n📉 TOP 3 NGÀNH YẾU:\n"
    for i, s in enumerate(sorted(sector_report.sectors, key=lambda x: x.rs_rating)[:3], 1):
        sector_section += f"   {i}. {s.name}: RS={s.rs_rating} | 1D={s.change_1d:+.2f}% | 1M={s.change_1m:+.2f}%\n"

    # === STOCK DATA ===
    stock_section = """
═══════════════════════════════════════════════════════════════
C. CỔ PHIẾU TOP PICKS
═══════════════════════════════════════════════════════════════
"""
    
    # Add Price/Volume History (Last 10 sessions)
    for c in screener_report.top_picks[:10]:
        # Get buy point and stop loss
        buy_point = c.pattern.buy_point if c.pattern.buy_point > 0 else c.technical.price * 1.02
        stop_loss = buy_point * 0.93
        
        # Format Price History String
        price_history_str = "N/A"
        try:
            # We need to re-fetch history because StockCandidate might not store the full DF
            # Use a temporary data collector
            from data_collector import EnhancedDataCollector
            dc = EnhancedDataCollector()
            # Fetch last 15 days to ensure we get 10 trading days
            hist_df = dc.data_manager.get_price_history(c.symbol, days=20)
            if not hist_df.empty:
                # Get last 10 records
                last_10 = hist_df.tail(10)
                # Format: "Date: Close (Vol)"
                # Example: "05/01: 25.5(1.2M) -> 04/01: ..."
                # We show from oldest to newest for trend
                history_list = []
                for idx, row in last_10.iterrows():
                    date_str = pd.to_datetime(row['time']).strftime('%d/%m')
                    close_price = row['close']
                    vol_mil = row['volume'] / 1_000_000
                    history_list.append(f"{date_str}:{close_price:,.0f}({vol_mil:.1f}M)")
                price_history_str = " -> ".join(history_list)
        except Exception as e:
            print(f"Error fetching history for {c.symbol}: {e}")
            price_history_str = "Not available"

        stock_section += f"""
───────────────────────────────────────────────────────────────
{c.rank}. {c.symbol} ({c.sector_name}) | Score: {c.score_total:.0f} | Signal: {c.signal}
───────────────────────────────────────────────────────────────

📊 FUNDAMENTAL:
   - ROE: {c.fundamental.roe:.1f}% | ROA: {c.fundamental.roa:.1f}%
   - EPS Q/Q: {c.fundamental.eps_growth_qoq:+.1f}% | EPS Y/Y: {c.fundamental.eps_growth_yoy:+.1f}%
   - EPS 3Y Growth: {c.fundamental.eps_growth_3y:+.1f}%
   - Revenue Q/Q: {c.fundamental.revenue_growth_qoq:+.1f}%
   - OCF/Profit: {c.fundamental.ocf_to_profit_ratio:.2f} | Warning: {c.fundamental.cash_flow_warning or 'None'}
   - C Score: {c.fundamental.c_score} | A Score: {c.fundamental.a_score}

📈 TECHNICAL:
   - Giá: {c.technical.price:,.0f} | RS: {c.technical.rs_rating}
   - RSI(14): {c.technical.rsi_14:.1f}
   - MA: {"✅ TRÊN MA20" if c.technical.above_ma20 else "❌ DƯỚI MA20"} | {"✅ TRÊN MA50" if c.technical.above_ma50 else "❌ DƯỚI MA50"}
   - Volume Ratio: {c.technical.volume_ratio:.2f}x
   - VWAP: {c.technical.vwap:,.0f} | Score: {c.technical.vwap_score}/100
   - ATR(14): {c.technical.atr_pct:.1f}%
   - % từ đỉnh 52W: {c.technical.distance_from_high:+.1f}%

📉 PRICE/VOLUME HISTORY (10 Sessions):
   {price_history_str}

🎯 PATTERN: {c.pattern.pattern_type.value} (Quality: {c.pattern.pattern_quality}/100)
   - Base Depth: {c.pattern.base_depth:.1f}%
   - Buy Point: {buy_point:,.0f}

💰 DÒNG TIỀN PHIÊN:
   - Khối ngoại: {c.technical.foreign_net_value/1e6:+.1f}M VND

📈 TRADING PLAN:
   - Buy Point: {buy_point:,.0f}
   - Stop Loss: {stop_loss:,.0f} (-7%)
   - Target: {buy_point * 1.2:,.0f} (+20%)
"""

    return market_section + sector_section + stock_section


def run_bull_analysis(dossier, ai_provider):
    """Round 1: Bull (Gemini) writes buy thesis"""
    prompt = BULL_ROUND1_PROMPT.format(dossier=dossier)
    return ai_provider.chat(prompt, system_prompt=BULL_SYSTEM_PROMPT)


def run_bear_analysis(dossier, ai_provider):
    """Round 1: Bear (DeepSeek) writes sell thesis"""
    prompt = BEAR_ROUND1_PROMPT.format(dossier=dossier)
    return ai_provider.chat(prompt, system_prompt=BEAR_SYSTEM_PROMPT)


def run_bull_rebuttal(dossier, bear_thesis, ai_provider):
    """Round 2: Bull attacks Bear's arguments"""
    prompt = BULL_ROUND2_PROMPT.format(dossier=dossier, bear_thesis=bear_thesis[:4000])
    return ai_provider.chat(prompt, system_prompt=BULL_SYSTEM_PROMPT)


def run_bear_rebuttal(dossier, bull_thesis, ai_provider):
    """Round 2: Bear attacks Bull's arguments"""
    prompt = BEAR_ROUND2_PROMPT.format(dossier=dossier, bull_thesis=bull_thesis[:4000])
    return ai_provider.chat(prompt, system_prompt=BEAR_SYSTEM_PROMPT)


def run_judge_verdict(dossier, bull_thesis, bear_thesis, bull_rebuttal, bear_rebuttal, ai_provider):
    """Round 3: Judge (Claude) delivers final verdict"""
    prompt = JUDGE_VERDICT_PROMPT.format(
        dossier=dossier[:5000],
        bull_thesis=bull_thesis[:3000],
        bear_thesis=bear_thesis[:3000],
        bull_rebuttal=bull_rebuttal[:2500],
        bear_rebuttal=bear_rebuttal[:2500]
    )
    return ai_provider.chat(prompt, system_prompt=JUDGE_SYSTEM_PROMPT)


def generate_simultaneous_report(context, timestamp, output_dir):
    """Generate the final debate report"""
    
    report = f"""# 📊 SIMULTANEOUS DEBATE REPORT
**Ngày:** {timestamp.strftime('%Y-%m-%d %H:%M')}
**Protocol:** Bull (Gemini) vs Bear (DeepSeek), Judge (Claude)

---

## 📋 HỒ SƠ DỮ LIỆU (DOSSIER)
{context['dossier'][:3000]}...

---

## 🐂 VÒNG 1: PHE BÒ (Gemini)
{context['bull_thesis']}

---

## 🐻 VÒNG 1: PHE GẤU (DeepSeek)
{context['bear_thesis']}

---

## ⚔️ VÒNG 2: PHẢN BIỆN

### 🐂 Gemini phản bác DeepSeek:
{context['bull_rebuttal']}

### 🐻 DeepSeek phản bác Gemini:
{context['bear_rebuttal']}

---

## ⚖️ VÒNG 3: PHÁN QUYẾT (Claude)
{context['verdict']}

---

# ⚠️ DISCLAIMER

*Báo cáo này được tạo tự động bởi AI Debate System.*
*Thông tin chỉ mang tính chất tham khảo, không phải khuyến nghị đầu tư.*
*Nhà đầu tư tự chịu trách nhiệm với quyết định giao dịch của mình.*

---
**Generated:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    # Save report
    report_path = os.path.join(output_dir, f"simultaneous_debate_{timestamp.strftime('%Y%m%d_%H%M')}.md")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✓ Report saved: {report_path}")
    return report_path, report


def run_simultaneous_debate():
    """Main function: Run the Simultaneous Debate Protocol"""
    
    print("\n" + "="*80)
    print("🎭 SIMULTANEOUS DEBATE: BULL (Gemini) vs BEAR (DeepSeek)")
    print("="*80 + "\n")
    
    timestamp = datetime.now()
    output_dir = f"./output/debate_{timestamp.strftime('%Y%m%d_%H%M')}"
    os.makedirs(output_dir, exist_ok=True)
    
    context = {}
    
    # ---------------------------------------------------------
    # STEP 0: COLLECT DATA & CREATE DOSSIER
    # ---------------------------------------------------------
    print("\n📋 STEP 0: DATA INGESTION & DOSSIER CREATION...")
    
    try:
        # Collect data using existing modules (with Gemini for initial analysis)
        os.environ['AI_PROVIDER'] = 'gemini'
        
        # 1. Market Timing
        print("\n[DATA] 1. Market Timing...")
        m1_config = create_m1_config()
        m1_config.AI_PROVIDER = "claude" # Force Claude as requested
        m1_config.IS_MID_SESSION = True
        m1_config.SAVE_REPORT = True  # Enable individual report
        m1 = MarketTimingModule(m1_config)
        market_report = m1.run()
        
        # 2. Sector Rotation
        print("\n[DATA] 2. Sector Rotation...")
        m2_config = create_m2_config()
        m2_config.AI_PROVIDER = 'gemini'
        m2_config.AI_API_KEY = APIKeys.GEMINI
        m2_config.SAVE_REPORT = True  # Enable individual report
        market_ctx = {
            'traffic_light': market_report.market_color,
            'distribution_days': 0,
            'market_regime': market_report.trend_status
        }
        m2 = SectorRotationModule(m2_config)
        sector_report = m2.run(market_context=market_ctx)
        
        # 3. Stock Screener
        print("\n[DATA] 3. Stock Screening...")
        m3_config = create_m3_config()
        m3_config.AI_PROVIDER = 'gemini'
        m3_config.AI_API_KEY = APIKeys.GEMINI
        m3_config.SAVE_REPORT = True  # Enable individual report
        m3_config.USE_AI_SELECTION = True
        
        SECTOR_MAP = {
            'Tài chính': 'VNFIN', 'Bất động sản': 'VNREAL',
            'Nguyên vật liệu': 'VNMAT', 'Công nghệ': 'VNIT',
            'Y tế': 'VNHEAL', 'Tiêu dùng không thiết yếu': 'VNCOND',
            'Tiêu dùng thiết yếu': 'VNCONS'
        }
        target_sectors = [SECTOR_MAP.get(n, n) for n in sector_report.top_sectors]
        target_sectors = list(dict.fromkeys(target_sectors))
        
        m3 = StockScreenerModule(m3_config)
        screener_report = m3.run(target_sectors=target_sectors, market_context=market_ctx)
        
        # Create Dossier
        print("\n[DOSSIER] Creating standardized dossier...")
        context['dossier'] = create_dossier(market_report, sector_report, screener_report)
        print(f"✓ Dossier created ({len(context['dossier'])} chars)")
        
    except Exception as e:
        print(f"\n❌ DATA COLLECTION FAILED: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # ---------------------------------------------------------
    # STEP 1: PARALLEL BULL/BEAR ANALYSIS (Round 1)
    # ---------------------------------------------------------
    print("\n\n🐂🐻 STEP 1: PARALLEL ANALYSIS (Bull & Bear don't see each other)...")
    
    try:
        # Create AI providers
        bull_config = AIConfig(provider='gemini', api_key=APIKeys.GEMINI)
        bear_config = AIConfig(provider='deepseek', api_key=APIKeys.DEEPSEEK)
        
        bull_ai = AIProvider(bull_config)
        bear_ai = AIProvider(bear_config)
        
        # Run in parallel
        with ThreadPoolExecutor(max_workers=2) as executor:
            print("   [PARALLEL] Submitting Bull (Gemini) task...")
            bull_future = executor.submit(run_bull_analysis, context['dossier'], bull_ai)
            
            print("   [PARALLEL] Submitting Bear (DeepSeek) task...")
            bear_future = executor.submit(run_bear_analysis, context['dossier'], bear_ai)
            
            # Wait for results
            for future in as_completed([bull_future, bear_future]):
                if future == bull_future:
                    context['bull_thesis'] = future.result()
                    print(f"   ✓ Bull thesis complete ({len(context['bull_thesis'])} chars)")
                else:
                    context['bear_thesis'] = future.result()
                    print(f"   ✓ Bear thesis complete ({len(context['bear_thesis'])} chars)")
        
        print("✅ ROUND 1 COMPLETE!")
        
    except Exception as e:
        print(f"\n❌ ROUND 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        context['bull_thesis'] = "⚠️ Bull analysis failed."
        context['bear_thesis'] = "⚠️ Bear analysis failed."
    
    # ---------------------------------------------------------
    # STEP 2: CROSS-EXAMINATION (Round 2)
    # ---------------------------------------------------------
    print("\n\n⚔️ STEP 2: CROSS-EXAMINATION...")
    
    try:
        # Recreate AI providers for round 2
        bull_ai = AIProvider(bull_config)
        bear_ai = AIProvider(bear_config)
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            print("   [CROSS] Bull attacking Bear's arguments...")
            bull_rebuttal_future = executor.submit(
                run_bull_rebuttal, context['dossier'], context['bear_thesis'], bull_ai
            )
            
            print("   [CROSS] Bear attacking Bull's arguments...")
            bear_rebuttal_future = executor.submit(
                run_bear_rebuttal, context['dossier'], context['bull_thesis'], bear_ai
            )
            
            for future in as_completed([bull_rebuttal_future, bear_rebuttal_future]):
                if future == bull_rebuttal_future:
                    context['bull_rebuttal'] = future.result()
                    print(f"   ✓ Bull rebuttal complete ({len(context['bull_rebuttal'])} chars)")
                else:
                    context['bear_rebuttal'] = future.result()
                    print(f"   ✓ Bear rebuttal complete ({len(context['bear_rebuttal'])} chars)")
        
        print("✅ ROUND 2 COMPLETE!")
        
    except Exception as e:
        print(f"\n❌ ROUND 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        context['bull_rebuttal'] = "⚠️ Bull rebuttal failed."
        context['bear_rebuttal'] = "⚠️ Bear rebuttal failed."
    
    # ---------------------------------------------------------
    # STEP 3: JUDGE VERDICT (Claude)
    # ---------------------------------------------------------
    print("\n\n⚖️ STEP 3: JUDGE VERDICT (Claude)...")
    
    try:
        judge_config = AIConfig(provider='claude', api_key=APIKeys.CLAUDE)
        judge_ai = AIProvider(judge_config)
        
        context['verdict'] = run_judge_verdict(
            context['dossier'],
            context['bull_thesis'],
            context['bear_thesis'],
            context['bull_rebuttal'],
            context['bear_rebuttal'],
            judge_ai
        )
        print(f"✓ Verdict complete ({len(context['verdict'])} chars)")
        print("✅ VERDICT DELIVERED!")
        
    except Exception as e:
        print(f"\n❌ VERDICT FAILED: {e}")
        import traceback
        traceback.print_exc()
        context['verdict'] = "⚠️ Judge verdict failed."
    
    # ---------------------------------------------------------
    # STEP 4: GENERATE REPORT & SEND EMAIL
    # ---------------------------------------------------------
    print("\n\n📝 STEP 4: GENERATING FINAL REPORT...")
    
    report_path, report_content = generate_simultaneous_report(context, timestamp, output_dir)
    
    # Send email
    print("\n📧 Sending email...")
    try:
        notifier = EmailNotifier()
        subject = f"🎭 [DEBATE] BULL vs BEAR - {timestamp.strftime('%Y-%m-%d')}"
        notifier.send_report(report_content, report_path, subject=subject)
        print("✓ Email sent!")
    except Exception as e:
        print(f"⚠️ Email failed: {e}")
    
    print("\n" + "="*80)
    print("🏁 SIMULTANEOUS DEBATE FINISHED!")
    print("="*80)


if __name__ == "__main__":
    run_simultaneous_debate()
