#!/usr/bin/env python3
"""
Run Full Pipeline với cả Claude và Gemini AI
Tạo bảng so sánh kết quả giữa 2 AI
"""

import os
import sys
import time
from datetime import datetime

# Import modules
from config import get_config, APIKeys
from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified as create_m1_config
from module2_sector_rotation_v3 import SectorRotationModule, create_config_from_unified as create_m2_config
from module3_stock_screener_v1 import StockScreenerModule, create_config_from_unified as create_m3_config
from history_manager import HistoryManager


def run_with_provider(provider: str, output_dir: str):
    """
    Chạy pipeline với một AI provider cụ thể
    """
    print(f"\n{'='*80}")
    print(f"🤖 RUNNING PIPELINE WITH {provider.upper()}")
    print(f"{'='*80}\n")
    
    # Set environment variable to override AI provider
    os.environ['AI_PROVIDER'] = provider
    
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
            
        m1_module = MarketTimingModule(m1_config)
        results['market_report'] = m1_module.run(history_context)
        print(f"   ✓ Market Score: {results['market_report'].market_score}/100")
        print(f"   ✓ Market Color: {results['market_report'].market_color}")
        
        # === MODULE 2: SECTOR ROTATION ===
        print(f"[{provider}] Module 2: Sector Rotation...")
        m2_config = create_m2_config()
        m2_config.SAVE_REPORT = False
        m2_config.AI_PROVIDER = provider
            
        m2_module = SectorRotationModule(m2_config)
        results['sector_report'] = m2_module.run()
        
        if hasattr(results['sector_report'], 'sectors') and results['sector_report'].sectors:
            top_sectors = [s.symbol if hasattr(s, 'symbol') else s.code for s in results['sector_report'].sectors[:3]]
            print(f"   ✓ Top 3 sectors: {top_sectors}")
        
        # === MODULE 3: STOCK SCREENER ===
        print(f"[{provider}] Module 3: Stock Screener...")
        target_sectors = []
        if hasattr(results['sector_report'], 'sectors') and results['sector_report'].sectors:
            for sector in results['sector_report'].sectors[:6]:
                sector_code = getattr(sector, 'code', getattr(sector, 'symbol', None))
                if sector_code:
                    target_sectors.append(sector_code)
        
        m3_config = create_m3_config()
        m3_config.SAVE_REPORT = False
        m3_config.AI_PROVIDER = provider
            
        m3_module = StockScreenerModule(m3_config)
        results['screener_report'] = m3_module.run(target_sectors)
        
        if hasattr(results['screener_report'], 'top_picks'):
            print(f"   ✓ Top 5 picks: {[c.symbol for c in results['screener_report'].top_picks[:5]]}")
        
        print(f"\n✅ [{provider.upper()}] Pipeline complete!")
        
    except Exception as e:
        print(f"❌ [{provider}] Error: {e}")
        import traceback
        traceback.print_exc()
        
    return results


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
    
    return output_file


if __name__ == "__main__":
    main()
