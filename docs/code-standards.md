# VNSTOCK-CANSLIM: Code Standards & Best Practices

**Last Updated:** 2026-02-23
**Python Version:** 3.10+

---

## File Organization

### Directory Structure
```
v2_optimized/
├── config.py                              # Centralized configuration
├── data_collector.py                      # Data fetching (VCI/TCBS/SSI)
├── database/                              # SQLite cache layer
│   ├── __init__.py
│   ├── base_store.py
│   ├── price_store.py
│   ├── fundamental_store.py
│   ├── foreign_flow_store.py
│   └── signal_store.py
├── candlestick_analyzer.py               # Technical patterns
├── chart_pattern_detector.py
├── volume_profile.py
├── earnings_calculator.py                # Fundamental analysis
├── financial_health_scorer.py
├── valuation-scorer.py
├── risk-metrics-calculator.py
├── data-reconciliation-checker.py
├── industry_analyzer.py
├── dupont-analyzer.py
├── dividend-analyzer.py
├── money_flow_analyzer.py
├── portfolio/                             # Portfolio management
│   ├── __init__.py
│   ├── position_sizer.py
│   ├── trailing_stop.py
│   ├── portfolio_manager.py
│   └── watchlist_manager.py
├── simple_backtester.py                  # Backtesting
├── performance_tracker.py
├── vn_market_optimizer.py
├── module1_market_timing_v2.py           # Analysis pipelines
├── module2_sector_rotation_v3.py
├── module3_stock_screener_v1.py
├── ai_providers.py                        # AI integrations
├── news_analyzer.py
├── run_full_pipeline.py                  # Entry points
├── run_backtest.py
└── initial_sync.py
```

