# Phase 02: PEG Ratio + Valuation Metrics

## Context Links
- Source: `/Users/bear1108/Documents/GitHub/baocaotaichinh-/webapp/analysis/valuation_analysis.py` (lines 16-175)
- Target: `v2_optimized/valuation-scorer.py` (NEW)
- Consumer: `module3_stock_screener_v1.py` scoring bonus/penalty

## Overview
- **Priority**: HIGH
- **Status**: ✅ COMPLETE
- **Description**: Port PEG Ratio calculation and valuation comparison logic. The source module is heavily DB-dependent; we extract only the pure calculation functions.

## Key Insights from Source

### PEG Ratio
- Formula: P/E / (EPS CAGR %)
- Source calculates EPS CAGR from financial_ratios.eps_vnd over 5 years
- Rating: <1 Very Cheap, 1-2 Cheap, 2-3 Fair, >3 Expensive, <0 Negative growth

### What to Port
- `calculate_cagr(values, years)` - pure math function
- `get_peg_rating(peg_ratio)` - classification function
- `compare_valuation(company, industry, lower_is_better)` - comparison helper
- `calculate_percentiles(values)` - for historical P/E band positioning

### What NOT to Port
- `analyze_valuation()` - DB-heavy, SQL queries; not applicable
- Fair price heuristics - require DB-specific price history table
- Graham Number - nice but not critical for CANSLIM

## Requirements

### Functional
- `calculate_peg_ratio(pe_ratio, eps_values, years)` -> dict with value, rating
- `calculate_percentiles(values)` -> dict with p5/p25/p50/p75/p95
- `classify_valuation(pe, pb, industry_pe, industry_pb)` -> dict with status
- Handle None/negative inputs gracefully

### Non-Functional
- File under 150 lines (simpler module)
- Pure functions, no state

## Architecture

### Input Contract

```python
# PEG inputs (from earnings_calculator + screener data)
pe_ratio: float          # Current P/E
eps_values: list[float]  # EPS history oldest->newest (from quarterly cache)
years_span: int          # Number of years for CAGR

# Valuation comparison
company_pe: float
company_pb: float
industry_pe: float  # median from sector analysis
industry_pb: float
```

### Output Contract

```python
# PEG result
{
    'peg_ratio': 1.35,
    'rating': 'cheap',         # very_cheap/cheap/fair/expensive/negative
    'description': 'Khá rẻ - Định giá hợp lý',
    'eps_cagr': 15.2,          # % annual growth used
    'pe_used': 20.5,
}

# Valuation result
{
    'pe_vs_industry': {'company': 15.2, 'industry': 18.5, 'status': 'cheaper'},
    'pb_vs_industry': {'company': 2.1, 'industry': 2.3, 'status': 'similar'},
    'overall': 'undervalued',  # undervalued/fair/overvalued/unknown
}
```

## Related Code Files
- CREATE: `v2_optimized/valuation-scorer.py`
- MODIFY: `v2_optimized/module3_stock_screener_v1.py` (Phase 07, valuation bonus)

## Implementation Steps

1. Create `v2_optimized/valuation-scorer.py`
2. Port `calculate_cagr(values: list, years: int) -> float | None` from source lines 16-43
3. Implement `calculate_peg_ratio(pe, eps_values, years)` combining CAGR + PEG
4. Port `get_peg_rating(peg)` from source lines 110-133
5. Port `compare_valuation(company, industry, lower_is_better)` from source lines 136-174
6. Implement `classify_valuation(pe, pb, industry_pe, industry_pb)` combining comparisons
7. Port `calculate_percentiles(values)` from source lines 46-107
8. Add CLI test block

## Todo List
- [x] Create valuation-scorer.py
- [x] Implement calculate_cagr
- [x] Implement calculate_peg_ratio
- [x] Implement get_peg_rating
- [x] Implement compare_valuation
- [x] Implement classify_valuation
- [x] Implement calculate_percentiles
- [x] Add CLI test block

## Success Criteria
- PEG ratio correctly computed: P/E 20, EPS CAGR 15% -> PEG = 1.33
- Handles negative/zero growth (returns negative rating)
- Percentile function matches numpy type-7 interpolation
- File under 150 lines

## Risk Assessment
- **EPS history length**: CANSLIM cache stores 20 quarters but EPS CAGR needs annual values. Mitigation: aggregate 4Q sums for annual EPS, then compute CAGR.
- **Industry comparison data**: sector rotation module (`module2`) already collects sector stats. Can piggyback.

## Next Steps
- Phase 07 wires PEG into screener scoring: PEG<1 -> +5 bonus, PEG>3 -> -5 penalty
