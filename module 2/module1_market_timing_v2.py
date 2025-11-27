#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     MODULE 1 v2: MARKET TIMING - ĐỊNH THỜI ĐIỂM THỊ TRƯỜNG                  ║
║              Sử dụng Config chung + Volume Profile                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# Import từ các module chung
from config import get_config, APIKeys, UnifiedConfig
from data_collector import EnhancedDataCollector, get_data_collector, EnhancedStockData
from volume_profile import VolumeProfileFormatter

# Import AI Provider
try:
    from ai_providers import AIProvider, AIConfig
except ImportError:
    AIProvider = None


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MarketTimingConfig:
    """Config cho Module 1 - có thể tạo từ UnifiedConfig"""
    
    # API
    VNSTOCK_API_KEY: str = ""
    DATA_SOURCE: str = "VCI"
    
    # Indices
    MAIN_INDEX: str = "VNINDEX"
    COMPARISON_INDICES: List[str] = field(default_factory=lambda: ["VN30", "VNMID"])
    SECTOR_INDICES: List[str] = field(default_factory=lambda: [
        "VNFIN", "VNREAL", "VNMAT", "VNIT", "VNENERGY",
        "VNHEAL", "VNCOND", "VNIND", "VNUTI"
    ])
    
    # Lookback
    LOOKBACK_DAYS: int = 120
    
    # AI
    AI_PROVIDER: str = ""
    AI_API_KEY: str = ""
    AI_MODEL: str = ""
    AI_MAX_TOKENS: int = 4096
    AI_TEMPERATURE: float = 0.7
    
    # Volume Profile
    ENABLE_VOLUME_PROFILE: bool = True
    VP_LOOKBACK_DAYS: int = 20
    
    # Output
    OUTPUT_DIR: str = "./output"
    SAVE_REPORT: bool = True


def create_config_from_unified() -> MarketTimingConfig:
    """Tạo MarketTimingConfig từ UnifiedConfig"""
    unified = get_config()
    
    config = MarketTimingConfig()
    config.VNSTOCK_API_KEY = unified.get_vnstock_key()
    config.DATA_SOURCE = unified.get_data_source()
    
    ai_provider, ai_key = unified.get_ai_provider()
    config.AI_PROVIDER = ai_provider
    config.AI_API_KEY = ai_key
    
    config.LOOKBACK_DAYS = unified.analysis.LOOKBACK_DAYS
    config.OUTPUT_DIR = unified.output.OUTPUT_DIR
    config.SAVE_REPORT = unified.output.SAVE_REPORTS
    
    config.ENABLE_VOLUME_PROFILE = True
    config.VP_LOOKBACK_DAYS = unified.volume_profile.LOOKBACK_DAYS
    
    return config


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MarketBreadth:
    """Độ rộng thị trường"""
    advances: int = 0
    declines: int = 0
    unchanged: int = 0
    
    @property
    def ad_ratio(self) -> float:
        return self.advances / self.declines if self.declines > 0 else 0


@dataclass
class MoneyFlow:
    """Dòng tiền"""
    foreign_net: float = 0.0
    proprietary_net: float = 0.0
    total_value: float = 0.0
    top_foreign_buy: List[Tuple[str, float]] = field(default_factory=list)
    top_foreign_sell: List[Tuple[str, float]] = field(default_factory=list)


@dataclass
class SectorData:
    """Dữ liệu ngành"""
    code: str
    name: str
    change_1d: float = 0.0
    change_5d: float = 0.0
    change_1m: float = 0.0


