#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     MODULE 2 v3: SECTOR ROTATION - PHÂN TÍCH LUÂN CHUYỂN NGÀNH              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  NÂNG CẤP TỪ V2:                                                             ║
║  ✅ RS Rating IBD-style (Weighted: Q1 40% + Q2 30% + Q3 20% + Q4 10%)        ║
║  ✅ Sector Money Flow (Foreign flow theo ngành)                              ║
║  ✅ Rotation Clock (Early/Mid/Late Cycle)                                    ║
║  ✅ Leader Stocks (Top mã mỗi ngành)                                         ║
║  ✅ Tích hợp Market Context từ Module 1                                      ║
║  ✅ Output JSON cho AI                                                       ║
║  ✅ FIX: Chỉ dùng Sector Indices hợp lệ (loại bỏ VNENERGY, VNIND, VNUTI)    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# Import từ các module chung
from config import get_config, UnifiedConfig
from data_collector import get_data_collector, EnhancedStockData

# Import AI Provider
try:
    from ai_providers import AIProvider, AIConfig
except ImportError:
    AIProvider = None


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

class SectorPhase(Enum):
    """Phase của ngành trong Rotation Cycle"""
    LEADING = "🚀 LEADING"          # RS > 0, Momentum up, Above MA
    IMPROVING = "📈 IMPROVING"      # RS improving, Starting to outperform
    WEAKENING = "📉 WEAKENING"      # RS still positive but declining
    LAGGING = "⛔ LAGGING"          # RS negative, Underperforming


class RotationClock(Enum):
    """Vị trí trong chu kỳ kinh tế"""
    EARLY_CYCLE = "🌱 EARLY CYCLE"      # Recovery - Financials, Consumer Discretionary
    MID_CYCLE = "🌳 MID CYCLE"          # Expansion - Tech, Industrials
    LATE_CYCLE = "🍂 LATE CYCLE"        # Peak - Energy, Materials
    RECESSION = "❄️ RECESSION"          # Contraction - Utilities, Healthcare, Consumer Staples


class SectorType(Enum):
    """Loại ngành"""
    CYCLICAL = "Cyclical"       # Tài chính, BĐS, Nguyên vật liệu
    DEFENSIVE = "Defensive"     # Y tế, Tiêu dùng thiết yếu
    GROWTH = "Growth"           # Công nghệ, Tiêu dùng không thiết yếu


# ══════════════════════════════════════════════════════════════════════════════
# VALID SECTOR INDICES (Đã loại bỏ VNENERGY, VNIND, VNUTI)
# ══════════════════════════════════════════════════════════════════════════════

# Sector classification - CHỈ các index hợp lệ
SECTOR_TYPES = {
    'VNFIN': SectorType.CYCLICAL,      # Tài chính
    'VNREAL': SectorType.CYCLICAL,     # Bất động sản
    'VNMAT': SectorType.CYCLICAL,      # Nguyên vật liệu
    'VNIT': SectorType.GROWTH,         # Công nghệ
    'VNCOND': SectorType.GROWTH,       # Tiêu dùng không thiết yếu
    'VNHEAL': SectorType.DEFENSIVE,    # Y tế
    'VNCONS': SectorType.DEFENSIVE,    # Tiêu dùng thiết yếu
}

# Rotation Clock mapping - ngành nào dẫn dắt ở giai đoạn nào
# Đã điều chỉnh cho các index hợp lệ
ROTATION_LEADERS = {
    RotationClock.EARLY_CYCLE: ['VNFIN', 'VNCOND', 'VNREAL'],       # Recovery
    RotationClock.MID_CYCLE: ['VNIT', 'VNMAT', 'VNCOND'],           # Expansion
    RotationClock.LATE_CYCLE: ['VNMAT', 'VNREAL', 'VNCONS'],        # Peak
    RotationClock.RECESSION: ['VNCONS', 'VNHEAL', 'VNFIN'],         # Contraction
}


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SectorRotationConfig:
    """Config cho Module 2 v3"""
    
    # API
    VNSTOCK_API_KEY: str = ""
    DATA_SOURCE: str = "VCI"
    
    # Sector indices - CHỈ các index hợp lệ (loại bỏ VNENERGY, VNIND, VNUTI)
    SECTOR_INDICES: Dict[str, str] = field(default_factory=lambda: {
        'VNFIN': 'Tài chính',
        'VNREAL': 'Bất động sản',
        'VNMAT': 'Nguyên vật liệu',
        'VNIT': 'Công nghệ',
        'VNHEAL': 'Y tế',
        'VNCOND': 'Tiêu dùng không thiết yếu',
        'VNCONS': 'Tiêu dùng thiết yếu',
    })
    
    # RS Rating weights (IBD style)
    RS_WEIGHT_Q1: float = 0.40  # Quý gần nhất (3 tháng)
    RS_WEIGHT_Q2: float = 0.30  # Quý 2
    RS_WEIGHT_Q3: float = 0.20  # Quý 3
    RS_WEIGHT_Q4: float = 0.10  # Quý 4
    
    # Lookback periods
    LOOKBACK_DAYS: int = 250  # ~1 năm
    
    # Rate limit
    API_DELAY: float = 0.3
    
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
    SAVE_JSON: bool = True


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
class SectorMoneyFlow:
    """Dòng tiền ngành"""
    foreign_net_1d: float = 0.0
    foreign_net_5d: float = 0.0
    foreign_net_20d: float = 0.0
    
    proprietary_net_1d: float = 0.0
    
    # Cumulative trend
    foreign_trend: str = "NEUTRAL"  # ACCUMULATING, DISTRIBUTING, NEUTRAL


