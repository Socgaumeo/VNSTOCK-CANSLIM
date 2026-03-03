"""
Asset price store for persisting gold, silver, oil, and FX prices in SQLite.
Follows the same pattern as news_store.py and signal_store.py.
"""

from datetime import datetime
from typing import List, Dict, Optional

from .db_manager import get_db

ASSET_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS asset_prices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        ticker TEXT NOT NULL,
        price REAL NOT NULL,
        daily_change_pct REAL,
        weekly_change_pct REAL,
        source TEXT DEFAULT 'tradingeconomics',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(date, ticker)
    )
"""

ASSET_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_asset_date ON asset_prices(date)",
    "CREATE INDEX IF NOT EXISTS idx_asset_ticker ON asset_prices(ticker)",
]


class AssetStore:
    """
    SQLite-backed store for commodity and FX asset prices.

    Usage:
        store = AssetStore()
        store.insert_price({
            "date": "2026-03-03", "ticker": "GOLD",
            "price": 2080.5, "daily_change_pct": 0.3,
            "weekly_change_pct": 1.2, "source": "tradingeconomics"
        })
    """

    def __init__(self, db=None):
        self.db = db or get_db()
        self._ensure_table()

    def _ensure_table(self):
        """Create asset_prices table and indexes if they don't exist."""
        try:
            with self.db.connection() as conn:
                conn.execute(ASSET_TABLE_SQL)
                for idx_sql in ASSET_INDEXES_SQL:
                    conn.execute(idx_sql)
        except Exception as e:
            print(f"[AssetStore] Table init error: {e}")

    def insert_price(self, data: dict) -> bool:
        """
        Insert an asset price record. Silently ignores duplicates (INSERT OR IGNORE).
        Returns True if inserted, False if duplicate or error.
        """
        try:
            with self.db.connection() as conn:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO asset_prices
                       (date, ticker, price, daily_change_pct, weekly_change_pct, source)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        data.get("date", ""),
                        data.get("ticker", ""),
                        float(data.get("price", 0)),
                        float(data.get("daily_change_pct", 0)),
                        float(data.get("weekly_change_pct", 0)),
                        data.get("source", "tradingeconomics"),
                    ),
                )
                return cur.rowcount > 0
        except Exception as e:
            print(f"[AssetStore] insert_price error: {e}")
            return False

    def get_latest(self, ticker: str) -> Optional[Dict]:
        """Get the most recent price record for a ticker."""
        try:
            row = self.db.fetchone(
                "SELECT * FROM asset_prices WHERE ticker=? ORDER BY date DESC LIMIT 1",
                (ticker,),
            )
            return dict(row) if row else None
        except Exception as e:
            print(f"[AssetStore] get_latest error: {e}")
            return None

    def get_by_date_range(self, ticker: str, start: str, end: str) -> List[Dict]:
        """Get price records for a ticker between start and end dates (inclusive)."""
        try:
            rows = self.db.fetchall(
                "SELECT * FROM asset_prices WHERE ticker=? AND date BETWEEN ? AND ? ORDER BY date ASC",
                (ticker, start, end),
            )
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"[AssetStore] get_by_date_range error: {e}")
            return []

    def get_recent(self, ticker: str, days: int = 30) -> List[Dict]:
        """Get recent price records for a ticker in the last N days."""
        try:
            rows = self.db.fetchall(
                """SELECT * FROM asset_prices
                   WHERE ticker=? AND date >= date('now', ?)
                   ORDER BY date DESC""",
                (ticker, f"-{days} days"),
            )
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"[AssetStore] get_recent error: {e}")
            return []

    def is_stale(self, ticker: str) -> bool:
        """Return True if no record exists for ticker today (date-level check)."""
        try:
            latest = self.get_latest(ticker)
            if not latest:
                return True
            record_date = latest.get("date", "")
            if not record_date:
                return True
            today = datetime.now().strftime("%Y-%m-%d")
            return record_date < today
        except Exception as e:
            print(f"[AssetStore] is_stale error: {e}")
            return True

    def purge_old(self, days: int = 365) -> int:
        """Delete records older than N days. Returns count deleted."""
        try:
            with self.db.connection() as conn:
                cur = conn.execute(
                    "DELETE FROM asset_prices WHERE date < date('now', ?)",
                    (f"-{days} days",),
                )
                return cur.rowcount
        except Exception as e:
            print(f"[AssetStore] purge_old error: {e}")
            return 0