@dataclass
class MarketReport:
    """Báo cáo tổng hợp"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Index data
    vnindex: EnhancedStockData = None
    vn30: EnhancedStockData = None
    vnmid: EnhancedStockData = None
    
    # Market internals
    breadth: MarketBreadth = field(default_factory=MarketBreadth)
    money_flow: MoneyFlow = field(default_factory=MoneyFlow)
    
    # Sectors
    sectors: List[SectorData] = field(default_factory=list)
    
    # Analysis
    market_color: str = "🟡 VÀNG"
    market_score: int = 50
    trend_status: str = "SIDEWAY"
    key_signals: List[str] = field(default_factory=list)
    
    # AI
    ai_analysis: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# MARKET ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class MarketTimingAnalyzer:
    """Phân tích Market Timing với Volume Profile"""
    
    SECTOR_NAMES = {
        'VNFIN': 'Tài chính',
        'VNREAL': 'Bất động sản',
        'VNMAT': 'Nguyên vật liệu',
        'VNIT': 'Công nghệ',
        'VNENERGY': 'Năng lượng',
        'VNHEAL': 'Y tế',
        'VNCOND': 'Tiêu dùng',
        'VNIND': 'Công nghiệp',
        'VNUTI': 'Tiện ích',
    }
    
    def __init__(self, config: MarketTimingConfig):
        self.config = config
        self.collector = get_data_collector(
            enable_volume_profile=config.ENABLE_VOLUME_PROFILE
        )
    
    def collect_data(self) -> MarketReport:
        """Thu thập dữ liệu"""
        print("\n" + "="*60)
        print("📊 THU THẬP DỮ LIỆU THỊ TRƯỜNG")
        print("="*60)
        
        report = MarketReport()
        
        # 1. VNIndex với Volume Profile
        print("\n[1/4] VN-INDEX...")
        report.vnindex = self.collector.get_stock_data(
            "VNINDEX", 
            lookback_days=self.config.LOOKBACK_DAYS,
            include_vp=self.config.ENABLE_VOLUME_PROFILE
        )
        
        if report.vnindex.price > 0:
            print(f"   ✓ VNIndex: {report.vnindex.price:,.0f} ({report.vnindex.change_1d:+.2f}%)")
            if report.vnindex.poc > 0:
                print(f"   📊 Volume Profile: POC={report.vnindex.poc:,.0f} | "
                      f"VA={report.vnindex.val:,.0f}-{report.vnindex.vah:,.0f}")
        
        # 2. VN30
        print("\n[2/4] VN30...")
        report.vn30 = self.collector.get_stock_data("VN30", include_vp=False)
        if report.vn30.price > 0:
            print(f"   ✓ VN30: {report.vn30.price:,.0f} ({report.vn30.change_1d:+.2f}%)")
        
        # 3. VNMID
        print("\n[3/4] VNMID...")
        report.vnmid = self.collector.get_stock_data("VNMID", include_vp=False)
        
        # 4. Sectors
        print("\n[4/4] CHỈ SỐ NGÀNH...")
        for code in self.config.SECTOR_INDICES[:5]:  # Giới hạn 5 ngành
            data = self.collector.get_stock_data(code, lookback_days=30, include_vp=False)
            if data.price > 0:
                sector = SectorData(
                    code=code,
                    name=self.SECTOR_NAMES.get(code, code),
                    change_1d=data.change_1d,
                    change_5d=data.change_5d,
                    change_1m=data.change_1m
                )
                report.sectors.append(sector)
                print(f"   ✓ {code}: {data.change_1d:+.2f}%")
        
        # Sort sectors
        report.sectors.sort(key=lambda x: x.change_1d, reverse=True)
        
        # Breadth (estimate)
        report.breadth = self._estimate_breadth(report)
        
        # Money flow (placeholder)
        report.money_flow = MoneyFlow(
            foreign_net=-143.8,
            proprietary_net=43.1,
            total_value=18500
        )
        
        return report
    
    def _estimate_breadth(self, report: MarketReport) -> MarketBreadth:
        """Ước tính breadth từ sector data"""
        breadth = MarketBreadth()
        
        # Estimate từ số ngành tăng/giảm
        advances = sum(1 for s in report.sectors if s.change_1d > 0)
        declines = sum(1 for s in report.sectors if s.change_1d < 0)
        
        # Scale lên
        scale = 30
        breadth.advances = advances * scale + 50
        breadth.declines = declines * scale + 50
        breadth.unchanged = 30
        
        return breadth
    
    def analyze(self, report: MarketReport) -> MarketReport:
        """Phân tích và tính điểm"""
        print("\n" + "="*60)
        print("🔍 PHÂN TÍCH THỊ TRƯỜNG")
        print("="*60)
        
        vni = report.vnindex
        if vni is None or vni.price == 0:
            return report
        
        signals = []
        score = 0
        
        # 1. Price vs MA (30 điểm)
        if vni.price > vni.ma20 and vni.ma20 > vni.ma50:
            score += 30
            signals.append(f"✅ Bullish: Giá({vni.price:,.0f}) > MA20({vni.ma20:,.0f}) & MA50({vni.ma50:,.0f})")
        elif vni.price > vni.ma50:
            score += 15
            signals.append(f"✅ Giá trên MA50")
        elif vni.price < vni.ma20 and vni.ma20 < vni.ma50:
            score -= 30
            signals.append(f"❌ Bearish: Giá < MA20 < MA50")
        else:
            signals.append(f"➖ MA chưa rõ xu hướng")
        
        # 2. RSI (15 điểm)
        if vni.rsi_14 > 70:
            score -= 10
            signals.append(f"⚠️ RSI quá mua: {vni.rsi_14:.0f}")
        elif vni.rsi_14 < 30:
            score += 10
            signals.append(f"📈 RSI quá bán: {vni.rsi_14:.0f}")
        elif vni.rsi_14 > 50:
            score += 10
            signals.append(f"✅ RSI tích cực: {vni.rsi_14:.0f}")
        else:
            score -= 5
            signals.append(f"❌ RSI yếu: {vni.rsi_14:.0f}")
        
        # 3. MACD (15 điểm)
        if vni.macd_hist > 0:
            score += 15
            signals.append("✅ MACD Histogram dương")
        else:
            score -= 15
            signals.append("❌ MACD Histogram âm")
        
        # 4. ADX (10 điểm)
        if vni.adx > 25:
            score += 10
            signals.append(f"✅ Trend mạnh bullish (ADX={vni.adx:.0f})")
        else:
            signals.append(f"➖ Trend yếu (ADX={vni.adx:.0f})")
        
        # 5. Breadth (15 điểm)
        ad = report.breadth.ad_ratio
        if ad >= 1.5:
            score += 15
            signals.append(f"✅ Breadth rất tốt (A/D={ad:.2f})")
        elif ad >= 1:
            score += 5
            signals.append(f"✅ Breadth tích cực (A/D={ad:.2f})")
        else:
            score -= 10
            signals.append(f"❌ Breadth yếu (A/D={ad:.2f})")
        
        # 6. Money Flow (15 điểm)
        mf = report.money_flow
        if mf.foreign_net > 0:
            score += 10
            signals.append(f"✅ Khối ngoại mua ròng ({mf.foreign_net:+.0f} tỷ)")
        else:
            score -= 10
            signals.append(f"❌ Khối ngoại bán mạnh ({mf.foreign_net:+.0f} tỷ)")
        
        # 7. Volume Profile signals (bonus)
        if vni.poc > 0:
            if vni.price_vs_va == "ABOVE_VA":
                score += 5
                signals.append(f"📈 Giá TRÊN Value Area (VAH={vni.vah:,.0f})")
            elif vni.price_vs_va == "BELOW_VA":
                score -= 5
                signals.append(f"📉 Giá DƯỚI Value Area (VAL={vni.val:,.0f})")
            else:
                signals.append(f"📊 Giá TRONG Value Area ({vni.val:,.0f}-{vni.vah:,.0f})")
        
        # Market Color
        report.market_score = max(-100, min(100, score))
        
        if score >= 40:
            report.market_color = "🟢 XANH - TẤN CÔNG"
            report.trend_status = "UPTREND"
        elif score >= 0:
            report.market_color = "🟡 VÀNG - PHÒNG THỦ"
            report.trend_status = "SIDEWAY"
        else:
            report.market_color = "🔴 ĐỎ - RÚT LUI"
            report.trend_status = "DOWNTREND"
        
        report.key_signals = signals
        
        # Print
        print(f"\n📊 ĐIỂM THỊ TRƯỜNG: {report.market_score}/100")
        print(f"🎯 {report.market_color}")
        for sig in signals:
            print(f"   {sig}")
        
        return report


# ══════════════════════════════════════════════════════════════════════════════
# AI GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class MarketTimingAIGenerator:
    """Tạo báo cáo AI"""
    
    SYSTEM_PROMPT = """Bạn là Giám đốc Phân tích Chiến lược tại một quỹ đầu tư quy mô 100 tỷ VNĐ.
