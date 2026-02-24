"""VN Market-specific indicator optimization.

Vietnam stock market has unique characteristics:
- HOSE price limit: ±7% daily
- T+2.5 settlement cycle
- Low-cap stocks have very low liquidity
- Sector PE ranges differ significantly
- Ceiling/floor price signals are important
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

# ─── VN Market Constants ─────────────────────────────────────────────
HOSE_PRICE_LIMIT = 0.07   # ±7%
HNX_PRICE_LIMIT = 0.10    # ±10%
UPCOM_PRICE_LIMIT = 0.15  # ±15%

# RSI adjusted for VN market ±7% limit (moves slower than US)
VN_RSI_OVERSOLD = 35      # vs standard 30
VN_RSI_OVERBOUGHT = 65    # vs standard 70
VN_RSI_OPTIMAL = (45, 65) # Best entry zone

# Sector PE acceptable ranges for VN market
SECTOR_PE_RANGES = {
    'VNFIN': (5, 15),      # Banks: low PE
    'VNREAL': (8, 25),     # Real Estate: higher PE
    'VNMAT': (5, 12),      # Materials: low PE
    'VNIT': (15, 35),      # Tech: highest PE
    'VNHEAL': (10, 25),    # Healthcare: mid-high PE
    'VNCOND': (10, 20),    # Consumer Discretionary: mid PE
    'VNCONS': (15, 30),    # Consumer Staples: stable, higher PE
}

# ─── Dataclasses ─────────────────────────────────────────────────────

@dataclass
class LiquidityCheck:
    avg_value_20d: float = 0.0      # Average traded value (VND/session)
    passes_filter: bool = False
    participation_shares: int = 0    # Max shares without market impact
    liquidity_grade: str = "F"       # A/B/C/D/F

@dataclass
class CeilingFloorSignal:
    at_ceiling_today: bool = False
    at_floor_today: bool = False
    ceiling_count_5d: int = 0
    floor_count_5d: int = 0
    ceiling_with_volume: bool = False  # Ceiling + volume > 2x avg
    floor_with_volume: bool = False

@dataclass
class SectorPEScore:
    sector: str = ""
    current_pe: float = 0.0
    pe_low: float = 0.0
    pe_high: float = 0.0
    pe_percentile: float = 50.0    # 0-100 within sector range
    pe_verdict: str = "FAIR"       # CHEAP, FAIR, EXPENSIVE

@dataclass
class VNMarketSignals:
    liquidity: LiquidityCheck = field(default_factory=LiquidityCheck)
    ceiling_floor: CeilingFloorSignal = field(default_factory=CeilingFloorSignal)
    sector_pe: SectorPEScore = field(default_factory=SectorPEScore)
    rsi_adjusted: float = 50.0
    rsi_zone: str = "NEUTRAL"       # OVERSOLD, NEUTRAL, OVERBOUGHT, OPTIMAL
    timing_advice: str = ""

# ─── Main Optimizer Class ────────────────────────────────────────────

class VNMarketOptimizer:
    """Optimize indicators for VN stock market specifics."""

    def __init__(self, min_avg_value: float = 5_000_000_000,
                 max_participation_rate: float = 0.05):
        """
        Args:
            min_avg_value: Minimum 20-day avg traded value in VND (default 5 billion)
            max_participation_rate: Max % of daily volume we can trade (default 5%)
        """
        self.min_avg_value = min_avg_value
        self.max_participation_rate = max_participation_rate

    def check_liquidity(self, df: pd.DataFrame, entry_price: float = 0) -> LiquidityCheck:
        """Check liquidity using Average Traded Value instead of just volume."""
        result = LiquidityCheck()

        if df is None or df.empty or len(df) < 20:
            return result

        recent = df.tail(20)

        # Calculate average traded value
        if 'value' in recent.columns:
            avg_value = float(recent['value'].mean())
        else:
            # Estimate: close * volume
            avg_value = float((recent['close'] * recent['volume']).mean())

        result.avg_value_20d = avg_value
        result.passes_filter = avg_value >= self.min_avg_value

        # Participation sizing
        if entry_price > 0:
            avg_volume = float(recent['volume'].mean())
            result.participation_shares = int(avg_volume * self.max_participation_rate)
            result.participation_shares = (result.participation_shares // 100) * 100  # Round to lots

        # Grade
        if avg_value >= 50_000_000_000:   result.liquidity_grade = "A"    # 50B+
        elif avg_value >= 20_000_000_000: result.liquidity_grade = "B"    # 20B+
        elif avg_value >= 10_000_000_000: result.liquidity_grade = "C"    # 10B+
        elif avg_value >= 5_000_000_000:  result.liquidity_grade = "D"    # 5B+
        else:                             result.liquidity_grade = "F"    # <5B

        return result

    def detect_ceiling_floor(self, df: pd.DataFrame, exchange: str = "HOSE") -> CeilingFloorSignal:
        """Detect ceiling (trần) and floor (sàn) prices with volume confirmation."""
        result = CeilingFloorSignal()

        if df is None or df.empty or len(df) < 2:
            return result

        limit = HOSE_PRICE_LIMIT
        if exchange == "HNX": limit = HNX_PRICE_LIMIT
        elif exchange == "UPCOM": limit = UPCOM_PRICE_LIMIT

        recent = df.tail(6)  # Last 5 sessions + today
        avg_vol = float(df['volume'].tail(20).mean()) if len(df) >= 20 else float(df['volume'].mean())

        for i in range(1, len(recent)):  # Start from 1 to have previous day
            row = recent.iloc[i]
            prev_close = float(recent.iloc[i-1]['close'])
            close = float(row['close'])
            volume = float(row['volume'])

            if prev_close <= 0:
                continue

            change_pct = (close - prev_close) / prev_close

            # Ceiling/Floor detection with tolerance
            is_ceiling = change_pct >= (limit - 0.002)
            is_floor = change_pct <= (-limit + 0.002)

            if i == len(recent) - 1:  # Today
                result.at_ceiling_today = is_ceiling
                result.at_floor_today = is_floor
                if is_ceiling and volume > avg_vol * 2:
                    result.ceiling_with_volume = True
                if is_floor and volume > avg_vol * 2:
                    result.floor_with_volume = True

            if is_ceiling: result.ceiling_count_5d += 1
            if is_floor: result.floor_count_5d += 1

        return result

    def score_sector_pe(self, sector: str, current_pe: float) -> SectorPEScore:
        """Score PE relative to sector norms."""
        result = SectorPEScore(sector=sector, current_pe=current_pe)

        pe_range = SECTOR_PE_RANGES.get(sector)
        if not pe_range or current_pe <= 0:
            return result

        result.pe_low, result.pe_high = pe_range

        # Percentile within range
        range_width = result.pe_high - result.pe_low
        if range_width > 0:
            result.pe_percentile = ((current_pe - result.pe_low) / range_width) * 100
            result.pe_percentile = max(0, min(100, result.pe_percentile))

        # Verdict
        if current_pe < result.pe_low:
            result.pe_verdict = "CHEAP"
        elif current_pe > result.pe_high:
            result.pe_verdict = "EXPENSIVE"
        elif result.pe_percentile <= 30:
            result.pe_verdict = "CHEAP"
        elif result.pe_percentile >= 70:
            result.pe_verdict = "EXPENSIVE"
        else:
            result.pe_verdict = "FAIR"

        return result

    def adjust_rsi(self, rsi_14: float) -> Tuple[str, float]:
        """Adjust RSI interpretation for VN market. Returns (zone_name, score_adjustment)."""
        if rsi_14 <= VN_RSI_OVERSOLD:
            return "OVERSOLD", 5.0
        elif rsi_14 >= VN_RSI_OVERBOUGHT:
            return "OVERBOUGHT", -5.0
        elif VN_RSI_OPTIMAL[0] <= rsi_14 <= VN_RSI_OPTIMAL[1]:
            return "OPTIMAL", 5.0
        else:
            return "NEUTRAL", 0.0

    def get_timing_advice(self, signal: str = "BUY") -> str:
        """T+2.5 settlement-aware timing advice."""
        advices = {
            "BUY": "🕘 ATO (9:00-9:15) for breakout. Session sáng confirm volume. TRÁNH ATC (14:30-14:45). T+2.5: tiền trừ sau 2.5 ngày.",
            "SELL": "🕐 Bán sáng if stop loss triggered. ATC for guaranteed execution. T+2.5: tiền về sau 2.5 ngày.",
        }
        return advices.get(signal, "")

    def analyze(self, df: pd.DataFrame, sector: str = "", pe: float = 0.0,
                rsi: float = 50.0, entry_price: float = 0.0,
                exchange: str = "HOSE") -> VNMarketSignals:
        """Run full VN market optimization analysis."""
        signals = VNMarketSignals()

        signals.liquidity = self.check_liquidity(df, entry_price)
        signals.ceiling_floor = self.detect_ceiling_floor(df, exchange)

        if sector and pe > 0:
            signals.sector_pe = self.score_sector_pe(sector, pe)

        signals.rsi_zone, _ = self.adjust_rsi(rsi)
        signals.rsi_adjusted = rsi
        signals.timing_advice = self.get_timing_advice("BUY")

        return signals
