#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     NEWS ANALYZER - PHÂN TÍCH TIN TỨC ẢNH HƯỞNG GIÁ                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Sử dụng vnstock_news v2.1.3 để:                                             ║
║  - Thu thập tin tức từ các nguồn Việt Nam                                    ║
║  - Lọc tin liên quan đến VNIndex, ngành, cổ phiếu                           ║
║  - Phân tích sentiment và trending topics                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import asyncio
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

import pandas as pd

warnings.filterwarnings('ignore')

# Import từ config
from config import get_config

# Import vnstock_news
try:
    from vnstock_news import EnhancedNewsCrawler, list_supported_sites
    from vnstock_news.trending.analyzer import TrendingAnalyzer
    HAS_NEWS = True
except ImportError as e:
    print(f"⚠️ vnstock_news chưa cài: {e}")
    HAS_NEWS = False

# Import AI
try:
    from ai_providers import AIProvider, AIConfig
except ImportError:
    AIProvider = None


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class NewsConfig:
    """Config cho News Analyzer"""
    
    # Sites để crawl
    SITES: List[str] = field(default_factory=lambda: [
        'cafef', 'vietstock', 'vneconomy', 'vnexpress'
    ])
    
    # Số bài mỗi site
    MAX_ARTICLES: int = 50
    
    # Time window
    TIME_WINDOW: str = '24h'
    
    # Keywords để filter
    MARKET_KEYWORDS: List[str] = field(default_factory=lambda: [
        'vnindex', 'vn-index', 'chứng khoán', 'thị trường',
        'cổ phiếu', 'bluechip', 'vn30', 'hose', 'hnx'
    ])
    
    SECTOR_KEYWORDS: Dict[str, List[str]] = field(default_factory=lambda: {
        'VNFIN': ['ngân hàng', 'bank', 'chứng khoán', 'bảo hiểm', 'tài chính'],
        'VNREAL': ['bất động sản', 'địa ốc', 'nhà đất', 'căn hộ', 'dự án'],
        'VNMAT': ['thép', 'xi măng', 'vật liệu', 'xây dựng', 'hóa chất'],
        'VNIT': ['công nghệ', 'phần mềm', 'fpt', 'cmg', 'viễn thông'],
        'VNHEAL': ['y tế', 'dược phẩm', 'bệnh viện', 'sức khỏe'],
        'VNCOND': ['bán lẻ', 'tiêu dùng', 'ô tô', 'xe máy', 'thương mại'],
        'VNCONS': ['thực phẩm', 'đồ uống', 'vinamilk', 'sữa', 'bia']
    })
    
    # Output
    OUTPUT_DIR: str = "./output"
    
    # AI
    AI_PROVIDER: str = ""
    AI_API_KEY: str = ""


def create_config() -> NewsConfig:
    unified = get_config()
    config = NewsConfig()
    config.OUTPUT_DIR = unified.output.OUTPUT_DIR
    ai_provider, ai_key = unified.get_ai_provider()
    config.AI_PROVIDER = ai_provider
    config.AI_API_KEY = ai_key
    return config


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class NewsArticle:
    """Bài báo"""
    title: str
    url: str
    source: str
    publish_time: str = ""
    description: str = ""
    content: str = ""
    
    # Analysis
    sentiment: str = "neutral"  # positive/negative/neutral
    relevance: str = ""  # market/sector/stock
    related_sectors: List[str] = field(default_factory=list)
    related_stocks: List[str] = field(default_factory=list)


