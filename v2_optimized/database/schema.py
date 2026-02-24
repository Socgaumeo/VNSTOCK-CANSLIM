"""
SQLite schema definitions for VNSTOCK-CANSLIM historical data store.
"""

SCHEMA_VERSION = 1

TABLES_SQL = {
    "prices": """
        CREATE TABLE IF NOT EXISTS prices (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            value REAL,
            PRIMARY KEY (symbol, date)
        )
    """,

    "financial_quarterly": """
        CREATE TABLE IF NOT EXISTS financial_quarterly (
            symbol TEXT NOT NULL,
            period TEXT NOT NULL,
            year INTEGER,
            quarter INTEGER,
            revenue REAL,
            profit REAL,
            eps REAL,
            roe REAL,
            roa REAL,
            pe REAL,
            pb REAL,
            gross_margin REAL,
            net_margin REAL,
            ocf REAL,
            icf REAL,
            fcf REAL,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (symbol, period)
        )
    """,

    "foreign_flow": """
        CREATE TABLE IF NOT EXISTS foreign_flow (
            symbol TEXT NOT NULL,
            date TEXT NOT NULL,
            buy_volume INTEGER DEFAULT 0,
            sell_volume INTEGER DEFAULT 0,
            buy_value REAL DEFAULT 0,
            sell_value REAL DEFAULT 0,
            net_value REAL DEFAULT 0,
            PRIMARY KEY (symbol, date)
        )
    """,

    "signals_history": """
        CREATE TABLE IF NOT EXISTS signals_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            signal TEXT,
            score_total REAL,
            score_fundamental REAL,
            score_technical REAL,
            score_pattern REAL,
            rs_rating INTEGER,
            pattern_type TEXT,
            buy_point REAL,
            stop_loss REAL,
            target REAL,
            actual_return_5d REAL,
            actual_return_20d REAL,
            actual_return_60d REAL,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """,

    "market_snapshots": """
        CREATE TABLE IF NOT EXISTS market_snapshots (
            date TEXT PRIMARY KEY,
            vnindex_close REAL,
            vnindex_change REAL,
            market_score INTEGER,
            market_color TEXT,
            breadth_advance INTEGER,
            breadth_decline INTEGER,
            foreign_net_total REAL,
            distribution_days INTEGER
        )
    """,

    "schema_version": """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        )
    """,
}

INDEXES_SQL = [
    # prices: PK is (symbol, date), so symbol-only index helps COUNT(DISTINCT symbol)
    "CREATE INDEX IF NOT EXISTS idx_prices_date ON prices(date)",
    "CREATE INDEX IF NOT EXISTS idx_financial_symbol ON financial_quarterly(symbol)",
    # foreign_flow: PK is (symbol, date) so no separate composite index needed
    "CREATE INDEX IF NOT EXISTS idx_signals_date ON signals_history(date)",
    "CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals_history(symbol)",
    "CREATE INDEX IF NOT EXISTS idx_signals_signal ON signals_history(signal)",
]
