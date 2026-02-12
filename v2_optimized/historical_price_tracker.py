#!/usr/bin/env python3
"""
Historical Price Tracker - Theo doi lich su gia va indicators

Tinh nang:
- Luu daily snapshot OHLCV + indicators
- Giu 30 ngay lich su
- Phan tich trend khong can goi API
- Auto cleanup du lieu cu
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict
import warnings

warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DailyPriceSnapshot:
    """Snapshot gia 1 ngay voi day du indicators"""

    date: str                    # YYYY-MM-DD
    symbol: str

    # OHLCV
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: int = 0

    # Change
    change_pct: float = 0.0      # % thay doi so voi hom truoc

    # Moving Averages
    ma20: float = 0.0
    ma50: float = 0.0
    ma200: float = 0.0

    # Indicators
    rsi_14: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_histogram: float = 0.0

    # Volume
    volume_ma20: float = 0.0
    volume_ratio: float = 1.0    # Volume / MA20

    # Volume Profile
    poc: float = 0.0             # Point of Control
    vah: float = 0.0             # Value Area High
    val: float = 0.0             # Value Area Low

    # RS Rating
    rs_rating: int = 50

    def to_dict(self) -> Dict:
        """Convert to dict for JSON serialization"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'DailyPriceSnapshot':
        """Create from dict"""
        return cls(**data)


@dataclass
class TrendAnalysis:
    """Ket qua phan tich trend"""

    symbol: str
    days_analyzed: int = 0

    # Trend
    trend_direction: str = "NEUTRAL"  # UP / DOWN / NEUTRAL
    trend_strength: float = 0.0       # 0-100

    # MA Analysis
    above_ma20: bool = False
    above_ma50: bool = False
    above_ma200: bool = False
    ma_alignment: str = "MIXED"       # BULLISH / BEARISH / MIXED

    # Momentum
    rsi_trend: str = "NEUTRAL"        # RISING / FALLING / NEUTRAL
    rsi_current: float = 50.0
    macd_trend: str = "NEUTRAL"       # BULLISH / BEARISH / NEUTRAL

    # Volume
    volume_trend: str = "NEUTRAL"     # INCREASING / DECREASING / NEUTRAL
    avg_volume_ratio: float = 1.0

    # Price action
    price_change_5d: float = 0.0
    price_change_10d: float = 0.0
    price_change_20d: float = 0.0

    # Support/Resistance (from Volume Profile)
    nearest_support: float = 0.0
    nearest_resistance: float = 0.0

    # Summary
    overall_signal: str = "NEUTRAL"   # BULLISH / BEARISH / NEUTRAL
    confidence: float = 50.0          # 0-100


# ══════════════════════════════════════════════════════════════════════════════
# HISTORICAL PRICE TRACKER
# ══════════════════════════════════════════════════════════════════════════════

