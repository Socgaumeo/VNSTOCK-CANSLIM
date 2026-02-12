#!/usr/bin/env python3
"""
Historical Foreign Tracker - Theo dõi giao dịch khối ngoại

Tính năng:
- Lưu daily foreign buy/sell data
- Tính rolling 20-day net buy
- Phát hiện accumulation/distribution patterns
- Giữ 30 ngày lịch sử
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import warnings

warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

class ForeignTrend(Enum):
    """Xu hướng giao dịch khối ngoại"""
    ACCUMULATING = "ACCUMULATING"      # Đang tích lũy
    DISTRIBUTING = "DISTRIBUTING"      # Đang phân phối
    NEUTRAL = "NEUTRAL"                # Trung lập


@dataclass
class DailyForeignFlow:
    """Dữ liệu giao dịch khối ngoại 1 ngày"""

    date: str               # YYYY-MM-DD
    symbol: str

    # Foreign transactions (VND)
    buy_value: float = 0.0      # Giá trị mua
    sell_value: float = 0.0     # Giá trị bán
    net_value: float = 0.0      # Mua ròng (buy - sell)

    # Volume (shares)
    buy_volume: int = 0         # KL mua
    sell_volume: int = 0        # KL bán
    net_volume: int = 0         # KL mua ròng

    # Context
    price: float = 0.0          # Giá đóng cửa
    total_volume: int = 0       # Tổng KL phiên
    foreign_pct: float = 0.0    # % KL khối ngoại / Tổng KL

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'DailyForeignFlow':
        return cls(**data)


@dataclass
class ForeignFlowAnalysis:
    """Phân tích giao dịch khối ngoại rolling"""

    symbol: str
    analysis_date: str = ""
    days_analyzed: int = 0

    # Data coverage
    data_coverage_pct: float = 0.0      # % dữ liệu có sẵn (0-100)
    is_data_complete: bool = False      # True nếu có đủ 20 ngày

    # Rolling 20-day metrics (VND)
    net_value_20d: float = 0.0          # Tổng mua ròng 20 ngày
    avg_daily_net_20d: float = 0.0      # TB mua ròng/ngày
    total_buy_20d: float = 0.0          # Tổng mua 20 ngày
    total_sell_20d: float = 0.0         # Tổng bán 20 ngày

    # Buy/Sell balance
    buy_days_count: int = 0             # Số ngày mua ròng
    sell_days_count: int = 0            # Số ngày bán ròng
    neutral_days_count: int = 0         # Số ngày trung lập

    # Trend
    trend: str = "NEUTRAL"              # ACCUMULATING / DISTRIBUTING / NEUTRAL
    trend_strength: float = 0.0         # 0-100

    # Intensity (so với tổng volume)
    avg_foreign_pct: float = 0.0        # % TB tham gia khối ngoại
    intensity_score: float = 0.0        # 0-100 (dựa trên độ mạnh giao dịch)

    # Recent momentum
    net_value_5d: float = 0.0           # Mua ròng 5 ngày gần nhất
    momentum: str = "NEUTRAL"           # ACCELERATING / DECELERATING / NEUTRAL

    # Signals
    is_accumulating: bool = False
    is_distributing: bool = False
    consecutive_buy_days: int = 0
    consecutive_sell_days: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# HISTORICAL FOREIGN TRACKER
# ══════════════════════════════════════════════════════════════════════════════

class HistoricalForeignTracker:
    """
    Theo dõi và cache daily foreign flow data

    Usage:
        tracker = HistoricalForeignTracker()

        # Save today's foreign flow
        tracker.save_daily_flow("VCB", buy_value, sell_value, price, volume)

        # Get rolling analysis
        analysis = tracker.calculate_rolling_metrics("VCB")
        print(f"Net 20d: {analysis.net_value_20d/1e9:.1f}B, Trend: {analysis.trend}")

        # Get the missing field value
        net_buy_20d = tracker.get_foreign_net_buy_20d("VCB")
    """

    def __init__(self, cache_dir: str = "./cache/historical/foreign"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_days = 30

        # Thresholds for accumulation/distribution detection
        self.accumulation_min_buy_days = 12   # >= 12/20 ngày mua ròng
        self.distribution_min_sell_days = 12  # >= 12/20 ngày bán ròng
        self.significant_net_threshold = 1e9  # 1 tỷ VND

    def _get_cache_file(self, symbol: str) -> Path:
        return self.cache_dir / f"foreign_flow_{symbol}.json"

    def _load_history(self, symbol: str) -> List[DailyForeignFlow]:
        """Load history from cache"""
        cache_file = self._get_cache_file(symbol)

        if not cache_file.exists():
            return []

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                flows = data.get('daily_flows', [])
                return [DailyForeignFlow.from_dict(d) for d in flows]
        except Exception as e:
            print(f"   Warning: Could not load foreign history for {symbol}: {e}")
            return []

    def _save_history(self, symbol: str, flows: List[DailyForeignFlow],
                      analysis: ForeignFlowAnalysis = None) -> bool:
        """Save history to cache"""
        cache_file = self._get_cache_file(symbol)

        try:
            data = {
                'symbol': symbol,
                'last_updated': datetime.now().isoformat(),
                'count': len(flows),
                'daily_flows': [f.to_dict() for f in flows]
            }

            if analysis:
                data['analysis'] = {
                    'net_value_20d': analysis.net_value_20d,
                    'trend': analysis.trend,
                    'intensity_score': analysis.intensity_score,
                    'buy_days_count': analysis.buy_days_count,
                    'sell_days_count': analysis.sell_days_count,
                }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"   Error saving foreign history for {symbol}: {e}")
            return False

    def save_daily_flow(self, symbol: str,
                        buy_value: float = 0,
                        sell_value: float = 0,
                        buy_volume: int = 0,
                        sell_volume: int = 0,
                        price: float = 0,
                        total_volume: int = 0,
                        date: str = None) -> bool:
        """
        Save today's foreign flow data

        Args:
            symbol: Stock symbol
            buy_value: Foreign buy value in VND
            sell_value: Foreign sell value in VND
            buy_volume: Foreign buy volume in shares
            sell_volume: Foreign sell volume in shares
            price: Closing price
            total_volume: Total session volume
            date: Date string (YYYY-MM-DD), defaults to today

        Returns:
            True if saved successfully
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')

        # Calculate net values
        net_value = buy_value - sell_value
        net_volume = buy_volume - sell_volume

        # Calculate foreign percentage
        foreign_volume = buy_volume + sell_volume
        foreign_pct = (foreign_volume / total_volume * 100) if total_volume > 0 else 0

        flow = DailyForeignFlow(
            date=date,
            symbol=symbol,
            buy_value=buy_value,
            sell_value=sell_value,
            net_value=net_value,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            net_volume=net_volume,
            price=price,
            total_volume=total_volume,
            foreign_pct=foreign_pct
        )

        # Load existing
        history = self._load_history(symbol)

        # Check if date exists
        existing_idx = next((i for i, f in enumerate(history) if f.date == date), None)

        if existing_idx is not None:
            history[existing_idx] = flow
        else:
            history.append(flow)

        # Sort by date
        history.sort(key=lambda f: f.date)

        # Keep only last max_days
        if len(history) > self.max_days:
            history = history[-self.max_days:]

        # Calculate analysis and save
        analysis = self._calculate_analysis(symbol, history)
        return self._save_history(symbol, history, analysis)

    def save_daily_flow_from_data(self, symbol: str, data: Any) -> bool:
        """
        Save foreign flow from EnhancedStockData object

        Args:
            symbol: Stock symbol
            data: EnhancedStockData or similar object with foreign data

        Returns:
            True if saved
        """
        # Extract foreign data from object
        buy_value = getattr(data, 'foreign_buy_value', 0) or 0
        sell_value = getattr(data, 'foreign_sell_value', 0) or 0
        buy_volume = int(getattr(data, 'foreign_buy_volume', 0) or 0)
        sell_volume = int(getattr(data, 'foreign_sell_volume', 0) or 0)
        price = getattr(data, 'price', 0) or getattr(data, 'close', 0) or 0
        total_volume = int(getattr(data, 'volume', 0) or 0)

        return self.save_daily_flow(
            symbol=symbol,
            buy_value=buy_value,
            sell_value=sell_value,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            price=price,
            total_volume=total_volume
        )

    def _calculate_analysis(self, symbol: str,
                            history: List[DailyForeignFlow]) -> ForeignFlowAnalysis:
        """Calculate rolling metrics from history"""

        analysis = ForeignFlowAnalysis(
            symbol=symbol,
            analysis_date=datetime.now().strftime('%Y-%m-%d'),
            days_analyzed=len(history)
        )

        # Set data coverage
        analysis.data_coverage_pct = min(100, len(history) / 20 * 100)
        analysis.is_data_complete = len(history) >= 20

        if not history:
            analysis.trend = "NO_DATA"
            return analysis

        # Use last 20 days for rolling metrics
        h20 = history[-20:] if len(history) >= 20 else history
        h5 = history[-5:] if len(history) >= 5 else history

        # Calculate 20-day metrics
        analysis.net_value_20d = sum(f.net_value for f in h20)
        analysis.total_buy_20d = sum(f.buy_value for f in h20)
        analysis.total_sell_20d = sum(f.sell_value for f in h20)
        analysis.avg_daily_net_20d = analysis.net_value_20d / len(h20) if h20 else 0

        # 5-day momentum
        analysis.net_value_5d = sum(f.net_value for f in h5)

        # Count buy/sell days
        for flow in h20:
            if flow.net_value > self.significant_net_threshold:
                analysis.buy_days_count += 1
            elif flow.net_value < -self.significant_net_threshold:
                analysis.sell_days_count += 1
            else:
                analysis.neutral_days_count += 1

        # Average foreign participation
        foreign_pcts = [f.foreign_pct for f in h20 if f.foreign_pct > 0]
        analysis.avg_foreign_pct = sum(foreign_pcts) / len(foreign_pcts) if foreign_pcts else 0

        # Determine trend
        if analysis.buy_days_count >= self.accumulation_min_buy_days:
            analysis.trend = ForeignTrend.ACCUMULATING.value
            analysis.is_accumulating = True
        elif analysis.sell_days_count >= self.distribution_min_sell_days:
            analysis.trend = ForeignTrend.DISTRIBUTING.value
            analysis.is_distributing = True
        else:
            analysis.trend = ForeignTrend.NEUTRAL.value

        # Trend strength (0-100)
        total_days = analysis.buy_days_count + analysis.sell_days_count + analysis.neutral_days_count
        if total_days > 0:
            if analysis.is_accumulating:
                analysis.trend_strength = (analysis.buy_days_count / total_days) * 100
            elif analysis.is_distributing:
                analysis.trend_strength = (analysis.sell_days_count / total_days) * 100
            else:
                analysis.trend_strength = 50

        # Intensity score (based on net value relative to average)
        if analysis.total_buy_20d + analysis.total_sell_20d > 0:
            net_ratio = abs(analysis.net_value_20d) / (analysis.total_buy_20d + analysis.total_sell_20d)
            analysis.intensity_score = min(100, net_ratio * 200)

        # Momentum comparison (5d vs 20d average)
        avg_5d = analysis.net_value_5d / 5 if len(h5) >= 5 else 0
        avg_20d = analysis.avg_daily_net_20d

        if avg_5d > avg_20d * 1.5 and avg_5d > 0:
            analysis.momentum = "ACCELERATING"
        elif avg_5d < avg_20d * 0.5 or (avg_5d < 0 and avg_20d > 0):
            analysis.momentum = "DECELERATING"
        else:
            analysis.momentum = "NEUTRAL"

        # Consecutive days
        analysis.consecutive_buy_days = 0
        analysis.consecutive_sell_days = 0

        for flow in reversed(history):
            if flow.net_value > 0:
                if analysis.consecutive_sell_days == 0:
                    analysis.consecutive_buy_days += 1
                else:
                    break
            elif flow.net_value < 0:
                if analysis.consecutive_buy_days == 0:
                    analysis.consecutive_sell_days += 1
                else:
                    break
            else:
                break

        return analysis

    def calculate_rolling_metrics(self, symbol: str, window: int = 20) -> ForeignFlowAnalysis:
        """
        Calculate rolling foreign flow metrics

        Args:
            symbol: Stock symbol
            window: Rolling window in days (default 20)

        Returns:
            ForeignFlowAnalysis with metrics
        """
        history = self._load_history(symbol)

        if not history:
            result = ForeignFlowAnalysis(symbol=symbol)
            result.trend = "NO_DATA"
            return result

        return self._calculate_analysis(symbol, history)

    def get_foreign_net_buy_20d(self, symbol: str) -> float:
        """
        Get 20-day rolling net buy value

        This implements the missing field in EnhancedStockData.foreign_net_buy_20d

        Args:
            symbol: Stock symbol

        Returns:
            Net buy value in VND (positive = net buy, negative = net sell)
            Returns partial sum if less than 20 days available
        """
        history = self._load_history(symbol)

        if not history:
            return 0.0

        # Use available data (up to 20 days)
        h20 = history[-20:]
        net_value = sum(f.net_value for f in h20)

        return net_value

    def get_data_coverage(self, symbol: str) -> dict:
        """
        Get data coverage info for a symbol

        Returns:
            Dict with coverage info
        """
        history = self._load_history(symbol)
        days_available = len(history)

        return {
            'symbol': symbol,
            'days_available': days_available,
            'days_needed': 20,
            'coverage_pct': min(100, days_available / 20 * 100),
            'is_complete': days_available >= 20,
            'message': f"{days_available}/20 ngày" if days_available < 20 else "Đủ dữ liệu"
        }

    def detect_accumulation_pattern(self, symbol: str) -> Tuple[bool, str]:
        """
        Detect if foreign investors are accumulating

        Returns:
            (is_accumulating, description)
        """
        analysis = self.calculate_rolling_metrics(symbol)

        if analysis.trend == "NO_DATA" or analysis.days_analyzed < 10:
            return False, f"Chưa đủ dữ liệu ({analysis.days_analyzed}/20 ngày)"

        if analysis.is_accumulating:
            net_b = analysis.net_value_20d / 1e9
            return True, f"TÍCH LŨY: Mua ròng {net_b:.1f}B ({analysis.buy_days_count}/20 ngày)"
        elif analysis.is_distributing:
            net_b = abs(analysis.net_value_20d) / 1e9
            return False, f"PHÂN PHỐI: Bán ròng {net_b:.1f}B ({analysis.sell_days_count}/20 ngày)"
        else:
            return False, f"Trung lập ({analysis.buy_days_count} mua, {analysis.sell_days_count} bán)"

    def get_flow_history(self, symbol: str, days: int = 20) -> List[DailyForeignFlow]:
        """Get foreign flow history"""
        history = self._load_history(symbol)
        return history[-days:] if history else []

    def get_all_symbols(self) -> List[str]:
        """Get all symbols with cached data"""
        symbols = []
        for f in self.cache_dir.glob("foreign_flow_*.json"):
            symbol = f.stem.replace("foreign_flow_", "")
            symbols.append(symbol)
        return sorted(symbols)

    def cleanup_old_data(self, older_than_days: int = 90):
        """Remove old cache files"""
        cutoff = datetime.now() - timedelta(days=older_than_days)

        for cache_file in self.cache_dir.glob("foreign_flow_*.json"):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    last_updated = datetime.fromisoformat(data.get('last_updated', ''))

                    if last_updated < cutoff:
                        cache_file.unlink()
                        print(f"   Cleaned up: {cache_file.name}")
            except:
                pass

    def get_top_accumulated(self, min_net_value: float = 10e9,
                            limit: int = 10) -> List[Tuple[str, ForeignFlowAnalysis]]:
        """
        Get top stocks with foreign accumulation

        Args:
            min_net_value: Minimum 20-day net buy (default 10B VND)
            limit: Max results

        Returns:
            List of (symbol, analysis) tuples sorted by net value
        """
        results = []

        for symbol in self.get_all_symbols():
            analysis = self.calculate_rolling_metrics(symbol)

            if analysis.is_accumulating and analysis.net_value_20d >= min_net_value:
                results.append((symbol, analysis))

        # Sort by net value descending
        results.sort(key=lambda x: x[1].net_value_20d, reverse=True)

        return results[:limit]

    def get_summary(self) -> Dict:
        """Get summary of cached data"""
        symbols = self.get_all_symbols()

        accumulating = 0
        distributing = 0
        neutral = 0

        for symbol in symbols:
            analysis = self.calculate_rolling_metrics(symbol)
            if analysis.is_accumulating:
                accumulating += 1
            elif analysis.is_distributing:
                distributing += 1
            else:
                neutral += 1

        return {
            'symbols_count': len(symbols),
            'accumulating': accumulating,
            'distributing': distributing,
            'neutral': neutral,
            'cache_dir': str(self.cache_dir),
        }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

