# Phase 04: News Hub (VnNew)

## Context Links
- Parent plan: [plan.md](./plan.md)
- Dependencies: [Phase 01 - Context Memo](./phase-01-context-memo-system.md)
- Research: [Bond & RSS Research](../../plans/reports/260302-vietnamese-bond-rss-research.md)
- Current: [news_analyzer.py](../../v2_optimized/news_analyzer.py) (stub to be replaced)

## Overview
- **Date**: 2026-03-02
- **Priority**: P2
- **Status**: complete
- **Effort**: 6h
- **Description**: Replace current `news_analyzer.py` stub with `news-hub.py` -- RSS-based news crawler (Vietstock, VnEconomy, VnEconomy Finance), SQLite persistence with dedup, Vietnamese keyword sentiment scoring, and integration into Module3 scoring (+3/-5 news sentiment points).

## Key Insights
- Current `news_analyzer.py` uses `vnstock_news` (import fails) and vnstock company news (per-stock, slow, limited)
- RSS feeds tested and active: Vietstock (`vietstock.vn/rss`), VnEconomy (`vneconomy.vn/rss.html`), VnEconomy Finance (`vneconomy.vn/tai-chinh.rss`)
- `feedparser` is lightweight, no external deps, parses RSS/Atom
- Dedup by `hash(title + source)` prevents duplicate entries
- Vietnamese sentiment: keyword-based (positive: "tang", "loi nhuan", "pha dinh"; negative: "giam", "lo", "bi phat") + optional AI refinement
- Module3 `score_news` field exists but always returns 0 -- wire real sentiment
- Refresh on pipeline run (not daemon) -- one-shot crawl per run

## Requirements

### Functional
- FR1: `NewsHub` class crawls 3+ RSS feeds, returns list of articles
- FR2: SQLite table `news` with columns: id, source, title, url, published_at, sentiment, symbols, content_hash, created_at
- FR3: Dedup by `content_hash = hashlib.md5(title + source).hexdigest()`
- FR4: Vietnamese keyword-based sentiment scoring: positive (+1), negative (-1), neutral (0)
- FR5: Symbol extraction: scan title for known stock symbols (3-letter uppercase)
- FR6: `analyze_symbol(symbol)` returns: recent article count, aggregate sentiment, latest headlines
- FR7: Screener integration: `news_sentiment_score` added to Module3 scoring
- FR8: Scoring rules: positive sentiment >= +0.5 -> +3 pts; negative sentiment <= -0.5 -> -5 pts
- FR9: Maintain backward compatibility with `NewsReport` dataclass interface

### Non-Functional
- NFR1: New dependency: `feedparser` (pip install feedparser)
- NFR2: RSS crawl < 10s for 3 feeds (network dependent)
- NFR3: SQLite news table < 10MB (auto-purge articles older than 90 days)
- NFR4: Graceful feed failure: skip unavailable feeds, continue with others

## Architecture

```
news-hub.py
  |
  +-- NewsHub class
  |     +-- __init__(db_path, feeds_config)
  |     +-- refresh() -> int  # Crawl all feeds, return new article count
  |     +-- analyze_symbol(symbol) -> NewsReport  # Symbol-specific analysis
  |     +-- get_market_sentiment() -> dict  # Overall market mood
  |
  +-- _crawl_feed(url) -> list[dict]      # feedparser wrapper
  +-- _extract_symbols(title) -> list[str]  # Regex symbol extraction
  +-- _score_sentiment(title) -> float      # Vietnamese keyword scoring
  +-- _dedup_and_store(articles) -> int     # SQLite insert with hash check

database/news_store.py
  |
  +-- NewsStore class (extends BaseStore pattern)
  |     +-- create_table()
  |     +-- insert_article(article: dict)
  |     +-- get_by_symbol(symbol, days=30) -> list
  |     +-- get_recent(days=7) -> list
  |     +-- purge_old(days=90) -> int
  |     +-- exists(content_hash) -> bool
```

### RSS Feed Configuration

