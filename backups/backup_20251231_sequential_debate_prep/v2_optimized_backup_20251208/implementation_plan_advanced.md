# Implementation Plan: Advanced Features (History & Caching)

## Goal
1.  **Historical Analysis:** Enable AI to review past 10-20 days of reports to track recommendation performance and adjust current analysis.
2.  **Data Caching:** Cache fundamental data (ROE, P/E, etc.) to minimize API calls and speed up scanning.

## Proposed Changes

### 1. Fundamental Data Caching (`v2_optimized/data_collector.py`)
- **Mechanism:** JSON-based file cache (`data_cache/fundamental_cache.json`).
- **Logic:**
    - Key: `Symbol`
    - Value: `{data: {...}, timestamp: "YYYY-MM-DD"}`
    - Expiry: 7 days (Fundamental data changes quarterly).
- **Changes:**
    - Modify `EnhancedDataCollector`.
    - Add `_load_cache()`, `_save_cache()`.
    - Update `get_financial_ratios` and `get_financial_flow` to check cache first.

### 2. History Manager (`v2_optimized/history_manager.py`) [NEW]
- **Purpose:** Parse past reports to extract insights.
- **Features:**
    - `scan_reports(limit=20)`: Read last N report files from `output/`.
    - `extract_market_view(report_content)`: Extract Market Color, Score, and "What-If" scenarios.
    - `extract_sector_view(report_content)`: Extract Top 3 Sectors and their status.
    - `extract_recommendations(report_content)`: Parse Markdown to find "Top Picks" and their signals.
    - `evaluate_performance()`: Compare past predictions (Market/Stock) with current reality.
    - `get_ai_context()`: Generate a comprehensive summary string (Market Trend History + Sector Rotation History + Stock Performance).

### 3. Pipeline Integration (`v2_optimized/run_full_pipeline.py`)
- Initialize `HistoryManager`.
- Before AI Analysis, call `history_manager.get_ai_context()`.
- Inject this context into the AI prompt in `MarketTimingModule` and `StockScreenerModule`.

## Verification Plan
- **Caching:** Run screener twice. Second run should be significantly faster and not hit API for fundamentals.
- **History:**
    - Mock some past reports in `output/`.
    - Run pipeline and verify AI mentions past performance in the new report.
