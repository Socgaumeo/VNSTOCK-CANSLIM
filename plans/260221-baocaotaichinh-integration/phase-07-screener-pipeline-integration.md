# Phase 07: Screener & Pipeline Integration

## Context Links
- All new modules from Phases 01-06
- Target files to modify:
  - `v2_optimized/module3_stock_screener_v1.py`
  - `v2_optimized/data_collector.py`
  - `v2_optimized/portfolio/position_sizer.py`
  - `v2_optimized/run_full_pipeline.py`
  - `v2_optimized/run_backtest.py`

## Overview
- **Priority**: HIGH (all modules are useless without integration)
- **Status**: pending
- **Description**: Wire Phases 01-06 modules into the existing screening pipeline, position sizing, and report generation. This is the glue phase.

## Key Integration Points

### 1. Screener Scoring (module3_stock_screener_v1.py)

Current scoring: `fundamental_score = C_score * 0.6 + A_score * 0.4 + bonus`

**New bonus/penalty system:**

| Metric | Condition | Points | Source |
|--------|-----------|--------|--------|
| Piotroski F-Score | >= 7 | +5 | Phase 01 |
| Piotroski F-Score | <= 3 | -10 | Phase 01 |
| Altman Z-Score | < 1.81 (Distress) | REJECT | Phase 01 |
| Altman Z-Score | 1.81-2.99 (Grey) | -5 | Phase 01 |
| PEG Ratio | < 1.0 | +5 | Phase 02 |
| PEG Ratio | > 3.0 | -5 | Phase 02 |
| Dividend Yield | >= 4% | +3 | Phase 06 |
| Industry Health | >= 80 | +3 | Phase 05 |
| Industry Health | < 40 | -5 | Phase 05 |

**Hard reject gate:** Altman Z < 1.81 -> skip stock entirely (distress zone).

### 2. Data Collection (data_collector.py)

New data to fetch per stock:
- Balance sheet data for Piotroski/Altman (partially available from existing quarterly data)
- VNINDEX price history for Beta calculation (fetch once per run)
- Industry classification (ICB code from vnstock)
- Dividend history (from vnstock stock.finance.dividend_history())

### 3. Position Sizing (portfolio/position_sizer.py)

Add risk-based adjustments:
- If Altman Z-Score in Grey zone: reduce max_pct_nav by 30%
- If volatility_30d > 50%: reduce conviction by 1 level
- If Beta > 1.5: apply 0.8x risk budget multiplier

### 4. Pipeline Report (run_full_pipeline.py)

Add new report sections:
- Financial Health: Piotroski score + Altman zone per stock
- Valuation: PEG ratio + industry comparison
- Risk Profile: Volatility, Beta, Sharpe, Max Drawdown
- DuPont Decomposition: 5-component breakdown for top picks
- Dividend Summary: yield + consistency for dividend payers

### 5. Backtest Report (run_backtest.py)

Add risk-adjusted metrics:
- Sharpe Ratio of strategy returns
- Max Drawdown of equity curve
- Sortino Ratio

## Requirements

### Functional
- FundamentalAnalyzer.analyze() adds Piotroski, Altman, PEG to stock data
- Hard reject for Z < 1.81 before scoring
- Position sizer respects risk gates
- Reports include new analysis sections
- VNINDEX fetched once at pipeline start

### Non-Functional
- Minimize changes to existing files (additive, not restructuring)
- New imports at top of files only
- No breaking changes to existing scoring (new metrics are bonus/penalty only)

## Architecture

### Data Flow

```
data_collector.py
  |-- fetch_fundamentals() [existing]
  |-- fetch_price_history() [existing]
  |-- fetch_vnindex_history() [NEW]
  |-- fetch_dividend_history() [NEW]
  |-- fetch_industry_classification() [NEW]
       |
       v
module3_stock_screener_v1.py
  |-- FundamentalAnalyzer.analyze()
  |     |-- earnings_calculator.calculate()  [existing]
  |     |-- financial_health_scorer.calc_piotroski()  [NEW Phase 01]
  |     |-- financial_health_scorer.calc_altman_z()   [NEW Phase 01]
  |     |-- valuation_scorer.calc_peg()               [NEW Phase 02]
  |     |-- industry_analyzer.analyze_industry()       [NEW Phase 05]
  |     |
  |     v
  |-- FundamentalAnalyzer.score()
  |     |-- [existing C+A scoring]
  |     |-- + Piotroski bonus/penalty
  |     |-- + Altman hard reject
  |     |-- + PEG bonus/penalty
  |     |-- + Industry health bonus/penalty
  |     |-- + Dividend bonus
  |
  v
portfolio/position_sizer.py
  |-- calc_position()
  |     |-- [existing ATR-based sizing]
  |     |-- + Altman Grey zone reduction  [NEW]
  |     |-- + Volatility-based conviction [NEW]
  |     |-- + Beta risk multiplier        [NEW]
  |
  v
run_full_pipeline.py
  |-- [existing report sections]
  |-- + Financial Health section  [NEW]
  |-- + Valuation section         [NEW]
  |-- + Risk Profile section      [NEW]
  |-- + DuPont section            [NEW]
  |-- + Dividend section          [NEW]
```

