# Phase 05: BondLab + ResearchLab

## Context Links
- Parent plan: [plan.md](./plan.md)
- Dependencies: [Phase 01](./phase-01-context-memo-system.md), [Phase 02](./phase-02-expand-market-agent.md)
- Research: [Bond & RSS Research](../../plans/reports/260302-vietnamese-bond-rss-research.md)
- Architecture: [system-architecture.md](../../docs/system-architecture.md)

## Overview
- **Date**: 2026-03-02
- **Priority**: P2
- **Status**: pending
- **Effort**: 6h
- **Description**: Create `bond-lab.py` for Vietnamese government bond yield fetching and SQLite storage, plus `research-lab.py` for bond-stock Granger causality testing and rolling correlation analysis. Feed results into context memo as `bond_health` indicator for Module1 macro timing signal.

## Key Insights
- vnstock library already supports bond data retrieval (TCBS source)
- Government bond yields (TPCP) are key macro indicator: rising yields -> bearish for stocks
- Granger causality test via statsmodels determines if bond yields "predict" stock returns at various lags
- Research recommends: keep SQLite for bonds (not DuckDB) to avoid new dependency -- dataset is small (365 rows/year)
- Bond-stock lead time unknown for VN market -- test lags 1-10 days, report optimal lag
- Module1 already has `_fallback_scoring()` that sums +/- adjustments -- add bond_health adjustment

### Bond Health Scoring Logic

```
bond_health_score: -10 to +10
  - 10Y yield down 20bps/week: +5 (supportive)
  - 10Y yield up 20bps/week: -5 (headwind)
  - Yield curve steepening: +3 (recovery signal)
  - Yield curve flattening: -3 (caution)
  - Granger significant (p<0.05): amplify above by 1.5x
```

## Requirements

### Functional
- FR1: `BondLab` class fetches VN government bond yields via vnstock
- FR2: SQLite table `bond_yields` stores: date, ticker, type, yield_pct, maturity, duration
- FR3: Daily yield change, weekly change, yield curve slope computed
- FR4: `ResearchLab` class runs Granger causality test (bond yields vs VNINDEX returns)
- FR5: Rolling correlation (30-day window) between bond yield changes and stock returns
- FR6: `bond_health` score (-10 to +10) saved to context memo
- FR7: Module1 reads `bond_health` and adjusts market score by up to +/-5 points
- FR8: Granger results include: optimal lag, p-value, direction (leads/follows)

### Non-Functional
- NFR1: New dependency: `statsmodels` (for grangercausalitytests)
- NFR2: Bond data fetch < 5s (single API call)
- NFR3: Granger test < 2s (small dataset, max 500 rows)
- NFR4: Graceful skip if vnstock bond API unavailable

## Architecture

```
bond-lab.py
  |
  +-- BondLab class
  |     +-- __init__(db_path)
  |     +-- fetch_and_store() -> int        # Fetch today's yields, store in DB
  |     +-- get_yield_curve() -> dict       # Current yield curve snapshot
  |     +-- get_yield_change(days=5) -> dict # Weekly yield change
  |     +-- get_bond_health_score() -> float # Composite score (-10 to +10)
  |
  +-- database/bond_store.py
        +-- BondStore class
        +-- create_table(), insert_yield(), get_by_date_range()

research-lab.py
  |
  +-- ResearchLab class
  |     +-- __init__(bond_store, price_store)
  |     +-- granger_test(bond_series, stock_series, max_lag=10) -> dict
  |     +-- rolling_correlation(bond_series, stock_series, window=30) -> pd.Series
  |     +-- lead_lag_analysis() -> dict     # Full analysis with interpretation
  |
  +-- Output: {optimal_lag, p_value, correlation, direction, interpretation}
```

### vnstock Bond Data Access

