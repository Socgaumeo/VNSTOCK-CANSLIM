"""ATR-based position sizing for VN stock market."""
from dataclasses import dataclass


@dataclass
class PositionSize:
    """Result of position size calculation."""
    shares: int
    amount: float           # VND
    risk_amount: float      # VND at risk
    risk_pct: float         # % of NAV at risk
    risk_reward: float      # R:R ratio
    lot_adjusted: bool      # Rounded to 100-share lots
    risk_adjustments: str = ""  # Notes about risk-based reductions


class PositionSizer:
    """Calculate position size based on ATR, market condition, conviction."""

    # Risk budget by market condition
    RISK_BY_MARKET = {
        'GREEN': 0.015,   # 1.5% NAV per trade
        'YELLOW': 0.010,  # 1.0%
        'RED': 0.005,     # 0.5%
    }

    # Conviction multipliers
    CONVICTION_MULT = {
        'STRONG_BUY': 1.2,
        'BUY': 1.0,
        'WATCH': 0.5,
    }

    def calc_position(self, nav: float, entry_price: float, stop_loss: float,
                      target_price: float = None,
                      market_color: str = 'YELLOW',
                      conviction: str = 'BUY',
                      max_pct_nav: float = 0.15,
                      altman_zone: str = 'safe',
                      volatility_30d: float = 0.0,
                      beta: float = 1.0) -> PositionSize:
        """
        Calculate optimal position size.

        Args:
            nav: Total portfolio NAV in VND
            entry_price: Planned entry price
            stop_loss: Stop loss price
            target_price: Optional target for R:R calc
            market_color: GREEN/YELLOW/RED
            conviction: STRONG_BUY/BUY/WATCH
            max_pct_nav: Max % of NAV for this position (default 15%)
            altman_zone: safe/grey/distress (Altman Z-Score zone)
            volatility_30d: 30-day volatility percentage
            beta: Stock beta vs VN30 index

        Returns: PositionSize with shares rounded to 100-lot
        """
        # 1. Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share <= 0:
            return PositionSize(0, 0, 0, 0, 0, False, "")

        # 2. Risk budget
        base_risk = self.RISK_BY_MARKET.get(market_color, 0.01)
        conv_mult = self.CONVICTION_MULT.get(conviction, 1.0)
        risk_pct = base_risk * conv_mult
        risk_amount = nav * risk_pct

        # --- Risk-Based Adjustments (Phase 07 Integration) ---
        risk_notes = []
        risk_adjustment = 1.0
        adjusted_max_pct_nav = max_pct_nav

        # Altman Grey zone: reduce allocation by 30%
        if altman_zone and altman_zone.lower() == 'grey':
            adjusted_max_pct_nav *= 0.7
            risk_notes.append("Grey zone: -30% position size")

        # Altman Distress: safety net (should be filtered by screener)
        if altman_zone and altman_zone.lower() == 'distress':
            adjusted_max_pct_nav *= 0.3
            risk_notes.append("DISTRESS zone: -70% position size")

        # High volatility: reduce risk budget
        if volatility_30d > 50:
            risk_adjustment *= 0.7
            risk_notes.append(f"High volatility ({volatility_30d:.1f}%): -30% risk")

        # High beta: reduce risk budget
        if beta > 1.5:
            risk_adjustment *= 0.8
            risk_notes.append(f"High beta ({beta:.2f}): -20% risk")

        # Apply risk adjustment to risk amount
        risk_amount *= risk_adjustment

        # 3. Shares from risk
        shares_from_risk = int(risk_amount / risk_per_share)

        # 4. Max shares from NAV constraint (using adjusted max_pct_nav)
        max_amount = nav * adjusted_max_pct_nav
        shares_from_nav = int(max_amount / entry_price)

        # 5. Take minimum
        shares = min(shares_from_risk, shares_from_nav)

        # 6. Round to 100-share lots (VN market requirement)
        original_shares = shares
        shares = (shares // 100) * 100
        lot_adjusted = shares != original_shares

        if shares <= 0:
            return PositionSize(0, 0, 0, 0, 0, False, "; ".join(risk_notes) if risk_notes else "")

        amount = shares * entry_price
        actual_risk = shares * risk_per_share
        actual_risk_pct = actual_risk / nav if nav > 0 else 0

        # R:R ratio
        rr = 0.0
        if target_price and risk_per_share > 0:
            reward_per_share = abs(target_price - entry_price)
            rr = reward_per_share / risk_per_share

        # Combine risk notes
        risk_adjustment_note = "; ".join(risk_notes) if risk_notes else ""

        return PositionSize(shares, amount, actual_risk, actual_risk_pct, rr, lot_adjusted, risk_adjustment_note)

    def calc_pyramid_sizes(self, total_shares: int) -> dict:
        """
        Split total position into pyramid levels.
        Level 1 (Pilot): 30% - at pocket pivot in base
        Level 2 (Add):   50% - at breakout point
        Level 3 (Full):  20% - after successful retest
        """
        l1 = (int(total_shares * 0.30) // 100) * 100
        l2 = (int(total_shares * 0.50) // 100) * 100
        l3 = total_shares - l1 - l2
        l3 = (l3 // 100) * 100
        return {'pilot': l1, 'add': l2, 'full': l3}
