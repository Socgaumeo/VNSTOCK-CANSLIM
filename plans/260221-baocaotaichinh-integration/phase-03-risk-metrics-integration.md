# Phase 03: Risk Metrics Integration

## Context Links
- Source: `/Users/bear1108/Documents/GitHub/baocaotaichinh-/webapp/analysis/risk_analysis.py` (979 lines)
- Target: `v2_optimized/risk-metrics-calculator.py` (NEW)
- Consumers: `portfolio/position_sizer.py`, `run_backtest.py`, reports

## Overview
- **Priority**: HIGH
- **Status**: COMPLETE
- **Description**: Port price-based risk metrics (Volatility, Beta, VaR, Sharpe, Sortino, Max Drawdown) from RiskAnalysisEngine. The source is well-structured; we adapt it to use `data_collector.py` price history format.

## Key Insights from Source

### RiskAnalysisEngine Design
- Accepts list of price dicts `[{'time': '2025-01-01', 'close': 50.0}, ...]`
- Pre-computes daily log returns in `__init__`
- Status contracts: OK, PENDING_PRICE_DATA, PENDING_MARKET_DATA, ERROR
- Min data requirements: volatility(5d), beta(10d), var/sharpe/sortino(20d), max_drawdown(2d)

### Metrics to Port
1. **Volatility** (30d/90d/1y annualized) - stddev of log returns * sqrt(252)
2. **Beta** vs VNINDEX - Cov(stock, market) / Var(market), aligned by date
3. **VaR 95%/99%** - historical percentile method
4. **Sharpe Ratio** - (annual_log_return - rf_log) / annualized_vol
5. **Sortino Ratio** - excess return / downside deviation
6. **Max Drawdown** - peak-to-trough

### What NOT to Port
- Expected Shortfall (CVaR) - nice but not actionable for CANSLIM screening
- Calmar Ratio - redundant with Sharpe + MDD
- Status contract system - overkill; simple None/error handling sufficient

## Requirements

### Functional
- `RiskCalculator` class (needs state: pre-computed returns)
- `calc_volatility(days=None)` -> annualized vol %
- `calc_beta(market_returns)` -> beta value
- `calc_var(confidence=0.95)` -> VaR %
- `calc_sharpe(risk_free_rate=0.05)` -> Sharpe ratio
- `calc_sortino(target_return=0.0)` -> Sortino ratio
- `calc_max_drawdown()` -> MDD %
- `calc_all()` -> dict with all metrics
- Min data checks: return None when insufficient data

### Non-Functional
- File under 200 lines (tight budget - skip verbose interpretations)
- No DB access; receives price lists from data_collector
- Risk-free rate default 5% (Vietnam treasury)

## Architecture

### Input Contract

```python
# Price data from data_collector.py
price_history = [
    {'time': '2025-01-02', 'close': 50.5, 'high': 51.0, 'low': 50.0},
    {'time': '2025-01-03', 'close': 51.2, ...},
    ...
]
market_history = [...]  # VNINDEX same format

# Alternative: raw numpy arrays for performance
closes = [50.5, 51.2, 50.8, ...]
market_closes = [1250.0, 1255.0, ...]
```

### Output Contract

```python
{
    'volatility_30d': 25.3,     # annualized %
    'volatility_90d': 28.1,
    'volatility_1y': 30.5,
    'beta': 1.15,
    'var_95': 3.2,              # daily VaR %
    'var_99': 4.8,
    'sharpe': 0.85,
    'sortino': 1.12,
    'max_drawdown': 18.5,       # %
    'data_days': 252,
}
```

## Related Code Files
- CREATE: `v2_optimized/risk-metrics-calculator.py`
- MODIFY: `v2_optimized/portfolio/position_sizer.py` (Phase 07, VaR-based risk gate)
- MODIFY: `v2_optimized/run_backtest.py` (Phase 07, add risk-adjusted metrics to report)

## Implementation Steps

1. Create `v2_optimized/risk-metrics-calculator.py`
2. Implement `RiskCalculator.__init__(price_history, market_history=None, risk_free_rate=0.05)`
   - Pre-compute log returns from close prices
   - Store as-of date from latest price
3. Implement `_calc_returns(prices) -> list[float]` (log returns)
4. Implement `calc_volatility(days=None) -> float | None`
   - stddev of returns * sqrt(252)
   - Return None if < 5 data points
5. Implement `calc_beta() -> float | None`
   - Align stock/market returns by date
   - Cov(stock, market) / Var(market)
   - Return None if < 10 common dates or no market data
6. Implement `calc_var(confidence=0.95) -> float | None`
   - Historical percentile (sort returns, pick tail quantile)
   - Return None if < 20 data points
7. Implement `calc_sharpe(risk_free_rate=0.05) -> float | None`
   - (annual_log_return - ln(1+rf)) / annualized_vol
8. Implement `calc_sortino(target=0.0) -> float | None`
   - Excess return / downside_deviation_annual
9. Implement `calc_max_drawdown() -> float | None`
   - Peak-to-trough from price series
10. Implement `calc_all() -> dict` convenience method
11. Add CLI test block

## Todo List
- [x] Create risk-metrics-calculator.py
- [x] Implement RiskCalculator class with log returns
- [x] Implement calc_volatility
- [x] Implement calc_beta with date alignment
- [x] Implement calc_var (historical percentile)
- [x] Implement calc_sharpe
- [x] Implement calc_sortino
- [x] Implement calc_max_drawdown
- [x] Implement calc_all convenience
- [x] Add CLI test
- [x] Verify file under 200 lines (154 lines)

## Success Criteria
- All metrics return correct values for sample data
- None returned when data insufficient (not crash/0)
- Beta aligns stock and market by date (not by index position)
- Sharpe uses log-consistent math (log returns, log risk-free)
- File under 200 lines

## Risk Assessment
- **200 line budget tight** for 7 metrics + class. Mitigation: minimize docstrings, skip rating/interpretation strings (those go in reports), use compact math.
- **VNINDEX data availability**: data_collector may not fetch VNINDEX by default. Mitigation: add VNINDEX fetch in Phase 07 integration step.
- **Performance**: 252+ daily returns per stock across 50+ stocks. Pure Python math is fine for this scale.

## Security Considerations
- No sensitive data
- No database writes
