#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     MODULE 2 v2: SECTOR ROTATION - PHÂN TÍCH LUÂN CHUYỂN NGÀNH              ║
║              Sử dụng Config chung + Volume Profile                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# Import từ các module chung
from config import get_config, UnifiedConfig
from data_collector import EnhancedDataCollector, get_data_collector, EnhancedStockData

# Import AI Provider
try:
    from ai_providers import AIProvider, AIConfig
except ImportError:
    AIProvider = None


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

class SectorPhase(Enum):
    LEADING = "🚀 Dẫn dắt"
    IMPROVING = "📈 Tăng tốc"
    WEAKENING = "📉 Suy yếu"
    LAGGING = "⛔ Tụt hậu"


@dataclass
class SectorRotationConfig:
    """Config cho Module 2"""
    
    # API
    VNSTOCK_API_KEY: str = ""
    DATA_SOURCE: str = "VCI"
    
    # Sector indices - CHỈ 7 NGÀNH HỢP LỆ (đã xác nhận hoạt động với VCI)
    # Loại bỏ: VNENERGY, VNIND, VNUTI (không khả dụng)
    SECTOR_INDICES: Dict[str, str] = field(default_factory=lambda: {
        'VNFIN': 'Tài chính',
        'VNREAL': 'Bất động sản',
        'VNMAT': 'Nguyên vật liệu',
        'VNIT': 'Công nghệ',
        'VNHEAL': 'Y tế',
        'VNCOND': 'Tiêu dùng không thiết yếu',
        'VNCONS': 'Tiêu dùng thiết yếu',
    })
    
    # Rate limit
    API_DELAY: float = 0.3
    
    # Lookback
    LOOKBACK_DAYS: int = 90
    
    # AI
    AI_PROVIDER: str = ""
    AI_API_KEY: str = ""
    AI_MODEL: str = ""
    AI_MAX_TOKENS: int = 4096
    AI_TEMPERATURE: float = 0.7
    
    # Volume Profile
    ENABLE_VOLUME_PROFILE: bool = True
    
    # Output
    OUTPUT_DIR: str = "./output"
    SAVE_REPORT: bool = True


def create_config_from_unified() -> SectorRotationConfig:
    """Tạo SectorRotationConfig từ UnifiedConfig"""
    unified = get_config()
    
    config = SectorRotationConfig()
    config.VNSTOCK_API_KEY = unified.get_vnstock_key()
    config.DATA_SOURCE = unified.get_data_source()
    config.API_DELAY = unified.rate_limit.API_DELAY
    
    ai_provider, ai_key = unified.get_ai_provider()
    config.AI_PROVIDER = ai_provider
    config.AI_API_KEY = ai_key
    
    config.OUTPUT_DIR = unified.output.OUTPUT_DIR
    config.SAVE_REPORT = unified.output.SAVE_REPORTS
    
    return config


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SectorData:
    """Dữ liệu ngành"""
    code: str
    name: str
    
    # Performance
    change_1d: float = 0.0
    change_5d: float = 0.0
    change_1m: float = 0.0
    change_3m: float = 0.0
    
    # RS vs VNIndex
    rs_vs_vnindex_1m: float = 0.0
    
    # Technical
    rsi_14: float = 50.0
    above_ma20: bool = False
    above_ma50: bool = False
    
    # Volume Profile
    poc: float = 0.0
    vah: float = 0.0
    val: float = 0.0
    price_vs_va: str = ""
    
    # Scoring
    composite_score: float = 0.0
    rank: int = 0
    phase: SectorPhase = SectorPhase.LAGGING
    
    # Raw data
    data: EnhancedStockData = None