### File Naming Conventions
- **Kebab-case** for all Python files: `financial-health-scorer.py`, `data-reconciliation-checker.py`
- **Self-documenting names**: File purpose clear from name (don't use abbreviated names)
- **Max line limit**: 200 LOC per file (exception: module3 102 KB - pending refactoring in v2.8)
- **Package folders**: Use `__init__.py` with public API exports

---

## Code Style Guidelines

### Python Style (PEP 8 baseline with pragmatism)
```python
# Import order: stdlib → 3rd party → local
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import pandas as pd
from database import get_db
from earnings_calculator import calculate_eps_growth

# Naming
CONSTANT_VALUE = 42  # Module-level constants UPPERCASE
def calculate_score(data: Dict) -> float:  # camelCase variables
    local_var = "value"  # snake_case functions/variables
    return 0.0

class AnalysisEngine:  # PascalCase classes (rare - mostly functions)
    """Docstring following Google style."""
    def __init__(self):
        pass

# Spacing
def func1(a: int, b: str) -> bool:  # 2 blank lines before function
    """Brief description. More detail here if needed."""
    x = a + 1
    return x > 0

def func2():  # 2 blank lines between top-level functions
    pass

# Line length: 100 chars (pragmatic, not 79)
# If line > 100, break into multiple lines
result = calculate_score(
    data=fundamentals,
    symbol=ticker,
    date=current_date
)
```

### Key Rules
1. **No type hints on simple vars**: `data = {}` OK (not `data: dict = {}`)
2. **Type hints on functions**: Always for parameters & return type
3. **Docstrings**: Function-level (1-3 lines), no module-level essays
4. **Comments**: Only for "why", not "what" (code is self-documenting)
5. **Line length**: 100 chars (pragmatic, not strict 79)
6. **No classes unless required**: Prefer stateless functions (match existing pattern)

---

## Architecture Patterns

### 1. Pure Functions (Preferred)
```python
# GOOD - stateless, testable
def calculate_piotroski_f_score(current: dict, previous: dict) -> dict:
    """Calculate Piotroski F-Score (0-9).

    Args:
        current: Current period financials
        previous: Previous period financials

    Returns:
        dict with keys: score (0-9), rating, details
    """
    criteria = {
        'roa_positive': 1 if current['roa'] > 0 else 0,
        'cfo_positive': 1 if current['cfo'] > 0 else 0,
        # ... 7 more criteria
    }
    score = sum(criteria.values())
    return {
        'score': score,
        'rating': _get_rating(score),
        'details': criteria
    }

# Usage
result = calculate_piotroski_f_score(current_data, previous_data)
```

### 2. Database Access Pattern (via Singleton)
```python
# GOOD - thread-safe, centralized
from database import get_db

def fetch_stock_data(symbol: str) -> pd.DataFrame:
    db = get_db()  # Singleton instance
    prices = db['price_store'].get_all(symbol)
    return pd.DataFrame(prices)

# BAD - direct instantiation
# db = SQLiteConnection("path.db")  # ❌ Don't do this
```

### 3. Input Validation
```python
# GOOD - explicit error handling
def calculate_altman_z_score(data: dict) -> dict:
    """Calculate Altman Z-Score with graceful fallback."""
    if not data:
        return {'z_score': 0, 'zone': 'unknown', 'error': 'no data'}

    try:
        x1 = data.get('working_capital', 0) / data.get('total_assets', 1)
        # ... calculations
    except (KeyError, ZeroDivisionError, TypeError) as e:
        return {'z_score': 0, 'zone': 'error', 'details': str(e)}

    return {'z_score': z_score, 'zone': classify_zone(z_score), 'components': {...}}

# BAD - crashes on missing data
# x1 = data['working_capital'] / data['total_assets']  # ❌ KeyError risk
```

### 4. Configuration Access
```python
# GOOD - centralized config
from config import Config

def get_api_key():
    cfg = Config()
    return cfg.GEMINI_API_KEY

# BAD - hardcoded
# api_key = "AIzaSy..."  # ❌ Security risk
```

---

## VN Market Specific Patterns

### 1. MultiIndex DataFrame Handling
```python
# vnstock returns MultiIndex columns
# Example: df[('price', 'close')], df[('volume', 'quantity')]

def extract_close_price(df: pd.DataFrame) -> pd.Series:
    """Extract close price from MultiIndex DataFrame."""
    # GOOD - explicit tuple key
    close = df[('price', 'close')]

    # Alternative - if column names vary
    close_col = [col for col in df.columns if col[1] == 'close'][0]
    close = df[close_col]

    return close

# BAD - assumes single index
# close = df['close']  # ❌ May fail with MultiIndex
```

### 2. RSI Thresholds (VN Market)
```python
# VN market has ±7% daily limit, different momentum patterns

def is_oversold(rsi: float) -> bool:
    """VN market oversold threshold (adjusted from 30)."""
    return rsi < 35  # Not 30 (too frequent)

def is_overbought(rsi: float) -> bool:
    """VN market overbought threshold (adjusted from 70)."""
    return rsi > 65  # Not 70 (too frequent)
```

### 3. Foreign Flow Analysis
```python
# Foreign investment flows only available for large-cap HoSE stocks

def analyze_foreign_flow(symbol: str) -> dict:
    """Analyze foreign investment trend."""
    flows = get_db()['foreign_flow_store'].get_by_symbol(symbol)

    if not flows:
        return {
            'status': 'no_data',
            'reason': 'only_available_for_hose_large_cap'
        }

    # Calculate accumulation
    net_flow = sum(f['net_volume'] for f in flows[-20:])
    return {'net_flow': net_flow, 'trend': 'up' if net_flow > 0 else 'down'}
```

### 4. Price Limits & Gaps
```python
# VN market has ±7% daily limit, may gap on next day

def detect_gap(previous_close: float, current_open: float) -> Optional[float]:
    """Detect price gap (may exceed ±7% limit at market open)."""
    pct_change = (current_open - previous_close) / previous_close * 100

    if abs(pct_change) > 7:
        return pct_change  # Gap detected (opening at limit)

    return None
```

---

## Error Handling Patterns

### 1. Graceful Degradation
```python
# GOOD - returns partial result on error
def calculate_multiple_scores(symbols: List[str]) -> dict:
    results = {}
    for sym in symbols:
        try:
            results[sym] = calculate_score(sym)
        except Exception as e:
            results[sym] = {
                'error': str(e),
                'symbol': sym,
                'score': 0
            }
    return results

# BAD - one error stops all
# for sym in symbols:
#     results[sym] = calculate_score(sym)  # ❌ Stops on first error
```

### 2. Specific Exception Catching
```python
# GOOD - specific exceptions
try:
    z_score = calculate_altman_z_score(data)
except ZeroDivisionError:
    z_score = 0  # Graceful fallback for missing data
except KeyError as e:
    logger.warning(f"Missing field: {e}")
    z_score = 0

# BAD - catch-all
# try:
#     z_score = calculate_altman_z_score(data)
# except:  # ❌ Catches KeyboardInterrupt, SystemExit, etc.
#     z_score = 0
```

---

## Testing Patterns

### 1. Unit Test Example
```python
# File: test_financial_health_scorer.py
import pytest
from financial_health_scorer import calculate_piotroski_f_score

def test_piotroski_strong_company():
    """Test Piotroski scoring for strong company."""
    current = {
        'roa': 0.15,  # Positive
        'cfo': 1_000_000,  # Positive
        'net_income': 900_000,
        'total_assets': 10_000_000,
        # ... all 9 criteria positive
    }
    previous = {...}  # Similar or worse than current

    result = calculate_piotroski_f_score(current, previous)

    assert result['score'] == 9
    assert result['rating'] == 'Very Strong'

def test_piotroski_weak_company():
    """Test Piotroski scoring for weak company."""
    current = {
        'roa': -0.05,  # Negative
        'cfo': -500_000,  # Negative
        # ... all 9 criteria negative
    }
    previous = {...}

    result = calculate_piotroski_f_score(current, previous)

    assert result['score'] == 0
    assert result['rating'] == 'Weak'

def test_piotroski_missing_data():
    """Test Piotroski with missing data."""
    current = {}  # Empty
    previous = {}

    result = calculate_piotroski_f_score(current, previous)

    assert result['score'] == 0
    assert result['error'] == 'insufficient_data'
```

### 2. Integration Test Example
```python
def test_screener_full_pipeline():
    """Test screener end-to-end with real data."""
    symbol = 'TCB'

    # Fetch data
    prices = data_collector.get_stock_prices(symbol)
    fundamentals = data_collector.get_fundamentals(symbol)

    # Calculate scores
    result = module3_stock_screener.screen_stock(symbol)

    # Validate result structure
    assert 'technical_score' in result
    assert 'fundamental_score' in result
    assert 'piotroski_score' in result
    assert 'altman_z' in result
    assert 'peg_ratio' in result
    assert 'combined_score' in result

    # Validate score ranges
    assert 0 <= result['piotroski_score'] <= 9
    assert 0 <= result['technical_score'] <= 100
    assert result['altman_z'] > 0
```

---

## Database Patterns

### 1. Thread-Safe Singleton
```python
# GOOD - thread-safe, single instance
import sqlite3
from threading import Lock

class DatabaseConnection:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init_db()
        return cls._instance

    def _init_db(self):
        self.conn = sqlite3.connect('vnstock_canslim.db')
        self.conn.execute('PRAGMA journal_mode=WAL')

    def execute(self, query: str, params: tuple = ()):
        return self.conn.execute(query, params)

# Usage
def get_db():
    return DatabaseConnection()

db = get_db()  # Always same instance
```

### 2. Parameterized Queries
```python
# GOOD - prevents SQL injection
db = get_db()
symbol = "TCB'; DROP TABLE signals; --"
result = db.execute(
    "SELECT * FROM signals WHERE symbol = ?",
    (symbol,)  # Parameterized
)

# BAD - vulnerable
# result = db.execute(f"SELECT * FROM signals WHERE symbol = '{symbol}'")
```

### 3. Transaction Management
```python
# GOOD - atomic writes
def insert_multiple_signals(signals: List[dict]):
    db = get_db()
    try:
        for signal in signals:
            db.execute(
                "INSERT INTO signals (symbol, score, ...) VALUES (?, ?, ...)",
                (signal['symbol'], signal['score'], ...)
            )
        db.commit()
    except Exception as e:
        db.rollback()
        raise
```

---

## Performance Guidelines

### 1. Avoid N+1 Queries
```python
# BAD - N+1 query problem
symbols = ['TCB', 'MBB', 'VNM']
for symbol in symbols:
    # Each loop iteration queries database
    fundamentals = get_db()['fundamental_store'].get_by_symbol(symbol)
    score = calculate_score(fundamentals)

# GOOD - batch query
fundamentals_dict = {
    sym: get_db()['fundamental_store'].get_by_symbol(sym)
    for sym in symbols
}
scores = {sym: calculate_score(fundamentals_dict[sym]) for sym in symbols}
```

### 2. Caching Strategy
```python
# GOOD - cache computed values
_cache = {}

def get_stock_beta(symbol: str) -> float:
    if symbol in _cache:
        return _cache[symbol]

    beta = calculate_beta_vs_vnindex(symbol)
    _cache[symbol] = beta
    return beta

# BAD - recalculate every time
# def get_stock_beta(symbol: str) -> float:
#     return calculate_beta_vs_vnindex(symbol)  # Every call recalculates
```

### 3. Pandas Memory Usage
```python
# GOOD - use efficient dtypes
df = pd.DataFrame({
    'symbol': pd.Categorical(symbols),  # Low memory
    'price': pd.Series(prices, dtype='float32'),  # Not float64
    'volume': pd.Series(volumes, dtype='int32'),  # Not int64
})

# BAD - default dtypes
# df = pd.DataFrame({
#     'symbol': symbols,  # str (high memory)
#     'price': prices,    # float64 (overkill for prices)
#     'volume': volumes   # int64 (overkill)
# })
```

---

## Security Guidelines

### 1. API Key Management
```python
# GOOD - from environment/config
import os
from config import Config

cfg = Config()
api_key = cfg.GEMINI_API_KEY  # From .env or config.py

# BAD - hardcoded
# api_key = "AIzaSy..."  # ❌ Exposed in git
```

### 2. Database Credentials
```python
# GOOD - environment variables
db_path = os.getenv('DB_PATH', 'data_cache/vnstock_canslim.db')
db = sqlite3.connect(db_path)

# BAD - hardcoded path
# db = sqlite3.connect('/home/user/.password/db.db')  # ❌ Visible in code
```

### 3. No Logging Secrets
```python
# GOOD - sanitize logs
def log_request(symbol: str, api_key: str):
    logger.info(f"Fetching {symbol}")  # No API key in log
    # Use api_key internally but don't log it

# BAD - logs sensitive data
# logger.info(f"Using API key: {api_key}")  # ❌ Exposed in logs
```

---

## Documentation Standards

### 1. Module Docstring
```python
"""
financial_health_scorer - Financial health metrics calculation.

This module calculates Piotroski F-Score (0-9) and Altman Z-Score
for financial health assessment. Used by module3_stock_screener.py
for scoring and risk gating.

Functions:
    calculate_piotroski_f_score(current, previous) -> dict
    calculate_altman_z_score(data) -> dict
    get_financial_health_summary(current, previous, market_cap) -> dict

Example:
    >>> current = {'roa': 0.15, 'cfo': 1_000_000, ...}
    >>> previous = {'roa': 0.10, 'cfo': 900_000, ...}
    >>> result = calculate_piotroski_f_score(current, previous)
    >>> print(result['score'])  # 7
    >>> print(result['rating'])  # 'Strong'
"""

import typing
```

### 2. Function Docstring
```python
def calculate_piotroski_f_score(current: dict, previous: dict) -> dict:
    """Calculate Piotroski F-Score (0-9).

    Evaluates 9 financial criteria comparing current vs previous period.
    Used for assessing financial strength and accounting quality.

    Args:
        current: Current period financials with keys:
            roa, cfo, net_income, total_assets, etc.
        previous: Previous period financials (same keys).

    Returns:
        dict with keys:
            - score (0-9): Piotroski score
            - rating (str): 'Very Strong', 'Strong', 'Average', 'Weak'
            - details (dict): Individual criteria (1 or 0)

    Raises:
        TypeError: If current or previous not dict.

    Note:
        Uses Vietnam-adjusted CFO/NI threshold (0.8x, not strict >1).
        Requires 2 periods of fundamentals for YoY comparison.

    Example:
        >>> result = calculate_piotroski_f_score(curr, prev)
        >>> if result['score'] >= 7:
        ...     print("Strong fundamentals")
    """
```

### 3. Complex Logic Comments
```python
def calculate_altman_z_score(data: dict) -> dict:
    # Only comment "why", not "what"

    # X4 uses market cap if available (more accurate),
    # falls back to equity/liabilities ratio (conservative)
    if 'market_cap' in data:
        x4 = data['market_cap'] / data.get('total_liabilities', 1)
    else:
        x4 = data.get('total_equity', 0) / data.get('total_liabilities', 1)
```

---

## Common Gotchas & Fixes

### 1. vnstock MultiIndex Columns
**Gotcha**: Assuming single-level column index
```python
# FAILS - MultiIndex columns
close = df['close']  # KeyError

# FIXED
close = df[('price', 'close')]
# or use helper
close_col = next(c for c in df.columns if c[1] == 'close')
close = df[close_col]
```

### 2. Division by Zero
**Gotcha**: PEG = PE / EPS_growth (if growth=0 → error)
```python
# FAILS
peg = pe_ratio / eps_growth_rate  # ZeroDivisionError if growth=0

# FIXED
if eps_growth_rate > 0:
    peg = pe_ratio / eps_growth_rate
else:
    peg = None  # or 0, or flag as 'undefined'
```

### 3. Missing Fundamental Data
**Gotcha**: New stocks have no historical data
```python
# FAILS
prev_roa = previous['roa']  # KeyError for new IPOs

# FIXED
prev_roa = previous.get('roa', 0)  # Default to 0
if prev_roa == 0:
    # Can't compare YoY, mark as unavailable
    roa_improved = None
```

### 4. Foreign Flow Not Available
**Gotcha**: Small-cap or HNX stocks have no foreign flow data
```python
# FAILS
flows = get_db()['foreign_flow_store'].get_by_symbol('DHI')  # Returns empty

# FIXED
flows = get_db()['foreign_flow_store'].get_by_symbol('DHI')
if flows:
    accumulation = calculate_accumulation(flows)
else:
    # Handle gracefully
    accumulation = 0  # No foreign interest detected
```

---

## Checklist for New Code

- [ ] File under 200 lines (split if >200)
- [ ] Type hints on all functions
- [ ] Docstring on all functions (Google style)
- [ ] Error handling (no bare exceptions)
- [ ] No hardcoded API keys or paths
- [ ] Parameterized SQL queries
- [ ] Testable (pure functions where possible)
- [ ] Comments explain "why", not "what"
- [ ] Variable names self-documenting
- [ ] No print() statements (use logging)
- [ ] Follows VN market conventions (RSI 35/65, etc.)
- [ ] Handles missing data gracefully
- [ ] No N+1 queries
- [ ] Performance validated (if critical path)

---

## Linting & Formatting

### Recommended Tools (Optional)
```bash
# Code style (PEP 8)
pip install flake8
flake8 v2_optimized/ --max-line-length=100

# Format code
pip install black
black v2_optimized/ --line-length=100

# Type checking
pip install mypy
mypy v2_optimized/ --ignore-missing-imports

# Sort imports
pip install isort
isort v2_optimized/
```

### Pre-Commit Checks (Manual)
```bash
# Before committing:
python -m py_compile v2_optimized/new_module.py  # Syntax check
# Run unit tests if added
python -m pytest tests/test_new_module.py
```

---

## Revision History

- **2026-02-23**: v2.7 - Added financial analysis standards, VN market patterns
- **2026-02-10**: v2.6 - Added backtesting standards
- **2026-01-20**: v2.0 - Initial code standards document