Phong cách: Thận trọng, dựa trên dữ liệu (Data-driven), tuân thủ VSA và quản trị rủi ro chặt chẽ.
Luôn trả lời bằng tiếng Việt, chuyên nghiệp."""
    
    def __init__(self, config: MarketTimingConfig):
        self.config = config
        self.ai = self._init_ai()
    
    def _init_ai(self) -> Optional[AIProvider]:
        if not self.config.AI_API_KEY or AIProvider is None:
            return None
        
        try:
            ai_config = AIConfig(
                provider=self.config.AI_PROVIDER,
                api_key=self.config.AI_API_KEY,
                model=self.config.AI_MODEL,
                max_tokens=self.config.AI_MAX_TOKENS,
                temperature=self.config.AI_TEMPERATURE,
                system_prompt=self.SYSTEM_PROMPT
            )
            return AIProvider(ai_config)
        except Exception as e:
            print(f"⚠️ Lỗi AI: {e}")
            return None
    
    def generate_prompt(self, report: MarketReport) -> str:
        """Tạo prompt"""
        vni = report.vnindex
        vn30 = report.vn30
        
        # Volume Profile section
        vp_section = ""
        if vni and vni.poc > 0:
            vp_section = f"""
📊 VOLUME PROFILE (20 ngày):
   - POC (Point of Control): {vni.poc:,.0f}
   - Value Area: {vni.val:,.0f} - {vni.vah:,.0f}
   - Giá hiện tại vs POC: {vni.price_vs_poc}
   - Giá hiện tại vs VA: {vni.price_vs_va}
   - VP Support: {', '.join([f'{p:,.0f}' for p in vni.vp_support[:3]]) if vni.vp_support else 'N/A'}
   - VP Resistance: {', '.join([f'{p:,.0f}' for p in vni.vp_resistance[:3]]) if vni.vp_resistance else 'N/A'}
