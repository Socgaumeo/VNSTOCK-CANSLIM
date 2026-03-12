# Phase 1: Switch Report Path + Add OPS Sections

## Context Links

- Pipeline runner: `v2_optimized/run_full_pipeline.py` (1136 lines)
- ContextMemo API: `v2_optimized/context-memo.py` (75 lines)
- Bond Lab: `v2_optimized/bond-lab.py`
- Asset Tracker: `v2_optimized/asset-tracker.py`
- News Hub: `v2_optimized/news-hub.py`

## Overview

- **Priority:** P1
- **Status:** complete
- **Description:** Bypassed Jinja2 template path, stored memo as instance variable, added 3 OPS sections to combined report

## Key Insights

- `_generate_combined_report()` already has: Market Timing, Sector Rotation, Screening Stats, Top Picks table, per-stock Financial Health, per-stock News, MA Positions, Volume Profile, DuPont Analysis, Dynamic SL/TP, breadth section
- Jinja2 template path is tried first (line 372) and succeeds, preventing combined report from ever running
- `memo` is a local variable in `run()` method -- report methods cannot access it
- OPS data stored in memo keys: `"bonds"`, `"assets"`, `"news"`

## Requirements

### Functional
1. Combined report path must always run (bypass Jinja2 templates)
2. BondLab section: VN10Y yield, weekly/monthly change, health score, interpretation
3. AssetTracker section: Gold/Silver/Oil prices, weekly changes, macro signal
4. NewsHub section: Overall market sentiment score, article counts

### Non-functional
- No breaking changes to existing report content
- Graceful handling when OPS data unavailable

## Related Code Files

### Files to Modify
- `v2_optimized/run_full_pipeline.py`

### Files NOT to Modify
- `context-memo.py`, `bond-lab.py`, `asset-tracker.py`, `news-hub.py` (no changes needed)

## Implementation Steps

### Step 1: Store memo as instance variable

In `run()` method (line ~191), after creating memo, store on `self`:

```python
# Line ~191-193, CHANGE:
memo = _memo_module.ContextMemo()
memo.clear()
# ADD:
self.memo = memo
```

Also add `self.memo = None` in `__init__` (around line 170).

### Step 2: Bypass Jinja2 template path

Line 372, change:
```python
# BEFORE:
combined_report = self._generate_report_via_templates() or self._generate_combined_report()

# AFTER:
combined_report = self._generate_combined_report()
```

### Step 3: Add OPS section generator method

Add new method `_generate_ops_sections()` that reads from `self.memo` and returns markdown string. Place it near the other section generators (around line 688).

```python
def _generate_ops_sections(self) -> str:
    """Generate BondLab + AssetTracker + NewsHub report sections from ContextMemo."""
    if not self.memo:
        return ""

    content = ""

    # ── Bond Lab ──
    bonds = self.memo.read("bonds")
    if bonds:
        health = bonds.get("bond_health", {})
        curve = bonds.get("yield_curve", {})
        vn10y = health.get("vn10y_yield", curve.get("VN10Y", "N/A"))
        score = health.get("score", 0)
        interp = health.get("interpretation", "N/A")
        weekly_bps = health.get("weekly_change_bps", 0)
        monthly_bps = health.get("monthly_change_bps", 0)

        score_emoji = "🟢" if score >= 3 else "🔴" if score <= -3 else "🟡"

        content += f"""## 🏦 Bond Lab - Lãi suất trái phiếu

| Chỉ số | Giá trị |
|--------|---------|
| **VN10Y Yield** | {vn10y}% |
| **Weekly Change** | {weekly_bps:+.1f} bps |
| **Monthly Change** | {monthly_bps:+.1f} bps |
| **Health Score** | {score_emoji} {score:+.1f}/10 |
| **Interpretation** | {interp} |

"""

    # ── Asset Tracker ──
    assets_data = self.memo.read("assets")
    if assets_data:
        macro = assets_data.get("macro_signal", {})
        summary = assets_data.get("summary", {})
        assets = summary.get("assets", {})

        signal = macro.get("signal", "neutral")
        macro_score = macro.get("score", 0)
        signal_emoji = "🟢" if signal == "risk-on" else "🔴" if signal == "risk-off" else "🟡"

        content += f"""## 🌍 Asset Tracker - Macro Signal

| Asset | Price | Daily | Weekly | Direction |
|-------|-------|-------|--------|-----------|
"""
        for ticker, info in assets.items():
            price = info.get("price", "N/A")
            unit = info.get("unit", "")
            daily = info.get("daily_change_pct", 0)
            weekly = info.get("weekly_change_pct", 0)
            direction = "📈" if info.get("direction") == "up" else "📉"
            content += f"| **{ticker}** | {price} {unit} | {daily:+.1f}% | {weekly:+.1f}% | {direction} |\n"

        content += f"""
**Macro Signal:** {signal_emoji} **{signal.upper()}** (score: {macro_score:+.1f})

"""

    # ── News Hub ──
    news = self.memo.read("news")
    if news:
        avg_sent = news.get("avg_sentiment", 0)
        total = news.get("total_articles", 0)
        positive = news.get("positive", 0)
        negative = news.get("negative", 0)

        sent_emoji = "🟢" if avg_sent > 0.1 else "🔴" if avg_sent < -0.1 else "🟡"

        content += f"""## 📰 News Hub - Market Sentiment

| Metric | Value |
|--------|-------|
| **Avg Sentiment** | {sent_emoji} {avg_sent:+.3f} |
| **Total Articles (7d)** | {total} |
| **Positive** | {positive} |
| **Negative** | {negative} |

"""

    return content
```

### Step 4: Insert OPS sections in combined report

In `_generate_combined_report()`, insert OPS sections **between Market Timing (Part 1) and Sector Rotation (Part 2)**.

After line ~882 (`content += "\n---\n\n"` after market timing AI analysis), add:

```python
# OPS Platform sections (Bond Lab, Asset Tracker, News Hub)
ops_sections = self._generate_ops_sections()
if ops_sections:
    content += "# 🔬 OPS PLATFORM DATA\n\n"
    content += ops_sections
    content += "\n---\n\n"
```

## Todo List

- [x] Add `self.memo = None` in `__init__`
- [x] Store `memo` on `self.memo` in `run()` method
- [x] Change line 372 to bypass Jinja2 template path
- [x] Add `_generate_ops_sections()` method
- [x] Insert OPS sections call in `_generate_combined_report()`
- [x] Test: run pipeline and verify report contains BondLab/AssetTracker/NewsHub sections
- [x] Test: verify existing sections (Market Timing, Sector, Screener) still render correctly

## Success Criteria

1. Report output contains BondLab yield + health score section
2. Report output contains AssetTracker commodity prices + macro signal
3. Report output contains NewsHub sentiment summary
4. All previously existing sections still present and correct
5. No crashes when OPS modules fail (graceful None handling)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Jinja2 removal breaks email rendering | Low - email just uses plain text report | Combined report is plain markdown, same as before |
| Memo empty when OPS modules fail | Low | All sections guarded with `if` checks, return "" |
| Report too long | Medium | OPS sections add ~30 lines, acceptable |

## Security Considerations

None - no auth/credentials involved. Report is local file output.
