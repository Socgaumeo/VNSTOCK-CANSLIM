# Phase 05: Portfolio Management & Position Sizing

## Overview
- **Priority:** P1 - High
- **Status:** Pending
- **Mô tả:** Thêm module quản lý danh mục đầu tư: pyramiding, trailing stop, position sizing dựa trên ATR và market condition, theo dõi P&L.

## Key Insights
- PROJECT_EVALUATION: "Hệ thống hiện tại chỉ đưa ra điểm mua. Với 10 tỷ, không thể all-in"
- Đề xuất: Pyramiding 30% → 50% → 20% (Pocket Pivot → Breakout → Test thành công)
- Trailing Stop: MA10 hoặc MA20 khi cổ phiếu đã vào pha chạy
- VN market T+2.5: cần tính thời gian settle khi tính position

## Requirements

### Functional
- Portfolio state tracking (holdings, cash, total NAV)
- Position sizing based on: ATR, market score, conviction level
- Pyramiding rules: pilot → add → full position
- Trailing stop logic: ATR-based + MA-based
- Risk budget: max % per position, max % per sector
- P&L tracking daily
- Watchlist management với buy zones

### Non-functional
- State persistent qua SQLite
- Export CSV cho reconciliation

## Architecture

```
v2_optimized/
├── portfolio/
│   ├── __init__.py
│   ├── portfolio_manager.py    # Core portfolio logic
│   ├── position_sizer.py      # ATR-based position sizing
│   ├── trailing_stop.py       # Stop loss management
│   └── watchlist_manager.py   # Buy zone tracking
```

## Implementation Steps

### 1. Tạo portfolio_manager.py

```python
@dataclass
class Position:
    symbol: str
    entry_date: str
    entry_price: float
    shares: int
    current_price: float
    stop_loss: float
    target: float
    pyramid_level: int  # 1=pilot, 2=add, 3=full
    sector: str
    signal_score: float

@dataclass
class Portfolio:
    total_nav: float           # Tổng NAV (VND)
    cash: float
    positions: List[Position]
    max_positions: int = 8     # Tối đa 8 vị thế
    max_per_position: float = 0.15  # Max 15% NAV/vị thế
    max_per_sector: float = 0.30    # Max 30% NAV/ngành

class PortfolioManager:
    def __init__(self, nav: float = 10_000_000_000):
        """NAV mặc định 10 tỷ VND"""

    def calc_position_size(self, symbol, entry_price, stop_loss,
                           market_score, conviction) -> int:
        """
        Position Size = Risk Budget / (Entry - Stop Loss)

        Risk Budget rules:
        - Market GREEN (score >= 60): Risk 1.5% NAV per trade
        - Market YELLOW (score >= 40): Risk 1.0% NAV per trade
        - Market RED (score < 40): Risk 0.5% NAV per trade

        Conviction multiplier:
        - STRONG_BUY: 1.2x
        - BUY: 1.0x
        - WATCH: 0.5x (pilot only)
        """

    def add_position(self, symbol, price, shares, stop_loss, target, sector):
        """Thêm vị thế mới, check constraints"""

    def pyramid_position(self, symbol, price, shares):
        """
        Pyramiding rules:
        Level 1 (Pilot): 30% planned size - tại Pocket Pivot trong nền giá
        Level 2 (Add):   50% planned size - tại Breakout point
        Level 3 (Full):  20% planned size - khi test lại thành công + đã có lãi
        """

    def check_stops(self, current_prices: Dict[str, float]):
        """Check trailing stops cho tất cả positions"""

    def daily_update(self):
        """Update P&L, check stops, generate alerts"""

    def generate_report(self) -> str:
        """Báo cáo portfolio: holdings, P&L, risk exposure"""
```

### 2. Tạo position_sizer.py

```python
class PositionSizer:
    def calc_shares(self, nav, entry, stop, market_score, conviction) -> int:
        """
        ATR-based sizing:
        1. risk_pct = base_risk * market_mult * conviction_mult
        2. risk_amount = nav * risk_pct
        3. risk_per_share = entry - stop
        4. shares = risk_amount / risk_per_share
        5. Adjust for lot size (100 shares), max_per_position constraint
        """

    def calc_risk_reward(self, entry, stop, target) -> float:
        """R:R ratio, minimum 2:1 để mua"""
```

### 3. Tạo trailing_stop.py

```python
class TrailingStopManager:
    def calc_stop(self, position, df) -> float:
        """
        Stop loss strategies:
        1. Initial: -7% from entry (hard stop)
        2. After +5%: Move to breakeven
        3. After +10%: Trail MA10
        4. After +20%: Trail MA20 hoặc -10% from highest
        5. Emergency: Floor price (sàn) triggered
        """

    def should_sell(self, position, current_price, df) -> tuple:
        """Returns (should_sell: bool, reason: str)"""
```

### 4. Tạo watchlist_manager.py

```python
class WatchlistManager:
    def add_to_watchlist(self, symbol, buy_zone_low, buy_zone_high,
                         stop_loss, target, notes):
        """Thêm mã vào watchlist với buy zone"""

    def check_alerts(self, current_prices) -> List[str]:
        """
        Alert khi:
        - Giá vào buy zone
        - Giá vượt buy point (breakout)
        - Volume surge (> 1.5x avg)
        - Giá hit stop loss
        """

    def generate_daily_watchlist(self) -> str:
        """Markdown watchlist với status"""
```

## Todo List
- [ ] Tạo portfolio/ directory
- [ ] Viết portfolio_manager.py
- [ ] Viết position_sizer.py
- [ ] Viết trailing_stop.py
- [ ] Viết watchlist_manager.py
- [ ] Tích hợp với SQLite (positions table, watchlist table)
- [ ] Tích hợp với run_full_pipeline.py (auto-check stops)
- [ ] Thêm portfolio section trong báo cáo cuối ngày
- [ ] Test: simulate 3 tháng paper trading

## Success Criteria
- Position sizing phù hợp market condition (nhỏ khi đèn đỏ)
- Trailing stop bảo vệ profit > 80% trường hợp
- Portfolio không vượt quá risk constraints
- Watchlist alert đúng thời điểm (< 1 phiên delay)

## Risk Assessment
- Paper trading ≠ real: slippage, T+2.5 timing
- Cần test kỹ trailing stop logic để tránh whipsaw
