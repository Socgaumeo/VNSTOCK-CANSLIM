#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    MODULE 0: DATA CONTEXT LAYER                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Chuyển từ phân tích điểm (scalar) sang phân tích dòng chảy (time-series)   ║
║                                                                              ║
║  Core concept: "Ngày hôm nay không tồn tại độc lập"                         ║
║  - Mọi tín hiệu đều cần CONTEXT từ quá khứ                                  ║
║  - Vector hóa dữ liệu bằng Rolling Window                                    ║
║  - Các chỉ báo có "bộ nhớ" (Memory-based Indicators)                        ║
║                                                                              ║
║  Functions:                                                                  ║
║  - calc_trend_slope(): Độ dốc MA (Linear Regression)                        ║
║  - calc_percentile_rank(): Vị thế giá trong N ngày                          ║
║  - calc_rsi_regime(): RSI Min/Max 50 phiên                                  ║
║  - calc_macd_impulse(): MACD Histogram direction                            ║
║  - count_distribution_days(): Đếm ngày phân phối                            ║
║  - detect_follow_through_day(): Phát hiện FTD                               ║
║  - get_ma_position(): Vị trí giá vs MA20, MA50                              ║
║  - classify_market_regime(): Accumulation/Markup/Distribution/Markdown      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json
import warnings
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS & DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

class TrendStatus(Enum):
    """Trạng thái xu hướng dựa trên độ dốc"""
    STRONG_UP = "🚀 STRONG_UP"      # slope > 0.5
    UP = "📈 UP"                     # 0.1 < slope <= 0.5
    FLAT = "➡️ FLAT"                # -0.1 <= slope <= 0.1
    DOWN = "📉 DOWN"                 # -0.5 <= slope < -0.1
    STRONG_DOWN = "💥 STRONG_DOWN"  # slope < -0.5


class RSIRegime(Enum):
    """Chế độ RSI"""
    BULLISH = "🟢 BULLISH"    # RSI_Min_50 > 40
    BEARISH = "🔴 BEARISH"    # RSI_Max_50 < 60
    NEUTRAL = "🟡 NEUTRAL"    # Còn lại


class MACDImpulse(Enum):
    """MACD Impulse direction"""
    INCREASING = "▲ INCREASING"  # Histogram đang tăng
    DECREASING = "▼ DECREASING"  # Histogram đang giảm
    FLAT = "■ FLAT"              # Không đổi


class DistributionStatus(Enum):
    """Trạng thái phân phối"""
    SAFE = "🟢 SAFE"           # < 3 ngày
    WARNING = "🟡 WARNING"     # 4-5 ngày
    DANGER = "🔴 DANGER"       # > 6 ngày


class MAPosition(Enum):
    """Vị trí giá so với MA"""
    STRONG_BULLISH = "🚀 STRONG_BULLISH"  # Giá > MA20 > MA50
    BULLISH = "📈 BULLISH"                 # Giá > MA50 (nhưng < MA20)
    WEAK_BULLISH = "📊 WEAK_BULLISH"       # Giá > MA50 nhưng MA20 < MA50
    BEARISH = "📉 BEARISH"                 # Giá < MA50
    STRONG_BEARISH = "💥 STRONG_BEARISH"   # Giá < MA20 < MA50


class MarketRegime(Enum):
    """Chế độ thị trường (Wyckoff)"""
    ACCUMULATION = "🔵 ACCUMULATION"    # Tích lũy
    MARKUP = "🟢 MARKUP"                 # Tăng giá
    DISTRIBUTION = "🟠 DISTRIBUTION"    # Phân phối
    MARKDOWN = "🔴 MARKDOWN"             # Giảm giá


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES FOR CONTEXT RESULTS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TrendContext:
    """Ngữ cảnh xu hướng"""
    # MA20
    ma20_value: float = 0.0
    ma20_slope: float = 0.0
    ma20_slope_status: str = "FLAT"
    
    # MA50
    ma50_value: float = 0.0
    ma50_slope: float = 0.0
    ma50_slope_status: str = "FLAT"
    
    # MA200
    ma200_value: float = 0.0
    ma200_slope: float = 0.0
    ma200_slope_status: str = "FLAT"
    
    # MA Alignment
    ma_alignment: str = "NEUTRAL"  # BULLISH: MA20 > MA50 > MA200
    ma_alignment_note: str = ""


@dataclass
class PriceContext:
    """Ngữ cảnh vị thế giá"""
    current_price: float = 0.0
    
    # Percentile
    percentile_20d: float = 50.0
    percentile_50d: float = 50.0
    percentile_100d: float = 50.0
    
    # Status
    price_status: str = "NEUTRAL"  # VERY_EXPENSIVE, EXPENSIVE, NEUTRAL, CHEAP, VERY_CHEAP
    
    # vs MA
    ma_position: str = "NEUTRAL"
    price_vs_ma20: float = 0.0  # % distance
    price_vs_ma50: float = 0.0
    price_vs_ma200: float = 0.0


@dataclass
class RSIContext:
    """Ngữ cảnh RSI"""
    rsi_current: float = 50.0
    rsi_min_50d: float = 30.0
    rsi_max_50d: float = 70.0
    rsi_avg_50d: float = 50.0
    
    regime: str = "NEUTRAL"
    regime_note: str = ""
    
    # Overbought/Oversold
    is_overbought: bool = False
    is_oversold: bool = False


