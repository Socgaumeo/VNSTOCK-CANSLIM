# Phase 06: Backtesting & Performance Tracking

## Overview
- **Priority:** P1 - High
- **Status:** Pending
- **Mô tả:** Xây dựng framework backtest đơn giản để đo lường hiệu quả signals, tracking performance qua thời gian, và tối ưu tham số.

## Key Insights
- Hiện tại KHÔNG CÓ cách nào biết signals có hiệu quả hay không
- History Manager chỉ parse markdown, không track actual returns
- Cần: "Mã X được recommend ngày Y, sau 5d/20d/60d return bao nhiêu?"
- Cần: "Win rate của signals STRONG_BUY vs BUY?"
- Cần: "Pattern nào cho return tốt nhất?"

## Requirements

### Functional
- Forward-fill returns: track mỗi recommendation sau 5d, 20d, 60d
- Win rate by signal type (STRONG_BUY, BUY, WATCH)
- Win rate by pattern type (VCP, Cup&Handle, Flat Base)
- Average return by sector
- Drawdown analysis
- Signal quality scoring (nên tin signal nào?)
- Monthly performance summary

### Non-functional
- Sử dụng SQLite data (Phase 01)
- Auto-update returns khi có data mới

## Implementation Steps

### 1. Tạo performance_tracker.py

```python
@dataclass
class SignalPerformance:
    symbol: str
    signal_date: str
    signal_type: str       # STRONG_BUY, BUY, WATCH
    pattern_type: str
    entry_price: float     # Giá tại thời điểm signal
    score_total: float

    # Actual returns
    return_5d: float = None    # % return sau 5 ngày
    return_20d: float = None   # % return sau 20 ngày (1 tháng)
    return_60d: float = None   # % return sau 60 ngày (3 tháng)

    # Max favorable/adverse excursion
    max_gain: float = None     # Max gain trong 60d
    max_drawdown: float = None # Max drawdown trong 60d

class PerformanceTracker:
    def __init__(self, db):
        self.db = db

    def record_signal(self, symbol, signal_type, pattern, entry_price, score):
        """Lưu signal vào signals_history"""

    def update_returns(self):
        """
        Auto-update: query signals chưa có return data
        Fetch actual prices → calc returns
        """

    def calc_win_rate(self, signal_type=None, pattern=None, period='20d') -> Dict:
        """
        Win = return > 0
        Win rate = wins / total signals
        Avg winner, avg loser
        Profit factor = sum(wins) / abs(sum(losses))
        """

    def generate_performance_report(self) -> str:
        """
        Monthly report:
        - Total signals issued
        - Win rate by type
        - Best/worst performing picks
        - Pattern effectiveness ranking
        - Sector performance
        - Equity curve
        """
```

### 2. Tạo simple_backtester.py

```python
class SimpleBacktester:
    """
    Backtest đơn giản: "Nếu mua tất cả STRONG_BUY signals,
    bán sau 20 ngày, kết quả ra sao?"
    """

    def backtest_signals(self, start_date, end_date,
                         signal_filter='STRONG_BUY',
                         hold_days=20) -> BacktestResult:
        """
        1. Query all signals in date range
        2. For each: calc entry price, exit price (hold_days later)
        3. Aggregate: total return, win rate, max drawdown
        """

    def backtest_with_stops(self, start_date, end_date,
                            stop_pct=0.07, target_pct=0.20) -> BacktestResult:
        """
        Realistic backtest với stop loss và take profit
        Exit = earliest of: stop hit, target hit, max_hold_days
        """

    def compare_strategies(self) -> str:
        """
        So sánh:
        - Buy all STRONG_BUY vs Buy all BUY
        - VCP only vs Cup&Handle only
        - High RS (>90) vs Medium RS (70-90)
        - With volume confirm vs Without
        """
```

### 3. Tích hợp auto-tracking vào pipeline

```python
# Trong run_full_pipeline.py:
# Sau khi generate report:
# 1. Record all signals vào DB
# 2. Update returns cho signals cũ
# 3. Append performance summary vào report
```

### 4. Dashboard summary

```markdown
# PERFORMANCE TRACKING (Last 30 days)

| Metric | Value |
|--------|-------|
| Signals issued | 45 |
| Win rate (20d) | 62% |
| Avg winner | +8.3% |
| Avg loser | -4.1% |
| Profit factor | 1.85 |
| Best pick | FPT (+18.5%) |
| Worst pick | NVL (-12.3%) |

## By Signal Type
| Type | Count | Win Rate | Avg Return |
|------|-------|----------|------------|
| STRONG_BUY | 8 | 75% | +6.2% |
| BUY | 15 | 60% | +3.1% |
| WATCH | 22 | 50% | +0.8% |

## By Pattern
| Pattern | Count | Win Rate | Avg Return |
|---------|-------|----------|------------|
| VCP | 12 | 67% | +5.1% |
| Cup&Handle | 8 | 62% | +4.8% |
| Flat Base | 5 | 40% | +1.2% |
```

## Todo List
- [ ] Tạo performance_tracker.py
- [ ] Implement record_signal()
- [ ] Implement update_returns() (auto-fill từ price data)
- [ ] Implement calc_win_rate() với filters
- [ ] Tạo simple_backtester.py
- [ ] Implement backtest_signals() basic
- [ ] Implement backtest_with_stops()
- [ ] Implement compare_strategies()
- [ ] Tích hợp auto-tracking vào pipeline
- [ ] Thêm performance section vào report
- [ ] Test: backtest 6 tháng historical signals

## Success Criteria
- Return data tự động update cho > 95% signals sau 20d
- Performance report generate < 5 giây
- Backtest kết quả consistent với expectations

## Risk Assessment
- Survivorship bias: signals cho mã bị delist sẽ thiếu data
- Look-ahead bias: cần đảm bảo backtest chỉ dùng data available tại signal time
