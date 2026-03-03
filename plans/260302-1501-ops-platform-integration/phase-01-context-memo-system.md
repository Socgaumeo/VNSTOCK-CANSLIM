# Phase 01: Context Memo System

## Context Links
- Parent plan: [plan.md](./plan.md)
- Dependencies: None (first phase)
- Research: [Multi-Agent Patterns Report](../../plans/reports/research-multi-agent-patterns-20260302.md)
- Code standards: [code-standards.md](../../docs/code-standards.md)

## Overview
- **Date**: 2026-03-02
- **Priority**: P1
- **Status**: complete
- **Effort**: 3h
- **Description**: Create JSON file-based context memo enabling module1/2/3 to share state through the sequential pipeline. Module3 reads full context to dynamically adjust screening thresholds based on market color and sector rotation phase.

## Key Insights
- Sequential pipeline (m1->m2->m3) makes file-based JSON simplest option (no queues needed)
- `_build_market_context()` in `run_full_pipeline.py` (line 346) already builds a dict manually -- replace with memo read
- `calculate_dynamic_sl_tp()` already uses `market_score` -- extend pattern to screening thresholds
- Module3 `StockScreenerModule.run()` accepts `market_context` dict -- wire memo into this param
- JSON file survives process restarts and is human-readable for debugging

## Requirements

### Functional
- FR1: `ContextMemo.save(stage, data)` appends stage output to shared JSON
- FR2: `ContextMemo.read(stage)` returns specific stage output or full memo
- FR3: `ContextMemo.clear()` resets memo (called at pipeline start)
- FR4: Module1 saves: `market_color`, `market_score`, `risk_level`, `trend_status`, `breadth`, `top_sectors`, `vp_data`
- FR5: Module2 reads module1 context, saves: `sector_scores`, `sector_phases`, `rotation_clock`, `leading_sectors`
- FR6: Module3 reads full context, adjusts: CANSLIM thresholds (stricter RED, looser GREEN), RS minimum, volume requirements
- FR7: Memo file stored at `cache/context_memo.json`

### Non-Functional
- NFR1: File write < 10ms (small JSON, no contention)
- NFR2: Thread-safe (single writer in sequential pipeline)
- NFR3: Graceful fallback if memo file missing/corrupt (use defaults)

## Architecture

```
run_full_pipeline.py
  |
  +-- ContextMemo.clear()          # Reset at pipeline start
  |
  +-- Module1.run()
  |     +-- memo.save("module1", {market_color, score, breadth, vp...})
  |
  +-- Module2.run()
  |     +-- ctx = memo.read("module1")   # Read market context
  |     +-- memo.save("module2", {sector_scores, phases, clock...})
  |
  +-- Module3.run()
  |     +-- ctx = memo.read()            # Read FULL context
  |     +-- adjust_thresholds(ctx)       # Dynamic threshold adjustment
  |     +-- memo.save("module3", {candidates, scores...})
  |
  +-- Report generation
        +-- ctx = memo.read()            # For template rendering (Phase 3)
```

### Threshold Adjustment Logic (Module3)

```python
# Market color -> screening strictness
if market_color == "RED":
    min_rs_rating = 70        # Only strong momentum (default: 50)
    min_volume_ratio = 1.5    # Higher volume confirmation
    min_canslim_score = 65    # Higher bar
elif market_color == "GREEN":
    min_rs_rating = 40        # More permissive
    min_volume_ratio = 1.0    # Normal
    min_canslim_score = 50    # Standard
else:  # YELLOW
    min_rs_rating = 55        # Moderate
    min_volume_ratio = 1.2
    min_canslim_score = 55
```

## Related Code Files

### Create
| File | Lines | Purpose |
|------|-------|---------|
| `v2_optimized/context-memo.py` | ~80 | ContextMemo class (save/read/clear) |

### Modify
| File | Changes |
|------|---------|
| `v2_optimized/run_full_pipeline.py` | Import memo, clear() at start, replace `_build_market_context()` with memo.read() |
| `v2_optimized/module1_market_timing_v2.py` | Accept memo param, save output after scoring |
| `v2_optimized/module2_sector_rotation_v3.py` | Accept memo param, read module1, save sector output |
| `v2_optimized/module3_stock_screener_v1.py` | Read full memo, add `_adjust_thresholds_by_context()` |