## Related Code Files
- MODIFY: `v2_optimized/data_collector.py` (add 3 new fetch methods)
- MODIFY: `v2_optimized/module3_stock_screener_v1.py` (add scoring integration)
- MODIFY: `v2_optimized/portfolio/position_sizer.py` (add risk gates)
- MODIFY: `v2_optimized/run_full_pipeline.py` (add report sections)
- MODIFY: `v2_optimized/run_backtest.py` (add risk-adjusted metrics)

## Implementation Steps

### Step 1: Data Collector Extensions
1. Add `fetch_vnindex_history(days=365)` -> list of price dicts
2. Add `fetch_dividend_history(symbol)` -> list of {year, amount} dicts
3. Add `get_industry_classification(symbol)` -> ICB name string
4. Cache VNINDEX data (fetch once per pipeline run, reuse for all stocks)

### Step 2: Screener FundamentalData Extensions
5. Add fields to FundamentalData dataclass:
   - `piotroski_score: int = 0`
   - `altman_z_score: float = 0.0`
   - `altman_zone: str = ''`
   - `peg_ratio: float = 0.0`
   - `industry_health: float = 0.0`
   - `dividend_yield: float = 0.0`
6. In FundamentalAnalyzer.analyze():
   - After existing earnings_calculator call
   - Call financial_health_scorer functions
   - Call valuation_scorer functions
   - Call industry_analyzer if industry known
   - Map results to FundamentalData fields

### Step 3: Scoring Integration
7. In FundamentalAnalyzer.score():
   - After existing base_score + bonus calculation
   - Add Piotroski bonus (+5 if >=7) / penalty (-10 if <=3)
   - Add Altman hard reject (return -1 or skip if Z < 1.81)
   - Add PEG bonus/penalty
   - Add industry health bonus/penalty
   - Add dividend yield bonus
   - Cap total at 0-100

### Step 4: Position Sizer Risk Gates
8. Add optional parameters to calc_position():
   - `altman_zone: str = 'safe'`
   - `volatility_30d: float = 0`
   - `beta: float = 1.0`
9. Apply adjustments:
   - Grey zone: max_pct_nav *= 0.7
   - High vol (>50%): conviction down 1 level
   - High beta (>1.5): risk_pct *= 0.8

### Step 5: Report Enhancements
10. In run_full_pipeline.py report generation:
    - Add "Financial Health" section with Piotroski + Altman per stock
    - Add "Valuation" section with PEG ratings
    - Add "Risk Profile" table with vol/beta/sharpe/mdd
    - Add "DuPont" decomposition for top 5 picks
    - Add "Dividends" section for stocks with yield > 2%

### Step 6: Backtest Enhancements
11. In run_backtest.py:
    - Compute Sharpe/Sortino/MaxDD of equity curve using risk-metrics-calculator
    - Add to backtest report markdown output

## Todo List
- [ ] Add fetch_vnindex_history to data_collector
- [ ] Add fetch_dividend_history to data_collector
- [ ] Add get_industry_classification to data_collector
- [ ] Extend FundamentalData with new fields
- [ ] Wire Phase 01 (Piotroski + Altman) into analyze()
- [ ] Wire Phase 02 (PEG) into analyze()
- [ ] Wire Phase 05 (Industry) into analyze()
- [ ] Wire Phase 06 (Dividend) into analyze()
- [ ] Add bonus/penalty/reject to score()
- [ ] Add risk gates to position_sizer
- [ ] Add Financial Health section to pipeline report
- [ ] Add Risk Profile section to pipeline report
- [ ] Add DuPont + Dividend sections to pipeline report
- [ ] Add Sharpe/MDD to backtest report
- [ ] End-to-end test: run pipeline on 5 stocks

## Success Criteria
- Pipeline runs end-to-end without errors
- Stocks with Z < 1.81 are rejected before scoring
- Piotroski/PEG bonuses appear in scoring logs
- Report contains all new sections
- Position sizes reduced for high-risk stocks
- No regression in existing CANSLIM scoring

## Risk Assessment
- **module3 is ~102KB**: Large file, risky to modify. Mitigation: changes are additive (new fields + bonus lines), not restructuring. Use grep to find exact insertion points.
- **API rate limits**: 3 new API calls per stock (dividend, industry, balance sheet). Mitigation: use existing cache, batch where possible.
- **VNINDEX not in cache**: data_collector may not support index data. Mitigation: check vnstock `stock.trading.price_history(symbol='VNINDEX')`.

## Security Considerations
- No new sensitive data handling
- No new external API keys required (uses existing vnstock)
