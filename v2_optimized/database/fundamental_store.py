"""
Fundamental data store for financial quarterly data.
Handles caching of income statement, ratios, and cash flow data.
"""

from datetime import datetime
from typing import Optional, Dict, List

import pandas as pd

from .db_manager import get_db


class FundamentalStore:
    """
    Financial quarterly data store backed by SQLite.

    Usage:
        store = FundamentalStore()
        store.save_quarterly("VCB", quarterly_data_list)
        df = store.get_quarterly("VCB", periods=8)
    """

    def __init__(self, db=None):
        self.db = db or get_db()

    def save_quarterly(self, symbol: str, data: List[Dict]) -> int:
        """
        Upsert quarterly financial data.
        data: list of dicts with keys matching financial_quarterly columns.
        Returns number of rows inserted/updated.
        """
        if not data:
            return 0

        rows = []
        for d in data:
            period = d.get('period', '')
            if not period:
                continue
            year, quarter = self._parse_period(period)
            rows.append((
                symbol,
                period,
                year,
                quarter,
                float(d.get('revenue', 0) or 0),
                float(d.get('profit', 0) or 0),
                float(d.get('eps', 0) or 0),
                float(d.get('roe', 0) or 0),
                float(d.get('roa', 0) or 0),
                float(d.get('pe', 0) or 0),
                float(d.get('pb', 0) or 0),
                float(d.get('gross_margin', 0) or 0),
                float(d.get('net_margin', 0) or 0),
                float(d.get('ocf', 0) or 0),
                float(d.get('icf', 0) or 0),
                float(d.get('fcf', 0) or 0),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            ))

        if not rows:
            return 0

        self.db.executemany(
            """INSERT OR REPLACE INTO financial_quarterly
               (symbol, period, year, quarter, revenue, profit, eps,
                roe, roa, pe, pb, gross_margin, net_margin,
                ocf, icf, fcf, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        return len(rows)

    def _parse_period(self, period: str) -> tuple:
        """Parse period string like 'Q1/2024' into (year, quarter)."""
        try:
            parts = period.replace('-', '/').split('/')
            if len(parts) == 2:
                q_part = parts[0].upper().replace('Q', '')
                return int(parts[1]), int(q_part)
        except (ValueError, IndexError):
            pass
        return 0, 0

    def get_quarterly(
        self,
        symbol: str,
        periods: int = 8,
        start_period: str = None,
    ) -> pd.DataFrame:
        """
        Get quarterly financial data for a symbol.
        Returns DataFrame sorted by year/quarter descending (newest first).
        """
        sql = """SELECT * FROM financial_quarterly
                 WHERE symbol=?"""
        params = [symbol]

        if start_period:
            sql += " AND period >= ?"
            params.append(start_period)

        sql += " ORDER BY year DESC, quarter DESC"

        if periods:
            sql += " LIMIT ?"
            params.append(periods)

        rows = self.db.fetchall(sql, params)
        if not rows:
            return pd.DataFrame()

        return pd.DataFrame([dict(r) for r in rows])

    def get_latest_quarter(self, symbol: str) -> Optional[Dict]:
        """Get the most recent quarterly data."""
        row = self.db.fetchone(
            """SELECT * FROM financial_quarterly
               WHERE symbol=?
               ORDER BY year DESC, quarter DESC LIMIT 1""",
            (symbol,),
        )
        return dict(row) if row else None

    def get_eps_history(self, symbol: str, periods: int = 12) -> List[Dict]:
        """Get EPS history for growth calculations."""
        rows = self.db.fetchall(
            """SELECT period, year, quarter, eps, revenue, profit
               FROM financial_quarterly
               WHERE symbol=?
               ORDER BY year DESC, quarter DESC
               LIMIT ?""",
            (symbol, periods),
        )
        return [dict(r) for r in rows]

    def is_fresh(self, symbol: str, max_days: int = 7) -> bool:
        """Check if data is fresh enough (within max_days)."""
        row = self.db.fetchone(
            """SELECT updated_at FROM financial_quarterly
               WHERE symbol=?
               ORDER BY updated_at DESC LIMIT 1""",
            (symbol,),
        )
        if not row or not row['updated_at']:
            return False

        try:
            ts = row['updated_at']
            # Handle both 'YYYY-MM-DD HH:MM:SS' and 'YYYY-MM-DD' formats
            fmt = '%Y-%m-%d %H:%M:%S' if ' ' in ts else '%Y-%m-%d'
            updated = datetime.strptime(ts, fmt)
            return (datetime.now() - updated).days < max_days
        except (ValueError, TypeError):
            return False

    def get_symbols_with_data(self) -> list:
        """Get list of symbols that have financial data."""
        rows = self.db.fetchall(
            "SELECT DISTINCT symbol FROM financial_quarterly ORDER BY symbol"
        )
        return [r['symbol'] for r in rows]

    def delete_symbol(self, symbol: str) -> int:
        """Delete all financial data for a symbol."""
        with self.db.connection() as conn:
            cur = conn.execute(
                "DELETE FROM financial_quarterly WHERE symbol=?", (symbol,)
            )
            return cur.rowcount
