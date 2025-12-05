
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
    from ai_providers import AIProvider, AIConfig
    HAS_AI = True
except ImportError:
    AIProvider = None
    HAS_AI = False

# Import News Analyzer
try:
    from news_analyzer import NewsAnalyzer, NewsConfig, NewsArticle, NewsReport
    HAS_NEWS = True
except ImportError:
    HAS_NEWS = False
    NewsAnalyzer = None


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
    eps_growth_qoq: float = 0.0      # Quarter over Quarter
    eps_growth_yoy: float = 0.0      # Year over Year
    eps_growth_3y: float = 0.0       # 3 năm CAGR
    
    revenue_ttm: float = 0.0
    revenue_growth_qoq: float = 0.0
    revenue_growth_yoy: float = 0.0
    
    roe: float = 0.0
    roa: float = 0.0
    profit_margin: float = 0.0
    
    market_cap: float = 0.0
    pe_ratio: float = 0.0
    pb_ratio: float = 0.0
    
    # CANSLIM specific
    c_score: float = 0.0  # Current EPS
    a_score: float = 0.0  # Annual EPS
    
    # Institutional
    foreign_ownership: float = 0.0
    foreign_net_buy_20d: float = 0.0


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
    """
    
    def __init__(self, config: ScreenerConfig):
        self.config = config
        self.collector = get_data_collector()
    
    def analyze(self, symbol: str) -> FundamentalData:
        """Phân tích fundamental cho một mã"""
        data = FundamentalData()
        
        try:
            # Lấy thông tin tài chính từ vnstock
            # Note: Cần implement chi tiết dựa trên API vnstock
            stock = self.collector.get_stock_data(symbol, lookback_days=30, include_vp=False)
            
            # Placeholder - trong thực tế cần lấy từ financial statements
            # Giả lập dữ liệu để test
            data.market_cap = getattr(stock, 'market_cap', 0)
            data.pe_ratio = getattr(stock, 'pe', 0)
            
            # Tính C score (Current EPS)
            data.c_score = self._calc_c_score(data)
            
            # Tính A score (Annual EPS)
            data.a_score = self._calc_a_score(data)
            
        except Exception as e:
            pass
        
        return data
    
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
        if 5 <= data.pe_ratio <= 20:
            bonus += 5
        elif data.pe_ratio > 40:
            bonus -= 5
        
        # Foreign interest
        if data.foreign_net_buy_20d > 0:
            bonus += 5
        
        return min(100, max(0, base_score + bonus))


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
    """
    
    def __init__(self, config: ScreenerConfig):
        self.config = config
        self.collector = get_data_collector(enable_volume_profile=True)
    
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
            
        except Exception as e:
            pass
        
        return data
    
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
        
        # Thử dùng vnstock_news trước
        if self.crawler and not self.use_fallback:
            news = self._fetch_with_vnstock_news(symbol, max_articles)
            if news.articles:
                return news
        
        # Fallback: dùng requests để fetch từ web
        news = self._fetch_with_requests(symbol, max_articles)
        
        return news
    
    def _fetch_with_vnstock_news(self, symbol: str, max_articles: int = 5) -> StockNews:
        """Fetch news using vnstock_news library"""
        news = StockNews()
        
        if not self.crawler:
            return news
        
        try:
            import asyncio
            import concurrent.futures
            
            # Tạo keywords từ symbol
            keywords = [symbol.upper(), symbol.lower()]
            
            # Fetch từ các nguồn
            async def fetch():
                articles = []
                for site in ['cafef', 'vietstock']:
                    try:
                        df = await self.crawler.fetch_articles_async(
                            sources=[site],
                            site_name=site,
                            max_articles=max_articles,
                            time_frame='7d',
                            clean_content=True
                        )
                        if df is not None and not df.empty:
                            for _, row in df.iterrows():
                                title = row.get('title', '')
                                desc = row.get('short_description', '')
                                
                                # Check if related to symbol
                                if symbol.upper() in title.upper() or symbol.upper() in desc.upper():
                                    articles.append({
                                        'title': title,
                                        'description': desc,
                                        'source': site,
                                        'url': row.get('url', ''),
                                        'time': str(row.get('publish_time', ''))
                                    })
                    except Exception as e:
                        print(f"   ⚠️ Error fetching from {site}: {e}")
                return articles
            
            # Run async - multiple approaches
            articles = []
            
            # Method 1: Try asyncio.run() first
            try:
                articles = asyncio.run(fetch())
            except RuntimeError as e:
                # Method 2: If loop already running, use thread pool
                if "cannot be called from a running event loop" in str(e):
                    try:
                        with concurrent.futures.ThreadPoolExecutor() as executor:
                            future = executor.submit(asyncio.run, fetch())
                            articles = future.result(timeout=30)
                    except Exception as e2:
                        print(f"   ⚠️ Thread pool failed: {e2}")
                # Method 3: Try getting existing loop
                else:
                    try:
                        loop = asyncio.get_event_loop()
                        articles = loop.run_until_complete(fetch())
                    except Exception as e3:
                        print(f"   ⚠️ Event loop failed: {e3}")
            except Exception as e:
                print(f"   ⚠️ Async error: {e}")
            
            news.articles = articles[:5]  # Limit 5 bài
            
            # Analyze sentiment
            if articles:
                all_text = " ".join([a.get('title', '') + " " + a.get('description', '') for a in articles])
                news.sentiment, news.sentiment_score = self.analyze_sentiment(all_text)
                news.key_topics = self._extract_topics(all_text)
            
        except Exception as e:
            print(f"   ⚠️ Lỗi fetch news (vnstock_news) {symbol}: {e}")
        
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