```python
DEFAULT_FEEDS = [
    {
        "name": "Vietstock",
        "url": "https://vietstock.vn/rss",
        "category": "stocks",
    },
    {
        "name": "VnEconomy",
        "url": "https://vneconomy.vn/rss.html",
        "category": "economy",
    },
    {
        "name": "VnEconomy Finance",
        "url": "https://vneconomy.vn/tai-chinh.rss",
        "category": "finance",
    },
]
```

### Vietnamese Sentiment Keywords

```python
POSITIVE_KEYWORDS = [
    "tang", "tang truong", "loi nhuan", "pha dinh", "dot pha",
    "tang manh", "bung no", "tich cuc", "vuot", "ky luc",
    "hoi phuc", "tang von", "co tuc", "mua rong", "khuyen nghi mua"
]

NEGATIVE_KEYWORDS = [
    "giam", "thua lo", "bi phat", "no xau", "pha san",
    "giam manh", "ban thao", "ban rong", "canh bao",
    "rui ro", "sut giam", "dinh chi", "ket qua kinh doanh te"
]
```

## Related Code Files

### Create
| File | Lines | Purpose |
|------|-------|---------|
| `v2_optimized/news-hub.py` | ~180 | RSS crawler + sentiment + symbol extraction |
| `v2_optimized/database/news_store.py` | ~100 | SQLite persistence for news |

### Modify
| File | Changes |
|------|---------|
| `v2_optimized/database/__init__.py` | Add `NewsStore` to exports |
| `v2_optimized/run_full_pipeline.py` | Import news-hub, call refresh() before Module3 |
| `v2_optimized/module3_stock_screener_v1.py` | Replace news_analyzer usage with news-hub.analyze_symbol() |

### Delete
| File | Reason |
|------|--------|
| `v2_optimized/news_analyzer.py` | Replaced by news-hub.py (keep as backup initially, remove after validation) |

## Implementation Steps

1. **Create `database/news_store.py`**
   - Follow existing store pattern (see `signal_store.py`, `foreign_flow_store.py`)
   - Schema:
     ```sql
     CREATE TABLE IF NOT EXISTS news (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         source TEXT NOT NULL,
         title TEXT NOT NULL,
         url TEXT,
         published_at TEXT,
         sentiment REAL DEFAULT 0.0,
         symbols TEXT,  -- comma-separated: "VCB,TCB,MBB"
         content_hash TEXT UNIQUE NOT NULL,
         created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
     );
     CREATE INDEX IF NOT EXISTS idx_news_symbols ON news(symbols);
     CREATE INDEX IF NOT EXISTS idx_news_published ON news(published_at);
     ```
   - `insert_article(article)`: INSERT OR IGNORE (dedup via UNIQUE content_hash)
   - `get_by_symbol(symbol, days)`: `WHERE symbols LIKE '%{symbol}%' AND published_at >= ?`
   - `get_recent(days)`: all articles within N days
   - `purge_old(days)`: DELETE WHERE created_at < N days ago
   - `exists(content_hash)`: quick check before insert

2. **Create `news-hub.py`**
   - Import feedparser, hashlib, re, unicodedata
   - `NewsHub.__init__(feeds=DEFAULT_FEEDS)`:
     - Init `NewsStore` from database package
     - Load feed config
     - Load stock universe for symbol matching
   - `refresh() -> int`:
     - For each feed: `_crawl_feed(url)` with try/except per feed
     - Extract articles, compute hash, sentiment, symbols
     - Bulk insert via `_dedup_and_store()`
     - Purge old articles (>90 days)
     - Return count of new articles
   - `_crawl_feed(url) -> list[dict]`:
     - `feedparser.parse(url)` with timeout
     - Map entry fields: title, link, published, source
     - Handle date parsing (RSS dates vary in format)
   - `_score_sentiment(title: str) -> float`:
     - Normalize: lowercase, remove diacritics (unicodedata)
     - Count positive/negative keyword matches
     - Score = (pos_count - neg_count) / max(pos_count + neg_count, 1)
     - Clamp to [-1.0, +1.0]
   - `_extract_symbols(title: str) -> list[str]`:
     - Regex: `re.findall(r'\b([A-Z]{3})\b', title)`
     - Filter against known stock universe (from Listing or cached list)
   - `analyze_symbol(symbol: str) -> NewsReport`:
     - Query `news_store.get_by_symbol(symbol, days=30)`
     - Compute aggregate sentiment (mean of article sentiments)
     - Return `NewsReport` dataclass (keep interface compatible)
   - `get_market_sentiment() -> dict`:
     - All articles from last 7 days
     - Aggregate sentiment, top topics, article count