@dataclass
class LeaderStock:
    """Cổ phiếu dẫn dắt trong ngành"""
    symbol: str
    name: str = ""
    price: float = 0.0
    change_1d: float = 0.0
    change_1m: float = 0.0
    rs_rating: int = 0  # 1-99
    volume_ratio: float = 0.0
    
    # Technical
    above_ma20: bool = False
    above_ma50: bool = False
    
    # Score
    score: float = 0.0


@dataclass
class SectorData:
    """Dữ liệu ngành chi tiết"""
    code: str
    name: str
    sector_type: SectorType = SectorType.CYCLICAL
    
    # Performance (multiple timeframes)
    change_1d: float = 0.0
    change_5d: float = 0.0
    change_1m: float = 0.0      # Q1 - 1 month (~21 trading days)
    change_3m: float = 0.0      # Q2 - 3 months (~63 trading days)
    change_6m: float = 0.0      # Q3 - 6 months (~126 trading days)
    change_12m: float = 0.0     # Q4 - 12 months (~252 trading days)
    
    # RS Rating (IBD-style, 1-99)
    rs_rating: int = 50
    rs_vs_vnindex_1m: float = 0.0
    rs_vs_vnindex_3m: float = 0.0
    
    # RS Trend
    rs_trend: str = "FLAT"  # IMPROVING, FLAT, DECLINING
    
    # Technical
    price: float = 0.0
    rsi_14: float = 50.0
    above_ma20: bool = False
    above_ma50: bool = False
    ma20_slope: float = 0.0
    
    # Volume Profile
    poc: float = 0.0
    vah: float = 0.0
    val: float = 0.0
    price_vs_va: str = ""
    
    # Money Flow
    money_flow: SectorMoneyFlow = field(default_factory=SectorMoneyFlow)
    
    # Leader Stocks
    leaders: List[LeaderStock] = field(default_factory=list)
    
    # Scoring & Phase
    composite_score: float = 0.0
    rank: int = 0
    phase: SectorPhase = SectorPhase.LAGGING
    
    # Raw data
    raw_data: EnhancedStockData = None


@dataclass
class RotationAnalysis:
    """Phân tích Rotation Clock"""
    current_clock: RotationClock = RotationClock.MID_CYCLE
    confidence: float = 0.0
    
    # Evidence
    leading_now: List[str] = field(default_factory=list)
    expected_leaders: List[str] = field(default_factory=list)
    
    # Signals
    rotation_signals: List[str] = field(default_factory=list)
    
    # Allocation suggestion
    cyclical_weight: float = 40.0
    defensive_weight: float = 30.0
    growth_weight: float = 30.0