"""
        
        # Sectors
        sectors_str = "\n".join([
            f"   {i+1}. {s.name}: {s.change_1d:+.2f}% (1D)"
            for i, s in enumerate(report.sectors[:5])
        ])
        
        prompt = f"""
═══════════════════════════════════════════════════════════════
DỮ LIỆU THỊ TRƯỜNG - {report.timestamp.strftime('%d/%m/%Y %H:%M')}
═══════════════════════════════════════════════════════════════

📈 VN-INDEX:
   - Giá: {vni.price:,.0f} | Thay đổi: {vni.change_1d:+.2f}%
   - OHLC: O={vni.open:,.0f} H={vni.high:,.0f} L={vni.low:,.0f} C={vni.price:,.0f}
   - MA20: {vni.ma20:,.0f} | MA50: {vni.ma50:,.0f}
   - RSI(14): {vni.rsi_14:.1f}
   - MACD Histogram: {vni.macd_hist:+.2f}
   - ADX: {vni.adx:.1f}
   - Volume Ratio: {vni.volume_ratio:.2f}x
{vp_section}
📊 VN30:
   - Giá: {vn30.price:,.0f} | Thay đổi: {vn30.change_1d:+.2f}%
   - RSI: {vn30.rsi_14:.1f}

📉 ĐỘ RỘNG THỊ TRƯỜNG:
   - Tăng: {report.breadth.advances} | Giảm: {report.breadth.declines}
   - A/D Ratio: {report.breadth.ad_ratio:.2f}

💰 DÒNG TIỀN:
   - Khối ngoại: {report.money_flow.foreign_net:+.1f} tỷ
   - Tự doanh: {report.money_flow.proprietary_net:+.1f} tỷ

🏭 TOP NGÀNH:
{sectors_str}