@dataclass
class MACDContext:
    """Ngữ cảnh MACD"""
    macd_line: float = 0.0
    signal_line: float = 0.0
    histogram: float = 0.0
    
    # Impulse
    impulse_direction: str = "FLAT"
    impulse_bars: int = 0  # Số nến liên tiếp theo hướng này
    
    # Signals
    histogram_positive: bool = False
    cross_signal: str = ""  # BULLISH_CROSS, BEARISH_CROSS, NONE
    
    # Trading implication
    impulse_signal: str = ""  # "Không được Short", "Không được Long mới"


@dataclass
class DistributionContext:
    """Ngữ cảnh Distribution Days"""
    count: int = 0
    dates: List[str] = field(default_factory=list)
    details: List[Dict] = field(default_factory=list)
    
    status: str = "SAFE"
    status_note: str = ""


@dataclass
class FTDContext:
    """Ngữ cảnh Follow-Through Day"""
    has_ftd: bool = False
    ftd_date: Optional[str] = None
    ftd_gain: float = 0.0
    ftd_volume_ratio: float = 0.0
    
    # Recent low info
    recent_low_date: Optional[str] = None
    recent_low_price: float = 0.0
    days_from_low: int = 0
    
    note: str = ""


@dataclass
class MarketRegimeContext:
    """Ngữ cảnh Market Regime"""
    regime: str = "NEUTRAL"
    confidence: float = 0.0
    
    signals: List[str] = field(default_factory=list)
    
    # Component scores
    trend_score: int = 0      # -2 to +2
    momentum_score: int = 0   # -2 to +2
    volume_score: int = 0     # -2 to +2
    structure_score: int = 0  # -2 to +2


@dataclass
class FullContext:
    """Tổng hợp tất cả context"""
    timestamp: str = ""
    symbol: str = ""
    
    # Sub-contexts
    trend: TrendContext = field(default_factory=TrendContext)
    price: PriceContext = field(default_factory=PriceContext)
    rsi: RSIContext = field(default_factory=RSIContext)
    macd: MACDContext = field(default_factory=MACDContext)
    distribution: DistributionContext = field(default_factory=DistributionContext)
    ftd: FTDContext = field(default_factory=FTDContext)
    regime: MarketRegimeContext = field(default_factory=MarketRegimeContext)
    
    # Summary
    overall_bias: str = "NEUTRAL"  # BULLISH, BEARISH, NEUTRAL
    key_signals: List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CLASS: DataContext
# ══════════════════════════════════════════════════════════════════════════════

