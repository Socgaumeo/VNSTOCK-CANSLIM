# Phase 01 - Context Memo Code Review Report

**Date:** 2026-03-03
**Reviewer:** code-reviewer agent
**Commit:** 8d43c44e (fix: resolve division by zero for banks in Piotroski/Altman scoring)

---

## Code Review Summary

### Scope
- **Files reviewed:** 5
  - `v2_optimized/context-memo.py` (new, 75 lines)
  - `v2_optimized/run_full_pipeline.py` (26 changed lines)
  - `v2_optimized/module1_market_timing_v2.py` (57 changed lines)
  - `v2_optimized/module2_sector_rotation_v3.py` (63 changed lines)
  - `v2_optimized/module3_stock_screener_v1.py` (275 changed lines, includes enhanced scoring)
- **Total LOC changed:** ~487 (insertions) / ~74 (deletions)
- **Focus:** Context Memo inter-module state sharing + enhanced scoring integration

### Overall Assessment

Implementation is **solid** overall. The ContextMemo class follows good design principles (atomic writes, graceful error handling, clean API). Backward compatibility is correctly preserved via `memo=None` defaults. However, there are **one high-priority bug**, **two medium concerns** about config mutation and missing attribute access, and a few low-priority items.

---

## Critical Issues

None.

---

## High Priority

### H1. Wrong attribute name in Module1 memo: `rsi` instead of `rsi_14`

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/module1_market_timing_v2.py`
**Line:** 1024

```python
memo_data["vnindex_rsi"] = getattr(vnindex, "rsi", 0)
```

`EnhancedStockData` (defined in `data_collector.py` line 424) has attribute `rsi_14`, not `rsi`. This `getattr` call silently returns `0` every time, so downstream consumers will never see the actual RSI value.

**Fix:**
```python
memo_data["vnindex_rsi"] = getattr(vnindex, "rsi_14", 0)
```

**Impact:** Module2/Module3 would always see `vnindex_rsi=0` in memo, which could mislead any future consumer that relies on it. Currently no downstream module reads this specific field, so functional impact is limited to data correctness in the JSON memo file.

---

### H2. Config mutation in `_adjust_thresholds_by_context` is permanent and not reversible

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/module3_stock_screener_v1.py`
**Lines:** 2721-2760

```python
def _adjust_thresholds_by_context(self, memo) -> None:
    ...
    self.config.MIN_RS_RATING = 70
    self.config.MIN_VOLUME_AVG = max(self.config.MIN_VOLUME_AVG, 150000)
    ...
    self.screener.config = self.config
```

This **mutates** the shared `ScreenerConfig` dataclass instance. If `StockScreenerModule.run()` were called multiple times (e.g., in a loop or test), the thresholds from the first call would persist and compound. Additionally, the `self.screener.config = self.config` line reassigns the screener's config reference, but `self.screener` may have other internal objects initialized with the old config values that are not updated.

**Recommended Fix:** Either (a) save/restore original values after screening, or (b) create a copy of config before mutating:

```python
import copy
adjusted_config = copy.copy(self.config)
# mutate adjusted_config instead
self.screener.config = adjusted_config
```

**Impact:** In current pipeline flow (`run_full_pipeline.py`) this method is only called once, so the risk is low today. But it creates a latent bug for reuse scenarios.

---

## Medium Priority

### M1. GREEN market sets `MIN_VOLUME_AVG = 100000` unconditionally (may lower existing threshold)

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/module3_stock_screener_v1.py`
**Line:** 2748

```python
elif color == "GREEN":
    self.config.MIN_RS_RATING = 40
    self.config.MIN_VOLUME_AVG = 100000  # Hardcoded, ignores existing
```

RED and YELLOW branches use `max(self.config.MIN_VOLUME_AVG, ...)` to only **raise** the floor, but GREEN forces `MIN_VOLUME_AVG = 100000` even if the original config had a higher value (e.g., 150000). This inconsistency could accidentally lower liquidity requirements.

**Fix:**
```python
self.config.MIN_VOLUME_AVG = min(self.config.MIN_VOLUME_AVG, 100000)
```
Or keep `max` for consistency (never lower the configured floor).

---

### M2. `enhanced_scoring` module import will always fail (module file does not exist)

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/module3_stock_screener_v1.py`
**Lines:** 96-103

```python
try:
    from enhanced_scoring import get_enhanced_scorer, EnhancedScorer
    HAS_ENHANCED_SCORING = True
except ImportError as e:
    HAS_ENHANCED_SCORING = False
```

No file `enhanced_scoring.py` exists in the `v2_optimized/` directory. The import silently fails and `HAS_ENHANCED_SCORING` is always `False`. All `_apply_enhanced_scoring` and `_apply_enhanced_scoring_v3` code paths are dead code. The `FundamentalData` dataclass gained 15+ new fields (piotroski_score, altman_z_score, etc.) that are never populated.

**Impact:** The enhanced scoring fields remain at default (0 / empty string). Scoring bonus logic in `_calc_fundamental_score` references `data.piotroski_score` and `data.altman_zone` -- these always return 0/"" so they never trigger, meaning **no scoring change**. This is inert code, not broken, but indicates incomplete integration.

**Note:** This may be intentional if `enhanced_scoring.py` is being developed in a separate branch/PR. If so, consider adding a TODO comment.

