#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     MODULE 1 v3: MARKET TIMING - ĐỊNH THỜI ĐIỂM THỊ TRƯỜNG                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  NÂNG CẤP TỪ V2:                                                             ║
║  ✅ Tích hợp DataContext (Module 0) - Vector hóa dữ liệu                    ║
║  ✅ Distribution Days counting (IBD)                                         ║
║  ✅ Follow-Through Day detection                                             ║
║  ✅ Traffic Light theo IBD model                                             ║
║  ✅ RSI Regime, MACD Impulse, Trend Slope                                   ║
║  ✅ Output JSON cho AI                                                       ║
║  ✅ Volume Profile (giữ nguyên từ v2)                                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# Import từ các module chung
from config import get_config, UnifiedConfig
from data_collector import get_data_collector, EnhancedStockData
from volume_profile import VolumeProfileFormatter
from data_context import DataContext, FullContext, get_data_context

# Import AI Provider
try:
    from ai_providers import AIProvider, AIConfig
except ImportError:
    AIProvider = None


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

class TrafficLight:
    """IBD Traffic Light System"""
    GREEN = "🟢 XANH - TẤN CÔNG"        # Full margin, aggressive buying
    YELLOW = "🟡 VÀNG - THẬN TRỌNG"     # Reduce exposure, no new buys
    RED = "🔴 ĐỎ - RÚT LUI"             # Cash is king, sell into rallies


class MarketPhase:
    """Wyckoff Market Phases"""
    ACCUMULATION = "🔵 ACCUMULATION"    # Smart money buying
    MARKUP = "🟢 MARKUP"                 # Uptrend
    DISTRIBUTION = "🟠 DISTRIBUTION"    # Smart money selling
    MARKDOWN = "🔴 MARKDOWN"             # Downtrend


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MarketTimingConfig:
    """Config cho Module 1 v3"""
    
    # Data Source
    VNSTOCK_API_KEY: str = ""
    DATA_SOURCE: str = "VCI"
    
    # Indices
    MAIN_INDEX: str = "VNINDEX"
    COMPARISON_INDICES: List[str] = field(default_factory=lambda: ["VN30", "VNMID"])
    SECTOR_INDICES: List[str] = field(default_factory=lambda: [
        "VNFIN", "VNREAL", "VNMAT", "VNIT",
        "VNHEAL", "VNCOND", "VNCONS"
    ])
    
    # Analysis Parameters
    LOOKBACK_DAYS: int = 120
    DISTRIBUTION_WINDOW: int = 25
    FTD_MIN_DAY: int = 4
    FTD_MAX_DAY: int = 10
    FTD_MIN_GAIN: float = 1.25
    
    # Volume Profile
    ENABLE_VOLUME_PROFILE: bool = True
    VP_LOOKBACK_DAYS: int = 20
    
    # AI
    AI_PROVIDER: str = ""
    AI_API_KEY: str = ""
    AI_MODEL: str = ""
    AI_MAX_TOKENS: int = 4096
    AI_TEMPERATURE: float = 0.7
    
    # Output
    OUTPUT_DIR: str = "./output"
    SAVE_REPORT: bool = True
    SAVE_JSON: bool = True


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
    new_highs: int = 0
    new_lows: int = 0
    
    @property
    def ad_ratio(self) -> float:
        return self.advances / self.declines if self.declines > 0 else 0
    
    @property
    def ad_diff(self) -> int:
        return self.advances - self.declines


@dataclass
class MoneyFlow:
    """Dòng tiền"""
    foreign_net: float = 0.0
    foreign_buy: float = 0.0
    foreign_sell: float = 0.0
    proprietary_net: float = 0.0
    total_value: float = 0.0
    
    # Cumulative
    foreign_net_5d: float = 0.0
    foreign_net_20d: float = 0.0
    
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
    rs_vs_index: float = 0.0  # Relative Strength vs VNIndex


@dataclass
class TrafficLightResult:
    """Kết quả Traffic Light"""
    color: str = TrafficLight.YELLOW
    score: int = 50
    
    # Component scores (-2 to +2 each)
    trend_score: int = 0
    momentum_score: int = 0
    distribution_score: int = 0
    structure_score: int = 0
    volume_score: int = 0
    
    # Conditions
    conditions_met: List[str] = field(default_factory=list)
    conditions_failed: List[str] = field(default_factory=list)
    
    # Recommendations
    position_size: str = "50%"  # % equity in stocks
    action: str = "HOLD"  # BUY, HOLD, REDUCE, SELL