class DataContext:
    """
    Data Context Layer - Vector hóa dữ liệu và tính các chỉ báo có context
    
    Usage:
        ctx = DataContext()
        result = ctx.analyze(df)  # df có columns: open, high, low, close, volume
        
        # Get specific analysis
        trend = ctx.calc_trend_context(df)
        dist = ctx.count_distribution_days(df)
        
        # Export
        json_str = ctx.to_json(result)
    """
    
    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize DataContext
        
        Args:
            config: Optional configuration dict
        """
        self.config = config or {}
        
        # Default parameters
        self.ma_short = self.config.get('ma_short', 20)
        self.ma_medium = self.config.get('ma_medium', 50)
        self.ma_long = self.config.get('ma_long', 200)
        self.rsi_period = self.config.get('rsi_period', 14)
        self.distribution_window = self.config.get('distribution_window', 25)
        self.ftd_min_day = self.config.get('ftd_min_day', 4)
        self.ftd_max_day = self.config.get('ftd_max_day', 10)
        self.ftd_min_gain = self.config.get('ftd_min_gain', 1.25)  # %
    
    # ══════════════════════════════════════════════════════════════════════════
    # 1. TREND ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    def calc_trend_slope(self, series: pd.Series, window: int = 20) -> float:
        """
        Tính độ dốc của chuỗi dữ liệu bằng Linear Regression
        
        Args:
            series: Chuỗi giá trị (thường là MA)
            window: Số phiên để tính slope
            
        Returns:
            slope: Độ dốc (đã chuẩn hóa theo giá trị trung bình)
        """
        if len(series) < window:
            return 0.0
        
        recent = series.tail(window).dropna()
        if len(recent) < window // 2:
            return 0.0
        
        x = np.arange(len(recent))
        y = recent.values
        
        try:
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
            
            # Chuẩn hóa slope theo giá trị trung bình để so sánh được
            mean_value = np.mean(y)
            if mean_value > 0:
                normalized_slope = (slope * window) / mean_value * 100  # % change over window
            else:
                normalized_slope = 0.0
                
            return round(normalized_slope, 3)
        except Exception:
            return 0.0
    
    def get_slope_status(self, slope: float) -> str:
        """
        Phân loại độ dốc thành trạng thái
        
        Args:
            slope: Độ dốc (đã chuẩn hóa, %)
            
        Returns:
            status: STRONG_UP, UP, FLAT, DOWN, STRONG_DOWN
        """
        if slope > 3.0:
            return TrendStatus.STRONG_UP.value
        elif slope > 0.5:
            return TrendStatus.UP.value
        elif slope >= -0.5:
            return TrendStatus.FLAT.value
        elif slope >= -3.0:
            return TrendStatus.DOWN.value
        else:
            return TrendStatus.STRONG_DOWN.value
    
    def calc_ma_alignment(self, ma20: float, ma50: float, ma200: float) -> Tuple[str, str]:
        """
        Xác định MA Alignment
        
        Returns:
            (alignment, note)
        """
        if ma20 > ma50 > ma200:
            return "BULLISH", "MA20 > MA50 > MA200 ✓ Perfect alignment"
        elif ma20 > ma50 and ma50 < ma200:
            return "MIXED_BULLISH", "MA20 > MA50 nhưng MA50 < MA200"
        elif ma50 > ma200:
            return "WEAK_BULLISH", "MA50 > MA200 nhưng MA20 không dẫn đầu"
        elif ma20 < ma50 < ma200:
            return "BEARISH", "MA20 < MA50 < MA200 ✗ Perfect bearish"
        elif ma50 < ma200:
            return "WEAK_BEARISH", "MA50 < MA200"
        else:
            return "NEUTRAL", "MA không có xu hướng rõ ràng"
    
    def calc_trend_context(self, df: pd.DataFrame) -> TrendContext:
        """
        Tính toàn bộ Trend Context
        
        Args:
            df: DataFrame với columns [close]
            
        Returns:
            TrendContext
        """
        ctx = TrendContext()
        
        if len(df) < self.ma_long:
            return ctx
        
        close = df['close']
        
        # Calculate MAs
        ma20 = close.rolling(self.ma_short).mean()
        ma50 = close.rolling(self.ma_medium).mean()
        ma200 = close.rolling(self.ma_long).mean()
        
        # Current values
        ctx.ma20_value = round(ma20.iloc[-1], 2) if not pd.isna(ma20.iloc[-1]) else 0
        ctx.ma50_value = round(ma50.iloc[-1], 2) if not pd.isna(ma50.iloc[-1]) else 0
        ctx.ma200_value = round(ma200.iloc[-1], 2) if not pd.isna(ma200.iloc[-1]) else 0
        
        # Calculate slopes
        ctx.ma20_slope = self.calc_trend_slope(ma20, window=10)
        ctx.ma50_slope = self.calc_trend_slope(ma50, window=20)
        ctx.ma200_slope = self.calc_trend_slope(ma200, window=50)
        
        # Slope status
        ctx.ma20_slope_status = self.get_slope_status(ctx.ma20_slope)
        ctx.ma50_slope_status = self.get_slope_status(ctx.ma50_slope)
        ctx.ma200_slope_status = self.get_slope_status(ctx.ma200_slope)
        
        # MA Alignment
        ctx.ma_alignment, ctx.ma_alignment_note = self.calc_ma_alignment(
            ctx.ma20_value, ctx.ma50_value, ctx.ma200_value
        )
        
        return ctx
    
    # ══════════════════════════════════════════════════════════════════════════
    # 2. PRICE POSITION ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    def calc_percentile_rank(self, price: float, prices: pd.Series) -> float:
        """
        Tính percentile của giá hiện tại trong phân phối N ngày
        
        Args:
            price: Giá hiện tại
            prices: Chuỗi giá
            
        Returns:
            percentile: 0-100
        """
        if len(prices) == 0:
            return 50.0
        
        count_below = (prices < price).sum()
        percentile = (count_below / len(prices)) * 100
        
        return round(percentile, 1)
    
    def get_price_status(self, percentile: float) -> str:
        """
        Phân loại vị thế giá
        """
        if percentile >= 90:
            return "VERY_EXPENSIVE"
        elif percentile >= 70:
            return "EXPENSIVE"
        elif percentile >= 30:
            return "NEUTRAL"
        elif percentile >= 10:
            return "CHEAP"
        else:
            return "VERY_CHEAP"
    
    def calc_ma_position(self, price: float, ma20: float, ma50: float, ma200: float) -> Tuple[str, str]:
        """
        Xác định vị trí giá so với các MA
        
        Returns:
            (position, note)
        """
        above_ma20 = price > ma20
        above_ma50 = price > ma50
        above_ma200 = price > ma200
        ma20_above_ma50 = ma20 > ma50
        
        if above_ma20 and above_ma50 and ma20_above_ma50:
            return MAPosition.STRONG_BULLISH.value, "Giá > MA20 > MA50 ✓ Rất mạnh"
        elif above_ma50 and above_ma20:
            return MAPosition.BULLISH.value, "Giá > MA20 và MA50"
        elif above_ma50:
            return MAPosition.WEAK_BULLISH.value, "Giá > MA50 nhưng < MA20"
        elif not above_ma50 and not above_ma20:
            if not ma20_above_ma50:
                return MAPosition.STRONG_BEARISH.value, "Giá < MA20 < MA50 ✗ Rất yếu"
            return MAPosition.BEARISH.value, "Giá < MA50"
        else:
            return "NEUTRAL", "Không xác định rõ xu hướng"
    
    def calc_price_context(self, df: pd.DataFrame) -> PriceContext:
        """
        Tính toàn bộ Price Context
        """
        ctx = PriceContext()
        
        if len(df) < 20:
            return ctx
        
        close = df['close']
        ctx.current_price = round(close.iloc[-1], 2)
        
        # MAs
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1] if len(df) >= 50 else ma20
        ma200 = close.rolling(200).mean().iloc[-1] if len(df) >= 200 else ma50
        
        # Percentiles
        ctx.percentile_20d = self.calc_percentile_rank(ctx.current_price, close.tail(20))
        ctx.percentile_50d = self.calc_percentile_rank(ctx.current_price, close.tail(50)) if len(df) >= 50 else ctx.percentile_20d
        ctx.percentile_100d = self.calc_percentile_rank(ctx.current_price, close.tail(100)) if len(df) >= 100 else ctx.percentile_50d
        
        # Price status
        ctx.price_status = self.get_price_status(ctx.percentile_50d)
        
        # MA Position
        ctx.ma_position, _ = self.calc_ma_position(ctx.current_price, ma20, ma50, ma200)
        
        # Distance from MAs (%)
        ctx.price_vs_ma20 = round((ctx.current_price / ma20 - 1) * 100, 2) if ma20 > 0 else 0
        ctx.price_vs_ma50 = round((ctx.current_price / ma50 - 1) * 100, 2) if ma50 > 0 else 0
        ctx.price_vs_ma200 = round((ctx.current_price / ma200 - 1) * 100, 2) if ma200 > 0 else 0
        
        return ctx
    
    # ══════════════════════════════════════════════════════════════════════════
    # 3. RSI REGIME ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    def calc_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """
        Tính RSI theo công thức Wilder (chuẩn)
        
        Sử dụng Wilder's Smoothed Moving Average (SMMA):
        - alpha = 1/period cho EMA tương đương SMMA
        - Đây là công thức chuẩn được sử dụng bởi hầu hết các nền tảng
        """
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = (-delta).where(delta < 0, 0)
        
        # Wilder's Smoothed Moving Average (SMMA)
        # alpha = 1/period cho EMA hoạt động như SMMA
        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calc_rsi_context(self, df: pd.DataFrame) -> RSIContext:
        """
        Tính RSI Context với Regime analysis
        """
        ctx = RSIContext()
        
        if len(df) < 50:
            return ctx
        
        close = df['close']
        rsi = self.calc_rsi(close, self.rsi_period)
        
        ctx.rsi_current = round(rsi.iloc[-1], 1) if not pd.isna(rsi.iloc[-1]) else 50
        
        # Rolling stats for regime
        rsi_50d = rsi.tail(50).dropna()
        if len(rsi_50d) > 0:
            ctx.rsi_min_50d = round(rsi_50d.min(), 1)
            ctx.rsi_max_50d = round(rsi_50d.max(), 1)
            ctx.rsi_avg_50d = round(rsi_50d.mean(), 1)
        
        # Determine regime
        if ctx.rsi_min_50d > 40:
            ctx.regime = RSIRegime.BULLISH.value
            ctx.regime_note = f"RSI_Min_50d ({ctx.rsi_min_50d}) > 40 → Đáy RSI không thủng 40, xu hướng tăng bền vững"
        elif ctx.rsi_max_50d < 60:
            ctx.regime = RSIRegime.BEARISH.value
            ctx.regime_note = f"RSI_Max_50d ({ctx.rsi_max_50d}) < 60 → Đỉnh RSI không vượt 60, xu hướng giảm"
        else:
            ctx.regime = RSIRegime.NEUTRAL.value
            ctx.regime_note = f"RSI dao động bình thường ({ctx.rsi_min_50d} - {ctx.rsi_max_50d})"
        
        # Overbought/Oversold
        ctx.is_overbought = ctx.rsi_current > 70
        ctx.is_oversold = ctx.rsi_current < 30
        
        return ctx
    
    # ══════════════════════════════════════════════════════════════════════════
    # 4. MACD IMPULSE ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    def calc_macd(self, close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """
        Tính MACD
        """
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def calc_macd_context(self, df: pd.DataFrame) -> MACDContext:
        """
        Tính MACD Context với Impulse System
        """
        ctx = MACDContext()
        
        if len(df) < 30:
            return ctx
        
        close = df['close']
        macd_line, signal_line, histogram = self.calc_macd(close)
        
        ctx.macd_line = round(macd_line.iloc[-1], 4) if not pd.isna(macd_line.iloc[-1]) else 0
        ctx.signal_line = round(signal_line.iloc[-1], 4) if not pd.isna(signal_line.iloc[-1]) else 0
        ctx.histogram = round(histogram.iloc[-1], 4) if not pd.isna(histogram.iloc[-1]) else 0
        
        ctx.histogram_positive = ctx.histogram > 0
        
        # Impulse direction - đếm số nến liên tiếp
        hist_diff = histogram.diff()
        recent_hist = hist_diff.tail(10).dropna()
        
        if len(recent_hist) > 0:
            current_direction = "INCREASING" if recent_hist.iloc[-1] > 0 else "DECREASING"
            
            # Count consecutive bars
            count = 0
            for val in reversed(recent_hist.values):
                if (current_direction == "INCREASING" and val > 0) or \
                   (current_direction == "DECREASING" and val < 0):
                    count += 1
                else:
                    break
            
            ctx.impulse_direction = MACDImpulse.INCREASING.value if current_direction == "INCREASING" else MACDImpulse.DECREASING.value
            ctx.impulse_bars = count
            
            # Trading implication
            if current_direction == "INCREASING":
                ctx.impulse_signal = "⚠️ Histogram đang tăng → Không được Short"
            else:
                ctx.impulse_signal = "⚠️ Histogram đang giảm → Không được Long mới"
        
        # Cross signal
        prev_macd = macd_line.iloc[-2] if len(macd_line) > 1 else 0
        prev_signal = signal_line.iloc[-2] if len(signal_line) > 1 else 0
        
        if prev_macd <= prev_signal and ctx.macd_line > ctx.signal_line:
            ctx.cross_signal = "🟢 BULLISH_CROSS"
        elif prev_macd >= prev_signal and ctx.macd_line < ctx.signal_line:
            ctx.cross_signal = "🔴 BEARISH_CROSS"
        else:
            ctx.cross_signal = "NONE"
        
        return ctx
    
    # ══════════════════════════════════════════════════════════════════════════
    # 5. DISTRIBUTION DAYS ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    def is_distribution_day(self, row: pd.Series, prev_row: pd.Series) -> bool:
        """
        Kiểm tra 1 ngày có phải Distribution Day không
        
        Distribution Day = Giá giảm > 0.2% VÀ Volume > hôm trước
        """
        if prev_row is None:
            return False
        
        price_change = (row['close'] - prev_row['close']) / prev_row['close'] * 100
        volume_increase = row['volume'] > prev_row['volume']
        
        return price_change < -0.2 and volume_increase
    
    def count_distribution_days(self, df: pd.DataFrame, window: int = None) -> DistributionContext:
        """
        Đếm số ngày phân phối trong N phiên gần nhất
        
        Args:
            df: DataFrame với columns [close, volume]
            window: Số phiên (mặc định 25)
            
        Returns:
            DistributionContext
        """
        ctx = DistributionContext()
        window = window or self.distribution_window
        
        if len(df) < window + 1:
            return ctx
        
        recent = df.tail(window + 1).reset_index(drop=True)
        
        for i in range(1, len(recent)):
            row = recent.iloc[i]
            prev_row = recent.iloc[i - 1]
            
            if self.is_distribution_day(row, prev_row):
                ctx.count += 1
                
                # Get date if available
                date_str = str(row.name) if hasattr(row, 'name') else f"Day-{window - i}"
                if 'time' in df.columns:
                    date_str = str(row['time'])
                
                ctx.dates.append(date_str)
                ctx.details.append({
                    'date': date_str,
                    'change': round((row['close'] - prev_row['close']) / prev_row['close'] * 100, 2),
                    'volume_ratio': round(row['volume'] / prev_row['volume'], 2)
                })
        
        # Determine status
        if ctx.count < 3:
            ctx.status = DistributionStatus.SAFE.value
            ctx.status_note = f"Chỉ {ctx.count} ngày phân phối trong {window} phiên → Thị trường khỏe"
        elif ctx.count <= 5:
            ctx.status = DistributionStatus.WARNING.value
            ctx.status_note = f"{ctx.count} ngày phân phối trong {window} phiên → Áp lực phân phối tăng"
        else:
            ctx.status = DistributionStatus.DANGER.value
            ctx.status_note = f"{ctx.count} ngày phân phối trong {window} phiên → Phân phối nặng, cẩn thận!"
        
        return ctx
    
    # ══════════════════════════════════════════════════════════════════════════
    # 6. FOLLOW-THROUGH DAY ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    def find_recent_low(self, df: pd.DataFrame, lookback: int = 20) -> Dict:
        """
        Tìm đáy gần nhất
        """
        if len(df) < lookback:
            return {'date': None, 'price': 0, 'days_ago': 0}
        
        recent = df.tail(lookback)
        low_idx = recent['close'].idxmin()
        low_price = recent.loc[low_idx, 'close']
        
        # Calculate days ago
        days_ago = len(df) - df.index.get_loc(low_idx) - 1
        
        # Get date
        date_str = str(low_idx)
        if 'time' in df.columns:
            date_str = str(recent.loc[low_idx, 'time'])
        
        return {
            'date': date_str,
            'price': round(low_price, 2),
            'days_ago': days_ago
        }
    
    def detect_follow_through_day(self, df: pd.DataFrame) -> FTDContext:
        """
        Phát hiện Follow-Through Day
        
        FTD = Ngày 4-10 từ đáy + Tăng > 1.25% + Volume > hôm trước
        """
        ctx = FTDContext()
        
        if len(df) < 15:
            return ctx
        
        # Find recent low
        low_info = self.find_recent_low(df, lookback=20)
        ctx.recent_low_date = low_info['date']
        ctx.recent_low_price = low_info['price']
        ctx.days_from_low = low_info['days_ago']
        
        # Check for FTD in the valid window (day 4-10 from low)
        if ctx.days_from_low < self.ftd_min_day:
            ctx.note = f"Mới {ctx.days_from_low} ngày từ đáy, chưa đủ điều kiện FTD (cần day 4-10)"
            return ctx
        
        # Look for FTD in the window
        start_check = max(0, len(df) - ctx.days_from_low - 1 + self.ftd_min_day)
        end_check = min(len(df) - 1, len(df) - ctx.days_from_low - 1 + self.ftd_max_day)
        
        for i in range(start_check, end_check + 1):
            if i <= 0:
                continue
                
            row = df.iloc[i]
            prev_row = df.iloc[i - 1]
            
            # Check conditions
            gain = (row['close'] - prev_row['close']) / prev_row['close'] * 100
            volume_ratio = row['volume'] / prev_row['volume'] if prev_row['volume'] > 0 else 0
            
            if gain >= self.ftd_min_gain and volume_ratio > 1:
                ctx.has_ftd = True
                
                # Get date
                if 'time' in df.columns:
                    ctx.ftd_date = str(row['time'])
                else:
                    ctx.ftd_date = f"Day {i}"
                
                ctx.ftd_gain = round(gain, 2)
                ctx.ftd_volume_ratio = round(volume_ratio, 2)
                ctx.note = f"✓ FTD detected: +{gain:.2f}% với Volume {volume_ratio:.2f}x"
                break
        
        if not ctx.has_ftd:
            ctx.note = f"Không tìm thấy FTD trong window day {self.ftd_min_day}-{self.ftd_max_day} từ đáy"
        
        return ctx
    
    # ══════════════════════════════════════════════════════════════════════════
    # 7. MARKET REGIME CLASSIFICATION
    # ══════════════════════════════════════════════════════════════════════════
    
    def classify_market_regime(self, 
                               trend_ctx: TrendContext,
                               price_ctx: PriceContext,
                               rsi_ctx: RSIContext,
                               dist_ctx: DistributionContext,
                               ftd_ctx: FTDContext) -> MarketRegimeContext:
        """
        Phân loại Market Regime dựa trên tổng hợp các context
        """
        ctx = MarketRegimeContext()
        
        # 1. Trend Score (-2 to +2)
        if "STRONG_UP" in trend_ctx.ma50_slope_status:
            ctx.trend_score = 2
            ctx.signals.append("MA50 slope rất dốc lên")
        elif "UP" in trend_ctx.ma50_slope_status:
            ctx.trend_score = 1
            ctx.signals.append("MA50 slope dốc lên")
        elif "STRONG_DOWN" in trend_ctx.ma50_slope_status:
            ctx.trend_score = -2
            ctx.signals.append("MA50 slope rất dốc xuống")
        elif "DOWN" in trend_ctx.ma50_slope_status:
            ctx.trend_score = -1
            ctx.signals.append("MA50 slope dốc xuống")
        
        # 2. Momentum Score (-2 to +2) based on RSI regime
        if "BULLISH" in rsi_ctx.regime:
            ctx.momentum_score = 2
            ctx.signals.append("RSI regime BULLISH")
        elif "BEARISH" in rsi_ctx.regime:
            ctx.momentum_score = -2
            ctx.signals.append("RSI regime BEARISH")
        
        # 3. Volume Score (-2 to +2) based on distribution
        if "SAFE" in dist_ctx.status:
            ctx.volume_score = 1
            ctx.signals.append(f"Distribution days ít ({dist_ctx.count})")
        elif "WARNING" in dist_ctx.status:
            ctx.volume_score = -1
            ctx.signals.append(f"Distribution days tăng ({dist_ctx.count})")
        elif "DANGER" in dist_ctx.status:
            ctx.volume_score = -2
            ctx.signals.append(f"Distribution days nhiều ({dist_ctx.count})")
        
        # 4. Structure Score based on MA position
        if "STRONG_BULLISH" in price_ctx.ma_position:
            ctx.structure_score = 2
            ctx.signals.append("Giá > MA20 > MA50")
        elif "BULLISH" in price_ctx.ma_position:
            ctx.structure_score = 1
            ctx.signals.append("Giá trên MA50")
        elif "STRONG_BEARISH" in price_ctx.ma_position:
            ctx.structure_score = -2
            ctx.signals.append("Giá < MA20 < MA50")
        elif "BEARISH" in price_ctx.ma_position:
            ctx.structure_score = -1
            ctx.signals.append("Giá dưới MA50")
        
        # FTD bonus
        if ftd_ctx.has_ftd:
            ctx.structure_score += 1
            ctx.signals.append("Có Follow-Through Day")
        
        # Total score
        total_score = ctx.trend_score + ctx.momentum_score + ctx.volume_score + ctx.structure_score
        ctx.confidence = min(100, max(0, (total_score + 8) / 16 * 100))  # Normalize to 0-100
        
        # Determine regime
        if total_score >= 4:
            ctx.regime = MarketRegime.MARKUP.value
        elif total_score >= 1:
            ctx.regime = MarketRegime.ACCUMULATION.value
        elif total_score >= -3:
            ctx.regime = MarketRegime.DISTRIBUTION.value
        else:
            ctx.regime = MarketRegime.MARKDOWN.value
        
        return ctx
    
    # ══════════════════════════════════════════════════════════════════════════
    # 8. AGGREGATE ANALYSIS
    # ══════════════════════════════════════════════════════════════════════════
    
    def analyze(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> FullContext:
        """
        Tổng hợp tất cả phân tích context
        
        Args:
            df: DataFrame với columns [open, high, low, close, volume]
            symbol: Mã chứng khoán
            
        Returns:
            FullContext
        """
        ctx = FullContext()
        ctx.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ctx.symbol = symbol
        
        # Normalize column names
        df.columns = df.columns.str.lower()
        
        # 1. Trend Context
        ctx.trend = self.calc_trend_context(df)
        
        # 2. Price Context
        ctx.price = self.calc_price_context(df)
        
        # 3. RSI Context
        ctx.rsi = self.calc_rsi_context(df)
        
        # 4. MACD Context
        ctx.macd = self.calc_macd_context(df)
        
        # 5. Distribution Context
        ctx.distribution = self.count_distribution_days(df)
        
        # 6. FTD Context
        ctx.ftd = self.detect_follow_through_day(df)
        
        # 7. Market Regime
        ctx.regime = self.classify_market_regime(
            ctx.trend, ctx.price, ctx.rsi, ctx.distribution, ctx.ftd
        )
        
        # 8. Overall bias
        regime_value = ctx.regime.regime
        if "MARKUP" in regime_value:
            ctx.overall_bias = "BULLISH"
        elif "MARKDOWN" in regime_value:
            ctx.overall_bias = "BEARISH"
        elif "ACCUMULATION" in regime_value:
            ctx.overall_bias = "CAUTIOUSLY_BULLISH"
        elif "DISTRIBUTION" in regime_value:
            ctx.overall_bias = "CAUTIOUSLY_BEARISH"
        else:
            ctx.overall_bias = "NEUTRAL"
        
        # Key signals
        ctx.key_signals = ctx.regime.signals[:5]  # Top 5 signals
        
        return ctx
    
    # ══════════════════════════════════════════════════════════════════════════
    # 9. EXPORT FUNCTIONS
    # ══════════════════════════════════════════════════════════════════════════
    
    def context_to_dict(self, ctx: FullContext) -> Dict:
        """
        Convert FullContext to dictionary
        """
        return {
            'timestamp': ctx.timestamp,
            'symbol': ctx.symbol,
            'trend': {
                'ma20': {
                    'value': ctx.trend.ma20_value,
                    'slope': ctx.trend.ma20_slope,
                    'status': ctx.trend.ma20_slope_status
                },
                'ma50': {
                    'value': ctx.trend.ma50_value,
                    'slope': ctx.trend.ma50_slope,
                    'status': ctx.trend.ma50_slope_status
                },
                'ma200': {
                    'value': ctx.trend.ma200_value,
                    'slope': ctx.trend.ma200_slope,
                    'status': ctx.trend.ma200_slope_status
                },
                'alignment': ctx.trend.ma_alignment,
                'alignment_note': ctx.trend.ma_alignment_note
            },
            'price': {
                'current': ctx.price.current_price,
                'percentile_50d': ctx.price.percentile_50d,
                'status': ctx.price.price_status,
                'ma_position': ctx.price.ma_position,
                'vs_ma20': ctx.price.price_vs_ma20,
                'vs_ma50': ctx.price.price_vs_ma50,
                'vs_ma200': ctx.price.price_vs_ma200
            },
            'rsi': {
                'current': ctx.rsi.rsi_current,
                'min_50d': ctx.rsi.rsi_min_50d,
                'max_50d': ctx.rsi.rsi_max_50d,
                'regime': ctx.rsi.regime,
                'note': ctx.rsi.regime_note,
                'overbought': ctx.rsi.is_overbought,
                'oversold': ctx.rsi.is_oversold
            },
            'macd': {
                'line': ctx.macd.macd_line,
                'signal': ctx.macd.signal_line,
                'histogram': ctx.macd.histogram,
                'histogram_positive': ctx.macd.histogram_positive,
                'impulse_direction': ctx.macd.impulse_direction,
                'impulse_bars': ctx.macd.impulse_bars,
                'impulse_signal': ctx.macd.impulse_signal,
                'cross': ctx.macd.cross_signal
            },
            'distribution': {
                'count': ctx.distribution.count,
                'status': ctx.distribution.status,
                'note': ctx.distribution.status_note,
                'dates': ctx.distribution.dates
            },
            'ftd': {
                'has_ftd': ctx.ftd.has_ftd,
                'date': ctx.ftd.ftd_date,
                'gain': ctx.ftd.ftd_gain,
                'volume_ratio': ctx.ftd.ftd_volume_ratio,
                'recent_low': {
                    'date': ctx.ftd.recent_low_date,
                    'price': ctx.ftd.recent_low_price,
                    'days_ago': ctx.ftd.days_from_low
                },
                'note': ctx.ftd.note
            },
            'regime': {
                'current': ctx.regime.regime,
                'confidence': ctx.regime.confidence,
                'scores': {
                    'trend': ctx.regime.trend_score,
                    'momentum': ctx.regime.momentum_score,
                    'volume': ctx.regime.volume_score,
                    'structure': ctx.regime.structure_score
                },
                'signals': ctx.regime.signals
            },
            'summary': {
                'overall_bias': ctx.overall_bias,
                'key_signals': ctx.key_signals
            }
        }
    
    def to_json(self, ctx: FullContext, indent: int = 2) -> str:
        """
        Export context thành JSON string
        """
        def convert_numpy(obj):
            """Convert numpy types to Python native types"""
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {k: convert_numpy(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy(i) for i in obj]
            return obj
        
        data = convert_numpy(self.context_to_dict(ctx))
        return json.dumps(data, indent=indent, ensure_ascii=False)
    
    def to_markdown(self, ctx: FullContext) -> str:
        """
        Export context thành Markdown
        """
        md = f"""## 📊 DATA CONTEXT - {ctx.symbol}
