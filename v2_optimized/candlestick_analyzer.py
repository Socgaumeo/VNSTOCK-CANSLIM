#!/usr/bin/env python3
"""
Candlestick pattern recognition with Volume Profile zone integration.
Detects 12 key candlestick patterns and scores them based on:
- Pattern quality
- Volume confirmation
- Position relative to VP zones (POC/VAH/VAL)
- VN market specifics (ceiling/floor ±7%)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np
import pandas as pd


# VN market price limit (HOSE)
CEILING_PCT = 0.069  # +6.9% (threshold to detect near-ceiling)
FLOOR_PCT = -0.069   # -6.9%


@dataclass
class CandlestickSignal:
    """A detected candlestick pattern signal."""
    pattern_name: str
    signal_type: str       # "bullish_reversal", "bearish_reversal", "continuation"
    confidence: float      # 0-100 base confidence
    volume_confirmed: bool
    vp_zone: str           # "AT_POC", "AT_VAH", "AT_VAL", "IN_VA", "OUTSIDE"
    context_score: float   # Final score: confidence * volume_mult * vp_mult
    date: str
    description: str


class CandlestickAnalyzer:
    """
    Analyze OHLCV data for 12 key candlestick patterns.

    Usage:
        analyzer = CandlestickAnalyzer()
        signals = analyzer.analyze(df, vp_result)
    """

    def __init__(self, vp_proximity_pct: float = 0.02):
        """
        Args:
            vp_proximity_pct: How close price must be to VP level (default 2%)
        """
        self.vp_proximity_pct = vp_proximity_pct

    def analyze(
        self,
        df: pd.DataFrame,
        vp_result=None,
        lookback: int = 20,
    ) -> List[CandlestickSignal]:
        """
        Analyze recent candles for patterns.

        Args:
            df: OHLCV DataFrame (must have open, high, low, close, volume)
            vp_result: VolumeProfileResult with poc, vah, val
            lookback: Number of recent candles to analyze

        Returns:
            List of detected signals, sorted by context_score descending.
        """
        if df.empty or len(df) < 10:
            return []

        df = df.tail(max(lookback + 5, 25)).copy()
        signals = []

        o = df['open'].values
        h = df['high'].values
        lo = df['low'].values
        c = df['close'].values
        v = df['volume'].values
        vol_ma = pd.Series(v).rolling(20, min_periods=5).mean().values

        dates = self._extract_dates(df)

        # Scan recent candles (skip first few for context)
        for i in range(max(3, len(df) - lookback), len(df)):
            candle = _Candle(o[i], h[i], lo[i], c[i], v[i])
            prev = _Candle(o[i-1], h[i-1], lo[i-1], c[i-1], v[i-1]) if i > 0 else None
            prev2 = _Candle(o[i-2], h[i-2], lo[i-2], c[i-2], v[i-2]) if i > 1 else None

            vol_avg = vol_ma[i] if i < len(vol_ma) and not np.isnan(vol_ma[i]) else np.mean(v[max(0,i-20):i]) if i > 0 else v[i]
            vol_ratio = v[i] / vol_avg if vol_avg > 0 else 1.0
            vol_confirmed = vol_ratio >= 1.3

            # Recent trend context
            trend = self._calc_trend(c, i)
            date_str = dates[i] if i < len(dates) else ""

            # Detect patterns
            detectors = [
                self._detect_hammer,
                self._detect_shooting_star,
                self._detect_bullish_engulfing,
                self._detect_bearish_engulfing,
                self._detect_morning_star,
                self._detect_evening_star,
                self._detect_piercing_line,
                self._detect_dark_cloud,
                self._detect_doji,
                self._detect_spinning_top,
                self._detect_marubozu,
                self._detect_three_white_soldiers,
            ]

            for detector in detectors:
                sig = detector(candle, prev, prev2, trend)
                if sig:
                    sig.date = date_str
                    sig.volume_confirmed = vol_confirmed
                    sig.vp_zone = self._get_vp_zone(c[i], vp_result)
                    sig.context_score = self._calc_context_score(
                        sig.confidence, vol_ratio, sig.vp_zone, sig.signal_type
                    )
                    # VN ceiling/floor bonus
                    cf_bonus = self._ceiling_floor_bonus(candle, prev, c, i)
                    sig.context_score += cf_bonus
                    signals.append(sig)

        signals.sort(key=lambda s: s.context_score, reverse=True)
        return signals

    # ─────────────────────────────────────────────────────────────
    # PATTERN DETECTORS
    # ─────────────────────────────────────────────────────────────

    def _detect_hammer(self, c, prev, prev2, trend) -> Optional[CandlestickSignal]:
        """Hammer: small body, long lower shadow >= 2x body, at bottom of downtrend."""
        if trend != "down":
            return None
        body = c.body_size
        rng = c.range
        if rng == 0:
            return None
        lower_shadow = c.lower_shadow
        upper_shadow = c.upper_shadow
        if body < rng * 0.35 and lower_shadow >= 2 * body and upper_shadow < body:
            return CandlestickSignal(
                pattern_name="Hammer",
                signal_type="bullish_reversal",
                confidence=70,
                volume_confirmed=False, vp_zone="", context_score=0, date="",
                description="Nến Hammer - bóng dưới dài, thân nhỏ ở đáy downtrend"
            )
        return None

    def _detect_shooting_star(self, c, prev, prev2, trend) -> Optional[CandlestickSignal]:
        """Shooting Star: small body, long upper shadow >= 2x body, at top of uptrend."""
        if trend != "up":
            return None
        body = c.body_size
        rng = c.range
        if rng == 0:
            return None
        if body < rng * 0.35 and c.upper_shadow >= 2 * body and c.lower_shadow < body:
            return CandlestickSignal(
                pattern_name="Shooting Star",
                signal_type="bearish_reversal",
                confidence=70,
                volume_confirmed=False, vp_zone="", context_score=0, date="",
                description="Nến Shooting Star - bóng trên dài, thân nhỏ ở đỉnh uptrend"
            )
        return None

    def _detect_bullish_engulfing(self, c, prev, prev2, trend) -> Optional[CandlestickSignal]:
        """Bullish Engulfing: green candle fully engulfs previous red candle."""
        if prev is None or trend != "down":
            return None
        if not prev.is_bearish or not c.is_bullish:
            return None
        if c.open_val <= prev.close_val and c.close_val >= prev.open_val:
            conf = 75 if c.body_size > prev.body_size * 1.5 else 65
            return CandlestickSignal(
                pattern_name="Bullish Engulfing",
                signal_type="bullish_reversal",
                confidence=conf,
                volume_confirmed=False, vp_zone="", context_score=0, date="",
                description="Nến Bullish Engulfing - nến xanh bao trùm nến đỏ trước"
            )
        return None

    def _detect_bearish_engulfing(self, c, prev, prev2, trend) -> Optional[CandlestickSignal]:
        """Bearish Engulfing: red candle fully engulfs previous green candle."""
        if prev is None or trend != "up":
            return None
        if not prev.is_bullish or not c.is_bearish:
            return None
        if c.open_val >= prev.close_val and c.close_val <= prev.open_val:
            conf = 75 if c.body_size > prev.body_size * 1.5 else 65
            return CandlestickSignal(
                pattern_name="Bearish Engulfing",
                signal_type="bearish_reversal",
                confidence=conf,
                volume_confirmed=False, vp_zone="", context_score=0, date="",
                description="Nến Bearish Engulfing - nến đỏ bao trùm nến xanh trước"
            )
        return None

    def _detect_morning_star(self, c, prev, prev2, trend) -> Optional[CandlestickSignal]:
        """Morning Star: 3 candles - long red + small body + long green."""
        if prev is None or prev2 is None or trend != "down":
            return None
        if not prev2.is_bearish:
            return None
        if prev.body_size > prev2.body_size * 0.4:
            return None
        if not c.is_bullish or c.body_size < prev2.body_size * 0.5:
            return None
        if c.close_val > (prev2.open_val + prev2.close_val) / 2:
            return CandlestickSignal(
                pattern_name="Morning Star",
                signal_type="bullish_reversal",
                confidence=80,
                volume_confirmed=False, vp_zone="", context_score=0, date="",
                description="Morning Star - 3 nến: đỏ dài + thân nhỏ + xanh dài"
            )
        return None

    def _detect_evening_star(self, c, prev, prev2, trend) -> Optional[CandlestickSignal]:
        """Evening Star: 3 candles - long green + small body + long red."""
        if prev is None or prev2 is None or trend != "up":
            return None
        if not prev2.is_bullish:
            return None
        if prev.body_size > prev2.body_size * 0.4:
            return None
        if not c.is_bearish or c.body_size < prev2.body_size * 0.5:
            return None
        if c.close_val < (prev2.open_val + prev2.close_val) / 2:
            return CandlestickSignal(
                pattern_name="Evening Star",
                signal_type="bearish_reversal",
                confidence=80,
                volume_confirmed=False, vp_zone="", context_score=0, date="",
                description="Evening Star - 3 nến: xanh dài + thân nhỏ + đỏ dài"
            )
        return None

    def _detect_piercing_line(self, c, prev, prev2, trend) -> Optional[CandlestickSignal]:
        """Piercing Line: green candle opens below prev close, closes above 50% of prev body."""
        if prev is None or trend != "down":
            return None
        if not prev.is_bearish or not c.is_bullish:
            return None
        mid = (prev.open_val + prev.close_val) / 2
        if c.open_val < prev.close_val and c.close_val > mid:
            return CandlestickSignal(
                pattern_name="Piercing Line",
                signal_type="bullish_reversal",
                confidence=65,
                volume_confirmed=False, vp_zone="", context_score=0, date="",
                description="Piercing Line - mở gap down, đóng trên 50% thân nến đỏ trước"
            )
        return None

    def _detect_dark_cloud(self, c, prev, prev2, trend) -> Optional[CandlestickSignal]:
        """Dark Cloud Cover: red candle opens above prev close, closes below 50% of prev body."""
        if prev is None or trend != "up":
            return None
        if not prev.is_bullish or not c.is_bearish:
            return None
        mid = (prev.open_val + prev.close_val) / 2
        if c.open_val > prev.close_val and c.close_val < mid:
            return CandlestickSignal(
                pattern_name="Dark Cloud Cover",
                signal_type="bearish_reversal",
                confidence=65,
                volume_confirmed=False, vp_zone="", context_score=0, date="",
                description="Dark Cloud Cover - mở gap up, đóng dưới 50% thân nến xanh trước"
            )
        return None

    def _detect_doji(self, c, prev, prev2, trend) -> Optional[CandlestickSignal]:
        """Doji: very small body (open ~ close)."""
        if c.range == 0:
            return None
        if c.body_size / c.range > 0.1:
            return None
        sig_type = "bearish_reversal" if trend == "up" else ("bullish_reversal" if trend == "down" else "continuation")
        return CandlestickSignal(
            pattern_name="Doji",
            signal_type=sig_type,
            confidence=50,
            volume_confirmed=False, vp_zone="", context_score=0, date="",
            description="Doji - thân rất nhỏ, lực mua/bán cân bằng"
        )

    def _detect_spinning_top(self, c, prev, prev2, trend) -> Optional[CandlestickSignal]:
        """Spinning Top: small body with roughly equal shadows."""
        if c.range == 0:
            return None
        body_ratio = c.body_size / c.range
        if 0.1 < body_ratio < 0.35:
            shadow_diff = abs(c.upper_shadow - c.lower_shadow)
            if shadow_diff < c.range * 0.3:
                return CandlestickSignal(
                    pattern_name="Spinning Top",
                    signal_type="continuation",
                    confidence=40,
                    volume_confirmed=False, vp_zone="", context_score=0, date="",
                    description="Spinning Top - thân nhỏ, bóng cân đối, lực cân bằng"
                )
        return None

    def _detect_marubozu(self, c, prev, prev2, trend) -> Optional[CandlestickSignal]:
        """Marubozu: large body with no/tiny shadows."""
        if c.range == 0:
            return None
        body_ratio = c.body_size / c.range
        if body_ratio < 0.85:
            return None
        sig_type = "continuation"
        if c.is_bullish:
            desc = "Bullish Marubozu - thân dài không bóng, momentum tăng mạnh"
        else:
            desc = "Bearish Marubozu - thân dài không bóng, momentum giảm mạnh"
        return CandlestickSignal(
            pattern_name="Marubozu",
            signal_type=sig_type,
            confidence=60,
            volume_confirmed=False, vp_zone="", context_score=0, date="",
            description=desc,
        )

    def _detect_three_white_soldiers(self, c, prev, prev2, trend) -> Optional[CandlestickSignal]:
        """Three White Soldiers: 3 consecutive bullish candles, each closing higher."""
        if prev is None or prev2 is None:
            return None
        if not (c.is_bullish and prev.is_bullish and prev2.is_bullish):
            return None
        if c.close_val > prev.close_val > prev2.close_val:
            if c.open_val > prev.open_val > prev2.open_val:
                return CandlestickSignal(
                    pattern_name="Three White Soldiers",
                    signal_type="bullish_reversal",
                    confidence=75,
                    volume_confirmed=False, vp_zone="", context_score=0, date="",
                    description="Three White Soldiers - 3 nến xanh liên tiếp tăng dần"
                )
        return None

    # ─────────────────────────────────────────────────────────────
    # CONTEXT & SCORING
    # ─────────────────────────────────────────────────────────────

    def _calc_trend(self, close: np.ndarray, idx: int, period: int = 10) -> str:
        """Determine short-term trend: 'up', 'down', or 'sideways'."""
        start = max(0, idx - period)
        if idx - start < 3:
            return "sideways"
        segment = close[start:idx+1]
        change = (segment[-1] - segment[0]) / segment[0] if segment[0] != 0 else 0
        if change > 0.03:
            return "up"
        elif change < -0.03:
            return "down"
        return "sideways"

    def _get_vp_zone(self, price: float, vp_result) -> str:
        """Determine which VP zone price is in."""
        if vp_result is None or not hasattr(vp_result, 'poc') or vp_result.poc == 0:
            return "OUTSIDE"

        poc, vah, val = vp_result.poc, vp_result.vah, vp_result.val
        pct = self.vp_proximity_pct

        if abs(price - poc) / poc < pct:
            return "AT_POC"
        if abs(price - vah) / vah < pct:
            return "AT_VAH"
        if abs(price - val) / val < pct:
            return "AT_VAL"
        if val <= price <= vah:
            return "IN_VA"
        return "OUTSIDE"

    def _calc_context_score(
        self, confidence: float, vol_ratio: float, vp_zone: str, signal_type: str
    ) -> float:
        """
        Calculate context-aware score.
        context_score = confidence * volume_mult * vp_mult
        """
        # Volume multiplier
        if vol_ratio >= 2.0:
            vol_mult = 1.5
        elif vol_ratio >= 1.3:
            vol_mult = 1.3
        elif vol_ratio >= 0.8:
            vol_mult = 1.0
        else:
            vol_mult = 0.7

        # VP zone multiplier
        vp_mult_map = {
            "AT_POC": 1.5,
            "AT_VAH": 1.4 if "bearish" in signal_type else 1.2,
            "AT_VAL": 1.4 if "bullish" in signal_type else 1.2,
            "IN_VA": 1.0,
            "OUTSIDE": 0.8,
        }
        vp_mult = vp_mult_map.get(vp_zone, 1.0)

        return round(confidence * vol_mult * vp_mult / 100 * 100, 1)

    def _ceiling_floor_bonus(self, candle, prev, close, idx) -> float:
        """VN market: bonus for ceiling/floor signals."""
        if prev is None or idx < 1:
            return 0
        change = (candle.close_val - prev.close_val) / prev.close_val if prev.close_val > 0 else 0

        if change >= CEILING_PCT and candle.is_bullish:
            return 10  # Ceiling hit = strong demand
        if change <= FLOOR_PCT and candle.is_bearish:
            return 5   # Floor hit in context of bearish reversal pattern
        return 0

    def _extract_dates(self, df: pd.DataFrame) -> list:
        """Extract date strings from DataFrame index."""
        dates = []
        for idx in df.index:
            if hasattr(idx, 'strftime'):
                dates.append(idx.strftime('%Y-%m-%d'))
            else:
                dates.append(str(idx))
        return dates

    def get_top_signals(
        self, df: pd.DataFrame, vp_result=None, top_n: int = 3, recent_days: int = 5
    ) -> List[CandlestickSignal]:
        """Get top N signals from the most recent N days."""
        all_signals = self.analyze(df, vp_result, lookback=recent_days)
        return all_signals[:top_n]

    def get_candlestick_score(
        self, df: pd.DataFrame, vp_result=None, recent_days: int = 5
    ) -> float:
        """
        Get a single candlestick score (0-30) for integration into PatternDetector.
        Uses the best signal from recent days.
        """
        signals = self.get_top_signals(df, vp_result, top_n=1, recent_days=recent_days)
        if not signals:
            return 0
        best = signals[0]
        # Scale context_score to 0-30 range
        return min(30, best.context_score * 0.3)


class _Candle:
    """Helper class for candle properties."""

    __slots__ = ('open_val', 'high_val', 'low_val', 'close_val', 'volume')

    def __init__(self, o, h, lo, c, v):
        self.open_val = float(o)
        self.high_val = float(h)
        self.low_val = float(lo)
        self.close_val = float(c)
        self.volume = float(v)

    @property
    def body_size(self) -> float:
        return abs(self.close_val - self.open_val)

    @property
    def range(self) -> float:
        return self.high_val - self.low_val

    @property
    def upper_shadow(self) -> float:
        return self.high_val - max(self.open_val, self.close_val)

    @property
    def lower_shadow(self) -> float:
        return min(self.open_val, self.close_val) - self.low_val

    @property
    def is_bullish(self) -> bool:
        return self.close_val > self.open_val

    @property
    def is_bearish(self) -> bool:
        return self.close_val < self.open_val

    @property
    def mid(self) -> float:
        return (self.open_val + self.close_val) / 2


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Testing CandlestickAnalyzer...")

    np.random.seed(42)
    n = 50
    base = 100
    prices = base + np.cumsum(np.random.randn(n) * 1.5)

    df = pd.DataFrame({
        'open': prices + np.random.randn(n) * 0.5,
        'high': prices + abs(np.random.randn(n)) * 2,
        'low': prices - abs(np.random.randn(n)) * 2,
        'close': prices,
        'volume': np.random.randint(100000, 500000, n),
    })

    analyzer = CandlestickAnalyzer()
    signals = analyzer.analyze(df)

    print(f"\nDetected {len(signals)} signals:")
    for s in signals[:5]:
        print(f"  {s.pattern_name}: {s.signal_type} (score={s.context_score:.1f}, vol={s.volume_confirmed})")

    score = analyzer.get_candlestick_score(df)
    print(f"\nCandlestick score: {score:.1f}/30")
