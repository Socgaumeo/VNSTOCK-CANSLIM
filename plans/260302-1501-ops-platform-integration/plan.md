---
title: "OPS Platform Integration"
description: "Add context memo, market breadth, deterministic fallback, news hub, bond lab, and asset tracker to CANSLIM pipeline"
status: complete
priority: P1
effort: 28h
branch: claude/dazzling-stonebraker
tags: [ops, pipeline, news, bonds, context-sharing, fallback]
created: 2026-03-02
completed: 2026-03-03
---

# OPS Platform Integration Plan

## Summary

Upgrade VNSTOCK-CANSLIM pipeline with 6 capabilities: inter-module context sharing, expanded market breadth, AI-independent report generation, RSS news hub with sentiment, bond yield correlation lab, and multi-asset tracker.

## Phases

| # | Phase | Priority | Effort | Status | File |
|---|-------|----------|--------|--------|------|
| 1 | Context Memo System | P1 | 3h | complete | [phase-01](./phase-01-context-memo-system.md) |
| 2 | Expand Market Agent | P1 | 5h | complete | [phase-02](./phase-02-expand-market-agent.md) |
| 3 | Deterministic Fallback | P1 | 4h | complete | [phase-03](./phase-03-deterministic-fallback.md) |
| 4 | News Hub (VnNew) | P2 | 6h | complete | [phase-04](./phase-04-news-hub.md) |
| 5 | BondLab + ResearchLab | P2 | 6h | complete | [phase-05](./phase-05-bondlab-researchlab.md) |
| 6 | Asset Tracker (Post-MVP) | P3 | 4h | complete | [phase-06](./phase-06-asset-tracker.md) |

## Execution Order

**Sequential**: 1 → 2 → 3 → 4 → 5 → 6 (validated decision — zero conflict risk)

```
Phase 1 (Context Memo)
  → Phase 2 (Market Agent)
    → Phase 3 (Fallback)
      → Phase 4 (News Hub)
        → Phase 5 (BondLab) ← API validation required before start
          → Phase 6 (Asset Tracker)
```

- Phase 1 is prerequisite for all others (memo is the shared bus)
- Phase 5 requires vnstock bond API validation before implementation
- Phase 6 depends on Phase 5 (asset DB pattern reuse)

## Key Design Decisions

1. **JSON file memo** over message queue -- sequential pipeline, KISS
2. **Jinja2 Markdown templates** over HTML -- match existing .md report output
3. **SQLite** for news/bonds -- reuse existing database/ package pattern
4. **feedparser** for RSS -- lightweight, no external service dependency
5. **Kebab-case filenames** per code standards (`context-memo.py`, `news-hub.py`)
6. **statsmodels** for Granger causality -- already common in Python data stack

## New Files (planned)

| File | Phase | Purpose |
|------|-------|---------|
| `v2_optimized/context-memo.py` | 1 | Inter-module state sharing |
| `v2_optimized/market-breadth-analyzer.py` | 2 | A/D ratio, new highs/lows, heatmap |
| `v2_optimized/templates/` | 3 | Jinja2 Markdown report templates |
| `v2_optimized/report-template-renderer.py` | 3 | Deterministic report generator |
| `v2_optimized/news-hub.py` | 4 | RSS crawler + sentiment scoring |
| `v2_optimized/database/news_store.py` | 4 | News persistence layer |
| `v2_optimized/bond-lab.py` | 5 | Bond yield fetcher + storage |
| `v2_optimized/research-lab.py` | 5 | Granger causality + correlation |
| `v2_optimized/database/bond_store.py` | 5 | Bond yield persistence |
| `v2_optimized/asset-tracker.py` | 6 | Gold/silver price tracker |
| `v2_optimized/database/asset_store.py` | 6 | Asset price persistence |

## Modified Files

| File | Phases | Changes |
|------|--------|---------|
| `run_full_pipeline.py` | 1,2,3,4 | Wire memo, breadth, fallback, news |
| `module1_market_timing_v2.py` | 1,2,5 | Save to memo, read bond context, add breadth |
| `module2_sector_rotation_v3.py` | 1 | Read module1 context, save to memo |
| `module3_stock_screener_v1.py` | 1,4 | Read full context, adjust thresholds, news score |
| `ai_providers.py` | 3 | Return None on failure (not error string) |
| `database/__init__.py` | 4,5,6 | Register new stores |

## Risk Summary

- **RSS feed downtime**: mitigate with multi-source + graceful skip
- **vnstock bond API gaps**: fallback to manual SBV data
- **Granger causality noise**: require p < 0.05, min 60 data points
- **Template drift**: keep templates synced with report structure changes

---

## Validation Log

**Date**: 2026-03-03
**Interviewer**: Claude (plan:validate)

### Q1: Module3 Dynamic Thresholds (Phase 01)
- **Question**: RED market thresholds (rs=70, vol=1.5, score=65) could filter ALL stocks. How strict?
- **Answer**: **Use plan values (aggressive)** — better 0 picks than bad picks in bear market
- **Impact**: No changes needed. Phase 01 thresholds confirmed as-is.

### Q2: AI Provider Return Type (Phase 03)
- **Question**: Changing AI providers to return None on failure is a breaking change. Migration strategy?
- **Answer**: **Clean break** — update all providers + all callers in one phase
- **Impact**: Phase 03 must audit ALL ai_providers.py callers. Add checklist to phase file.

### Q3: Sentiment Approach (Phase 04)
- **Question**: Keyword-only vs AI-enhanced sentiment for Vietnamese financial news?
- **Answer**: **Keyword-only first** — ship keyword scoring, iterate based on accuracy later
- **Impact**: No changes needed. Phase 04 already plans keyword-only as primary approach.

### Q4: vnstock Bond API (Phase 05)
- **Question**: Bond API availability is UNTESTED. If unavailable, Phase 5 is blocked.
- **Answer**: **Test API first** — run validation script before implementing Phase 5
- **Impact**: Add "Step 0: API Validation" to Phase 05 implementation steps. Gate on result.

### Q5: New Dependencies (Phase 03-06)
- **Question**: 4 new pip packages (jinja2, feedparser, statsmodels, yfinance). Strategy?
- **Answer**: **Add all as planned** — install per phase as needed
- **Impact**: No changes. Each phase installs its own deps.

### Q6: Execution Order (All Phases)
- **Question**: Parallel (2+3+4 after 1) vs sequential execution?
- **Answer**: **Sequential 1→2→3→4→5→6** — safest, zero conflict risk
- **Impact**: Updated dependency graph above. Removed parallel execution option.