**Timestamp:** {ctx.timestamp}

---

### 🎯 SUMMARY
| Metric | Value |
|--------|-------|
| **Overall Bias** | {ctx.overall_bias} |
| **Market Regime** | {ctx.regime.regime} |
| **Confidence** | {ctx.regime.confidence:.0f}% |

**Key Signals:**
"""
        for signal in ctx.key_signals:
            md += f"- {signal}\n"
        
        md += f"""
---

### 📈 TREND CONTEXT

| MA | Value | Slope | Status |
|----|-------|-------|--------|
| MA20 | {ctx.trend.ma20_value:,.0f} | {ctx.trend.ma20_slope:+.2f}% | {ctx.trend.ma20_slope_status} |
| MA50 | {ctx.trend.ma50_value:,.0f} | {ctx.trend.ma50_slope:+.2f}% | {ctx.trend.ma50_slope_status} |
| MA200 | {ctx.trend.ma200_value:,.0f} | {ctx.trend.ma200_slope:+.2f}% | {ctx.trend.ma200_slope_status} |

**MA Alignment:** {ctx.trend.ma_alignment}
> {ctx.trend.ma_alignment_note}

---

### 💰 PRICE CONTEXT

| Metric | Value |
|--------|-------|
| Current Price | {ctx.price.current_price:,.0f} |
| Percentile 50D | {ctx.price.percentile_50d:.0f}% |
| Price Status | {ctx.price.price_status} |
| MA Position | {ctx.price.ma_position} |
| vs MA20 | {ctx.price.price_vs_ma20:+.2f}% |
| vs MA50 | {ctx.price.price_vs_ma50:+.2f}% |

