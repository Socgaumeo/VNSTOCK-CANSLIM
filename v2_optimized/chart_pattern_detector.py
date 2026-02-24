#!/usr/bin/env python3
"""
Chart pattern detection based on Bulkowski's Encyclopedia statistics.
Detects high-success geometric patterns from OHLCV data.

Priority patterns (Tier 1-2, success >= 80%):
- Double Bottom/Top
- Head and Shoulders / Inverse
- Ascending/Descending Triangle
- Bull/Bear Flag
- Falling Wedge

Reference: thanhtran-165.github.io/ChartPattern (Bulkowski Vietnamese)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class ChartPatternSignal:
    """A detected chart pattern signal."""
    pattern_name: str
    pattern_name_vn: str
    signal_type: str        # "bullish", "bearish", "bilateral"
    success_rate: float     # Bulkowski historical success rate
    avg_move: float         # Expected avg % move
    confidence: float       # 0-100 detection confidence
    breakout_price: float   # Expected breakout level
    target_price: float     # Price target based on pattern
    start_idx: int          # Pattern start index in dataframe
    end_idx: int            # Pattern end index
    description: str


class ChartPatternDetector:
    """
    Detect high-success chart patterns from OHLCV data.

    Usage:
        detector = ChartPatternDetector()
        patterns = detector.detect_all(df)
    """

    def detect_all(self, df: pd.DataFrame) -> List[ChartPatternSignal]:
        """Run all pattern detectors on the DataFrame."""
        if df.empty or len(df) < 30:
            return []

        c = df['close'].values.astype(float)
        h = df['high'].values.astype(float)
        lo = df['low'].values.astype(float)
        v = df['volume'].values.astype(float)

        patterns = []

        detectors = [
            self._detect_double_bottom,
            self._detect_double_top,
            self._detect_head_shoulders,
            self._detect_inv_head_shoulders,
            self._detect_ascending_triangle,
            self._detect_descending_triangle,
            self._detect_bull_flag,
            self._detect_bear_flag,
            self._detect_falling_wedge,
            self._detect_rising_wedge,
        ]

        for detector in detectors:
            result = detector(c, h, lo, v)
            if result:
                patterns.append(result)

        patterns.sort(key=lambda p: p.confidence * p.success_rate / 100, reverse=True)
        return patterns

    def get_pattern_score(self, df: pd.DataFrame) -> float:
        """Get a single score (0-30) for integration into screener scoring."""
        patterns = self.detect_all(df)
        if not patterns:
            return 0
        best = patterns[0]
        # Weight by success_rate and confidence
        raw = best.confidence * best.success_rate / 100
        return min(30, raw * 0.35)

    # ─────────────────────────────────────────────────────────────
    # PATTERN DETECTORS
    # ─────────────────────────────────────────────────────────────

    def _find_swing_points(self, data: np.ndarray, order: int = 5) -> Tuple[list, list]:
        """Find local maxima (highs) and minima (lows) in price data."""
        highs, lows = [], []
        for i in range(order, len(data) - order):
            if all(data[i] >= data[i-j] for j in range(1, order+1)) and \
               all(data[i] >= data[i+j] for j in range(1, order+1)):
                highs.append(i)
            if all(data[i] <= data[i-j] for j in range(1, order+1)) and \
               all(data[i] <= data[i+j] for j in range(1, order+1)):
                lows.append(i)
        return highs, lows

    def _detect_double_bottom(self, c, h, lo, v) -> Optional[ChartPatternSignal]:
        """Double Bottom: two lows at similar levels with neckline break. Success: 82%."""
        _, swing_lows = self._find_swing_points(lo, order=5)
        if len(swing_lows) < 2:
            return None

        # Check last two swing lows
        for i in range(len(swing_lows) - 1, 0, -1):
            l2_idx = swing_lows[i]
            l1_idx = swing_lows[i - 1]

            # Lows should be within 3% of each other
            l1, l2 = lo[l1_idx], lo[l2_idx]
            if l1 == 0:
                continue
            diff_pct = abs(l1 - l2) / l1
            if diff_pct > 0.03:
                continue

            # Separation: 10-60 bars between lows
            sep = l2_idx - l1_idx
            if sep < 10 or sep > 60:
                continue

            # Neckline: highest point between the two lows
            between = c[l1_idx:l2_idx+1]
            neckline_idx = l1_idx + np.argmax(between)
            neckline = c[neckline_idx]

            # Pattern should be forming recently (within last 20 bars)
            if len(c) - l2_idx > 20:
                continue

            # Check if price is breaking above neckline
            current = c[-1]
            conf = 70 if current >= neckline * 0.98 else 50
            target = neckline + (neckline - min(l1, l2))

            return ChartPatternSignal(
                pattern_name="Double Bottom",
                pattern_name_vn="Đáy Kép",
                signal_type="bullish",
                success_rate=82,
                avg_move=20,
                confidence=conf,
                breakout_price=neckline,
                target_price=target,
                start_idx=l1_idx,
                end_idx=l2_idx,
                description=f"Đáy Kép tại {min(l1,l2):,.0f}, neckline {neckline:,.0f}, target {target:,.0f}"
            )
        return None

    def _detect_double_top(self, c, h, lo, v) -> Optional[ChartPatternSignal]:
        """Double Top: two highs at similar levels. Success: 78%."""
        swing_highs, _ = self._find_swing_points(h, order=5)
        if len(swing_highs) < 2:
            return None

        for i in range(len(swing_highs) - 1, 0, -1):
            h2_idx = swing_highs[i]
            h1_idx = swing_highs[i - 1]

            h1, h2 = h[h1_idx], h[h2_idx]
            if h1 == 0:
                continue
            diff_pct = abs(h1 - h2) / h1
            if diff_pct > 0.03:
                continue

            sep = h2_idx - h1_idx
            if sep < 10 or sep > 60:
                continue

            between = c[h1_idx:h2_idx+1]
            neckline_idx = h1_idx + np.argmin(between)
            neckline = c[neckline_idx]

            if len(c) - h2_idx > 20:
                continue

            current = c[-1]
            conf = 70 if current <= neckline * 1.02 else 50
            target = neckline - (max(h1, h2) - neckline)

            return ChartPatternSignal(
                pattern_name="Double Top",
                pattern_name_vn="Đỉnh Kép",
                signal_type="bearish",
                success_rate=78,
                avg_move=-15,
                confidence=conf,
                breakout_price=neckline,
                target_price=target,
                start_idx=h1_idx,
                end_idx=h2_idx,
                description=f"Đỉnh Kép tại {max(h1,h2):,.0f}, neckline {neckline:,.0f}"
            )
        return None

    def _detect_head_shoulders(self, c, h, lo, v) -> Optional[ChartPatternSignal]:
        """Head and Shoulders: left shoulder, head (higher), right shoulder. Success: 89%."""
        swing_highs, _ = self._find_swing_points(h, order=4)
        if len(swing_highs) < 3:
            return None

        for i in range(len(swing_highs) - 2, -1, -1):
            ls_idx, head_idx, rs_idx = swing_highs[i], swing_highs[i+1], swing_highs[i+2] if i+2 < len(swing_highs) else None
            if rs_idx is None:
                continue

            ls, head, rs = h[ls_idx], h[head_idx], h[rs_idx]

            # Head must be highest
            if head <= ls or head <= rs:
                continue

            # Shoulders roughly equal (within 5%)
            if ls == 0:
                continue
            if abs(ls - rs) / ls > 0.05:
                continue

            # Recent pattern
            if len(c) - rs_idx > 15:
                continue

            # Neckline from lows between shoulders
            low_between_ls_head = np.min(lo[ls_idx:head_idx+1])
            low_between_head_rs = np.min(lo[head_idx:rs_idx+1])
            neckline = max(low_between_ls_head, low_between_head_rs)
            target = neckline - (head - neckline)

            conf = 75 if c[-1] < neckline * 1.02 else 55

            return ChartPatternSignal(
                pattern_name="Head and Shoulders",
                pattern_name_vn="Đầu và Vai",
                signal_type="bearish",
                success_rate=89,
                avg_move=-18,
                confidence=conf,
                breakout_price=neckline,
                target_price=target,
                start_idx=ls_idx,
                end_idx=rs_idx,
                description=f"Head & Shoulders: head={head:,.0f}, neckline={neckline:,.0f}"
            )
        return None

    def _detect_inv_head_shoulders(self, c, h, lo, v) -> Optional[ChartPatternSignal]:
        """Inverse Head and Shoulders. Success: 81%."""
        _, swing_lows = self._find_swing_points(lo, order=4)
        if len(swing_lows) < 3:
            return None

        for i in range(len(swing_lows) - 2, -1, -1):
            ls_idx, head_idx = swing_lows[i], swing_lows[i+1]
            rs_idx = swing_lows[i+2] if i+2 < len(swing_lows) else None
            if rs_idx is None:
                continue

            ls, head, rs = lo[ls_idx], lo[head_idx], lo[rs_idx]

            if head >= ls or head >= rs:
                continue

            if ls == 0:
                continue
            if abs(ls - rs) / ls > 0.05:
                continue

            if len(c) - rs_idx > 15:
                continue

            high_ls_head = np.max(h[ls_idx:head_idx+1])
            high_head_rs = np.max(h[head_idx:rs_idx+1])
            neckline = min(high_ls_head, high_head_rs)
            target = neckline + (neckline - head)

            conf = 75 if c[-1] > neckline * 0.98 else 55

            return ChartPatternSignal(
                pattern_name="Inverse Head and Shoulders",
                pattern_name_vn="Đầu và Vai Ngược",
                signal_type="bullish",
                success_rate=81,
                avg_move=22,
                confidence=conf,
                breakout_price=neckline,
                target_price=target,
                start_idx=ls_idx,
                end_idx=rs_idx,
                description=f"Inverse H&S: head={head:,.0f}, neckline={neckline:,.0f}, target={target:,.0f}"
            )
        return None

    def _detect_ascending_triangle(self, c, h, lo, v) -> Optional[ChartPatternSignal]:
        """Ascending Triangle: flat resistance + rising support. Success: 75%."""
        if len(c) < 30:
            return None

        recent = c[-30:]
        swing_highs, swing_lows = self._find_swing_points(recent, order=3)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return None

        # Check flat resistance (highs within 2%)
        high_vals = [recent[i] for i in swing_highs[-3:]]
        if len(high_vals) < 2:
            return None
        high_range = (max(high_vals) - min(high_vals)) / max(high_vals) if max(high_vals) > 0 else 1
        if high_range > 0.02:
            return None

        # Check rising lows
        low_vals = [recent[i] for i in swing_lows[-3:]]
        if len(low_vals) < 2:
            return None
        if not all(low_vals[j] >= low_vals[j-1] * 0.99 for j in range(1, len(low_vals))):
            return None

        resistance = np.mean(high_vals)
        target = resistance + (resistance - min(low_vals))

        return ChartPatternSignal(
            pattern_name="Ascending Triangle",
            pattern_name_vn="Tam Giác Tăng",
            signal_type="bullish",
            success_rate=75,
            avg_move=12,
            confidence=60,
            breakout_price=resistance,
            target_price=target,
            start_idx=len(c) - 30,
            end_idx=len(c) - 1,
            description=f"Tam Giác Tăng: resistance={resistance:,.0f}, target={target:,.0f}"
        )

    def _detect_descending_triangle(self, c, h, lo, v) -> Optional[ChartPatternSignal]:
        """Descending Triangle: flat support + falling resistance. Success: 79%."""
        if len(c) < 30:
            return None

        recent_lo = lo[-30:]
        recent_h = h[-30:]
        swing_highs, swing_lows = self._find_swing_points(c[-30:], order=3)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return None

        low_vals = [recent_lo[i] for i in swing_lows[-3:]]
        if len(low_vals) < 2:
            return None
        low_range = (max(low_vals) - min(low_vals)) / max(low_vals) if max(low_vals) > 0 else 1
        if low_range > 0.02:
            return None

        high_vals = [recent_h[i] for i in swing_highs[-3:]]
        if len(high_vals) < 2:
            return None
        if not all(high_vals[j] <= high_vals[j-1] * 1.01 for j in range(1, len(high_vals))):
            return None

        support = np.mean(low_vals)
        target = support - (max(high_vals) - support)

        return ChartPatternSignal(
            pattern_name="Descending Triangle",
            pattern_name_vn="Tam Giác Giảm",
            signal_type="bearish",
            success_rate=79,
            avg_move=-15,
            confidence=60,
            breakout_price=support,
            target_price=target,
            start_idx=len(c) - 30,
            end_idx=len(c) - 1,
            description=f"Tam Giác Giảm: support={support:,.0f}"
        )

    def _detect_bull_flag(self, c, h, lo, v) -> Optional[ChartPatternSignal]:
        """Bull Flag: strong uptrend + shallow pullback consolidation. Success: 85%."""
        if len(c) < 20:
            return None

        # Look for strong pole (15%+ rise in 10 bars)
        for pole_start in range(max(0, len(c)-30), len(c)-10):
            pole_end = pole_start + 10
            if pole_end >= len(c):
                continue
            pole_rise = (c[pole_end] - c[pole_start]) / c[pole_start] if c[pole_start] > 0 else 0
            if pole_rise < 0.10:
                continue

            # Flag: shallow pullback (< 50% of pole)
            flag = c[pole_end:]
            if len(flag) < 3:
                continue
            flag_low = np.min(flag)
            pole_height = c[pole_end] - c[pole_start]
            pullback = (c[pole_end] - flag_low) / pole_height if pole_height > 0 else 1

            if 0.1 < pullback < 0.5:
                breakout = c[pole_end]
                target = breakout + pole_height

                return ChartPatternSignal(
                    pattern_name="Bull Flag",
                    pattern_name_vn="Cờ Tăng",
                    signal_type="bullish",
                    success_rate=85,
                    avg_move=14,
                    confidence=65,
                    breakout_price=breakout,
                    target_price=target,
                    start_idx=pole_start,
                    end_idx=len(c) - 1,
                    description=f"Bull Flag: pole +{pole_rise*100:.0f}%, pullback {pullback*100:.0f}%, target {target:,.0f}"
                )
        return None

    def _detect_bear_flag(self, c, h, lo, v) -> Optional[ChartPatternSignal]:
        """Bear Flag: strong downtrend + shallow bounce consolidation. Success: 83%."""
        if len(c) < 20:
            return None

        for pole_start in range(max(0, len(c)-30), len(c)-10):
            pole_end = pole_start + 10
            if pole_end >= len(c):
                continue
            pole_drop = (c[pole_start] - c[pole_end]) / c[pole_start] if c[pole_start] > 0 else 0
            if pole_drop < 0.10:
                continue

            flag = c[pole_end:]
            if len(flag) < 3:
                continue
            flag_high = np.max(flag)
            pole_height = c[pole_start] - c[pole_end]
            bounce = (flag_high - c[pole_end]) / pole_height if pole_height > 0 else 1

            if 0.1 < bounce < 0.5:
                breakout = c[pole_end]
                target = breakout - pole_height

                return ChartPatternSignal(
                    pattern_name="Bear Flag",
                    pattern_name_vn="Cờ Giảm",
                    signal_type="bearish",
                    success_rate=83,
                    avg_move=-13,
                    confidence=65,
                    breakout_price=breakout,
                    target_price=target,
                    start_idx=pole_start,
                    end_idx=len(c) - 1,
                    description=f"Bear Flag: pole -{pole_drop*100:.0f}%, bounce {bounce*100:.0f}%"
                )
        return None

    def _detect_falling_wedge(self, c, h, lo, v) -> Optional[ChartPatternSignal]:
        """Falling Wedge: converging downtrend lines, typically bullish. Success: 81%."""
        if len(c) < 25:
            return None

        recent = c[-25:]
        swing_highs, swing_lows = self._find_swing_points(recent, order=3)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return None

        high_vals = [recent[i] for i in swing_highs[-3:]]
        low_vals = [recent[i] for i in swing_lows[-3:]]

        # Both highs and lows should be falling
        highs_falling = all(high_vals[j] < high_vals[j-1] for j in range(1, len(high_vals)))
        lows_falling = all(low_vals[j] < low_vals[j-1] for j in range(1, len(low_vals)))

        if not (highs_falling and lows_falling):
            return None

        # Converging: rate of decline in highs > rate in lows
        if len(high_vals) >= 2 and len(low_vals) >= 2:
            high_slope = (high_vals[-1] - high_vals[0]) / len(high_vals) if len(high_vals) > 1 else 0
            low_slope = (low_vals[-1] - low_vals[0]) / len(low_vals) if len(low_vals) > 1 else 0

            if high_slope < low_slope:  # Converging
                breakout = high_vals[-1]
                height = high_vals[0] - low_vals[0]
                target = breakout + height * 0.6

                return ChartPatternSignal(
                    pattern_name="Falling Wedge",
                    pattern_name_vn="Nêm Giảm",
                    signal_type="bullish",
                    success_rate=81,
                    avg_move=18,
                    confidence=55,
                    breakout_price=breakout,
                    target_price=target,
                    start_idx=len(c) - 25,
                    end_idx=len(c) - 1,
                    description=f"Nêm Giảm - converging, target {target:,.0f}"
                )
        return None

    def _detect_rising_wedge(self, c, h, lo, v) -> Optional[ChartPatternSignal]:
        """Rising Wedge: converging uptrend lines, typically bearish. Success: 72%."""
        if len(c) < 25:
            return None

        recent = c[-25:]
        swing_highs, swing_lows = self._find_swing_points(recent, order=3)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return None

        high_vals = [recent[i] for i in swing_highs[-3:]]
        low_vals = [recent[i] for i in swing_lows[-3:]]

        highs_rising = all(high_vals[j] > high_vals[j-1] for j in range(1, len(high_vals)))
        lows_rising = all(low_vals[j] > low_vals[j-1] for j in range(1, len(low_vals)))

        if not (highs_rising and lows_rising):
            return None

        if len(high_vals) >= 2 and len(low_vals) >= 2:
            high_slope = (high_vals[-1] - high_vals[0]) / len(high_vals) if len(high_vals) > 1 else 0
            low_slope = (low_vals[-1] - low_vals[0]) / len(low_vals) if len(low_vals) > 1 else 0

            if high_slope < low_slope:  # Converging
                breakout = low_vals[-1]
                height = high_vals[0] - low_vals[0]
                target = breakout - height * 0.6

                return ChartPatternSignal(
                    pattern_name="Rising Wedge",
                    pattern_name_vn="Nêm Tăng",
                    signal_type="bearish",
                    success_rate=72,
                    avg_move=-12,
                    confidence=55,
                    breakout_price=breakout,
                    target_price=target,
                    start_idx=len(c) - 25,
                    end_idx=len(c) - 1,
                    description=f"Nêm Tăng - converging bearish, target {target:,.0f}"
                )
        return None


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Testing ChartPatternDetector...")

    np.random.seed(42)
    n = 100
    prices = 100 + np.cumsum(np.random.randn(n) * 1.5)

    df = pd.DataFrame({
        'open': prices + np.random.randn(n) * 0.5,
        'high': prices + abs(np.random.randn(n)) * 2,
        'low': prices - abs(np.random.randn(n)) * 2,
        'close': prices,
        'volume': np.random.randint(100000, 500000, n),
    })

    detector = ChartPatternDetector()
    patterns = detector.detect_all(df)

    print(f"\nDetected {len(patterns)} chart patterns:")
    for p in patterns:
        print(f"  {p.pattern_name} ({p.pattern_name_vn}): {p.signal_type}")
        print(f"    Success: {p.success_rate}%, Confidence: {p.confidence}")
        print(f"    Breakout: {p.breakout_price:,.0f}, Target: {p.target_price:,.0f}")

    score = detector.get_pattern_score(df)
    print(f"\nChart pattern score: {score:.1f}/30")
