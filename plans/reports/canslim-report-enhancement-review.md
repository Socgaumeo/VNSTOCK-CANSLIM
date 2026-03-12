# Code Review: CANSLIM Report Enhancement

**Date:** 2026-03-04
**Branch:** claude/dazzling-stonebraker
**Reviewer:** code-reviewer agent
**Focus:** Recent changes to enrich CANSLIM report with OPS platform data + AI prompt bias

---

## Scope

- **Files reviewed:** 2 source files, 4 dependency modules
  - `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/run_full_pipeline.py` (main changes)
  - `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/module3_stock_screener_v1.py` (prompt + screener changes)
  - `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/context-memo.py` (data bus)
  - `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/bond-lab.py`
  - `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/asset-tracker.py`
  - `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/news-hub.py`
- **LOC changed:** ~730 lines (diff)
- **Scout findings:** 3 edge cases, 1 dead code path, 1 type mismatch

---

## Overall Assessment

The changes are well-structured and follow the project's pattern of graceful degradation. OPS sections integrate cleanly into the pipeline. The prompt bias change achieves its goal but needs threshold refinement. Two bugs need attention -- one causes "None" rendering in reports, the other is dead code that should be cleaned up.

---

## Critical Issues

None.

---

## High Priority

### H1. `analyze_candidate()` and `generate_report_summary()` now return `None` instead of error string -- causes "None" rendered in report

**Severity:** HIGH
**Files:** `module3_stock_screener_v1.py` lines 1891-1896, 1964-1968; line 2607

**Problem:** The old code returned `f"Error: {e}"` on failure. The new code returns `None`. At line 2451, `candidate.ai_analysis = None` overwrites the default `str = ""`. Most consumers check truthiness (safe), but line 2607 in `ScreenerExporter.generate_content()` uses `{report.ai_analysis}` directly in an f-string -- if `generate_report_summary` returns `None`, the report literally renders the word "None" under the AI Analysis header.

**Fix at line 2451:**
```python
candidate.ai_analysis = self.ai_analyzer.analyze_candidate(candidate) or ""
```

**Fix at line 2455:**
```python
report.ai_analysis = self.ai_analyzer.generate_report_summary(report, history_context) or ""
```

Alternatively, guard line 2607 with a conditional (but the `or ""` approach is more defensive across all consumers).

### H2. NewsHub bonus score applied AFTER weighted total but BEFORE signal determination -- asymmetric penalty (+3/-5)

**Severity:** HIGH (data quality)
**File:** `module3_stock_screener_v1.py` lines 2379-2391

**Problem:** The +3/-5 bonus is additive on the weighted total score (0-100 range). The asymmetry (-5 for negative vs +3 for positive) is intentional and reasonable for risk management. However:

1. The sentiment thresholds (0.5 / -0.5) are high given that `_score_sentiment()` in `news-hub.py` produces scores from keyword ratios. A single positive keyword yields 1.0, a single negative yields -1.0. Titles with mixed keywords produce intermediate values. Threshold of 0.5 means at least 75% of keywords must be positive -- this may rarely trigger for individual stocks.

2. There is no cap on cumulative adjustments if `news_hub.analyze_symbol()` is called multiple times (it is not here, but worth noting).

**Recommendation:** Consider lowering threshold to 0.3/-0.3 for more frequent activation, or document the intentional conservatism.

---

## Medium Priority

### M1. `_generate_report_via_templates()` is dead code (135 lines)

**Severity:** MEDIUM (maintainability)
**File:** `run_full_pipeline.py` lines 775-909

**Problem:** The original line was:
```python
combined_report = self._generate_report_via_templates() or self._generate_combined_report()
```
It was changed to:
```python
combined_report = self._generate_combined_report()
```

The `_generate_report_via_templates()` method (135 lines) is now unreachable. No other caller invokes it. This is dead code that adds cognitive load and maintenance burden.

**Recommendation:** Either remove it entirely, or add a comment explaining it is retained for future Jinja2 template support. If kept, mark with `# TODO: Re-enable when template coverage matches combined report`.

### M2. `_generate_breadth_section()` loads module via `_load_kebab_module` on every call

**Severity:** MEDIUM (performance)
**File:** `run_full_pipeline.py` lines 456-476

**Problem:** `_generate_breadth_section()` calls `_load_kebab_module()` to import `market-breadth-analyzer.py` each time it is invoked. While `importlib` caches modules internally, the overhead of path resolution + spec creation is unnecessary. Other modules (bond-lab, asset-tracker, news-hub) are loaded once at module level.

**Fix:** Move the import to module-level alongside the other `_load_kebab_module` calls:
```python
_breadth_module = _load_kebab_module(
    os.path.join(os.path.dirname(__file__), "market-breadth-analyzer.py"),
    "market_breadth_analyzer"
)
```

### M3. `self.memo` may be `None` if `_memo_module` fails to load

**Severity:** MEDIUM
**File:** `run_full_pipeline.py` line 188

**Problem:** `self.memo` is set to `None` in `__init__` (line 170). It is only assigned a value if `_memo_module` is truthy (line 185-188). If `context-memo.py` has a syntax error or the `cache/` directory is not writable, `self.memo` stays `None`. The `_generate_ops_sections()` method correctly guards with `if not self.memo: return ""` (line 696). Other memo consumers also guard. This is handled correctly.

**Status:** No bug, but worth noting that if memo init fails silently, all OPS data is lost for the report with no warning in the final output. Consider adding a warning flag that surfaces in the report header.

### M4. Asset Tracker format string assumes `info.get("direction")` returns "up" or something else

