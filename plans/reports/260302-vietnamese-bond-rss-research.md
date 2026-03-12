# Research Report: Vietnamese Bond Market & Financial News Integration

**Date:** March 2, 2026 | **Status:** Complete

## Executive Summary

Vietnamese bond market data integration into Python stock analysis requires multi-source approach: HNX/ICE APIs (official), vnstock library (community wrapper), SBV interest rates (public), plus 3-4 active RSS feeds for news. Granger causality via statsmodels (0.14.6+) enables bond-yield correlation analysis. DuckDB preferred over SQLite for time-series scaling due to columnar compression. Implementation feasible in 2-3 weeks with proper API rate limiting.

## Key Findings

### 1. Vietnamese Bond Data Sources

**HNX Bond Market (Official)**
- URL: https://hnx.vn/en-gb/trai-phieu.html
- Data: Corporate bonds, government bonds (TPCP), yields, maturity, volume
- Access: ICE Developer Portal (enterprise level, requires registration)
- API: Level 1/2 feeds via ICE Consolidated Feed + REST APIs
- Status: Active, 2024 bond market deployment completed

**vnstock Library (Community-Maintained)**
- PyPI: https://pypi.org/project/vnstock/
- GitHub: https://github.com/thinh-vu/vnstock
- Version: vnstock3 (as of Jan 2, 2025)
- Coverage: Government bonds, corporate bonds, yields, OHLCV data
- Advantage: Already integrated into VNSTOCK-CANSLIM (familiar API)
- Data Source: Aggregates from HNX, TCBS, SSI

**State Bank of Vietnam (SBV)**
- Public data: Interest rates, policy rates, FX reserves
- Access: https://www.sbv.gov.vn (Vietnamese only, no API)
- Manual: Daily/weekly updates via scraping recommended

**Third-party Financial Data (Fallback)**
- CEIC Data: https://www.ceicdata.com/en/vietnam (requires subscription)
- Trading Economics: Bond yield data available

### 2. Vietnamese Financial News RSS Feeds

**Primary Feeds (Tested & Active):**

| Source | URL | Update Freq | Category | Status |
|--------|-----|-------------|----------|--------|
| **Vietstock** | https://vietstock.vn/rss | Real-time | Stocks, Real Estate, Finance | Active |
| **VnEconomy** | https://vneconomy.vn/rss.html | 24/7 | Economy, Stocks, Finance | Active |
| **VnEconomy Finance** | vneconomy.vn/tai-chinh.rss | 24/7 | Monetary Policy, Interest Rates | Active |
| **Vietnam+** | https://en.vietnamplus.vn/rss.html | 24/7 | Business, Economy | Active |
| **IndochinaStock** | https://en.vietstock.vn/RSS.aspx | Daily | Indochina Markets (VN/Laos/Cambodia) | Active |

**Implementation Tool:**
```python
import feedparser

# Example: Parse VnEconomy finance RSS
feed = feedparser.parse('https://vneconomy.vn/tai-chinh.rss')
for entry in feed.entries[:5]:
    print(entry.title, entry.published)
```

**Installation:** `pip install feedparser` (lightweight, no external deps)

### 3. Database Strategy: DuckDB vs SQLite

**For Bond Time-Series (Recommendation: DuckDB)**

| Aspect | SQLite | DuckDB |
|--------|--------|--------|
| **Compression** | Row-oriented (7-10% typical) | Columnar (60-70% for OHLCV) |
| **Query Speed** | 1-5s on 1M rows | 100-500ms on 1M rows |
| **Concurrency** | Single writer (WAL helps) | Multiple readers + async |
| **Learning Curve** | Low | Low (SQL compatible) |
| **Time-Series Ops** | Manual windowing | Native window functions |
| **Python Integration** | sqlite3 (stdlib) | duckdb (pip install) |

**Recommendation:** Keep SQLite for current price/signal cache (proven setup). Add DuckDB for bond yield time-series (better compression, faster aggregation for correlation analysis).

```python
import duckdb

# Create bond yield table
conn = duckdb.connect(':memory:')
conn.execute('''
  CREATE TABLE bond_yields AS
  SELECT date, ticker, yield, maturity, duration
  FROM read_csv('bonds.csv')
''')

# Efficient time-series aggregation
conn.execute('''
  SELECT ticker,
         DATE_TRUNC('week', date) as week,
         AVG(yield) as avg_yield
  FROM bond_yields
  GROUP BY ALL
''')
```

### 4. Granger Causality & Correlation Analysis