### Delete
None.

## Implementation Steps

1. **Create `context-memo.py`**
   - `ContextMemo` class with `__init__(memo_path)`, `save(stage, data)`, `read(stage=None)`, `clear()`
   - JSON file at `cache/context_memo.json`
   - `save()`: load existing, merge stage key, write back with `updated_at` timestamp
   - `read()`: return full dict or `{stage}_output` sub-dict
   - `clear()`: delete file or write empty `{"created_at": ...}`
   - Handle `FileNotFoundError` and `json.JSONDecodeError` gracefully

2. **Wire into `run_full_pipeline.py`**
   - Import via `importlib.util` (kebab-case file)
   - Instantiate `ContextMemo()` at top of `FullPipelineRunner.run()`
   - Call `memo.clear()` before Module 1
   - Pass `memo` to each module's `run()` method
   - Replace `_build_market_context()` body with `memo.read()`

3. **Update Module 1**
   - Add optional `memo: ContextMemo = None` param to `MarketTimingModule.run()`
   - After AI scoring (line 978), call `memo.save("module1", {...})` with:
     - `market_color`, `market_score`, `trend_status`
     - `breadth: {advances, declines, ad_ratio}`
     - `top_sectors: [code1, code2, code3]`
     - `vp_data: {poc, vah, val, price_vs_va}`
     - `foreign_net`, `vnindex_price`, `vnindex_rsi`

4. **Update Module 2**
   - Add optional `memo` param to `SectorRotationModule.run()`
   - At start: `m1_ctx = memo.read("module1")` if memo exists
   - Use `m1_ctx["market_score"]` to weight sector scoring
   - After analysis: `memo.save("module2", {...})` with:
     - `sector_scores: {VNFIN: 78, VNIT: 65, ...}`
     - `sector_phases: {VNFIN: "LEADING", VNIT: "IMPROVING", ...}`
     - `rotation_clock`, `leading_sectors`, `improving_sectors`

5. **Update Module 3**
   - Add optional `memo` param to `StockScreenerModule.run()`
   - Add `_adjust_thresholds_by_context(self, context: dict)` method
   - RED market: raise min RS to 70, min volume to 1.5, min score to 65
   - GREEN market: lower min RS to 40, normal volume 1.0, min score to 50
   - Read `sector_phases` to prioritize LEADING/IMPROVING sectors
   - Save top candidates summary to memo after screening

6. **Test integration**
   - Run pipeline with `python run_full_pipeline.py`
   - Verify `cache/context_memo.json` contains all 3 stages
   - Verify Module3 thresholds change based on market color

## Todo List

- [x] Create `context-memo.py` with ContextMemo class
- [x] Add unit test for save/read/clear cycle
- [x] Wire memo into `run_full_pipeline.py`
- [x] Update Module 1 to save market context
- [x] Update Module 2 to read module1 + save sector context
- [x] Update Module 3 to read full context + adjust thresholds
- [x] Add `_adjust_thresholds_by_context()` to Module 3
- [x] Integration test: full pipeline run
- [x] Verify JSON file contents after run

## Success Criteria
- `cache/context_memo.json` written with all 3 module outputs after pipeline run
- Module3 uses different RS/volume thresholds based on market_color
- No regression in pipeline output (same stocks selected when market is YELLOW)
- Memo file < 10KB, write time < 50ms

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Corrupt JSON on crash mid-write | M | L | Use `tempfile` + atomic rename |
| Module3 too strict in RED | M | M | Tunable config, A/B test thresholds |
| Memo schema drift | L | M | Version field in JSON, migration helper |

## Security Considerations
- Memo file in `cache/` directory (gitignored)
- No sensitive data in memo (scores, not API keys)
- No external network access

## Next Steps
- Phase 2: Market breadth data feeds into memo
- Phase 3: Fallback templates read memo for deterministic reports
- Phase 4: News sentiment score added to memo