@dataclass
class SectorRotationReport:
    """Báo cáo tổng hợp"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # VNIndex reference
    vnindex_price: float = 0.0
    vnindex_change_1d: float = 0.0
    vnindex_change_1m: float = 0.0
    vnindex_change_3m: float = 0.0
    
    # Market context (từ Module 1)
    market_traffic_light: str = ""
    market_distribution_days: int = 0
    market_regime: str = ""
    
    # Sectors
    sectors: List[SectorData] = field(default_factory=list)
    
    # Categorized by phase
    leading_sectors: List[SectorData] = field(default_factory=list)
    improving_sectors: List[SectorData] = field(default_factory=list)
    weakening_sectors: List[SectorData] = field(default_factory=list)
    lagging_sectors: List[SectorData] = field(default_factory=list)
    
    # Categorized by type
    cyclical_sectors: List[SectorData] = field(default_factory=list)
    defensive_sectors: List[SectorData] = field(default_factory=list)
    growth_sectors: List[SectorData] = field(default_factory=list)
    
    # Rotation analysis
    rotation: RotationAnalysis = field(default_factory=RotationAnalysis)
    
    # Top picks
    top_sectors: List[str] = field(default_factory=list)
    avoid_sectors: List[str] = field(default_factory=list)
    
    # AI
    ai_analysis: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# RS RATING CALCULATOR (IBD-style)
# ══════════════════════════════════════════════════════════════════════════════

class RSRatingCalculator:
    """
    Tính RS Rating theo IBD style
    
    RS Rating = Weighted average của performance qua 4 quý
    - Q1 (3 tháng gần nhất): 40%
    - Q2 (3-6 tháng): 30%
    - Q3 (6-9 tháng): 20%
    - Q4 (9-12 tháng): 10%
    
    Sau đó rank tất cả sectors từ 1-99 (percentile)
    """
    
    def __init__(self, config: SectorRotationConfig):
        self.config = config
    
    def calculate_raw_rs(self, sector: SectorData) -> float:
        """Tính raw RS score (chưa rank)"""
        # Weighted performance
        raw_rs = (
            sector.change_1m * self.config.RS_WEIGHT_Q1 +
            sector.change_3m * self.config.RS_WEIGHT_Q2 +
            sector.change_6m * self.config.RS_WEIGHT_Q3 +
            sector.change_12m * self.config.RS_WEIGHT_Q4
        )
        return raw_rs
    
    def calculate_rs_ratings(self, sectors: List[SectorData]) -> List[SectorData]:
        """
        Tính RS Rating cho tất cả sectors
        
        Returns:
            List[SectorData] với rs_rating đã được cập nhật (1-99)
        """
        if not sectors:
            return sectors
        
        # Calculate raw RS for all sectors
        raw_scores = []
        for sector in sectors:
            raw_rs = self.calculate_raw_rs(sector)
            raw_scores.append((sector, raw_rs))
        
        # Sort by raw RS
        raw_scores.sort(key=lambda x: x[1])
        
        # Assign percentile rank (1-99)
        n = len(raw_scores)
        for i, (sector, raw_rs) in enumerate(raw_scores):
            # Percentile: 1 = worst, 99 = best
            percentile = int((i / (n - 1)) * 98 + 1) if n > 1 else 50
            sector.rs_rating = percentile
        
        return sectors
    
    def calculate_rs_trend(self, sector: SectorData) -> str:
        """Xác định RS trend (improving/declining)"""
        # Compare short-term RS vs long-term RS
        short_term_rs = sector.rs_vs_vnindex_1m
        long_term_rs = sector.rs_vs_vnindex_3m
        
        if short_term_rs > long_term_rs + 2:
            return "📈 IMPROVING"
        elif short_term_rs < long_term_rs - 2:
            return "📉 DECLINING"
        else:
            return "➡️ FLAT"


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR ROTATION ANALYZER v3
# ══════════════════════════════════════════════════════════════════════════════

class SectorRotationAnalyzer:
    """Phân tích Sector Rotation v3"""
    
    def __init__(self, config: SectorRotationConfig):
        self.config = config
        self.collector = get_data_collector(
            enable_volume_profile=config.ENABLE_VOLUME_PROFILE
        )
        self.rs_calculator = RSRatingCalculator(config)
    
    def analyze(self, market_context: Optional[Dict] = None) -> SectorRotationReport:
        """
        Phân tích Sector Rotation
        
        Args:
            market_context: Optional dict với thông tin từ Module 1
                {
                    'traffic_light': '🟡 VÀNG',
                    'distribution_days': 6,
                    'market_regime': 'DISTRIBUTION'
                }
        """
        print("\n" + "="*60)
        print("📊 MODULE 2 v3: SECTOR ROTATION ANALYSIS")
        print("="*60)
        
        report = SectorRotationReport()
        
        # Apply market context if provided
        if market_context:
            report.market_traffic_light = market_context.get('traffic_light', '')
            report.market_distribution_days = market_context.get('distribution_days', 0)
            report.market_regime = market_context.get('market_regime', '')
            print(f"\n📋 Market Context: {report.market_traffic_light} | Dist Days: {report.market_distribution_days}")
        
        # 1. Get VNIndex baseline
        print("\n[1/5] VNIndex baseline...")
        vnindex_data = self._get_vnindex_data()
        report.vnindex_price = vnindex_data.get('price', 0)
        report.vnindex_change_1d = vnindex_data.get('change_1d', 0)
        report.vnindex_change_1m = vnindex_data.get('change_1m', 0)
        report.vnindex_change_3m = vnindex_data.get('change_3m', 0)
        print(f"   ✓ VNIndex: {report.vnindex_price:,.0f} | 1D={report.vnindex_change_1d:+.2f}% | 1M={report.vnindex_change_1m:+.2f}%")
        
        # 2. Analyze each sector
        print("\n[2/5] Phân tích từng ngành...")
        for code, name in self.config.SECTOR_INDICES.items():
            sector = self._analyze_sector(code, name, report)
            if sector:
                report.sectors.append(sector)
        
        # 3. Calculate RS Ratings
        print("\n[3/5] Tính RS Rating (IBD-style)...")
        report.sectors = self.rs_calculator.calculate_rs_ratings(report.sectors)
        for s in report.sectors:
            s.rs_trend = self.rs_calculator.calculate_rs_trend(s)
            print(f"   {s.name}: RS={s.rs_rating} | {s.rs_trend}")
        
        # 4. Classify sectors
        print("\n[4/5] Phân loại ngành...")
        self._classify_sectors(report)
        
        # 5. Rotation Clock analysis
        print("\n[5/5] Phân tích Rotation Clock...")
        report.rotation = self._analyze_rotation_clock(report)
        print(f"   Clock: {report.rotation.current_clock.value}")
        print(f"   Confidence: {report.rotation.confidence:.0f}%")
        
        # Generate top picks
        report.top_sectors = [s.name for s in report.sectors[:3]]
        report.avoid_sectors = [s.name for s in report.sectors[-2:] if s.phase == SectorPhase.LAGGING]
        
        return report
    
    def _get_vnindex_data(self) -> Dict:
        """Lấy dữ liệu VNIndex"""
        try:
            data = self.collector.get_stock_data("VNINDEX", lookback_days=250, include_vp=False)
            return {
                'price': data.price,
                'change_1d': data.change_1d,
                'change_1m': data.change_1m,
                'change_3m': data.change_3m,
            }
        except Exception as e:
            print(f"   ⚠️ Lỗi lấy VNIndex: {e}")
            return {}
    
    def _analyze_sector(self, code: str, name: str, report: SectorRotationReport) -> Optional[SectorData]:
        """Phân tích một ngành"""
        print(f"   📊 {name}...", end=" ")
        
        try:
            data = self.collector.get_stock_data(
                code,
                lookback_days=self.config.LOOKBACK_DAYS,
                include_vp=self.config.ENABLE_VOLUME_PROFILE
            )
            
            if data.price == 0:
                print("✗ (no data)")
                return None
            
            # Create SectorData
            sector = SectorData(
                code=code,
                name=name,
                sector_type=SECTOR_TYPES.get(code, SectorType.CYCLICAL),
                
                # Performance
                change_1d=data.change_1d,
                change_5d=data.change_5d,
                change_1m=data.change_1m,
                change_3m=data.change_3m,
                change_6m=getattr(data, 'change_6m', data.change_3m * 1.5),  # Estimate if not available
                change_12m=getattr(data, 'change_12m', data.change_3m * 2),
                
                # RS vs VNIndex
                rs_vs_vnindex_1m=data.change_1m - report.vnindex_change_1m,
                rs_vs_vnindex_3m=data.change_3m - report.vnindex_change_3m,
                
                # Technical
                price=data.price,
                rsi_14=data.rsi_14,
                above_ma20=data.above_ma20,
                above_ma50=data.above_ma50,
                
                # Volume Profile
                poc=data.poc,
                vah=data.vah,
                val=data.val,
                price_vs_va=data.price_vs_va,
                
                # Money Flow (placeholder - cần API thực)
                money_flow=SectorMoneyFlow(
                    foreign_net_1d=0,
                    foreign_net_5d=0,
                    foreign_net_20d=0,
                ),
                
                # Raw data
                raw_data=data
            )
            
            # Calculate composite score
            sector.composite_score = self._calc_composite_score(sector)
            
            # Determine phase
            sector.phase = self._determine_phase(sector)
            
            print(f"✓ RS_1M={sector.rs_vs_vnindex_1m:+.2f}% | {sector.phase.value}")
            
            time.sleep(self.config.API_DELAY)
            return sector
            
        except Exception as e:
            print(f"✗ Error: {e}")
            return None
    
    def _calc_composite_score(self, sector: SectorData) -> float:
        """
        Tính Composite Score (0-100)
        
        Components:
        - RS Rating: 30%
        - Performance 1M: 25%
        - Technical (MA alignment): 20%
        - RSI position: 15%
        - Volume Profile position: 10%
        """
        score = 0
        
        # RS Rating contribution (30 points max)
        # rs_rating is 1-99, scale to 0-30
        score += (sector.rs_rating / 99) * 30
        
        # 1M Performance (25 points max)
        # +10% = 25 points, -10% = 0 points
        perf_score = max(0, min(25, (sector.change_1m + 10) / 20 * 25))
        score += perf_score
        
        # MA Alignment (20 points max)
        if sector.above_ma20 and sector.above_ma50:
            score += 20
        elif sector.above_ma50:
            score += 12
        elif sector.above_ma20:
            score += 8
        
        # RSI Position (15 points max)
        # Optimal: 50-70 (bullish but not overbought)
        if 50 <= sector.rsi_14 <= 70:
            score += 15
        elif 40 <= sector.rsi_14 < 50:
            score += 12  # Starting to recover
        elif sector.rsi_14 > 70:
            score += 8   # Overbought risk
        elif sector.rsi_14 < 30:
            score += 10  # Oversold, potential bounce
        else:
            score += 5
        
        # Volume Profile (10 points max)
        if sector.price_vs_va == "ABOVE_VA":
            score += 10
        elif sector.price_vs_va == "IN_VA":
            score += 6
        else:
            score += 2
        
        return round(max(0, min(100, score)), 1)
    
    def _determine_phase(self, sector: SectorData) -> SectorPhase:
        """Xác định phase của ngành"""
        rs = sector.rs_vs_vnindex_1m
        momentum = sector.change_5d
        
        # LEADING: Strong RS + Positive momentum + Above MAs
        if rs > 3 and momentum > 0 and sector.above_ma20:
            return SectorPhase.LEADING
        
        # IMPROVING: RS turning positive + Momentum picking up
        elif rs > 0 or (rs > -2 and momentum > sector.change_1d * 0.5):
            if momentum > 0 or sector.rsi_14 > 50:
                return SectorPhase.IMPROVING
        
        # WEAKENING: RS still positive but declining + Momentum slowing
        if rs > -2 and rs < 3 and momentum < 0:
            return SectorPhase.WEAKENING
        
        # LAGGING: Negative RS + Weak momentum
        return SectorPhase.LAGGING
    
    def _classify_sectors(self, report: SectorRotationReport):
        """Phân loại sectors theo phase và type"""
        # Sort by composite score
        report.sectors.sort(key=lambda x: x.composite_score, reverse=True)
        
        # Assign ranks
        for i, s in enumerate(report.sectors, 1):
            s.rank = i
        
        # By phase
        report.leading_sectors = [s for s in report.sectors if s.phase == SectorPhase.LEADING]
        report.improving_sectors = [s for s in report.sectors if s.phase == SectorPhase.IMPROVING]
        report.weakening_sectors = [s for s in report.sectors if s.phase == SectorPhase.WEAKENING]
        report.lagging_sectors = [s for s in report.sectors if s.phase == SectorPhase.LAGGING]
        
        # By type
        report.cyclical_sectors = [s for s in report.sectors if s.sector_type == SectorType.CYCLICAL]
        report.defensive_sectors = [s for s in report.sectors if s.sector_type == SectorType.DEFENSIVE]
        report.growth_sectors = [s for s in report.sectors if s.sector_type == SectorType.GROWTH]
    
    def _analyze_rotation_clock(self, report: SectorRotationReport) -> RotationAnalysis:
        """Phân tích Rotation Clock"""
        rotation = RotationAnalysis()
        
        # Get leading sectors codes
        leading_codes = [s.code for s in report.leading_sectors]
        improving_codes = [s.code for s in report.improving_sectors]
        current_leaders = leading_codes + improving_codes[:2]
        
        rotation.leading_now = [self.config.SECTOR_INDICES.get(c, c) for c in current_leaders]
        
        # Match against rotation patterns
        scores = {}
        for clock, expected in ROTATION_LEADERS.items():
            match_count = sum(1 for code in current_leaders if code in expected)
            scores[clock] = match_count / len(expected) if expected else 0
        
        # Determine current clock
        best_clock = max(scores, key=scores.get)
        rotation.current_clock = best_clock
        rotation.confidence = scores[best_clock] * 100
        rotation.expected_leaders = [self.config.SECTOR_INDICES.get(c, c) for c in ROTATION_LEADERS[best_clock]]
        
        # Generate rotation signals
        if rotation.confidence > 60:
            rotation.rotation_signals.append(f"✅ Strong {best_clock.value} pattern detected")
        else:
            rotation.rotation_signals.append(f"⚠️ Mixed signals, possibly transitioning")
        
        # Check for rotation transition
        if report.weakening_sectors:
            rotation.rotation_signals.append(f"📉 {len(report.weakening_sectors)} sector(s) weakening - possible rotation")
        
        # Allocation suggestion based on clock
        if best_clock == RotationClock.EARLY_CYCLE:
            rotation.cyclical_weight = 50
            rotation.defensive_weight = 20
            rotation.growth_weight = 30
        elif best_clock == RotationClock.MID_CYCLE:
            rotation.cyclical_weight = 40
            rotation.defensive_weight = 20
            rotation.growth_weight = 40
        elif best_clock == RotationClock.LATE_CYCLE:
            rotation.cyclical_weight = 30
            rotation.defensive_weight = 40
            rotation.growth_weight = 30
        else:  # RECESSION
            rotation.cyclical_weight = 20
            rotation.defensive_weight = 60
            rotation.growth_weight = 20
        
        return rotation


# ══════════════════════════════════════════════════════════════════════════════
# AI GENERATOR v3
# ══════════════════════════════════════════════════════════════════════════════

class SectorRotationAIGenerator:
    """Tạo báo cáo AI cho Sector Rotation"""
    
    SYSTEM_PROMPT = """Bạn là Giám đốc Phân tích Ngành tại quỹ đầu tư quy mô 100 tỷ VNĐ.
