# VNSTOCK-CANSLIM: System Architecture

**Last Updated:** 2026-02-23
**Phase:** Complete (all 7 phases ✅)

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Layer                               │
│  (CLI: run_full_pipeline.py, run_backtest.py)              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Screening & Orchestration                      │
│  module3_stock_screener_v1.py (CANSLIM + Financial Health) │
│  - Technical scoring (RS, MA, Volume, RSI, Money Flow)     │
│  - Fundamental scoring (C, A, L, P, Earnings)             │
│  - Financial health (Piotroski, Altman, PEG, Dividend)    │
│  - Industry-specific analysis (Banking, Real Estate, etc.) │
│  - Risk gating (Altman distress rejection)                 │
│  - Position sizing with risk management                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│           Analysis Engines (Phase 1-6 Integration)         │
├────────────────────────────────────────────────────────────┤
│ Technical Layer                                            │
│ - candlestick_analyzer.py (12 patterns)                   │
│ - chart_pattern_detector.py (10 Bulkowski patterns)       │
│ - volume_profile.py (POC, VAH, VAL)                       │
│ - money_flow_analyzer.py (Foreign flow, MFI, OBV)         │
├────────────────────────────────────────────────────────────┤
│ Fundamental Layer                                          │
│ - earnings_calculator.py (EPS/Revenue growth, CAGR)       │
│ - financial_health_scorer.py (Piotroski, Altman)          │
│ - valuation-scorer.py (PEG, fair value)                   │
│ - industry_analyzer.py (Banking, Real Estate, Retail)     │
│ - dupont-analyzer.py (ROE decomposition)                  │
│ - dividend-analyzer.py (Yield, payout, consistency)       │
├────────────────────────────────────────────────────────────┤
│ Risk & Validation Layer                                    │
│ - risk-metrics-calculator.py (Beta, Sharpe, Sortino, VaR)│
│ - data-reconciliation-checker.py (Verify ratios)         │
│ - portfolio/position_sizer.py (Risk gates, ATR sizing)   │
│ - portfolio/trailing_stop.py (Dynamic stops)             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Data Acquisition Layer                         │
│  data_collector.py (VCI/TCBS/SSI with fallback)           │
│  - Stock prices (daily, weekly, monthly)                   │
│  - Fundamentals (quarterly/annual)                         │
│  - Foreign investment flows                                │
│  - Index data (VNINDEX, VNFIN, sector indices)            │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│              Cache & Storage Layer                          │
│                  SQLite Database                            │
│  database/price_store.py          → prices table           │
│  database/fundamental_store.py    → fundamentals table     │
│  database/signal_store.py         → signals table          │
│  database/foreign_flow_store.py   → foreign_flows table    │
│  WAL mode, thread-safe singleton pattern                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│         External APIs & Reporting                          │
│  - vnstock API (price, fundamental, company data)          │
│  - Google Gemini API (AI analysis)                         │
│  - Output: Markdown reports, backtesting results           │
└─────────────────────────────────────────────────────────────┘
```

---

## Detailed Component Architecture

### 1. Screening Engine (module3_stock_screener_v1.py)

**Responsibility**: Unified CANSLIM scoring system integrating all analysis modules.

**Inputs**:
- Symbol, exchange, date range
- Configurable thresholds (RSI, PE, volume, etc.)

**Processing Flow**:
```
1. Load technical data (price, volume, indicators)
2. Load fundamental data (EPS, PE, debt, etc.)
3. Calculate technical score (RS, MA, Volume, RSI, Money Flow)
4. Calculate fundamental score (C, A, L, P, Earnings)
5. Calculate financial health scores:
   - Piotroski F-Score → +5/-10 bonus/penalty
   - Altman Z-Score → REJECT if Z < 1.81 (distress)
   - PEG Ratio → +5/-5 bonus/penalty
6. Calculate valuation & income:
   - Dividend yield bonus (+3 if >= 4%)
   - Industry health bonus/penalty
7. Calculate risk metrics:
   - Volatility, Beta, VaR, Sharpe ratio
   - Risk gates in position_sizer.py
