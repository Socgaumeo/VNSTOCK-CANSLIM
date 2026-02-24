"""Trailing stop management for positions."""
from dataclasses import dataclass
from typing import Optional, Tuple
import pandas as pd
import numpy as np


@dataclass
class StopLevel:
    """Current stop level information."""
    stop_price: float
    stop_type: str       # INITIAL, BREAKEVEN, MA10, MA20, TRAILING
    pct_from_entry: float
    pct_from_current: float


class TrailingStopManager:
    """Dynamic trailing stop based on position profit level."""

    INITIAL_STOP_PCT = 0.07    # -7% hard stop
    BREAKEVEN_TRIGGER = 0.05   # Move to breakeven after +5%
    MA10_TRIGGER = 0.10        # Trail MA10 after +10%
    MA20_TRIGGER = 0.20        # Trail MA20 after +20%
    MAX_TRAIL_PCT = 0.10       # Max -10% from highest close

    def calc_stop(self, entry_price: float, current_price: float,
                  highest_price: float, df: pd.DataFrame = None) -> StopLevel:
        """
        Calculate current stop level based on profit stage.

        Stages:
        1. Initial: -7% from entry (hard stop)
        2. After +5%: Move to breakeven (entry price)
        3. After +10%: Trail MA10
        4. After +20%: Trail MA20 or -10% from highest
        """
        pct_gain = (current_price - entry_price) / entry_price if entry_price > 0 else 0

        if pct_gain >= self.MA20_TRIGGER:
            # Stage 4: Trail MA20 or -10% from highest
            stop_ma20 = self._get_ma(df, 20) if df is not None and len(df) >= 20 else 0
            stop_trail = highest_price * (1 - self.MAX_TRAIL_PCT)
            stop_price = max(stop_ma20, stop_trail, entry_price)
            stop_type = "MA20_TRAIL"
        elif pct_gain >= self.MA10_TRIGGER:
            # Stage 3: Trail MA10
            stop_ma10 = self._get_ma(df, 10) if df is not None and len(df) >= 10 else 0
            stop_trail = highest_price * (1 - self.MAX_TRAIL_PCT)
            stop_price = max(stop_ma10, stop_trail, entry_price)
            stop_type = "MA10_TRAIL"
        elif pct_gain >= self.BREAKEVEN_TRIGGER:
            # Stage 2: Breakeven
            stop_price = entry_price
            stop_type = "BREAKEVEN"
        else:
            # Stage 1: Initial hard stop
            stop_price = entry_price * (1 - self.INITIAL_STOP_PCT)
            stop_type = "INITIAL"

        pct_from_entry = (stop_price - entry_price) / entry_price if entry_price > 0 else 0
        pct_from_current = (stop_price - current_price) / current_price if current_price > 0 else 0

        return StopLevel(stop_price, stop_type, pct_from_entry, pct_from_current)

    def should_sell(self, entry_price: float, current_price: float,
                    highest_price: float, stop_price: float) -> Tuple[bool, str]:
        """Check if position should be sold."""
        if current_price <= stop_price:
            pct_loss = (current_price - entry_price) / entry_price * 100
            return True, f"STOP HIT at {current_price:,.0f} (stop={stop_price:,.0f}, P&L={pct_loss:+.1f}%)"
        return False, ""

    def _get_ma(self, df: pd.DataFrame, period: int) -> float:
        """Get latest moving average value."""
        if df is None or len(df) < period:
            return 0.0
        closes = df['close'].tail(period)
        return float(closes.mean())