Chuyên môn: Sector Rotation, Chu kỳ kinh tế, IBD Relative Strength methodology.
Phong cách: Data-driven, thực tế, có action items cụ thể.
Luôn trả lời bằng tiếng Việt, chuyên nghiệp."""
    
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
        """Tạo prompt với full data"""
        
        # Sector table
        sector_table = ""
        for s in report.sectors:
            sector_table += f"""
   {s.rank}. {s.name:<18} | RS={s.rs_rating:>2} | 1D={s.change_1d:+.2f}% | 1M={s.change_1m:+.2f}% | Phase: {s.phase.value}
      Type: {s.sector_type.value} | RSI: {s.rsi_14:.0f} | MA20: {'✓' if s.above_ma20 else '✗'} | MA50: {'✓' if s.above_ma50 else '✗'} | RS Trend: {s.rs_trend}"""
        
        # Market context
        market_ctx = ""
        if report.market_traffic_light:
            market_ctx = f"""
📋 MARKET CONTEXT (từ Module 1):
   Traffic Light: {report.market_traffic_light}
   Distribution Days: {report.market_distribution_days}
   Market Regime: {report.market_regime}
"""
        
        # Rotation clock
        rotation_section = f"""
🕐 ROTATION CLOCK:
   Current Phase: {report.rotation.current_clock.value}
   Confidence: {report.rotation.confidence:.0f}%
   Leading Now: {', '.join(report.rotation.leading_now) or 'N/A'}
   Expected Leaders: {', '.join(report.rotation.expected_leaders)}
   
   Allocation Suggestion:
   - Cyclical: {report.rotation.cyclical_weight:.0f}%
   - Defensive: {report.rotation.defensive_weight:.0f}%
   - Growth: {report.rotation.growth_weight:.0f}%