@dataclass
class MarketReport:
    """Báo cáo tổng hợp"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Index data (EnhancedStockData từ data_collector)
    vnindex: EnhancedStockData = None
    vn30: EnhancedStockData = None
    vnmid: EnhancedStockData = None
    
    # Raw dataframe (cho DataContext)
    vnindex_df: pd.DataFrame = None
    
    # Data Context (từ Module 0)
    context: FullContext = None
    
    # Market internals
    breadth: MarketBreadth = field(default_factory=MarketBreadth)
    money_flow: MoneyFlow = field(default_factory=MoneyFlow)
    
    # Sectors
    sectors: List[SectorData] = field(default_factory=list)
    
    # Traffic Light (IBD model)
    traffic_light: TrafficLightResult = field(default_factory=TrafficLightResult)
    
    # Legacy fields (backward compatible)
    market_color: str = "🟡 VÀNG"
    market_score: int = 50
    trend_status: str = "SIDEWAY"
    key_signals: List[str] = field(default_factory=list)
    
    # AI
    ai_analysis: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# MARKET TIMING ANALYZER v3
# ══════════════════════════════════════════════════════════════════════════════

class MarketTimingAnalyzer:
    """
    Market Timing Analyzer v3
    Tích hợp DataContext cho phân tích có ngữ cảnh
    """
    
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
        self.data_context = DataContext({
            'distribution_window': config.DISTRIBUTION_WINDOW,
            'ftd_min_day': config.FTD_MIN_DAY,
            'ftd_max_day': config.FTD_MAX_DAY,
            'ftd_min_gain': config.FTD_MIN_GAIN
        })
    
    def collect_data(self) -> MarketReport:
        """Thu thập dữ liệu thị trường"""
        print("\n" + "="*60)
        print("📊 THU THẬP DỮ LIỆU THỊ TRƯỜNG")
        print("="*60)
        
        report = MarketReport()
        
        # 1. VNIndex với Volume Profile + Raw DataFrame
        print("\n[1/4] VN-INDEX...")
        report.vnindex, report.vnindex_df = self._get_index_with_df("VNINDEX")
        
        if report.vnindex and report.vnindex.price > 0:
            print(f"   ✓ VNIndex: {report.vnindex.price:,.0f} ({report.vnindex.change_1d:+.2f}%)")
            if report.vnindex.poc > 0:
                print(f"   📊 VP: POC={report.vnindex.poc:,.0f} | VA={report.vnindex.val:,.0f}-{report.vnindex.vah:,.0f}")
        
        # 2. VN30
        print("\n[2/4] VN30...")
        report.vn30 = self.collector.get_stock_data("VN30", include_vp=False)
        if report.vn30 and report.vn30.price > 0:
            print(f"   ✓ VN30: {report.vn30.price:,.0f} ({report.vn30.change_1d:+.2f}%)")
        
        # 3. VNMID
        print("\n[3/4] VNMID...")
        report.vnmid = self.collector.get_stock_data("VNMID", include_vp=False)
        
        # 4. Sectors
        print("\n[4/4] CHỈ SỐ NGÀNH...")
        vnindex_1m = report.vnindex.change_1m if report.vnindex else 0
        
        for code in self.config.SECTOR_INDICES[:5]:
            data = self.collector.get_stock_data(code, lookback_days=30, include_vp=False)
            if data and data.price > 0:
                sector = SectorData(
                    code=code,
                    name=self.SECTOR_NAMES.get(code, code),
                    change_1d=data.change_1d,
                    change_5d=data.change_5d,
                    change_1m=data.change_1m,
                    rs_vs_index=data.change_1m - vnindex_1m
                )
                report.sectors.append(sector)
                print(f"   ✓ {code}: {data.change_1d:+.2f}% (RS: {sector.rs_vs_index:+.2f}%)")
        
        report.sectors.sort(key=lambda x: x.rs_vs_index, reverse=True)
        
        # 5. Breadth & Money Flow
        report.breadth = self._estimate_breadth(report)
        report.money_flow = self._get_money_flow()
        
        return report
    
    def _get_index_with_df(self, symbol: str) -> Tuple[EnhancedStockData, pd.DataFrame]:
        """Lấy cả EnhancedStockData và raw DataFrame"""
        try:
            from vnstock import Vnstock
            
            stock = Vnstock().stock(symbol=symbol, source=self.config.DATA_SOURCE)
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=self.config.LOOKBACK_DAYS)).strftime('%Y-%m-%d')
            
            df = stock.quote.history(start=start_date, end=end_date)
            
            # Get EnhancedStockData
            enhanced_data = self.collector.get_stock_data(
                symbol, 
                lookback_days=self.config.LOOKBACK_DAYS,
                include_vp=self.config.ENABLE_VOLUME_PROFILE
            )
            
            return enhanced_data, df
            
        except Exception as e:
            print(f"   ⚠️ Lỗi: {e}")
            return EnhancedStockData(symbol=symbol), pd.DataFrame()
    
    def _estimate_breadth(self, report: MarketReport) -> MarketBreadth:
        """Ước tính breadth"""
        breadth = MarketBreadth()
        
        advances = sum(1 for s in report.sectors if s.change_1d > 0)
        declines = sum(1 for s in report.sectors if s.change_1d < 0)
        
        # Scale
        scale = 30
        breadth.advances = advances * scale + 50
        breadth.declines = declines * scale + 50
        breadth.unchanged = 30
        
        return breadth
    
    def _get_money_flow(self) -> MoneyFlow:
        """Lấy dữ liệu dòng tiền (placeholder - cần tích hợp API thực)"""
        # TODO: Tích hợp vnstock API cho foreign flow thực
        return MoneyFlow(
            foreign_net=-41.2,
            foreign_buy=850,
            foreign_sell=891.2,
            proprietary_net=15.5,
            total_value=18500,
            foreign_net_5d=-180,
            foreign_net_20d=350
        )
    
    def analyze_context(self, report: MarketReport) -> MarketReport:
        """Phân tích với DataContext (Module 0)"""
        print("\n" + "="*60)
        print("🔍 PHÂN TÍCH DATA CONTEXT")
        print("="*60)
        
        if report.vnindex_df is None or len(report.vnindex_df) == 0:
            print("   ⚠️ Không có dữ liệu để phân tích context")
            return report
        
        # Analyze với DataContext
        report.context = self.data_context.analyze(report.vnindex_df, symbol="VNINDEX")
        
        # Print summary
        ctx = report.context
        print(f"\n📈 TREND:")
        print(f"   MA20 Slope: {ctx.trend.ma20_slope:+.2f}% ({ctx.trend.ma20_slope_status})")
        print(f"   MA50 Slope: {ctx.trend.ma50_slope:+.2f}% ({ctx.trend.ma50_slope_status})")
        print(f"   Alignment: {ctx.trend.ma_alignment}")
        
        print(f"\n💰 PRICE POSITION:")
        print(f"   {ctx.price.ma_position}")
        print(f"   Percentile 50D: {ctx.price.percentile_50d:.0f}%")
        
        print(f"\n📊 RSI REGIME:")
        print(f"   Current: {ctx.rsi.rsi_current:.1f} | Regime: {ctx.rsi.regime}")
        
        print(f"\n📉 MACD IMPULSE:")
        print(f"   {ctx.macd.impulse_direction} ({ctx.macd.impulse_bars} bars)")
        
        print(f"\n📅 DISTRIBUTION DAYS:")
        print(f"   Count: {ctx.distribution.count}/25 | {ctx.distribution.status}")
        
        print(f"\n✨ FOLLOW-THROUGH DAY:")
        print(f"   {ctx.ftd.note}")
        
        print(f"\n🎪 MARKET REGIME:")
        print(f"   {ctx.regime.regime} (Confidence: {ctx.regime.confidence:.0f}%)")
        
        return report
    
    def calculate_traffic_light(self, report: MarketReport) -> MarketReport:
        """
        Tính Traffic Light theo IBD model
        
        GREEN conditions:
        - Giá > MA20 > MA50 > MA200
        - Distribution Days < 3
        - Có Follow-Through Day gần đây
        - RSI Regime BULLISH
        
        YELLOW conditions:
        - Distribution Days 4-5
        - Giá < MA20 nhưng > MA50
        - RSI Regime NEUTRAL
        
        RED conditions:
        - Distribution Days > 6
        - Giá < MA50
        - RSI Regime BEARISH
        - Death Cross (MA50 < MA200)
        """
        print("\n" + "="*60)
        print("🚦 TÍNH TRAFFIC LIGHT (IBD Model)")
        print("="*60)
        
        tl = TrafficLightResult()
        ctx = report.context
        vni = report.vnindex
        
        if not ctx or not vni:
            print("   ⚠️ Thiếu dữ liệu để tính Traffic Light")
            report.traffic_light = tl
            return report
        
        # ═══════════════════════════════════════════════════════════════
        # 1. TREND SCORE (-2 to +2)
        # ═══════════════════════════════════════════════════════════════
        if "STRONG_UP" in ctx.trend.ma50_slope_status:
            tl.trend_score = 2
            tl.conditions_met.append("✅ MA50 slope STRONG UP")
        elif "UP" in ctx.trend.ma50_slope_status:
            tl.trend_score = 1
            tl.conditions_met.append("✅ MA50 slope UP")
        elif "STRONG_DOWN" in ctx.trend.ma50_slope_status:
            tl.trend_score = -2
            tl.conditions_failed.append("❌ MA50 slope STRONG DOWN")
        elif "DOWN" in ctx.trend.ma50_slope_status:
            tl.trend_score = -1
            tl.conditions_failed.append("⚠️ MA50 slope DOWN")
        
        # MA Alignment bonus
        if ctx.trend.ma_alignment == "BULLISH":
            tl.trend_score += 1
            tl.conditions_met.append("✅ MA Alignment BULLISH (MA20>MA50>MA200)")
        elif ctx.trend.ma_alignment == "BEARISH":
            tl.trend_score -= 1
            tl.conditions_failed.append("❌ MA Alignment BEARISH")
        
        # ═══════════════════════════════════════════════════════════════
        # 2. STRUCTURE SCORE (-2 to +2)
        # ═══════════════════════════════════════════════════════════════
        if "STRONG_BULLISH" in ctx.price.ma_position:
            tl.structure_score = 2
            tl.conditions_met.append("✅ Giá > MA20 > MA50 (STRONG BULLISH)")
        elif "BULLISH" in ctx.price.ma_position:
            tl.structure_score = 1
            tl.conditions_met.append("✅ Giá > MA50")
        elif "STRONG_BEARISH" in ctx.price.ma_position:
            tl.structure_score = -2
            tl.conditions_failed.append("❌ Giá < MA20 < MA50 (STRONG BEARISH)")
        elif "BEARISH" in ctx.price.ma_position:
            tl.structure_score = -1
            tl.conditions_failed.append("⚠️ Giá < MA50")
        
        # ═══════════════════════════════════════════════════════════════
        # 3. MOMENTUM SCORE (-2 to +2)
        # ═══════════════════════════════════════════════════════════════
        # RSI Regime
        if "BULLISH" in ctx.rsi.regime:
            tl.momentum_score += 1
            tl.conditions_met.append("✅ RSI Regime BULLISH (min>40)")
        elif "BEARISH" in ctx.rsi.regime:
            tl.momentum_score -= 1
            tl.conditions_failed.append("⚠️ RSI Regime BEARISH (max<60)")
        
        # MACD Impulse
        if "INCREASING" in ctx.macd.impulse_direction and ctx.macd.histogram_positive:
            tl.momentum_score += 1
            tl.conditions_met.append("✅ MACD Histogram tăng & dương")
        elif "DECREASING" in ctx.macd.impulse_direction and not ctx.macd.histogram_positive:
            tl.momentum_score -= 1
            tl.conditions_failed.append("⚠️ MACD Histogram giảm & âm")
        
        # ═══════════════════════════════════════════════════════════════
        # 4. DISTRIBUTION SCORE (-2 to +2) - QUAN TRỌNG TRONG IBD
        # ═══════════════════════════════════════════════════════════════
        dist_count = ctx.distribution.count
        
        if dist_count <= 2:
            tl.distribution_score = 2
            tl.conditions_met.append(f"✅ Distribution Days = {dist_count} (< 3)")
        elif dist_count <= 3:
            tl.distribution_score = 1
            tl.conditions_met.append(f"✅ Distribution Days = {dist_count}")
        elif dist_count <= 5:
            tl.distribution_score = -1
            tl.conditions_failed.append(f"⚠️ Distribution Days = {dist_count} (4-5)")
        else:
            tl.distribution_score = -2
            tl.conditions_failed.append(f"❌ Distribution Days = {dist_count} (> 5)")
        
        # ═══════════════════════════════════════════════════════════════
        # 5. VOLUME & FTD SCORE (-2 to +2)
        # ═══════════════════════════════════════════════════════════════
        # Follow-Through Day
        if ctx.ftd.has_ftd:
            tl.volume_score += 2
            tl.conditions_met.append(f"✅ Follow-Through Day detected ({ctx.ftd.ftd_date})")
        elif ctx.ftd.days_from_low <= 10:
            tl.volume_score += 0  # Neutral - still in potential FTD window
            tl.conditions_met.append(f"📊 Đang trong window FTD (ngày {ctx.ftd.days_from_low} từ đáy)")
        
        # Volume Profile position
        if vni.price_vs_va == "ABOVE_VA":
            tl.volume_score += 1
            tl.conditions_met.append(f"✅ Giá TRÊN Value Area (VAH={vni.vah:,.0f})")
        elif vni.price_vs_va == "BELOW_VA":
            tl.volume_score -= 1
            tl.conditions_failed.append(f"⚠️ Giá DƯỚI Value Area (VAL={vni.val:,.0f})")
        
        # ═══════════════════════════════════════════════════════════════
        # CALCULATE TOTAL SCORE & DETERMINE COLOR
        # ═══════════════════════════════════════════════════════════════
        total_score = (
            tl.trend_score + 
            tl.structure_score + 
            tl.momentum_score + 
            tl.distribution_score + 
            tl.volume_score
        )
        
        # Normalize to 0-100
        # Max possible = +10, Min possible = -10
        tl.score = int((total_score + 10) / 20 * 100)
        tl.score = max(0, min(100, tl.score))
        
        # Determine color
        if total_score >= 5:
            tl.color = TrafficLight.GREEN
            tl.position_size = "80-100%"
            tl.action = "BUY"
        elif total_score >= 0:
            tl.color = TrafficLight.YELLOW
            tl.position_size = "40-60%"
            tl.action = "HOLD"
        else:
            tl.color = TrafficLight.RED
            tl.position_size = "0-20%"
            tl.action = "REDUCE/SELL"
        
        # Override rules (IBD hard rules)
        if dist_count > 6:
            tl.color = TrafficLight.RED
            tl.action = "REDUCE/SELL"
            tl.position_size = "0-20%"
            tl.conditions_failed.append("🚨 OVERRIDE: Distribution > 6 → RED")
        
        if "BEARISH" in ctx.trend.ma_alignment and tl.structure_score < 0:
            if tl.color == TrafficLight.GREEN:
                tl.color = TrafficLight.YELLOW
                tl.conditions_failed.append("🚨 OVERRIDE: Bearish alignment → không thể GREEN")
        
        # Print results
        print(f"\n📊 COMPONENT SCORES:")
        print(f"   Trend:        {tl.trend_score:+d}")
        print(f"   Structure:    {tl.structure_score:+d}")
        print(f"   Momentum:     {tl.momentum_score:+d}")
        print(f"   Distribution: {tl.distribution_score:+d}")
        print(f"   Volume/FTD:   {tl.volume_score:+d}")
        print(f"   ─────────────────")
        print(f"   TOTAL:        {total_score:+d} → Score: {tl.score}/100")
        
        print(f"\n🚦 TRAFFIC LIGHT: {tl.color}")
        print(f"   Position Size: {tl.position_size}")
        print(f"   Action: {tl.action}")
        
        # Update report
        report.traffic_light = tl
        report.market_color = tl.color
        report.market_score = tl.score
        report.key_signals = tl.conditions_met + tl.conditions_failed
        
        if "XANH" in tl.color:
            report.trend_status = "UPTREND"
        elif "ĐỎ" in tl.color:
            report.trend_status = "DOWNTREND"
        else:
            report.trend_status = "SIDEWAY"
        
        return report


# ══════════════════════════════════════════════════════════════════════════════
# AI GENERATOR v3
# ══════════════════════════════════════════════════════════════════════════════

class MarketTimingAIGenerator:
    """AI Generator với JSON context"""
    
    SYSTEM_PROMPT = """Bạn là Giám đốc Phân tích Chiến lược tại một quỹ đầu tư quy mô 100 tỷ VNĐ.
