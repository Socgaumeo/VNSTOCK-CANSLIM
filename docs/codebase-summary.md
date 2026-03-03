# VNSTOCK-CANSLIM: Codebase Summary

**Last Updated:** 2026-02-23
**Status:** All phases complete (07/07)

## System Overview

VNSTOCK-CANSLIM is a comprehensive Vietnamese stock analysis system implementing the CANSLIM methodology combined with technical analysis, volume profile, risk management, and AI-powered insights.

### Core Technologies
- **Data Source**: vnstock API (VCI/TCBS/SSI fallback)
- **Analysis Framework**: CANSLIM + Technical + Fundamental + Risk
- **Storage**: SQLite with WAL mode (thread-safe)
- **AI Providers**: Gemini 3.0 Pro, DeepSeek (configurable)
- **Python**: 3.10+

---

## v2_optimized/ Module Structure

### Data Acquisition & Storage

| File | Lines | Purpose |
|------|-------|---------|
| `config.py` | ~80 | Centralized config, API keys, singleton settings |
| `data_collector.py` | ~650 | Multi-source data fetcher (VCI/TCBS/SSI), index data, price history |
| `database/` | 4 files | SQLite cache layer with WAL mode, singleton pattern |
| `database/__init__.py` | ~20 | Package init, `get_db()` factory |
| `database/base_store.py` | ~80 | BaseStore parent class (CRUD operations) |
| `database/price_store.py` | ~120 | OHLCV data, technical indicators caching |
| `database/fundamental_store.py` | ~140 | Fundamentals, ratios, quarterly/annual caching |
| `database/signal_store.py` | ~100 | Signal persistence, scoring, performance tracking |

### Technical Analysis

| File | Lines | Purpose |
|------|-------|---------|
| `candlestick_analyzer.py` | ~180 | 12 candlestick patterns + VP zone integration |
| `chart_pattern_detector.py` | ~200 | 10 Bulkowski chart patterns (head-shoulders, triangles, etc.) |
| `volume_profile.py` | ~250 | POC, VAH, VAL, 20-bar profile |

### Fundamental & Financial Analysis

| File | Lines | Purpose |
|------|-------|---------|
| `earnings_calculator.py` | ~180 | EPS/Revenue growth, CAGR, cash flow quality, margin analysis |
| `financial_health_scorer.py` | ~112 | **NEW** Piotroski F-Score (0-9), Altman Z-Score (distress detection) |
| `valuation-scorer.py` | ~143 | **NEW** PEG ratio, valuation classification (cheap/fair/expensive) |
| `risk-metrics-calculator.py` | ~154 | **NEW** Volatility, Beta, VaR, Sharpe/Sortino ratios, max drawdown |
| `data-reconciliation-checker.py` | ~122 | **NEW** Validate computed ratios vs provided fundamentals |
| `industry_analyzer.py` | ~140 | **NEW** Banking (NIM/LDR), Real Estate (D/E), Retail (DSI/CCC) |
| `dupont-analyzer.py` | ~125 | **NEW** DuPont 5-component ROE decomposition |
| `dividend-analyzer.py` | ~86 | **NEW** Dividend yield, consistency, CAGR, payout ratio |

### Money Flow & Market Sentiment

| File | Lines | Purpose |
|------|-------|---------|
| `money_flow_analyzer.py` | ~220 | Foreign flow, distribution days, MFI, OBV |
| `market-breadth-analyzer.py` | ~150 | **NEW (Phase 02)** A/D ratio, new highs/lows, sector heatmap, sparkline trends |

### Portfolio Management

| File | Lines | Purpose |
|------|-------|---------|
| `portfolio/` | 4 files | Complete position sizing, trailing stops, watchlist management |
| `portfolio/__init__.py` | ~10 | Package init |
| `portfolio/position_sizer.py` | ~180 | ATR-based sizing, risk gates (Altman/volatility/beta), pyramid splits |
| `portfolio/trailing_stop.py` | ~120 | Dynamic trailing stops (Initial→Breakeven→MA10→MA20) |
| `portfolio/portfolio_manager.py` | ~200 | Position tracking, sector exposure, constraint checks |
| `portfolio/watchlist_manager.py` | ~160 | Buy zone alerts, breakout detection |