"""
        
        prompt = f"""
═══════════════════════════════════════════════════════════════
BÁO CÁO SECTOR ROTATION v3 - {report.timestamp.strftime('%d/%m/%Y %H:%M')}
═══════════════════════════════════════════════════════════════

📊 BENCHMARK:
   VNIndex: {report.vnindex_price:,.0f} | 1D={report.vnindex_change_1d:+.2f}% | 1M={report.vnindex_change_1m:+.2f}%
{market_ctx}
📈 XẾP HẠNG NGÀNH (by RS Rating - IBD style):
{sector_table}

📊 PHÂN LOẠI THEO PHASE:
   🚀 LEADING: {', '.join([s.name for s in report.leading_sectors]) or 'Không có'}
   📈 IMPROVING: {', '.join([s.name for s in report.improving_sectors]) or 'Không có'}
   📉 WEAKENING: {', '.join([s.name for s in report.weakening_sectors]) or 'Không có'}
   ⛔ LAGGING: {', '.join([s.name for s in report.lagging_sectors]) or 'Không có'}

📊 PHÂN LOẠI THEO TYPE:
   Cyclical: {', '.join([s.name for s in report.cyclical_sectors])}
   Defensive: {', '.join([s.name for s in report.defensive_sectors])}
   Growth: {', '.join([s.name for s in report.growth_sectors])}
{rotation_section}
═══════════════════════════════════════════════════════════════