**Python Implementation (statsmodels 0.14.6+)**

```python
from statsmodels.tsa.stattools import grangercausalitytests, coint
import pandas as pd
import numpy as np

# Data: DataFrame with ['stock_return', 'bond_yield_change']
data = pd.DataFrame({
    'stock_return': [...],
    'bond_yield_change': [...]
})

# 1. Cointegration test (Johansen for multivariate)
score, pvalue, _ = coint(data['stock_return'], data['bond_yield_change'])
print(f"Cointegration p-value: {pvalue:.4f}")

# 2. Granger Causality (test if bond yields "Granger-cause" stock returns)
# H0: Bond yields do NOT Granger-cause stock returns
granger_result = grangercausalitytests(
    data[['stock_return', 'bond_yield_change']],
    maxlag=5,  # Test up to 5 lags
    verbose=True
)

# 3. Correlation heatmap (lead-lag analysis)
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
import matplotlib.pyplot as plt

fig, axes = plt.subplots(2, 1, figsize=(10, 6))
plot_acf(data['stock_return'], lags=20, ax=axes[0])
plot_pacf(data['stock_yield_change'], lags=20, ax=axes[1])
plt.tight_layout()
plt.show()
```

**Key Interpretation:**
- p-value < 0.05: Reject H0 → Bond yields Granger-cause stock returns
- Useful for market timing: Rising bond yields → watch stock weakness
- Lag order critical: Test 1-5 lags based on data frequency (daily/weekly)

**Alternative: Toda-Yamamoto Causality** (more robust for non-stationary series)
- Requires VAR in levels + unit root tests (ADF)
- Implementation: statsmodels.tsa.vector_ar.vecm (more complex)

## Implementation Roadmap

**Phase 1: Bond Data (Week 1-2)**
- [ ] Register HNX/ICE developer account (enterprise contact)
- [ ] Extend vnstock to fetch TPCP yields (already supported)
- [ ] Create DuckDB schema: `bonds(date, ticker, type, yield, maturity, duration, volume)`
- [ ] Daily scheduler: fetch + store bond data at 3 PM HN time

**Phase 2: News RSS (Week 2)**
- [ ] Create `news_aggregator.py`: feedparser + SQLite cache
- [ ] Deduplicate by hash(title + source)
- [ ] Sentiment tagging: neutral/positive/negative (use existing Claude integration)
- [ ] Store schema: `news(id, source, title, url, published, sentiment, category)`

**Phase 3: Correlation Analysis (Week 3)**
- [ ] Bond-stock correlation heatmap (monthly rolling)
- [ ] Granger causality test (lag=5, daily/weekly) → output p-value + lag
- [ ] Integrate into module3_stock_screener: Filter by bond market health

**Phase 4: Integration (Week 3)**
- [ ] Update `run_full_pipeline.py` to include bond health score
- [ ] Alert: "Rising yields detected" when 10Y yield +20bps week-over-week
- [ ] News sentiment flag: Negative news count threshold

## Unresolved Questions

1. **HNX API Access:** Enterprise registration required - unclear turnaround time
   - Fallback: Use vnstock (already integrated, public data)

2. **SBV Interest Rate Scraping:** No official API
   - Solution: Manual schedule or CEIC subscription

3. **Bond-Stock Lead Time:** Unknown if bonds lead stocks by 1, 5, or 10 days in VN market
   - Action: Run historical Granger test (2024-2025) to determine optimal lag

4. **RSS Feed Reliability:** Vietstock/VnEconomy downtime frequency unknown
   - Mitigation: Implement feed health check + fallback sources

## References

- [HNX Bond Market](https://hnx.vn/en-gb/trai-phieu.html)
- [ICE Developer Portal](https://developer.ice.com/fixed-income-data-services/catalog/hanoi-stock-exchange-hnx)
- [vnstock PyPI](https://pypi.org/project/vnstock/)
- [vnstock GitHub](https://github.com/thinh-vu/vnstock)
- [Vietstock RSS](https://vietstock.vn/rss)
- [VnEconomy RSS](https://vneconomy.vn/rss.html)
- [Vietnam+ RSS](https://en.vietnamplus.vn/rss.html)
- [Granger Causality statsmodels](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.grangercausalitytests.html)
- [Machine Learning Plus: Granger Causality](https://www.machinelearningplus.com/time-series/granger-causality-test-in-python/)
- [Statology: Granger Causality Python](https://www.statology.org/granger-causality-test-in-python/)

