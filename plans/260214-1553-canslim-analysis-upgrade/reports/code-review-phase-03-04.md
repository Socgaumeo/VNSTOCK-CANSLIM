# Code Review: Phase 03 (Enhanced Fundamental) & Phase 04 (Money Flow)

**Date:** 2026-02-15
**Reviewer:** code-reviewer agent
**Branch:** claude/dazzling-stonebraker

---

## Scope

- **Files reviewed:**
  - `v2_optimized/earnings_calculator.py` (NEW, 530 lines)
  - `v2_optimized/money_flow_analyzer.py` (NEW, 190 lines)
  - `v2_optimized/module3_stock_screener_v1.py` (MODIFIED, +466 -231 lines diff)
  - `v2_optimized/data_collector.py` (MODIFIED, +282 -120 lines diff)
  - `v2_optimized/database/fundamental_store.py` (reference)
  - `v2_optimized/database/foreign_flow_store.py` (reference)
- **LOC changed:** ~748 net additions across 4 files
- **Focus:** Phase 03 (EarningsCalculator integration) + Phase 04 (MoneyFlowAnalyzer integration)

---

## Overall Assessment

Solid implementation that addresses the core problem: Fundamental score was stuck at 6/100 due to broken MultiIndex parsing. The new `EarningsCalculator` bypasses the fragile column-name matching by using flexible keyword search, and `MoneyFlowAnalyzer` adds meaningful volume/flow signals. Architecture is clean -- both modules are self-contained with graceful degradation. However, several **field mapping omissions** silently neutralize parts of the new scoring logic, and one **UnboundLocalError** in `data_collector.py` is a crash-level bug.

---

## Critical Issues

### C1. UnboundLocalError in `data_collector.py:get_price_history()` -- CRASH BUG

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/data_collector.py`
**Lines:** 182-209

When `_DB_AVAILABLE` is False or `self._price_store` is None, the `cached_df` variable is never assigned. But line 206 references `cached_df` unconditionally inside the `if not df.empty and _DB_AVAILABLE and self._price_store:` block.

If the database was available at save time but NOT at cache-check time (unlikely but possible with `_DB_AVAILABLE` being a module-level flag), or if a race condition occurs, this throws `UnboundLocalError: local variable 'cached_df' referenced before assignment`.

More critically, even in the normal "no DB" path: if `_DB_AVAILABLE` is True but `self._price_store` is None (init failed, line 88 catch), `cached_df` is never set but lines 202-209 execute because `self._price_store` is re-checked.

**Fix:** Initialize `cached_df = pd.DataFrame()` at the top of `get_price_history()`, before the `if` block.

```python
def get_price_history(self, symbol, days=120, source=None):
    end_date = ...
    start_date = ...
    cached_df = pd.DataFrame()  # <-- ADD THIS

    if _DB_AVAILABLE and self._price_store:
        cached_df = self._price_store.get_prices(...)
        ...
```

### C2. CAGR returns large negative for turnaround stocks -- misleading score

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/earnings_calculator.py`
**Lines:** 356-372

`_calc_cagr` guards `past <= 0` but not `current <= 0`. When a company was profitable 3 years ago (past > 0) but now has losses (current < 0), `pow(negative / positive, 1/years)` raises `ValueError` on fractional exponents, which is caught. BUT if current is very small positive (e.g. 1M vs past 100M), the CAGR will be a large negative like -80%, which then maps to 0 pts in A-score. This is correct behavior but should be documented.

However, the real issue: `current <= 0` with `past > 0` --> `pow()` raises ValueError for fractional years. The except catches it and returns 0.0, which gives the same score as "insufficient data." A turnaround stock with losses should probably score 0 explicitly with a different code path, not silently match the "no data" case.

---

## High Priority

### H1. Missing field mapping: `gross_margin_expansion` never set in Phase 03 path

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/module3_stock_screener_v1.py`
**Lines:** 562-590

`EarningsResult` calculates `gross_margin_expansion` (earnings_calculator.py line 56), but the Phase 03 integration (module3 lines 562-590) never maps it:

```python
# MISSING:
data.gross_margin_expansion = er.gross_margin_expansion
```

This means `_calc_a_score` (line 670-674) always sees `gm_exp == 0` for the condition `gm_exp != 0`, so the 20-point Gross Margin Expansion component of A-score is silently disabled. **20% of A-score potential is dead.**

**Impact:** A-score max is effectively 80 instead of 100 for EarningsCalculator path.

### H2. Missing field mappings: `eps_growth_3y_cagr` and `eps_growth_5y_cagr`

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/module3_stock_screener_v1.py`
**Lines:** 287-288, 562-590