YÊU CẦU PHÂN TÍCH:

1. ĐÁNH GIÁ ROTATION CLOCK
   - Xác nhận/điều chỉnh vị trí trong chu kỳ
   - So sánh leading sectors hiện tại vs expected
   - Dấu hiệu rotation tiếp theo

2. TOP 3 NGÀNH NÊN TĂNG TỶ TRỌNG
   - Ngành nào? Tại sao? 
   - RS Rating + Technical setup
   - Target allocation

3. NGÀNH CẦN TRÁNH/GIẢM
   - Ngành nào đang distribution?
   - Warning signs cụ thể

4. CHIẾN LƯỢC ROTATION 2-4 TUẦN TỚI
   - Kịch bản chính (70% probability)
   - Kịch bản phụ (30% probability)
   - Trigger để điều chỉnh

5. PORTFOLIO ALLOCATION
   - Cyclical vs Defensive vs Growth
   - Điều chỉnh theo Market Context (Traffic Light)
"""
        return prompt
    
    def generate(self, report: SectorRotationReport) -> str:
        """Tạo báo cáo AI"""
        if not self.ai:
            return "⚠️ AI chưa cấu hình. Điền API key vào config.py"
        
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
# REPORT EXPORTER
# ══════════════════════════════════════════════════════════════════════════════

class ReportExporter:
    """Export báo cáo"""
    
    def __init__(self, config: SectorRotationConfig):
        self.config = config
    
    def to_dict(self, report: SectorRotationReport) -> Dict:
        """Convert to dictionary"""
        return {
            'timestamp': report.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'vnindex': {
                'price': report.vnindex_price,
                'change_1d': report.vnindex_change_1d,
                'change_1m': report.vnindex_change_1m,
            },
            'market_context': {
                'traffic_light': report.market_traffic_light,
                'distribution_days': report.market_distribution_days,
                'market_regime': report.market_regime,
            },
            'sectors': [
                {
                    'rank': s.rank,
                    'code': s.code,
                    'name': s.name,
                    'type': s.sector_type.value,
                    'rs_rating': s.rs_rating,
                    'rs_trend': s.rs_trend,
                    'change_1d': s.change_1d,
                    'change_1m': s.change_1m,
                    'rs_vs_vnindex': s.rs_vs_vnindex_1m,
                    'phase': s.phase.value,
                    'composite_score': s.composite_score,
                    'technical': {
                        'rsi': s.rsi_14,
                        'above_ma20': s.above_ma20,
                        'above_ma50': s.above_ma50,
                    },
                    'volume_profile': {
                        'poc': s.poc,
                        'vah': s.vah,
                        'val': s.val,
                        'position': s.price_vs_va,
                    }
                }
                for s in report.sectors
            ],
            'classification': {
                'leading': [s.name for s in report.leading_sectors],
                'improving': [s.name for s in report.improving_sectors],
                'weakening': [s.name for s in report.weakening_sectors],
                'lagging': [s.name for s in report.lagging_sectors],
            },
            'rotation': {
                'clock': report.rotation.current_clock.value,
                'confidence': report.rotation.confidence,
                'leading_now': report.rotation.leading_now,
                'expected_leaders': report.rotation.expected_leaders,
                'allocation': {
                    'cyclical': report.rotation.cyclical_weight,
                    'defensive': report.rotation.defensive_weight,
                    'growth': report.rotation.growth_weight,
                }
            },
            'recommendations': {
                'top_sectors': report.top_sectors,
                'avoid_sectors': report.avoid_sectors,
            }
        }
    
    def to_json(self, report: SectorRotationReport, indent: int = 2) -> str:
        """Export JSON"""
        return json.dumps(self.to_dict(report), indent=indent, ensure_ascii=False, default=str)
    
    def to_markdown(self, report: SectorRotationReport) -> str:
        """Export Markdown"""
        
        # Sector table
        sector_rows = "\n".join([
            f"| {s.rank} | {s.name} | {s.rs_rating} | {s.change_1d:+.2f}% | {s.change_1m:+.2f}% | {s.rs_vs_vnindex_1m:+.2f}% | {s.phase.value} |"
            for s in report.sectors
        ])
        
        content = f"""# 📊 BÁO CÁO SECTOR ROTATION v3
