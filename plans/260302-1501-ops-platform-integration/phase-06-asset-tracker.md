# Phase 06: Asset Tracker (Post-MVP)

## Context Links
- Parent plan: [plan.md](./plan.md)
- Dependencies: [Phase 05 - BondLab](./phase-05-bondlab-researchlab.md)
- Architecture: [system-architecture.md](../../docs/system-architecture.md)

## Overview
- **Date**: 2026-03-02
- **Priority**: P3
- **Status**: complete
- **Effort**: 4h
- **Description**: Track gold, silver, and USD/VND prices via TradingEconomics API. Store in SQLite with correlation analysis against VN indices. Provides macro context for portfolio diversification and risk assessment. Post-MVP -- lowest priority, builds on bond store pattern.

## Key Insights
- Gold, Silver, Oil prices available via TradingEconomics free guest API (no API key required)
- USD/VND rate available via same API for FX risk assessment
- Gold-stock negative correlation during stress: gold up -> stocks down (risk-off signal)
- USD/VND appreciation -> foreign outflow from VN market (investors repatriating)
- Reuse BondStore pattern for AssetStore (same schema structure)
- TradingEconomics free API provides daily updates without rate limiting concerns
- Macro signal scoring: risk-on/off/neutral in [-5,+5] range

## Requirements

### Functional
- FR1: `AssetTracker` class fetches gold, silver, USD/VND daily prices
- FR2: SQLite table `asset_prices` stores: date, asset, price, change_pct, change_1w, change_1m
- FR3: Correlation with VNINDEX computed on fetch (rolling 30-day)
- FR4: `get_macro_indicators() -> dict`: gold trend, USD/VND trend, correlation signs
- FR5: Save macro context to context memo for Module1 consumption
- FR6: Weekly summary in report: asset price table with trends

### Non-Functional
- NFR1: New dependency: `yfinance` (pip install yfinance)
- NFR2: Data fetch < 5s (3 tickers, 1 API call each)
- NFR3: Graceful failure if yfinance API unavailable
- NFR4: Minimal pipeline latency impact (run only if cache stale >6h)

## Architecture

```
asset-tracker.py
  |
  +-- AssetTracker class
  |     +-- __init__(db_path)
  |     +-- fetch_and_store() -> int        # Fetch latest prices
  |     +-- get_asset_summary() -> dict     # Current prices + changes
  |     +-- get_correlation_with_vnindex() -> dict  # 30-day rolling corr
  |     +-- get_macro_indicators() -> dict  # Interpreted signals
  |
  +-- database/asset_store.py
        +-- AssetStore class
        +-- create_table(), insert_price(), get_by_asset()

Pipeline integration:
  run_full_pipeline.py
    +-- asset_tracker.fetch_and_store()  # Before Module1
    +-- memo.save("assets", tracker.get_macro_indicators())
    +-- Module1 reads: gold_trend, usd_vnd_trend
```

### Asset Tickers

| Asset | yfinance Ticker | Purpose |
|-------|-----------------|---------|
| Gold | `GC=F` (futures) or `GLD` (ETF) | Safe haven indicator |
| Silver | `SI=F` (futures) or `SLV` (ETF) | Commodities proxy |
| USD/VND | `USDVND=X` | FX risk for foreign flows |

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS asset_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    asset TEXT NOT NULL,         -- 'GOLD', 'SILVER', 'USDVND'
    ticker TEXT NOT NULL,        -- 'GC=F', 'SI=F', 'USDVND=X'
    price REAL NOT NULL,
    change_pct REAL,            -- Daily % change
    change_1w_pct REAL,         -- 5-day % change
    change_1m_pct REAL,         -- 22-day % change
    vnindex_corr_30d REAL,      -- 30-day rolling correlation with VNINDEX
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, asset)
);
CREATE INDEX IF NOT EXISTS idx_asset_date ON asset_prices(date);
```

### Macro Indicator Interpretation

```python
def get_macro_indicators(self) -> dict:
    gold = self.get_asset_summary()["GOLD"]
    usd = self.get_asset_summary()["USDVND"]

    indicators = {
        "gold_trend": "UP" if gold["change_1w_pct"] > 1 else "DOWN" if gold["change_1w_pct"] < -1 else "FLAT",
        "usd_vnd_trend": "WEAK_VND" if usd["change_1w_pct"] > 0.5 else "STRONG_VND" if usd["change_1w_pct"] < -0.5 else "STABLE",
        "risk_signal": "RISK_OFF" if gold["change_1w_pct"] > 2 else "RISK_ON" if gold["change_1w_pct"] < -2 else "NEUTRAL",
        "fx_pressure": "NEGATIVE" if usd["change_1w_pct"] > 1 else "POSITIVE" if usd["change_1w_pct"] < -1 else "NEUTRAL",
    }

    # Composite macro score: -5 to +5
    score = 0
    if indicators["risk_signal"] == "RISK_OFF": score -= 3
    if indicators["risk_signal"] == "RISK_ON": score += 2
    if indicators["fx_pressure"] == "NEGATIVE": score -= 2
    if indicators["fx_pressure"] == "POSITIVE": score += 1
    indicators["macro_score"] = max(-5, min(5, score))

    return indicators