### Backtesting & Performance

| File | Lines | Purpose |
|------|-------|---------|
| `simple_backtester.py` | ~280 | Multi-strategy backtester with stop-loss/take-profit |
| `performance_tracker.py` | ~150 | Signal performance tracking, win rate, profit factor, MAE/MFE |
| `vn_market_optimizer.py` | ~200 | VN-specific tuning (RSI 35/65, PE liquidity, ceiling/floor) |

### Screening & Execution

| File | Lines | Purpose |
|------|-------|---------|
| `module1_market_timing_v2.py` | ~250 | Market color detection, VNINDEX analysis, Volume Profile |
| `module2_sector_rotation_v3.py` | ~220 | Sector rotation scoring, RS analysis, phase classification |
| `module3_stock_screener_v1.py` | ~102KB | **Core screener** - CANSLIM scoring with all new modules integrated |

### Analysis & Reporting

| File | Lines | Purpose |
|------|-------|---------|
| `ai_providers.py` | ~150 | Multi-AI provider abstraction (Gemini, DeepSeek), returns None on error |
| `news_analyzer.py` | ~120 | News sentiment analysis, AI-powered insights |
| `report-template-renderer.py` | ~210 | **NEW (Phase 03)** Jinja2 Markdown report generator with rule-based fallback |

### Report Templates

| File | Bytes | Purpose |
|------|-------|---------|
| `templates/base-report.md.j2` | 292 | Full report wrapper with header/footer |
| `templates/market-timing-section.md.j2` | 1379 | Market timing (Module 1) table + analysis |
| `templates/sector-rotation-section.md.j2` | 521 | Sector ranking (Module 2) + phase analysis |
| `templates/stock-picks-section.md.j2` | 2043 | Stock picks (Module 3) + trading plans |

### Pipeline & Orchestration

| File | Lines | Purpose |
|------|-------|---------|
| `context-memo.py` | ~80 | **NEW (Phase 01)** Inter-module state sharing via JSON |
| `run_full_pipeline.py` | ~200 | End-to-end pipeline orchestration, batch screening |
| `run_backtest.py` | ~150 | Backtest execution, markdown report generation |
| `initial_sync.py` | ~100 | One-time DB initialization from vnstock |

---

## Scoring System Architecture

### Technical Score (100 points)
- **RS (Relative Strength)** vs VNINDEX: 25 pts
- **MA (Moving Average)** alignment (50/200/260): 20 pts
- **Distribution Days** (1-3 day weakness): 10 pts
- **RSI (Relative Strength Index)** momentum: 10 pts
- **Volume** profile & POC alignment: 10 pts
- **Money Flow** (MFI/OBV/Foreign): 25 pts

### Fundamental Score (100+ points)
- **Earnings** (EPS growth, quality): 25 pts
- **C Score** (Chart patterns): 20 pts
- **A Score** (Accumulation/Distribution): 15 pts
- **L Score** (Long-term uprend): 15 pts
- **P Score** (Price pattern): 10 pts

### Financial Health Bonus/Penalty
- **Piotroski >= 7**: +5 points (strong fundamentals)
- **Piotroski <= 3**: -10 points (weak quality)
- **Altman Z > 2.99**: Safe zone (no penalty)
- **Altman Z 1.81-2.99**: Grey zone (-5 points)
- **Altman Z < 1.81**: Distress zone (REJECT - hard filter)

### Valuation Adjustments
- **PEG < 1**: +5 points (undervalued)
- **PEG > 3**: -5 points (overvalued)

### Industry & Income
- **Industry Health >= 80**: +3 points
- **Industry Health < 40**: -5 points
- **Dividend >= 4%**: +3 points

---

## Database Schema (SQLite)

### Tables
1. **prices** - OHLCV, technical indicators, 87 VNINDEX + stock prices
2. **fundamentals** - Annual/quarterly data, ratios, financials
3. **foreign_flows** - Foreign investment flows by date/sector
4. **signals** - CANSLIM scores, detection dates, performance tracking
5. **positions** - Portfolio positions, stops, targets, P&L

