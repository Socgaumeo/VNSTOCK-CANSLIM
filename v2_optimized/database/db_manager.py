"""
Database manager for VNSTOCK-CANSLIM.
Handles connection pooling, schema creation, migrations, and WAL mode.
"""

import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

from .schema import TABLES_SQL, INDEXES_SQL, SCHEMA_VERSION


class DatabaseManager:
    """
    SQLite database manager with WAL mode and thread-safe connections.

    Usage:
        db = DatabaseManager()
        with db.connection() as conn:
            conn.execute("SELECT * FROM prices WHERE symbol=?", ("VCB",))
    """

    _instance: Optional['DatabaseManager'] = None
    _lock = threading.Lock()

    def __init__(self, db_path: str = None):
        if db_path is None:
            base = Path(__file__).parent.parent / "data_cache"
            base.mkdir(exist_ok=True)
            db_path = str(base / "vnstock_canslim.db")

        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: str = None) -> 'DatabaseManager':
        """Singleton accessor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(db_path)
        return cls._instance

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            conn.execute("PRAGMA temp_store=MEMORY")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def connection(self):
        """Context manager for database operations with auto-commit."""
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    @contextmanager
    def cursor(self):
        """Context manager that yields a cursor."""
        with self.connection() as conn:
            cur = conn.cursor()
            yield cur

    def execute(self, sql: str, params=None):
        """Execute a single SQL statement."""
        with self.connection() as conn:
            if params:
                return conn.execute(sql, params)
            return conn.execute(sql)

    def executemany(self, sql: str, params_list):
        """Execute SQL for multiple parameter sets."""
        with self.connection() as conn:
            return conn.executemany(sql, params_list)

    def fetchall(self, sql: str, params=None) -> list:
        """Execute and fetch all rows."""
        conn = self._get_conn()
        if params:
            rows = conn.execute(sql, params).fetchall()
        else:
            rows = conn.execute(sql).fetchall()
        return rows

    def fetchone(self, sql: str, params=None):
        """Execute and fetch one row."""
        conn = self._get_conn()
        if params:
            return conn.execute(sql, params).fetchone()
        return conn.execute(sql).fetchone()

    def _init_db(self):
        """Create tables and indexes if they don't exist."""
        with self.connection() as conn:
            for table_sql in TABLES_SQL.values():
                conn.execute(table_sql)
            for index_sql in INDEXES_SQL:
                conn.execute(index_sql)

            # Track schema version
            row = conn.execute(
                "SELECT MAX(version) as v FROM schema_version"
            ).fetchone()
            current = row['v'] if row and row['v'] else 0

            if current < SCHEMA_VERSION:
                conn.execute(
                    "INSERT OR REPLACE INTO schema_version (version) VALUES (?)",
                    (SCHEMA_VERSION,),
                )

    def close(self):
        """Close thread-local connection."""
        if hasattr(self._local, 'conn') and self._local.conn:
            self._local.conn.close()
            self._local.conn = None

    # Whitelist of valid table names for stats queries (no user input allowed)
    _STATS_TABLES = frozenset([
        "prices", "financial_quarterly", "foreign_flow",
        "signals_history", "market_snapshots",
    ])

    def get_table_stats(self) -> dict:
        """Return row counts for all tables."""
        stats = {}
        conn = self._get_conn()
        for t in self._STATS_TABLES:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {t}").fetchone()
            stats[t] = row['cnt'] if row else 0
        return stats


def get_db(db_path: str = None) -> DatabaseManager:
    """Get the global DatabaseManager instance (thread-safe)."""
    return DatabaseManager.get_instance(db_path)
