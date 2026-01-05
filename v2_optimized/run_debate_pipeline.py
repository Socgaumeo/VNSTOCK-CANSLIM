#!/usr/bin/env python3
"""
SEQUENTIAL DEBATE PIPELINE
--------------------------
1. ANALYST (Gemini): Collects data, analyzes, produces initial report.
2. SENIOR REVIEWER (Claude): Reviews data & analysis, provides critique.
3. DEBATE REPORT: Consolidated view + Senior Verdict.
"""

import os
import sys
import time
from datetime import datetime
from config import APIKeys

# Import Modules
from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified as create_m1_config
from module2_sector_rotation_v3 import SectorRotationModule, create_config_from_unified as create_m2_config
from module3_stock_screener_v1 import StockScreenerModule, create_config_from_unified as create_m3_config
from email_notifier import EmailNotifier

def run_debate():
    """Run the Sequential Debate"""
    print("\n" + "="*80)
    print("🎭 SEQUENTIAL DEBATE: GEMINI (Analyst) vs CLAUDE (Reviewer)")
    print("="*80 + "\n")
    
    timestamp = datetime.now()
    output_dir = f"./output/debate_{timestamp.strftime('%Y%m%d_%H%M')}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Shared Data Context (Passed from Analyst to Reviewer)
    debate_context = {
        'market_report': None,
        'sector_report': None,
        'screener_report': None,
        'gemini_analysis': {},
        'claude_critique': {}
    }
    
    # ---------------------------------------------------------
    # PHASE 1: GEMINI (ANALYST) - COLLECT & ANALYZE
    # ---------------------------------------------------------
    print("\n🚀 PHASE 1: JUNIOR ANALYST (GEMINI) STARTING...")
    
    # Setup Gemini Config
    os.environ['AI_PROVIDER'] = 'gemini'
    
    try:
        # 1. Market Timing
        print("\n[GEMINI] 1. Market Timing Analysis...")
        m1_config = create_m1_config()
        m1_config.AI_PROVIDER = 'gemini'
        m1_config.AI_API_KEY = APIKeys.GEMINI
        m1_config.SAVE_REPORT = False
        # Enable Mid-Session if needed, defaulting to False/True based on time? 
        # For now assume Standard Run.
        
        m1 = MarketTimingModule(m1_config)
        debate_context['market_report'] = m1.run()
        debate_context['gemini_analysis']['market'] = debate_context['market_report'].ai_analysis
        
        # 2. Sector Rotation
        print("\n[GEMINI] 2. Sector Rotation Analysis...")
        m2_config = create_m2_config()
        m2_config.AI_PROVIDER = 'gemini'
        m2_config.AI_API_KEY = APIKeys.GEMINI
        m2_config.SAVE_REPORT = False
        
        market_ctx_dict = {
            'traffic_light': debate_context['market_report'].market_color,
            'distribution_days': 0, # Not explicitly counted in V2 Report
            'market_regime': debate_context['market_report'].trend_status
        }
        # Correct attributes for Module 1 Report? 
        # Module 1 Report attributes: market_color, market_score, trend_status (not market_trend?), distribution_days (maybe not present?)
        # Checking m1 definitions... m1 report has 'market_color', 'trend_status'.
        # Let's check 'market_trend' vs 'trend_status'. 
        
        m2 = SectorRotationModule(m2_config)
        debate_context['sector_report'] = m2.run(market_context=market_ctx_dict)
        debate_context['gemini_analysis']['sector'] = debate_context['sector_report'].ai_analysis
        
        # 3. Stock Screener
        print("\n[GEMINI] 3. Stock Screening...")
        m3_config = create_m3_config()
        m3_config.AI_PROVIDER = 'gemini'
        m3_config.AI_API_KEY = APIKeys.GEMINI
        m3_config.SAVE_REPORT = False
        m3_config.USE_AI_SELECTION = True
        
        # Convert names to codes if needed
        # SECTOR_NAMES inverse mapping
        SECTOR_MAP = {
            'Tài chính': 'VNFIN',
            'Bất động sản': 'VNREAL',
            'Nguyên vật liệu': 'VNMAT',
            'Công nghệ': 'VNIT',
            'Y tế': 'VNHEAL',
            'Tiêu dùng không thiết yếu': 'VNCOND', 
            'Tiêu dùng thiết yếu': 'VNCONS',
            'Năng lượng': 'VNENE', # Assuming potential
            'Công nghiệp': 'VNIND',
            'Tiện ích': 'VNUTI'
        }
        
        target_names = debate_context['sector_report'].top_sectors
        target_sectors = []
        for name in target_names:
            # Try specific map first, then check if it is already a code
            if name in SECTOR_MAP:
                target_sectors.append(SECTOR_MAP[name])
            elif name in SECTOR_MAP.values(): # It's a key? No values are names.
                 # Search value?
                 found = False
                 for k, v in SECTOR_MAP.items():
                     if v == name:
                         target_sectors.append(k)
                         found = True
                         break
                 if not found:
                     # Maybe it IS a code
                     target_sectors.append(name)
            else:
                 target_sectors.append(name)
        
        # Deduplicate
        target_sectors = list(dict.fromkeys(target_sectors))
        print(f"   Mapped Sectors: {target_names} -> {target_sectors}")
        
        m3 = StockScreenerModule(m3_config)
        debate_context['screener_report'] = m3.run(target_sectors=target_sectors, market_context=market_ctx_dict)
        debate_context['gemini_analysis']['stock'] = debate_context['screener_report'].ai_analysis
        
        print("\n✅ GEMINI PHASE COMPLETE! Data collected.")
        
    except Exception as e:
        print(f"\n❌ GEMINI PHASE FAILED: {e}")
        import traceback
        traceback.print_exc()
        return

    # ---------------------------------------------------------
    # PHASE 2: CLAUDE (SENIOR REVIEWER) - CRITIQUE
    # ---------------------------------------------------------
    print("\n🧐 PHASE 2: SENIOR REVIEWER (CLAUDE) STARTING...")
    
    # Setup Claude Config - NOTE: We do NOT re-run data collection.
    # We call 'run_critique' on the SAME module instances (or new ones with same config but passing data)
    # Ideally passing the 'report' object is enough.
    
    try:
        # 1. Market Critique
        print("\n[CLAUDE] 1. Reviewing Market Analysis...")
        m1_config_c = create_m1_config()
        m1_config_c.AI_PROVIDER = 'claude'
        m1_config_c.AI_API_KEY = APIKeys.CLAUDE
        
        m1_c = MarketTimingModule(m1_config_c)
        debate_context['claude_critique']['market'] = m1_c.run_critique(
            debate_context['market_report'], 
            debate_context['gemini_analysis']['market']
        )
        
        # 2. Sector Critique
        print("\n[CLAUDE] 2. Reviewing Sector Analysis...")
        m2_config_c = create_m2_config()
        m2_config_c.AI_PROVIDER = 'claude'
        m2_config_c.AI_API_KEY = APIKeys.CLAUDE
        
        m2_c = SectorRotationModule(m2_config_c)
        debate_context['claude_critique']['sector'] = m2_c.run_critique(
            debate_context['sector_report'],
            debate_context['gemini_analysis']['sector']
        )
        
        # 3. Stock Critique
        print("\n[CLAUDE] 3. Reviewing Stock Picks...")
        m3_config_c = create_m3_config()
        m3_config_c.AI_PROVIDER = 'claude'
        m3_config_c.AI_API_KEY = APIKeys.CLAUDE
        
        m3_c = StockScreenerModule(m3_config_c)
        debate_context['claude_critique']['stock'] = m3_c.run_critique(
            debate_context['screener_report'],
            debate_context['gemini_analysis']['stock']
        )
        
        print("\n✅ CLAUDE PHASE COMPLETE!")
        
    except Exception as e:
        print(f"\n❌ CLAUDE PHASE FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    # ---------------------------------------------------------
    # PHASE 3: DEEPSEEK (RISK MANAGER) - CHALLENGE BOTH
    # ---------------------------------------------------------
    print("\n⚠️ PHASE 3: RISK MANAGER (DEEPSEEK) STARTING...")
    
    debate_context['deepseek_risk'] = {}
    
    try:
        # 1. Market Risk Review
        print("\n[DEEPSEEK] 1. Risk Review - Market Analysis...")
        m1_config_d = create_m1_config()
        m1_config_d.AI_PROVIDER = 'deepseek'
        m1_config_d.AI_API_KEY = APIKeys.DEEPSEEK
        
        m1_d = MarketTimingModule(m1_config_d)
        debate_context['deepseek_risk']['market'] = m1_d.run_risk_review(
            debate_context['market_report'], 
            debate_context['gemini_analysis']['market'],
            debate_context['claude_critique'].get('market', '')
        )
        
        # 2. Sector Risk Review
        print("\n[DEEPSEEK] 2. Risk Review - Sector Analysis...")
        m2_config_d = create_m2_config()
        m2_config_d.AI_PROVIDER = 'deepseek'
        m2_config_d.AI_API_KEY = APIKeys.DEEPSEEK
        
        m2_d = SectorRotationModule(m2_config_d)
        debate_context['deepseek_risk']['sector'] = m2_d.run_risk_review(
            debate_context['sector_report'],
            debate_context['gemini_analysis']['sector'],
            debate_context['claude_critique'].get('sector', '')
        )
        
        # 3. Stock Risk Review
        print("\n[DEEPSEEK] 3. Risk Review - Stock Picks...")
        m3_config_d = create_m3_config()
        m3_config_d.AI_PROVIDER = 'deepseek'
        m3_config_d.AI_API_KEY = APIKeys.DEEPSEEK
        
        m3_d = StockScreenerModule(m3_config_d)
        debate_context['deepseek_risk']['stock'] = m3_d.run_risk_review(
            debate_context['screener_report'],
            debate_context['gemini_analysis']['stock'],
            debate_context['claude_critique'].get('stock', '')
        )
        
        print("\n✅ DEEPSEEK RISK MANAGER PHASE COMPLETE!")
        
    except Exception as e:
        print(f"\n❌ DEEPSEEK PHASE FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    # ---------------------------------------------------------
    # PHASE 4: GENERATE 3-WAY DEBATE REPORT
    # ---------------------------------------------------------
    print("\n📝 PHASE 4: GENERATING FINAL 3-WAY REPORT...")
    
    report_content = generate_debate_report(debate_context, timestamp)
    
    # Save Report
    report_file = f"{output_dir}/debate_report_{timestamp.strftime('%Y%m%d_%H%M')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)
    
    print(f"✓ Report saved: {report_file}")
    
    # Send Email
    try:
        notifier = EmailNotifier()
        if notifier.config.ENABLED:
            print("📧 Sending email...")
            subject_prefix = notifier.config.SUBJECT_PREFIX
            notifier.config.SUBJECT_PREFIX = "🎭 [3-WAY DEBATE] GEMINI vs CLAUDE vs DEEPSEEK"
            notifier.send_report(report_content, report_file)
            notifier.config.SUBJECT_PREFIX = subject_prefix
            print("✓ Email sent!")
    except Exception as e:
        print(f"⚠️ Email failed: {e}")
        
    print("\n🏁 3-WAY SEQUENTIAL DEBATE FINISHED!")


def generate_debate_report(ctx, timestamp):
    """Generate Markdown Report with 3-way debate"""
    # Helper to clean text
    def clean(text): return text.strip() if text else "N/A"
    
    # Market Data
    m_report = ctx['market_report']
    vni = m_report.vnindex
    
    # Get DeepSeek risk reviews (with fallback)
    deepseek_risk = ctx.get('deepseek_risk', {})
    
    return f"""# 🎭 AI INVESTMENT DEBATE REPORT (3-WAY)
**Date:** {timestamp.strftime('%d/%m/%Y %H:%M')}
**Protocol:** 3-Way Sequential Review
- 🤖 **Gemini** (Junior Analyst) → Initial Analysis
- 🧐 **Claude** (Senior Reviewer) → Critique
- ⚠️ **DeepSeek** (Risk Manager) → Risk Assessment & Consensus

---

## 1. MARKET TIMING DEBATE

### 📊 DATA (Fact)
- **VNIndex:** {vni.price:,.0f} ({vni.change_1d:+.2f}%)
- **Market Score:** {m_report.market_score}/100
- **Status:** {m_report.market_color}

### 🤖 JUNIOR ANALYST (Gemini)
{clean(ctx['gemini_analysis']['market'])}

### 🧐 SENIOR REVIEWER (Claude)
{clean(ctx['claude_critique'].get('market', 'N/A'))}

### ⚠️ RISK MANAGER (DeepSeek)
{clean(deepseek_risk.get('market', 'Risk review not available'))}

---

## 2. SECTOR ROTATION DEBATE

### 🤖 JUNIOR ANALYST (Gemini)
{clean(ctx['gemini_analysis']['sector'])}

### 🧐 SENIOR REVIEWER (Claude) 
{clean(ctx['claude_critique'].get('sector', 'N/A'))}

### ⚠️ RISK MANAGER (DeepSeek)
{clean(deepseek_risk.get('sector', 'Risk review not available'))}

---

## 3. STOCK SELECTION DEBATE

### 🤖 JUNIOR ANALYST (Gemini)
{clean(ctx['gemini_analysis']['stock'])}

### 🧐 SENIOR REVIEWER (Claude)
{clean(ctx['claude_critique'].get('stock', 'N/A'))}

### ⚠️ RISK MANAGER (DeepSeek)
{clean(deepseek_risk.get('stock', 'Risk review not available'))}

---

## 4. CONSENSUS SUMMARY

> **Phương pháp 3-Way Debate:**
> - Gemini đưa ra phân tích ban đầu (momentum/technical focus)
> - Claude phản biện và bổ sung góc nhìn fundamental
> - DeepSeek đóng vai Risk Manager, tìm ra rủi ro bị bỏ sót và đưa consensus

**⚠️ LƯU Ý:** Khi cả 3 AI đồng ý về một điểm, đó là tín hiệu mạnh. 
Khi có bất đồng, hãy ưu tiên theo Risk Manager để bảo toàn vốn.

---

**DISCLAIMER:** Báo cáo được tạo tự động bởi AI (Gemini, Claude & DeepSeek). Cân nhắc rủi ro trước khi giao dịch.
"""

if __name__ == "__main__":
    run_debate()
