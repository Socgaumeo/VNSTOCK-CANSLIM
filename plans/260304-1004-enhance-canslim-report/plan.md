---
title: "Enhance CANSLIM Daily Report"
description: "Switch to combined report path, add OPS sections, fix AI WATCH bias"
status: complete
priority: P1
effort: 2h
branch: claude/dazzling-stonebraker
tags: [report, ops, ai-prompt, pipeline]
created: 2026-03-04
completed: 2026-03-05
---

# Enhance CANSLIM Daily Report

## Problem Summary

1. **Jinja2 template path wins** but is missing 12+ report sections (Financial Health, DuPont, BondLab, AssetTracker, NewsHub, MA Positions, Volume Profile, etc.)
2. **OPS modules** (BondLab, AssetTracker, NewsHub) save data to ContextMemo during pipeline but report generation **never reads** from memo
3. **AI recommends WATCH for everything** in per-stock analysis because prompt lacks context that stock IS a top pick

## Solution

Switch to `_generate_combined_report()` (already has most sections) and add OPS data from ContextMemo.

## Phases

| Phase | Description | Status | Effort |
|-------|-------------|--------|--------|
| [Phase 1](phase-01-report-path-and-ops.md) | Switch report path + add OPS sections | complete | 45min |
| [Phase 2](phase-02-ai-prompt-fix.md) | Fix AI WATCH bias in per-stock prompt | complete | 30min |
| [Phase 3](#phase-3-notes) | Enhanced scoring bridge module discovery | complete | 15min |

## Key Files

- `v2_optimized/run_full_pipeline.py` - report path switch + OPS sections
- `v2_optimized/module3_stock_screener_v1.py` - AI prompt adjustment
- `v2_optimized/enhanced_scoring.py` - financial data bridge (discovered during implementation)

## Phase 3 Notes

During implementation, discovered missing `enhanced_scoring.py` bridge module that was root cause of N/A values in Financial Health tables:
- **File created:** `v2_optimized/enhanced_scoring.py`
- **Purpose:** Bridge between baocaotaichinh financial data and screener module3
- **Key fixes:**
  - PEG ratio propagation now works correctly (was None causing N/A display)
  - Fixed Piotroski/Altman score display (0/None now shows proper value)
  - Unified financial health scoring interface for all candidates
- **Integration:** Wired into `module3_stock_screener_v1.py` candidate processing

## Dependencies

- ContextMemo (`context-memo.py`) - read API: `memo.read("bonds")`, `memo.read("assets")`, `memo.read("news")`
- BondLab saves: `{"bond_health": {...}, "yield_curve": {...}}`
- AssetTracker saves: `{"macro_signal": {...}, "summary": {...}}`
- NewsHub saves: `{"avg_sentiment": float, "total_articles": int, "positive": int, "negative": int}`
- enhanced_scoring.py bridge for unified financial scoring