3. **Update `database/__init__.py`**
   - Add `from .news_store import NewsStore` to imports
   - Add `NewsStore` to `__all__`

4. **Wire into `run_full_pipeline.py`**
   - Before Module3 runs:
     ```python
     news_hub = _load_kebab_module(".../news-hub.py", "news_hub")
     if news_hub:
         hub = news_hub.NewsHub()
         new_articles = hub.refresh()
         print(f"News Hub: {new_articles} new articles")
     ```
   - Pass `news_hub` instance to Module3 or save market sentiment to context memo

5. **Update Module3 integration**
   - Replace `from news_analyzer import NewsAnalyzer` with news-hub import
   - In stock screening loop: `news_report = hub.analyze_symbol(symbol)`
   - Scoring: `if news_report.sentiment_score >= 0.5: score += 3`
   - Scoring: `if news_report.sentiment_score <= -0.5: score -= 5`
   - Keep `NewsReport` dataclass interface for compatibility

6. **Save market sentiment to context memo**
   - In pipeline, after refresh: `memo.save("news", hub.get_market_sentiment())`
   - Module3 reads: overall market news mood

7. **Add feedparser to dependencies**
   - `pip install feedparser`

## Todo List

- [ ] Create `database/news_store.py` with schema + CRUD
- [ ] Create `news-hub.py` with NewsHub class
- [ ] Implement RSS crawling with feedparser
- [ ] Implement Vietnamese keyword sentiment scoring
- [ ] Implement symbol extraction from titles
- [ ] Implement dedup by content_hash
- [ ] Implement auto-purge (>90 days)
- [ ] Update database/__init__.py with NewsStore
- [ ] Wire news-hub into run_full_pipeline.py
- [ ] Replace news_analyzer usage in Module3
- [ ] Add news_sentiment_score to Module3 scoring (+3/-5)
- [ ] Save market sentiment to context memo
- [ ] Test RSS feed crawling (all 3 feeds)
- [ ] Test sentiment scoring accuracy (spot check 20 titles)
- [ ] Test full pipeline with news integration

## Success Criteria
- 3 RSS feeds crawled successfully on pipeline run
- News articles stored in SQLite with dedup (no duplicates on re-run)
- Vietnamese sentiment scoring gives reasonable positive/negative for known headlines
- Module3 scoring includes news_sentiment_score (visible in report)
- Pipeline completes even if all feeds are down (graceful degradation)
- Old articles purged automatically (>90 days)

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| RSS feed downtime | L | M | Try all 3 feeds, skip failed ones |
| Sentiment accuracy low | M | M | Keyword list tuning, optional AI refinement later |
| Symbol extraction false positives | L | M | Filter against known stock universe |
| RSS format changes | M | L | feedparser handles most RSS/Atom variants |
| High article volume | L | L | Purge >90 days, limit to 1000 per feed |

## Security Considerations
- RSS feeds are public, read-only -- no authentication needed
- No user data sent to external services
- SQLite parameterized queries prevent injection
- Content hashes use MD5 (collision resistance not critical for dedup)

## Next Steps
- Add AI-powered sentiment refinement (optional, use existing AI providers)
- Add Vietnam+ and IndochinaStock RSS feeds as secondary sources
- News alerts via Telegram for high-impact negative sentiment