@dataclass
class SectorRotationReport:
    """Báo cáo tổng hợp"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # VNIndex reference
    vnindex_change_1d: float = 0.0
    vnindex_change_1m: float = 0.0
    
    # Sectors
    sectors: List[SectorData] = field(default_factory=list)
    
    # Categorized
    leading_sectors: List[SectorData] = field(default_factory=list)
    improving_sectors: List[SectorData] = field(default_factory=list)
    weakening_sectors: List[SectorData] = field(default_factory=list)
    lagging_sectors: List[SectorData] = field(default_factory=list)
    
    # AI
    ai_analysis: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class SectorRotationAnalyzer:
    """Phân tích Sector Rotation"""
    
    def __init__(self, config: SectorRotationConfig):
        self.config = config
        self.collector = get_data_collector(
            enable_volume_profile=config.ENABLE_VOLUME_PROFILE
        )
    
    def analyze(self) -> SectorRotationReport:
        """Phân tích tất cả ngành"""
        print("\n" + "="*60)
        print("📊 MODULE 2: SECTOR ROTATION ANALYSIS")
        print("="*60)
        
        report = SectorRotationReport()
        
        # 1. Lấy VNIndex
        print("\n[1/2] VNIndex baseline...")
        vnindex_data = self.collector.get_stock_data("VNINDEX", lookback_days=90, include_vp=False)
        report.vnindex_change_1d = vnindex_data.change_1d
        report.vnindex_change_1m = vnindex_data.change_1m
        print(f"   ✓ VNIndex: 1D={vnindex_data.change_1d:+.2f}%, 1M={vnindex_data.change_1m:+.2f}%")
        
        # 2. Phân tích từng ngành
        print("\n[2/2] Phân tích các ngành...")
        
        for code, name in self.config.SECTOR_INDICES.items():
            print(f"   📊 {name}...", end=" ")
            
            data = self.collector.get_stock_data(
                code, 
                lookback_days=self.config.LOOKBACK_DAYS,
                include_vp=self.config.ENABLE_VOLUME_PROFILE
            )
            
            if data.price == 0:
                print("✗")
                continue
            
            sector = SectorData(
                code=code,
                name=name,
                change_1d=data.change_1d,
                change_5d=data.change_5d,
                change_1m=data.change_1m,
                change_3m=data.change_3m,
                rs_vs_vnindex_1m=data.change_1m - report.vnindex_change_1m,
                rsi_14=data.rsi_14,
                above_ma20=data.above_ma20,
                above_ma50=data.above_ma50,
                poc=data.poc,
                vah=data.vah,
                val=data.val,
                price_vs_va=data.price_vs_va,
                data=data
            )
            
            # Tính composite score
            sector.composite_score = self._calc_score(sector)
            
            # Xác định phase
            sector.phase = self._determine_phase(sector)
            
            report.sectors.append(sector)
            print(f"✓ RS={sector.rs_vs_vnindex_1m:+.2f}% | {sector.phase.value}")
        
        # 3. Rank và categorize
        report.sectors.sort(key=lambda x: x.composite_score, reverse=True)
        for i, s in enumerate(report.sectors, 1):
            s.rank = i
        
        report.leading_sectors = [s for s in report.sectors if s.phase == SectorPhase.LEADING]
        report.improving_sectors = [s for s in report.sectors if s.phase == SectorPhase.IMPROVING]
        report.weakening_sectors = [s for s in report.sectors if s.phase == SectorPhase.WEAKENING]
        report.lagging_sectors = [s for s in report.sectors if s.phase == SectorPhase.LAGGING]
        
        return report
    
    def _calc_score(self, sector: SectorData) -> float:
        """Tính composite score"""
        score = 0
        
        # 1M Performance (30%)
        score += max(-30, min(30, sector.change_1m * 2))
        
        # RS vs VNIndex (30%)
        score += max(-30, min(30, sector.rs_vs_vnindex_1m * 3))
        
        # RSI position (20%)
        if 50 <= sector.rsi_14 <= 70:
            score += 20
        elif sector.rsi_14 > 70:
            score += 10
        elif sector.rsi_14 < 30:
            score += 15
        
        # MA alignment (20%)
        if sector.above_ma20 and sector.above_ma50:
            score += 20
        elif sector.above_ma20:
            score += 10
        
        return max(0, min(100, 50 + score))
    
    def _determine_phase(self, sector: SectorData) -> SectorPhase:
        """Xác định phase của ngành"""
        rs = sector.rs_vs_vnindex_1m
        momentum = sector.change_5d
        
        if rs > 3 and momentum > 0 and sector.above_ma20:
            return SectorPhase.LEADING
        elif rs > 0 and momentum > sector.change_1d:
            return SectorPhase.IMPROVING
        elif rs > 0 and momentum < 0:
            return SectorPhase.WEAKENING
        else:
            return SectorPhase.LAGGING


# ══════════════════════════════════════════════════════════════════════════════
# AI GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class SectorRotationAIGenerator:
    """Tạo báo cáo AI"""
    
    SYSTEM_PROMPT = """Bạn là Giám đốc Phân tích Ngành tại quỹ đầu tư.
