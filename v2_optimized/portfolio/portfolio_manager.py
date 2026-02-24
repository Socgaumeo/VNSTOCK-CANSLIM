"""Core portfolio management with position tracking and risk controls."""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json


@dataclass
class Position:
    """Represents a single position in the portfolio."""
    symbol: str
    entry_date: str
    entry_price: float
    shares: int
    current_price: float = 0.0
    highest_price: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0
    pyramid_level: int = 1    # 1=pilot, 2=add, 3=full
    sector: str = ""
    signal_score: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pct: float = 0.0


@dataclass
class Portfolio:
    """Portfolio state with positions and risk constraints."""
    total_nav: float = 10_000_000_000  # 10 billion VND default
    cash: float = 10_000_000_000
    positions: List[Position] = field(default_factory=list)
    max_positions: int = 8
    max_per_position: float = 0.15   # 15% NAV
    max_per_sector: float = 0.30     # 30% NAV

    @property
    def invested(self) -> float:
        """Total invested capital."""
        return sum(p.shares * p.current_price for p in self.positions)

    @property
    def total_value(self) -> float:
        """Total portfolio value (cash + invested)."""
        return self.cash + self.invested

    @property
    def total_pnl(self) -> float:
        """Total unrealized P&L across all positions."""
        return sum(p.unrealized_pnl for p in self.positions)

    @property
    def total_pnl_pct(self) -> float:
        """Total unrealized P&L as percentage of cost basis."""
        cost = sum(p.shares * p.entry_price for p in self.positions)
        return (self.total_pnl / cost * 100) if cost > 0 else 0.0

    @property
    def position_count(self) -> int:
        """Number of open positions."""
        return len(self.positions)