🎯 ĐÁNH GIÁ SƠ BỘ:
   - Market Color: {report.market_color}
   - Score: {report.market_score}/100

═══════════════════════════════════════════════════════════════

NHIỆM VỤ: Viết BÁO CÁO CHIẾN LƯỢC NGÀY với cấu trúc:

1. TỔNG QUAN THỊ TRƯỜNG
   - Xu hướng, phân tích VSA, tâm lý

2. PHÂN TÍCH CẤU TRÚC  
   - So sánh VN30 vs VNIndex
   - Phân kỳ (nếu có)

3. VOLUME PROFILE INSIGHTS
   - Ý nghĩa của POC và Value Area hiện tại
   - Các vùng Support/Resistance từ VP

4. DÒNG TIỀN & NGÀNH
   - Hành động Khối ngoại, Tự doanh
   - Ngành dẫn dắt

5. KỊCH BẢN "WHAT-IF" (3 kịch bản với xác suất)
   - Điều kiện kích hoạt CỤ THỂ (mức giá, volume)
   - Hành động tương ứng

6. KHUYẾN NGHỊ
   - Tỷ trọng CP/Tiền mặt
   - Top ngành theo dõi
"""
        return prompt
    
    def generate(self, report: MarketReport) -> str:
        """Tạo báo cáo AI"""
        if not self.ai:
            return "⚠️ AI chưa được cấu hình"
        
        print("\n" + "="*60)
        print(f"🤖 ĐANG TẠO BÁO CÁO AI ({self.config.AI_PROVIDER.upper()})...")
        print("="*60)
        
        prompt = self.generate_prompt(report)
        
        try:
            response = self.ai.chat(prompt)
            print("✓ Hoàn thành!")
            return response
        except Exception as e:
            return f"❌ Lỗi: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MODULE
# ══════════════════════════════════════════════════════════════════════════════

class MarketTimingModule:
    """Module chính"""
    
    def __init__(self, config: MarketTimingConfig = None):
        self.config = config or create_config_from_unified()
        self.analyzer = MarketTimingAnalyzer(self.config)
        self.ai_generator = MarketTimingAIGenerator(self.config)
        self.report: MarketReport = None
    
    def run(self) -> MarketReport:
        """Chạy module"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║     MODULE 1: MARKET TIMING + VOLUME PROFILE                 ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # 1. Thu thập
        self.report = self.analyzer.collect_data()
        
        # 2. Phân tích
        self.report = self.analyzer.analyze(self.report)
        
        # 3. AI
        self.report.ai_analysis = self.ai_generator.generate(self.report)
        
        # 4. Print
        self._print_report()
        
        # 5. Save
        if self.config.SAVE_REPORT:
            self._save_report()
        
        return self.report
    
    def _print_report(self):
        """In báo cáo"""
        print("\n" + "─"*70)
        print("🤖 PHÂN TÍCH TỪ AI:")
        print("─"*70)
        print(self.report.ai_analysis)
    
    def _save_report(self):
        """Lưu báo cáo"""
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        
        filename = os.path.join(
            self.config.OUTPUT_DIR,
            f"market_timing_{self.report.timestamp.strftime('%Y%m%d_%H%M')}.md"
        )
        
        vni = self.report.vnindex
        
        content = f"""# BÁO CÁO MARKET TIMING
**Ngày:** {self.report.timestamp.strftime('%d/%m/%Y %H:%M')}

## TỔNG QUAN
- **Market Color:** {self.report.market_color}
- **Score:** {self.report.market_score}/100
- **VNIndex:** {vni.price:,.0f} ({vni.change_1d:+.2f}%)

## VOLUME PROFILE
- **POC:** {vni.poc:,.0f}
- **Value Area:** {vni.val:,.0f} - {vni.vah:,.0f}
- **Position:** {vni.price_vs_va}

## TÍN HIỆU CHÍNH
{chr(10).join(['- ' + s for s in self.report.key_signals])}

## PHÂN TÍCH AI
{self.report.ai_analysis}
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✓ Đã lưu: {filename}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    module = MarketTimingModule()
    report = module.run()