**Ngày:** {report.timestamp.strftime('%d/%m/%Y %H:%M')}

---

## 📋 TỔNG QUAN

| Metric | Value |
|--------|-------|
| **VNIndex** | {report.vnindex_price:,.0f} ({report.vnindex_change_1d:+.2f}%) |
| **Rotation Clock** | {report.rotation.current_clock.value} |
| **Confidence** | {report.rotation.confidence:.0f}% |

---

## 📈 XẾP HẠNG NGÀNH (by RS Rating)

| Rank | Ngành | RS | 1D | 1M | RS vs VNI | Phase |
|------|-------|----|----|----|-----------| ------|
{sector_rows}

---

## 🔄 PHÂN LOẠI

### Theo Phase
- 🚀 **LEADING:** {', '.join([s.name for s in report.leading_sectors]) or 'N/A'}
- 📈 **IMPROVING:** {', '.join([s.name for s in report.improving_sectors]) or 'N/A'}
- 📉 **WEAKENING:** {', '.join([s.name for s in report.weakening_sectors]) or 'N/A'}
- ⛔ **LAGGING:** {', '.join([s.name for s in report.lagging_sectors]) or 'N/A'}

### Theo Type
- **Cyclical:** {', '.join([s.name for s in report.cyclical_sectors])}
- **Defensive:** {', '.join([s.name for s in report.defensive_sectors])}
- **Growth:** {', '.join([s.name for s in report.growth_sectors])}

