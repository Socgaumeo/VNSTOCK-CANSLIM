---
title: "baocaotaichinh- Financial Analysis Integration"
description: "Integrate Piotroski F-Score, Altman Z-Score, PEG, risk metrics, reconciliation, industry analysis, DuPont, and dividends into VNSTOCK-CANSLIM"
status: complete
priority: P1
effort: 12h
branch: claude/dazzling-stonebraker
tags: [financial-analysis, integration, piotroski, altman, risk, industry]
created: 2026-02-21
---

# baocaotaichinh- Integration Plan

## Summary

Port financial analysis capabilities from `baocaotaichinh-` repo into the VNSTOCK-CANSLIM `v2_optimized/` pipeline. Focus on actionable metrics that enhance CANSLIM screening, risk gating, and report quality.

## Source Repository

`/Users/bear1108/Documents/GitHub/baocaotaichinh-/webapp/analysis/`

Key modules: `core_analysis.py` (1670 lines), `valuation_analysis.py` (572 lines), `risk_analysis.py` (979 lines), `reconciliation.py` (590 lines), `dupont_extended.py` (472 lines), `dividend_analysis.py` (430 lines), `banking_analysis.py` (746 lines), `realestate_analysis.py` (910 lines), `retail_analysis.py` (950 lines)

## Target Architecture

All new files in `v2_optimized/`. Each file under 200 lines. Standalone functions (no class wrapper needed unless state is required).

## Phases

| # | Phase | Files | Effort | Status |
|---|-------|-------|--------|--------|
| 1 | [Piotroski F-Score + Altman Z-Score](phase-01-piotroski-altman-zscore.md) | `financial_health_scorer.py` | 2h | ✅ complete |
| 2 | [PEG Ratio + Valuation Metrics](phase-02-peg-valuation-metrics.md) | `valuation-scorer.py` | 1.5h | ✅ complete |
| 3 | [Risk Metrics](phase-03-risk-metrics-integration.md) | `risk-metrics-calculator.py` | 2h | ✅ complete |
| 4 | [Data Reconciliation](phase-04-data-reconciliation.md) | `data-reconciliation-checker.py` | 1h | ✅ complete |
| 5 | [Industry-Specific Analysis](phase-05-industry-specific-analysis.md) | `industry_analyzer.py` | 2.5h | ✅ complete |
| 6 | [DuPont Extended + Dividend Analysis](phase-06-dupont-dividend-analysis.md) | `dupont-analyzer.py`, `dividend-analyzer.py` | 1.5h | ✅ complete |
| 7 | [Screener & Pipeline Integration](phase-07-screener-pipeline-integration.md) | modify existing files | 1.5h | ✅ complete |

## Key Design Decisions

1. **No `data_contract.py` port** - Source relies on DB column aliases for baocaotaichinh-'s SQLite schema. VNSTOCK-CANSLIM uses vnstock API + its own SQLite cache with different column names. New modules will accept simple dicts/values directly.

2. **Functional over OOP** - Source uses `CoreAnalysisEngine` class with 8 constructor params. We'll use stateless functions that accept computed values, matching the existing `earnings_calculator.py` pattern.

3. **No DB dependency in new modules** - Data fetching stays in `data_collector.py` and `database/`. New modules receive pre-fetched data as arguments.

4. **Score integration** - New scores feed into `module3_stock_screener_v1.py` scoring via bonus/penalty system (not replacing existing C/A scores).

## Dependencies

- `earnings_calculator.py` provides quarterly financial data
- `data_collector.py` provides price history, market data
- `database/fundamental_store.py` provides cached fundamentals
- `portfolio/position_sizer.py` consumes risk gates

## Resolved Questions (Tested 2026-02-22)

1. **Altman Z-Score**: Hard reject for Z < 1.81 (Distress zone) — confirmed approach.

2. **ICB Classification**: ✅ CONFIRMED — `stock.company.overview()` returns `icb_name2`, `icb_name3`, `icb_name4`
   - Ngân hàng: TCB, MBB, STB
   - Bất động sản: VHM, VIC, NVL
   - Bán lẻ: MWG, DGW
   - Công nghệ Thông tin: FPT, CMG
   - Bảo hiểm: BVH
   - API: `Vnstock().stock(symbol=SYM, source='VCI').company.overview()`

3. **VNINDEX Data for Beta**: ✅ CONFIRMED — `stock.quote.history()` works for VNINDEX
   - API: `Vnstock().stock(symbol='VNINDEX', source='VCI').quote.history(start, end)`
   - Returns: 295 rows with time/open/high/low/close/volume
   - Also in DB: `prices` table has 87 VNINDEX rows (from initial_sync)
   - ETF proxy also available: E1VFVN30 tracks VN30
   - Existing method: `data_collector.get_index_data('VNINDEX')` (line 646)
