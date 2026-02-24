"""
Signal store for tracking recommendations and their performance.
"""

from datetime import datetime
from typing import Optional, List, Dict

import pandas as pd

from .db_manager import get_db


class SignalStore:
    """
    Signal/recommendation tracking store backed by SQLite.

    Usage:
        store = SignalStore()
        store.record_signal("VCB", "STRONG_BUY", scores, pattern_info)
        report = store.get_performance_summary(days=30)
    """

    def __init__(self, db=None):
        self.db = db or get_db()

    def record_signal(
        self,
        symbol: str,
        signal: str,
        score_total: float = 0,
        score_fundamental: float = 0,
        score_technical: float = 0,
        score_pattern: float = 0,
        rs_rating: int = 0,
        pattern_type: str = "",
        buy_point: float = 0,
        stop_loss: float = 0,
        target: float = 0,
        date: str = None,
    ) -> int:
        """Record a new signal/recommendation."""
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        with self.db.connection() as conn:
            cur = conn.execute(
                """INSERT INTO signals_history
                   (date, symbol, signal, score_total, score_fundamental,
                    score_technical, score_pattern, rs_rating, pattern_type,
                    buy_point, stop_loss, target)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (date, symbol, signal, score_total, score_fundamental,
                 score_technical, score_pattern, rs_rating, pattern_type,
                 buy_point, stop_loss, target),
            )
            return cur.lastrowid

    def record_signals_batch(self, signals: List[Dict]) -> int:
        """Record multiple signals at once."""
        if not signals:
            return 0

        rows = []
        for s in signals:
            date = s.get('date', datetime.now().strftime('%Y-%m-%d'))
            rows.append((
                date,
                s.get('symbol', ''),
                s.get('signal', ''),
                float(s.get('score_total', 0) or 0),
                float(s.get('score_fundamental', 0) or 0),
                float(s.get('score_technical', 0) or 0),
                float(s.get('score_pattern', 0) or 0),
                int(s.get('rs_rating', 0) or 0),
                s.get('pattern_type', ''),
                float(s.get('buy_point', 0) or 0),
                float(s.get('stop_loss', 0) or 0),
                float(s.get('target', 0) or 0),
            ))

        self.db.executemany(
            """INSERT INTO signals_history
               (date, symbol, signal, score_total, score_fundamental,
                score_technical, score_pattern, rs_rating, pattern_type,
                buy_point, stop_loss, target)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        return len(rows)

    def update_returns(
        self,
        signal_id: int,
        return_5d: float = None,
        return_20d: float = None,
        return_60d: float = None,
    ):
        """Update actual returns for a signal."""
        updates = []
        params = []
        if return_5d is not None:
            updates.append("actual_return_5d=?")
            params.append(return_5d)
        if return_20d is not None:
            updates.append("actual_return_20d=?")
            params.append(return_20d)
        if return_60d is not None:
            updates.append("actual_return_60d=?")
            params.append(return_60d)

        if not updates:
            return

        params.append(signal_id)
        self.db.execute(
            f"UPDATE signals_history SET {', '.join(updates)} WHERE id=?",
            params,
        )

    def get_signals(
        self,
        symbol: str = None,
        signal_type: str = None,
        days: int = 30,
        limit: int = 100,
    ) -> pd.DataFrame:
        """Get signals with optional filters."""
        sql = "SELECT * FROM signals_history WHERE 1=1"
        params = []

        if symbol:
            sql += " AND symbol=?"
            params.append(symbol)
        if signal_type:
            sql += " AND signal=?"
            params.append(signal_type)
        if days:
            sql += " AND date >= date('now', ?)"
            params.append(f'-{days} days')

        sql += " ORDER BY date DESC, score_total DESC LIMIT ?"
        params.append(limit)

        rows = self.db.fetchall(sql, params)
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])

    def get_signals_needing_return_update(self, period: str = '5d') -> List[Dict]:
        """Get signals that need return data filled in."""
        col_map = {'5d': 'actual_return_5d', '20d': 'actual_return_20d', '60d': 'actual_return_60d'}
        col = col_map.get(period, 'actual_return_5d')

        day_map = {'5d': 5, '20d': 20, '60d': 60}
        min_days = day_map.get(period, 5)

        rows = self.db.fetchall(
            f"""SELECT * FROM signals_history
                WHERE {col} IS NULL
                AND date <= date('now', ?)
                ORDER BY date ASC""",
            (f'-{min_days} days',),
        )
        return [dict(r) for r in rows]

    def get_win_rate(
        self,
        signal_type: str = None,
        pattern_type: str = None,
        period: str = '20d',
        days: int = 90,
    ) -> Dict:
        """Calculate win rate statistics."""
        col_map = {'5d': 'actual_return_5d', '20d': 'actual_return_20d', '60d': 'actual_return_60d'}
        col = col_map.get(period, 'actual_return_20d')

        sql = f"""SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN {col} > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN {col} <= 0 THEN 1 ELSE 0 END) as losses,
                    AVG({col}) as avg_return,
                    AVG(CASE WHEN {col} > 0 THEN {col} END) as avg_winner,
                    AVG(CASE WHEN {col} <= 0 THEN {col} END) as avg_loser,
                    MAX({col}) as best,
                    MIN({col}) as worst
                 FROM signals_history
                 WHERE {col} IS NOT NULL"""
        params = []

        if signal_type:
            sql += " AND signal=?"
            params.append(signal_type)
        if pattern_type:
            sql += " AND pattern_type=?"
            params.append(pattern_type)
        if days:
            sql += " AND date >= date('now', ?)"
            params.append(f'-{days} days')

        row = self.db.fetchone(sql, params)
        if not row or row['total'] == 0:
            return {'total': 0, 'win_rate': 0}

        total = row['total']
        wins = row['wins'] or 0
        return {
            'total': total,
            'wins': wins,
            'losses': row['losses'] or 0,
            'win_rate': round(wins / total * 100, 1) if total > 0 else 0,
            'avg_return': round(row['avg_return'] or 0, 2),
            'avg_winner': round(row['avg_winner'] or 0, 2),
            'avg_loser': round(row['avg_loser'] or 0, 2),
            'best': round(row['best'] or 0, 2),
            'worst': round(row['worst'] or 0, 2),
        }

    def save_market_snapshot(
        self,
        date: str,
        vnindex_close: float = 0,
        vnindex_change: float = 0,
        market_score: int = 0,
        market_color: str = "",
        breadth_advance: int = 0,
        breadth_decline: int = 0,
        foreign_net_total: float = 0,
        distribution_days: int = 0,
    ):
        """Save a market snapshot for the day."""
        self.db.execute(
            """INSERT OR REPLACE INTO market_snapshots
               (date, vnindex_close, vnindex_change, market_score, market_color,
                breadth_advance, breadth_decline, foreign_net_total, distribution_days)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (date, vnindex_close, vnindex_change, market_score, market_color,
             breadth_advance, breadth_decline, foreign_net_total, distribution_days),
        )

    def get_market_snapshots(self, days: int = 30) -> pd.DataFrame:
        """Get recent market snapshots."""
        rows = self.db.fetchall(
            """SELECT * FROM market_snapshots
               WHERE date >= date('now', ?)
               ORDER BY date DESC""",
            (f'-{days} days',),
        )
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])

    def get_stock_signal_history(self, symbol: str, limit: int = 20) -> List[Dict]:
        """Get signal history for a specific stock."""
        rows = self.db.fetchall(
            """SELECT * FROM signals_history
               WHERE symbol=?
               ORDER BY date DESC LIMIT ?""",
            (symbol, limit),
        )
        return [dict(r) for r in rows]