Chuyên về: Sector Rotation, chu kỳ kinh doanh, Relative Strength.
Trả lời bằng tiếng Việt, chuyên nghiệp."""
    
    def __init__(self, config: SectorRotationConfig):
        self.config = config
        self.ai = self._init_ai()
    
    def _init_ai(self):
        if not self.config.AI_API_KEY or AIProvider is None:
            return None
        
        try:
            ai_config = AIConfig(
                provider=self.config.AI_PROVIDER,
                api_key=self.config.AI_API_KEY,
                max_tokens=self.config.AI_MAX_TOKENS,
                system_prompt=self.SYSTEM_PROMPT
            )
            return AIProvider(ai_config)
        except:
            return None
    
    def generate_prompt(self, report: SectorRotationReport) -> str:
        """Tạo prompt"""
        
        # Sector table
        sector_table = ""
        for s in report.sectors:
            vp_info = f"POC={s.poc:,.0f}" if s.poc > 0 else ""
            sector_table += f"""
   {s.rank}. {s.name:<20} | 1D: {s.change_1d:+.2f}% | 1M: {s.change_1m:+.2f}% | RS: {s.rs_vs_vnindex_1m:+.2f}% | {s.phase.value}
      RSI: {s.rsi_14:.0f} | MA20: {'✓' if s.above_ma20 else '✗'} | MA50: {'✓' if s.above_ma50 else '✗'} | {vp_info}"""
        
        prompt = f"""
═══════════════════════════════════════════════════════════════
BÁO CÁO SECTOR ROTATION - {report.timestamp.strftime('%d/%m/%Y')}
═══════════════════════════════════════════════════════════════

📊 BENCHMARK:
   VNIndex: 1D={report.vnindex_change_1d:+.2f}% | 1M={report.vnindex_change_1m:+.2f}%

📈 XẾP HẠNG NGÀNH:
{sector_table}

🚀 LEADING: {', '.join([s.name for s in report.leading_sectors]) or 'Không có'}
📈 IMPROVING: {', '.join([s.name for s in report.improving_sectors]) or 'Không có'}
📉 WEAKENING: {', '.join([s.name for s in report.weakening_sectors]) or 'Không có'}
⛔ LAGGING: {', '.join([s.name for s in report.lagging_sectors]) or 'Không có'}

═══════════════════════════════════════════════════════════════

YÊU CẦU PHÂN TÍCH:

1. ĐÁNH GIÁ CHU KỲ ROTATION
   - Thị trường đang ở giai đoạn nào? (Early/Mid/Late Cycle)
   - Dòng tiền đang luân chuyển từ ngành nào sang ngành nào?

2. NGÀNH CẦN TĂNG TỶ TRỌNG
   - 2-3 ngành tiềm năng outperform trong 2-4 tuần tới
   - Lý do cụ thể

3. NGÀNH CẦN GIẢM TỶ TRỌNG
   - Ngành có dấu hiệu distribution
   - Nên chốt lời/cắt lỗ