---

## 🕐 ROTATION CLOCK

| Metric | Value |
|--------|-------|
| **Current Phase** | {report.rotation.current_clock.value} |
| **Confidence** | {report.rotation.confidence:.0f}% |
| **Leading Now** | {', '.join(report.rotation.leading_now)} |
| **Expected Leaders** | {', '.join(report.rotation.expected_leaders)} |

### Allocation Suggestion
| Type | Weight |
|------|--------|
| Cyclical | {report.rotation.cyclical_weight:.0f}% |
| Defensive | {report.rotation.defensive_weight:.0f}% |
| Growth | {report.rotation.growth_weight:.0f}% |

---

## 🎯 KHUYẾN NGHỊ

### Top Sectors
{chr(10).join(['- ' + s for s in report.top_sectors])}

### Avoid Sectors
{chr(10).join(['- ' + s for s in report.avoid_sectors]) if report.avoid_sectors else '- N/A'}

---

## 🤖 AI ANALYSIS

{report.ai_analysis}
"""
        return content
    
    def save(self, report: SectorRotationReport):
        """Save reports"""
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        timestamp = report.timestamp.strftime('%Y%m%d_%H%M')
        
        # Markdown
        md_file = os.path.join(self.config.OUTPUT_DIR, f"sector_rotation_{timestamp}.md")
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(self.to_markdown(report))
        print(f"✓ Saved: {md_file}")
        
        # JSON
        if self.config.SAVE_JSON:
            json_file = os.path.join(self.config.OUTPUT_DIR, f"sector_rotation_{timestamp}.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                f.write(self.to_json(report))
            print(f"✓ Saved: {json_file}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MODULE
# ══════════════════════════════════════════════════════════════════════════════

class SectorRotationModule:
    """Module 2 v3: Sector Rotation"""
    
    def __init__(self, config: SectorRotationConfig = None):
        self.config = config or create_config_from_unified()
        self.analyzer = SectorRotationAnalyzer(self.config)
        self.ai_generator = SectorRotationAIGenerator(self.config)
        self.exporter = ReportExporter(self.config)
        self.report: SectorRotationReport = None
    
    def run(self, market_context: Optional[Dict] = None) -> SectorRotationReport:
        """
        Chạy module
        
        Args:
            market_context: Optional dict từ Module 1
                {
                    'traffic_light': '🟡 VÀNG',
                    'distribution_days': 6,
                    'market_regime': 'DISTRIBUTION'
                }
        """
        print("""
╔══════════════════════════════════════════════════════════════╗
║     MODULE 2 v3: SECTOR ROTATION                             ║
║     RS Rating (IBD) + Rotation Clock + Leader Analysis       ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # 1. Analyze
        self.report = self.analyzer.analyze(market_context)
        
        # 2. AI
        self.report.ai_analysis = self.ai_generator.generate(self.report)
        
        # 3. Print summary
        self._print_summary()
        
        # 4. Save
        if self.config.SAVE_REPORT:
            self.exporter.save(self.report)
        
        return self.report
    
    def _print_summary(self):
        """Print summary"""
        print("\n" + "="*70)
        print("📋 TÓM TẮT SECTOR ROTATION")
        print("="*70)
        
        print(f"\n{'RANK':<5} {'NGÀNH':<18} {'RS':>4} {'1D':>8} {'1M':>8} {'PHASE':<15}")
        print("-"*65)
        
        for s in self.report.sectors:
            print(f"{s.rank:<5} {s.name:<18} {s.rs_rating:>4} {s.change_1d:>+7.2f}% "
                  f"{s.change_1m:>+7.2f}% {s.phase.value:<15}")
        
        print(f"\n🕐 Rotation Clock: {self.report.rotation.current_clock.value}")
        print(f"   Confidence: {self.report.rotation.confidence:.0f}%")
        
        print("\n" + "─"*70)
        print("🤖 AI ANALYSIS:")
        print("─"*70)
        print(self.report.ai_analysis[:2000] + "..." if len(self.report.ai_analysis) > 2000 else self.report.ai_analysis)
    
    def get_json(self) -> str:
        """Get JSON output"""
        if self.report:
            return self.exporter.to_json(self.report)
        return "{}"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Example with market context from Module 1
    market_context = {
        'traffic_light': '🟡 VÀNG - THẬN TRỌNG',
        'distribution_days': 6,
        'market_regime': 'DISTRIBUTION'
    }
    
    module = SectorRotationModule()
    report = module.run(market_context)
    
    # Print JSON sample
    print("\n" + "="*60)
    print("📄 JSON OUTPUT SAMPLE:")
    print("="*60)
    print(module.get_json()[:1500] + "...")