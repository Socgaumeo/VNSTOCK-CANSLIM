# Phase 02: Expand Market Agent

## Context Links
- Parent plan: [plan.md](./plan.md)
- Dependencies: [Phase 01 - Context Memo](./phase-01-context-memo-system.md)
- Codebase: [module1_market_timing_v2.py](../../v2_optimized/module1_market_timing_v2.py)
- Architecture: [system-architecture.md](../../docs/system-architecture.md)

## Overview
- **Date**: 2026-03-02
- **Priority**: P1
- **Status**: complete
- **Effort**: 5h
- **Description**: Expand Module1 with VNMID/VNSML indices, full market breadth analysis (A/D ratio, New Highs/Lows), text-based sector heatmap, and Unicode sparkline trend indicators in reports.

## Key Insights
- Module1 currently tracks VNINDEX, VN30, VN100 -- missing mid/small cap signals (VNMID, VNSML)
- `MarketBreadth` dataclass (line 116) only has advances/declines/unchanged/ceiling/floor -- needs new_highs/new_lows
- Breadth calculation in `_get_market_internals()` already iterates all HOSE stocks via price_board -- extend loop
- Sparkline characters: `'_________'` maps value range to 8 Unicode bars
- Sector heatmap: Markdown table with color-coded emoji indicators (no matplotlib dependency)
- Research shows A/D ratio > 1.5 = strong breadth, < 0.7 = weak

## Requirements

### Functional
- FR1: Add VNMID, VNSML to `COMPARISON_INDICES` in MarketTimingConfig
- FR2: New `MarketBreadthAnalyzer` class computing: A/D ratio, A/D line cumulative, new 52-week highs/lows, breadth thrust indicator
- FR3: Sector heatmap as Markdown table with change% and emoji indicators
- FR4: Sparkline trend string for A/D ratio (last 10 data points from memo history)
- FR5: Breadth data saved to context memo for Module3 consumption
- FR6: Report includes breadth section between Volume Profile and Money Flow

### Non-Functional
- NFR1: No new pip dependencies (use numpy/pandas already available)
- NFR2: Breadth calculation adds < 5s to pipeline (reuse existing price_board data)
- NFR3: Heatmap renders in any Markdown viewer

## Architecture

```
module1_market_timing_v2.py
  |
  +-- MarketTimingAnalyzer.collect_data()
  |     +-- Fetch VNINDEX, VN30, VN100, VNMID, VNSML
  |     +-- _get_market_internals()
  |           +-- MarketBreadthAnalyzer.calculate(price_board_df)
  |                 +-- A/D ratio, new highs/lows, breadth thrust
  |
  +-- market-breadth-analyzer.py (NEW)
  |     +-- MarketBreadthAnalyzer class
  |     +-- calculate_breadth_metrics(df) -> dict
  |     +-- generate_sector_heatmap(sector_data) -> str
  |     +-- generate_sparkline(values) -> str
  |
  +-- context-memo.py
        +-- memo.save("module1", {...breadth_data...})
```

### Sector Heatmap Format (Markdown)

```markdown
## Sector Heatmap
| Sector | 1D | 5D | Trend | Phase |
|--------|-----|-----|-------|-------|
| VNFIN  | +1.2% | +3.5% | ________ | LEADING |
| VNREAL | -0.5% | +1.2% | ________ | IMPROVING |
| VNMAT  | -1.1% | -2.3% | ________ | WEAKENING |
```

## Related Code Files

### Create
| File | Lines | Purpose |
|------|-------|---------|
| `v2_optimized/market-breadth-analyzer.py` | ~150 | Breadth metrics, heatmap, sparkline |

### Modify
| File | Changes |
|------|---------|
| `v2_optimized/module1_market_timing_v2.py` | Add VNMID/VNSML to config, integrate breadth analyzer, update report dataclass |
| `v2_optimized/run_full_pipeline.py` | Include breadth section in combined report |

### Delete
None.

## Implementation Steps