4. KỊCH BẢN ROTATION TIẾP THEO
   - Nếu thị trường tăng: Dòng tiền vào đâu?
   - Nếu thị trường giảm: Ngành nào chống chịu tốt?

5. KHUYẾN NGHỊ PHÂN BỔ
   - Cyclical: __%
   - Defensive: __%
   - Growth: __%
   - Cash: __%
"""
        return prompt
    
    def generate(self, report: SectorRotationReport) -> str:
        """Tạo báo cáo AI"""
        if not self.ai:
            return "⚠️ AI chưa cấu hình"
        
        print("\n" + "="*60)
        print(f"🤖 AI ANALYSIS ({self.config.AI_PROVIDER.upper()})...")
        print("="*60)
        
        try:
            response = self.ai.chat(self.generate_prompt(report))
            print("✓ Hoàn thành!")
            return response
        except Exception as e:
            return f"❌ Lỗi: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MODULE
# ══════════════════════════════════════════════════════════════════════════════

class SectorRotationModule:
    """Module chính"""
    
    def __init__(self, config: SectorRotationConfig = None):
        self.config = config or create_config_from_unified()
        self.analyzer = SectorRotationAnalyzer(self.config)
        self.ai_generator = SectorRotationAIGenerator(self.config)
        self.report: SectorRotationReport = None
    
    def run(self) -> SectorRotationReport:
        """Chạy module"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║     MODULE 2: SECTOR ROTATION + VOLUME PROFILE               ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # 1. Phân tích
        self.report = self.analyzer.analyze()
        
        # 2. AI
        self.report.ai_analysis = self.ai_generator.generate(self.report)
        
        # 3. Print
        self._print_report()
        
        # 4. Save
        if self.config.SAVE_REPORT:
            self._save_report()
        
        return self.report
    
    def _print_report(self):
        """In báo cáo"""
        print("\n" + "─"*70)
        print("📊 SUMMARY")
        print("─"*70)
        
        print(f"\n{'RANK':<5} {'NGÀNH':<20} {'1D':>8} {'1M':>8} {'RS':>8} {'PHASE':<15}")
        print("-"*70)
        
        for s in self.report.sectors:
            print(f"{s.rank:<5} {s.name:<20} {s.change_1d:>+7.2f}% {s.change_1m:>+7.2f}% "
                  f"{s.rs_vs_vnindex_1m:>+7.2f} {s.phase.value:<15}")
        
        print("\n" + "─"*70)
        print("🤖 AI ANALYSIS:")
        print("─"*70)
        print(self.report.ai_analysis)
    
    def _save_report(self):
        """Lưu báo cáo"""
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        
        filename = os.path.join(
            self.config.OUTPUT_DIR,
            f"sector_rotation_{self.report.timestamp.strftime('%Y%m%d_%H%M')}.md"
        )
        
        content = f"""# BÁO CÁO SECTOR ROTATION
**Ngày:** {self.report.timestamp.strftime('%d/%m/%Y %H:%M')}

## XẾP HẠNG NGÀNH

| Rank | Ngành | 1D | 1M | RS | Phase |
|------|-------|----|----|----| ------|
{''.join([f"| {s.rank} | {s.name} | {s.change_1d:+.2f}% | {s.change_1m:+.2f}% | {s.rs_vs_vnindex_1m:+.2f} | {s.phase.value} |" + chr(10) for s in self.report.sectors])}

## PHÂN LOẠI
- 🚀 Leading: {', '.join([s.name for s in self.report.leading_sectors]) or 'N/A'}
- 📈 Improving: {', '.join([s.name for s in self.report.improving_sectors]) or 'N/A'}
- 📉 Weakening: {', '.join([s.name for s in self.report.weakening_sectors]) or 'N/A'}

## AI ANALYSIS
{self.report.ai_analysis}
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✓ Đã lưu: {filename}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    module = SectorRotationModule()
    report = module.run()