```python
from vnstock import Vnstock

# Fetch government bond data (expected API)
stock = Vnstock()
# Method varies by vnstock version -- try:
# 1. stock.finance.bond_listing()
# 2. stock.quote.history(symbol='VN10Y', ...)
# 3. Direct TCBS API fallback
```

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS bond_yields (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    ticker TEXT NOT NULL,       -- 'VN1Y', 'VN3Y', 'VN5Y', 'VN10Y'
    type TEXT DEFAULT 'TPCP',   -- Government bond
    yield_pct REAL NOT NULL,
    maturity_years REAL,
    daily_change_bps REAL,      -- Basis points change
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, ticker)
);
CREATE INDEX IF NOT EXISTS idx_bond_date ON bond_yields(date);
```

## Related Code Files

### Create
| File | Lines | Purpose |
|------|-------|---------|
| `v2_optimized/bond-lab.py` | ~150 | Bond yield fetching + health scoring |
| `v2_optimized/research-lab.py` | ~130 | Granger causality + correlation analysis |
| `v2_optimized/database/bond_store.py` | ~90 | SQLite persistence for bond yields |

### Modify
| File | Changes |
|------|---------|
| `v2_optimized/database/__init__.py` | Add BondStore to exports |
| `v2_optimized/module1_market_timing_v2.py` | Read bond_health from memo, adjust score |
| `v2_optimized/run_full_pipeline.py` | Call bond-lab fetch before Module1 |

### Delete
None.

## Implementation Steps

0. **[GATE] Validate vnstock Bond API Availability**
   - Run validation script before any Phase 5 implementation:
     ```python
     from vnstock import Vnstock
     stock = Vnstock()
     # Try known methods: stock.finance.bond_listing(), stock.quote.history('VN10Y'), etc.
     # If ALL methods fail: STOP Phase 5, report to user, consider CSV fallback
     ```
   - **If API unavailable**: Phase 5 is BLOCKED. Pivot to manual CSV or defer.
   - **If API available**: Document working method and proceed.

1. **Create `database/bond_store.py`**
   - Follow BaseStore pattern from existing stores
   - `create_table()`: bond_yields schema above
   - `insert_yield(date, ticker, yield_pct, maturity, daily_change)`: INSERT OR REPLACE
   - `get_by_date_range(ticker, start, end)`: SELECT ordered by date
   - `get_latest(ticker)`: most recent yield for given tenor
   - `get_yield_curve(date)`: all tickers for given date -> dict

2. **Create `bond-lab.py`**
   - `BondLab.__init__()`: init BondStore, configure tickers
   - `fetch_and_store() -> int`:
     - Try vnstock bond API (explore available methods)
     - Parse yields for: VN1Y, VN3Y, VN5Y, VN10Y
     - Compute daily_change_bps = (today_yield - yesterday_yield) * 100
     - Store in bond_store
     - Return count of new entries
   - `get_yield_curve() -> dict`:
     - Latest yields for all tenors
     - `{"VN1Y": 4.5, "VN3Y": 5.2, "VN5Y": 5.8, "VN10Y": 6.1}`
   - `get_yield_change(days=5) -> dict`:
     - Change in bps over N days for each tenor
     - `{"VN10Y": {"current": 6.1, "change_bps": -15, "direction": "down"}}`
   - `get_bond_health_score() -> float`:
     - 10Y weekly change: up 20+bps -> -5, down 20+bps -> +5
     - Yield curve slope (10Y - 1Y): steepening -> +3, flattening -> -3
     - Clamp to [-10, +10]
     - Return score with interpretation string

3. **Create `research-lab.py`**
   - `ResearchLab.__init__(bond_store, price_store)`: init with data sources
   - `_prepare_series(days=180) -> tuple[pd.Series, pd.Series]`:
     - Bond: daily 10Y yield changes (bps)
     - Stock: daily VNINDEX returns (%)
     - Align dates, drop NaN
     - Require min 60 data points
   - `granger_test(max_lag=10) -> dict`:
     - Import `from statsmodels.tsa.stattools import grangercausalitytests`
     - Test H0: bond yields do NOT Granger-cause stock returns
     - Return: `{optimal_lag, p_value, significant: bool, f_stat}`
   - `rolling_correlation(window=30) -> pd.Series`:
     - `bond_changes.rolling(window).corr(stock_returns)`
     - Return series with timestamps
   - `lead_lag_analysis() -> dict`:
     - Run granger_test
     - Run rolling_correlation
     - Interpret: "Bond yields lead stocks by N days (p=X)"
     - Return full results dict

4. **Update `database/__init__.py`**
   - Add `from .bond_store import BondStore`
   - Add to `__all__`

5. **Wire into pipeline**
   - In `run_full_pipeline.py`, before Module1:
     ```python
     bond_lab = _load_kebab_module(".../bond-lab.py", "bond_lab")
     if bond_lab:
         lab = bond_lab.BondLab()
         lab.fetch_and_store()
         bond_health = lab.get_bond_health_score()
         memo.save("bonds", {"bond_health": bond_health, "yield_curve": lab.get_yield_curve()})
     ```

6. **Update Module1 to read bond context**
   - In `MarketTimingModule.run()`, after scoring:
     ```python
     bond_ctx = memo.read("bonds") if memo else None
     if bond_ctx:
         bond_adj = bond_ctx.get("bond_health", 0) * 0.5  # Half weight
         self.report.market_score = max(0, min(100, self.report.market_score + bond_adj))
     ```
   - Add bond health info to AI context builder

7. **Run research analysis periodically**
   - `research-lab.py` Granger test runs weekly (not every pipeline run)
   - Store results in memo: `memo.save("research", granger_results)`
   - Module1 reads significance to weight bond_health adjustment

## Todo List

- [ ] Create `database/bond_store.py` with schema + CRUD
- [ ] Create `bond-lab.py` with BondLab class
- [ ] Explore vnstock bond API methods (test availability)
- [ ] Implement yield curve snapshot
- [ ] Implement weekly yield change calculation
- [ ] Implement bond_health_score (-10 to +10)
- [ ] Create `research-lab.py` with ResearchLab class
- [ ] Implement Granger causality test
- [ ] Implement rolling correlation
- [ ] Implement lead_lag_analysis with interpretation
- [ ] Update database/__init__.py
- [ ] Wire bond-lab into pipeline (before Module1)
- [ ] Update Module1 to read bond_health from memo
- [ ] Test bond data fetching
- [ ] Test Granger causality with historical data
- [ ] Validate bond_health scoring logic

## Success Criteria
- Bond yields fetched and stored in SQLite for VN1Y, VN3Y, VN5Y, VN10Y
- Bond health score (-10 to +10) computed and saved to context memo
- Module1 market score adjusted by bond health (visible in report)
- Granger causality test produces valid results with p-value
- Rolling correlation series generated for last 180 days
- Pipeline completes even if bond API unavailable (graceful skip)

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| vnstock bond API not available | H | M | Manual data entry, TCBS direct API, SBV scraping |
| Insufficient historical data for Granger | M | M | Require min 60 points, skip if insufficient |
| Bond-stock correlation noise | M | H | Require p < 0.05, weight adjustment is small (+/-5) |
| statsmodels import failure | L | L | Optional dependency, skip research-lab if missing |
| Yield curve data gaps (weekends/holidays) | L | M | Forward-fill missing dates |

## Security Considerations
- Bond yield data is public market data
- No authentication required for vnstock API
- SQLite parameterized queries
- No sensitive financial advice (research results are informational)

## Next Steps
- Phase 6 reuses BondStore pattern for asset prices
- Future: Add corporate bond yields for sector-specific analysis
- Future: Automate weekly Granger report generation