@dataclass
class NewsReport:
    """Báo cáo tin tức"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Articles
    total_articles: int = 0
    market_news: List[NewsArticle] = field(default_factory=list)
    sector_news: Dict[str, List[NewsArticle]] = field(default_factory=dict)
    
    # Trending
    trending_topics: List[str] = field(default_factory=list)
    
    # AI
    ai_summary: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# NEWS ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class NewsAnalyzer:
    """Phân tích tin tức"""
    
    def __init__(self, config: NewsConfig):
        self.config = config
        self.crawler = None
        self.trending = None
        
        if HAS_NEWS:
            self.crawler = EnhancedNewsCrawler(
                cache_enabled=True,
                cache_ttl=3600,
                max_concurrency=4
            )
            self.trending = TrendingAnalyzer(min_token_length=3)
    
    async def fetch_news(self) -> NewsReport:
        """Fetch và phân tích tin tức"""
        print("\n" + "="*60)
        print("📰 NEWS ANALYZER - THU THẬP TIN TỨC")
        print("="*60)
        
        report = NewsReport()
        
        if not HAS_NEWS:
            print("❌ vnstock_news chưa cài đặt!")
            return report
        
        # 1. Crawl từ các site
        print(f"\n[1/3] Crawling từ {len(self.config.SITES)} sites...")
        all_articles = []
        
        for site in self.config.SITES:
            print(f"   📰 {site}...", end=" ")
            try:
                df = await self.crawler.fetch_articles_async(
                    sources=[f"{site}"],
                    site_name=site,
                    max_articles=self.config.MAX_ARTICLES,
                    time_frame=self.config.TIME_WINDOW,
                    clean_content=True,
                    sort_order='desc'
                )
                
                if df is not None and not df.empty:
                    for _, row in df.iterrows():
                        article = NewsArticle(
                            title=row.get('title', ''),
                            url=row.get('url', ''),
                            source=site,
                            publish_time=str(row.get('publish_time', '')),
                            description=row.get('short_description', ''),
                            content=row.get('content', '')[:500] if row.get('content') else ''
                        )
                        all_articles.append(article)
                        
                        # Update trending
                        text = f"{article.title} {article.description}"
                        self.trending.update_trends(text)
                    
                    print(f"✓ {len(df)} bài")
                else:
                    print("✗ 0 bài")
                    
            except Exception as e:
                print(f"✗ {e}")
        
        report.total_articles = len(all_articles)
        print(f"\n   Tổng: {report.total_articles} bài")
        
        # 2. Filter theo keywords
        print("\n[2/3] Lọc tin theo keywords...")
        report.market_news = self._filter_market_news(all_articles)
        report.sector_news = self._filter_sector_news(all_articles)
        
        print(f"   ✓ Tin thị trường: {len(report.market_news)} bài")
        for sector, news in report.sector_news.items():
            if news:
                print(f"   ✓ {sector}: {len(news)} bài")
        
        # 3. Trending topics
        print("\n[3/3] Phân tích trending...")
        trends = self.trending.get_top_trends(10)
        report.trending_topics = list(trends.keys())
        print(f"   ✓ Top trending: {', '.join(report.trending_topics[:5])}")
        
        return report
    
    def _filter_market_news(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Lọc tin thị trường"""
        result = []
        for article in articles:
            text = f"{article.title} {article.description}".lower()
            for kw in self.config.MARKET_KEYWORDS:
                if kw.lower() in text:
                    article.relevance = "market"
                    result.append(article)
                    break
        return result[:20]  # Top 20
    
    def _filter_sector_news(self, articles: List[NewsArticle]) -> Dict[str, List[NewsArticle]]:
        """Lọc tin theo ngành"""
        result = {sector: [] for sector in self.config.SECTOR_KEYWORDS}
        
        for article in articles:
            text = f"{article.title} {article.description}".lower()
            
            for sector, keywords in self.config.SECTOR_KEYWORDS.items():
                for kw in keywords:
                    if kw.lower() in text:
                        article.relevance = "sector"
                        article.related_sectors.append(sector)
                        result[sector].append(article)
                        break
        
        # Top 5 mỗi ngành
        for sector in result:
            result[sector] = result[sector][:5]
        
        return result


# ══════════════════════════════════════════════════════════════════════════════
# AI SUMMARIZER
# ══════════════════════════════════════════════════════════════════════════════

