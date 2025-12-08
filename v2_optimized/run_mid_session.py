#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                 CANSLIM MID-SESSION PIPELINE                                  ║
║            Gộp Market Timing + Sector Rotation (Bỏ Stock Screener)            ║
6: ╠══════════════════════════════════════════════════════════════════════════════╣
║  OUTPUT: 1 file Markdown duy nhất với thông tin thị trường và ngành           ║
║  - Module 1: Market Timing (Traffic Light, Volume Profile)                   ║
║  - Module 2: Sector Rotation (Top ngành, RS Ranking)                         ║
║  (Không chạy Module 3 vì giữa phiên chưa cần lọc cổ phiếu)                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

Cách sử dụng:
    python run_mid_session.py
"""

import os
from datetime import datetime
from typing import Dict, List, Optional

# Import config
from config import get_config

# Import modules
from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified as create_m1_config
from module2_sector_rotation_v3 import SectorRotationModule, create_config_from_unified as create_m2_config
from email_notifier import EmailNotifier
from history_manager import HistoryManager


class MidSessionPipelineRunner:
    """Chạy pipeline giữa phiên (Module 1 & 2)"""
    
    def __init__(self):
        self.config = get_config()
        self.output_dir = self.config.output.OUTPUT_DIR
        self.timestamp = datetime.now()
        
        # Results
        self.market_report = None
        self.sector_report = None
    
    def run(self) -> str:
        """
        Chạy pipeline giữa phiên
        """
        print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🚀 CANSLIM MID-SESSION PIPELINE 🚀                        ║
║              Market Timing → Sector Rotation (No Screener)                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """)
        
        # ══════════════════════════════════════════════════════════════════════
        # PREPARE HISTORY CONTEXT
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("📜 FETCHING HISTORY CONTEXT")
        print("="*80)
        
        history_manager = HistoryManager(self.output_dir)
        history_context = history_manager.get_ai_context()
        print("✓ History context loaded.")

        # ══════════════════════════════════════════════════════════════════════
        # MODULE 1: MARKET TIMING
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("📊 MODULE 1: MARKET TIMING")
        print("="*80)
        
        m1_config = create_m1_config()
        m1_config.SAVE_REPORT = False  # Không save riêng
        
        m1_module = MarketTimingModule(m1_config)
        self.market_report = m1_module.run(history_context)
        
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
        
        # ══════════════════════════════════════════════════════════════════════
        # GENERATE COMBINED OUTPUT
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("📝 GENERATING MID-SESSION REPORT")
        print("="*80)
        
        combined_report = self._generate_combined_report()
        output_file = self._save_report(combined_report)
        
        print(f"\n✅ HOÀN THÀNH!")
        print(f"📄 Output file: {output_file}")
        
        # Send Email
        try:
            notifier = EmailNotifier()
            if notifier.config.ENABLED:
                notifier.send_report(combined_report, output_file)
        except Exception as e:
            print(f"⚠️ Email Error: {e}")
        
        return output_file
    
    def _generate_combined_report(self) -> str:
        """Tạo báo cáo gộp từ Module 1 & 2"""
        
        # Header
        content = f"""# 📊 CANSLIM MID-SESSION REPORT
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
                rs = getattr(sector, 'rs_rating', 50)
                content += f"| {i} | {name} | {change:+.2f}% | {rs:.0f} |\n"
            
            if hasattr(self.sector_report, 'ai_analysis') and self.sector_report.ai_analysis:
                content += f"""
## 🤖 AI Analysis - Sector Rotation
{self.sector_report.ai_analysis}
"""
        
        # Footer
        content += f"""
---

# ⚠️ DISCLAIMER

*Báo cáo này được tạo tự động bởi hệ thống CANSLIM Scanner (Mid-Session).*
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
            f"canslim_mid_session_{self.timestamp.strftime('%Y%m%d_%H%M')}.md"
        )
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return filename


def main():
    """Main entry point"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🚀 CANSLIM MID-SESSION PIPELINE 🚀                        ║
║              2-in-1: Market + Sector (No Stock Screening)                    ║
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
    runner = MidSessionPipelineRunner()
    output_file = runner.run()
    
    print("\n" + "="*80)
    print("🎉 HOÀN THÀNH PIPELINE GIỮA PHIÊN!")
    print("="*80)
    print(f"\n📄 File output: {output_file}")
    print("\nMở file để xem báo cáo.")
    
    return output_file


if __name__ == "__main__":
    main()
