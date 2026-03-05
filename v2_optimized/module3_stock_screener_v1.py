
#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     MODULE 3: STOCK SCREENER - LỌC CỔ PHIẾU TỪ NGÀNH MẠNH                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  TÍNH NĂNG:                                                                  ║
║  ✅ Lấy danh sách mã từ ngành có RS cao (từ Module 2)                        ║
║  ✅ CANSLIM Fundamental Screening                                            ║
║  ✅ Technical Screening (RS Rating, MA, Volume)                              ║
║  ✅ Pattern Detection (VCP, Cup&Handle, Flat Base)                           ║
║  ✅ News Integration - Thu thập & phân tích tin tức                          ║
║  ✅ Composite Scoring System (0-100)                                         ║
║  ✅ AI Analysis cho từng candidate                                           ║
║  ✅ Output: JSON + Markdown Watchlist                                        ║
║  ✅ FIX: Chỉ dùng Sector Indices hợp lệ (loại bỏ VNENERGY, VNIND, VNUTI)    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import json
import time
import asyncio
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
    from .ai_providers import AIProvider, AIConfig
    HAS_AI = True
except ImportError:
    try:
        from ai_providers import AIProvider, AIConfig
        HAS_AI = True
    except ImportError:
        HAS_AI = False
        print("⚠️ Could not import AIProvider")
        AIProvider = None

# Import News Analyzer
try:
    from news_analyzer import NewsAnalyzer, NewsConfig, NewsArticle, NewsReport
    HAS_NEWS = True
except ImportError:
    HAS_NEWS = False
    NewsAnalyzer = None

# Import V3 Enhanced Modules
try:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from v3_enhanced.fundamental_enhanced_v3 import FundamentalAggregator, EnhancedCANSLIMScorer
    from v3_enhanced.vwap_indicator import VWAPIndicator, calculate_vwap
    from v3_enhanced.news_analyzer import NewsAnalyzer as V3NewsAnalyzer, analyze_news
    HAS_V3_ENHANCED = True
    print("✓ V3 Enhanced modules loaded")
except ImportError as e:
    HAS_V3_ENHANCED = False
    FundamentalAggregator = None
    VWAPIndicator = None
    V3NewsAnalyzer = None
    print(f"⚠️ V3 Enhanced not available: {e}")

# Import Stock Universe (dynamic stock list)
try:
    from stock_universe import StockUniverse, get_stock_universe
    HAS_STOCK_UNIVERSE = True
    print("✓ Stock Universe module loaded")
except ImportError as e:
    HAS_STOCK_UNIVERSE = False
    StockUniverse = None
    get_stock_universe = None
    print(f"⚠️ Stock Universe not available: {e}")

# Import Recommendation History Tracker
try:
    from history_manager import get_recommendation_tracker, RecommendationHistoryTracker
    HAS_REC_TRACKER = True
except ImportError:
    HAS_REC_TRACKER = False
    get_recommendation_tracker = None
    RecommendationHistoryTracker = None

# Import Enhanced Scoring (Piotroski, Altman, PEG, DuPont, etc.)
try:
    from enhanced_scoring import get_enhanced_scorer, EnhancedScorer
    HAS_ENHANCED_SCORING = True
    print("✓ Enhanced Scoring module loaded")