class NewsSummarizer:
    """Tóm tắt tin tức bằng AI"""
    
    def __init__(self, config: NewsConfig):
        self.config = config
        self.ai = self._init_ai()
    
    def _init_ai(self):
        if not self.config.AI_API_KEY or AIProvider is None:
            return None
        try:
            return AIProvider(AIConfig(
                provider=self.config.AI_PROVIDER,
                api_key=self.config.AI_API_KEY,
                system_prompt="Bạn là chuyên gia phân tích tin tức chứng khoán."
            ))
        except:
            return None
    
    def summarize(self, report: NewsReport) -> str:
        """Tóm tắt tin tức"""
        if not self.ai:
            return "⚠️ AI chưa cấu hình"
        
        # Build news list
        market_titles = "\n".join([f"- {a.title}" for a in report.market_news[:10]])
        
        sector_news_str = ""
        for sector, news in report.sector_news.items():
            if news:
                titles = "\n".join([f"  - {a.title}" for a in news[:3]])
                sector_news_str += f"\n{sector}:\n{titles}"
        
        prompt = f"""
TIN TỨC CHỨNG KHOÁN - {report.timestamp.strftime('%d/%m/%Y')}

📈 TIN THỊ TRƯỜNG (Top 10):
{market_titles}

🏭 TIN NGÀNH:
{sector_news_str}

🔥 TRENDING: {', '.join(report.trending_topics[:5])}

Hãy phân tích:
1. TIN QUAN TRỌNG nhất hôm nay (2-3 tin)
2. TÁC ĐỘNG đến VNIndex ngắn hạn (tăng/giảm/sideway)
3. NGÀNH được hưởng lợi / bị ảnh hưởng
4. CẢNH BÁO rủi ro nếu có
"""
        try:
            return self.ai.chat(prompt)
        except Exception as e:
            return f"❌ {e}"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MODULE
# ══════════════════════════════════════════════════════════════════════════════

class NewsAnalyzerModule:
    """Module News Analyzer"""
    
    def __init__(self):
        self.config = create_config()
        self.analyzer = NewsAnalyzer(self.config)
        self.summarizer = NewsSummarizer(self.config)
        self.report: NewsReport = None
    
    def run(self) -> NewsReport:
        """Chạy module"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║     NEWS ANALYZER - PHÂN TÍCH TIN TỨC CHỨNG KHOÁN            ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # Fetch
        self.report = asyncio.run(self.analyzer.fetch_news())
        
        # Summarize
        print("\n[4/4] AI Summary...")
        self.report.ai_summary = self.summarizer.summarize(self.report)
        
        # Print & Save
        self._print_report()
        self._save_report()
        
        return self.report
    
    def _print_report(self):
        print("\n" + "="*60)
        print("📰 TÓM TẮT TIN TỨC")
        print("="*60)
        
        print(f"\n📈 TIN THỊ TRƯỜNG ({len(self.report.market_news)} bài):")
        for i, article in enumerate(self.report.market_news[:5], 1):
            print(f"   {i}. {article.title[:60]}...")
            print(f"      📅 {article.publish_time} | 🔗 {article.source}")
        
        print(f"\n🔥 TRENDING: {', '.join(self.report.trending_topics[:5])}")
        
        print("\n" + "-"*60)
        print("🤖 AI SUMMARY:")
        print(self.report.ai_summary)
    
    def _save_report(self):
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        
        filename = os.path.join(
            self.config.OUTPUT_DIR,
            f"news_analysis_{self.report.timestamp.strftime('%Y%m%d_%H%M')}.md"
        )
        
        market_rows = "\n".join([
            f"| {i+1} | [{a.title[:50]}...]({a.url}) | {a.source} | {a.publish_time} |"
            for i, a in enumerate(self.report.market_news[:10])
        ])
        
        content = f"""# PHÂN TÍCH TIN TỨC CHỨNG KHOÁN
**Ngày:** {self.report.timestamp.strftime('%d/%m/%Y %H:%M')}

## THỐNG KÊ
- Tổng số bài: {self.report.total_articles}
- Tin thị trường: {len(self.report.market_news)}
- Trending: {', '.join(self.report.trending_topics[:5])}

## TIN THỊ TRƯỜNG (Top 10)

| # | Tiêu đề | Nguồn | Thời gian |
|---|---------|-------|-----------|
{market_rows}

## AI SUMMARY
{self.report.ai_summary}
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\n✓ Đã lưu: {filename}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    module = NewsAnalyzerModule()
    report = module.run()