Phong cách: Thận trọng, dựa trên dữ liệu (Data-driven), tuân thủ VSA và IBD methodology.
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
        """Tạo prompt với full context"""
        vni = report.vnindex
        ctx = report.context
        tl = report.traffic_light
        
        # Context JSON (simplified for prompt)
        context_summary = ""
        if ctx:
            context_summary = f"""
📊 DATA CONTEXT (Module 0):
   TREND:
   - MA20 Slope: {ctx.trend.ma20_slope:+.2f}% ({ctx.trend.ma20_slope_status})
   - MA50 Slope: {ctx.trend.ma50_slope:+.2f}% ({ctx.trend.ma50_slope_status})
   - MA Alignment: {ctx.trend.ma_alignment}
   
   PRICE POSITION:
   - {ctx.price.ma_position}
   - Percentile 50D: {ctx.price.percentile_50d:.0f}%
   - vs MA20: {ctx.price.price_vs_ma20:+.2f}%
   - vs MA50: {ctx.price.price_vs_ma50:+.2f}%
   
   RSI REGIME:
   - Current: {ctx.rsi.rsi_current:.1f}
   - Min/Max 50D: {ctx.rsi.rsi_min_50d:.1f} / {ctx.rsi.rsi_max_50d:.1f}
   - Regime: {ctx.rsi.regime}
   
   MACD IMPULSE:
   - {ctx.macd.impulse_direction} ({ctx.macd.impulse_bars} bars)
   - Histogram: {ctx.macd.histogram:.4f}
   - Signal: {ctx.macd.impulse_signal}
   
   DISTRIBUTION DAYS (25 phiên):
   - Count: {ctx.distribution.count}
   - Status: {ctx.distribution.status}
   
   FOLLOW-THROUGH DAY:
   - Has FTD: {"✅ Yes" if ctx.ftd.has_ftd else "❌ No"}
   - Recent Low: {ctx.ftd.recent_low_price:,.0f} ({ctx.ftd.days_from_low} days ago)
   - Note: {ctx.ftd.note}
   
   MARKET REGIME: {ctx.regime.regime}
"""
        
        # Volume Profile
        vp_section = ""
        if vni and vni.poc > 0:
            vp_section = f"""
📊 VOLUME PROFILE (20 ngày):
   - POC: {vni.poc:,.0f}
   - Value Area: {vni.val:,.0f} - {vni.vah:,.0f}
   - Position: {vni.price_vs_va}
   - VP Support: {', '.join([f'{p:,.0f}' for p in (vni.vp_support or [])[:3]]) or 'N/A'}
   - VP Resistance: {', '.join([f'{p:,.0f}' for p in (vni.vp_resistance or [])[:3]]) or 'N/A'}
"""
        
        # Traffic Light
        tl_section = ""
        if tl:
            conditions = "\n".join([f"   {c}" for c in tl.conditions_met[:5]])
            warnings = "\n".join([f"   {c}" for c in tl.conditions_failed[:5]])
            tl_section = f"""
🚦 TRAFFIC LIGHT (IBD Model):
   Color: {tl.color}
   Score: {tl.score}/100
   Action: {tl.action}
   Position Size: {tl.position_size}
   
   ✅ Conditions Met:
{conditions}
   
   ⚠️ Warnings:
{warnings}
"""
        
        # Sectors
        sectors_str = "\n".join([
            f"   {i+1}. {s.name}: {s.change_1d:+.2f}% (RS: {s.rs_vs_index:+.2f}%)"
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
   - RSI(14): {vni.rsi_14:.1f} | ADX: {vni.adx:.1f}
   - Volume Ratio: {vni.volume_ratio:.2f}x

{context_summary}
{vp_section}
{tl_section}

📊 VN30: {report.vn30.price:,.0f} ({report.vn30.change_1d:+.2f}%)

📉 ĐỘ RỘNG: Tăng {report.breadth.advances} | Giảm {report.breadth.declines} (A/D: {report.breadth.ad_ratio:.2f})

💰 DÒNG TIỀN:
   - Khối ngoại: {report.money_flow.foreign_net:+.1f} tỷ (20D: {report.money_flow.foreign_net_20d:+.1f} tỷ)
   - Tự doanh: {report.money_flow.proprietary_net:+.1f} tỷ

🏭 TOP NGÀNH (theo RS):
{sectors_str}

═══════════════════════════════════════════════════════════════

NHIỆM VỤ: Viết BÁO CÁO CHIẾN LƯỢC NGÀY với cấu trúc:

1. TỔNG QUAN THỊ TRƯỜNG
   - Đánh giá Traffic Light và Market Regime
   - Xu hướng ngắn/trung hạn

2. PHÂN TÍCH DATA CONTEXT
   - Ý nghĩa của Trend Slope và MA Position
   - RSI Regime đang nói gì?
   - Distribution Days và rủi ro phân phối

3. VOLUME PROFILE INSIGHTS
   - POC và Value Area
   - Support/Resistance levels

4. KỊCH BẢN "WHAT-IF" (3 kịch bản với xác suất)
   - Trigger conditions cụ thể (mức giá, volume)
   - Hành động trading

5. KHUYẾN NGHỊ
   - Tỷ trọng danh mục phù hợp với Traffic Light
   - Ngành/cổ phiếu theo dõi
"""
        return prompt
    
    def generate(self, report: MarketReport) -> str:
        """Tạo báo cáo AI"""
        if not self.ai:
            return "⚠️ AI chưa được cấu hình. Điền API key vào config.py"
        
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
# REPORT EXPORTER
# ══════════════════════════════════════════════════════════════════════════════

class ReportExporter:
    """Export báo cáo ra nhiều format"""
    
    def __init__(self, config: MarketTimingConfig):
        self.config = config
    
    def to_dict(self, report: MarketReport) -> Dict:
        """Convert report to dictionary (for JSON)"""
        ctx = report.context
        tl = report.traffic_light
        vni = report.vnindex
        
        result = {
            'timestamp': report.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'vnindex': {
                'price': vni.price if vni else 0,
                'change_1d': vni.change_1d if vni else 0,
                'change_5d': vni.change_5d if vni else 0,
                'change_1m': vni.change_1m if vni else 0,
                'ma20': vni.ma20 if vni else 0,
                'ma50': vni.ma50 if vni else 0,
                'rsi_14': vni.rsi_14 if vni else 0,
                'adx': vni.adx if vni else 0,
                'volume_ratio': vni.volume_ratio if vni else 0,
                'volume_profile': {
                    'poc': vni.poc if vni else 0,
                    'vah': vni.vah if vni else 0,
                    'val': vni.val if vni else 0,
                    'price_vs_va': vni.price_vs_va if vni else '',
                }
            },
            'traffic_light': {
                'color': tl.color if tl else '',
                'score': tl.score if tl else 0,
                'action': tl.action if tl else '',
                'position_size': tl.position_size if tl else '',
                'scores': {
                    'trend': tl.trend_score if tl else 0,
                    'structure': tl.structure_score if tl else 0,
                    'momentum': tl.momentum_score if tl else 0,
                    'distribution': tl.distribution_score if tl else 0,
                    'volume': tl.volume_score if tl else 0,
                },
                'conditions_met': tl.conditions_met if tl else [],
                'conditions_failed': tl.conditions_failed if tl else [],
            },
            'breadth': {
                'advances': report.breadth.advances,
                'declines': report.breadth.declines,
                'ad_ratio': report.breadth.ad_ratio,
            },
            'money_flow': {
                'foreign_net': report.money_flow.foreign_net,
                'foreign_net_20d': report.money_flow.foreign_net_20d,
                'proprietary_net': report.money_flow.proprietary_net,
            },
            'sectors': [
                {
                    'code': s.code,
                    'name': s.name,
                    'change_1d': s.change_1d,
                    'rs_vs_index': s.rs_vs_index
                }
                for s in report.sectors
            ]
        }
        
        # Add context if available
        if ctx:
            result['context'] = self._context_to_dict(ctx)
        
        return result
    
    def _context_to_dict(self, ctx: FullContext) -> Dict:
        """Convert FullContext to dict"""
        return {
            'trend': {
                'ma20_slope': ctx.trend.ma20_slope,
                'ma50_slope': ctx.trend.ma50_slope,
                'ma_alignment': ctx.trend.ma_alignment,
            },
            'price': {
                'ma_position': ctx.price.ma_position,
                'percentile_50d': ctx.price.percentile_50d,
                'vs_ma20': ctx.price.price_vs_ma20,
                'vs_ma50': ctx.price.price_vs_ma50,
            },
            'rsi': {
                'current': ctx.rsi.rsi_current,
                'regime': ctx.rsi.regime,
                'overbought': ctx.rsi.is_overbought,
            },
            'macd': {
                'histogram': ctx.macd.histogram,
                'impulse_direction': ctx.macd.impulse_direction,
                'impulse_signal': ctx.macd.impulse_signal,
            },
            'distribution': {
                'count': ctx.distribution.count,
                'status': ctx.distribution.status,
            },
            'ftd': {
                'has_ftd': ctx.ftd.has_ftd,
                'date': ctx.ftd.ftd_date,
                'note': ctx.ftd.note,
            },
            'regime': {
                'current': ctx.regime.regime,
                'confidence': ctx.regime.confidence,
            }
        }
    
    def to_json(self, report: MarketReport, indent: int = 2) -> str:
        """Export to JSON string"""
        data = self.to_dict(report)
        return json.dumps(data, indent=indent, ensure_ascii=False, default=str)
    
    def to_markdown(self, report: MarketReport) -> str:
        """Export to Markdown"""
        vni = report.vnindex
        ctx = report.context
        tl = report.traffic_light
        
        # Context section
        context_section = ""
        if ctx:
            context_section = f"""
## 📊 DATA CONTEXT

### Trend Analysis
| Metric | Value | Status |
|--------|-------|--------|
| MA20 Slope | {ctx.trend.ma20_slope:+.2f}% | {ctx.trend.ma20_slope_status} |
| MA50 Slope | {ctx.trend.ma50_slope:+.2f}% | {ctx.trend.ma50_slope_status} |
| MA Alignment | {ctx.trend.ma_alignment} | {ctx.trend.ma_alignment_note} |

### Price Position
| Metric | Value |
|--------|-------|
| Position | {ctx.price.ma_position} |
| Percentile 50D | {ctx.price.percentile_50d:.0f}% |
| vs MA20 | {ctx.price.price_vs_ma20:+.2f}% |
| vs MA50 | {ctx.price.price_vs_ma50:+.2f}% |

### RSI Regime
| Metric | Value |
|--------|-------|
| RSI Current | {ctx.rsi.rsi_current:.1f} |
| RSI Min/Max 50D | {ctx.rsi.rsi_min_50d:.1f} / {ctx.rsi.rsi_max_50d:.1f} |
| Regime | {ctx.rsi.regime} |

### Distribution Days
| Count | Status | Note |
|-------|--------|------|
| {ctx.distribution.count} | {ctx.distribution.status} | {ctx.distribution.status_note} |

### Follow-Through Day
| Has FTD | Note |
|---------|------|
| {"✅ Yes" if ctx.ftd.has_ftd else "❌ No"} | {ctx.ftd.note} |

### Market Regime
**{ctx.regime.regime}** (Confidence: {ctx.regime.confidence:.0f}%)
"""
        
        # Traffic Light section
        tl_section = ""
        if tl:
            conditions_met = "\n".join([f"- {c}" for c in tl.conditions_met])
            conditions_failed = "\n".join([f"- {c}" for c in tl.conditions_failed])
            
            tl_section = f"""
## 🚦 TRAFFIC LIGHT (IBD Model)

| Metric | Value |
|--------|-------|
| **Color** | {tl.color} |
| **Score** | {tl.score}/100 |
| **Action** | {tl.action} |
| **Position Size** | {tl.position_size} |

### Component Scores
| Component | Score |
|-----------|-------|
| Trend | {tl.trend_score:+d} |
| Structure | {tl.structure_score:+d} |
| Momentum | {tl.momentum_score:+d} |
| Distribution | {tl.distribution_score:+d} |
| Volume/FTD | {tl.volume_score:+d} |

### Conditions Met
{conditions_met}

### Warnings
{conditions_failed}
"""
        
        content = f"""# 📈 BÁO CÁO MARKET TIMING v3
**Ngày:** {report.timestamp.strftime('%d/%m/%Y %H:%M')}

---

## 📊 TỔNG QUAN

| Metric | Value |
|--------|-------|
| **VNIndex** | {vni.price:,.0f} ({vni.change_1d:+.2f}%) |
| **Traffic Light** | {tl.color if tl else 'N/A'} |
| **Score** | {tl.score if tl else 0}/100 |
| **Action** | {tl.action if tl else 'N/A'} |

---
{context_section}
---
{tl_section}
---

## 📊 VOLUME PROFILE

| Metric | Value |
|--------|-------|
| POC | {vni.poc:,.0f} |
| Value Area | {vni.val:,.0f} - {vni.vah:,.0f} |
| Position | {vni.price_vs_va} |

---

## 📉 BREADTH & MONEY FLOW

| Metric | Value |
|--------|-------|
| Advances/Declines | {report.breadth.advances}/{report.breadth.declines} |
| A/D Ratio | {report.breadth.ad_ratio:.2f} |
| Foreign Net | {report.money_flow.foreign_net:+.1f} tỷ |
| Foreign 20D | {report.money_flow.foreign_net_20d:+.1f} tỷ |

---

## 🏭 SECTORS (by RS)

| Rank | Sector | 1D | RS vs Index |
|------|--------|-----|-------------|
""" + "\n".join([
            f"| {i+1} | {s.name} | {s.change_1d:+.2f}% | {s.rs_vs_index:+.2f}% |"
            for i, s in enumerate(report.sectors)
        ]) + f"""

---

## 🤖 AI ANALYSIS

{report.ai_analysis}
"""
        return content
    
    def save(self, report: MarketReport):
        """Save report to files"""
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        timestamp = report.timestamp.strftime('%Y%m%d_%H%M')
        
        # Save Markdown
        md_file = os.path.join(self.config.OUTPUT_DIR, f"market_timing_{timestamp}.md")
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(self.to_markdown(report))
        print(f"✓ Saved: {md_file}")
        
        # Save JSON
        if self.config.SAVE_JSON:
            json_file = os.path.join(self.config.OUTPUT_DIR, f"market_timing_{timestamp}.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                f.write(self.to_json(report))
            print(f"✓ Saved: {json_file}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MODULE
# ══════════════════════════════════════════════════════════════════════════════

class MarketTimingModule:
    """Module 1 v3: Market Timing với DataContext"""
    
    def __init__(self, config: MarketTimingConfig = None):
        self.config = config or create_config_from_unified()
        self.analyzer = MarketTimingAnalyzer(self.config)
        self.ai_generator = MarketTimingAIGenerator(self.config)
        self.exporter = ReportExporter(self.config)
        self.report: MarketReport = None
    
    def run(self) -> MarketReport:
        """Chạy full module"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║     MODULE 1 v3: MARKET TIMING + DATA CONTEXT                ║
║     Traffic Light (IBD) + Distribution Days + FTD            ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # 1. Thu thập dữ liệu
        self.report = self.analyzer.collect_data()
        
        # 2. Phân tích với DataContext (Module 0)
        self.report = self.analyzer.analyze_context(self.report)
        
        # 3. Tính Traffic Light (IBD model)
        self.report = self.analyzer.calculate_traffic_light(self.report)
        
        # 4. Generate AI analysis
        self.report.ai_analysis = self.ai_generator.generate(self.report)
        
        # 5. Print summary
        self._print_summary()
        
        # 6. Save
        if self.config.SAVE_REPORT:
            self.exporter.save(self.report)
        
        return self.report
    
    def _print_summary(self):
        """In tóm tắt"""
        print("\n" + "="*70)
        print("📋 TÓM TẮT")
        print("="*70)
        
        tl = self.report.traffic_light
        ctx = self.report.context
        
        print(f"\n🚦 TRAFFIC LIGHT: {tl.color}")
        print(f"   Score: {tl.score}/100 | Action: {tl.action}")
        print(f"   Position Size: {tl.position_size}")
        
        if ctx:
            print(f"\n🎪 MARKET REGIME: {ctx.regime.regime}")
            print(f"   Distribution Days: {ctx.distribution.count}/25")
            print(f"   FTD: {'✅ Yes' if ctx.ftd.has_ftd else '❌ No'}")
        
        print("\n" + "─"*70)
        print("🤖 AI ANALYSIS:")
        print("─"*70)
        print(self.report.ai_analysis[:2000] + "..." if len(self.report.ai_analysis) > 2000 else self.report.ai_analysis)
    
    def get_json(self) -> str:
        """Get report as JSON string"""
        if self.report:
            return self.exporter.to_json(self.report)
        return "{}"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Run module
    module = MarketTimingModule()
    report = module.run()
    
    # Print JSON sample
    print("\n" + "="*60)
    print("📄 JSON OUTPUT SAMPLE:")
    print("="*60)
    json_output = module.get_json()
    print(json_output[:1500] + "...")