---

### M3. Module2 memo reads do not propagate `history_context` to memo

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/module2_sector_rotation_v3.py`
**Lines:** 1144-1152

When Module2 reads Module1 context from memo, it only extracts `traffic_light` and `market_score`. Other available fields (`breadth`, `foreign_net`, `key_signals`, `top_sectors`) are ignored. This is not a bug, but Module2's `analyzer.analyze(market_context)` may benefit from richer context. Low urgency.

---

## Low Priority

### L1. Memo file location hardcoded to `cache/context_memo.json`

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/context-memo.py`
**Line:** 22

```python
memo_path = os.path.join(base_dir, "cache", "context_memo.json")
```

Acceptable for now. If tests need isolation, they can pass a custom `memo_path`. Consider using config to specify the path in future.

---

### L2. No type annotation for `memo` parameter

All `run()` methods and `_save_to_memo()` methods use `memo=None` with no type hint. While duck typing works, adding `Optional[ContextMemo]` or `Optional[Any]` would improve IDE support and self-documentation.

```python
# Current
def run(self, history_context: str = "", memo=None) -> MarketReport:

# Suggested
def run(self, history_context: str = "", memo: Optional[Any] = None) -> MarketReport:
```

---

### L3. `.pyc` files in git diff

The diff includes 13 `__pycache__/*.pyc` binary files. These should be in `.gitignore`.

---

## Edge Cases Found by Scout

### E1. Backward Compatibility -- PASS

All 6 existing callers (`telegram_bot.py:687`, `telegram_bot.py:1186`, `run_simultaneous_debate.py:300/314/334`, `run_mid_session.py:78/92`, `run_compare_ai.py:83/95/128`, `run_debate_pipeline.py:60/81/132`) call `.run()` **without** the `memo` parameter. Since `memo=None` is the default and all memo operations are guarded by `if memo:`, backward compatibility is preserved.

### E2. Concurrent Access -- LOW RISK

`ContextMemo._write()` uses `tempfile.mkstemp` + `os.replace` for atomic writes. `os.replace` is atomic on POSIX systems, so concurrent reads during a write are safe (reader sees old or new, never corrupt). However, two concurrent writers could race. Since the pipeline is sequential (module1 -> module2 -> module3), this is not a current risk.

### E3. Memo clear() at pipeline start -- CORRECT

`run_full_pipeline.py:174` calls `memo.clear()` before any module runs, ensuring no stale data from a previous run leaks in.

### E4. Error isolation -- GOOD

All `_save_to_memo()` methods use try/except with `[WARN]` prints. A memo failure will not crash the pipeline. This follows the project's "silent fail for optional features" pattern.

### E5. `self.screener.config` reassignment

`_adjust_thresholds_by_context` at line 2754 does `self.screener.config = self.config`. Since `self.config` and `self.screener.config` already reference the same object (set in `__init__`), this line is a no-op. It would only matter if they diverged, which they currently don't.

---

## Positive Observations

1. **Atomic writes** -- `ContextMemo._write()` correctly uses `mkstemp` + `os.replace` with cleanup in the except block. Well done.
2. **Graceful degradation** -- `_memo_module` loaded via dynamic import; if `context-memo.py` is missing, `memo = None` and pipeline proceeds without memo. No hard dependency.
3. **Clean API** -- `save(stage, data)` / `read(stage)` / `clear()` is minimal and intuitive.
4. **Module1 context memo data** -- Good selection of fields: market_color, score, breadth, foreign_net, key_signals, top_sectors. Covers key downstream needs.
5. **Module3 threshold logic** -- Dynamically adjusting screening strictness based on market color is a sound CANSLIM practice (tighter in red, looser in green).

---

## Recommended Actions

1. **[H1] Fix RSI attribute** -- Change `getattr(vnindex, "rsi", 0)` to `getattr(vnindex, "rsi_14", 0)` in `module1_market_timing_v2.py:1024`. Immediate fix.
2. **[H2] Protect config from mutation** -- Use `copy.copy(self.config)` or save/restore pattern in `_adjust_thresholds_by_context`. Prevents latent reuse bugs.
3. **[M1] Fix GREEN volume threshold** -- Use `max()` or `min()` consistently across all color branches.
4. **[M2] Clarify enhanced_scoring status** -- Either create the missing `enhanced_scoring.py` module or add a TODO comment explaining the import is for a future PR.
5. **[L2] Add type hints for `memo` params** -- Minor improvement for maintainability.
6. **[L3] Add `__pycache__/` to `.gitignore`** -- Stop committing compiled bytecode.

---

## Metrics

- **Type Coverage:** Partial -- `memo` parameters lack type annotations
- **Test Coverage:** Not measured (no unit tests for ContextMemo exist)
- **Linting Issues:** 1 (wrong attribute name `rsi` vs `rsi_14`)

---

## Unresolved Questions

1. Is `enhanced_scoring.py` being developed in a separate PR? If yes, the dead code in module3 is acceptable as forward preparation. If no, 15+ unused dataclass fields and 100+ lines of unreachable code should be removed.
2. Should `context_memo.json` be added to `.gitignore`? It is runtime state, not source code.
3. Should the memo data include `vnindex_price` and `vnindex_rsi` at all, given no downstream module currently reads them?