**Severity:** LOW-MEDIUM
**File:** `run_full_pipeline.py` line 745

**Problem:**
```python
direction = "up" if info.get("direction") == "up" else "down"
```
Wait, the actual code is:
```python
direction = "\U0001f4c8" if info.get("direction") == "up" else "\U0001f4c9"
```
If `direction` is missing or `None`, it defaults to the down arrow. This is a minor UX issue -- a missing value should show neutral, not bearish.

**Fix:**
```python
raw_dir = info.get("direction", "")
direction = "\U0001f4c8" if raw_dir == "up" else "\U0001f4c9" if raw_dir == "down" else "\u27a1\ufe0f"
```

---

## Low Priority

### L1. Prompt bias may reduce WATCH recommendations for genuinely extended stocks

**Severity:** LOW
**File:** `module3_stock_screener_v1.py` lines 1826-1830

**Problem:** The prompt instructs:
> "Only recommend WATCH if price >15% above buy point AND RSI > 80"

The AND condition is very strict. A stock 20% above buy point with RSI at 75 would still get BUY per this guidance. In practice, the AI may interpret this flexibly, but the explicit threshold combination is narrow.

**Assessment:** This is an intentional design choice per the user's requirements -- biasing toward BUY for top CANSLIM picks. The AVOID thresholds (Altman Z < 1.81, OCF/Profit < -0.5) are well-calibrated and serve as hard safety gates. The overall approach is acceptable.

### L2. `score_total` can exceed 100 after NewsHub bonus

**Severity:** LOW
**File:** `module3_stock_screener_v1.py` line 2385

**Problem:** The weighted total is in range [0, 100]. Adding +3 can push it to 103. Subtracting 5 cannot go below -5 (unlikely but possible if weights produce near-zero). No downstream code assumes score_total is capped at 100, so this is cosmetic.

**Recommendation:** Add a clamp if needed for display: `candidate.score_total = min(100, max(0, candidate.score_total))` after the bonus.

### L3. `_adjust_thresholds_by_context` uses Vietnamese text matching for color detection

**Severity:** LOW
**File:** `module3_stock_screener_v1.py` lines 2767-2775

**Problem:** Color detection relies on substring matching in Vietnamese text (`"DO"`, `"XANH"`). If the format of `market_color` changes (e.g., just an emoji without text, or English-only), the detection falls to YELLOW default. The fallback is safe but may not reflect actual market conditions.

**Status:** Acceptable given the codebase convention of Vietnamese color names.

---

## Edge Cases Found

1. **Bond Lab API returns empty list:** `_fetch_from_te()` returns `None`, `get_bond_health_score()` returns `{score: 0, interpretation: "Bond data unavailable"}`. The `_generate_ops_sections()` memo check `if bonds:` passes because the dict is non-empty, but `health.get("vn10y_yield")` falls back to `curve.get("VN10Y", "N/A")` which is also `None` if API failed. Result: renders "None%" in the report. **Fix:** Add `vn10y = ... or "N/A"` coalescing.

2. **ContextMemo file corruption between pipeline stages:** If the JSON file is corrupted mid-write (power loss), `_load()` catches `json.JSONDecodeError` and returns `{}`. All downstream reads get `None` from `.get()`. The atomic write via tempfile+rename minimizes this risk but does not eliminate it on all filesystems.

3. **`_restore_thresholds()` called without prior `_adjust_thresholds_by_context()`:** If memo is None, `_adjust_thresholds_by_context` returns early without setting `self._orig_rs`. The `_restore_thresholds()` uses `hasattr(self, "_orig_rs")` check -- safe.

---

## Positive Observations

1. **Graceful degradation pattern is consistent.** All OPS modules (BondLab, AssetTracker, NewsHub) wrap in try/except with informative warnings. Pipeline continues even if external APIs fail.

2. **ContextMemo design is clean.** Atomic writes via tempfile+rename, simple dict-based API, file-based for debuggability. Good for a sequential pipeline.

3. **Threshold restoration pattern** (`_adjust_thresholds_by_context` / `_restore_thresholds`) prevents config mutation leak between runs. Config is a dataclass instance (not singleton), so even without restoration, separate pipeline runs would not be affected. Belt-and-suspenders approach.

4. **OPS section placement** between Market Timing and Sector Rotation is logical -- provides macro context before drilling into sector/stock picks.

5. **NewsHub integration is non-invasive.** The +3/-5 bonus is small relative to the 0-100 score range, avoiding score distortion while still providing signal.

---

## Recommended Actions

1. **[HIGH]** Fix None-rendering: add `or ""` at lines 2451 and 2455 in `module3_stock_screener_v1.py`
2. **[MEDIUM]** Remove or annotate the dead `_generate_report_via_templates()` method (135 lines)
3. **[MEDIUM]** Move `market-breadth-analyzer.py` import to module level
4. **[LOW]** Add None coalescing for `vn10y` in `_generate_ops_sections()` (line 706)
5. **[LOW]** Consider clamping `score_total` after NewsHub bonus

---

## Metrics

- **Type Coverage:** N/A (Python, no mypy enforcement)
- **Test Coverage:** Not measured (no test suite run in this review)
- **Linting Issues:** 0 syntax errors found
- **Dead Code:** 135 lines (`_generate_report_via_templates`)

---

## Unresolved Questions

1. Is the template renderer path (`_generate_report_via_templates`) planned for re-enablement? If so, it needs OPS section support added before reconnecting.
2. Should the NewsHub sentiment bonus thresholds (0.5/-0.5) be configurable via `ScreenerConfig`?
