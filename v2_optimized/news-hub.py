"""
News Hub - RSS-based news crawler with Vietnamese keyword sentiment scoring.
Crawls stock market news feeds, scores sentiment, and persists to SQLite.
"""

import re
import sys
import hashlib
import unicodedata
from datetime import datetime
from typing import List, Dict, Optional

try:
    import feedparser
    _FEEDPARSER_OK = True
except ImportError:
    _FEEDPARSER_OK = False
    print("[NewsHub] feedparser not installed. Run: pip3 install feedparser")

# Vietnamese stock market RSS feeds
DEFAULT_FEEDS = [
    {"name": "Vietstock", "url": "https://vietstock.vn/rss/chung-khoan.rss", "category": "stocks"},
    {"name": "VnEconomy", "url": "https://vneconomy.vn/chung-khoan.rss", "category": "stocks"},
    {"name": "CafeF", "url": "https://cafef.vn/rss/thi-truong-chung-khoan.rss", "category": "stocks"},
]

# Keywords for Vietnamese sentiment scoring (no diacritics - normalized)
POSITIVE_KEYWORDS = [
    "tang", "tang truong", "loi nhuan", "pha dinh", "dot pha",
    "tang manh", "bung no", "tich cuc", "vuot", "ky luc",
    "hoi phuc", "tang von", "co tuc", "mua rong", "khuyen nghi mua",
    "tich luy", "but pha", "xuat sac", "hieu qua", "tin tuong",
]

NEGATIVE_KEYWORDS = [
    "giam", "thua lo", "bi phat", "no xau", "pha san",
    "giam manh", "ban thao", "ban rong", "canh bao",
    "rui ro", "sut giam", "dinh chi", "lo von", "vi pham",
    "xu ly", "khieu kien", "thua kien", "cam giao dich",
]

# Known 3-letter VN stock symbols to filter regex matches
_KNOWN_SYMBOLS: Optional[set] = None


def _get_known_symbols() -> set:
    """Load known symbols lazily from stock_universe or fallback set."""
    global _KNOWN_SYMBOLS
    if _KNOWN_SYMBOLS is not None:
        return _KNOWN_SYMBOLS
    # Common liquid VN stocks as fallback
    fallback = {
        "VCB", "BID", "CTG", "MBB", "TCB", "VPB", "ACB", "HDB", "STB", "TPB",
        "HPG", "HSG", "NKG", "VNM", "SAB", "MSN", "MCH", "QNS", "VHC", "ANV",
        "FPT", "CMG", "FOX", "VIC", "VHM", "VRE", "PDR", "NVL", "KDH", "DXG",
        "GAS", "PLX", "PVS", "BSR", "OIL", "PVD", "GVR", "HAG", "HNG", "TAR",
        "DRC", "CSM", "SCS", "AST", "VJC", "HVN", "REE", "PPC", "EIB", "LPB",
    }
    _KNOWN_SYMBOLS = fallback
    return _KNOWN_SYMBOLS


def _normalize_vn(text: str) -> str:
    """Remove Vietnamese diacritics, lowercase, normalize spaces."""
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", ascii_only.lower().strip())