except ImportError as e:
    HAS_ENHANCED_SCORING = False
    get_enhanced_scorer = None
    EnhancedScorer = None
    print(f"⚠️ Enhanced Scoring not available: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS & CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

class SignalStrength(Enum):
    """Độ mạnh tín hiệu"""
    STRONG_BUY = "⭐⭐⭐ STRONG BUY"
    BUY = "⭐⭐ BUY"
    WATCH = "👀 WATCH"
    NEUTRAL = "➖ NEUTRAL"
    AVOID = "⛔ AVOID"


class PatternType(Enum):
    """Loại pattern kỹ thuật"""
    VCP = "VCP (Volatility Contraction)"
    CUP_HANDLE = "Cup & Handle"
    DOUBLE_BOTTOM = "Double Bottom"
    FLAT_BASE = "Flat Base"
    HIGH_TIGHT_FLAG = "High Tight Flag"
    ASCENDING_BASE = "Ascending Base"
    IPO_BASE = "IPO Base"
    NONE = "No Pattern"


# ══════════════════════════════════════════════════════════════════════════════
# VALID SECTOR STOCKS (Đã loại bỏ VNENERGY, VNIND, VNUTI)
# ══════════════════════════════════════════════════════════════════════════════

# Mapping ngành → danh sách mã (CHỈ CÁC NGÀNH HỢP LỆ)
SECTOR_STOCKS = {
    'VNFIN': ['VCB', 'BID', 'CTG', 'TCB', 'MBB', 'ACB', 'VPB', 'STB', 'TPB', 'HDB',
              'SSI', 'VND', 'HCM', 'VCI', 'SHS', 'MBS', 'BSI', 'BVH', 'PVI', 'MIG'],
    
    'VNREAL': ['VHM', 'VIC', 'NVL', 'KDH', 'DXG', 'NLG', 'HDG', 'DIG', 'PDR', 'KBC',
               'IJC', 'CEO', 'LDG', 'SCR', 'NBB', 'DXS', 'NHA', 'HQC', 'TDC', 'VRE'],
    
    'VNMAT': ['HPG', 'HSG', 'NKG', 'TLH', 'SMC', 'POM', 'HT1', 'BCC', 'HMC', 'DTL',
              'DPM', 'DCM', 'DGC', 'CSV', 'LAS', 'PHR', 'DRC', 'CSM', 'SRC', 'BMP'],
    
    'VNIT': ['FPT', 'CMG', 'VGI', 'FOX', 'ITD', 'ELC', 'SAM', 'ONE', 'POT', 'ICT'],
    
    'VNHEAL': ['DHG', 'DMC', 'IMP', 'DBD', 'TRA', 'PME', 'AMV', 'DBT', 'DCL', 'OPC'],
    
    'VNCOND': ['MWG', 'PNJ', 'DGW', 'FRT', 'VNM', 'SAB', 'MSN', 'QNS', 'KDC', 'MCH',
               'HAG', 'DBC', 'ANV', 'VHC', 'IDI', 'ASM', 'CTF', 'TCM', 'TNG', 'MSH'],
    
    # Thêm VNCONS - Tiêu dùng thiết yếu (từ các mã tiêu dùng)
    'VNCONS': ['VNM', 'SAB', 'MSN', 'QNS', 'KDC', 'MCH', 'VLC', 'SBT', 'LSS', 'NHS',
               'NAF', 'HAG', 'DBC', 'ANV', 'VHC', 'IDI'],
}

# Sector name mapping
SECTOR_NAMES = {
    'VNFIN': 'Tài chính',
    'VNREAL': 'Bất động sản',
    'VNMAT': 'Nguyên vật liệu',
    'VNIT': 'Công nghệ',
    'VNHEAL': 'Y tế',
    'VNCOND': 'Tiêu dùng không thiết yếu',
    'VNCONS': 'Tiêu dùng thiết yếu',
}


# ══════════════════════════════════════════════════════════════════════════════
# DYNAMIC STOCK LIST (từ Stock Universe)
# ══════════════════════════════════════════════════════════════════════════════

# Flag để enable/disable dynamic stock list
USE_DYNAMIC_STOCK_LIST = True  # Set False để dùng SECTOR_STOCKS hardcode

def get_sector_stocks_dynamic(sector: str, min_volume: int = 100_000) -> List[str]:
    """
    Lấy danh sách cổ phiếu theo ngành từ Stock Universe API

    Fallback về SECTOR_STOCKS nếu Stock Universe không khả dụng

    Args:
        sector: Mã ngành (VNFIN, VNREAL, etc.)
        min_volume: Volume tối thiểu (mặc định 100k)

    Returns:
        List[str]: Danh sách mã cổ phiếu
    """
    # Nếu không dùng dynamic list hoặc không có StockUniverse
    if not USE_DYNAMIC_STOCK_LIST or not HAS_STOCK_UNIVERSE:
        return SECTOR_STOCKS.get(sector, [])

    try:
        universe = get_stock_universe()
        sector_map = universe.get_stocks_by_sector(sector, min_volume=min_volume)
        stocks = sector_map.get(sector, [])

        if stocks:
            return stocks
        else:
            # Fallback nếu không tìm thấy
            return SECTOR_STOCKS.get(sector, [])

    except Exception as e:
        print(f"⚠️ Stock Universe error for {sector}: {e}")
        return SECTOR_STOCKS.get(sector, [])


def get_all_sector_stocks(sectors: List[str] = None,
                         min_volume: int = 100_000) -> Dict[str, List[str]]:
    """
    Lấy danh sách cổ phiếu cho tất cả hoặc một số ngành

    Args:
        sectors: Danh sách ngành cần lấy. None = tất cả 7 ngành
        min_volume: Volume tối thiểu

    Returns:
        Dict[sector, List[symbol]]
    """
    if sectors is None:
        sectors = list(SECTOR_NAMES.keys())

    # Nếu không dùng dynamic list
    if not USE_DYNAMIC_STOCK_LIST or not HAS_STOCK_UNIVERSE:
        return {s: SECTOR_STOCKS.get(s, []) for s in sectors}

    try:
        universe = get_stock_universe()
        all_stocks = universe.get_stocks_by_sector(min_volume=min_volume)

        # Filter chỉ các sector được yêu cầu
        result = {}
        for sector in sectors:
            if sector in all_stocks:
                result[sector] = all_stocks[sector]
            else:
                # Fallback
                result[sector] = SECTOR_STOCKS.get(sector, [])

        return result

    except Exception as e:
        print(f"⚠️ Stock Universe error: {e}")
        return {s: SECTOR_STOCKS.get(s, []) for s in sectors}


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScreenerConfig:
    """Config cho Module 3"""
    
    # API
    VNSTOCK_API_KEY: str = ""
    DATA_SOURCE: str = "VCI"
    
    # Sector indices mapping
    SECTOR_INDICES: Dict[str, str] = field(default_factory=lambda: SECTOR_NAMES)
    
    # Screening thresholds
    MIN_RS_RATING: int = 70          # RS tối thiểu để xét
    MIN_EPS_GROWTH: float = 15.0     # EPS growth % tối thiểu
    MIN_REVENUE_GROWTH: float = 10.0 # Revenue growth % tối thiểu
    MIN_ROE: float = 12.0            # ROE % tối thiểu
    
    # Technical
    MIN_VOLUME_AVG: int = 100000     # Volume trung bình tối thiểu
    MAX_DISTANCE_FROM_HIGH: float = 25.0  # % tối đa so với đỉnh 52 tuần
    
    # Score weights
    WEIGHT_FUNDAMENTAL: float = 0.35
    WEIGHT_TECHNICAL: float = 0.35
    WEIGHT_PATTERN: float = 0.15
    WEIGHT_NEWS: float = 0.15
    
    # Lookback
    LOOKBACK_DAYS: int = 250
    
    # Rate limit
    API_DELAY: float = 0.3
    
    # AI
    AI_PROVIDER: str = ""
    AI_API_KEY: str = ""
    AI_MAX_TOKENS: int = 4096
    USE_AI_SELECTION: bool = True  # Full AI-based stock selection (instead of algorithm)
    
    # News
    ENABLE_NEWS: bool = True
    NEWS_KEYWORDS_PER_STOCK: int = 3
    
    # Output
    OUTPUT_DIR: str = "./output"
    SAVE_REPORT: bool = True
    SAVE_JSON: bool = True
    
    # Top picks
    TOP_PICKS_COUNT: int = 10


def create_config_from_unified() -> ScreenerConfig:
    """Tạo config từ UnifiedConfig"""
    unified = get_config()
    
    config = ScreenerConfig()
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
class FundamentalData:
    """Dữ liệu cơ bản"""
    eps_ttm: float = 0.0
    eps_growth_qoq: float = 0.0
    eps_growth_yoy: float = 0.0
    eps_growth_3y: float = 0.0
    revenue_ttm: float = 0.0
    revenue_growth_qoq: float = 0.0
    revenue_growth_yoy: float = 0.0
    roe: float = 0.0
    roa: float = 0.0
    profit_margin: float = 0.0
    pe: float = 0.0
    pb: float = 0.0
    dividend_yield: float = 0.0
    market_cap: float = 0.0
    outstanding_shares: float = 0.0
    foreign_net_buy_20d: float = 0.0
    consecutive_eps_growth: int = 0    # Consecutive quarters
    earnings_stability: float = 0.0    # Stability score
    confidence_score: float = 50.0     # Data confidence
    
    # Cash Flow Quality
    ocf_to_profit_ratio: float = 0.0
    cash_flow_quality_score: float = 0.0
    cash_flow_warning: str = ""

    # Fundamental Scores
    c_score: float = 0.0
    a_score: float = 0.0

    # Enhanced Scoring (NEW)
    piotroski_score: int = 0              # 0-9
    piotroski_rating: str = ""            # Very Strong, Strong, Average, Weak
    altman_z_score: float = 0.0
    altman_zone: str = ""                 # safe, grey, distress
    peg_ratio: float = 0.0
    peg_rating: str = ""                  # very_cheap, cheap, fair, expensive
    dupont_roe: float = 0.0
    dupont_driver: str = ""               # Strongest ROE component
    dupont_weakness: str = ""             # Weakest ROE component
    valuation_status: str = ""            # undervalued, fair, overvalued
    dividend_yield_pct: float = 0.0
    dividend_rating: str = ""             # excellent, high, good, average, low, none
    industry_health_score: int = 0        # 0-100
    financial_health_score: float = 0.0   # Composite 0-100

    # V3 Enhanced
    eps_growth_3y_cagr: float = 0.0
    eps_growth_5y_cagr: float = 0.0
    eps_acceleration: float = 0.0



@dataclass
class TechnicalData:
    """Dữ liệu kỹ thuật"""
    price: float = 0.0
    change_1d: float = 0.0
    change_5d: float = 0.0
    change_1m: float = 0.0
    change_3m: float = 0.0
    
    # RS Rating
    rs_raw: float = 0.0
    rs_rating: int = 50
    
    # Moving Averages
    ma20: float = 0.0
    ma50: float = 0.0
    ma200: float = 0.0
    above_ma20: bool = False
    above_ma50: bool = False
    above_ma200: bool = False
    
    ma50_slope: float = 0.0  # Độ dốc MA50
    
    # RSI
    rsi_14: float = 50.0
    
    # Volume
    volume_avg_20: int = 0
    volume_ratio: float = 1.0  # Hôm nay / Avg
    
    # High/Low
    high_52w: float = 0.0
    low_52w: float = 0.0
    distance_from_high: float = 0.0  # % dưới đỉnh
    
    # Volume Profile
    poc: float = 0.0
    vah: float = 0.0
    val: float = 0.0
    price_vs_va: str = ""
    
    # VWAP (V3 Enhanced)
    vwap: float = 0.0
    vwap_score: float = 50.0
    price_vs_vwap: str = ""  # "ABOVE", "BELOW", "AT"
    vwap_buy_signal: bool = False
    
    # ATR for Dynamic SL/TP
    atr_14: float = 0.0       # Average True Range 14 ngày
    atr_pct: float = 0.0      # ATR as % of price
    
    # Foreign Trade (Current Session)
    foreign_buy_value: float = 0.0
    foreign_sell_value: float = 0.0
    foreign_net_value: float = 0.0



@dataclass
class PatternData:
    """Dữ liệu pattern"""
    pattern_type: PatternType = PatternType.NONE
    pattern_quality: float = 0.0  # 0-100
    
    # Pattern details
    base_depth: float = 0.0       # % độ sâu base
    base_length: int = 0          # Số ngày
    contraction_count: int = 0    # Số lần co hẹp (cho VCP)
    
    # Buy point
    buy_point: float = 0.0
    current_vs_buy_point: float = 0.0  # % so với buy point
    
    # Description
    description: str = ""
    
    # Volume Confirmation (NEW)
    volume_confirmed: bool = False     # True nếu đủ điều kiện volume
    volume_score: float = 0.0          # 0-80 điểm volume
    has_shakeout: bool = False         # Có phiên rũ bỏ volume lớn
    has_dryup: bool = False            # Volume cạn kiệt gần pivot
    breakout_ready: bool = False       # Sẵn sàng breakout (shakeout + dryup)


@dataclass
class StockNews:
    """Tin tức cổ phiếu"""
    articles: List = field(default_factory=list)
    sentiment: str = "neutral"  # positive/negative/neutral
    sentiment_score: float = 0.0  # -1 to +1
    key_topics: List[str] = field(default_factory=list)
    ai_summary: str = ""


@dataclass
class StockCandidate:
    """Ứng viên cổ phiếu"""
    symbol: str
    name: str = ""
    sector_code: str = ""
    sector_name: str = ""
    
    # Data
    fundamental: FundamentalData = field(default_factory=FundamentalData)
    technical: TechnicalData = field(default_factory=TechnicalData)
    pattern: PatternData = field(default_factory=PatternData)
    news: StockNews = field(default_factory=StockNews)
    
    # Scores (0-100)
    score_fundamental: float = 0.0
    score_technical: float = 0.0
    score_pattern: float = 0.0
    score_news: float = 0.0
    score_total: float = 0.0
    
    # Signal
    signal: SignalStrength = SignalStrength.NEUTRAL
    
    # Rank
    rank: int = 0
    
    # AI
    ai_analysis: str = ""
    
    # Action
    action: str = ""
    buy_zone: str = ""
    stop_loss: float = 0.0


@dataclass 
class ScreenerReport:
    """Báo cáo screening"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Input context
    target_sectors: List[str] = field(default_factory=list)
    market_context: Dict = field(default_factory=dict)
    
    # Screening stats
    total_scanned: int = 0
    passed_fundamental: int = 0
    passed_technical: int = 0
    passed_pattern: int = 0
    
    # Results
    candidates: List[StockCandidate] = field(default_factory=list)
    
    # Top picks
    top_picks: List[StockCandidate] = field(default_factory=list)
    
    # News summary
    news_summary: str = ""
    
    # AI
    ai_analysis: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# FUNDAMENTAL ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class FundamentalAnalyzer:
    """
    Phân tích cơ bản theo CANSLIM
    
    C - Current quarterly EPS: ≥ 25% growth
    A - Annual EPS growth: ≥ 25% over 3-5 years
    N - New highs, new products, new management
    S - Supply/demand (float, volume)
    L - Leader (RS Rating)
    I - Institutional sponsorship
    M - Market direction
    
    V3 Enhanced: Uses FundamentalAggregator for multi-source data
    """
    
    def __init__(self, config: ScreenerConfig):
        self.config = config
        self.collector = get_data_collector()

        # V3 Enhanced: Initialize FundamentalAggregator
        self.v3_aggregator = None
        self.v3_scorer = None
        if HAS_V3_ENHANCED and FundamentalAggregator:
            try:
                self.v3_aggregator = FundamentalAggregator(
                    vnstock_api_key=config.VNSTOCK_API_KEY,
                    cache_dir="./cache"
                )
                self.v3_scorer = EnhancedCANSLIMScorer()
                print("   ✓ V3 FundamentalAggregator initialized")
            except Exception as e:
                print(f"   ⚠️ V3 Aggregator init failed: {e}")

        # Enhanced Scoring: Piotroski, Altman, PEG, DuPont
        self.enhanced_scorer = None
        if HAS_ENHANCED_SCORING and get_enhanced_scorer:
            try:
                self.enhanced_scorer = get_enhanced_scorer()
                print("   ✓ Enhanced Scorer initialized (Piotroski, Altman, PEG, DuPont)")
            except Exception as e:
                print(f"   ⚠️ Enhanced Scorer init failed: {e}")
    
    def analyze(self, symbol: str) -> FundamentalData:
        """Phân tích fundamental cho một mã"""
        data = FundamentalData()
        
        try:
            # V3 Enhanced: Use FundamentalAggregator if available
            if self.v3_aggregator:
                v3_data = self.v3_aggregator.get_fundamental_data(symbol)
                
                # Map V3 data to local FundamentalData
                data.roe = v3_data.roe
                data.roa = v3_data.roa
                data.profit_margin = v3_data.net_profit_margin if hasattr(v3_data, 'net_profit_margin') else 0.0
                data.pe = v3_data.pe
                data.pb = v3_data.pb
                data.eps_growth_qoq = v3_data.eps_growth_qoq
                data.eps_growth_yoy = v3_data.eps_growth_yoy
                data.eps_growth_3y = v3_data.eps_growth_3y_cagr
                data.eps_growth_3y_cagr = v3_data.eps_growth_3y_cagr
                data.eps_growth_5y_cagr = v3_data.eps_growth_5y_cagr
                data.revenue_growth_qoq = v3_data.revenue_growth_qoq
                data.revenue_growth_yoy = v3_data.revenue_growth_yoy
                data.eps_acceleration = v3_data.eps_acceleration
                data.consecutive_eps_growth = v3_data.consecutive_eps_growth
                data.earnings_stability = v3_data.earnings_stability
                data.confidence_score = v3_data.confidence_score
                
                # Cash Flow Quality
                data.ocf_to_profit_ratio = v3_data.ocf_to_profit_ratio
                data.cash_flow_quality_score = v3_data.cash_flow_quality_score
                data.cash_flow_warning = v3_data.cash_flow_warning
                
                # Use V3 scorer
                if self.v3_scorer:
                    score, breakdown = self.v3_scorer.score_fundamental(v3_data)
                    data.c_score = breakdown['c_score']
                    data.a_score = breakdown['a_score']
                else:
                    data.c_score = self._calc_c_score(data)
                    data.a_score = self._calc_a_score(data)

                print(f"   📊 Funda V3: ROE={data.roe:.1f}% EPS_3Y={data.eps_growth_3y_cagr:.1f}% Conf={data.confidence_score:.0f}%")

                # Apply Enhanced Scoring (Piotroski, Altman, PEG, DuPont) to V3 data
                if self.enhanced_scorer:
                    self._apply_enhanced_scoring_v3(symbol, data, v3_data)

                return data
            
            # Fallback to original logic
            stock = self.collector.get_stock_data(symbol, lookback_days=30, include_vp=False)
            
            # Lấy Real Financial Data
            ratios = self.collector.get_financial_ratios(symbol)
            flow = self.collector.get_financial_flow(symbol)
            
            # Map data
            data.market_cap = getattr(stock, 'market_cap', 0)
            
            # Ratios
            data.pe = ratios.get('pe', 0)
            data.pb = ratios.get('pb', 0)
            data.roe = ratios.get('roe', 0)
            data.roa = ratios.get('roa', 0)
            data.profit_margin = ratios.get('net_margin', 0)
            
            # Growth
            data.eps_growth_qoq = flow.get('eps_growth_qoq', 0)
            data.eps_growth_yoy = flow.get('eps_growth_yoy', 0)
            data.revenue_growth_qoq = flow.get('revenue_growth_qoq', 0)
            data.revenue_growth_yoy = flow.get('revenue_growth_yoy', 0)
            
            # Placeholder for 3y growth
            data.eps_growth_3y = data.eps_growth_yoy 
            
            # Tính C score (Current EPS)
            data.c_score = self._calc_c_score(data)
            
            # Tính A score (Annual EPS)
            data.a_score = self._calc_a_score(data)
            
            print(f"   📊 Funda: ROE={data.roe:.1f}% EPS_YoY={data.eps_growth_yoy:.1f}%")

            # Run Enhanced Scoring (Piotroski, Altman, PEG, DuPont)
            self._apply_enhanced_scoring(symbol, data, ratios, flow)

        except Exception as e:
            print(f"   ⚠️ Fundamental error {symbol}: {e}")

        return data

    def _apply_enhanced_scoring(self, symbol: str, data: FundamentalData,
                                ratios: Dict = None, flow: Dict = None):
        """Apply enhanced scoring (Piotroski, Altman, PEG, DuPont) to FundamentalData"""
        if not self.enhanced_scorer:
            return

        try:
            # Build financials dict for enhanced scorer
            current_financials = {
                'roa': data.roa / 100 if data.roa else 0,
                'cfo': flow.get('ocf', 0) if flow else 0,
                'net_income': flow.get('net_income', 0) if flow else 0,
                'total_assets': flow.get('total_assets', 0) if flow else 0,
                'total_liabilities': flow.get('total_liabilities', 0) if flow else 0,
                'total_equity': flow.get('total_equity', 0) if flow else 0,
                'current_assets': flow.get('current_assets', 0) if flow else 0,
                'current_liabilities': flow.get('current_liabilities', 0) if flow else 0,
                'shares_outstanding': data.outstanding_shares,
                'gross_profit': flow.get('gross_profit', 0) if flow else 0,
                'revenue': flow.get('revenue', 0) if flow else 0,
                'retained_earnings': flow.get('retained_earnings', 0) if flow else 0,
                'ebit': flow.get('operating_profit', 0) if flow else 0,
                'pe': data.pe,
                'pb': data.pb,
                'market_cap': data.market_cap,
                'eps_growth_yoy': data.eps_growth_yoy,
            }

            # Quick health check (Piotroski + Altman + PEG)
            health = self.enhanced_scorer.quick_health_check(current_financials)
            data.piotroski_score = health.get('piotroski_score', 0)
            data.piotroski_rating = health.get('piotroski_rating', '')
            data.altman_z_score = health.get('altman_z_score', 0)
            data.altman_zone = health.get('altman_zone', '')
            if health.get('peg_ratio') is not None:
                data.peg_ratio = health['peg_ratio']
                data.peg_rating = health.get('peg_rating', '')

            # Log enhanced metrics
            if data.piotroski_score > 0 or data.altman_z_score > 0:
                peg_str = f" PEG={data.peg_ratio:.2f}" if data.peg_ratio else ""
                print(f"   📈 Enhanced: Piotroski={data.piotroski_score}/9 Altman={data.altman_z_score:.2f} ({data.altman_zone}){peg_str}")

        except Exception as e:
            print(f"   ⚠️ Enhanced scoring error: {e}")

    def _apply_enhanced_scoring_v3(self, symbol: str, data: FundamentalData, v3_data):
        """Apply enhanced scoring using V3 aggregated data"""
        if not self.enhanced_scorer:
            return

        try:
            # Build current financials dict from v3_data
            current_financials = {
                'roa': data.roa / 100 if data.roa else 0,
                'cfo': getattr(v3_data, 'ocf', 0) or 0,
                'net_income': getattr(v3_data, 'net_income', 0) or 0,
                'total_assets': getattr(v3_data, 'total_assets', 0) or 0,
                'total_liabilities': getattr(v3_data, 'total_liabilities', 0) or 0,
                'total_equity': getattr(v3_data, 'total_equity', 0) or 0,
                'current_assets': getattr(v3_data, 'current_assets', 0) or 0,
                'current_liabilities': getattr(v3_data, 'current_liabilities', 0) or 0,
                'long_term_debt': getattr(v3_data, 'long_term_debt', 0) or 0,
                'shares_outstanding': getattr(v3_data, 'shares_outstanding', 0) or data.outstanding_shares,
                'gross_profit': getattr(v3_data, 'gross_profit', 0) or 0,
                'revenue': getattr(v3_data, 'revenue', 0) or 0,
                'retained_earnings': getattr(v3_data, 'retained_earnings', 0) or 0,
                'ebit': getattr(v3_data, 'operating_profit', 0) or 0,
                'operating_profit': getattr(v3_data, 'operating_profit', 0) or 0,
                'profit_before_tax': getattr(v3_data, 'profit_before_tax', 0) or 0,
                'pe': data.pe,
                'pb': data.pb,
                'market_cap': data.market_cap,
                'eps_growth_yoy': data.eps_growth_yoy,
            }

            # Build previous financials for Piotroski YoY comparison
            previous_financials = None
            if getattr(v3_data, 'prev_total_assets', 0) > 0:
                previous_financials = {
                    'roa': getattr(v3_data, 'prev_roa', 0) / 100 if getattr(v3_data, 'prev_roa', 0) else 0,
                    'total_assets': getattr(v3_data, 'prev_total_assets', 0) or 0,
                    'total_liabilities': getattr(v3_data, 'prev_total_liabilities', 0) or 0,
                    'current_assets': getattr(v3_data, 'prev_current_assets', 0) or 0,
                    'current_liabilities': getattr(v3_data, 'prev_current_liabilities', 0) or 0,
                    'shares_outstanding': getattr(v3_data, 'prev_shares_outstanding', 0) or 0,
                    'gross_profit': getattr(v3_data, 'prev_gross_profit', 0) or 0,
                    'revenue': getattr(v3_data, 'prev_revenue', 0) or 0,
                }

            # Quick health check (Piotroski + Altman + PEG)
            health = self.enhanced_scorer.quick_health_check(current_financials, previous_financials)
            data.piotroski_score = health.get('piotroski_score', 0)
            data.piotroski_rating = health.get('piotroski_rating', '')
            data.altman_z_score = health.get('altman_z_score', 0)
            data.altman_zone = health.get('altman_zone', '')
            if health.get('peg_ratio') is not None:
                data.peg_ratio = health['peg_ratio']
                data.peg_rating = health.get('peg_rating', '')

            # Log enhanced metrics
            if data.piotroski_score > 0 or data.altman_z_score > 0:
                peg_str = f" PEG={data.peg_ratio:.2f}" if data.peg_ratio else ""
                print(f"   📈 Enhanced: Piotroski={data.piotroski_score}/9 Altman={data.altman_z_score:.2f} ({data.altman_zone}){peg_str}")

        except Exception as e:
            print(f"   ⚠️ Enhanced scoring V3 error: {e}")

    def _calc_c_score(self, data: FundamentalData) -> float:
        """Tính C score (0-100)"""
        score = 0
        
        # EPS growth Q/Q
        if data.eps_growth_qoq >= 50:
            score += 40
        elif data.eps_growth_qoq >= 25:
            score += 30
        elif data.eps_growth_qoq >= 15:
            score += 20
        elif data.eps_growth_qoq > 0:
            score += 10
        
        # EPS acceleration
        if data.eps_growth_qoq > data.eps_growth_yoy:
            score += 20  # Đang tăng tốc
        
        # Revenue growth support
        if data.revenue_growth_qoq >= 25:
            score += 20
        elif data.revenue_growth_qoq >= 15:
            score += 15
        elif data.revenue_growth_qoq > 0:
            score += 10
        
        # Profit margin
        if data.profit_margin >= 20:
            score += 20
        elif data.profit_margin >= 10:
            score += 10
        
        return min(100, score)
    
    def _calc_a_score(self, data: FundamentalData) -> float:
        """Tính A score (0-100)"""
        score = 0
        
        # EPS growth 3 năm
        if data.eps_growth_3y >= 30:
            score += 40
        elif data.eps_growth_3y >= 20:
            score += 30
        elif data.eps_growth_3y >= 15:
            score += 20
        elif data.eps_growth_3y > 0:
            score += 10
        
        # ROE
        if data.roe >= 25:
            score += 30
        elif data.roe >= 17:
            score += 20
        elif data.roe >= 12:
            score += 10
        
        # ROA
        if data.roa >= 15:
            score += 15
        elif data.roa >= 10:
            score += 10
        
        # Stability (không âm trong 5 năm)
        # Placeholder
        score += 15
        
        return min(100, score)
    
    def score(self, data: FundamentalData) -> float:
        """Tính điểm fundamental tổng (0-100)"""
        # Weighted average of C and A scores
        c_weight = 0.6  # Current important hơn
        a_weight = 0.4

        base_score = data.c_score * c_weight + data.a_score * a_weight

        # Bonus/Penalty
        bonus = 0

        # ROE bonus
        if data.roe >= 20:
            bonus += 5

        # PE reasonable
        if 5 <= data.pe <= 20:
            bonus += 5
        elif data.pe > 40:
            bonus -= 5

        # Foreign interest
        if data.foreign_net_buy_20d > 0:
            bonus += 5

        # Enhanced Scoring Bonus (NEW)
        # Piotroski F-Score bonus (max +10)
        if data.piotroski_score >= 8:
            bonus += 10
        elif data.piotroski_score >= 6:
            bonus += 5
        elif data.piotroski_score <= 2:
            bonus -= 5

        # Altman Z-Score bonus/penalty (max +5/-10)
        if data.altman_zone == 'safe':
            bonus += 5
        elif data.altman_zone == 'distress':
            bonus -= 10

        # Store financial health score
        data.financial_health_score = min(100, max(0, base_score + bonus))

        return data.financial_health_score


# ══════════════════════════════════════════════════════════════════════════════
# TECHNICAL ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class TechnicalAnalyzer:
    """
    Phân tích kỹ thuật
    
    Criteria:
    - RS Rating (IBD style)
    - Price vs MA alignment
    - Volume characteristics
    - Distance from 52-week high
    - VWAP (V3 Enhanced)
    """
    
    def __init__(self, config: ScreenerConfig):
        self.config = config
        self.collector = get_data_collector(enable_volume_profile=True)
        
        # V3 Enhanced: Initialize VWAP Indicator
        self.vwap_indicator = None
        if HAS_V3_ENHANCED and VWAPIndicator:
            try:
                self.vwap_indicator = VWAPIndicator(lookback_days=20)
                print("   ✓ V3 VWAPIndicator initialized")
            except Exception as e:
                print(f"   ⚠️ VWAP Indicator init failed: {e}")
    
    def analyze(self, symbol: str, sector_rs: int = 50) -> TechnicalData:
        """Phân tích technical cho một mã"""
        data = TechnicalData()
        
        try:
            stock = self.collector.get_stock_data(
                symbol, 
                lookback_days=self.config.LOOKBACK_DAYS,
                include_vp=True
            )
            
            if stock.price == 0:
                return data
            
            # Price data
            data.price = stock.price
            data.change_1d = stock.change_1d
            data.change_5d = stock.change_5d
            data.change_1m = stock.change_1m
            data.change_3m = stock.change_3m
            
            # MA data
            data.ma20 = stock.ma20
            data.ma50 = stock.ma50
            data.ma200 = getattr(stock, 'ma200', stock.ma50 * 0.95)
            data.above_ma20 = stock.above_ma20
            data.above_ma50 = stock.above_ma50
            data.above_ma200 = data.price > data.ma200
            
            # RSI
            data.rsi_14 = stock.rsi_14
            
            # Volume
            data.volume_avg_20 = getattr(stock, 'volume_avg_20', 0)
            data.volume_ratio = getattr(stock, 'volume_ratio', 1.0)
            
            # High/Low
            data.high_52w = getattr(stock, 'high_52w', data.price * 1.1)
            data.low_52w = getattr(stock, 'low_52w', data.price * 0.7)
            data.distance_from_high = (data.high_52w - data.price) / data.high_52w * 100
            
            # Volume Profile
            data.poc = stock.poc
            data.vah = stock.vah
            data.val = stock.val
            data.price_vs_va = stock.price_vs_va
            
            # V3 Enhanced: VWAP (using pre-fetched data from stock.df)
            if self.vwap_indicator and hasattr(stock, 'df') and stock.df is not None:
                try:
                    # Use calculate_from_df to avoid extra API call
                    vwap_result = self.vwap_indicator.calculate_from_df(symbol, stock.df)
                    data.vwap = vwap_result.vwap
                    data.vwap_score = vwap_result.vwap_score
                    data.price_vs_vwap = vwap_result.price_vs_vwap
                    data.vwap_buy_signal = vwap_result.buy_signal
                except Exception as e:
                    pass  # Silent fail, VWAP is optional
            
            # V3 Enhanced: ATR for Dynamic SL/TP
            if hasattr(stock, 'df') and stock.df is not None and len(stock.df) >= 14:
                try:
                    import pandas_ta as ta
                    df = stock.df.copy()
                    atr = ta.atr(df['high'], df['low'], df['close'], length=14)
                    if atr is not None and len(atr) > 0:
                        data.atr_14 = float(atr.iloc[-1]) if not pd.isna(atr.iloc[-1]) else data.price * 0.03
                        data.atr_pct = (data.atr_14 / data.price) * 100 if data.price > 0 else 3.0
                except Exception as e:
                    data.atr_14 = data.price * 0.03  # Default 3%
                    data.atr_pct = 3.0

            # Foreign Trade (Current Session)
            data.foreign_buy_value = getattr(stock, 'foreign_buy_value', 0.0)
            data.foreign_sell_value = getattr(stock, 'foreign_sell_value', 0.0)
            data.foreign_net_value = getattr(stock, 'foreign_net_value', 0.0)

            
            # RS Rating - cần tính từ performance
            data.rs_raw = self._calc_rs_raw(stock)
            # RS Rating sẽ được tính sau khi có đủ data các mã
            
        except Exception as e:
            pass

        
        return data
    
    def _calc_rs_raw(self, stock: EnhancedStockData) -> float:
        """Tính RS raw score"""
        # IBD style weights
        return (
            stock.change_1m * 0.40 +
            stock.change_3m * 0.30 +
            getattr(stock, 'change_6m', stock.change_3m * 1.5) * 0.20 +
            getattr(stock, 'change_12m', stock.change_3m * 2) * 0.10
        )
    
    def score(self, data: TechnicalData, sector_rs: int = 50) -> float:
        """Tính điểm technical (0-100)"""
        score = 0
        
        # RS Rating (30 points)
        rs_score = (data.rs_rating / 99) * 30
        score += rs_score
        
        # MA Alignment (25 points)
        if data.above_ma20 and data.above_ma50 and data.above_ma200:
            score += 25  # Perfect alignment
        elif data.above_ma20 and data.above_ma50:
            score += 20
        elif data.above_ma50:
            score += 12
        elif data.above_ma20:
            score += 8
        
        # Distance from High (15 points)
        # Gần đỉnh = tốt (N in CANSLIM - New High)
        if data.distance_from_high <= 5:
            score += 15
        elif data.distance_from_high <= 10:
            score += 12
        elif data.distance_from_high <= 15:
            score += 8
        elif data.distance_from_high <= 25:
            score += 4
        
        # RSI (15 points)
        # Optimal: 50-70
        if 50 <= data.rsi_14 <= 70:
            score += 15
        elif 40 <= data.rsi_14 < 50:
            score += 12
        elif 70 < data.rsi_14 <= 80:
            score += 8
        elif data.rsi_14 < 30:
            score += 10  # Oversold bounce potential
        
        # Volume (15 points)
        if data.volume_ratio >= 1.5:
            score += 15  # Tăng với volume
        elif data.volume_ratio >= 1.0:
            score += 10
        elif data.volume_ratio >= 0.7:
            score += 5
        
        return min(100, max(0, score))


# ══════════════════════════════════════════════════════════════════════════════
# PATTERN DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

class PatternDetector:
    """
    Phát hiện các pattern kỹ thuật IBD
    
    Patterns:
    - VCP (Volatility Contraction Pattern)
    - Cup & Handle
    - Double Bottom
    - Flat Base
    - Ascending Base
    """
    
    def __init__(self, config: ScreenerConfig):
        self.config = config
        self.collector = get_data_collector()
    
    def detect(self, symbol: str) -> PatternData:
        """Phát hiện pattern cho một mã"""
        data = PatternData()
        
        try:
            # Lấy OHLCV data
            stock = self.collector.get_stock_data(symbol, lookback_days=120, include_vp=False)
            
            if stock.price == 0:
                return data
            
            # Lấy DataFrame nếu có
            df = getattr(stock, 'df', None)
            if df is None or len(df) < 50:
                # Không đủ data để detect pattern
                return data
            
            # Detect các pattern
            patterns_found = []
            
            # VCP Detection
            vcp_result = self._detect_vcp(df)
            if vcp_result['detected']:
                patterns_found.append(('VCP', vcp_result))
            
            # Flat Base Detection
            flat_result = self._detect_flat_base(df)
            if flat_result['detected']:
                patterns_found.append(('FLAT_BASE', flat_result))
            
            # Cup & Handle Detection
            cup_result = self._detect_cup_handle(df)
            if cup_result['detected']:
                patterns_found.append(('CUP_HANDLE', cup_result))
            
            # Chọn pattern tốt nhất
            if patterns_found:
                best = max(patterns_found, key=lambda x: x[1].get('quality', 0))
                pattern_type, result = best
                
                data.pattern_type = PatternType[pattern_type]
                data.pattern_quality = result.get('quality', 0)
                data.base_depth = result.get('depth', 0)
                data.base_length = result.get('length', 0)
                data.contraction_count = result.get('contractions', 0)
                data.buy_point = result.get('buy_point', stock.price * 1.02)
                data.description = result.get('description', '')
                
                # Current vs Buy Point
                data.current_vs_buy_point = (stock.price - data.buy_point) / data.buy_point * 100
                
                # NEW: Volume Confirmation Analysis
                vol_analysis = self._analyze_volume_profile(df)
                data.volume_confirmed = vol_analysis['breakout_ready']
                data.volume_score = vol_analysis['volume_score']
                data.has_shakeout = vol_analysis['has_shakeout']
                data.has_dryup = vol_analysis['has_dryup']
                data.breakout_ready = vol_analysis['breakout_ready']
                
                # Add volume bonus to quality
                data.pattern_quality = min(100, data.pattern_quality + vol_analysis['volume_score'] * 0.3)
                
                # Update description với volume info
                vol_desc = []
                if data.has_shakeout:
                    vol_desc.append("✓ Shakeout")
                if data.has_dryup:
                    vol_desc.append("✓ Dry-up")
                if vol_desc:
                    data.description += f" | {' | '.join(vol_desc)}"
            
        except Exception as e:
            pass
        
        return data
    
    def _analyze_volume_profile(self, df: pd.DataFrame) -> Dict:
        """
        Phân tích volume profile cho pattern theo IBD/Minervini
        
        Rules:
        1. SHAKEOUT: Volume > 1.5x avg khi rũ bỏ (giá giảm mạnh)
        2. DRY-UP: Volume < 0.6x avg gần pivot (nguồn cung cạn kiệt)
        3. VOLUME DECLINING: Volume giảm dần trong base
        4. BREAKOUT READY: Có cả Shakeout + Dry-up = sẵn sàng breakout
        
        Returns:
            Dict với các flags và volume_score
        """
        result = {
            'has_shakeout': False,
            'has_dryup': False,
            'breakout_ready': False,
            'volume_declining': False,
            'volume_score': 0
        }
        
        try:
            volumes = df['volume'].values
            closes = df['close'].values
            lows = df['low'].values
            
            n = len(volumes)
            if n < 30:
                return result
            
            avg_vol_20 = np.mean(volumes[-20:])
            avg_vol_50 = np.mean(volumes[-50:]) if n >= 50 else avg_vol_20
            
            # ═══════════════════════════════════════════════════════════════════
            # 1. CHECK SHAKEOUT (phiên rũ bỏ volume lớn trong base)
            # ═══════════════════════════════════════════════════════════════════
            # Tìm phiên có volume spike + giá giảm trong 20 ngày gần nhất
            for i in range(-20, -3):
                if volumes[i] > avg_vol_50 * 1.5:  # Volume > 150% avg
                    # Kiểm tra giá giảm mạnh trong ngày đó
                    if closes[i] < closes[i-1] * 0.98:  # Giảm > 2%
                        result['has_shakeout'] = True
                        result['volume_score'] += 20
                        break
                    # Hoặc có long tail (nến hammer)
                    elif lows[i] < closes[i] * 0.97:  # Tail > 3%
                        result['has_shakeout'] = True
                        result['volume_score'] += 15
                        break
            
            # ═══════════════════════════════════════════════════════════════════
            # 2. CHECK DRY-UP (volume cạn kiệt gần pivot)
            # ═══════════════════════════════════════════════════════════════════
            # Volume 5 ngày gần nhất phải thấp
            recent_vol_5 = np.mean(volumes[-5:])
            if recent_vol_5 < avg_vol_20 * 0.6:  # Volume < 60% avg
                result['has_dryup'] = True
                result['volume_score'] += 25
            elif recent_vol_5 < avg_vol_20 * 0.75:
                result['has_dryup'] = True
                result['volume_score'] += 15
            
            # ═══════════════════════════════════════════════════════════════════
            # 3. CHECK VOLUME DECLINING trong base
            # ═══════════════════════════════════════════════════════════════════
            vol_first_half = np.mean(volumes[-20:-10])
            vol_second_half = np.mean(volumes[-10:])
            
            if vol_second_half < vol_first_half * 0.8:  # Giảm 20%+
                result['volume_declining'] = True
                result['volume_score'] += 15
            elif vol_second_half < vol_first_half * 0.9:  # Giảm 10%
                result['volume_score'] += 8
            
            # ═══════════════════════════════════════════════════════════════════
            # 4. BREAKOUT READY = Shakeout + Dry-up
            # ═══════════════════════════════════════════════════════════════════
            if result['has_shakeout'] and result['has_dryup']:
                result['breakout_ready'] = True
                result['volume_score'] += 20  # Bonus
            
            # Cap score at 80
            result['volume_score'] = min(80, result['volume_score'])
            
        except Exception as e:
            pass
        
        return result

    
    def _detect_vcp(self, df: pd.DataFrame) -> Dict:
        """
        Phát hiện VCP (Volatility Contraction Pattern)
        
        Đặc điểm:
        - Giá tạo đỉnh, sau đó consolidate
        - Mỗi lần pullback ngắn hơn lần trước
        - Volume giảm dần
        - Thường có 3-4 lần co hẹp
        """
        result = {'detected': False}
        
        try:
            closes = df['close'].values
            highs = df['high'].values
            lows = df['low'].values
            volumes = df['volume'].values
            
            n = len(closes)
            if n < 50:
                return result
            
            # Tìm đỉnh trong 50 ngày gần nhất
            recent_high_idx = np.argmax(highs[-50:]) + (n - 50)
            recent_high = highs[recent_high_idx]
            
            # Phân tích từ đỉnh đến hiện tại
            if n - recent_high_idx < 10:
                return result  # Quá gần đỉnh
            
            # Đo các pullback
            pullbacks = []
            current_low = closes[recent_high_idx]
            
            for i in range(recent_high_idx + 5, n, 5):
                period_low = min(lows[i-5:i])
                period_high = max(highs[i-5:i])
                
                pullback_pct = (recent_high - period_low) / recent_high * 100
                pullbacks.append(pullback_pct)
            
            if len(pullbacks) < 2:
                return result
            
            # Kiểm tra co hẹp (mỗi pullback nhỏ hơn)
            contractions = 0
            for i in range(1, len(pullbacks)):
                if pullbacks[i] < pullbacks[i-1]:
                    contractions += 1
            
            # VCP cần ít nhất 2 lần co hẹp
            if contractions >= 2:
                current_pullback = (recent_high - closes[-1]) / recent_high * 100
                
                # Chất lượng pattern
                quality = min(100, 50 + contractions * 15)
                
                # Volume giảm?
                vol_recent = np.mean(volumes[-10:])
                vol_before = np.mean(volumes[recent_high_idx:recent_high_idx+10])
                if vol_recent < vol_before * 0.7:
                    quality += 15
                
                result = {
                    'detected': True,
                    'quality': quality,
                    'depth': current_pullback,
                    'length': n - recent_high_idx,
                    'contractions': contractions,
                    'buy_point': recent_high * 1.01,  # Breakout + 1%
                    'description': f'VCP với {contractions} lần co hẹp, depth {current_pullback:.1f}%'
                }
        
        except Exception as e:
            pass
        
        return result
    
    def _detect_flat_base(self, df: pd.DataFrame) -> Dict:
        """
        Phát hiện Flat Base
        
        Đặc điểm:
        - Sideway 5-7 tuần
        - Biên độ < 15%
        - Volume thấp
        """
        result = {'detected': False}
        
        try:
            closes = df['close'].values
            highs = df['high'].values
            lows = df['low'].values
            
            n = len(closes)
            if n < 30:
                return result
            
            # Kiểm tra 30 ngày gần nhất
            period_high = max(highs[-30:])
            period_low = min(lows[-30:])
            
            range_pct = (period_high - period_low) / period_low * 100
            
            # Flat base: range < 15%
            if range_pct <= 15:
                current_price = closes[-1]
                
                quality = 70 if range_pct <= 10 else 50
                
                result = {
                    'detected': True,
                    'quality': quality,
                    'depth': range_pct,
                    'length': 30,
                    'contractions': 0,
                    'buy_point': period_high * 1.01,
                    'description': f'Flat Base, biên độ {range_pct:.1f}% trong 30 ngày'
                }
        
        except Exception as e:
            pass
        
        return result
    
    def _detect_cup_handle(self, df: pd.DataFrame) -> Dict:
        """
        Phát hiện Cup & Handle
        
        Đặc điểm:
        - Hình chữ U (cup)
        - Handle nhỏ hơn cup
        - Depth 12-35%
        """
        result = {'detected': False}
        
        try:
            closes = df['close'].values
            n = len(closes)
            
            if n < 60:
                return result
            
            # Tìm đỉnh trái
            left_peak_idx = np.argmax(closes[:30])
            left_peak = closes[left_peak_idx]
            
            # Tìm đáy cup
            cup_bottom_idx = np.argmin(closes[left_peak_idx:left_peak_idx+40]) + left_peak_idx
            cup_bottom = closes[cup_bottom_idx]
            
            # Depth
            depth = (left_peak - cup_bottom) / left_peak * 100
            
            # Cup depth 12-35%
            if 12 <= depth <= 35:
                # Kiểm tra đỉnh phải (recovery)
                right_side = closes[cup_bottom_idx:]
                if len(right_side) >= 10:
                    right_high = max(right_side)
                    
                    # Recovery ít nhất 80% của cup
                    recovery = (right_high - cup_bottom) / (left_peak - cup_bottom) * 100
                    
                    if recovery >= 80:
                        quality = 60 + min(30, recovery - 80)
                        
                        result = {
                            'detected': True,
                            'quality': quality,
                            'depth': depth,
                            'length': n - left_peak_idx,
                            'contractions': 0,
                            'buy_point': left_peak * 1.01,
                            'description': f'Cup & Handle, depth {depth:.1f}%, recovery {recovery:.0f}%'
                        }
        
        except Exception as e:
            pass
        
        return result
    
    def score(self, data: PatternData) -> float:
        """Tính điểm pattern (0-100)"""
        if data.pattern_type == PatternType.NONE:
            return 30  # Base score for no pattern
        
        score = data.pattern_quality
        
        # Bonus for specific patterns
        if data.pattern_type == PatternType.VCP:
            score += 10  # VCP is high quality
        elif data.pattern_type == PatternType.CUP_HANDLE:
            score += 5
        
        # Near buy point bonus
        if -5 <= data.current_vs_buy_point <= 3:
            score += 15  # Trong vùng mua
        elif data.current_vs_buy_point > 3:
            score -= 10  # Đã vượt buy point
        
        return min(100, max(0, score))


# ══════════════════════════════════════════════════════════════════════════════
# NEWS COLLECTOR (Tích hợp vnstock_news)
# ══════════════════════════════════════════════════════════════════════════════

class StockNewsCollector:
    """Thu thập tin tức cho cổ phiếu - sử dụng vnstock_news hoặc fallback"""
    
    def __init__(self, config: ScreenerConfig):
        self.config = config
        self.crawler = None
        self.use_fallback = False
        self._init_crawler()
    
    def _init_crawler(self):
        """Khởi tạo news crawler"""
        # Thử import nest_asyncio để fix async loop issue
        try:
            import nest_asyncio
            nest_asyncio.apply()
            print("   ✓ nest_asyncio applied")
        except ImportError:
            print("   ⚠️ nest_asyncio không có - có thể gặp vấn đề với async")
        
        try:
            from vnstock_news import EnhancedNewsCrawler
            self.crawler = EnhancedNewsCrawler(
                cache_enabled=True,
                cache_ttl=3600,
                max_concurrency=2
            )
            print("   ✓ News crawler (vnstock_news) initialized")
        except ImportError as e:
            print(f"   ⚠️ vnstock_news không khả dụng: {e}")
            print("   → Sử dụng fallback news fetcher (requests)")
            self.use_fallback = True
            self.crawler = None
    
    def fetch_stock_news(self, symbol: str, max_articles: int = 5) -> StockNews:
        """Fetch tin tức cho một mã cổ phiếu"""
        news = StockNews()
        
        # Cách 1: Thử dùng vnstock API (company.news) - LUÔN THỬ TRƯỚC
        try:
            news = self._fetch_with_vnstock_news(symbol, max_articles)
            if news.articles:
                return news
        except Exception as e:
            pass  # Silent fail, try fallback
        
        # Cách 2: Fallback - dùng requests để fetch từ web
        news = self._fetch_with_requests(symbol, max_articles)
        
        return news
    
    def _fetch_with_vnstock_news(self, symbol: str, max_articles: int = 5) -> StockNews:
        """Fetch news using Vnstock company news (Synchronous)"""
        news = StockNews()
        
        try:
            from vnstock import Vnstock
            from datetime import datetime
            
            # Use VCI source
            stock = Vnstock().stock(symbol=symbol, source='VCI')
            df = stock.company.news()
            
            articles = []
            if df is not None and not df.empty:
                for _, row in df.iterrows():
                    title = row.get('news_title', '')
                    url = row.get('news_source_link', '')
                    
                    # Convert timestamp
                    pub_date = row.get('public_date')
                    time_str = ""
                    if pub_date:
                        try:
                            dt = datetime.fromtimestamp(pub_date / 1000)
                            time_str = dt.strftime('%d/%m/%Y')
                        except:
                            pass
                            
                    articles.append({
                        'title': title,
                        'description': row.get('news_short_content', ''),
                        'source': 'Vnstock',
                        'url': url,
                        'time': time_str
                    })
            
            news.articles = articles[:max_articles]
            
            # Analyze sentiment
            if articles:
                all_text = " ".join([a.get('title', '') for a in articles])
                news.sentiment, news.sentiment_score = self.analyze_sentiment(all_text)
                news.key_topics = self._extract_topics(all_text)
                
        except Exception as e:
            print(f"   ⚠️ Lỗi fetch news (vnstock): {e}")
            
        return news
    
    def _fetch_with_requests(self, symbol: str, max_articles: int = 5) -> StockNews:
        """Fallback: Fetch news using requests (synchronous)"""
        news = StockNews()
        
        try:
            import requests
            from urllib.parse import quote
            
            articles = []
            
            # Source 1: CafeF
            try:
                url = f"https://cafef.vn/tim-kiem.chn?q={quote(symbol)}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    # Simple parsing - tìm title trong HTML
                    import re
                    titles = re.findall(r'<h3[^>]*>.*?<a[^>]*>([^<]+)</a>', response.text, re.DOTALL)
                    
                    for title in titles[:max_articles]:
                        title = title.strip()
                        if symbol.upper() in title.upper() and len(title) > 20:
                            articles.append({
                                'title': title[:200],
                                'description': '',
                                'source': 'cafef',
                                'url': url,
                                'time': ''
                            })
            except Exception as e:
                pass
            
            # Source 2: VietStock
            try:
                url = f"https://vietstock.vn/tim-kiem.htm?q={quote(symbol)}"
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    import re
                    titles = re.findall(r'<h[23][^>]*>.*?<a[^>]*>([^<]+)</a>', response.text, re.DOTALL)
                    
                    for title in titles[:max_articles]:
                        title = title.strip()
                        if symbol.upper() in title.upper() and len(title) > 20:
                            articles.append({
                                'title': title[:200],
                                'description': '',
                                'source': 'vietstock',
                                'url': url,
                                'time': ''
                            })
            except Exception as e:
                pass
            
            # Source 3: Google News RSS (backup)
            if len(articles) < 2:
                try:
                    from xml.etree import ElementTree
                    url = f"https://news.google.com/rss/search?q={quote(symbol + ' chứng khoán')}&hl=vi&gl=VN"
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        root = ElementTree.fromstring(response.content)
                        items = root.findall('.//item')
                        
                        for item in items[:max_articles]:
                            title_el = item.find('title')
                            if title_el is not None:
                                title = title_el.text or ''
                                if len(title) > 20:
                                    articles.append({
                                        'title': title[:200],
                                        'description': '',
                                        'source': 'google_news',
                                        'url': '',
                                        'time': ''
                                    })
                except Exception as e:
                    pass
            
            # Remove duplicates
            seen_titles = set()
            unique_articles = []
            for a in articles:
                title_lower = a['title'].lower()[:50]
                if title_lower not in seen_titles:
                    seen_titles.add(title_lower)
                    unique_articles.append(a)
            
            news.articles = unique_articles[:5]
            
            # Analyze sentiment
            if news.articles:
                all_text = " ".join([a.get('title', '') + " " + a.get('description', '') for a in news.articles])
                news.sentiment, news.sentiment_score = self.analyze_sentiment(all_text)
                news.key_topics = self._extract_topics(all_text)
            
        except Exception as e:
            print(f"   ⚠️ Lỗi fetch news (requests) {symbol}: {e}")
        
        return news
    
    def _extract_topics(self, text: str) -> List[str]:
        """Trích xuất topics từ text"""
        topics = []
        keywords = {
            'kết quả kinh doanh': ['lợi nhuận', 'doanh thu', 'kết quả', 'quý', 'năm'],
            'cổ tức': ['cổ tức', 'chia tiền', 'trả cổ tức'],
            'phát hành': ['phát hành', 'tăng vốn', 'cổ phiếu mới'],
            'M&A': ['mua lại', 'sáp nhập', 'm&a', 'thâu tóm'],
            'thị trường': ['vnindex', 'thị trường', 'giao dịch'],
            'dự án': ['dự án', 'đầu tư', 'khởi công', 'triển khai']
        }
        
        text_lower = text.lower()
        for topic, kws in keywords.items():
            for kw in kws:
                if kw in text_lower:
                    topics.append(topic)
                    break
        
        return topics[:3]
    
    def analyze_sentiment(self, text: str) -> Tuple[str, float]:
        """Phân tích sentiment từ text"""
        positive_words = ['tăng', 'lãi', 'tích cực', 'đột phá', 'kỷ lục', 'tăng trưởng',
                         'lạc quan', 'vượt kỳ vọng', 'khả quan', 'bứt phá', 'cơ hội']
        negative_words = ['giảm', 'lỗ', 'tiêu cực', 'sụt', 'rủi ro', 'lo ngại', 'bi quan',
                         'thua lỗ', 'suy yếu', 'khó khăn', 'cảnh báo', 'thất bại']
        
        text_lower = text.lower()
        pos_count = sum(1 for w in positive_words if w in text_lower)
        neg_count = sum(1 for w in negative_words if w in text_lower)
        
        total = pos_count + neg_count
        if total == 0:
            return "neutral", 0.0
        
        score = (pos_count - neg_count) / total
        
        if score > 0.2:
            return "positive", score
        elif score < -0.2:
            return "negative", score
        else:
            return "neutral", score
    
    def score(self, news: StockNews) -> float:
        """Tính điểm news (0-100)"""
        base_score = 50  # Neutral
        
        # Có tin = tốt (attention)
        if len(news.articles) > 0:
            base_score += 5
        
        # Sentiment adjustment
        if news.sentiment == "positive":
            base_score += news.sentiment_score * 35
        elif news.sentiment == "negative":
            base_score += news.sentiment_score * 35  # Will be negative
        
        # Key topics bonus
        good_topics = ['kết quả kinh doanh', 'cổ tức', 'dự án']
        for topic in news.key_topics:
            if topic in good_topics:
                base_score += 5
        
        return min(100, max(0, base_score))
    
    def format_for_ai(self, news: StockNews) -> str:
        """Format news để gửi cho AI"""
        if not news.articles:
            return "Không có tin tức đáng chú ý trong 7 ngày qua."
        
        articles_str = "\n".join([
            f"- {a.get('title', '')[:80]}... ({a.get('source', '')})"
            for a in news.articles[:3]
        ])
        
        return f"""
📰 TIN TỨC GẦN ĐÂY ({len(news.articles)} bài):
{articles_str}

Sentiment: {news.sentiment.upper()} ({news.sentiment_score:+.2f})
Topics: {', '.join(news.key_topics) if news.key_topics else 'N/A'}
"""


# ══════════════════════════════════════════════════════════════════════════════
# AI ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class StockAIAnalyzer:
    """Phân tích AI cho từng cổ phiếu với Buy Point và Trading Plan cụ thể"""
    
    SYSTEM_PROMPT = """Bạn là chuyên gia phân tích cổ phiếu theo phương pháp CANSLIM của William O'Neil.
Phong cách: Ngắn gọn, data-driven, có action items CỤ THỂ với CON SỐ RÕ RÀNG.

BẮT BUỘC đưa ra:
1. Buy Point (Pivot Point): Mức giá cụ thể để mua vào
2. Buy Zone: Phạm vi giá chấp nhận được để mua (Buy Point đến +5%)
3. Stop Loss: Mức cắt lỗ cụ thể (thường -7% từ Buy Point)
4. Target Price: Mục tiêu chốt lời (+20% đến +25% từ Buy Point)
5. Trigger Conditions: Điều kiện KẾT HỢIC để xác nhận breakout (Volume >1.4x, RSI, etc.)

Trả lời bằng tiếng Việt với định dạng rõ ràng."""
    
    def __init__(self, config: ScreenerConfig):
        self.config = config
        self.ai = self._init_ai()
    
    def _init_ai(self):
        if not self.config.AI_API_KEY or not HAS_AI:
            return None
        try:
            return AIProvider(AIConfig(
                provider=self.config.AI_PROVIDER,
                api_key=self.config.AI_API_KEY,
                max_tokens=self.config.AI_MAX_TOKENS,
                system_prompt=self.SYSTEM_PROMPT
            ))
        except:
            return None
    
    def _format_news_for_prompt(self, news: StockNews) -> str:
        """Format news data cho AI prompt"""
        if not news.articles:
            return "📰 NEWS: Không có tin tức đáng chú ý trong 7 ngày qua."
        
        articles_str = "\n".join([
            f"   - {a.get('title', '')[:80]}... ({a.get('source', '')})"
            for a in news.articles[:3]
        ])
        
        return f"""📰 NEWS ({len(news.articles)} bài gần đây):
{articles_str}
   Sentiment: {news.sentiment.upper()} ({news.sentiment_score:+.2f})
   Topics: {', '.join(news.key_topics) if news.key_topics else 'N/A'}"""
    
    def analyze_candidate(self, candidate: StockCandidate) -> str:
        """Phân tích một candidate với Trading Plan chi tiết"""
        if not self.ai:
            return ""
        
        # Calculate trading levels
        price = candidate.technical.price
        buy_point = candidate.pattern.buy_point if candidate.pattern.buy_point > 0 else price * 1.02
        buy_zone_max = buy_point * 1.05  # +5% từ buy point
        stop_loss = buy_point * 0.93  # -7% từ buy point
        target_20 = buy_point * 1.20  # +20%
        target_25 = buy_point * 1.25  # +25%
        
        prompt = f"""
PHÂN TÍCH CỔ PHIẾU: {candidate.symbol} - {candidate.name}
Ngành: {candidate.sector_name}

⚡ CONTEXT: Cổ phiếu này đã LỌT TOP {candidate.rank} trong CANSLIM Screening với tổng điểm {candidate.score_total:.0f}/100.
Signal hiện tại: {candidate.signal.value}
→ Đây là cổ phiếu ĐÃ ĐƯỢC LỌC KỸ. Ưu tiên khuyến nghị BUY với điều kiện cụ thể (buy zone, entry trigger).
→ Chỉ khuyến nghị WATCH nếu giá quá extended (>15% trên buy point) VÀ RSI > 80.
→ Chỉ khuyến nghị AVOID nếu có red flags NGHIÊM TRỌNG (Altman Z < 1.81, OCF/Profit < -0.5, fraud risk).

📊 SCORES:
- Fundamental: {candidate.score_fundamental:.0f}/100
- Technical: {candidate.score_technical:.0f}/100
- Pattern: {candidate.score_pattern:.0f}/100
- Cash Flow Quality: {candidate.fundamental.cash_flow_quality_score:.0f}/100
- TOTAL: {candidate.score_total:.0f}/100

💹 FUNDAMENTAL & QUALITY:
- EPS Q/Q: {candidate.fundamental.eps_growth_qoq:+.1f}% | Y/Y: {candidate.fundamental.eps_growth_yoy:+.1f}%
- Revenue Q/Q: {candidate.fundamental.revenue_growth_qoq:+.1f}%
- ROE: {candidate.fundamental.roe:.1f}% | ROA: {candidate.fundamental.roa:.1f}%
- OCF/Profit Ratio: {candidate.fundamental.ocf_to_profit_ratio:.2f}
- Cash Flow Status: {candidate.fundamental.cash_flow_warning if candidate.fundamental.cash_flow_warning else "Healthy"}

📈 TECHNICAL DATA:
- Giá hiện tại: {price:,.0f}
- RS Rating: {candidate.technical.rs_rating}
- RSI(14): {candidate.technical.rsi_14:.0f}
- MA20: {candidate.technical.ma20:,.0f} | MA50: {candidate.technical.ma50:,.0f}
- Vị trí MA: {"Giá TRÊN MA20" if candidate.technical.above_ma20 else "Giá DƯỚI MA20"}, {"TRÊN MA50" if candidate.technical.above_ma50 else "DƯỚI MA50"}
- Distance from 52w High: {candidate.technical.distance_from_high:.1f}%
- Volume Ratio: {candidate.technical.volume_ratio:.2f}x
- Foreign Trade (Session): Buy {candidate.technical.foreign_buy_value/1e6:.1f}M, Sell {candidate.technical.foreign_sell_value/1e6:.1f}M, Net {candidate.technical.foreign_net_value/1e6:+.1f}M VND

📐 PATTERN DETECTED:
- Type: {candidate.pattern.pattern_type.value}
- Quality: {candidate.pattern.pattern_quality:.0f}/100
- Base Depth: {candidate.pattern.base_depth:.1f}%
- Pattern Buy Point: {candidate.pattern.buy_point:,.0f}

{self._format_news_for_prompt(candidate.news)}

═════════════════════════════════════════════════════════════
### 0. ĐÁNH GIÁ CHẤT LƯỢNG LỢI NHUẬN (Earnings Quality)
*Dựa trên sự tương quan giữa Lợi nhuận và Dòng tiền HĐKD (OCF/Profit Ratio). Phân tích xem lợi nhuận có thực chất không hay chỉ là hạch toán tài chính.*

### 1. ĐIỂM MẠNH / YẾU (Bao gồm đánh giá dòng tiền Khối ngoại)
*Liệt kê 2-3 điểm mỗi loại*

### 2. HÀNH ĐỘNG: BUY / WATCH / AVOID
*Ưu tiên BUY nếu đã lọt top CANSLIM. Chỉ WATCH nếu giá quá extended (>15% trên buy point VÀ RSI>80). Chỉ AVOID nếu red flags nghiêm trọng. Giải thích lý do.*

### 3. KỊCH BẢN GIAO DỊCH (NẾU BUY)

Đưa ra CON SỐ CỤ THỂ dựa trên dữ liệu trên:

*   **🎯 BUY POINT (Pivot):** [Giá cụ thể breakout từ pattern ~{buy_point:,.0f}]
*   **🛒 BUY ZONE:** [Phạm vi giá mua hợp lý ~{buy_point:,.0f} - {buy_zone_max:,.0f}]
*   **🛑 STOP LOSS:** [Cắt lỗ nếu thủng ~{stop_loss:,.0f} hoặc -7% từ giá mua]
*   **💰 TARGET PRICE:** [Mục tiêu 1: ~{target_20:,.0f} (+20%) | Mục tiêu 2: ~{target_25:,.0f} (+25%)]

### 4. TRIGGER CONDITIONS (Điều kiện xác nhận Breakout)

*Liệt kê ≥3 điều kiện phải thỏa mãn để mua:*
1. Volume phiên breakout > ... x trung bình 20 phiên
2. RSI nằm trong vùng ...
3. [Thêm điều kiện khác nếu cần]
"""
        
        try:
            response = self.ai.chat(prompt)
            return response  # May be None if AI failed
        except Exception as e:
            print(f"⚠️ AI analyze_candidate error: {e}")
            return None

    def generate_report_summary(self, report: ScreenerReport, history_context: str = "") -> str:
        """Tạo tóm tắt cho toàn bộ report với Trading Plan cụ thể"""
        if not self.ai:
            return ""
        
        # Build candidates summary with trading levels
        candidates_str = ""
        for c in report.top_picks[:10]:
            price = c.technical.price
            buy_point = c.pattern.buy_point if c.pattern.buy_point > 0 else price * 1.02
            stop_loss = buy_point * 0.93
            target = buy_point * 1.20
            
            candidates_str += f"""
{c.rank}. **{c.symbol}** ({c.sector_name})
   - Score: {c.score_total:.0f} | RS: {c.technical.rs_rating} | Pattern: {c.pattern.pattern_type.value}
   - Giá: {price:,.0f} | Buy Point: {buy_point:,.0f} | Stop: {stop_loss:,.0f} | Target: {target:,.0f}
   - Khối ngoại (Net): {c.technical.foreign_net_value/1e6:+.1f}M VND (Mua {c.technical.foreign_buy_value/1e6:.1f}M, Bán {c.technical.foreign_sell_value/1e6:.1f}M)
   - Signal: {c.signal.value}
"""
        
        prompt = f"""
BÁO CÁO STOCK SCREENING - {report.timestamp.strftime('%d/%m/%Y')}

{history_context}

📋 CONTEXT:
- Market Traffic Light: {report.market_context.get('traffic_light', 'N/A')}
- Distribution Days: {report.market_context.get('distribution_days', 'N/A')}
- Target Sectors: {', '.join(report.target_sectors)}

📊 SCREENING STATS:
- Total Scanned: {report.total_scanned}
- Passed Fundamental: {report.passed_fundamental}
- Passed Technical: {report.passed_technical}
- Final Candidates: {len(report.candidates)}

🏆 TOP PICKS (với Trading Levels):
{candidates_str}

═══════════════════════════════════════════════════════════════
YÊU CẦU PHÂN TÍCH TỔNG HỢP (BẮT BUỘC đưa ra CON SỐ CỤ THỂ):

### 1. ĐÁNH GIÁ TỔNG QUAN & THEO DÕI DANH MỤC (PORTFOLIO TRACKING)
- **SO SÁNH VỚI PHIÊN LATEST:** Thị trường và danh mục đã thay đổi thế nào từ phiên gần nhất?
- **STATUS UPDATE:** Đối với các mã đã khuyến nghị ở phiên trước (trong Historical Context), hãy đưa ra trạng thái cụ thể: **[TIẾP TỤC NẮM GIỮ / CHỐT LỜI / CẮT LỖ / MUA THÊM]**. 
- Nếu có mã mới lọt vào Top Picks, giải thích tại sao nó vượt trội hơn các mã cũ.

### 2. TOP 3 MÃ NÊN ƯU TIÊN (Phân tích chi tiết Dòng tiền & Trading Plan)

**CẢNH BÁO QUAN TRỌNG:** Bạn CHỈ ĐƯỢC PHÉP chọn 3 mã từ danh sách **TOP PICKS** bên trên để phân tích chi tiết. Tuyệt đối KHÔNG chọn các mã từ Historical Context nếu chúng không nằm trong Top Picks của phiên này.

Với MỖI mã trong TOP 3, đưa ra:
*   **Lý do chọn & Ảnh hưởng Khối ngoại:** [Phân tích 2-3 điểm, đặc biệt đánh giá việc Khối ngoại mua/bán ròng có ủng hộ xu hướng không]
*   **Plan:**
    *   Buy Zone: [Giá cụ thể]
    *   Stop loss: [Giá cụ thể hoặc % từ giá mua]
    *   Target: [Giá cụ thể hoặc % từ giá mua]

### 3. RISK WARNING (CẢNH BÁO RỦI RO)
*Liệt kê 2-3 rủi ro chính cần lưu ý*

### 4. KHUYẾN NGHỊ HÀNH ĐỘNG
*   Tỷ trọng: ...% NAV nên deploy
*   Chiến thuật: [Mua ngay/Chờ pullback/Chờ breakout xác nhận]
*   Watchlist: [Mã nào nên theo dõi thêm]
"""
        
        try:
            response = self.ai.chat(prompt)
            return response  # May be None if AI failed
        except Exception as e:
            print(f"⚠️ AI generate_report_summary error: {e}")
            return None

    def critique_screener(self, report: ScreenerReport, peer_analysis: str) -> str:
        """
        [NEW] Claude critique Gemini's Stock Selection
        """
        if not self.ai:
            return "⚠️ AI Reviewer not available."
            
        # Build prompt
        candidates_str = ""
        for c in report.top_picks[:10]:
            price = c.technical.price
            buy_point = c.pattern.buy_point if c.pattern.buy_point > 0 else price * 1.02
            
            candidates_str += f"""
{c.rank}. **{c.symbol}** ({c.sector_name})
   - Score: {c.score_total:.0f} | RS: {c.technical.rs_rating} | Pattern: {c.pattern.pattern_type.value}
   - Giá: {price:,.0f} | Buy Point: {buy_point:,.0f}
   - EPS Growth Y/Y: {c.fundamental.eps_growth_yoy:+.1f}% | ROE: {c.fundamental.roe:.1f}%
   - Net Foreign: {c.technical.foreign_net_value/1e6:+.1f}M VND
"""

        debate_prompt = f"""
Bạn là Senior Portfolio Manager. Dưới đây là danh sách Top Picks từ Analyst (Junior).

DỮ LIỆU TOP PICKS (FACT):
{candidates_str}

PHÂN TÍCH CỦA ANALYST (OPINION):
```
{peer_analysis}
```

NHIỆM VỤ CỦA BẠN (SENIOR REVIEW):
1. **Selection Review**: Analyst chọn mã có hợp lý không? Có mã nào rủi ro cao (RS yếu, Fundamental kém) mà Analyst bỏ qua?
2. **Trading Plan Check**: Buy Point/Stop Loss của Analyst có sát thực tế không?
3. **Consensus**: Bạn đồng ý 'All-in' mã nào? Hoặc từ chối mã nào?
4. **Final Top 3**: Đưa ra Top 3 của RIÊNG BẠN (có thể trùng hoặc khác, giải thích ngắn gọn).

VIẾT NGẮN GỌN, SÚC TÍCH.
"""
        return self.ai.chat(debate_prompt)
    
    def risk_review(self, report, gemini_analysis: str, claude_critique: str) -> str:
        """
        [NEW] DeepSeek Risk Manager - Challenge both stock pick analyses
        Focus: Position sizing risk, stop loss validity, fundamental red flags
        """
        if not self.ai:
            return "⚠️ AI Risk Manager not available."
        
        # Build top picks summary
        top_picks_str = ""
        if hasattr(report, 'top_picks') and report.top_picks:
            for i, pick in enumerate(report.top_picks[:5], 1):
                symbol = pick.get('symbol', pick) if isinstance(pick, dict) else str(pick)
                top_picks_str += f"{i}. {symbol}\n"
        else:
            top_picks_str = "Không có Top Picks rõ ràng"
        
        prompt = f"""
Bạn là CHIEF RISK OFFICER với 25 năm kinh nghiệm quản lý rủi ro trên thị trường chứng khoán Việt Nam.
Bạn vừa nhận được 2 báo cáo lựa chọn cổ phiếu từ team:

NHIỆM VỤ CỦA BẠN (Critical):
⚠️ BẠN ĐƯỢC THƯỞNG KHI TÌM RA RỦI RO MÀ CẢ 2 ANALYST ĐÃ BỎ SÓT.
⚠️ NẾU CẢ 2 ĐỒNG Ý VỚI NHAU → Tìm lý do họ có thể CÙNG SAI.

═══════════════════════════════════════════════════════════════
TOP PICKS HIỆN TẠI:
{top_picks_str}
═══════════════════════════════════════════════════════════════

PHÂN TÍCH CỦA JUNIOR ANALYST (Gemini):
```
{gemini_analysis[:2500]}
```

PHẢN BIỆN CỦA SENIOR REVIEWER (Claude):
```
{claude_critique[:2500]}
```
═══════════════════════════════════════════════════════════════

HÃY VIẾT BÁO CÁO RỦI RO CỔ PHIẾU (STOCK RISK REPORT):
Format:
### ⚠️ Stock Pick Risk Manager Review

**1. MÃ CÓ RỦI RO CAO NHẤT:**
| Mã | Rủi ro | Mức độ | Lý do cả 2 analyst bỏ qua |
|----|--------|--------|---------------------------|
| ...| ...    | 🔴/🟡  | ...                       |

**2. POSITION SIZING CONCERNS:**
- Mã nào không nên vượt quá 5% NAV?
- Mã nào cần cắt giảm size so với recommendations?

**3. STOP LOSS VALIDATION:**
- Trading plan nào có SL quá chặt/lỏng?
- Đề xuất điều chỉnh cụ thể

**4. FUNDAMENTAL RED FLAGS:**
- Mã nào có EPS âm nhưng vẫn được recommend?
- Mã nào có Cash Flow Warning?

**5. FINAL RISK-ADJUSTED PICKS:**
| Rank | Mã | Max Size | Entry | Stop | Confidence |
|------|----|----------|-------|------|------------|
| 1    | ...| 15%      | ...   | ...  | HIGH/MED/LOW|

**6. CONSENSUS RECOMMENDATION:**
- Điều gì cả 3 đều đồng ý?
- Điều gì cần cân nhắc thêm?
"""
        return self.ai.chat(prompt)
    
    def ai_select_top_stocks(self, candidates: List[StockCandidate], 
                             market_context: Dict = None,
                             history_context: str = "",
                             top_n: int = 10) -> List[Dict]:
        """
        Full AI Selection: AI phân tích tất cả candidates và tự chọn Top N, có tính đến lịch sử
        """
        # [BẮT BUỘC] Trả về duy nhất một mã JSON array.
        # [BẮT BUỘC] PHẢI ƯU TIÊN tính liên tục: Nếu các mã trong Historical Context vẫn duy trì setup tốt, hãy giữ lại chúng. Chỉ thay thế bằng mã mới nếu mã mới vượt trội rõ rệt.
        # Định dạng: [{"symbol": "AAA", "score": 95, "rank": 1, "reason": "Lý do ngắn gọn..."}, ...]
        if not self.ai:
            print("   ⚠️ AI not available for selection")
            return []
        
        if not candidates:
            return []
        
        print(f"\n🤖 AI SELECTION: Phân tích {len(candidates)} candidates...")
        
        # Build candidate data for AI
        candidates_data = ""
        for c in candidates:
            price = c.technical.price
            news_sentiment = c.news.sentiment if c.news else 'N/A'
            news_score = c.news.sentiment_score if c.news and hasattr(c.news, 'sentiment_score') else 0.0
            candidates_data += f"""
---
**{c.symbol}** ({c.sector_name})
- Giá: {price:,.0f} | RS Rating: {c.technical.rs_rating}
- RSI: {c.technical.rsi_14:.1f} | Volume Ratio: {c.technical.volume_ratio:.2f}x
- MA Alignment: {'✅ Above MA20/50/200' if (c.technical.above_ma20 and c.technical.above_ma50 and c.technical.above_ma200) else '❌ Not aligned'}
- Pattern: {c.pattern.pattern_type.value} (Quality: {c.pattern.pattern_quality:.0f})
- Volume Confirmed: {'✅' if c.pattern.volume_confirmed else '⭕'}
- Fundamental: ROE={c.fundamental.roe:.1f}%, EPS Q/Q={c.fundamental.eps_growth_qoq:+.1f}%, EPS Y/Y={c.fundamental.eps_growth_yoy:+.1f}%
- EPS 3Y CAGR: {c.fundamental.eps_growth_3y:+.1f}%
- Foreign Trade (Net): {c.technical.foreign_net_value/1e6:+.1f}M VND (B/S: {c.technical.foreign_buy_value/1e6:.1f}M/{c.technical.foreign_sell_value/1e6:.1f}M)
- News Sentiment: {news_sentiment} ({news_score:+.2f})
"""

        market_info = ""
        if market_context:
            market_info = f"""
📊 MARKET CONTEXT:
- Market Color: {market_context.get('market_color', 'N/A')}
- Market Score: {market_context.get('market_score', 'N/A')}/100
- Distribution Days: {market_context.get('distribution_days', 'N/A')}
- Leading Sectors: {market_context.get('leading_sectors', 'N/A')}
"""
        
        prompt = f"""
Bạn là chuyên gia phân tích cổ phiếu CANSLIM/IBD với kinh nghiệm 20+ năm.

{market_info}

{history_context}

---
DANH SÁCH ỨNG VIÊN (Candidates List):
{candidates_data}

═══════════════════════════════════════════════════════════════
YÊU CẦU: Phân tích và CHỌN TOP {top_n} cổ phiếu TỐT NHẤT để đầu tư ngay.

TIÊU CHÍ ƯU TIÊN (theo thứ tự):
1. **RS Rating cao** (≥80 là tốt nhất) - Leader trong ngành
2. **Pattern chất lượng** với Volume Confirmed - Sẵn sàng breakout
3. **Fundamental growth** - EPS tăng trưởng tốt
4. **MA Alignment** - Cấu trúc giá healthy
5. **Market phù hợp** - Sector đang leading

TRẢ VỀ DƯỚI DẠNG JSON (CHỈ JSON, KHÔNG GHI GÌ KHÁC):
**CẢNH BÁO:** Bạn CHỈ ĐƯỢC CHỌN các mã nằm trong "DANH SÁCH ỨNG VIÊN" bên trên. Tuyệt đối KHÔNG chọn mã từ Historical Context nếu mã đó không xuất hiện trong danh sách ứng viên mới nhất.
```json
{{
  "top_picks": [
    {{"symbol": "XXX", "score": 85, "rank": 1, "reason": "2-3 lý do ngắn gọn"}},
    {{"symbol": "YYY", "score": 80, "rank": 2, "reason": "2-3 lý do ngắn gọn"}},
    ...
  ],
  "avoid_list": ["AAA", "BBB"],
  "avoid_reason": "Lý do các mã nên tránh"
}}
```
"""
        
        try:
            response = self.ai.chat(prompt)
            
            # Parse JSON from response
            import json
            import re
            
            # Extract JSON from markdown code block if present
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    print(f"   ⚠️ Could not parse AI response as JSON")
                    return []
            
            result = json.loads(json_str)
            picks = result.get('top_picks', [])
            
            # Validate and clean picks
            valid_picks = []
            candidate_symbols = {c.symbol for c in candidates}
            
            for p in picks:
                symbol = p.get('symbol', '').upper().strip()
                # Handle cases where AI might return "1. VCB" or similar
                if ' ' in symbol:
                    symbol = symbol.split()[-1]
                if '.' in symbol:
                    symbol = symbol.split('.')[-1]
                symbol = re.sub(r'[^A-Z0-9]', '', symbol)
                
                if symbol in candidate_symbols:
                    p['symbol'] = symbol
                    valid_picks.append(p)
                else:
                    print(f"   ⚠️ AI selected {symbol} which is NOT in current candidate list. Skipping.")
            
            print(f"   ✅ AI selected {len(valid_picks)} valid stocks")
            for p in valid_picks[:5]:
                print(f"      {p.get('rank')}. {p.get('symbol')} (Score: {p.get('score')}) - {p.get('reason', '')[:50]}...")
            
            return valid_picks
            
        except json.JSONDecodeError as e:
            print(f"   ⚠️ JSON parse error: {e}")
            return []
        except Exception as e:
            print(f"   ❌ AI Selection Error: {e}")
            return []


# ══════════════════════════════════════════════════════════════════════════════
# MAIN SCREENER
# ══════════════════════════════════════════════════════════════════════════════

class StockScreener:
    """
    Stock Screener chính
    
    Flow:
    1. Nhận danh sách ngành mạnh từ Module 2
    2. Lấy danh sách mã trong các ngành đó
    3. Screen qua Fundamental → Technical → Pattern
    4. Thu thập News
    5. Tính Composite Score
    6. AI Analysis
    7. Output Watchlist
    """
    
    def __init__(self, config: ScreenerConfig = None):
        self.config = config or create_config_from_unified()
        
        self.fundamental_analyzer = FundamentalAnalyzer(self.config)
        self.technical_analyzer = TechnicalAnalyzer(self.config)
        self.pattern_detector = PatternDetector(self.config)
        self.news_collector = StockNewsCollector(self.config)
        self.ai_analyzer = StockAIAnalyzer(self.config)
        
        self.collector = get_data_collector(enable_volume_profile=True)
    
    def screen(self, 
               target_sectors: List[str],
               market_context: Optional[Dict] = None,
               history_context: str = "",
               news_hub=None) -> ScreenerReport:
        """
        Chạy screening

        Args:
            target_sectors: List mã ngành (e.g., ['VNREAL', 'VNFIN'])
            market_context: Context từ Module 1 & 2
            history_context: Context lịch sử từ HistoryManager
            news_hub: Optional NewsHub instance for RSS-based sentiment scoring
        """
        print("\n" + "="*70)
        print("📊 MODULE 3: STOCK SCREENER")
        print("="*70)
        
        report = ScreenerReport()
        report.target_sectors = target_sectors
        report.market_context = market_context or {}
        
        # Get stocks from target sectors (Deduplicate, prioritize stronger sector)
        stocks_to_scan = []
        seen_symbols = set()

        for sector in target_sectors:
            # Dùng dynamic stock list từ Stock Universe (với fallback về SECTOR_STOCKS)
            sector_stocks = get_sector_stocks_dynamic(sector, min_volume=self.config.MIN_VOLUME_AVG)
            for symbol in sector_stocks:
                if symbol not in seen_symbols:
                    stocks_to_scan.append((symbol, sector))
                    seen_symbols.add(symbol)
        
        report.total_scanned = len(stocks_to_scan)
        print(f"\n📋 Sectors: {', '.join(target_sectors)}")
        print(f"📊 Total stocks to scan: {report.total_scanned}")
        
        # Step 1: Collect all technical data (for RS Rating calculation)
        print("\n[1/5] Thu thập dữ liệu kỹ thuật...")
        all_technical = {}
        
        for i, (symbol, sector) in enumerate(stocks_to_scan):
            print(f"   [{i+1}/{len(stocks_to_scan)}] {symbol}...", end=" ", flush=True)
            
            try:
                tech_data = self.technical_analyzer.analyze(symbol)
                all_technical[symbol] = tech_data
                print(f"✓ RS_raw={tech_data.rs_raw:+.1f}")
            except Exception as e:
                print(f"✗ {e}")
            
            time.sleep(self.config.API_DELAY)
        
        # Calculate RS Rating (percentile ranking)
        print("\n[2/5] Tính RS Rating...")
        rs_values = [(s, d.rs_raw) for s, d in all_technical.items() if d.rs_raw != 0]
        if rs_values:
            rs_values.sort(key=lambda x: x[1])
            n = len(rs_values)
            for i, (symbol, _) in enumerate(rs_values):
                percentile = int((i / (n - 1)) * 98 + 1) if n > 1 else 50
                all_technical[symbol].rs_rating = percentile
        
        # Step 2: Screen and analyze
        print("\n[3/5] Phân tích fundamental + pattern...")
        candidates = []
        
        for symbol, sector in stocks_to_scan:
            tech_data = all_technical.get(symbol)
            if not tech_data or tech_data.price == 0:
                continue
            
            print(f"   {symbol}...", end=" ", flush=True)
            
            # Technical filter
            if tech_data.rs_rating < self.config.MIN_RS_RATING:
                print(f"✗ RS={tech_data.rs_rating} < {self.config.MIN_RS_RATING}")
                continue
            
            report.passed_technical += 1
            
            # Fundamental analysis
            fund_data = self.fundamental_analyzer.analyze(symbol)
            
            # Pattern detection
            pattern_data = self.pattern_detector.detect(symbol)
            
            # Create candidate
            candidate = StockCandidate(
                symbol=symbol,
                sector_code=sector,
                sector_name=SECTOR_NAMES.get(sector, sector),
                fundamental=fund_data,
                technical=tech_data,
                pattern=pattern_data,
            )
            
            # Calculate scores
            candidate.score_fundamental = self.fundamental_analyzer.score(fund_data)
            candidate.score_technical = self.technical_analyzer.score(tech_data)
            candidate.score_pattern = self.pattern_detector.score(pattern_data)
            
            # News analysis (nếu enabled)
            if self.config.ENABLE_NEWS and self.news_collector.crawler:
                news_data = self.news_collector.fetch_stock_news(symbol, max_articles=5)
                candidate.news = news_data
                candidate.score_news = self.news_collector.score(news_data)
                if news_data.articles:
                    print(f"   📰 News: {len(news_data.articles)} bài, sentiment={news_data.sentiment}")
            else:
                candidate.score_news = 50  # Neutral default

            # Total score
            candidate.score_total = (
                candidate.score_fundamental * self.config.WEIGHT_FUNDAMENTAL +
                candidate.score_technical * self.config.WEIGHT_TECHNICAL +
                candidate.score_pattern * self.config.WEIGHT_PATTERN +
                candidate.score_news * self.config.WEIGHT_NEWS
            )

            # News Hub bonus: apply RSS sentiment on top of weighted score
            if news_hub:
                try:
                    hub_result = news_hub.analyze_symbol(symbol)
                    hub_sentiment = hub_result.get("sentiment_score", 0.0)
                    if hub_sentiment >= 0.5:
                        candidate.score_total += 3
                        print(f"   📰 NewsHub +3 (sentiment={hub_sentiment:+.2f})")
                    elif hub_sentiment <= -0.5:
                        candidate.score_total -= 5
                        print(f"   📰 NewsHub -5 (sentiment={hub_sentiment:+.2f})")
                except Exception:
                    pass
            
            # Determine signal
            candidate.signal = self._determine_signal(candidate)
            
            candidates.append(candidate)
            print(f"✓ Score={candidate.score_total:.0f} | {candidate.signal.value}")
            
            time.sleep(self.config.API_DELAY)
        
        # Sort by total score (initial algorithm ranking)
        candidates.sort(key=lambda x: x.score_total, reverse=True)
        
        # Assign initial ranks
        for i, c in enumerate(candidates, 1):
            c.rank = i
        
        report.candidates = candidates
        
        # === AI SELECTION (Full AI Mode) ===
        if self.config.USE_AI_SELECTION and self.ai_analyzer.ai:
            print("\n[3.5/5] 🤖 FULL AI SELECTION...")
            ai_picks = self.ai_analyzer.ai_select_top_stocks(
                candidates, 
                market_context=market_context,
                history_context=history_context,
                top_n=self.config.TOP_PICKS_COUNT
            )
            
            if ai_picks:
                # Reorder candidates based on AI selection
                ai_ranked = []
                symbol_to_candidate = {c.symbol: c for c in candidates}
                
                for i, pick in enumerate(ai_picks):
                    symbol = pick.get('symbol')
                    if symbol and symbol in symbol_to_candidate:
                        c = symbol_to_candidate[symbol]
                        c.rank = i + 1
                        c.score_total = pick.get('score', c.score_total)  # Use AI score
                        c.ai_analysis = pick.get('reason', '')
                        # Recalculate signal based on new score
                        c.signal = self._determine_signal(c)
                        ai_ranked.append(c)
                
                report.top_picks = ai_ranked[:self.config.TOP_PICKS_COUNT]
                print(f"   ✅ AI đã chọn {len(report.top_picks)} stocks")
            else:
                # Fallback to algorithm ranking
                print("   ⚠️ AI selection failed, using algorithm ranking")
                report.top_picks = candidates[:self.config.TOP_PICKS_COUNT]
        else:
            # Traditional algorithm ranking
            report.top_picks = candidates[:self.config.TOP_PICKS_COUNT]
        
        # Step 4: AI Analysis for top picks
        print("\n[4/5] AI Analysis cho top picks...")
        if self.ai_analyzer.ai:
            for candidate in report.top_picks[:5]:
                print(f"   🤖 {candidate.symbol}...")
                candidate.ai_analysis = self.ai_analyzer.analyze_candidate(candidate) or ""

        # Step 5: Generate report summary
        print("\n[5/5] Tạo báo cáo tổng hợp...")
        report.ai_analysis = self.ai_analyzer.generate_report_summary(report, history_context) or ""
        
        return report
    
    def _determine_signal(self, candidate: StockCandidate) -> SignalStrength:
        """Xác định signal strength"""
        score = candidate.score_total
        
        if score >= 80:
            return SignalStrength.STRONG_BUY
        elif score >= 65:
            return SignalStrength.BUY
        elif score >= 50:
            return SignalStrength.WATCH
        elif score >= 35:
            return SignalStrength.NEUTRAL
        else:
            return SignalStrength.AVOID


# ══════════════════════════════════════════════════════════════════════════════
# REPORT EXPORTER
# ══════════════════════════════════════════════════════════════════════════════

class ScreenerExporter:
    """Export báo cáo screening"""
    
    def __init__(self, config: ScreenerConfig):
        self.config = config
    
    def _format_news_section(self, news: StockNews) -> str:
        """Format news section cho Markdown"""
        if not news or not news.articles:
            return "**📰 News:** Không có tin tức đáng chú ý trong 7 ngày qua."
        
        articles_str = "\n".join([
            f"  - {a.get('title', '')[:80]}... ({a.get('source', '')})"
            for a in news.articles[:3]
        ])
        
        sentiment_emoji = "🟢" if news.sentiment == "positive" else "🔴" if news.sentiment == "negative" else "🟡"
        
        return f"""**📰 News ({len(news.articles)} bài):**
{articles_str}
- Sentiment: {sentiment_emoji} {news.sentiment.upper()} ({news.sentiment_score:+.2f})
- Topics: {', '.join(news.key_topics) if news.key_topics else 'N/A'}"""
    
    def to_dict(self, report: ScreenerReport) -> Dict:
        """Convert to dictionary"""
        return {
            'timestamp': report.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'context': {
                'target_sectors': report.target_sectors,
                'market': report.market_context,
            },
            'stats': {
                'total_scanned': report.total_scanned,
                'passed_technical': report.passed_technical,
                'final_candidates': len(report.candidates),
            },
            'candidates': [
                {
                    'rank': c.rank,
                    'symbol': c.symbol,
                    'sector': c.sector_name,
                    'scores': {
                        'fundamental': c.score_fundamental,
                        'technical': c.score_technical,
                        'pattern': c.score_pattern,
                        'news': c.score_news,
                        'total': c.score_total,
                    },
                    'signal': c.signal.value,
                    'technical': {
                        'price': c.technical.price,
                        'rs_rating': c.technical.rs_rating,
                        'rsi': c.technical.rsi_14,
                        'above_ma50': c.technical.above_ma50,
                        'distance_from_high': c.technical.distance_from_high,
                    },
                    'pattern': {
                        'type': c.pattern.pattern_type.value,
                        'quality': c.pattern.pattern_quality,
                        'buy_point': c.pattern.buy_point,
                    },
                    'ai_analysis': c.ai_analysis[:500] if c.ai_analysis else '',
                }
                for c in report.candidates
            ],
            'ai_summary': report.ai_analysis,
        }
    
    def to_json(self, report: ScreenerReport, indent: int = 2) -> str:
        """Export JSON"""
        return json.dumps(self.to_dict(report), indent=indent, ensure_ascii=False, default=str)
    
    def to_markdown(self, report: ScreenerReport) -> str:
        """Export Markdown"""
        
        # Top picks table
        picks_rows = ""
        for c in report.top_picks:
            picks_rows += f"| {c.rank} | {c.symbol} | {c.sector_name} | {c.score_total:.0f} | {c.technical.rs_rating} | {c.pattern.pattern_type.value} | {c.signal.value} |\n"
        
        # All candidates table  
        all_rows = ""
        for c in report.candidates[:30]:
            all_rows += f"| {c.rank} | {c.symbol} | {c.score_fundamental:.0f} | {c.score_technical:.0f} | {c.score_pattern:.0f} | {c.score_total:.0f} | {c.signal.value} |\n"
        
        content = f"""# 📊 STOCK SCREENING REPORT
**Ngày:** {report.timestamp.strftime('%d/%m/%Y %H:%M')}

---

## 📋 CONTEXT

| Metric | Value |
|--------|-------|
| **Target Sectors** | {', '.join(report.target_sectors)} |
| **Market Traffic Light** | {report.market_context.get('traffic_light', 'N/A')} |
| **Distribution Days** | {report.market_context.get('distribution_days', 'N/A')} |

---

## 📊 SCREENING STATS

| Metric | Value |
|--------|-------|
| **Total Scanned** | {report.total_scanned} |
| **Passed Technical** | {report.passed_technical} |
| **Final Candidates** | {len(report.candidates)} |

---

## 🏆 TOP PICKS

| Rank | Symbol | Sector | Score | RS | Pattern | Signal |
|------|--------|--------|-------|----| --------|--------|
{picks_rows}

---

## 📈 ALL CANDIDATES

| Rank | Symbol | Fund | Tech | Pattern | Total | Signal |
|------|--------|------|------|---------|-------|--------|
{all_rows}

---

## 🤖 AI ANALYSIS

{report.ai_analysis}

---

## 📝 TOP PICKS DETAIL

"""
        
        # Add detail for top 5 with detailed trading plan
        for c in report.top_picks[:5]:
            # Calculate trading levels
            price = c.technical.price
            buy_point = c.pattern.buy_point if c.pattern.buy_point > 0 else price * 1.02
            buy_zone_max = buy_point * 1.05
            stop_loss = buy_point * 0.93
            target_20 = buy_point * 1.20
            target_25 = buy_point * 1.25
            
            content += f"""
### {c.rank}. {c.symbol} - {c.sector_name}

**Scores:** Fundamental {c.score_fundamental:.0f} | Technical {c.score_technical:.0f} | Pattern {c.score_pattern:.0f} | **Total: {c.score_total:.0f}**

**Technical:**
- Price: {price:,.0f} | RS: {c.technical.rs_rating}
- RSI: {c.technical.rsi_14:.0f} | MA: {'✓' if c.technical.above_ma50 else '✗'} MA50
- Distance from High: {c.technical.distance_from_high:.1f}%

**Pattern:** {c.pattern.pattern_type.value} (Quality: {c.pattern.pattern_quality:.0f})
- Buy Point: {buy_point:,.0f}

{self._format_news_section(c.news)}

**Signal:** {c.signal.value}

**📈 TRADING PLAN:**
| Level | Giá | Ghi chú |
|-------|-----|---------|
| 🎯 **Buy Point** | {buy_point:,.0f} | Breakout từ pattern |
| 🛒 **Buy Zone** | {buy_point:,.0f} - {buy_zone_max:,.0f} | Mua trong vùng này |
| 🛑 **Stop Loss** | {stop_loss:,.0f} | Cắt lỗ -7% từ Buy Point |
| 💰 **Target 1** | {target_20:,.0f} | Chốt lời +20% |
| 💰 **Target 2** | {target_25:,.0f} | Chốt lời +25% |

**⚡ Trigger Conditions:**
- Volume phiên Break > 1.4x trung bình 20 phiên
- RSI trong vùng 50-70 (không quá mua)
- Giá đóng cửa trên Buy Point {buy_point:,.0f}

**AI Analysis:**
{c.ai_analysis if c.ai_analysis else 'N/A'}

---
"""
        
        return content
    
    def save(self, report: ScreenerReport):
        """Save reports"""
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        timestamp = report.timestamp.strftime('%Y%m%d_%H%M')
        
        # Markdown
        md_file = os.path.join(self.config.OUTPUT_DIR, f"stock_screening_{timestamp}.md")
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(self.to_markdown(report))
        print(f"✓ Saved: {md_file}")
        
        # JSON
        if self.config.SAVE_JSON:
            json_file = os.path.join(self.config.OUTPUT_DIR, f"stock_screening_{timestamp}.json")
            with open(json_file, 'w', encoding='utf-8') as f:
                f.write(self.to_json(report))
            print(f"✓ Saved: {json_file}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MODULE
# ══════════════════════════════════════════════════════════════════════════════

class StockScreenerModule:
    """Module 3: Stock Screener"""

    def __init__(self, config: ScreenerConfig = None):
        self.config = config or create_config_from_unified()
        self.screener = StockScreener(self.config)
        self.exporter = ScreenerExporter(self.config)
        self.report: ScreenerReport = None

        # Recommendation History Tracker
        self.rec_tracker = get_recommendation_tracker() if HAS_REC_TRACKER else None
    
    def run(self,
            target_sectors: List[str] = None,
            market_context: Optional[Dict] = None,
            history_context: str = "",
            memo=None,
            news_hub=None) -> ScreenerReport:
        """
        Chạy module

        Args:
            target_sectors: List mã ngành để scan
            market_context: Context từ Module 1 & 2
            history_context: Context lịch sử
            memo: ContextMemo instance for inter-module sharing
            news_hub: Optional NewsHub instance for RSS sentiment scoring
        """
        print("""
╔══════════════════════════════════════════════════════════════╗
║     MODULE 3: STOCK SCREENER                                 ║
║     CANSLIM + Technical + Pattern + News                     ║
╚══════════════════════════════════════════════════════════════╝
        """)

        # Adjust thresholds based on context memo
        if memo:
            self._adjust_thresholds_by_context(memo)

        # Default sectors if not provided
        if not target_sectors:
            target_sectors = ['VNREAL', 'VNFIN']  # Default

        # Screen
        self.report = self.screener.screen(target_sectors, market_context, history_context, news_hub=news_hub)

        # Save screener summary to memo
        if memo:
            self._save_to_memo(memo)

        # Print summary
        self._print_summary()

        # Save
        if self.config.SAVE_REPORT:
            self.exporter.save(self.report)

        # Track recommendations for backtesting
        self._track_recommendations()

        # Restore thresholds to avoid mutation leak on repeated calls
        self._restore_thresholds()

        return self.report

    def _adjust_thresholds_by_context(self, memo) -> None:
        """Adjust screening thresholds based on market color from memo.

        Saves original values and restores them via _restore_thresholds().
        """
        try:
            m1_ctx = memo.read("module1")
            if not m1_ctx:
                return

            market_color = m1_ctx.get("market_color", "")
            market_score = m1_ctx.get("market_score", 50)

            # Detect color from Vietnamese text (e.g., "🔴 ĐỎ", "🟢 XANH")
            color_upper = market_color.upper()
            if "ĐỎ" in color_upper or "RED" in color_upper:
                color = "RED"
            elif "XANH" in color_upper or "GREEN" in color_upper:
                color = "GREEN"
            else:
                color = "YELLOW"

            # Save originals for restoration
            self._orig_rs = self.config.MIN_RS_RATING
            self._orig_vol = self.config.MIN_VOLUME_AVG

            if color == "RED":
                self.config.MIN_RS_RATING = 70
                self.config.MIN_VOLUME_AVG = max(self._orig_vol, 150000)
            elif color == "GREEN":
                self.config.MIN_RS_RATING = 40
                self.config.MIN_VOLUME_AVG = min(self._orig_vol, 100000)
            else:  # YELLOW
                self.config.MIN_RS_RATING = 55
                self.config.MIN_VOLUME_AVG = max(self._orig_vol, 120000)

            # Also update the screener's config reference
            self.screener.config = self.config

            print(f"✓ Thresholds adjusted for {color} market (score={market_score}): "
                  f"RS {self._orig_rs}→{self.config.MIN_RS_RATING}, "
                  f"Vol {self._orig_vol}→{self.config.MIN_VOLUME_AVG}")
        except Exception as e:
            print(f"[WARN] Threshold adjustment failed: {e}")

    def _restore_thresholds(self) -> None:
        """Restore config thresholds to originals after run."""
        if hasattr(self, "_orig_rs"):
            self.config.MIN_RS_RATING = self._orig_rs
            self.config.MIN_VOLUME_AVG = self._orig_vol
            self.screener.config = self.config

    def _save_to_memo(self, memo) -> None:
        """Save screener summary to memo for report generation."""
        try:
            rpt = self.report
            if not rpt:
                return
            picks_summary = []
            for c in (rpt.top_picks or [])[:10]:
                picks_summary.append({
                    "symbol": c.symbol,
                    "score": c.score_total,
                    "signal": c.signal.value if hasattr(c.signal, "value") else str(c.signal),
                    "rs_rating": getattr(c.technical, "rs_rating", 0),
                })
            memo.save("module3", {
                "total_scanned": rpt.total_scanned,
                "passed_technical": rpt.passed_technical,
                "top_picks_count": len(rpt.top_picks or []),
                "top_picks": picks_summary,
            })
            print("✓ Module3 context saved to memo")
        except Exception as e:
            print(f"[WARN] Module3 memo save failed: {e}")

    def _track_recommendations(self):
        """Save recommendations to history tracker for performance tracking"""
        if not self.rec_tracker or not self.report or not self.report.top_picks:
            return

        try:
            today = datetime.now().strftime('%Y-%m-%d')

            # Get current prices for all top picks
            current_prices = {}
            for c in self.report.top_picks:
                if c.technical and c.technical.price > 0:
                    current_prices[c.symbol] = c.technical.price

            # Convert StockCandidate to simple objects with correct attributes for tracker
            picks_for_tracking = []
            for c in self.report.top_picks:
                price = c.technical.price if c.technical else 0
                buy_point = c.pattern.buy_point if c.pattern and c.pattern.buy_point > 0 else price * 1.02
                stop_loss = c.stop_loss if c.stop_loss > 0 else buy_point * 0.93
                target_price = buy_point * 1.20  # +20% target

                # Create simple namespace object for tracker
                class PickData:
                    pass

                pick = PickData()
                pick.symbol = c.symbol
                pick.sector = c.sector_name
                pick.signal = c.signal.value if c.signal else "WATCH"
                pick.pattern = c.pattern.pattern_type.value if c.pattern else "No Pattern"
                pick.score = c.score_total
                pick.rs_rating = c.technical.rs_rating if c.technical else 50
                pick.price = price
                pick.buy_point = buy_point
                pick.stop_loss = stop_loss
                pick.target_price = target_price

                picks_for_tracking.append(pick)

            # Save recommendations
            saved = self.rec_tracker.save_daily_recommendations(
                date=today,
                picks=picks_for_tracking,
                current_prices=current_prices
            )

            if saved > 0:
                print(f"✓ Tracked {saved} new recommendations for backtesting")

            # Update tracking with current prices
            stats = self.rec_tracker.update_tracking(current_prices)
            if stats.get('triggered', 0) > 0 or stats.get('stopped', 0) > 0 or stats.get('target_hit', 0) > 0:
                print(f"   Tracking: {stats['triggered']} triggered, {stats['target_hit']} target hit, {stats['stopped']} stopped")

        except Exception as e:
            print(f"   ⚠️ Recommendation tracking error: {e}")

    def run_critique(self, report: ScreenerReport, peer_analysis: str) -> str:
        """
        [NEW] Critique Mode
        """
        print(f"\n[{self.config.AI_PROVIDER.upper()}] Running Critique Mode...")
        critique = self.screener.ai_analyzer.critique_screener(report, peer_analysis)
        print(f"✓ Critique Complete ({len(critique)} chars)")
        return critique

    def run_risk_review(self, report: ScreenerReport, gemini_analysis: str, claude_critique: str) -> str:
        """
        [NEW] Chạy chế độ Risk Manager (DeepSeek)
        """
        print(f"\n[{self.config.AI_PROVIDER.upper()}] Running Risk Review Mode...")
        
        # Gọi AI để risk review
        risk_review = self.screener.ai_analyzer.risk_review(report, gemini_analysis, claude_critique)
        
        print(f"✓ Risk Review Complete ({len(risk_review)} chars)")
        return risk_review
    
    def _print_summary(self):
        """Print summary"""
        print("\n" + "="*70)
        print("📋 SCREENING SUMMARY")
        print("="*70)
        
        print(f"\n📊 Stats:")
        print(f"   Scanned: {self.report.total_scanned}")
        print(f"   Passed: {len(self.report.candidates)}")
        print(f"   Top Picks: {len(self.report.top_picks)}")
        
        print(f"\n🏆 TOP 10 CANDIDATES:")
        print(f"{'Rank':<5} {'Symbol':<8} {'Score':>6} {'RS':>4} {'Pattern':<25} {'Signal':<20}")
        print("-"*75)
        
        for c in self.report.top_picks:
            print(f"{c.rank:<5} {c.symbol:<8} {c.score_total:>5.0f} {c.technical.rs_rating:>4} "
                  f"{c.pattern.pattern_type.value:<25} {c.signal.value:<20}")
        
        if self.report.ai_analysis:
            print("\n" + "-"*70)
            print("🤖 AI SUMMARY:")
            print("-"*70)
            print(self.report.ai_analysis[:2000])
    
    def get_json(self) -> str:
        """Get JSON output"""
        if self.report:
            return self.exporter.to_json(self.report)
        return "{}"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Example usage
    
    # Market context from Module 1 & 2
    market_context = {
        'traffic_light': '🟡 VÀNG - THẬN TRỌNG',
        'distribution_days': 6,
        'market_regime': 'DISTRIBUTION',
        'leading_sectors': ['VNREAL', 'VNMAT'],
    }
    
    # Target sectors (from Module 2 - leading sectors)
    target_sectors = ['VNREAL', 'VNFIN', 'VNMAT']
    
    # Run screener
    module = StockScreenerModule()
    report = module.run(
        target_sectors=target_sectors,
        market_context=market_context
    )
    
    # Print JSON sample
    print("\n" + "="*60)
    print("📄 JSON OUTPUT SAMPLE:")
    print("="*60)
    print(module.get_json()[:1500] + "...")