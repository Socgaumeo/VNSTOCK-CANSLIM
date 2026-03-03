# Phase 06: DuPont Extended + Dividend Analysis

## Context Links
- Source DuPont: `/Users/bear1108/Documents/GitHub/baocaotaichinh-/webapp/analysis/dupont_extended.py` (472 lines)
- Source Dividend: `/Users/bear1108/Documents/GitHub/baocaotaichinh-/webapp/analysis/dividend_analysis.py` (430 lines)
- Target DuPont: `v2_optimized/dupont-analyzer.py` (NEW)
- Target Dividend: `v2_optimized/dividend-analyzer.py` (NEW)
- Consumer: `run_full_pipeline.py` reports, screener bonus scoring

## Overview
- **Priority**: MEDIUM
- **Status**: ✅ COMPLETE
- **Description**: Port 5-component DuPont decomposition and dividend analysis. Both are report-enhancement features, not core screening criteria.

## Key Insights from Source

### DuPont Extended (5-component)
```
ROE = Tax Burden x Interest Burden x Operating Margin x Asset Turnover x Financial Leverage
     (NI/EBT)    (EBT/EBIT)       (EBIT/Rev)         (Rev/Assets)     (Assets/Equity)
```
- Source: 200 lines of core logic + 270 lines of DB/comparison helpers
- We port: core calculation + interpretation thresholds
- Skip: DB functions, year-over-year comparison (can add later)

### Dividend Analysis
- Source queries events/dividend_history tables from baocaotaichinh- DB
- We need different data source: vnstock `stock.finance.dividend_history()`
- Core metrics: yield, payout ratio, consistency score, CAGR
- Rating: yield >=8% excellent, >=6% high, >=4% average, >=2% low

## Requirements

### Functional - DuPont
- `calculate_dupont(income, balance, ratios)` -> 5 components + reconstructed ROE
- Handle missing EBIT (fallback: operating_profit or EBT + financial_expense)
- Return component interpretation flags (strength/weakness)

### Functional - Dividend
- `calculate_dividend_metrics(div_history, current_price)` -> yield, consistency, CAGR
- `get_dividend_rating(yield_value)` -> rating string
- Accept pre-fetched dividend data (list of {year, amount} dicts)

### Non-Functional
- DuPont: under 120 lines
- Dividend: under 100 lines
- No DB access in either module

## Architecture

### DuPont Input/Output

```python
# Input
income = {'net_income': float, 'profit_before_tax': float, 'operating_profit': float, 'revenue': float}
balance = {'total_assets': float, 'total_equity': float}

# Output
{
    'roe': 0.185,
    'dupont_roe': 0.183,   # reconstructed from 5 components
    'components': {
        'tax_burden': {'value': 0.82, 'label': 'NI/EBT'},
        'interest_burden': {'value': 0.91, 'label': 'EBT/EBIT'},
        'operating_margin': {'value': 0.15, 'label': 'EBIT/Revenue'},
        'asset_turnover': {'value': 1.2, 'label': 'Revenue/Assets'},
        'financial_leverage': {'value': 1.8, 'label': 'Assets/Equity'},
    },
    'driver': 'operating_margin',  # strongest contributor
    'weakness': 'tax_burden',      # weakest component
}
```

### Dividend Input/Output

```python
# Input
div_history = [
    {'year': 2025, 'amount': 1500},   # VND per share
    {'year': 2024, 'amount': 1200},
    {'year': 2023, 'amount': 1000},
]
current_price_vnd = 45000.0

# Output
{
    'yield': 0.0333,               # 3.33%
    'yield_rating': 'Trung bình',
    'payout_ratio': None,          # requires earnings data
    'consistency': {'years_paid': 3, 'total_years': 3, 'score': 1.0, 'rating': 'Rất tốt'},
    'cagr': 0.2247,               # 22.47% growth
}
```

## Related Code Files
- CREATE: `v2_optimized/dupont-analyzer.py`
- CREATE: `v2_optimized/dividend-analyzer.py`
- MODIFY: `v2_optimized/run_full_pipeline.py` (Phase 07, add to report)
- MODIFY: `v2_optimized/module3_stock_screener_v1.py` (Phase 07, dividend bonus)

## Implementation Steps

### DuPont Analyzer
1. Create `v2_optimized/dupont-analyzer.py`
2. Implement `calculate_dupont(income, balance, ratios=None)`:
   - tax_burden = net_income / profit_before_tax
   - interest_burden = profit_before_tax / ebit
   - operating_margin = ebit / revenue
   - asset_turnover = revenue / total_assets
   - financial_leverage = total_assets / total_equity
   - dupont_roe = product of all 5
3. Identify driver (highest component) and weakness (lowest)
4. Handle None/zero with safe_divide, return partial results

### Dividend Analyzer
5. Create `v2_optimized/dividend-analyzer.py`
6. Implement `calculate_dividend_metrics(div_history, current_price_vnd)`:
   - yield = latest_dividend / current_price
   - consistency_score = years_with_dividend / total_years
   - cagr = (newest/oldest)^(1/years) - 1
7. Implement `get_dividend_rating(yield_value)` -> label + class
8. Add CLI test blocks for both

## Todo List
- [x] Create dupont-analyzer.py
- [x] Implement calculate_dupont with 5 components
- [x] Identify driver/weakness
- [x] Create dividend-analyzer.py
- [x] Implement calculate_dividend_metrics
- [x] Implement get_dividend_rating
- [x] Add CLI tests for both
- [x] Verify line counts

## Success Criteria
- DuPont: product of 5 components approximates actual ROE (within 5% tolerance)
- DuPont: correctly identifies driver and weakness
- Dividend: yield correctly computed from amount/price
- Dividend: CAGR handles 1-year data (returns simple growth)
- Both files under line limits

## Risk Assessment
- **EBIT availability**: vnstock may not provide operating_profit directly. Mitigation: fallback to profit_before_tax + interest_expense.
- **Dividend data source**: vnstock dividend_history() may return different format. Mitigation: adapter in Phase 07 data_collector changes.
- **Low priority**: these are report enrichments, not blocking for core screening.

## Next Steps
- Phase 07 wires DuPont into pipeline report as a new section
- Phase 07 adds dividend yield >4% as +3 bonus in screener