class NewsHub:
    """
    RSS news crawler with Vietnamese sentiment analysis.

    Usage:
        hub = NewsHub()
        new_count = hub.refresh()
        result = hub.analyze_symbol("VCB")
        market = hub.get_market_sentiment()
    """

    def __init__(self, feeds: List[Dict] = None):
        self.feeds = feeds or DEFAULT_FEEDS
        self._store = None
        self._init_store()

    def _init_store(self):
        """Initialize news store, fail silently if DB unavailable."""
        try:
            # Import from same package directory
            import os
            sys.path.insert(0, os.path.dirname(__file__))
            from database.news_store import NewsStore
            self._store = NewsStore()
        except Exception as e:
            print(f"[NewsHub] Store init failed (news won't persist): {e}")
            self._store = None

    def refresh(self) -> int:
        """
        Crawl all feeds, deduplicate, persist new articles.
        Returns count of new articles inserted.
        """
        if not _FEEDPARSER_OK:
            return 0

        total_new = 0
        for feed_cfg in self.feeds:
            try:
                articles = self._crawl_feed(feed_cfg)
                for article in articles:
                    if self._store:
                        inserted = self._store.insert_article(article)
                        if inserted:
                            total_new += 1
                    else:
                        total_new += 1  # Count even without persistence
            except Exception as e:
                print(f"[NewsHub] Feed {feed_cfg.get('name')} error: {e}")

        # Purge old articles (90 days)
        if self._store:
            try:
                self._store.purge_old(days=90)
            except Exception:
                pass

        return total_new

    def analyze_symbol(self, symbol: str) -> Dict:
        """
        Get news sentiment for a specific symbol.
        Returns dict compatible with existing NewsReport interface.
        """
        if not self._store:
            return {"sentiment_score": 0.0, "article_count": 0, "headlines": []}

        try:
            articles = self._store.get_by_symbol(symbol, days=30)
            if not articles:
                return {"sentiment_score": 0.0, "article_count": 0, "headlines": []}

            sentiments = [a.get("sentiment", 0.0) for a in articles if a.get("sentiment") is not None]
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
            headlines = [a.get("title", "") for a in articles[:5]]

            return {
                "sentiment_score": round(avg_sentiment, 3),
                "article_count": len(articles),
                "headlines": headlines,
            }
        except Exception as e:
            print(f"[NewsHub] analyze_symbol error: {e}")
            return {"sentiment_score": 0.0, "article_count": 0, "headlines": []}

    def get_market_sentiment(self) -> Dict:
        """
        Compute overall market sentiment from recent articles.
        Returns summary dict for memo/reporting.
        """
        if not self._store:
            return {"avg_sentiment": 0.0, "total_articles": 0, "positive": 0, "negative": 0}

        try:
            articles = self._store.get_recent(days=7)
            if not articles:
                return {"avg_sentiment": 0.0, "total_articles": 0, "positive": 0, "negative": 0}

            sentiments = [a.get("sentiment", 0.0) for a in articles]
            avg = sum(sentiments) / len(sentiments) if sentiments else 0.0
            positive = sum(1 for s in sentiments if s > 0.3)
            negative = sum(1 for s in sentiments if s < -0.3)

            return {
                "avg_sentiment": round(avg, 3),
                "total_articles": len(articles),
                "positive": positive,
                "negative": negative,
            }
        except Exception as e:
            print(f"[NewsHub] get_market_sentiment error: {e}")
            return {"avg_sentiment": 0.0, "total_articles": 0, "positive": 0, "negative": 0}

    def _crawl_feed(self, feed: Dict) -> List[Dict]:
        """Parse RSS feed and return list of article dicts."""
        articles = []
        parsed = feedparser.parse(feed["url"])

        for entry in parsed.entries:
            try:
                title = entry.get("title", "").strip()
                if not title:
                    continue

                url = entry.get("link", "")
                published = ""
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    import time
                    published = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M:%S")
                elif hasattr(entry, "published"):
                    published = entry.get("published", "")

                sentiment = self._score_sentiment(title)
                symbols = self._extract_symbols(title)
                content_hash = hashlib.md5(f"{title}{url}".encode("utf-8")).hexdigest()

                articles.append({
                    "source": feed["name"],
                    "title": title,
                    "url": url,
                    "published_at": published,
                    "sentiment": sentiment,
                    "symbols": ",".join(symbols),
                    "content_hash": content_hash,
                })
            except Exception:
                continue

        return articles

    def _score_sentiment(self, title: str) -> float:
        """
        Score sentiment of a Vietnamese news title.
        Returns float in range [-1.0, 1.0].
        """
        normalized = _normalize_vn(title)

        positive_hits = sum(1 for kw in POSITIVE_KEYWORDS if kw in normalized)
        negative_hits = sum(1 for kw in NEGATIVE_KEYWORDS if kw in normalized)

        total = positive_hits + negative_hits
        if total == 0:
            return 0.0

        # Score: ratio capped at ±1.0
        score = (positive_hits - negative_hits) / total
        return round(max(-1.0, min(1.0, score)), 3)

    def _extract_symbols(self, title: str) -> List[str]:
        """Extract 3-letter uppercase stock symbols from title."""
        known = _get_known_symbols()
        matches = re.findall(r"\b([A-Z]{3})\b", title)
        return [m for m in matches if m in known]


if __name__ == "__main__":
    # Quick smoke test
    hub = NewsHub()
    print("Refreshing news...")
    new_count = hub.refresh()
    print(f"New articles: {new_count}")
    print("Market sentiment:", hub.get_market_sentiment())
    print("VCB sentiment:", hub.analyze_symbol("VCB"))
