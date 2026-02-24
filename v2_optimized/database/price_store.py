"""
Price store for OHLCV historical data.
Handles caching, incremental sync, and fast retrieval.
"""

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from .db_manager import get_db


class PriceStore:
    """
    OHLCV price data store backed by SQLite.

    Usage:
        store = PriceStore()
        store.save_prices("VCB", df)
        df = store.get_prices("VCB", start="2024-01-01", end="2024-12-31")
    """

    def __init__(self, db=None):
        self.db = db or get_db()

    def save_prices(self, symbol: str, df: pd.DataFrame) -> int:
        """
        Upsert OHLCV data from DataFrame.
        Returns number of rows inserted/updated.
        """
        if df.empty:
            return 0

        rows = []
        for _, row in df.iterrows():
            date_val = self._extract_date(row, df)
            if not date_val:
                continue
            rows.append((
                symbol,
                date_val,
                float(row.get('open', 0) or 0),
                float(row.get('high', 0) or 0),
                float(row.get('low', 0) or 0),
                float(row.get('close', 0) or 0),
                int(row.get('volume', 0) or 0),
                float(row.get('value', 0) or 0),
            ))

        if not rows:
            return 0

        self.db.executemany(
            """INSERT OR REPLACE INTO prices
               (symbol, date, open, high, low, close, volume, value)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        return len(rows)

    def _extract_date(self, row, df) -> Optional[str]:
        """Extract and validate date string from a row."""
        date_str = None

        # Check if date is in index
        if hasattr(row, 'name'):
            idx = row.name
            if isinstance(idx, (pd.Timestamp, datetime)):
                date_str = idx.strftime('%Y-%m-%d')
            elif isinstance(idx, str) and len(idx) >= 10:
                date_str = idx[:10]

        # Check 'time' or 'date' column
        if not date_str:
            for col in ('time', 'date', 'trading_date'):
                val = row.get(col)
                if val is not None:
                    if isinstance(val, (pd.Timestamp, datetime)):
                        date_str = val.strftime('%Y-%m-%d')
                    elif isinstance(val, str) and len(val) >= 10:
                        date_str = val[:10]
                    if date_str:
                        break

        # Validate date format
        if date_str:
            try:
                datetime.strptime(date_str, '%Y-%m-%d')
                return date_str
            except ValueError:
                return None
        return None

    def get_prices(
        self,
        symbol: str,
        start: str = None,
        end: str = None,
        limit: int = None,
    ) -> pd.DataFrame:
        """
        Get OHLCV data for a symbol.
        Returns DataFrame with columns: open, high, low, close, volume, value.
        Index is DatetimeIndex named 'time'.
        """
        sql = "SELECT date, open, high, low, close, volume, value FROM prices WHERE symbol=?"
        params = [symbol]

        if start:
            sql += " AND date >= ?"
            params.append(start)
        if end:
            sql += " AND date <= ?"
            params.append(end)

        sql += " ORDER BY date ASC"

        if limit:
            sql += " LIMIT ?"
            params.append(limit)

        rows = self.db.fetchall(sql, params)

        if not rows:
            return pd.DataFrame()

        data = [dict(r) for r in rows]
        df = pd.DataFrame(data)
        df['time'] = pd.to_datetime(df['date'])
        df = df.set_index('time').drop(columns=['date'])
        return df

    def get_latest_date(self, symbol: str) -> Optional[str]:
        """Get the most recent date we have data for this symbol."""
        row = self.db.fetchone(
            "SELECT MAX(date) as d FROM prices WHERE symbol=?", (symbol,)
        )
        return row['d'] if row and row['d'] else None

    def get_earliest_date(self, symbol: str) -> Optional[str]:
        """Get the earliest date we have data for this symbol."""
        row = self.db.fetchone(
            "SELECT MIN(date) as d FROM prices WHERE symbol=?", (symbol,)
        )
        return row['d'] if row and row['d'] else None

    def get_data_range(self, symbol: str) -> dict:
        """Get date range and row count for a symbol."""
        row = self.db.fetchone(
            """SELECT MIN(date) as earliest, MAX(date) as latest, COUNT(*) as cnt
               FROM prices WHERE symbol=?""",
            (symbol,),
        )
        if row:
            return {
                'earliest': row['earliest'],
                'latest': row['latest'],
                'count': row['cnt'],
            }
        return {'earliest': None, 'latest': None, 'count': 0}

    def get_missing_dates(self, symbol: str, start: str, end: str) -> list:
        """
        Identify date gaps for a symbol between start and end.
        Returns list of (gap_start, gap_end) tuples.
        """
        rows = self.db.fetchall(
            "SELECT date FROM prices WHERE symbol=? AND date BETWEEN ? AND ? ORDER BY date",
            (symbol, start, end),
        )
        existing = {r['date'] for r in rows}
        if not existing:
            return [(start, end)]

        # Generate trading days (Mon-Fri)
        current = datetime.strptime(start, '%Y-%m-%d')
        end_dt = datetime.strptime(end, '%Y-%m-%d')
        gaps = []
        gap_start = None

        while current <= end_dt:
            date_str = current.strftime('%Y-%m-%d')
            is_weekday = current.weekday() < 5

            if is_weekday and date_str not in existing:
                if gap_start is None:
                    gap_start = date_str
            else:
                if gap_start is not None:
                    prev = (current - timedelta(days=1)).strftime('%Y-%m-%d')
                    gaps.append((gap_start, prev))
                    gap_start = None

            current += timedelta(days=1)

        if gap_start is not None:
            gaps.append((gap_start, end_dt.strftime('%Y-%m-%d')))

        return gaps

    def get_symbols_with_data(self) -> list:
        """Get list of all symbols that have price data."""
        rows = self.db.fetchall("SELECT DISTINCT symbol FROM prices ORDER BY symbol")
        return [r['symbol'] for r in rows]

    def count_symbols(self) -> int:
        """Count distinct symbols in price table."""
        row = self.db.fetchone("SELECT COUNT(DISTINCT symbol) as cnt FROM prices")
        return row['cnt'] if row else 0

    def delete_symbol(self, symbol: str) -> int:
        """Delete all price data for a symbol."""
        with self.db.connection() as conn:
            cur = conn.execute("DELETE FROM prices WHERE symbol=?", (symbol,))
            return cur.rowcount