8. Final score = Tech (100) + Fundamental (100+) + Health + Val + Industry
9. Position sizing with ATR-based stops
10. Persist signal to database
```

**Output**:
- Combined score (0-300+)
- Component breakdown (technical, fundamental, health, valuation)
- Position size, entry, stop-loss, take-profit
- Risk metrics (Beta, Sharpe, Max Drawdown)

---

### 2. Financial Health Analysis (Phase 07)

#### Piotroski F-Score (financial_health_scorer.py)

**Purpose**: 0-9 score indicating financial strength via accounting quality.

**9 Criteria**:
1. ROA > 0 (profitability)
2. CFO > 0 (cash generation)
3. ROA improved YoY (trend)
4. CFO >= 0.8 * Net Income (Vietnam-adjusted cash quality)
5. Debt/Assets decreased (leveraging down)
6. Current Ratio improved (liquidity trend)
7. No dilution in shares outstanding
8. Gross Margin improved (pricing power)
9. Asset Turnover improved (efficiency)

**Integration**: Bonus +5 if Piotroski >= 7, Penalty -10 if <= 3

#### Altman Z-Score (financial_health_scorer.py)

**Formula**: Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5

**Components**:
- X1: Working Capital / Total Assets
- X2: Retained Earnings / Total Assets
- X3: EBIT / Total Assets
- X4: Market Cap / Total Liabilities
- X5: Revenue / Total Assets

**Zones**:
- Z > 2.99: **Safe** (no action)
- Z 1.81-2.99: **Grey** (apply -5 penalty)
- Z < 1.81: **Distress** (HARD REJECT - exclude from portfolio)

---

### 3. Valuation & Income Analysis (Phase 02, 06)

#### PEG Ratio (valuation-scorer.py)

**Formula**: PEG = (PE Ratio) / (Earnings Growth CAGR)

**Classifications**:
- PEG < 1: Undervalued (+5 points)
- PEG 1-2: Fair (+0 points)
- PEG > 3: Overvalued (-5 points)

**Usage**: Filters out expensive growth stocks

#### Dividend Analysis (dividend-analyzer.py)

**Metrics Calculated**:
- Dividend Yield (annual / price)
- Payout Ratio (dividend / earnings)
- Consistency (consecutive years paid)
- 3-year dividend CAGR

**Bonus**: +3 points if yield >= 4% (income attraction)

---

### 4. Risk Management (Phase 03, 05)

#### Risk Metrics (risk-metrics-calculator.py)

**Calculated**:
- Volatility (annualized std dev)
- Beta (vs VNINDEX)
- Value at Risk (VaR 95%)
- Sharpe Ratio (risk-adjusted return)
- Sortino Ratio (downside risk)
- Max Drawdown (peak-to-trough decline)

**Integration**: Position sizing adjusts for Beta > 1.2 (higher volatility)

#### Position Sizing (portfolio/position_sizer.py)

**Risk Gates** (hard filters):
1. **Altman Distress Gate**: Z < 1.81 → REJECT
2. **Volatility Gate**: Annualized vol > 60% → reduce size
3. **Beta Gate**: Beta > 1.5 → reduce size

**Sizing Formula**:
```
risk_amount = NAV * base_risk_pct * conviction_multiplier
shares = risk_amount / (entry_price - stop_loss)
```

**Stop-Loss Hierarchy**:
1. Initial: ATR-based (2 × ATR below entry)
2. Breakeven: Move to entry + 0.5 ATR
3. Trailing: Lock profit with MA10 or MA20

---

### 5. Industry-Specific Analysis (Phase 05)

#### Banking Sector (industry_analyzer.py)
- **NIM** (Net Interest Margin): Loan profitability
- **LDR** (Loan-to-Deposit Ratio): Lending capacity (healthy: 70-100%)

#### Real Estate Sector
- **D/E** (Debt-to-Equity): Leverage ratio (healthy: < 1.0)
- **Land Bank**: Years of supply

#### Retail Sector
- **DSI** (Days Sales of Inventory): Turnover speed
- **CCC** (Cash Conversion Cycle): Cash flow efficiency

**Bonus/Penalty**:
- Industry Health >= 80: +3 points
- Industry Health < 40: -5 points

---

### 6. Data Reconciliation (Phase 04)

**Purpose**: Validate computed metrics vs provider-supplied ratios.

**Checks**:
- PE = Price / EPS
- PB = Price / Book Value
- ROE = Net Income / Equity
- ROA = Net Income / Assets
- Debt Ratio = Debt / Assets

**Output**: Divergence report (if computed ≠ provided by >5%)

---

### 7. DuPont Analysis (Phase 06)

**Formula**: ROE = NPM × ATO × EM

**Components**:
- **NPM** (Net Profit Margin): Net Income / Revenue
- **ATO** (Asset Turnover): Revenue / Assets
- **EM** (Equity Multiplier): Assets / Equity

**Usage**: Identify which driver improves/declines ROE (profitability vs efficiency vs leverage)

---

## Database Schema

### prices
```sql
CREATE TABLE prices (
    id INTEGER PRIMARY KEY,
    symbol TEXT,
    date TEXT,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER,
    ma_10 REAL, ma_20 REAL, ma_50 REAL, ma_200 REAL, ma_260 REAL,
    rsi_14 REAL, rsi_21 REAL,
    macd REAL, signal REAL, histogram REAL,
    adx REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### fundamentals
```sql
CREATE TABLE fundamentals (
    id INTEGER PRIMARY KEY,
    symbol TEXT,
    period TEXT, -- '2025-Q4' or '2024-annual'
    eps REAL, revenue REAL, net_income REAL,
    total_assets REAL, total_liabilities REAL, total_equity REAL,
    pe REAL, pb REAL, dividend_yield REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### signals
```sql
CREATE TABLE signals (
    id INTEGER PRIMARY KEY,
    symbol TEXT, date TEXT,
    technical_score REAL, fundamental_score REAL,
    piotroski_score INTEGER, altman_z REAL,
    peg_ratio REAL, dividend_yield REAL,
    industry_health REAL,
    combined_score REAL,
    position_size INTEGER, entry REAL, stop_loss REAL, take_profit REAL,
    beta REAL, volatility REAL, sharpe REAL, max_drawdown REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### foreign_flows
```sql
CREATE TABLE foreign_flows (
    id INTEGER PRIMARY KEY,
    date TEXT, symbol TEXT,
    buy_volume INTEGER, sell_volume INTEGER,
    net_volume INTEGER, net_value REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Data Flow During Screening

```
Input: ['TCB', 'MBB', 'VNM', ...]
    ↓
For each symbol:
    ├─ data_collector.get_stock_prices(symbol)
    │   ├─ vnstock API fetch (VCI/TCBS fallback)
    │   └─ price_store.upsert() → prices table
    │
    ├─ data_collector.get_fundamentals(symbol)
    │   ├─ vnstock API fetch (quarterly)
    │   └─ fundamental_store.upsert() → fundamentals table
    │
    ├─ earnings_calculator.calculate_scores(fundamentals)
    │   └─ EPS growth, Revenue growth, CAGR
    │
    ├─ financial_health_scorer.calculate_piotroski_f_score(current, previous)
    │   └─ 0-9 score with YoY criteria
    │
    ├─ financial_health_scorer.calculate_altman_z_score(balance_sheet)
    │   └─ Z-score, zone classification
    │
    ├─ valuation_scorer.calculate_peg_ratio(eps_growth, pe)
    │   └─ PEG ratio classification
    │
    ├─ industry_analyzer.get_industry_metrics(symbol, sector)
    │   └─ Banking/Real Estate/Retail specific ratios
    │
    ├─ dividend_analyzer.calculate_yield_and_payout(fundamentals)
    │   └─ Yield, payout ratio, consistency
    │
    ├─ risk_metrics_calculator.calculate_beta_and_volatility(prices, index)
    │   └─ Beta vs VNINDEX, annualized volatility
    │
    ├─ candlestick_analyzer.detect_all(prices)
    │   └─ 12 patterns detected
    │
    ├─ chart_pattern_detector.detect_all(prices)
    │   └─ 10 Bulkowski patterns detected
    │
    ├─ volume_profile.calculate(prices)
    │   └─ POC, VAH, VAL
    │
    ├─ money_flow_analyzer.analyze(prices, foreign_flow)
    │   └─ Foreign accumulation, MFI, OBV
    │
    ├─ module3_stock_screener_v1.score(all_above_data)
    │   ├─ Tech score = RS(25) + MA(20) + Dist(10) + RSI(10) + Vol(10) + MF(25) = 100
    │   ├─ Fund score = C(20) + A(15) + L(15) + P(10) + Earnings(25) = 85
    │   ├─ Health score = Piotroski(+5/-10) + Altman(-5 grey, reject distress)
    │   ├─ Val score = PEG(+5/-5) + Dividend(+3) + Industry(+3/-5)
    │   └─ Final = Tech + Fund + Health + Val
    │
    ├─ Altman distress check: if Z < 1.81 → REJECT (skip position sizing)
    │
    ├─ portfolio/position_sizer.calculate_size(final_score, price, volatility, beta)
    │   └─ Risk gates applied, ATR stops calculated
    │
    └─ signal_store.upsert(symbol, scores, size, stops, metrics)
        └─ signals table persistence
```

---

## Execution Entry Points

### run_full_pipeline.py
- Orchestrates end-to-end screening
- Runs module1 (market timing) → module2 (sector rotation) → module3 (stock screener)
- Generates markdown report
- Output: `output/canslim_report_YYYYMMDD_HHMM.md`

### run_backtest.py
- Loads signals from signal_store
- Replays trades with stop-loss/take-profit
- Calculates P&L, win rate, profit factor
- Output: `output/backtest_report_YYYYMMDD_HHMM.md`

### run_market_timing.py
- Quick market color detection (Red/Yellow/Green)
- Volume Profile analysis
- Output: `output/market_timing_YYYYMMDD_HHMM.md`

---

## Key Design Decisions

1. **Stateless Functions**: All analysis modules are pure functions accepting pre-fetched data (no DB reads inside)
2. **Lazy Evaluation**: Scores computed on-demand, cached in signal_store
3. **VN-Specific Thresholds**: RSI 35/65 (not 30/70), Piotroski CFO/NI 0.8x (not strict >1)
4. **Hard Rejects**: Altman Z < 1.81 automatically excludes stock (no scoring)
5. **Bonus/Penalty System**: Financial health adds/subtracts from base scores (not replacing)
6. **Risk Gates in Sizing**: Position size reduced for high Beta/Volatility, not rejection
7. **SQLite WAL Mode**: Concurrent reads + atomic writes for safe parallel execution

---

## Assumptions & Limitations

1. **Price Limits**: VN market has ±7% daily limit; backtesting doesn't model gap downs
2. **Trading Hours**: 9:15-11:30, 13:00-14:30 UTC+7 (not modeled in realtime alerts)
3. **Liquidity**: Doesn't check bid-ask spread or volume for actual execution
4. **Fundamental Lag**: Quarterly fundamentals 10-20 days delayed after quarter-end
5. **Foreign Flow Data**: Only provided for large-cap stocks on HoSE
6. **Piotroski YoY**: Requires 2 quarters data; new stocks score 0
7. **Industry Data**: Only banking/real estate/retail fully modeled; others score 0

---

## Future Architecture Enhancements

1. **Module 3 Split**: Current 102 KB file should be modularized (scoring engine, validators, reporters)
2. **Real-Time WebSocket**: Replace daily batch with live VNINDEX streaming
3. **PostgreSQL Migration**: SQLite → PostgreSQL for multi-user web app
4. **Redis Cache**: In-memory cache for frequently accessed fundamentals
5. **Async I/O**: Parallel data collection for 100+ stocks
6. **ML Scoring**: Replace rule-based scoring with trained neural network
7. **News Ingestion**: Real-time news API → NLP sentiment → signal boost/penalty

