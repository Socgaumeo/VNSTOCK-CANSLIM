# Phase 04: Data Reconciliation

## Context Links
- Source: `/Users/bear1108/Documents/GitHub/baocaotaichinh-/webapp/analysis/reconciliation.py` (590 lines)
- Target: `v2_optimized/data-reconciliation-checker.py` (NEW)
- Consumer: `database/fundamental_store.py` validation, pipeline diagnostics

## Overview
- **Priority**: HIGH
- **Status**: ✅ COMPLETE
- **Description**: Port metric reconciliation logic that computes financial ratios from raw statements and compares against provided ratio values. Catches data quality issues (wrong column mapping, stale data, formula mismatches).

## Key Insights from Source

### Reconciliation Pattern
1. Fetch provided ratio (e.g., ROE = 0.21 from financial_ratios)
2. Compute from raw data (ROE = net_income / equity = 0.215)
3. Compare: delta_pct = |0.215 - 0.21| / |0.21| * 100 = 2.38%
4. Status: OK (<5%), WARN (5-10%), FAIL (>10%)

### Computable Metrics (from source)
- ROE, ROA, Net Margin, Gross Margin, EBIT Margin
- Current Ratio, Quick Ratio
- Debt/Equity, Financial Leverage
- Asset Turnover, Inventory Turnover

### Source Complexity We Skip
- DB-dependent annual_selector.py (quarterly vs annual disambiguation)
- COLUMN_ALIASES system (baocaotaichinh- specific)
- Valuation multiples (require market data cross-referencing)

## Requirements

### Functional
- `reconcile_metric(metric_name, computed_value, provided_value, tolerance)` -> result dict
- `compute_ratio(metric_name, income, balance, cash_flow)` -> computed value
- `reconcile_fundamentals(income, balance, cash_flow, ratios)` -> list of results
- Tolerance defaults: 5% for ratios, 3% for margins, 10% for multiples

### Non-Functional
- File under 150 lines
- Diagnostic tool (run occasionally, not per-stock in pipeline)
- Stateless functions

## Architecture

### Input Contract

```python
# Pre-fetched financial data (from database or API)
income_statement = {
    'revenue': float, 'gross_profit': float, 'operating_profit': float,
    'net_income': float, 'cost_of_goods_sold': float
}
balance_sheet = {
    'total_assets': float, 'current_assets': float, 'current_liabilities': float,
    'total_equity': float, 'total_liabilities': float, 'inventory': float
}
ratios_provided = {
    'roe': float, 'roa': float, 'net_profit_margin': float,
    'gross_margin': float, 'current_ratio': float, 'debt_to_equity': float,
    'asset_turnover': float
}
```

### Output Contract

```python
{
    'results': [
        {
            'metric': 'roe',
            'computed': 0.215,
            'provided': 0.21,
            'delta_pct': 2.38,
            'status': 'OK',       # OK/WARN/FAIL/MISSING
            'formula': 'net_income / total_equity',
        },
        ...
    ],
    'summary': {'total': 7, 'ok': 5, 'warn': 1, 'fail': 0, 'missing': 1}
}
```

## Related Code Files
- CREATE: `v2_optimized/data-reconciliation-checker.py`
- No modifications to existing files (diagnostic tool)

## Implementation Steps

1. Create `v2_optimized/data-reconciliation-checker.py`
2. Define TOLERANCES dict: `{'ratio': 0.05, 'margin': 0.03, 'multiple': 0.10}`
3. Define METRIC_FORMULAS dict mapping metric name to (formula_fn, tolerance_type)
4. Implement `_safe_divide(a, b) -> float | None`
5. Implement `compute_ratio(metric, income, balance, cash_flow) -> float | None`
   - ROE = net_income / total_equity
   - ROA = net_income / total_assets
   - Net Margin = net_income / abs(revenue)
   - Gross Margin = gross_profit / abs(revenue)
   - Current Ratio = current_assets / current_liabilities
   - Quick Ratio = (current_assets - inventory) / current_liabilities
   - Debt/Equity = total_liabilities / total_equity
   - Asset Turnover = abs(revenue) / total_assets
6. Implement `reconcile_metric(metric, computed, provided, tolerance)` -> result dict
7. Implement `reconcile_fundamentals(income, balance, cash_flow, ratios)` -> summary
8. Add CLI test block

## Todo List
- [x] Create data-reconciliation-checker.py
- [x] Define tolerance and formula maps
- [x] Implement compute_ratio for 8 metrics
- [x] Implement reconcile_metric comparison
- [x] Implement reconcile_fundamentals batch
- [x] Add CLI test
- [x] Verify < 150 lines (122 lines total)

## Success Criteria
- Correctly identifies delta between computed and provided ratios
- Handles None/zero denominators without crash
- Status thresholds: OK < tolerance, WARN < 2x tolerance, FAIL >= 2x tolerance
- File under 150 lines

## Risk Assessment
- **Low risk** - self-contained diagnostic module
- Revenue sign convention: vnstock may return positive revenue (unlike baocaotaichinh- DB). Use abs() defensively.

## Next Steps
- Can be used in `initial_sync.py` to validate data quality after sync
- Report output can be logged to `output/` directory