New fields `eps_growth_3y_cagr` and `eps_growth_5y_cagr` were added to `FundamentalData` (lines 287-288) but are never populated in the Phase 03 path. Only `eps_growth_3y` (the old field) is set at line 573. The V3 path correctly sets both (lines 535-537).

While these fields are not used in scoring logic (A-score uses `eps_growth_3y`), they appear in display output (line 559 for V3 path) and could confuse consumers who read the dataclass. Dead fields.

**Fix:** Add `data.eps_growth_3y_cagr = er.eps_3y_cagr` and `data.eps_growth_5y_cagr = er.eps_5y_cagr` in the Phase 03 path.

### H3. `profit_margin` mapped to `gross_margin` -- semantic mismatch

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/module3_stock_screener_v1.py`
**Line:** 574

```python
data.profit_margin = er.gross_margin
```

`profit_margin` semantically means net profit margin. The V3 path correctly maps it from `net_profit_margin` (line 530). But Phase 03 maps `gross_margin` to it. For Vietnamese stocks, gross margin is typically 20-40% while net margin is 5-15%. This inflates the apparent profitability of stocks.

The old C-score used `profit_margin >= 20` for 20pts (now removed in Phase 03), so this currently has no scoring impact. But it misleads any consumer reading `data.profit_margin` (e.g., display/export).

### H4. EPS calculation uses hardcoded 1B shares -- incorrect per-share value

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/earnings_calculator.py`
**Line:** 199

```python
eps = profit / 1e9 if profit else 0
```

This divides profit by 1 billion, which is NOT the company's actual share count. It produces a meaningless number. VCB has ~4.7B shares; HPG has ~5.9B shares; a small-cap might have 50M shares. The "EPS" field in the result is not a real EPS value.

Fortunately, the scoring logic uses `profit` (not `eps`) for growth calculations, so this does not affect scores. But `eps_current_q` displayed to users will be wrong.

**Mitigations:**
- Either fetch share count from the ratio API, or
- Use `eps` values from vnstock's ratio data if available, or
- Document clearly that `eps` field is a proxy, not actual EPS

### H5. OBV calculation uses O(n) Python loop -- performance concern

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/money_flow_analyzer.py`
**Lines:** 159-166

```python
for i in range(1, len(df)):
    if df['close'].iloc[i] > df['close'].iloc[i-1]:
        obv.iloc[i] = obv.iloc[i-1] + df['volume'].iloc[i]
```

This iterates row-by-row in Python. For 250 trading days this is ~250 iterations, acceptable. But if called for longer histories or in batch processing, it becomes a bottleneck. Standard vectorized OBV:

```python
direction = np.sign(df['close'].diff())
obv = (direction * df['volume']).cumsum()
```

**Impact:** Minor for current usage (250 rows per stock), but worth vectorizing for Phase 06 backtesting.

---

## Medium Priority

### M1. Bare `except:` clauses swallow all errors silently

**Files:**
- `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/money_flow_analyzer.py` lines 120, 172
- `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/data_collector.py` lines 774, 802

Bare `except:` catches everything including `KeyboardInterrupt`, `SystemExit`, `MemoryError`. Should be `except Exception:` at minimum.

### M2. `_find_column` excludes all growth columns unconditionally

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/earnings_calculator.py`
**Lines:** 259-260

```python
if 'tang truong' in col_str:
    continue
```

(Using `tăng trưởng` in original.) This skips ALL columns containing "growth" in the name. If vnstock ever names a non-growth column with this keyword, or if a future caller needs to find a growth column, this exclusion will cause silent data loss.

The exclusion makes sense for finding "Doanh thu (đồng)" instead of "Tăng trưởng doanh thu (%)", but it's fragile. Consider making the exclusion list a parameter.

### M3. Scoring weight analysis: Money Flow could dominate Technical Score

New Technical scoring: RS(25) + MA(20) + Distance(10) + RSI(10) + Volume(10) + MoneyFlow(25) = 100

Money Flow gets 25 pts, same as RS Rating. The composite money_flow_score (from `_calc_composite_score`) maxes at 100, which maps to 25 technical pts. The components inside money_flow_score:

| Component | Max Points |
|-----------|-----------|
| Foreign trend (ACCUMULATING) | 25 |
| Vol-price divergence (BULLISH_DIV) | 15 |
| Distribution days (0) | 20 |
| MFI (100) | 20 |
| OBV (RISING) | 20 |

Total possible = 100. So max 25 technical pts from money flow.

**Assessment:** The 25-point allocation is reasonable. However, when foreign flow data is missing (empty DataFrame), the composite score defaults: foreign=12 (NEUTRAL), divergence=8 (NONE), distribution=20 (0 days), mfi=10 (50/100*20), obv=10 (FLAT) = **60/100 = 15 technical pts**. This means even without any real data, money flow contributes a substantial 15/25 pts. This inflates technical scores for stocks with no foreign flow data.

**Recommendation:** Default money_flow_score to 50 (neutral) only when data is available. When no OHLCV data, keep it at 50. But adjust the default so missing foreign flow data gives 50, not 60.

### M4. `_calc_acceleration` compares Q0-Q1 growth vs Q2-Q3 growth, skipping Q1-Q2

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/earnings_calculator.py`
**Lines:** 374-387

```python
recent_growth = self._calc_growth(quarters[0]['profit'], quarters[1]['profit'])
prev_growth = self._calc_growth(quarters[2]['profit'], quarters[3]['profit'])
```

This compares Q0vsQ1 growth against Q2vsQ3 growth, completely skipping the Q1vsQ2 transition. If Q1-Q2 had a spike, acceleration would miss it. Standard acceleration should compare consecutive growth rates, e.g., (Q0vsQ1) - (Q1vsQ2).

### M5. `consecutive_growth_q` counts QoQ, not YoY

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/earnings_calculator.py`
**Lines:** 389-399

The function compares each quarter to its immediate predecessor (QoQ). For seasonal businesses, Q1 is often weaker than Q4 even in a growing company. Standard CANSLIM consecutive growth counts YoY improvements (each Q vs same Q last year). This could undercount stability for seasonal stocks.

### M6. `earnings_stability` filter excludes negative-profit quarters

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/earnings_calculator.py`
**Line:** 406

```python
profits = [q['profit'] for q in quarters[:8] if pd.notna(q['profit']) and q['profit'] > 0]
```

Only positive-profit quarters are included. A company with 1 loss quarter and 7 profit quarters appears MORE stable than it should because the loss is excluded. This biases the stability score upward for companies that had a bad quarter.

---

## Low Priority

### L1. `EarningsCalculator` is not a singleton -- created per `FundamentalAnalyzer`

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/module3_stock_screener_v1.py`
**Line:** 501

`self.earnings_calc = EarningsCalculator()` creates a new instance each time FundamentalAnalyzer is constructed. `EarningsCalculator.__init__` creates `FundamentalStore()` and potentially `Vnstock()`. The store uses `get_db()` singleton, so no real harm, but the Vnstock instance is per-calculator.

### L2. `_parse_period` duplicated in earnings_calculator.py and fundamental_store.py

Both files have identical `_parse_period` methods (lines 276-285 in earnings_calculator.py, lines 75-84 in fundamental_store.py). DRY violation. Should be extracted to a shared utility.

### L3. `_save_ratios_to_db` and `_save_income_to_db` silently swallow all errors

**File:** `/Users/bear1108/Documents/GitHub/VNSTOCK-CANSLIM/.claude/worktrees/dazzling-stonebraker/v2_optimized/data_collector.py`
**Lines:** 774, 802

Both methods have `except Exception: pass`. Any DB corruption or schema mismatch will be completely invisible. At minimum, log the error.

### L4. Module3 file size: 2685 lines

Still growing. With Phase 02 + 03 + 04 additions, it's now even larger. Consider extracting scoring logic into a dedicated `scoring_engine.py` in a future phase.

---

## Edge Cases Found by Scout

1. **Turnaround stocks (negative to positive profit):** CAGR returns 0.0 (caught by ValueError), same as "no data". No distinction between "company was unprofitable" and "data unavailable."

2. **Seasonal businesses:** `consecutive_growth_q` uses QoQ comparison, which breaks for companies where Q1 < Q4 is normal (e.g., retail). False stability penalty.

3. **Empty foreign flow data:** `MoneyFlowAnalyzer.analyze()` with `foreign_df=None` still produces a non-neutral composite score (60/100) because distribution_days=0 gives 20pts and MFI/OBV defaults add more.