1. **Create `market-breadth-analyzer.py`**
   - `MarketBreadthAnalyzer` class
   - `calculate_breadth_metrics(price_board_df: pd.DataFrame) -> dict`:
     - A/D ratio = advances / max(declines, 1)
     - New 52-week highs: count where `match_price >= high_52w`
     - New 52-week lows: count where `match_price <= low_52w`
     - Breadth thrust: (advances / (advances + declines)) -- bullish if > 0.615
     - Net breadth score: (advances - declines) / total * 100
   - `generate_sector_heatmap(sectors: list) -> str`:
     - Markdown table with columns: Sector, 1D%, Trend sparkline, Phase
     - Emoji: green_circle for +, red_circle for -, yellow for flat
   - `generate_sparkline(values: list) -> str`:
     - Map value list to Unicode block chars: `'_________'`
     - Return formatted: `"________ [min->current]"`

2. **Update `MarketBreadth` dataclass in module1**
   - Add fields: `new_highs: int = 0`, `new_lows: int = 0`, `breadth_thrust: float = 0.0`, `net_breadth_score: float = 0.0`

3. **Update `MarketTimingConfig`**
   - Add `"VNMID"` and `"VNSML"` to `COMPARISON_INDICES` default list
   - Add corresponding entries in `SECTOR_NAMES` dict

4. **Update `MarketTimingAnalyzer.collect_data()`**
   - Fetch VNMID and VNSML data (steps [2/7] and [3/7])
   - Store as `report.vnmid` and `report.vnsml` on MarketReport

5. **Update `_get_market_internals()`**
   - After breadth loop, calculate new highs/lows from price_board data
   - Need 52-week high/low columns -- check `listing` group in price_board response
   - If not available: fetch from `stock.quote.history(period='1Y')` for each stock (expensive) or skip with N/A

6. **Integrate breadth analyzer into module1**
   - After `_get_market_internals()`, create `MarketBreadthAnalyzer` instance
   - Call `calculate_breadth_metrics()` with collected data
   - Save results into `MarketBreadth` dataclass fields

7. **Update `_build_market_data_context()` in AI generator**
   - Add breadth metrics section: A/D ratio, new highs/lows, breadth thrust
   - Add VNMID/VNSML price and change data

8. **Update report generation in `run_full_pipeline.py`**
   - Add "Market Breadth" section after Volume Profile
   - Include sector heatmap table
   - Add sparkline for A/D trend

9. **Save breadth to context memo**
   - In module1 memo.save(), include: `new_highs`, `new_lows`, `breadth_thrust`, `net_breadth_score`, `ad_ratio`

## Todo List

- [x] Create `market-breadth-analyzer.py` with MarketBreadthAnalyzer
- [x] Implement `calculate_breadth_metrics()`
- [x] Implement `generate_sector_heatmap()`
- [x] Implement `generate_sparkline()`
- [x] Add VNMID, VNSML to module1 config
- [x] Update MarketBreadth dataclass with new fields
- [x] Update MarketReport dataclass for vnmid/vnsml
- [x] Update `collect_data()` to fetch VNMID/VNSML
- [x] Update `_get_market_internals()` for new highs/lows
- [x] Integrate breadth analyzer into module1
- [x] Update AI context builder with breadth data
- [x] Update combined report with breadth section + heatmap
- [x] Save breadth metrics to context memo
- [x] Test with full pipeline run

## Success Criteria
- VNMID and VNSML data appear in market report
- Breadth section shows A/D ratio, new highs/lows, breadth thrust
- Sector heatmap renders correctly in Markdown viewer
- Sparkline shows trend direction visually
- All breadth data available in context memo JSON

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| VNMID/VNSML API not available | M | L | Graceful skip, mark as N/A |
| 52-week high/low not in price_board | M | M | Use last 260 daily candles from price history |
| Breadth adds latency | L | M | Reuse existing price_board data (no extra API calls) |

## Security Considerations
- No new API keys required
- No sensitive data exposed
- Market breadth data is public information

## Next Steps
- Breadth metrics feed into Phase 3 deterministic fallback templates
- Phase 5 BondLab adds bond_health to memo, module1 reads it for macro signal