### Key Features
- **WAL Mode**: Concurrent reads, atomic writes
- **Thread-Safe**: Singleton pattern via `get_db()`
- **Cached**: Quarterly fundamentals (20 quarters), daily prices (87 rows VNINDEX)

---

## Integration Flow

```
data_collector.py
    ↓
database/ (price_store, fundamental_store, foreign_flow_store)
    ↓
Technical Analysis:
  - candlestick_analyzer.py
  - chart_pattern_detector.py
  - volume_profile.py
  - money_flow_analyzer.py
    ↓
Fundamental Analysis:
  - earnings_calculator.py
  - financial_health_scorer.py (Piotroski, Altman)
  - valuation-scorer.py
  - risk-metrics-calculator.py
  - industry_analyzer.py
  - dupont-analyzer.py
  - dividend-analyzer.py
    ↓
module3_stock_screener_v1.py
  - CANSLIM scoring (technical + fundamental + financial health + valuation + industry)
  - Altman distress hard reject
  - Position sizing via portfolio/position_sizer.py
    ↓
signal_store.py (persistence)
    ↓
Backtesting:
  - simple_backtester.py
  - performance_tracker.py
    ↓
Reporting:
  - run_full_pipeline.py
  - run_backtest.py
```

---

## File Statistics

- **Total Modules**: 35 files
- **New Modules (Phase 03)**: 1 file + 4 templates (report generation)
- **New Modules (Phase 07)**: 7 files (financial analysis integration)
- **Total LOC**: ~5,800 (excluding database schema, tests)
- **Max File Size**: 102 KB (module3_stock_screener_v1.py - too large, should be modularized in future)
- **Modularization Status**: All files <200 lines except module3

---

## Lessons Learned

1. **MultiIndex DataFrames**: vnstock returns column tuples like `('group', 'column')` — use tuple key access
2. **Fundamental Score Bug (Fixed)**: MultiIndex parsing fails silently. Solution: use `_find_column(*keywords)` helper
3. **SQLite Parameterization**: Always use `?` placeholders or whitelist table names for safety
4. **VP Zone Data**: Use SimpleNamespace (not dict) for attribute access in CandlestickAnalyzer
5. **Avoid Double-Computation**: Call `detect_all()` once, derive scores from cached results
6. **Pattern Score Capping**: Combined candlestick+chart bonus capped at 20 to prevent saturation
7. **CAGR Validity**: Only meaningful when both start/end profit are positive
8. **VN Market Adjustments**: RSI thresholds (35/65), ±7% price limits, Piotroski CFO/NI at 0.8x (not strict >1)
9. **Backtesting Reality**: Requires real signals from run_full_pipeline.py; fake data won't train correctly
10. **Phase 07 Completion**: All 7 phases of baocaotaichinh integration complete ✅
11. **AI Provider Error Handling (Phase 03)**: Return None on final failure (not error strings) for clean fallback handling
12. **Jinja2 Templates**: Use `.j2` extension, FileSystemLoader for template discovery, trim_blocks/lstrip_blocks for clean output
13. **Template Data Contracts**: Keep templates in sync with pipeline output structure; breaking changes require coordinated updates

---

## Dependencies

### Core
- `vnstock >= 3.3.0`
- `pandas >= 2.0`
- `numpy >= 1.24`
- `sqlite3` (stdlib)

### AI
- `google-generativeai >= 0.8` (Gemini)
- `httpx` (DeepSeek requests)

### Optional
- `matplotlib` (charting)
- `seaborn` (visualization)

---

## Next Steps / Future Roadmap

1. **Module 3 Refactoring**: Split 102 KB file into smaller focused modules
2. **Real-Time WebSocket**: Live VNINDEX/stock price streaming
3. **Web Dashboard**: Flask/FastAPI with PostgreSQL for multi-user portfolio tracking
4. **Risk Monitoring**: Daily alerts for position stop-loss/target management
5. **ML Enhancement**: Pattern recognition beyond Bulkowski patterns
6. **News Sentiment**: Real-time news ingestion + AI analysis

