# Phase 01: SQLite Historical Data Store

## Overview
- **Priority:** P0 - Critical
- **Status:** Pending
- **Mô tả:** Xây dựng lớp lưu trữ dữ liệu lịch sử bằng SQLite, giúp giảm API calls, cache dữ liệu OHLCV, fundamental, và theo dõi hiệu quả phân tích qua thời gian.

## Key Insights
- Hiện tại mỗi lần chạy đều fetch mới ~120 ngày dữ liệu cho mỗi mã, rất lãng phí API quota
- Không có khả năng so sánh dữ liệu hiện tại vs quá khứ sâu
- History Manager hiện tại chỉ parse markdown reports, không lưu raw data
- Cache JSON hiện tại (`data_cache/fundamental_cache.json`) quá thô sơ

## Requirements

### Functional
- Lưu trữ OHLCV daily data cho tất cả mã (tối thiểu 5 năm)
- Lưu trữ financial ratios quarterly (PE, PB, ROE, ROA, EPS)
- Lưu trữ income statement quarterly (Revenue, Profit, Margin)
- Lưu trữ cash flow statement quarterly (OCF, ICF, FCF)
- Lưu trữ foreign trade data daily (buy/sell/net)
- Lưu trữ report history (market score, recommendations, signals)
- Incremental update: chỉ fetch data mới, không fetch lại toàn bộ
- Auto-expire: data quá cũ tự động refresh

### Non-functional
- Đọc data từ SQLite phải < 50ms cho 1 mã/250 ngày
- Database size < 500MB cho full market (150+ mã)
- Thread-safe cho parallel access
- Migration support cho schema changes

## Architecture

```
v2_optimized/
├── database/
│   ├── __init__.py
│   ├── schema.py           # Schema definitions
│   ├── db_manager.py       # Connection pool, migrations
│   ├── price_store.py      # OHLCV data store
│   ├── fundamental_store.py # Financial data store
│   ├── signal_store.py     # Signals/recommendations history
│   └── foreign_flow_store.py # Foreign trade data
└── data_cache/
    └── vnstock_canslim.db  # SQLite database file
```

## Implementation Steps

### 1. Tạo schema.py
```sql
-- prices (OHLCV daily)
CREATE TABLE prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER,
    value REAL,  -- Giá trị giao dịch
    UNIQUE(symbol, date)
);
CREATE INDEX idx_prices_symbol_date ON prices(symbol, date);

-- financial_quarterly
CREATE TABLE financial_quarterly (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    period TEXT NOT NULL,  -- "Q1/2024"
    year INTEGER,
    quarter INTEGER,
    revenue REAL,
    profit REAL,
    eps REAL,
    roe REAL, roa REAL,
    pe REAL, pb REAL,
    gross_margin REAL,
    net_margin REAL,
    ocf REAL, icf REAL, fcf REAL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(symbol, period)
);

-- foreign_flow (daily)
CREATE TABLE foreign_flow (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    date DATE NOT NULL,
    buy_volume INTEGER, sell_volume INTEGER,
    buy_value REAL, sell_value REAL,
    net_value REAL,
    UNIQUE(symbol, date)
);

-- signals_history
CREATE TABLE signals_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    symbol TEXT NOT NULL,
    signal TEXT,  -- STRONG_BUY, BUY, WATCH, etc.
    score_total REAL,
    score_fundamental REAL,
    score_technical REAL,
    score_pattern REAL,
    rs_rating INTEGER,
    pattern_type TEXT,
    buy_point REAL,
    stop_loss REAL,
    target REAL,
    actual_return_5d REAL DEFAULT NULL,
    actual_return_20d REAL DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- market_snapshots
CREATE TABLE market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    vnindex_close REAL,
    vnindex_change REAL,
    market_score INTEGER,
    market_color TEXT,
    breadth_advance INTEGER,
    breadth_decline INTEGER,
    foreign_net_total REAL,
    distribution_days INTEGER,
    UNIQUE(date)
);
```

### 2. Tạo db_manager.py
- Singleton pattern cho connection
- Auto-create tables on first run
- Migration system (version tracking)
- Context manager cho transactions

### 3. Tạo price_store.py
- `save_prices(symbol, df)` - Upsert OHLCV data
- `get_prices(symbol, start, end)` - Query cached data
- `get_latest_date(symbol)` - Kiểm tra data freshness
- `sync_prices(symbol, days)` - Chỉ fetch data thiếu từ API
- `bulk_sync(symbols, days)` - Batch sync nhiều mã

### 4. Integrate vào data_collector.py
- Wrap existing `get_price_history()` với cache layer
- Check SQLite trước → chỉ fetch API cho data thiếu
- Auto-save mọi API response vào SQLite

### 5. Tạo fundamental_store.py
- Lưu financial_quarterly data
- Lưu ratio data
- 7-day TTL cho financial data

### 6. Tạo signal_store.py
- Lưu mọi recommendation đã phát
- Track actual return sau 5d, 20d
- Cho phép query: "Mã X được recommend bao nhiêu lần? Win rate?"

## Todo List
- [ ] Tạo thư mục database/ và __init__.py
- [ ] Viết schema.py với full schema
- [ ] Viết db_manager.py (connection, migration)
- [ ] Viết price_store.py (OHLCV cache)
- [ ] Viết fundamental_store.py (financial cache)
- [ ] Viết foreign_flow_store.py
- [ ] Viết signal_store.py (recommendation tracking)
- [ ] Integrate price_store vào data_collector.py
- [ ] Tạo script initial_sync.py để populate 5 năm data
- [ ] Test: verify cache hit ratio > 90% sau initial sync

## Success Criteria
- Lần chạy đầu: ~20 phút (initial sync)
- Các lần chạy sau: < 3 phút (chỉ fetch ngày mới)
- Query 1 mã/250 ngày < 50ms
- DB size < 500MB

## Risk Assessment
- vnstock API có rate limit → cần backoff strategy cho initial sync
- Schema thay đổi trong tương lai → cần migration system từ đầu
- Concurrent write conflict → dùng WAL mode cho SQLite