class HistoricalPriceTracker:
    """
    Theo doi va cache daily price snapshots

    Usage:
        tracker = HistoricalPriceTracker()

        # Save today's snapshot
        tracker.save_daily_snapshot("VCB", enhanced_stock_data)

        # Get history
        history = tracker.get_price_history("VCB", days=30)

        # Analyze trend (no API calls)
        trend = tracker.analyze_trend("VCB")
    """

    def __init__(self, cache_dir: str = "./cache/historical/price"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_days = 30  # Keep 30 days by default

    def _get_cache_file(self, symbol: str) -> Path:
        """Get cache file path for symbol"""
        return self.cache_dir / f"historical_price_{symbol}.json"

    def _load_history(self, symbol: str) -> List[DailyPriceSnapshot]:
        """Load history from cache file"""
        cache_file = self._get_cache_file(symbol)

        if not cache_file.exists():
            return []

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                snapshots = data.get('snapshots', [])
                return [DailyPriceSnapshot.from_dict(s) for s in snapshots]
        except Exception as e:
            print(f"   Warning: Could not load price history for {symbol}: {e}")
            return []

    def _save_history(self, symbol: str, snapshots: List[DailyPriceSnapshot]) -> bool:
        """Save history to cache file"""
        cache_file = self._get_cache_file(symbol)

        try:
            data = {
                'symbol': symbol,
                'last_updated': datetime.now().isoformat(),
                'count': len(snapshots),
                'snapshots': [s.to_dict() for s in snapshots]
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"   Error saving price history for {symbol}: {e}")
            return False

    def save_daily_snapshot(self, symbol: str, data: Any) -> bool:
        """
        Save today's snapshot from EnhancedStockData
        Also backfills historical data from DataFrame if available

        Args:
            symbol: Stock symbol
            data: EnhancedStockData object with price and indicator data

        Returns:
            True if saved successfully
        """
        # Load existing history
        history = self._load_history(symbol)
        existing_dates = {s.date for s in history}

        # If history is empty or incomplete, try to backfill from DataFrame
        df = getattr(data, 'df', None)
        if df is not None and not df.empty and len(history) < self.max_days:
            history = self._backfill_from_dataframe(symbol, df, history, existing_dates)
            existing_dates = {s.date for s in history}

        # Create today's snapshot from EnhancedStockData
        today = datetime.now().strftime('%Y-%m-%d')
        snapshot = DailyPriceSnapshot(
            date=today,
            symbol=symbol,
            open=getattr(data, 'open', 0) or 0,
            high=getattr(data, 'high', 0) or 0,
            low=getattr(data, 'low', 0) or 0,
            close=getattr(data, 'price', 0) or getattr(data, 'close', 0) or 0,
            volume=int(getattr(data, 'volume', 0) or 0),
            change_pct=getattr(data, 'change_1d', 0) or getattr(data, 'change_pct', 0) or 0,
            ma20=getattr(data, 'ma20', 0) or 0,
            ma50=getattr(data, 'ma50', 0) or 0,
            ma200=getattr(data, 'ma200', 0) or 0,
            rsi_14=getattr(data, 'rsi_14', 50) or getattr(data, 'rsi', 50) or 50,
            macd=getattr(data, 'macd', 0) or 0,
            macd_signal=getattr(data, 'macd_signal', 0) or 0,
            macd_histogram=getattr(data, 'macd_histogram', 0) or 0,
            volume_ma20=getattr(data, 'volume_ma20', 0) or 0,
            volume_ratio=getattr(data, 'volume_ratio', 1) or 1,
            poc=getattr(data, 'poc', 0) or 0,
            vah=getattr(data, 'vah', 0) or 0,
            val=getattr(data, 'val', 0) or 0,
            rs_rating=getattr(data, 'rs_rating', 50) or 50,
        )

        # Check if today already exists, update it
        existing_idx = next((i for i, s in enumerate(history) if s.date == today), None)

        if existing_idx is not None:
            history[existing_idx] = snapshot
        else:
            history.append(snapshot)

        # Sort by date
        history.sort(key=lambda s: s.date)

        # Keep only last max_days
        if len(history) > self.max_days:
            history = history[-self.max_days:]

        # Save
        return self._save_history(symbol, history)

    def _backfill_from_dataframe(self, symbol: str, df, history: List[DailyPriceSnapshot],
                                  existing_dates: set) -> List[DailyPriceSnapshot]:
        """
        Backfill historical data from DataFrame (already fetched from API)
        This allows immediate full analysis without waiting 30 days

        Args:
            symbol: Stock symbol
            df: DataFrame with historical OHLCV data
            history: Existing history list
            existing_dates: Set of dates already in history

        Returns:
            Updated history list with backfilled data
        """
        try:
            import numpy as np

            # Get last 30 days from DataFrame
            df_recent = df.tail(self.max_days).copy()

            if df_recent.empty:
                return history

            # Calculate indicators for backfill
            close = df['close'].values
            volume = df['volume'].values

            for idx, row in df_recent.iterrows():
                # Get date - handle both index types
                if hasattr(idx, 'strftime'):
                    date_str = idx.strftime('%Y-%m-%d')
                elif 'time' in df.columns:
                    date_str = str(row['time'])[:10]
                else:
                    continue

                # Skip if already exists
                if date_str in existing_dates:
                    continue

                # Find position in full array for indicator calculation
                pos = df.index.get_loc(idx) if idx in df.index else -1
                if pos < 20:
                    continue  # Need at least 20 days for indicators

                # Calculate indicators at this point in time
                close_slice = close[:pos+1]
                volume_slice = volume[:pos+1]

                ma20 = np.mean(close_slice[-20:]) if len(close_slice) >= 20 else 0
                ma50 = np.mean(close_slice[-50:]) if len(close_slice) >= 50 else ma20
                ma200 = np.mean(close_slice[-200:]) if len(close_slice) >= 200 else ma50
                volume_ma20 = np.mean(volume_slice[-20:]) if len(volume_slice) >= 20 else 0

                # RSI calculation
                rsi = self._calc_rsi_simple(close_slice) if len(close_slice) >= 15 else 50

                # Change percentage
                change_pct = ((close_slice[-1] / close_slice[-2]) - 1) * 100 if len(close_slice) >= 2 else 0

                # Volume ratio
                vol_ratio = volume_slice[-1] / volume_ma20 if volume_ma20 > 0 else 1

                snapshot = DailyPriceSnapshot(
                    date=date_str,
                    symbol=symbol,
                    open=float(row.get('open', 0) or 0),
                    high=float(row.get('high', 0) or 0),
                    low=float(row.get('low', 0) or 0),
                    close=float(row.get('close', 0) or 0),
                    volume=int(row.get('volume', 0) or 0),
                    change_pct=change_pct,
                    ma20=ma20,
                    ma50=ma50,
                    ma200=ma200,
                    rsi_14=rsi,
                    volume_ma20=volume_ma20,
                    volume_ratio=vol_ratio,
                )

                history.append(snapshot)
                existing_dates.add(date_str)

        except Exception as e:
            # Silent fail - backfill is optional enhancement
            pass

        return history

    def _calc_rsi_simple(self, prices, period: int = 14) -> float:
        """Simple RSI calculation for backfill"""
        import numpy as np

        if len(prices) < period + 1:
            return 50.0

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def get_price_history(self, symbol: str, days: int = 30) -> List[DailyPriceSnapshot]:
        """
        Get historical price snapshots

        Args:
            symbol: Stock symbol
            days: Number of days to return (max)

        Returns:
            List of DailyPriceSnapshot, most recent last
        """
        history = self._load_history(symbol)

        if not history:
            return []

        # Return last N days
        return history[-days:]

    def get_latest_snapshot(self, symbol: str) -> Optional[DailyPriceSnapshot]:
        """Get most recent snapshot"""
        history = self._load_history(symbol)
        return history[-1] if history else None

    def analyze_trend(self, symbol: str, min_days: int = 5) -> TrendAnalysis:
        """
        Analyze trend using cached history (no API calls)

        Args:
            symbol: Stock symbol
            min_days: Minimum days required for analysis

        Returns:
            TrendAnalysis with trend direction, strength, and signals
        """
        history = self._load_history(symbol)
        result = TrendAnalysis(symbol=symbol)

        if len(history) < min_days:
            result.days_analyzed = len(history)
            result.overall_signal = "INSUFFICIENT_DATA"
            result.confidence = 0
            return result

        result.days_analyzed = len(history)

        # Get recent data
        latest = history[-1]
        h5 = history[-5:]   # Last 5 days
        h10 = history[-10:] if len(history) >= 10 else history
        h20 = history[-20:] if len(history) >= 20 else history

        # Current values
        result.rsi_current = latest.rsi_14

        # MA Analysis
        current_price = latest.close
        result.above_ma20 = current_price > latest.ma20 if latest.ma20 > 0 else False
        result.above_ma50 = current_price > latest.ma50 if latest.ma50 > 0 else False
        result.above_ma200 = current_price > latest.ma200 if latest.ma200 > 0 else False

        # MA Alignment
        if result.above_ma20 and result.above_ma50 and result.above_ma200:
            result.ma_alignment = "BULLISH"
        elif not result.above_ma20 and not result.above_ma50 and not result.above_ma200:
            result.ma_alignment = "BEARISH"
        else:
            result.ma_alignment = "MIXED"

        # Price changes
        if len(history) >= 5:
            result.price_change_5d = ((h5[-1].close / h5[0].close) - 1) * 100 if h5[0].close > 0 else 0
        if len(history) >= 10:
            result.price_change_10d = ((h10[-1].close / h10[0].close) - 1) * 100 if h10[0].close > 0 else 0
        if len(history) >= 20:
            result.price_change_20d = ((h20[-1].close / h20[0].close) - 1) * 100 if h20[0].close > 0 else 0

        # Trend direction
        if result.price_change_5d > 2 and result.price_change_10d > 0:
            result.trend_direction = "UP"
            result.trend_strength = min(100, abs(result.price_change_5d) * 10)
        elif result.price_change_5d < -2 and result.price_change_10d < 0:
            result.trend_direction = "DOWN"
            result.trend_strength = min(100, abs(result.price_change_5d) * 10)
        else:
            result.trend_direction = "NEUTRAL"
            result.trend_strength = 50

        # RSI Trend
        rsi_values = [s.rsi_14 for s in h5]
        if len(rsi_values) >= 3:
            rsi_change = rsi_values[-1] - rsi_values[0]
            if rsi_change > 5:
                result.rsi_trend = "RISING"
            elif rsi_change < -5:
                result.rsi_trend = "FALLING"
            else:
                result.rsi_trend = "NEUTRAL"

        # MACD Trend
        if latest.macd > latest.macd_signal:
            result.macd_trend = "BULLISH"
        elif latest.macd < latest.macd_signal:
            result.macd_trend = "BEARISH"
        else:
            result.macd_trend = "NEUTRAL"

        # Volume Trend
        vol_ratios = [s.volume_ratio for s in h5 if s.volume_ratio > 0]
        if vol_ratios:
            result.avg_volume_ratio = sum(vol_ratios) / len(vol_ratios)
            if vol_ratios[-1] > vol_ratios[0] * 1.2:
                result.volume_trend = "INCREASING"
            elif vol_ratios[-1] < vol_ratios[0] * 0.8:
                result.volume_trend = "DECREASING"
            else:
                result.volume_trend = "NEUTRAL"

        # Support/Resistance from Volume Profile
        result.nearest_support = latest.val if latest.val > 0 else latest.poc * 0.95
        result.nearest_resistance = latest.vah if latest.vah > 0 else latest.poc * 1.05

        # Overall Signal
        bullish_signals = 0
        bearish_signals = 0

        if result.trend_direction == "UP":
            bullish_signals += 2
        elif result.trend_direction == "DOWN":
            bearish_signals += 2

        if result.ma_alignment == "BULLISH":
            bullish_signals += 2
        elif result.ma_alignment == "BEARISH":
            bearish_signals += 2

        if result.macd_trend == "BULLISH":
            bullish_signals += 1
        elif result.macd_trend == "BEARISH":
            bearish_signals += 1

        if result.rsi_current < 30:
            bullish_signals += 1  # Oversold
        elif result.rsi_current > 70:
            bearish_signals += 1  # Overbought

        if result.volume_trend == "INCREASING" and result.trend_direction == "UP":
            bullish_signals += 1

        total_signals = bullish_signals + bearish_signals
        if total_signals > 0:
            bull_pct = bullish_signals / total_signals * 100
            if bull_pct >= 60:
                result.overall_signal = "BULLISH"
                result.confidence = bull_pct
            elif bull_pct <= 40:
                result.overall_signal = "BEARISH"
                result.confidence = 100 - bull_pct
            else:
                result.overall_signal = "NEUTRAL"
                result.confidence = 50

        return result

    def get_all_symbols(self) -> List[str]:
        """Get all symbols with cached history"""
        symbols = []
        for f in self.cache_dir.glob("historical_price_*.json"):
            symbol = f.stem.replace("historical_price_", "")
            symbols.append(symbol)
        return sorted(symbols)

    def cleanup_old_data(self, older_than_days: int = 90):
        """Remove cache files not updated in X days"""
        cutoff = datetime.now() - timedelta(days=older_than_days)

        for cache_file in self.cache_dir.glob("historical_price_*.json"):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    last_updated = datetime.fromisoformat(data.get('last_updated', ''))

                    if last_updated < cutoff:
                        cache_file.unlink()
                        print(f"   Cleaned up old cache: {cache_file.name}")
            except:
                pass

    def get_summary(self) -> Dict:
        """Get summary of cached data"""
        symbols = self.get_all_symbols()
        total_snapshots = 0

        for symbol in symbols:
            history = self._load_history(symbol)
            total_snapshots += len(history)

        return {
            'symbols_count': len(symbols),
            'total_snapshots': total_snapshots,
            'cache_dir': str(self.cache_dir),
            'max_days_per_symbol': self.max_days
        }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

_tracker_instance: Optional[HistoricalPriceTracker] = None


def get_price_tracker() -> HistoricalPriceTracker:
    """Get singleton instance of HistoricalPriceTracker"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = HistoricalPriceTracker()
    return _tracker_instance


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Testing HistoricalPriceTracker...")

    tracker = get_price_tracker()

    # Summary
    summary = tracker.get_summary()
    print(f"\nCache Summary:")
    print(f"  Symbols: {summary['symbols_count']}")
    print(f"  Snapshots: {summary['total_snapshots']}")
    print(f"  Location: {summary['cache_dir']}")

    # List symbols
    symbols = tracker.get_all_symbols()
    if symbols:
        print(f"\nCached symbols: {symbols[:10]}...")

        # Analyze first symbol
        symbol = symbols[0]
        history = tracker.get_price_history(symbol, days=5)
        print(f"\n{symbol} last 5 days:")
        for snap in history:
            print(f"  {snap.date}: {snap.close:,.0f} | RSI: {snap.rsi_14:.0f}")

        # Trend analysis
        trend = tracker.analyze_trend(symbol)
        print(f"\nTrend Analysis for {symbol}:")
        print(f"  Direction: {trend.trend_direction}")
        print(f"  MA Alignment: {trend.ma_alignment}")
        print(f"  Overall Signal: {trend.overall_signal} ({trend.confidence:.0f}%)")
    else:
        print("\nNo cached data yet. Run pipeline to collect data.")
