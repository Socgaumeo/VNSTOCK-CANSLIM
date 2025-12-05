# IMPLEMENTATION PLAN: VNSTOCK PREMIUM DATA INTEGRATION

## Goal
Upgrade the system to utilize the **VNSTOCK Premium API** key (already in `config.py`) to fetch **Real Fundamental Data** (Financial Ratios, Growth metrics) instead of using placeholders. This will enable true CANSLIM analysis.

## User Review Required
> [!IMPORTANT]
> This change assumes `vnstock` library supports `stock.finance.ratio()` and `stock.finance.income_statement()`. If the installed version is different, we might need to adjust the API calls.

## Proposed Changes

### 1. [MODIFY] `data_collector.py`
Add methods to fetch financial data using `vnstock`.

#### New Methods in `EnhancedDataCollector`:
- `get_financial_ratios(symbol)`: Fetch PE, PB, ROE, ROA.
- `get_financial_flow(symbol)`: Fetch Revenue, Net Profit for growth calculation (QoQ, YoY).

#### Updates to `EnhancedStockData` dataclass:
- Ensure fields like `eps_growth_qoq`, `roe`, `revenue_growth` are populated from the new methods.

### 2. [MODIFY] `module3_stock_screener_v1.py`
Update `FundamentalAnalyzer` to use the real data.

#### Changes in `FundamentalAnalyzer.analyze()`:
- Remove placeholder assignments.
- Call `collector.get_financial_ratios(symbol)`.
- Map API response to `FundamentalData` fields:
    - `eps_growth_qoq` <- from financial flow
    - `eps_growth_yoy` <- from financial flow
    - `roe` <- from ratio
    - `revenue_growth` <- from financial flow

## Verification Plan

### Automated Tests
- Create a test script `test_fundamental_data.py` to fetch data for a known stock (e.g., `VCB`) and print the retrieved ratios and growth metrics.
- Verify that values are non-zero and reasonable (e.g., ROE > 0, PE > 0).

### Manual Verification
- Run `module3_stock_screener_v1.py` for a small sector (e.g., `VNFIN`) and check the output logs/report to see if "Fundamental Score" reflects reality (not just random/default).
