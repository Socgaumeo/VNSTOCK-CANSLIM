#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                 CANSLIM FULL PIPELINE - TẤT CẢ 3 MODULES                      ║
║            Gộp Market Timing + Sector Rotation + Stock Screener               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  OUTPUT: 1 file Markdown duy nhất với đầy đủ thông tin                        ║
║  - Module 1: Market Timing (Traffic Light, Volume Profile)                   ║
║  - Module 2: Sector Rotation (Top ngành, RS Ranking)                         ║
║  - Module 3: Stock Screener (CANSLIM, Pattern, News, AI Analysis)            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Cách sử dụng:
    python run_full_pipeline.py
"""

import os
from datetime import datetime
from typing import Dict, List, Optional

# Import config
from config import get_config

# Import modules
from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified as create_m1_config
from module2_sector_rotation_v3 import SectorRotationModule, create_config_from_unified as create_m2_config
from module3_stock_screener_v1 import StockScreenerModule, create_config_from_unified as create_m3_config


class FullPipelineRunner:
    """Chạy toàn bộ pipeline và gộp output"""
    
    def __init__(self):
        self.config = get_config()
        self.output_dir = self.config.output.OUTPUT_DIR
        self.timestamp = datetime.now()
        
        # Results
        self.market_report = None
        self.sector_report = None
        self.screener_report = None
    
    def run(self, target_sectors: List[str] = None) -> str:
        """
        Chạy toàn bộ pipeline
        
        Args:
            target_sectors: Danh sách ngành để scan (optional, sẽ lấy từ Module 2)
        """
        print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🚀 CANSLIM FULL PIPELINE 🚀                               ║
║              Market Timing → Sector Rotation → Stock Screener                ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """)
        
        # ══════════════════════════════════════════════════════════════════════
        # MODULE 1: MARKET TIMING
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("📊 MODULE 1: MARKET TIMING")
        print("="*80)
        
        m1_config = create_m1_config()
        m1_config.SAVE_REPORT = False  # Không save riêng
        
        m1_module = MarketTimingModule(m1_config)
        self.market_report = m1_module.run()
        
        # ══════════════════════════════════════════════════════════════════════
        # MODULE 2: SECTOR ROTATION
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("🏭 MODULE 2: SECTOR ROTATION")
        print("="*80)
        
        m2_config = create_m2_config()
        m2_config.SAVE_REPORT = False  # Không save riêng
        
        m2_module = SectorRotationModule(m2_config)
        self.sector_report = m2_module.run()
        
        # Xác định target sectors từ Module 2
        if not target_sectors and self.sector_report:
            # Lấy top 2-3 ngành có RS cao nhất
            top_sectors = []
            if hasattr(self.sector_report, 'sectors') and self.sector_report.sectors:
                for sector in self.sector_report.sectors[:3]:
                    if hasattr(sector, 'code'):
                        top_sectors.append(sector.code)
            target_sectors = top_sectors if top_sectors else ['VNREAL', 'VNCOND']
        
        # ══════════════════════════════════════════════════════════════════════
        # MODULE 3: STOCK SCREENER
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("📈 MODULE 3: STOCK SCREENER")
        print("="*80)
        
        # Build market context từ Module 1 & 2
        market_context = self._build_market_context()
        
        m3_config = create_m3_config()
        m3_config.SAVE_REPORT = False  # Không save riêng
        
        m3_module = StockScreenerModule(m3_config)
        self.screener_report = m3_module.run(
            target_sectors=target_sectors,
            market_context=market_context
        )
        
        # ══════════════════════════════════════════════════════════════════════
        # GENERATE COMBINED OUTPUT
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("📝 GENERATING COMBINED REPORT")
        print("="*80)
        
        combined_report = self._generate_combined_report()
        output_file = self._save_report(combined_report)
        
        print(f"\n✅ HOÀN THÀNH!")
        print(f"📄 Output file: {output_file}")
        
        return output_file
    
    def _build_market_context(self) -> Dict:
        """Xây dựng market context từ Module 1 & 2"""
        context = {
            'traffic_light': 'N/A',
            'market_score': 50,
            'distribution_days': 0,
            'leading_sectors': [],
        }
        
        if self.market_report:
            context['traffic_light'] = f"{self.market_report.market_color} ({self.market_report.market_score}/100)"
            context['market_score'] = self.market_report.market_score
            
            # Distribution days từ key_signals
            for sig in self.market_report.key_signals:
                if 'Distribution' in sig or 'distribution' in sig:
                    context['distribution_days'] = 1  # Placeholder
        
        if self.sector_report and hasattr(self.sector_report, 'sectors'):
            top_sectors = [s.code for s in self.sector_report.sectors[:3] if hasattr(s, 'code')]
            context['leading_sectors'] = top_sectors
        
        return context
    
    def _generate_combined_report(self) -> str:
        """Tạo báo cáo gộp từ 3 modules"""
        
        # Header
        content = f"""# 📊 CANSLIM DAILY REPORT
**Ngày:** {self.timestamp.strftime('%d/%m/%Y %H:%M')}

---

# 🎯 PHẦN 1: MARKET TIMING (Module 1)

"""
        
        # Module 1: Market Timing
        if self.market_report:
            vni = self.market_report.vnindex
            content += f"""## Tổng quan thị trường

| Chỉ số | Giá trị |
|--------|---------|
| **Market Color** | {self.market_report.market_color} |
| **Score** | {self.market_report.market_score}/100 |
| **VN-Index** | {vni.price:,.0f} ({vni.change_1d:+.2f}%) |
| **RSI(14)** | {vni.rsi_14:.1f} |
| **MACD Hist** | {vni.macd_hist:+.2f} |

## Volume Profile
| Level | Giá |
|-------|-----|
| **POC** | {vni.poc:,.0f} |
| **Value Area** | {vni.val:,.0f} - {vni.vah:,.0f} |
| **Price vs VA** | {vni.price_vs_va} |

## Tín hiệu chính
"""
            for sig in self.market_report.key_signals:
                content += f"- {sig}\n"
            
            if self.market_report.ai_analysis:
                content += f"""
## 🤖 AI Analysis - Market Timing
{self.market_report.ai_analysis}
"""
        
        content += "\n---\n\n"
        
        # Module 2: Sector Rotation
        content += """# 🏭 PHẦN 2: SECTOR ROTATION (Module 2)

"""
        if self.sector_report and hasattr(self.sector_report, 'sectors'):
            content += """## Bảng xếp hạng ngành

| Rank | Ngành | Change 1D | RS Score |
|------|-------|-----------|----------|
"""
            for i, sector in enumerate(self.sector_report.sectors, 1):
                name = getattr(sector, 'name', sector.code if hasattr(sector, 'code') else 'N/A')
                change = getattr(sector, 'change_1d', 0)
                rs = getattr(sector, 'rs_score', 50)
                content += f"| {i} | {name} | {change:+.2f}% | {rs:.0f} |\n"
            
            if hasattr(self.sector_report, 'ai_analysis') and self.sector_report.ai_analysis:
                content += f"""
## 🤖 AI Analysis - Sector Rotation
{self.sector_report.ai_analysis}
"""
        
        content += "\n---\n\n"
        
        # Module 3: Stock Screener
        content += """# 📈 PHẦN 3: STOCK SCREENER (Module 3)

"""
        if self.screener_report:
            content += f"""## Screening Stats

| Metric | Value |
|--------|-------|
| **Target Sectors** | {', '.join(self.screener_report.target_sectors)} |
| **Total Scanned** | {self.screener_report.total_scanned} |
| **Passed Technical** | {self.screener_report.passed_technical} |
| **Final Candidates** | {len(self.screener_report.candidates)} |

## 🏆 Top Picks

| Rank | Symbol | Sector | Score | RS | Pattern | Signal |
|------|--------|--------|-------|----| --------|--------|
"""
            for c in self.screener_report.top_picks[:10]:
                content += f"| {c.rank} | {c.symbol} | {c.sector_name} | {c.score_total:.0f} | {c.technical.rs_rating} | {c.pattern.pattern_type.value} | {c.signal.value} |\n"
            
            # Top 5 detail với Trading Plan
            content += "\n## 📝 Chi tiết Top 5 Candidates\n"
            
            for c in self.screener_report.top_picks[:5]:
                price = c.technical.price
                buy_point = c.pattern.buy_point if c.pattern.buy_point > 0 else price * 1.02
                buy_zone_max = buy_point * 1.05
                stop_loss = buy_point * 0.93
                target_20 = buy_point * 1.20
                target_25 = buy_point * 1.25
                
                content += f"""
### {c.rank}. {c.symbol} - {c.sector_name}

**Scores:** Fundamental {c.score_fundamental:.0f} | Technical {c.score_technical:.0f} | Pattern {c.score_pattern:.0f} | News {c.score_news:.0f} | **Total: {c.score_total:.0f}**

**Technical:**
- Giá: {price:,.0f} | RS: {c.technical.rs_rating} | RSI: {c.technical.rsi_14:.0f}
- MA: {'✅ TRÊN' if c.technical.above_ma50 else '❌ DƯỚI'} MA50 | Volume Ratio: {c.technical.volume_ratio:.2f}x

**Pattern:** {c.pattern.pattern_type.value} (Quality: {c.pattern.pattern_quality:.0f})

"""
                # News section
                if c.news and c.news.articles:
                    content += f"**📰 News ({len(c.news.articles)} bài):**\n"
                    for a in c.news.articles[:3]:
                        title = a.get('title', '')[:80]
                        source = a.get('source', '')
                        content += f"- {title}... ({source})\n"
                    sentiment_emoji = "🟢" if c.news.sentiment == "positive" else "🔴" if c.news.sentiment == "negative" else "🟡"
                    content += f"- Sentiment: {sentiment_emoji} {c.news.sentiment.upper()} ({c.news.sentiment_score:+.2f})\n"
                    if c.news.key_topics:
                        content += f"- Topics: {', '.join(c.news.key_topics)}\n"
                else:
                    content += "**📰 News:** Không có tin tức đáng chú ý\n"
                
                content += f"""
**📈 TRADING PLAN:**
| Level | Giá | Ghi chú |
|-------|-----|---------|
| 🎯 **Buy Point** | {buy_point:,.0f} | Breakout từ pattern |
| 🛒 **Buy Zone** | {buy_point:,.0f} - {buy_zone_max:,.0f} | Mua trong vùng này |
| 🛑 **Stop Loss** | {stop_loss:,.0f} | Cắt lỗ -7% |
| 💰 **Target 1** | {target_20:,.0f} | +20% |
| 💰 **Target 2** | {target_25:,.0f} | +25% |

**Signal:** {c.signal.value}

"""
                if c.ai_analysis:
                    content += f"**🤖 AI Analysis:**\n{c.ai_analysis}\n\n"
                
                content += "---\n"
            
            # AI Summary
            if self.screener_report.ai_analysis:
                content += f"""
## 🤖 AI Summary - Stock Screening
{self.screener_report.ai_analysis}
"""
        
        # Footer
        content += f"""
---

# ⚠️ DISCLAIMER

*Báo cáo này được tạo tự động bởi hệ thống CANSLIM Scanner.*
*Thông tin chỉ mang tính chất tham khảo, không phải khuyến nghị đầu tư.*
*Nhà đầu tư tự chịu trách nhiệm với quyết định giao dịch của mình.*

---
**Generated:** {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return content
    
    def _save_report(self, content: str) -> str:
        """Lưu báo cáo"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        filename = os.path.join(
            self.output_dir,
            f"canslim_report_{self.timestamp.strftime('%Y%m%d_%H%M')}.md"
        )
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return filename


def main():
    """Main entry point"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🚀 CANSLIM FULL PIPELINE 🚀                               ║
║              3-in-1: Market + Sector + Stock Screening                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Check config
    config = get_config()
    ai_provider, ai_key = config.get_ai_provider()
    
    print(f"📡 Data Source: {config.get_data_source()}")
    print(f"🤖 AI Provider: {ai_provider.upper() if ai_provider else 'Chưa cấu hình'}")
    print(f"📁 Output: {config.output.OUTPUT_DIR}")
    
    if not ai_key:
        print("\n⚠️ Không có AI key - báo cáo sẽ không có phân tích AI")
        print("   Điền API key vào config.py để có đầy đủ tính năng")
    
    # Run pipeline
    runner = FullPipelineRunner()
    
    # Có thể chỉ định sectors cụ thể hoặc để auto detect từ Module 2
    output_file = runner.run(target_sectors=None)  # Auto detect
    
    print("\n" + "="*80)
    print("🎉 HOÀN THÀNH PIPELINE!")
    print("="*80)
    print(f"\n📄 File output: {output_file}")
    print("\nMở file để xem báo cáo đầy đủ.")
    
    return output_file


if __name__ == "__main__":
    main()