```

## Related Code Files

### Create
| File | Lines | Purpose |
|------|-------|---------|
| `v2_optimized/asset-tracker.py` | ~130 | Gold/silver/FX fetcher + macro indicators |
| `v2_optimized/database/asset_store.py` | ~80 | SQLite persistence for asset prices |

### Modify
| File | Changes |
|------|---------|
| `v2_optimized/database/__init__.py` | Add AssetStore |
| `v2_optimized/run_full_pipeline.py` | Optional asset tracking before Module1 |
| `v2_optimized/module1_market_timing_v2.py` | Read macro indicators from memo (minor) |

### Delete
None.

## Implementation Steps

1. **Create `database/asset_store.py`**
   - Follow BondStore pattern (Phase 05)
   - `create_table()`: asset_prices schema
   - `insert_price(date, asset, ticker, price, changes, correlation)`
   - `get_by_asset(asset, days=60)`: recent price history
   - `get_latest(asset)`: most recent price
   - `is_stale(hours=6)`: check if latest data older than threshold

2. **Create `asset-tracker.py`**
   - `AssetTracker.__init__()`: init AssetStore, configure tickers
   - `fetch_and_store() -> int`:
     - Check `is_stale(hours=6)` -- skip if fresh
     - `import yfinance as yf`
     - Fetch: `yf.download(['GC=F', 'SI=F', 'USDVND=X'], period='1mo')`
     - Compute daily/weekly/monthly changes
     - Fetch VNINDEX returns for correlation
     - Compute 30-day rolling correlation
     - Store in asset_store
   - `get_asset_summary() -> dict`:
     - Latest price, daily/weekly/monthly changes for each asset
   - `get_correlation_with_vnindex() -> dict`:
     - 30-day rolling correlation for each asset
     - `{"GOLD": -0.35, "SILVER": -0.20, "USDVND": +0.45}`
   - `get_macro_indicators() -> dict`:
     - Interpreted signals (see above)
     - Composite macro_score (-5 to +5)

3. **Update `database/__init__.py`**
   - Add `from .asset_store import AssetStore`

4. **Wire into pipeline (optional step)**
   - In `run_full_pipeline.py`, before Module1:
     ```python
     asset_tracker = _load_kebab_module(".../asset-tracker.py", "asset_tracker")
     if asset_tracker:
         tracker = asset_tracker.AssetTracker()
         tracker.fetch_and_store()
         memo.save("assets", tracker.get_macro_indicators())
     ```
   - Wrap in try/except (completely optional feature)

5. **Module1 reads macro context (minor)**
   - After bond_health adjustment:
     ```python
     asset_ctx = memo.read("assets") if memo else None
     if asset_ctx:
         macro_adj = asset_ctx.get("macro_score", 0) * 0.3
         self.report.market_score += macro_adj
     ```

6. **Add to report**
   - Add "Macro Assets" section in combined report
   - Table: Asset | Price | 1W% | 1M% | Correlation | Signal

7. **Add yfinance to dependencies**
   - `pip install yfinance`

## Todo List

- [ ] Create `database/asset_store.py`
- [ ] Create `asset-tracker.py` with AssetTracker class
- [ ] Implement yfinance data fetching
- [ ] Implement daily/weekly/monthly change calculation
- [ ] Implement VNINDEX correlation computation
- [ ] Implement macro indicators interpretation
- [ ] Implement staleness check (skip if <6h old)
- [ ] Update database/__init__.py
- [ ] Wire into pipeline (optional feature)
- [ ] Add macro assets section to report
- [ ] Test yfinance data availability
- [ ] Test correlation calculation
- [ ] Validate macro scoring logic

## Success Criteria
- Gold, silver, USD/VND prices fetched and stored daily
- Macro indicators computed with meaningful interpretation
- Correlation with VNINDEX visible in report
- Pipeline completes even if yfinance unavailable
- Data staleness check prevents redundant API calls

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| yfinance rate limiting | L | M | Cache for 6h, single batch fetch |
| yfinance API changes | M | L | Pin version, fallback to manual entry |
| Gold-VN correlation weak | L | H | Informational only, small score weight (0.3x) |
| USD/VND data gaps | L | M | Forward-fill, mark as stale |

## Security Considerations
- yfinance uses public Yahoo Finance data
- No API key required
- No sensitive data exposed
- Minimal score impact (max +/-1.5 points via macro_score * 0.3)

## Next Steps
- Future: Web dashboard with real-time asset tracking
- Future: Portfolio mark-to-market using asset prices
- Future: Alert system for significant gold/FX moves
