"""Watchlist management with buy zones."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class WatchItem:
    """A stock on the watchlist with buy zone parameters."""
    symbol: str
    buy_zone_low: float
    buy_zone_high: float
    stop_loss: float
    target: float = 0.0
    notes: str = ""
    added_date: str = ""
    sector: str = ""
    score: float = 0.0


class WatchlistManager:
    """Manage buy zone watchlist for potential entries."""

    def __init__(self):
        self.items: List[WatchItem] = []

    def add(self, symbol: str, buy_zone_low: float, buy_zone_high: float,
            stop_loss: float, target: float = 0.0, notes: str = "",
            sector: str = "", score: float = 0.0) -> bool:
        """Add symbol to watchlist."""
        # Remove existing if any
        self.items = [w for w in self.items if w.symbol != symbol]
        from datetime import datetime
        item = WatchItem(
            symbol=symbol, buy_zone_low=buy_zone_low,
            buy_zone_high=buy_zone_high, stop_loss=stop_loss,
            target=target, notes=notes, sector=sector, score=score,
            added_date=datetime.now().strftime('%Y-%m-%d'),
        )
        self.items.append(item)
        return True

    def remove(self, symbol: str) -> bool:
        """Remove symbol from watchlist."""
        before = len(self.items)
        self.items = [w for w in self.items if w.symbol != symbol]
        return len(self.items) < before

    def check_alerts(self, current_prices: Dict[str, float]) -> List[str]:
        """Check which watchlist items are in buy zone or at breakout."""
        alerts = []
        for item in self.items:
            price = current_prices.get(item.symbol)
            if price is None:
                continue
            if item.buy_zone_low <= price <= item.buy_zone_high:
                alerts.append(f"🟢 {item.symbol}: IN BUY ZONE at {price:,.0f} (zone {item.buy_zone_low:,.0f}-{item.buy_zone_high:,.0f})")
            elif price > item.buy_zone_high:
                alerts.append(f"⚡ {item.symbol}: BREAKOUT at {price:,.0f} (above {item.buy_zone_high:,.0f})")
            elif price <= item.stop_loss:
                alerts.append(f"🔴 {item.symbol}: BELOW STOP at {price:,.0f} (stop {item.stop_loss:,.0f})")
        return alerts

    def generate_report(self) -> str:
        """Generate watchlist report."""
        if not self.items:
            return "## 👀 WATCHLIST\nNo items in watchlist."

        lines = [
            "## 👀 WATCHLIST",
            "| Symbol | Buy Zone | Stop | Target | Score | Notes |",
            "|--------|----------|------|--------|-------|-------|",
        ]
        for w in sorted(self.items, key=lambda x: -x.score):
            lines.append(
                f"| {w.symbol} | {w.buy_zone_low:,.0f}-{w.buy_zone_high:,.0f} | "
                f"{w.stop_loss:,.0f} | {w.target:,.0f} | {w.score:.0f} | {w.notes} |"
            )
        return "\n".join(lines)

    def to_list(self) -> list:
        """Serialize watchlist to list."""
        return [vars(w) for w in self.items]

    @classmethod
    def from_list(cls, data: list) -> 'WatchlistManager':
        """Deserialize watchlist from list."""
        wm = cls()
        for d in data:
            wm.items.append(WatchItem(**d))
        return wm