---

### 📊 RSI REGIME

| Metric | Value |
|--------|-------|
| RSI Current | {ctx.rsi.rsi_current:.1f} |
| RSI Min 50D | {ctx.rsi.rsi_min_50d:.1f} |
| RSI Max 50D | {ctx.rsi.rsi_max_50d:.1f} |
| **Regime** | {ctx.rsi.regime} |

> {ctx.rsi.regime_note}

{"⚠️ **Overbought Warning:** RSI > 70" if ctx.rsi.is_overbought else ""}
{"⚠️ **Oversold Alert:** RSI < 30" if ctx.rsi.is_oversold else ""}

---

### 📉 MACD IMPULSE

| Metric | Value |
|--------|-------|
| MACD Line | {ctx.macd.macd_line:.4f} |
| Signal Line | {ctx.macd.signal_line:.4f} |
| Histogram | {ctx.macd.histogram:.4f} |
| Direction | {ctx.macd.impulse_direction} |
| Bars | {ctx.macd.impulse_bars} |
| Cross | {ctx.macd.cross_signal} |

> {ctx.macd.impulse_signal}

---

### 📅 DISTRIBUTION DAYS (25 phiên)

| Metric | Value |
|--------|-------|
| Count | {ctx.distribution.count} |
| Status | {ctx.distribution.status} |

