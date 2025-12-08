#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           NEWS ANALYZER MODULE                               ║
║             Phân tích tin tức cho Stock Screening (CANSLIM "N")              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Features:                                                                   ║
║  - Crawl tin tức từ CafeF, VnExpress, BaoDauTu                              ║
║  - Filter tin tức theo mã cổ phiếu                                          ║
║  - Sentiment scoring (positive/negative keywords)                            ║
║  - News score cho CANSLIM "N" factor                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import pandas as pd

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from v2_optimized.config import get_config, APIKeys
except ImportError:
    from config import get_config, APIKeys

# Set API key before importing vnstock_news
os.environ['VNSTOCK_API_KEY'] = APIKeys.VNSTOCK

try:
    from vnstock_news.core.crawler import Crawler
    from vnstock_news.core.batch import BatchCrawler
    HAS_VNSTOCK_NEWS = True
except ImportError:
    HAS_VNSTOCK_NEWS = False
    print("⚠️ vnstock_news not available. Install with: pip install vnstock-news")


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class NewsArticle:
    """Một bài viết tin tức"""
    url: str = ""
    title: str = ""
    content: str = ""
    publish_time: datetime = None
    source: str = ""
    category: str = ""
    sentiment_score: float = 0.0  # -1 to 1


@dataclass
class NewsAnalysisResult:
    """Kết quả phân tích tin tức cho một mã"""
    symbol: str = ""
    total_articles: int = 0
    positive_articles: int = 0
    negative_articles: int = 0
    neutral_articles: int = 0
    avg_sentiment: float = 0.0
    news_score: float = 50.0  # 0-100
    recent_headlines: List[str] = field(default_factory=list)
    has_breaking_news: bool = False
    summary: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# SENTIMENT KEYWORDS
# ══════════════════════════════════════════════════════════════════════════════

POSITIVE_KEYWORDS = [
    # Business growth
    "tăng trưởng", "lợi nhuận tăng", "doanh thu tăng", "kỷ lục", "vượt kế hoạch",
    "đột phá", "tích cực", "khởi sắc", "phục hồi", "bứt phá",
    # Market signals
    "mua vào", "khối ngoại mua", "tăng giá", "breakout", "vượt đỉnh",
    "thanh khoản tăng", "thu hút", "nóng", "bùng nổ",
    # Fundamentals
    "cổ tức", "chia thưởng", "phát hành", "M&A", "hợp tác",
    "ký hợp đồng", "trúng thầu", "mở rộng", "đầu tư",
    # Ratings
    "khuyến nghị mua", "outperform", "overweight", "nâng mục tiêu",
]

NEGATIVE_KEYWORDS = [
    # Business decline
    "giảm", "lỗ", "thua lỗ", "sụt giảm", "suy yếu",
    "khó khăn", "thách thức", "rủi ro", "cắt giảm", "thu hẹp",
    # Market signals
    "bán tháo", "khối ngoại bán", "giảm giá", "breakdown", "mất mốc",
    "thanh khoản thấp", "điều chỉnh", "lao dốc", "bốc hơi",
    # Problems
    "nợ xấu", "vi phạm", "phạt", "kiện", "scandal",
    "truy thu", "thanh tra", "cảnh báo", "đình chỉ",
    # Ratings
    "khuyến nghị bán", "underperform", "underweight", "hạ mục tiêu",
]


# ══════════════════════════════════════════════════════════════════════════════
# NEWS ANALYZER CLASS
# ══════════════════════════════════════════════════════════════════════════════

