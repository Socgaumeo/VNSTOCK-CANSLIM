"""
Foreign flow data store for tracking institutional/foreign trading.
"""

from typing import Optional, List, Dict

import pandas as pd

from .db_manager import get_db


class ForeignFlowStore:
    """
    Foreign trade flow data store backed by SQLite.

    Usage:
        store = ForeignFlowStore()
        store.save_flow("VCB", flow_data_list)
        df = store.get_flow("VCB", days=20)
    """

    def __init__(self, db=None):
        self.db = db or get_db()

    def save_flow(self, symbol: str, data: List[Dict]) -> int:
        """
        Upsert foreign flow data.
        data: list of dicts with date, buy_volume, sell_volume, buy_value, sell_value, net_value.
        """
        if not data:
            return 0

        rows = []
        for d in data:
            date_val = d.get('date', '')
            if not date_val:
                continue
            if hasattr(date_val, 'strftime'):
                date_val = date_val.strftime('%Y-%m-%d')
            rows.append((
                symbol,
                str(date_val)[:10],
                int(d.get('buy_volume', 0) or 0),
                int(d.get('sell_volume', 0) or 0),
                float(d.get('buy_value', 0) or 0),
                float(d.get('sell_value', 0) or 0),
                float(d.get('net_value', 0) or 0),
            ))

        if not rows:
            return 0

        self.db.executemany(
            """INSERT OR REPLACE INTO foreign_flow
               (symbol, date, buy_volume, sell_volume, buy_value, sell_value, net_value)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        return len(rows)

    def get_flow(
        self,
        symbol: str,
        days: int = 20,
        start: str = None,
        end: str = None,
    ) -> pd.DataFrame:
        """Get foreign flow data for a symbol."""
        if start and end:
            sql = """SELECT * FROM foreign_flow
                     WHERE symbol=? AND date BETWEEN ? AND ?
                     ORDER BY date ASC"""
            params = [symbol, start, end]
        else:
            sql = """SELECT * FROM foreign_flow
                     WHERE symbol=?
                     ORDER BY date DESC LIMIT ?"""
            params = [symbol, days]

        rows = self.db.fetchall(sql, params)
        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame([dict(r) for r in rows])
        df = df.sort_values('date').reset_index(drop=True)
        return df

    def get_net_flow_summary(self, symbol: str, days: int = 20) -> Dict:
        """Get net flow summary for a symbol over N days."""
        row = self.db.fetchone(
            """SELECT
                SUM(net_value) as total_net,
                SUM(buy_value) as total_buy,
                SUM(sell_value) as total_sell,
                COUNT(*) as trading_days,
                SUM(CASE WHEN net_value > 0 THEN 1 ELSE 0 END) as buy_days,
                SUM(CASE WHEN net_value < 0 THEN 1 ELSE 0 END) as sell_days
               FROM (
                   SELECT * FROM foreign_flow
                   WHERE symbol=?
                   ORDER BY date DESC LIMIT ?
               )""",
            (symbol, days),
        )
        if not row:
            return {}
        return dict(row)

    def get_top_foreign_bought(self, days: int = 20, limit: int = 10) -> List[Dict]:
        """Get top N symbols by foreign net buying over N days."""
        rows = self.db.fetchall(
            """SELECT symbol, SUM(net_value) as total_net,
                      SUM(buy_value) as total_buy, SUM(sell_value) as total_sell,
                      COUNT(*) as days_count
               FROM (
                   SELECT * FROM foreign_flow
                   WHERE date >= date('now', ?)
               )
               GROUP BY symbol
               ORDER BY total_net DESC
               LIMIT ?""",
            (f'-{days} days', limit),
        )
        return [dict(r) for r in rows]

    def get_top_foreign_sold(self, days: int = 20, limit: int = 10) -> List[Dict]:
        """Get top N symbols by foreign net selling over N days."""
        rows = self.db.fetchall(
            """SELECT symbol, SUM(net_value) as total_net,
                      SUM(buy_value) as total_buy, SUM(sell_value) as total_sell,
                      COUNT(*) as days_count
               FROM (
                   SELECT * FROM foreign_flow
                   WHERE date >= date('now', ?)
               )
               GROUP BY symbol
               ORDER BY total_net ASC
               LIMIT ?""",
            (f'-{days} days', limit),
        )
        return [dict(r) for r in rows]

    def get_latest_date(self, symbol: str) -> Optional[str]:
        """Get the most recent date we have flow data for."""
        row = self.db.fetchone(
            "SELECT MAX(date) as d FROM foreign_flow WHERE symbol=?", (symbol,)
        )
        return row['d'] if row and row['d'] else None

    def get_symbols_with_data(self) -> list:
        """Get list of symbols that have foreign flow data."""
        rows = self.db.fetchall(
            "SELECT DISTINCT symbol FROM foreign_flow ORDER BY symbol"
        )
        return [r['symbol'] for r in rows]