> {ctx.distribution.status_note}

---

### ✨ FOLLOW-THROUGH DAY

| Metric | Value |
|--------|-------|
| Has FTD | {"✅ Yes" if ctx.ftd.has_ftd else "❌ No"} |
| FTD Date | {ctx.ftd.ftd_date or "N/A"} |
| FTD Gain | {ctx.ftd.ftd_gain:+.2f}% |
| Recent Low | {ctx.ftd.recent_low_price:,.0f} ({ctx.ftd.days_from_low} days ago) |

> {ctx.ftd.note}

---

### 🎪 MARKET REGIME

**Current Regime:** {ctx.regime.regime}

| Component | Score |
|-----------|-------|
| Trend | {ctx.regime.trend_score:+d} |
| Momentum | {ctx.regime.momentum_score:+d} |
| Volume | {ctx.regime.volume_score:+d} |
| Structure | {ctx.regime.structure_score:+d} |
| **Total** | **{sum([ctx.regime.trend_score, ctx.regime.momentum_score, ctx.regime.volume_score, ctx.regime.structure_score]):+d}** |

"""
        return md


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_data_context(config: Optional[Dict] = None) -> DataContext:
    """
    Factory function để tạo DataContext instance
    """
    return DataContext(config)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN - TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════╗
║         MODULE 0: DATA CONTEXT LAYER - TEST                   ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Test with vnstock
    try:
        from vnstock import Vnstock
        
        stock = Vnstock().stock(symbol='VNINDEX', source='VCI')
        df = stock.quote.history(start='2024-06-01', end='2025-11-27')
        
        print(f"✓ Loaded {len(df)} rows for VNINDEX")
        print(f"  Columns: {list(df.columns)}")
        print(f"  Date range: {df['time'].min()} to {df['time'].max()}")
        
        # Analyze
        ctx_analyzer = DataContext()
        result = ctx_analyzer.analyze(df, symbol='VNINDEX')
        
        # Print Markdown
        print("\n" + "="*60)
        print(ctx_analyzer.to_markdown(result))
        
        # Save JSON
        json_output = ctx_analyzer.to_json(result)
        print("\n" + "="*60)
        print("📄 JSON OUTPUT:")
        print(json_output[:2000] + "...")
        
        # Save to files
        import os
        os.makedirs('./output', exist_ok=True)
        
        with open('./output/context_test.json', 'w', encoding='utf-8') as f:
            f.write(json_output)
        print("\n✓ Saved JSON to ./output/context_test.json")
        
        with open('./output/context_test.md', 'w', encoding='utf-8') as f:
            f.write(ctx_analyzer.to_markdown(result))
        print("✓ Saved Markdown to ./output/context_test.md")
        
    except ImportError:
        print("❌ vnstock not installed. Run: pip install vnstock")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