class PortfolioManager:
    """Manages portfolio state, positions, and risk constraints."""

    def __init__(self, nav: float = 10_000_000_000):
        self.portfolio = Portfolio(total_nav=nav, cash=nav)

    def add_position(self, symbol: str, entry_price: float, shares: int,
                     stop_loss: float, target: float = 0.0,
                     sector: str = "", signal_score: float = 0.0,
                     pyramid_level: int = 1) -> Tuple[bool, str]:
        """Add new position with constraint checks."""
        # Check max positions
        if self.portfolio.position_count >= self.portfolio.max_positions:
            return False, f"Max positions ({self.portfolio.max_positions}) reached"

        # Check duplicate
        existing = [p for p in self.portfolio.positions if p.symbol == symbol]
        if existing:
            return False, f"{symbol} already in portfolio"

        # Check cash
        amount = shares * entry_price
        if amount > self.portfolio.cash:
            return False, f"Insufficient cash: need {amount:,.0f}, have {self.portfolio.cash:,.0f}"

        # Check max per position
        if amount > self.portfolio.total_nav * self.portfolio.max_per_position:
            return False, f"Exceeds max position size ({self.portfolio.max_per_position*100:.0f}% NAV)"

        # Check sector concentration
        sector_exposure = sum(p.shares * p.current_price for p in self.portfolio.positions if p.sector == sector)
        if sector and (sector_exposure + amount) > self.portfolio.total_nav * self.portfolio.max_per_sector:
            return False, f"Exceeds max sector exposure ({self.portfolio.max_per_sector*100:.0f}% NAV)"

        # Add position
        pos = Position(
            symbol=symbol,
            entry_date=datetime.now().strftime('%Y-%m-%d'),
            entry_price=entry_price,
            shares=shares,
            current_price=entry_price,
            highest_price=entry_price,
            stop_loss=stop_loss,
            target=target,
            pyramid_level=pyramid_level,
            sector=sector,
            signal_score=signal_score,
        )
        self.portfolio.positions.append(pos)
        self.portfolio.cash -= amount
        return True, f"Added {shares} shares of {symbol} at {entry_price:,.0f}"

    def update_prices(self, prices: Dict[str, float]):
        """Update current prices for all positions."""
        for pos in self.portfolio.positions:
            if pos.symbol in prices:
                pos.current_price = prices[pos.symbol]
                pos.highest_price = max(pos.highest_price, pos.current_price)
                pos.unrealized_pnl = (pos.current_price - pos.entry_price) * pos.shares
                pos.unrealized_pct = (pos.current_price - pos.entry_price) / pos.entry_price * 100

    def remove_position(self, symbol: str) -> Tuple[bool, str]:
        """Close position and return cash."""
        pos = next((p for p in self.portfolio.positions if p.symbol == symbol), None)
        if not pos:
            return False, f"{symbol} not in portfolio"

        proceeds = pos.shares * pos.current_price
        self.portfolio.cash += proceeds
        self.portfolio.positions.remove(pos)
        pnl = pos.unrealized_pnl
        return True, f"Sold {symbol}: {pos.shares} shares at {pos.current_price:,.0f}, P&L={pnl:+,.0f}"

    def get_sector_exposure(self) -> Dict[str, float]:
        """Get exposure by sector as % of NAV."""
        exposure = {}
        for pos in self.portfolio.positions:
            sector = pos.sector or "UNKNOWN"
            val = pos.shares * pos.current_price
            exposure[sector] = exposure.get(sector, 0) + val
        # Convert to % of NAV
        for k in exposure:
            exposure[k] = exposure[k] / self.portfolio.total_nav * 100
        return exposure

    def generate_report(self) -> str:
        """Generate portfolio summary report."""
        p = self.portfolio
        lines = [
            "# 📊 PORTFOLIO REPORT",
            f"**NAV:** {p.total_value:,.0f} VND | **Cash:** {p.cash:,.0f} ({p.cash/p.total_nav*100:.1f}%)",
            f"**Invested:** {p.invested:,.0f} | **P&L:** {p.total_pnl:+,.0f} ({p.total_pnl_pct:+.1f}%)",
            f"**Positions:** {p.position_count}/{p.max_positions}",
            "",
            "| Symbol | Entry | Current | Shares | P&L | P&L% | Stop | Status |",
            "|--------|-------|---------|--------|-----|------|------|--------|",
        ]
        for pos in sorted(p.positions, key=lambda x: x.unrealized_pct, reverse=True):
            status = "🟢" if pos.unrealized_pct > 0 else "🔴"
            lines.append(
                f"| {pos.symbol} | {pos.entry_price:,.0f} | {pos.current_price:,.0f} | "
                f"{pos.shares:,} | {pos.unrealized_pnl:+,.0f} | {pos.unrealized_pct:+.1f}% | "
                f"{pos.stop_loss:,.0f} | {status} |"
            )

        # Sector exposure
        exposure = self.get_sector_exposure()
        if exposure:
            lines.append("\n**Sector Exposure:**")
            for sector, pct in sorted(exposure.items(), key=lambda x: -x[1]):
                lines.append(f"- {sector}: {pct:.1f}%")

        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Serialize portfolio state."""
        return {
            'nav': self.portfolio.total_nav,
            'cash': self.portfolio.cash,
            'positions': [
                {
                    'symbol': p.symbol, 'entry_date': p.entry_date,
                    'entry_price': p.entry_price, 'shares': p.shares,
                    'current_price': p.current_price, 'highest_price': p.highest_price,
                    'stop_loss': p.stop_loss, 'target': p.target,
                    'pyramid_level': p.pyramid_level, 'sector': p.sector,
                    'signal_score': p.signal_score,
                }
                for p in self.portfolio.positions
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PortfolioManager':
        """Deserialize portfolio state."""
        pm = cls(nav=data.get('nav', 10_000_000_000))
        pm.portfolio.cash = data.get('cash', pm.portfolio.total_nav)
        for pd_item in data.get('positions', []):
            pos = Position(**pd_item)
            pm.portfolio.positions.append(pos)
        return pm