_tracker_instance: Optional[HistoricalForeignTracker] = None


def get_foreign_tracker() -> HistoricalForeignTracker:
    """Get singleton instance of HistoricalForeignTracker"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = HistoricalForeignTracker()
    return _tracker_instance


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("HISTORICAL FOREIGN TRACKER - TEST")
    print("=" * 60)

    tracker = get_foreign_tracker()

    # Summary
    summary = tracker.get_summary()
    print(f"\nCache Summary:")
    print(f"  Symbols: {summary['symbols_count']}")
    print(f"  Accumulating: {summary['accumulating']}")
    print(f"  Distributing: {summary['distributing']}")
    print(f"  Neutral: {summary['neutral']}")

    # List symbols
    symbols = tracker.get_all_symbols()
    if symbols:
        print(f"\nCached symbols: {symbols[:10]}...")

        # Analyze first symbol
        symbol = symbols[0]
        analysis = tracker.calculate_rolling_metrics(symbol)

        print(f"\nForeign Analysis for {symbol}:")
        print(f"  Days: {analysis.days_analyzed}")
        print(f"  Net 20d: {analysis.net_value_20d/1e9:.2f}B VND")
        print(f"  Buy days: {analysis.buy_days_count}, Sell days: {analysis.sell_days_count}")
        print(f"  Trend: {analysis.trend}")
        print(f"  Momentum: {analysis.momentum}")

        # Top accumulated
        print("\nTop Accumulated (20d net buy >= 10B):")
        top = tracker.get_top_accumulated(min_net_value=10e9, limit=5)
        for sym, ana in top:
            print(f"  {sym}: +{ana.net_value_20d/1e9:.1f}B ({ana.buy_days_count} buy days)")
    else:
        print("\nNo cached data yet. Run pipeline to collect data.")

    print("\n" + "=" * 60)
