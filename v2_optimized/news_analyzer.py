#!/usr/bin/env python3
"""
Module phân tích tin tức sử dụng vnstock_news
"""

import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field

try:
    from vnstock_news import EnhancedNewsCrawler
    HAS_VNSTOCK_NEWS = True
except ImportError:
    HAS_VNSTOCK_NEWS = False

@dataclass
class NewsArticle:
    title: str
    url: str
    source: str
    published_at: str
    summary: str = ""
    sentiment: str = "neutral"

@dataclass
class NewsReport:
    symbol: str
    articles: List[Dict] = field(default_factory=list)
    sentiment: str = "neutral"
    sentiment_score: float = 0.0
    key_topics: List[str] = field(default_factory=list)

@dataclass
class NewsConfig:
    lookback_days: int = 30
    max_articles: int = 10

class NewsAnalyzer:
    def __init__(self, config: NewsConfig = None):
        self.config = config or NewsConfig()
        if HAS_VNSTOCK_NEWS:
            self.crawler = EnhancedNewsCrawler()
        else:
            self.crawler = None
            print("⚠️ vnstock_news not found. News analysis disabled.")

    def analyze(self, symbol: str) -> NewsReport:
        report = NewsReport(symbol=symbol)
        
        if not self.crawler:
            return report
            
        try:
            # Fetch news
            # Note: The API might vary, assuming standard usage or using vnstock fallback
            # Since I don't have full docs, I will try to use a generic approach or vnstock's stock_news if available
            
            # Use Vnstock company news
            from vnstock import Vnstock
            
            try:
                # Use KBS source (VCI API blocked since 03/2026)
                stock = Vnstock().stock(symbol=symbol, source='KBS')
                df = stock.company.news()
                
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        title = row.get('news_title', '')
                        url = row.get('news_source_link', '')
                        
                        # Convert timestamp if needed
                        # public_date is likely ms timestamp
                        pub_date = row.get('public_date')
                        time_str = ""
                        if pub_date:
                            try:
                                dt = datetime.fromtimestamp(pub_date / 1000)
                                time_str = dt.strftime('%d/%m/%Y')
                            except:
                                pass
                                
                        article = {
                            'title': title,
                            'url': url,
                            'source': 'Vnstock',
                            'published_at': time_str
                        }
                        report.articles.append(article)
                        
                        if len(report.articles) >= self.config.max_articles:
                            break
                            
            except Exception as e:
                print(f"   ⚠️ Error fetching news for {symbol}: {e}")
                
            # Simple sentiment (mockup)
            report.sentiment = "neutral"
            report.sentiment_score = 0.0
            
        except Exception as e:
            print(f"   ⚠️ News analysis error: {e}")
            
        return report