4. **`cached_df` UnboundLocalError:** When DB is unavailable during cache-check but available during save, `cached_df` is referenced without being set. Crash risk.

5. **Cash flow negative OCF with negative profit:** `ocf_to_profit_ratio = avg_ocf / avg_profit`. If both are negative, ratio is positive and misleadingly appears "healthy." E.g., OCF=-50, Profit=-100 gives ratio=0.5 which maps to 10pts in C-score.

6. **`_find_column` with 'luu chuyen', 'tai chinh'** at line 188 finds the "financing cash flow" column, but the field is named `fcf` which conventionally means "Free Cash Flow." FCF = OCF - CapEx, not financing cash flow. Semantic mismatch in field naming.

---

## Positive Observations

1. **Flexible column matching** (`_find_column` with keyword search) is a pragmatic solution to the MultiIndex parsing problem. Much more resilient than hardcoded tuple keys.

2. **Graceful degradation** throughout -- every new module uses `HAS_X` flags with `try/except ImportError` guards. The system works fine with any subset of modules installed.

3. **Cache layering** (SQLite primary, JSON legacy fallback) in `data_collector.py` is well-designed with incremental fetch logic to minimize API calls.

4. **`MoneyFlowAnalyzer` is cleanly self-contained** -- single `analyze()` entry point, typed dataclass result, no external state. Easy to test in isolation.

5. **Distribution day counting** follows O'Neil's methodology correctly (down > 0.2% on higher volume).

6. **Cash flow quality scoring** is a strong addition for the VN market where earnings manipulation is common. The OCF/Profit ratio check adds real analytical value.

7. **Rate limiting** between vnstock API calls (1-second sleep in `_fetch_from_api`) shows awareness of API constraints.

---

## Recommended Actions (Priority Order)

1. **[CRITICAL] Fix `cached_df` UnboundLocalError** in `data_collector.py:get_price_history()` -- initialize `cached_df = pd.DataFrame()` before the cache-check block.

2. **[HIGH] Map `gross_margin_expansion`** in module3 Phase 03 path: `data.gross_margin_expansion = er.gross_margin_expansion`. Without this, 20% of A-score is dead code.

3. **[HIGH] Map `eps_growth_3y_cagr` and `eps_growth_5y_cagr`** in Phase 03 path for data completeness.

4. **[HIGH] Fix semantic mismatch:** `data.profit_margin = er.gross_margin` should use net margin, or document why gross margin is used.

5. **[HIGH] Fix CAGR for current <= 0:** Add explicit check for negative current profit.

6. **[MEDIUM] Adjust money flow default score** when foreign data is missing -- currently biased at 60/100 instead of 50.

7. **[MEDIUM] Fix acceleration calc** to compare consecutive growth rates (Q0vsQ1 vs Q1vsQ2) instead of skipping Q1-Q2.

8. **[MEDIUM] Replace bare `except:` with `except Exception:`** in money_flow_analyzer.py and data_collector.py.

9. **[LOW] Fix `fcf` field naming** -- rename to `financing_cf` or fetch actual free cash flow.

10. **[LOW] Vectorize OBV calculation** in money_flow_analyzer.py for future performance.

---

## Metrics

| Metric | Value |
|--------|-------|
| Files reviewed | 6 |
| Net LOC added | ~748 |
| Critical issues | 2 (1 crash bug, 1 misleading CAGR) |
| High issues | 5 |
| Medium issues | 6 |
| Low issues | 4 |
| Bare except clauses | 4 |
| Duplicated code | 1 (_parse_period) |
| Missing field mappings | 3 (gross_margin_expansion, eps_growth_3y_cagr, eps_growth_5y_cagr) |

---

## Unresolved Questions

1. Is the EPS field (`eps = profit / 1e9`) actually used anywhere downstream for display? If so, it needs real share counts.
2. Should `consecutive_growth_q` use YoY instead of QoQ for seasonal VN stocks?
3. Is the 7-day TTL for earnings data appropriate, or should it be extended to 30 days (quarterly data only changes quarterly)?
4. Will Phase 05 (Portfolio Management) consume `money_flow_score` and `distribution_days` for position sizing? If so, the default-score bias matters more.
5. The `_save_ratios_to_db` method uses hardcoded MultiIndex tuple keys -- the same pattern that caused the original bug. Should it also use `_find_column`?
