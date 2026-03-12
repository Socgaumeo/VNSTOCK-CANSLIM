"""
News store for persisting crawled news articles in SQLite.
Follows the same pattern as signal_store.py and foreign_flow_store.py.
"""

from datetime import datetime
from typing import List, Dict, Optional

from .db_manager import get_db

NEWS_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        title TEXT NOT NULL,
        url TEXT,
        published_at TEXT,
        sentiment REAL DEFAULT 0.0,
        symbols TEXT,
        content_hash TEXT UNIQUE NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
"""

NEWS_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at)",
    "CREATE INDEX IF NOT EXISTS idx_news_hash ON news(content_hash)",
    "CREATE INDEX IF NOT EXISTS idx_news_source ON news(source)",
]


class NewsStore:
    """
    SQLite-backed store for news articles.

    Usage:
        store = NewsStore()
        store.insert_article({
            "source": "Vietstock", "title": "VCB tang manh",
            "url": "...", "published_at": "2026-03-03",
            "sentiment": 0.5, "symbols": "VCB", "content_hash": "abc123"
        })
    """

    def __init__(self, db=None):
        self.db = db or get_db()
        self._ensure_table()

    def _ensure_table(self):
        """Create news table and indexes if they don't exist."""
        try:
            with self.db.connection() as conn:
                conn.execute(NEWS_TABLE_SQL)
                for idx_sql in NEWS_INDEXES_SQL:
                    conn.execute(idx_sql)
        except Exception as e:
            print(f"[NewsStore] Table init error: {e}")

    def insert_article(self, article: dict) -> bool:
        """
        Insert a news article. Silently ignores duplicates (INSERT OR IGNORE).
        Returns True if inserted, False if duplicate.
        """
        try:
            with self.db.connection() as conn:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO news
                       (source, title, url, published_at, sentiment, symbols, content_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        article.get("source", ""),
                        article.get("title", ""),
                        article.get("url", ""),
                        article.get("published_at", ""),
                        float(article.get("sentiment", 0.0)),
                        article.get("symbols", ""),
                        article.get("content_hash", ""),
                    ),
                )
                return cur.rowcount > 0
        except Exception as e:
            print(f"[NewsStore] insert_article error: {e}")
            return False

    def get_by_symbol(self, symbol: str, days: int = 30) -> List[Dict]:
        """Get articles mentioning a symbol in the last N days."""
        try:
            rows = self.db.fetchall(
                """SELECT * FROM news
                   WHERE symbols LIKE ?
                   AND (published_at >= date('now', ?) OR published_at IS NULL OR published_at = '')
                   ORDER BY published_at DESC""",
                (f"%{symbol}%", f"-{days} days"),
            )
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"[NewsStore] get_by_symbol error: {e}")
            return []

    def get_recent(self, days: int = 7) -> List[Dict]:
        """Get all recent articles from the last N days."""
        try:
            rows = self.db.fetchall(
                """SELECT * FROM news
                   WHERE published_at >= date('now', ?)
                   ORDER BY published_at DESC""",
                (f"-{days} days",),
            )
            return [dict(r) for r in rows]
        except Exception as e:
            print(f"[NewsStore] get_recent error: {e}")
            return []

    def purge_old(self, days: int = 90) -> int:
        """Delete articles older than N days. Returns count deleted."""
        try:
            with self.db.connection() as conn:
                cur = conn.execute(
                    "DELETE FROM news WHERE published_at < date('now', ?)",
                    (f"-{days} days",),
                )
                return cur.rowcount
        except Exception as e:
            print(f"[NewsStore] purge_old error: {e}")
            return 0

    def exists(self, content_hash: str) -> bool:
        """Check if an article with the given hash already exists."""
        try:
            row = self.db.fetchone(
                "SELECT id FROM news WHERE content_hash=?",
                (content_hash,),
            )
            return row is not None
        except Exception as e:
            print(f"[NewsStore] exists error: {e}")
            return False
