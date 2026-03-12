# Phase 05: Industry-Specific Analysis

## Context Links
- Source Banking: `/Users/bear1108/Documents/GitHub/baocaotaichinh-/webapp/analysis/banking_analysis.py` (746 lines)
- Source Real Estate: `/Users/bear1108/Documents/GitHub/baocaotaichinh-/webapp/analysis/realestate_analysis.py` (910 lines)
- Source Retail: `/Users/bear1108/Documents/GitHub/baocaotaichinh-/webapp/analysis/retail_analysis.py` (950 lines)
- Source Router: `/Users/bear1108/Documents/GitHub/baocaotaichinh-/webapp/analysis/industry_router.py` (371 lines)
- Target: `v2_optimized/industry-analyzer.py` (NEW)
- Consumer: `module2_sector_rotation_v3.py`, `module3_stock_screener_v1.py`

## Overview
- **Priority**: MEDIUM
- **Status**: COMPLETE ✅
- **Description**: Port key industry-specific metrics for Banking, Real Estate, and Retail sectors. Source modules are 750-950 lines each; we extract only the most actionable 3-4 metrics per industry into a single compact file.

## Key Insights from Source

### Banking (from banking_analysis.py)
- **NIM** (Net Interest Margin): (Interest Income - Interest Expense) / Total Assets. Rating: >3.5% excellent, >2.5% good.
- **NPL Ratio**: Non-Performing Loans / Total Loans. Rating: <1.5% excellent, <3% acceptable.
- **Cost-to-Income**: Operating Expense / Operating Income. Rating: <40% excellent, <50% good.
- **LDR**: Loan/Deposit Ratio. Rating: 80-90% optimal for VN banks.

### Real Estate (from realestate_analysis.py)
- **Inventory/Assets Ratio**: 40-70% normal for developers. >70% concentration risk.
- **Debt/Equity**: Critical for leverage-heavy RE firms. >3x is high risk.
- **Cash/Short-term Debt**: Liquidity coverage. >1.0 safe.
- **Gross Margin**: 25-35% typical for VN RE developers.

### Retail (from retail_analysis.py)
- **Inventory Turnover**: COGS / Avg Inventory. >8x excellent.
- **DSI** (Days Sales of Inventory): 365 / Inventory Turnover. <45 days excellent.
- **SG&A Ratio**: SG&A / Revenue. Efficiency indicator.
- **Cash Conversion Cycle**: DSO + DSI - DPO. <30 days excellent.

### Industry Router Pattern
Source uses `industry_router.py` to detect industry from stock metadata and dispatch to the correct analyzer. We simplify: accept industry_code parameter.

## Requirements

### Functional
- `analyze_banking(income, balance, ratios)` -> dict with NIM, NPL, Cost/Income, LDR
- `analyze_real_estate(income, balance)` -> dict with Inv/Assets, D/E, Cash/STDebt, Margin
- `analyze_retail(income, balance)` -> dict with InvTurnover, DSI, SGA%, CCC
- `analyze_industry(industry_code, income, balance, cash_flow, ratios)` -> dispatches to correct analyzer
- `get_industry_type(icb_code)` -> 'banking'/'real_estate'/'retail'/'general'
- Return None for unsupported industries (graceful fallback to general analysis)

### Non-Functional
- File under 200 lines (3 industries * ~50 lines each + dispatcher)
- No DB access
- Compact: skip verbose Vietnamese interpretation strings

## Architecture

### Industry Detection

```python
INDUSTRY_MAP = {
    # ICB Level 2 codes (from vnstock)
    'Ngân hàng': 'banking',
    'Bất động sản': 'real_estate',
    'Bán lẻ': 'retail',
    # English fallbacks
    'Banks': 'banking',
    'Real Estate': 'real_estate',
    'Retail': 'retail',
}
```

### Output Contract

```python
# Banking
{
    'industry': 'banking',
    'metrics': {
        'nim': {'value': 3.8, 'rating': 'excellent'},
        'cost_to_income': {'value': 38.5, 'rating': 'excellent'},
        'ldr': {'value': 85.2, 'rating': 'optimal'},
    },
    'health_score': 82,  # 0-100
}

# Real Estate
{
    'industry': 'real_estate',
    'metrics': {
        'inventory_to_assets': {'value': 55.3, 'rating': 'normal'},
        'debt_to_equity': {'value': 2.1, 'rating': 'acceptable'},
        'cash_to_st_debt': {'value': 1.2, 'rating': 'safe'},
    },
    'health_score': 65,
}
```

## Related Code Files
- CREATE: `v2_optimized/industry-analyzer.py`
- MODIFY: `v2_optimized/module2_sector_rotation_v3.py` (Phase 07, add industry health)
- MODIFY: `v2_optimized/module3_stock_screener_v1.py` (Phase 07, industry-aware scoring)

## Implementation Steps

1. Create `v2_optimized/industry-analyzer.py`
2. Define INDUSTRY_MAP for ICB detection
3. Implement `_safe_div(a, b)` helper
4. Implement `_rate(value, thresholds)` -> rating string
5. Implement `analyze_banking(income, balance, ratios)`:
   - NIM = net_interest_income / total_assets (or from ratios)
   - Cost/Income = operating_expense / operating_income
   - LDR = total_loans / total_deposits (from balance)
   - Health score = weighted average of metric ratings
6. Implement `analyze_real_estate(income, balance)`:
   - Inventory/Assets = inventory / total_assets
   - D/E = total_liabilities / total_equity
   - Cash/STDebt = cash / current_liabilities
   - Gross Margin = gross_profit / revenue
7. Implement `analyze_retail(income, balance)`:
   - Inventory Turnover = abs(cogs) / inventory
   - DSI = 365 / turnover
   - SGA% = (selling_exp + admin_exp) / revenue
   - CCC requires receivables + payables (may be unavailable)
8. Implement `analyze_industry(industry_code, ...)` dispatcher
9. Implement `get_industry_type(icb_name)` lookup
10. Add CLI test block

## Todo List
- [x] Create industry-analyzer.py
- [x] Define INDUSTRY_MAP and rating thresholds
- [x] Implement analyze_banking (NIM, Cost/Income, LDR)
- [x] Implement analyze_real_estate (Inv/Assets, D/E, Cash/STDebt, GrossMargin)
- [x] Implement analyze_retail (InvTurnover, DSI, SGA%)
- [x] Implement analyze_industry dispatcher
- [x] Implement get_industry_type
- [x] Add CLI test
- [x] Verify < 200 lines (final: 140 lines)

## Success Criteria
- Banking NIM correctly computed for bank-like income statements
- Real Estate Inventory/Assets in expected 40-70% range for developers
- Retail DSI correctly derived from Inventory Turnover
- Unknown industry returns None (not crash)
- File under 200 lines

## Risk Assessment
- **Banking data format**: VN bank income statements have interest_income/interest_expense as primary items, not revenue/COGS. vnstock API may label differently. Mitigation: use flexible key lookup.
- **ICB classification**: need to verify how vnstock labels industries. May need to expand INDUSTRY_MAP.
- **200 line budget**: 3 analyzers + dispatcher is tight. Mitigation: use compact dict-based threshold configs instead of if/elif chains.

## Security Considerations
- No sensitive data
- No database writes
