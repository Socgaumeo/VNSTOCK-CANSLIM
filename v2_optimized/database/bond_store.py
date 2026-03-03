"""
Bond yield store for persisting Vietnam government bond yield snapshots in SQLite.
Follows the same pattern as news_store.py and signal_store.py.
Daily snapshots accumulated over time for historical trend analysis.
"""

from typing import List, Dict, Optional

from .db_manager import get_db

BOND_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS bond_yields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        ticker TEXT NOT NULL DEFAULT 'VN10Y',
        yield_pct REAL NOT NULL,
        daily_change_bps REAL,
        weekly_change_bps REAL,
        monthly_change_bps REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(date, ticker)
    )
"""

BOND_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_bond_date ON bond_yields(date)",
    "CREATE INDEX IF NOT EXISTS idx_bond_ticker ON bond_yields(ticker)",
]


class BondStore:
    """
    SQLite-backed store for Vietnam government bond yield snapshots.

    Usage:
        store = BondStore()
        store.insert_yield({
            "date": "2026-03-03",
            "ticker": "VN10Y",
            "yield_pct": 4.295,
            "daily_change_bps": 0.5,
            "weekly_change_bps": 4.4,
            "monthly_change_bps": 7.2,
        })
        latest = store.get_latest("VN10Y")
        history = store.get_recent(days=30)
    """

    def __init__(self, db=None):
        self.db = db or get_db()
        self._ensure_table()

    def _ensure_table(self):
        """Create bond_yields table and indexes if they don't exist."""
        try:
            with self.db.connection() as conn:
                conn.execute(BOND_TABLE_SQL)
                for idx_sql in BOND_INDEXES_SQL:
                    conn.execute(idx_sql)
        except Exception as e:
            print(f"[BondStore] Table init error: {e}")

    def insert_yield(self, data: dict) -> bool:
        """
        Insert a bond yield record. Silently ignores duplicates (INSERT OR IGNORE).
        Returns True if inserted, False if duplicate or error.
        """
        try:
            with self.db.connection() as conn:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO bond_yields
                       (date, ticker, yield_pct, daily_change_bps, weekly_change_bps, monthly_change_bps)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        data.get("date", ""),
                        data.get("ticker", "VN10Y"),
                        float(data.get("yield_pct", 0.0)),
                        data.get("daily_change_bps"),
                        data.get("weekly_change_bps"),
                        data.get("monthly_change_bps"),
                    ),
                )
                return cur.rowcount > 0
        except Exception as e:
            print(f"[BondStore] insert_yield error: {e}")
            return False

    def get_latest(self, ticker: str = "VN10Y") -> Optional[Dict]:
        """Get the most recent yield record for the given ticker."""
        try:
            row = self.db.fetchone(
                "SELECT * FROM bond_yields WHERE ticker=? ORDER BY date DESC LIMIT 1",
                (ticker,),
            )
            return dict(row) if row else None
        except Exception as e:
            print(f"[BondStore] get_latest error: {e}")
            return None

    def get_by_date_range(self, ticker: str, start: str, end: str) -> List[Dict]:
        """Get yield records for a ticker between start and end date (inclusive)."""
        try:
            rows = self.db.fetchall(
                """SELECT * FROM bond_yields
                   WHERE ticker=? AND date >= ? AND date <= ?
                   ORDER BY date ASC""",
                (ticker, start, end),
            )
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"[BondStore] get_by_date_range error: {e}")
            return []

    def get_recent(self, days: int = 30, ticker: str = "VN10Y") -> List[Dict]:
        """Get the most recent N days of yield data for a ticker."""
        try:
            rows = self.db.fetchall(
                """SELECT * FROM bond_yields
                   WHERE ticker=? AND date >= date('now', ?)
                   ORDER BY date ASC""",
                (ticker, f"-{days} days"),
            )
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"[BondStore] get_recent error: {e}")
            return []

    def purge_old(self, days: int = 365) -> int:
        """Delete records older than N days. Returns count deleted."""
        try:
            with self.db.connection() as conn:
                cur = conn.execute(
                    "DELETE FROM bond_yields WHERE date < date('now', ?)",
                    (f"-{days} days",),
                )
                return cur.rowcount
        except Exception as e:
            print(f"[BondStore] purge_old error: {e}")
            return 0