📊 SCORES:
- Fundamental: {candidate.score_fundamental:.0f}/100
- Technical: {candidate.score_technical:.0f}/100
- Pattern: {candidate.score_pattern:.0f}/100
- TOTAL: {candidate.score_total:.0f}/100

📈 TECHNICAL DATA:
- Giá hiện tại: {price:,.0f}
- RS Rating: {candidate.technical.rs_rating}
- RSI(14): {candidate.technical.rsi_14:.0f}
- MA20: {candidate.technical.ma20:,.0f} | MA50: {candidate.technical.ma50:,.0f}
- Vị trí MA: {"Giá TRÊN MA20" if candidate.technical.above_ma20 else "Giá DƯỚI MA20"}, {"TRÊN MA50" if candidate.technical.above_ma50 else "DƯỚI MA50"}
- Distance from 52w High: {candidate.technical.distance_from_high:.1f}%
- Volume Ratio: {candidate.technical.volume_ratio:.2f}x

📐 PATTERN DETECTED:
- Type: {candidate.pattern.pattern_type.value}
- Quality: {candidate.pattern.pattern_quality:.0f}/100
- Base Depth: {candidate.pattern.base_depth:.1f}%
- Pattern Buy Point: {candidate.pattern.buy_point:,.0f}

{self._format_news_for_prompt(candidate.news)}

═════════════════════════════════════════════════════════════
YÊU CẦU PHÂN TÍCH (BẮT BUỘC đưa ra CON SỐ CỤ THỂ):

### 1. ĐIỂM MẠNH / YẾU
*Liệt kê 2-3 điểm mỗi loại*

### 2. HÀNH ĐỘNG: BUY / WATCH / AVOID
*Giải thích lý do*

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
            return self.ai.chat(prompt)
        except Exception as e:
            return f"❌ Error: {e}"
    
    def generate_report_summary(self, report: ScreenerReport) -> str:
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
   - Signal: {c.signal.value}
"""
        
        prompt = f"""
BÁO CÁO STOCK SCREENING - {report.timestamp.strftime('%d/%m/%Y')}

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

### 1. ĐÁNH GIÁ TỔNG QUAN
*Chất lượng danh mục: Cao/Trung bình/Thấp? Lý do?*

### 2. TOP 3 MÃ NÊN ƯU TIÊN (Đưa ra Trading Plan CỤ THỂ)

Với MỖI mã trong TOP 3, đưa ra:
*   **Lý do chọn:** [2-3 điểm]
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
            return self.ai.chat(prompt)
        except Exception as e:
            return f"❌ Error: {e}"


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
               market_context: Optional[Dict] = None) -> ScreenerReport:
        """
        Chạy screening
        
        Args:
            target_sectors: List mã ngành (e.g., ['VNREAL', 'VNFIN'])
            market_context: Context từ Module 1 & 2
        """
        print("\n" + "="*70)
        print("📊 MODULE 3: STOCK SCREENER")
        print("="*70)
        
        report = ScreenerReport()
        report.target_sectors = target_sectors
        report.market_context = market_context or {}
        
        # Get stocks from target sectors
        stocks_to_scan = []
        for sector in target_sectors:
            sector_stocks = SECTOR_STOCKS.get(sector, [])
            for symbol in sector_stocks:
                stocks_to_scan.append((symbol, sector))
        
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
            
            # Determine signal
            candidate.signal = self._determine_signal(candidate)
            
            candidates.append(candidate)
            print(f"✓ Score={candidate.score_total:.0f} | {candidate.signal.value}")
            
            time.sleep(self.config.API_DELAY)
        
        # Sort by total score
        candidates.sort(key=lambda x: x.score_total, reverse=True)
        
        # Assign ranks
        for i, c in enumerate(candidates, 1):
            c.rank = i
        
        report.candidates = candidates
        report.top_picks = candidates[:self.config.TOP_PICKS_COUNT]
        
        # Step 4: AI Analysis for top picks
        print("\n[4/5] AI Analysis cho top picks...")
        if self.ai_analyzer.ai:
            for candidate in report.top_picks[:5]:
                print(f"   🤖 {candidate.symbol}...")
                candidate.ai_analysis = self.ai_analyzer.analyze_candidate(candidate)
        
        # Step 5: Generate report summary
        print("\n[5/5] Tạo báo cáo tổng hợp...")
        report.ai_analysis = self.ai_analyzer.generate_report_summary(report)
        
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
    
    def run(self,
            target_sectors: List[str] = None,
            market_context: Optional[Dict] = None) -> ScreenerReport:
        """
        Chạy module
        
        Args:
            target_sectors: List mã ngành để scan
            market_context: Context từ Module 1 & 2
        """
        print("""
╔══════════════════════════════════════════════════════════════╗
║     MODULE 3: STOCK SCREENER                                 ║
║     CANSLIM + Technical + Pattern + News                     ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # Default sectors if not provided
        if not target_sectors:
            target_sectors = ['VNREAL', 'VNFIN']  # Default
        
        # Screen
        self.report = self.screener.screen(target_sectors, market_context)
        
        # Print summary
        self._print_summary()
        
        # Save
        if self.config.SAVE_REPORT:
            self.exporter.save(self.report)
        
        return self.report
    
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