class NewsAnalyzer:
    """
    Phân tích tin tức cho CANSLIM screening
    
    - "N" trong CANSLIM = New (sản phẩm mới, quản lý mới, high mới)
    - Tin tức tích cực về sản phẩm mới, hợp tác, mở rộng = điểm cộng
    """
    
    TARGET_SITES = ['cafef', 'vnexpress', 'baodautu']
    
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        if HAS_VNSTOCK_NEWS:
            print("✓ NewsAnalyzer initialized with vnstock_news")
        else:
            print("⚠️ NewsAnalyzer running without vnstock_news")
    
    def analyze_symbol(self, symbol: str, days_back: int = 7) -> NewsAnalysisResult:
        """
        Phân tích tin tức cho một mã cổ phiếu
        
        Args:
            symbol: Mã cổ phiếu (VD: VCB, FPT)
            days_back: Số ngày lùi lại để tìm tin
            
        Returns:
            NewsAnalysisResult với sentiment và score
        """
        result = NewsAnalysisResult(symbol=symbol)
        
        if not HAS_VNSTOCK_NEWS:
            result.summary = "News analysis unavailable"
            return result
        
        print(f"   📰 Analyzing news for {symbol}...")
        
        # Fetch articles từ các nguồn
        all_articles = self._fetch_articles(limit_per_site=30)
        
        # Filter theo symbol
        symbol_articles = self._filter_by_symbol(all_articles, symbol)
        
        # Filter theo thời gian
        cutoff_date = datetime.now() - timedelta(days=days_back)
        recent_articles = [
            a for a in symbol_articles 
            if a.publish_time and a.publish_time >= cutoff_date
        ]
        
        if not recent_articles:
            result.summary = f"Không có tin tức về {symbol} trong {days_back} ngày qua"
            return result
        
        # Analyze sentiment cho từng bài
        for article in recent_articles:
            article.sentiment_score = self._analyze_sentiment(article)
        
        # Aggregate results
        result.total_articles = len(recent_articles)
        result.positive_articles = len([a for a in recent_articles if a.sentiment_score > 0.2])
        result.negative_articles = len([a for a in recent_articles if a.sentiment_score < -0.2])
        result.neutral_articles = result.total_articles - result.positive_articles - result.negative_articles
        
        sentiments = [a.sentiment_score for a in recent_articles]
        result.avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0
        
        # Calculate news score (0-100)
        result.news_score = self._calculate_news_score(result)
        
        # Get recent headlines
        result.recent_headlines = [a.title for a in recent_articles[:5]]
        
        # Check for breaking news
        result.has_breaking_news = any(
            "nóng" in a.title.lower() or "breaking" in a.title.lower()
            for a in recent_articles
        )
        
        # Summary
        sentiment_text = "tích cực" if result.avg_sentiment > 0 else ("tiêu cực" if result.avg_sentiment < 0 else "trung lập")
        result.summary = f"{result.total_articles} tin ({result.positive_articles}+ / {result.negative_articles}-), sentiment {sentiment_text}"
        
        print(f"      ✓ {result.summary}")
        
        return result
    
    def _fetch_articles(self, limit_per_site: int = 30) -> List[NewsArticle]:
        """Fetch articles từ các nguồn tin"""
        all_articles = []
        
        for site in self.TARGET_SITES:
            try:
                crawler = Crawler(site_name=site)
                
                # Thử lấy từ RSS feed trước (nhanh hơn)
                try:
                    articles_data = crawler.get_articles_from_feed(limit_per_feed=limit_per_site)
                except:
                    articles_data = crawler.get_latest_articles(limit=limit_per_site)
                
                if articles_data is not None and len(articles_data) > 0:
                    # Convert to NewsArticle objects
                    if isinstance(articles_data, pd.DataFrame):
                        for _, row in articles_data.iterrows():
                            article = NewsArticle(
                                url=row.get('url', ''),
                                title=row.get('title', ''),
                                content=row.get('content', row.get('short_description', '')),
                                publish_time=pd.to_datetime(row.get('publish_time')) if row.get('publish_time') else None,
                                source=site,
                                category=row.get('category', '')
                            )
                            all_articles.append(article)
                    elif isinstance(articles_data, list):
                        for item in articles_data:
                            article = NewsArticle(
                                url=item.get('url', ''),
                                title=item.get('title', ''),
                                content=item.get('content', item.get('short_description', '')),
                                publish_time=pd.to_datetime(item.get('publish_time')) if item.get('publish_time') else None,
                                source=site,
                                category=item.get('category', '')
                            )
                            all_articles.append(article)
                    
                    print(f"      ✓ {site}: {len(articles_data)} articles")
                    
            except Exception as e:
                print(f"      ✗ {site}: {e}")
        
        return all_articles
    
    def _filter_by_symbol(self, articles: List[NewsArticle], symbol: str) -> List[NewsArticle]:
        """Filter articles có đề cập đến symbol"""
        symbol_upper = symbol.upper()
        symbol_lower = symbol.lower()
        
        # Các biến thể của symbol (VD: VCB, Vietcombank)
        symbol_variants = [symbol_upper, symbol_lower]
        
        # Thêm tên công ty phổ biến
        company_names = {
            "VCB": ["vietcombank", "ngoại thương"],
            "FPT": ["fpt"],
            "VNM": ["vinamilk"],
            "VIC": ["vingroup"],
            "VHM": ["vinhomes"],
            "MWG": ["thế giới di động", "mobile world"],
            "HPG": ["hòa phát", "hoa phat"],
            "TCB": ["techcombank"],
            "ACB": ["á châu"],
            "BID": ["bidv"],
        }
        
        if symbol_upper in company_names:
            symbol_variants.extend(company_names[symbol_upper])
        
        filtered = []
        for article in articles:
            text_to_search = (article.title + " " + article.content).lower()
            if any(variant.lower() in text_to_search for variant in symbol_variants):
                filtered.append(article)
        
        return filtered
    
    def _analyze_sentiment(self, article: NewsArticle) -> float:
        """
        Phân tích sentiment của một bài viết
        
        Returns:
            Score từ -1 (rất tiêu cực) đến 1 (rất tích cực)
        """
        text = (article.title + " " + article.content).lower()
        
        positive_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
        negative_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
        
        total = positive_count + negative_count
        if total == 0:
            return 0.0
        
        # Score = (positive - negative) / total, normalized to [-1, 1]
        score = (positive_count - negative_count) / total
        
        # Weight by title (title keywords count more)
        title_positive = sum(1 for kw in POSITIVE_KEYWORDS if kw in article.title.lower())
        title_negative = sum(1 for kw in NEGATIVE_KEYWORDS if kw in article.title.lower())
        
        title_score = 0
        title_total = title_positive + title_negative
        if title_total > 0:
            title_score = (title_positive - title_negative) / title_total
        
        # Final score = 60% content + 40% title
        final_score = score * 0.6 + title_score * 0.4
        
        return max(-1, min(1, final_score))
    
    def _calculate_news_score(self, result: NewsAnalysisResult) -> float:
        """
        Tính news score (0-100) cho CANSLIM
        
        Scoring logic:
        - Base: 50
        - Positive sentiment: +25 max
        - Negative sentiment: -25 max
        - Volume of coverage: ±10
        - Breaking news: +5
        """
        base = 50
        
        # Sentiment impact (±25)
        sentiment_impact = result.avg_sentiment * 25
        
        # Coverage impact (capped at ±10)
        coverage_impact = 0
        if result.total_articles >= 5:
            coverage_impact = 5
        if result.total_articles >= 10:
            coverage_impact = 10
        
        # If sentiment is negative, more coverage = more negative
        if result.avg_sentiment < 0:
            coverage_impact = -coverage_impact
        
        # Breaking news bonus
        breaking_bonus = 5 if result.has_breaking_news else 0
        
        # Calculate final score
        score = base + sentiment_impact + coverage_impact + breaking_bonus
        
        return max(0, min(100, score))


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def analyze_news(symbol: str, days_back: int = 7) -> Dict:
    """
    Quick analysis cho một mã
    
    Returns:
        Dict với news_score và summary
    """
    analyzer = NewsAnalyzer()
    result = analyzer.analyze_symbol(symbol, days_back)
    
    return {
        'symbol': result.symbol,
        'news_score': result.news_score,
        'total_articles': result.total_articles,
        'sentiment': result.avg_sentiment,
        'positive': result.positive_articles,
        'negative': result.negative_articles,
        'headlines': result.recent_headlines[:3],
        'summary': result.summary
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("NEWS ANALYZER - TEST")
    print("=" * 70)
    
    symbols = ['VCB', 'FPT', 'VIC']
    
    analyzer = NewsAnalyzer()
    
    for symbol in symbols:
        print(f"\n📰 Analyzing {symbol}...")
        print("-" * 50)
        
        result = analyzer.analyze_symbol(symbol, days_back=7)
        
        print(f"\n✓ Results for {symbol}:")
        print(f"   News Score: {result.news_score:.1f}/100")
        print(f"   Articles: {result.total_articles} ({result.positive_articles}+ / {result.negative_articles}-)")
        print(f"   Sentiment: {result.avg_sentiment:+.2f}")
        
        if result.recent_headlines:
            print(f"   Headlines:")
            for h in result.recent_headlines[:3]:
                print(f"     • {h[:60]}...")
