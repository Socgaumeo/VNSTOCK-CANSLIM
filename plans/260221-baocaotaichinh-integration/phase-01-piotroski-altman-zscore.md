# Phase 01: Piotroski F-Score + Altman Z-Score

## Context Links
- Source: `/Users/bear1108/Documents/GitHub/baocaotaichinh-/webapp/analysis/core_analysis.py` (lines 148-721)
- Target: `v2_optimized/financial-health-scorer.py` (NEW)
- Consumers: `module3_stock_screener_v1.py`, `portfolio/position_sizer.py`

## Overview
- **Priority**: HIGH
- **Status**: completed
- **Description**: Port Piotroski F-Score (0-9) and Altman Z-Score from CoreAnalysisEngine into a standalone module that accepts pre-fetched financial data.

## Key Insights from Source

### Piotroski F-Score (9 criteria)
1. **ROA > 0** - uses financial_ratios ROA
2. **CFO > 0** - operating cash flow positive
3. **ROA improved** - ROA current > ROA previous
4. **CFO >= 0.8 * Net Income** - Vietnam adjustment (not strict > 1.0)
5. **Debt/Assets decreased** - long-term debt or total liabilities proxy
6. **Current Ratio improved** - from financial_ratios or computed
7. **No dilution** - shares_outstanding not increased
8. **Gross Margin improved** - from ratios or computed
9. **Asset Turnover improved** - from ratios or computed

Critical: criteria 3-9 require previous year data (YoY comparison).

### Altman Z-Score
- Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
- X1: Working Capital / Total Assets
- X2: Retained Earnings / Total Assets
- X3: EBIT / Total Assets
- X4: Market Cap / Total Liabilities (or Equity/Liabilities fallback)
- X5: Revenue / Total Assets
- Zones: >2.99 Safe, 1.81-2.99 Grey, <1.81 Distress

## Requirements

### Functional
- `calculate_piotroski_f_score(current, previous)` -> dict with score 0-9, details, rating
- `calculate_altman_z_score(balance_sheet, income_statement, market_cap)` -> dict with z_score, zone, components
- Both handle None/missing data gracefully (return score=0 with note, not crash)
- Vietnam adjustment for CFO/NI ratio (0.8x threshold)

### Non-Functional
- File under 200 lines
- No external dependencies (only stdlib + typing)
- No database access; receives pre-fetched dicts

## Architecture

### Input Contract (simplified from source)

```python
# For Piotroski:
current = {
    'roa': float,           # from financial_ratios
    'cfo': float,           # operating cash flow
    'net_income': float,
    'total_assets': float,
    'long_term_debt': float,  # or total_liabilities
    'current_assets': float,
    'current_liabilities': float,
    'shares_outstanding': float,
    'gross_profit': float,
    'revenue': float,
}
previous = { ... same keys ... }

# For Altman:
altman_input = {
    'current_assets': float,
    'current_liabilities': float,
    'total_assets': float,
    'retained_earnings': float,
    'ebit': float,          # or operating_profit
    'total_liabilities': float,
    'revenue': float,
    'market_cap': float,    # optional; fallback to equity/liabilities
    'total_equity': float,  # fallback for X4
}
```

### Output Contract

```python
# Piotroski result
{
    'score': 7,                  # 0-9
    'rating': 'Strong',          # Very Strong/Strong/Average/Weak
    'details': {
        'roa_positive': 1,
        'cfo_positive': 1,
        'roa_improved': 1,
        'cfo_gt_net_income': 1,  # Vietnam: CFO >= 0.8 * NI
        'leverage_improved': 0,
        'current_ratio_improved': 1,
        'no_dilution': 1,
        'gross_margin_improved': 1,
        'asset_turnover_improved': 0,
    }
}

# Altman result
{
    'z_score': 3.15,
    'zone': 'safe',            # safe/grey/distress
    'components': {'x1': ..., 'x2': ..., 'x3': ..., 'x4': ..., 'x5': ...},
}
```

## Related Code Files
- CREATE: `v2_optimized/financial-health-scorer.py`
- MODIFY: `v2_optimized/module3_stock_screener_v1.py` (Phase 07)
- MODIFY: `v2_optimized/portfolio/position_sizer.py` (Phase 07)

## Implementation Steps

1. Create `v2_optimized/financial-health-scorer.py`
2. Implement `calculate_piotroski_f_score(current: dict, previous: dict) -> dict`
   - Port 9 criteria from source lines 148-518
   - Simplify: remove `_get_aliases()` lookup, accept flat values directly
   - Keep Vietnam CFO/NI adjustment (0.8x threshold)
   - Handle None values with `_safe_get()` helper
3. Implement `calculate_altman_z_score(data: dict) -> dict`
   - Port from source lines 547-721
   - Accept flat dict (no multi-source constructor)
   - Market cap optional; fallback to equity/liabilities for X4
4. Add `get_financial_health_summary(current, previous, market_cap)` convenience function
5. Add CLI test block (`if __name__ == "__main__"`)

## Todo List
- [x] Create financial-health-scorer.py with module docstring
- [x] Implement _safe_get helper
- [x] Implement calculate_piotroski_f_score with 9 criteria
- [x] Implement calculate_altman_z_score with 5 components
- [x] Implement get_financial_health_summary convenience function
- [x] Add CLI test block
- [x] Run compile check
- [x] Optimize file to <200 lines (final: 112 lines)

## Success Criteria
- Piotroski returns score 0-9 with correct criteria breakdown
- Altman returns z_score with correct zone classification
- Both handle all-None input without crashing (return score=0)
- File under 200 lines
- No import errors

## Risk Assessment
- **Data availability**: vnstock quarterly data may not have all 9 Piotroski inputs (e.g., shares_outstanding). Mitigation: score available criteria only, report availability count.
- **Previous year data**: requires 2 periods of fundamentals. EarningsCalculator already caches 20 quarters. Mitigation: derive YoY from cached quarterly sums.

## Security Considerations
- No sensitive data handling
- No database writes
