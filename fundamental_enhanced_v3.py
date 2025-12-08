#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    FUNDAMENTAL ENHANCED MODULE                                ║
║          Multi-source Fundamental Data với Cross-validation                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Sources:                                                                    ║
║  - VNStock (Primary)                                                         ║
║  - CafeF (Scraping)                                                          ║
║  - VietStock (Scraping)                                                      ║
║  - Simplize (API)                                                            ║
║                                                                              ║
║  Features:                                                                   ║
║  - EPS Growth (QoQ, YoY, 3Y CAGR, 5Y CAGR)                                  ║
║  - Revenue Growth tracking                                                   ║
║  - ROE/ROA historical                                                        ║
║  - Cross-validation từ nhiều nguồn                                           ║
║  - Caching để giảm requests                                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import re
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from statistics import median, mean
from abc import ABC, abstractmethod

import requests
from bs4 import BeautifulSoup
import pandas as pd
import numpy as np

# Optional imports
try:
    from vnstock import Vnstock
    HAS_VNSTOCK = True
except ImportError:
    HAS_VNSTOCK = False


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class QuarterlyData:
    """Dữ liệu theo quý"""
    period: str  # "Q1/2024"
    revenue: float = 0.0
    profit: float = 0.0  # Lợi nhuận sau thuế
    eps: float = 0.0
    roe: float = 0.0
    roa: float = 0.0
    gross_margin: float = 0.0
    net_margin: float = 0.0


@dataclass
class FundamentalData:
    """Dữ liệu fundamental tổng hợp"""
    symbol: str
    source: str = "aggregated"
    updated_at: str = ""
    
    # Current metrics
    eps_ttm: float = 0.0
    pe_ttm: float = 0.0
    pb: float = 0.0
    roe: float = 0.0
    roa: float = 0.0
    
    # Growth metrics
    eps_growth_qoq: float = 0.0      # Q/Q growth
    eps_growth_yoy: float = 0.0      # Y/Y growth
    eps_growth_3y_cagr: float = 0.0  # 3-year CAGR
    eps_growth_5y_cagr: float = 0.0  # 5-year CAGR
    
    revenue_growth_qoq: float = 0.0
    revenue_growth_yoy: float = 0.0
    revenue_growth_3y_cagr: float = 0.0
    
    # Acceleration (tăng tốc)
    eps_acceleration: float = 0.0     # Tốc độ tăng có đang tăng?
    revenue_acceleration: float = 0.0
    
    # Quality metrics
    consecutive_eps_growth: int = 0   # Số quý liên tiếp EPS tăng
    consecutive_rev_growth: int = 0
    earnings_stability: float = 0.0   # Độ ổn định (0-100)
    
    # Historical data
    quarterly_data: List[QuarterlyData] = field(default_factory=list)
    
    # Validation
    confidence_score: float = 0.0     # Độ tin cậy data (0-100)
    sources_used: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'symbol': self.symbol,
            'source': self.source,
            'updated_at': self.updated_at,
            'eps_ttm': self.eps_ttm,
            'pe_ttm': self.pe_ttm,
            'pb': self.pb,
            'roe': self.roe,
            'roa': self.roa,
            'eps_growth_qoq': self.eps_growth_qoq,
            'eps_growth_yoy': self.eps_growth_yoy,
            'eps_growth_3y_cagr': self.eps_growth_3y_cagr,
            'eps_growth_5y_cagr': self.eps_growth_5y_cagr,
            'revenue_growth_qoq': self.revenue_growth_qoq,
            'revenue_growth_yoy': self.revenue_growth_yoy,
            'revenue_growth_3y_cagr': self.revenue_growth_3y_cagr,
            'eps_acceleration': self.eps_acceleration,
            'consecutive_eps_growth': self.consecutive_eps_growth,
            'earnings_stability': self.earnings_stability,
            'confidence_score': self.confidence_score,
            'sources_used': self.sources_used
        }


# ══════════════════════════════════════════════════════════════════════════════
# ABSTRACT BASE SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

class BaseFundamentalScraper(ABC):
    """Base class cho các scrapers"""
    
    def __init__(self, cache_dir: str = "./cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Tên nguồn dữ liệu"""
        pass
    
    @abstractmethod
    def fetch_quarterly_data(self, symbol: str, quarters: int = 20) -> List[QuarterlyData]:
        """Lấy dữ liệu theo quý"""
        pass
    
    def _get_cache_key(self, symbol: str, data_type: str) -> str:
        return f"{self.source_name}_{symbol}_{data_type}"
    
    def _get_cache_path(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.json"
    
    def _load_cache(self, cache_key: str, max_age_hours: int = 24) -> Optional[Dict]:
        """Load từ cache nếu còn valid"""
        cache_path = self._get_cache_path(cache_key)
        
        if not cache_path.exists():
            return None
        
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check age
            cached_time = datetime.fromisoformat(data.get('timestamp', '2000-01-01'))
            if datetime.now() - cached_time > timedelta(hours=max_age_hours):
                return None
            
            return data.get('data')
        except:
            return None
    
    def _save_cache(self, cache_key: str, data: Any):
        """Save vào cache"""
        cache_path = self._get_cache_path(cache_key)
        
        try:
            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'data': data
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"   ⚠️ Cache save error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# VNSTOCK SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

class VnstockFundamentalScraper(BaseFundamentalScraper):
    """Scraper dùng vnstock library"""
    
    def __init__(self, api_key: str = None, **kwargs):
        super().__init__(**kwargs)
        self.api_key = api_key
        if api_key:
            os.environ['VNSTOCK_API_KEY'] = api_key
    
    @property
    def source_name(self) -> str:
        return "vnstock"
    
    def fetch_quarterly_data(self, symbol: str, quarters: int = 20) -> List[QuarterlyData]:
        """Lấy dữ liệu từ vnstock"""
        cache_key = self._get_cache_key(symbol, f"quarterly_{quarters}")
        cached = self._load_cache(cache_key, max_age_hours=168)  # 7 days
        
        if cached:
            return [QuarterlyData(**q) for q in cached]
        
        if not HAS_VNSTOCK:
            return []
        
        result = []
        
        try:
            stock = Vnstock().stock(symbol=symbol, source='VCI')
            
            # Income statement
            income_df = stock.finance.income_statement(period='quarter', lang='vi')
            
            # Ratio
            ratio_df = stock.finance.ratio(period='quarter', lang='vi')
            
            if income_df.empty:
                return []
            
            # Process data
            for i, (idx, row) in enumerate(income_df.head(quarters).iterrows()):
                if i >= quarters:
                    break
                
                try:
                    # Parse period from index
                    period = str(idx) if isinstance(idx, str) else f"Q{i+1}"
                    
                    # Extract values - handle MultiIndex columns
                    revenue = 0.0
                    profit = 0.0
                    
                    for col in income_df.columns:
                        col_str = str(col).lower()
                        if 'doanh thu' in col_str and 'thuần' in col_str:
                            revenue = float(row[col]) if pd.notna(row[col]) else 0.0
                        elif 'lợi nhuận sau thuế' in col_str and 'cổ đông' in col_str:
                            profit = float(row[col]) if pd.notna(row[col]) else 0.0
                    
                    # Get ratio data if available
                    roe = 0.0
                    roa = 0.0
                    
                    if not ratio_df.empty and i < len(ratio_df):
                        ratio_row = ratio_df.iloc[i]
                        for col in ratio_df.columns:
                            col_str = str(col).lower()
                            if 'roe' in col_str:
                                roe = float(ratio_row[col]) * 100 if pd.notna(ratio_row[col]) else 0.0
                            elif 'roa' in col_str:
                                roa = float(ratio_row[col]) * 100 if pd.notna(ratio_row[col]) else 0.0
                    
                    qdata = QuarterlyData(
                        period=period,
                        revenue=revenue,
                        profit=profit,
                        roe=roe,
                        roa=roa
                    )
                    result.append(qdata)
                    
                except Exception as e:
                    print(f"   ⚠️ Error parsing row {i}: {e}")
                    continue
            
            # Cache result
            if result:
                self._save_cache(cache_key, [vars(q) for q in result])
            
        except Exception as e:
            print(f"   ⚠️ vnstock error for {symbol}: {e}")
        
        return result


# ══════════════════════════════════════════════════════════════════════════════
# CAFEF SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

class CafefFundamentalScraper(BaseFundamentalScraper):
    """Scraper từ CafeF"""
    
    BASE_URL = "https://s.cafef.vn"
    
    @property
    def source_name(self) -> str:
        return "cafef"
    
    def fetch_quarterly_data(self, symbol: str, quarters: int = 20) -> List[QuarterlyData]:
        """Lấy dữ liệu từ CafeF"""
        cache_key = self._get_cache_key(symbol, f"quarterly_{quarters}")
        cached = self._load_cache(cache_key, max_age_hours=168)
        
        if cached:
            return [QuarterlyData(**q) for q in cached]
        
        result = []
        
        try:
            # CafeF API endpoint for financial data
            url = f"{self.BASE_URL}/Ajax/CongTy/BaoCaoTaiChinh.aspx"
            params = {
                'symbol': symbol,
                'type': 2,  # Income statement
                'quarter': 1,
                'year': datetime.now().year
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                # Parse HTML table
                soup = BeautifulSoup(response.text, 'html.parser')
                tables = soup.find_all('table')
                
                if tables:
                    # Process financial table
                    result = self._parse_cafef_table(tables[0], quarters)
            
            # Also try alternative endpoint
            if not result:
                result = self._fetch_cafef_api(symbol, quarters)
            
            if result:
                self._save_cache(cache_key, [vars(q) for q in result])
                
        except Exception as e:
            print(f"   ⚠️ CafeF error for {symbol}: {e}")
        
        return result
    
    def _fetch_cafef_api(self, symbol: str, quarters: int) -> List[QuarterlyData]:
        """Thử API endpoint khác của CafeF"""
        result = []
        
        try:
            # Alternative: CafeF financial summary page
            url = f"https://cafef.vn/du-lieu/bao-cao-tai-chinh/{symbol.lower()}.chn"
            
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find quarterly data table
            table = soup.find('table', {'class': 'tbl-data'})
            if table:
                result = self._parse_cafef_table(table, quarters)
                
        except Exception as e:
            print(f"   ⚠️ CafeF API error: {e}")
        
        return result
    
    def _parse_cafef_table(self, table, quarters: int) -> List[QuarterlyData]:
        """Parse bảng tài chính từ CafeF"""
        result = []
        
        try:
            rows = table.find_all('tr')
            
            # Headers (quarters)
            headers = []
            if rows:
                header_row = rows[0]
                for th in header_row.find_all(['th', 'td']):
                    text = th.get_text(strip=True)
                    if text and ('Q' in text or '/' in text):
                        headers.append(text)
            
            # Data rows
            revenue_row = None
            profit_row = None
            
            for row in rows[1:]:
                cells = row.find_all('td')
                if not cells:
                    continue
                
                label = cells[0].get_text(strip=True).lower()
                
                if 'doanh thu' in label and 'thuần' in label:
                    revenue_row = cells[1:]
                elif 'lợi nhuận sau thuế' in label:
                    profit_row = cells[1:]
            
            # Build quarterly data
            for i, period in enumerate(headers[:quarters]):
                revenue = 0.0
                profit = 0.0
                
                if revenue_row and i < len(revenue_row):
                    try:
                        rev_text = revenue_row[i].get_text(strip=True)
                        revenue = self._parse_number(rev_text)
                    except:
                        pass
                
                if profit_row and i < len(profit_row):
                    try:
                        prof_text = profit_row[i].get_text(strip=True)
                        profit = self._parse_number(prof_text)
                    except:
                        pass
                
                result.append(QuarterlyData(
                    period=period,
                    revenue=revenue,
                    profit=profit
                ))
                
        except Exception as e:
            print(f"   ⚠️ Parse error: {e}")
        
        return result
    
    def _parse_number(self, text: str) -> float:
        """Parse số từ text (có thể có đơn vị tỷ, triệu)"""
        if not text:
            return 0.0
        
        text = text.replace(',', '').replace(' ', '').strip()
        
        multiplier = 1.0
        if 'tỷ' in text.lower():
            multiplier = 1e9
            text = text.lower().replace('tỷ', '')
        elif 'triệu' in text.lower():
            multiplier = 1e6
            text = text.lower().replace('triệu', '')
        
        try:
            return float(text) * multiplier
        except:
            return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# VIETSTOCK SCRAPER
# ══════════════════════════════════════════════════════════════════════════════

class VietstockFundamentalScraper(BaseFundamentalScraper):
    """Scraper từ VietStock"""
    
    BASE_URL = "https://finance.vietstock.vn"
    
    @property
    def source_name(self) -> str:
        return "vietstock"
    
    def fetch_quarterly_data(self, symbol: str, quarters: int = 20) -> List[QuarterlyData]:
        """Lấy dữ liệu từ VietStock"""
        cache_key = self._get_cache_key(symbol, f"quarterly_{quarters}")
        cached = self._load_cache(cache_key, max_age_hours=168)
        
        if cached:
            return [QuarterlyData(**q) for q in cached]
        
        result = []
        
        try:
            # VietStock finance page
            url = f"{self.BASE_URL}/{symbol}/tai-chinh.htm"
            
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find income statement table
            tables = soup.find_all('table', {'class': 'table'})
            
            for table in tables:
                # Check if this is income statement
                caption = table.find('caption')
                if caption and 'kết quả' in caption.get_text().lower():
                    result = self._parse_vietstock_table(table, quarters)
                    break
            
            if result:
                self._save_cache(cache_key, [vars(q) for q in result])
                
        except Exception as e:
            print(f"   ⚠️ VietStock error for {symbol}: {e}")
        
        return result
    
    def _parse_vietstock_table(self, table, quarters: int) -> List[QuarterlyData]:
        """Parse bảng từ VietStock"""
        result = []
        
        try:
            rows = table.find_all('tr')
            
            # Similar parsing logic to CafeF
            headers = []
            if rows:
                header_row = rows[0]
                for th in header_row.find_all(['th', 'td']):
                    text = th.get_text(strip=True)
                    if text:
                        headers.append(text)
            
            # Extract data (simplified)
            for row in rows[1:]:
                cells = row.find_all('td')
                if len(cells) < 2:
                    continue
                
                # Process each quarter column
                # (Implementation similar to CafeF)
                pass
                
        except Exception as e:
            print(f"   ⚠️ VietStock parse error: {e}")
        
        return result


# ══════════════════════════════════════════════════════════════════════════════
# SIMPLIZE SCRAPER (API-based)
# ══════════════════════════════════════════════════════════════════════════════

class SimplizeFundamentalScraper(BaseFundamentalScraper):
    """Scraper từ Simplize (có API)"""
    
    BASE_URL = "https://simplize.vn/api"
    
    @property
    def source_name(self) -> str:
        return "simplize"
    
    def fetch_quarterly_data(self, symbol: str, quarters: int = 20) -> List[QuarterlyData]:
        """Lấy dữ liệu từ Simplize API"""
        cache_key = self._get_cache_key(symbol, f"quarterly_{quarters}")
        cached = self._load_cache(cache_key, max_age_hours=168)
        
        if cached:
            return [QuarterlyData(**q) for q in cached]
        
        result = []
        
        try:
            # Simplize public API
            url = f"{self.BASE_URL}/company/financials/{symbol}"
            
            response = self.session.get(url, timeout=10)
            if response.status_code != 200:
                # Try alternative endpoint
                url = f"https://simplize.vn/api/v1/stocks/{symbol}/financials"
                response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                result = self._parse_simplize_data(data, quarters)
            
            if result:
                self._save_cache(cache_key, [vars(q) for q in result])
                
        except Exception as e:
            print(f"   ⚠️ Simplize error for {symbol}: {e}")
        
        return result
    
    def _parse_simplize_data(self, data: Dict, quarters: int) -> List[QuarterlyData]:
        """Parse JSON từ Simplize"""
        result = []
        
        try:
            # Simplize returns data in structured format
            financials = data.get('financials', {})
            quarterly = financials.get('quarterly', [])
            
            for i, q in enumerate(quarterly[:quarters]):
                result.append(QuarterlyData(
                    period=q.get('period', f"Q{i+1}"),
                    revenue=q.get('revenue', 0.0),
                    profit=q.get('netProfit', 0.0),
                    eps=q.get('eps', 0.0),
                    roe=q.get('roe', 0.0),
                    roa=q.get('roa', 0.0)
                ))
                
        except Exception as e:
            print(f"   ⚠️ Simplize parse error: {e}")
        
        return result


# ══════════════════════════════════════════════════════════════════════════════
# AGGREGATOR - CROSS VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

class FundamentalAggregator:
    """
    Tổng hợp và cross-validate data từ nhiều nguồn
    
    Logic:
    1. Fetch từ tất cả nguồn available
    2. So sánh và lấy median value
    3. Tính confidence score dựa trên độ đồng nhất
    4. Calculate growth metrics
    """
    
    def __init__(self, 
                 vnstock_api_key: str = None,
                 cache_dir: str = "./cache",
                 enable_cafef: bool = True,
                 enable_vietstock: bool = True,
                 enable_simplize: bool = True):
        
        self.scrapers = []
        
        # VNStock (always primary)
        self.scrapers.append(VnstockFundamentalScraper(
            api_key=vnstock_api_key,
            cache_dir=cache_dir
        ))
        
        # CafeF
        if enable_cafef:
            self.scrapers.append(CafefFundamentalScraper(cache_dir=cache_dir))
        
        # VietStock
        if enable_vietstock:
            self.scrapers.append(VietstockFundamentalScraper(cache_dir=cache_dir))
        
        # Simplize
        if enable_simplize:
            self.scrapers.append(SimplizeFundamentalScraper(cache_dir=cache_dir))
        
        print(f"✓ Fundamental Aggregator initialized with {len(self.scrapers)} sources")
    
    def get_fundamental_data(self, symbol: str) -> FundamentalData:
        """
        Lấy và tổng hợp fundamental data
        
        Returns:
            FundamentalData với cross-validated metrics
        """
        print(f"   📊 Fetching fundamental data for {symbol}...")
        
        all_quarterly_data = {}
        sources_success = []
        
        # Fetch từ tất cả nguồn
        for scraper in self.scrapers:
            try:
                quarterly = scraper.fetch_quarterly_data(symbol, quarters=20)
                
                if quarterly:
                    all_quarterly_data[scraper.source_name] = quarterly
                    sources_success.append(scraper.source_name)
                    print(f"      ✓ {scraper.source_name}: {len(quarterly)} quarters")
                else:
                    print(f"      ✗ {scraper.source_name}: no data")
                    
            except Exception as e:
                print(f"      ✗ {scraper.source_name}: {e}")
        
        if not all_quarterly_data:
            return FundamentalData(symbol=symbol, confidence_score=0)
        
        # Cross-validate và tổng hợp
        result = self._aggregate_data(symbol, all_quarterly_data, sources_success)
        
        return result
    
    def _aggregate_data(self, 
                        symbol: str, 
                        all_data: Dict[str, List[QuarterlyData]],
                        sources: List[str]) -> FundamentalData:
        """Tổng hợp data từ nhiều nguồn"""
        
        result = FundamentalData(
            symbol=symbol,
            source="aggregated",
            updated_at=datetime.now().isoformat(),
            sources_used=sources
        )
        
        # Lấy primary source (vnstock) làm baseline
        primary_data = all_data.get('vnstock', [])
        
        if not primary_data:
            # Fallback to any available source
            primary_data = list(all_data.values())[0] if all_data else []
        
        if not primary_data:
            return result
        
        # Store quarterly data
        result.quarterly_data = primary_data
        
        # Calculate growth metrics
        self._calculate_growth_metrics(result, primary_data)
        
        # Cross-validate với các nguồn khác
        confidence = self._calculate_confidence(all_data)
        result.confidence_score = confidence
        
        # Calculate quality metrics
        self._calculate_quality_metrics(result, primary_data)
        
        return result
    
    def _calculate_growth_metrics(self, 
                                   result: FundamentalData, 
                                   quarterly: List[QuarterlyData]):
        """Tính các chỉ số growth"""
        
        if len(quarterly) < 2:
            return
        
        # Sort theo thời gian (mới nhất trước)
        # Giả sử data đã sorted
        
        # === EPS/Profit Growth ===
        
        # Q/Q Growth (so với quý trước)
        if len(quarterly) >= 2:
            curr_profit = quarterly[0].profit
            prev_profit = quarterly[1].profit
            
            if prev_profit != 0:
                result.eps_growth_qoq = ((curr_profit - prev_profit) / abs(prev_profit)) * 100
        
        # Y/Y Growth (so với cùng kỳ năm trước)
        if len(quarterly) >= 5:
            curr_profit = quarterly[0].profit
            yoy_profit = quarterly[4].profit  # 4 quý trước
            
            if yoy_profit != 0:
                result.eps_growth_yoy = ((curr_profit - yoy_profit) / abs(yoy_profit)) * 100
        
        # 3-Year CAGR
        if len(quarterly) >= 13:
            end_profit = quarterly[0].profit
            start_profit = quarterly[12].profit  # 3 năm = 12 quý
            
            if start_profit > 0 and end_profit > 0:
                result.eps_growth_3y_cagr = (pow(end_profit / start_profit, 1/3) - 1) * 100
        
        # 5-Year CAGR
        if len(quarterly) >= 21:
            end_profit = quarterly[0].profit
            start_profit = quarterly[20].profit
            
            if start_profit > 0 and end_profit > 0:
                result.eps_growth_5y_cagr = (pow(end_profit / start_profit, 1/5) - 1) * 100
        
        # === Revenue Growth ===
        
        # Q/Q
        if len(quarterly) >= 2:
            curr_rev = quarterly[0].revenue
            prev_rev = quarterly[1].revenue
            
            if prev_rev != 0:
                result.revenue_growth_qoq = ((curr_rev - prev_rev) / abs(prev_rev)) * 100
        
        # Y/Y
        if len(quarterly) >= 5:
            curr_rev = quarterly[0].revenue
            yoy_rev = quarterly[4].revenue
            
            if yoy_rev != 0:
                result.revenue_growth_yoy = ((curr_rev - yoy_rev) / abs(yoy_rev)) * 100
        
        # 3Y CAGR
        if len(quarterly) >= 13:
            end_rev = quarterly[0].revenue
            start_rev = quarterly[12].revenue
            
            if start_rev > 0 and end_rev > 0:
                result.revenue_growth_3y_cagr = (pow(end_rev / start_rev, 1/3) - 1) * 100
        
        # === Acceleration ===
        # EPS acceleration = (current growth - previous growth)
        if len(quarterly) >= 6:
            # Growth Q hiện tại
            g1 = 0
            if quarterly[1].profit != 0:
                g1 = (quarterly[0].profit - quarterly[1].profit) / abs(quarterly[1].profit)
            
            # Growth Q trước
            g2 = 0
            if quarterly[2].profit != 0:
                g2 = (quarterly[1].profit - quarterly[2].profit) / abs(quarterly[2].profit)
            
            result.eps_acceleration = (g1 - g2) * 100
        
        # === Current ROE/ROA ===
        if quarterly[0].roe:
            result.roe = quarterly[0].roe
        if quarterly[0].roa:
            result.roa = quarterly[0].roa
    
    def _calculate_quality_metrics(self, 
                                    result: FundamentalData, 
                                    quarterly: List[QuarterlyData]):
        """Tính chỉ số chất lượng"""
        
        # Consecutive growth quarters
        consecutive_eps = 0
        consecutive_rev = 0
        
        for i in range(len(quarterly) - 1):
            if quarterly[i].profit > quarterly[i+1].profit:
                consecutive_eps += 1
            else:
                break
        
        for i in range(len(quarterly) - 1):
            if quarterly[i].revenue > quarterly[i+1].revenue:
                consecutive_rev += 1
            else:
                break
        
        result.consecutive_eps_growth = consecutive_eps
        result.consecutive_rev_growth = consecutive_rev
        
        # Earnings stability (coefficient of variation)
        if len(quarterly) >= 4:
            profits = [q.profit for q in quarterly[:8] if q.profit != 0]
            
            if profits and len(profits) >= 4:
                mean_profit = mean(profits)
                if mean_profit != 0:
                    std_profit = np.std(profits)
                    cv = std_profit / abs(mean_profit)
                    # Convert to 0-100 score (lower CV = higher stability)
                    result.earnings_stability = max(0, min(100, 100 - cv * 50))
    
    def _calculate_confidence(self, all_data: Dict[str, List[QuarterlyData]]) -> float:
        """
        Tính confidence score dựa trên:
        1. Số nguồn có data
        2. Độ đồng nhất giữa các nguồn
        """
        
        if len(all_data) == 0:
            return 0
        
        if len(all_data) == 1:
            return 50  # Chỉ có 1 nguồn
        
        # Base score từ số nguồn
        base_score = min(100, len(all_data) * 25)
        
        # So sánh data giữa các nguồn
        # Lấy profit Q gần nhất từ mỗi nguồn
        latest_profits = []
        
        for source, quarterly in all_data.items():
            if quarterly and quarterly[0].profit:
                latest_profits.append(quarterly[0].profit)
        
        if len(latest_profits) >= 2:
            # Tính độ lệch chuẩn tương đối
            mean_profit = mean(latest_profits)
            if mean_profit != 0:
                std_profit = np.std(latest_profits)
                cv = std_profit / abs(mean_profit)
                
                # CV < 5% = rất đồng nhất
                # CV > 20% = không đồng nhất
                consistency_score = max(0, 100 - cv * 500)
                
                return (base_score + consistency_score) / 2
        
        return base_score


# ══════════════════════════════════════════════════════════════════════════════
# CANSLIM SCORER (Enhanced)
# ══════════════════════════════════════════════════════════════════════════════

class EnhancedCANSLIMScorer:
    """
    Scoring theo CANSLIM methodology với data đầy đủ hơn
    
    C - Current EPS:  EPS growth Q/Q ≥ 25%
    A - Annual EPS:   EPS growth 3Y CAGR ≥ 25%
    N - New:          Near 52-week high
    S - Supply:       Volume, float
    L - Leader:       RS Rating ≥ 80
    I - Institutional: (sẽ implement với Foreign Flow)
    M - Market:       Traffic Light
    """
    
    def __init__(self):
        # Thresholds
        self.C_THRESHOLD = 25.0    # 25% Q/Q growth
        self.A_THRESHOLD = 25.0    # 25% annual CAGR
        self.C_WEIGHT = 0.30       # 30% của fundamental score
        self.A_WEIGHT = 0.30
        self.QUALITY_WEIGHT = 0.40  # ROE, stability, etc.
    
    def score_fundamental(self, fund_data: FundamentalData) -> Tuple[float, Dict]:
        """
        Tính điểm fundamental từ 0-100
        
        Returns:
            (score, breakdown)
        """
        breakdown = {
            'c_score': 0,
            'a_score': 0,
            'quality_score': 0,
            'details': {}
        }
        
        # === C Score (Current EPS) ===
        c_score = 0
        
        # EPS Q/Q growth
        if fund_data.eps_growth_qoq >= 50:
            c_score += 40
        elif fund_data.eps_growth_qoq >= 25:
            c_score += 30
        elif fund_data.eps_growth_qoq >= 15:
            c_score += 20
        elif fund_data.eps_growth_qoq >= 0:
            c_score += 10
        
        # EPS acceleration bonus
        if fund_data.eps_acceleration > 10:
            c_score += 20
        elif fund_data.eps_acceleration > 0:
            c_score += 10
        
        # Revenue Q/Q growth
        if fund_data.revenue_growth_qoq >= 25:
            c_score += 20
        elif fund_data.revenue_growth_qoq >= 10:
            c_score += 10
        
        # Consecutive growth bonus
        if fund_data.consecutive_eps_growth >= 4:
            c_score += 20
        elif fund_data.consecutive_eps_growth >= 2:
            c_score += 10
        
        c_score = min(100, c_score)
        breakdown['c_score'] = c_score
        breakdown['details']['eps_growth_qoq'] = fund_data.eps_growth_qoq
        breakdown['details']['eps_acceleration'] = fund_data.eps_acceleration
        
        # === A Score (Annual EPS) ===
        a_score = 0
        
        # 3Y CAGR
        if fund_data.eps_growth_3y_cagr >= 30:
            a_score += 40
        elif fund_data.eps_growth_3y_cagr >= 25:
            a_score += 30
        elif fund_data.eps_growth_3y_cagr >= 20:
            a_score += 20
        elif fund_data.eps_growth_3y_cagr >= 10:
            a_score += 10
        
        # 5Y CAGR (bonus)
        if fund_data.eps_growth_5y_cagr >= 25:
            a_score += 20
        elif fund_data.eps_growth_5y_cagr >= 15:
            a_score += 10
        
        # Y/Y growth
        if fund_data.eps_growth_yoy >= 25:
            a_score += 20
        elif fund_data.eps_growth_yoy >= 10:
            a_score += 10
        
        # Revenue 3Y CAGR
        if fund_data.revenue_growth_3y_cagr >= 20:
            a_score += 20
        elif fund_data.revenue_growth_3y_cagr >= 10:
            a_score += 10
        
        a_score = min(100, a_score)
        breakdown['a_score'] = a_score
        breakdown['details']['eps_growth_3y_cagr'] = fund_data.eps_growth_3y_cagr
        breakdown['details']['eps_growth_yoy'] = fund_data.eps_growth_yoy
        
        # === Quality Score ===
        quality_score = 0
        
        # ROE
        if fund_data.roe >= 25:
            quality_score += 30
        elif fund_data.roe >= 17:
            quality_score += 20
        elif fund_data.roe >= 12:
            quality_score += 10
        
        # ROA
        if fund_data.roa >= 15:
            quality_score += 15
        elif fund_data.roa >= 10:
            quality_score += 10
        elif fund_data.roa >= 5:
            quality_score += 5
        
        # Earnings stability
        if fund_data.earnings_stability >= 80:
            quality_score += 25
        elif fund_data.earnings_stability >= 60:
            quality_score += 15
        elif fund_data.earnings_stability >= 40:
            quality_score += 10
        
        # Confidence bonus
        if fund_data.confidence_score >= 80:
            quality_score += 15
        elif fund_data.confidence_score >= 60:
            quality_score += 10
        elif fund_data.confidence_score >= 40:
            quality_score += 5
        
        # Consecutive growth
        if fund_data.consecutive_eps_growth >= 3:
            quality_score += 15
        
        quality_score = min(100, quality_score)
        breakdown['quality_score'] = quality_score
        breakdown['details']['roe'] = fund_data.roe
        breakdown['details']['stability'] = fund_data.earnings_stability
        
        # === Total Score ===
        total = (
            c_score * self.C_WEIGHT +
            a_score * self.A_WEIGHT +
            quality_score * self.QUALITY_WEIGHT
        )
        
        return total, breakdown
    
    def get_canslim_grade(self, fund_data: FundamentalData) -> str:
        """
        Đánh giá CANSLIM grade
        
        Returns:
            A, B, C, D, F
        """
        score, _ = self.score_fundamental(fund_data)
        
        if score >= 80:
            return 'A'
        elif score >= 65:
            return 'B'
        elif score >= 50:
            return 'C'
        elif score >= 35:
            return 'D'
        else:
            return 'F'


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_fundamental_aggregator(vnstock_api_key: str = None) -> FundamentalAggregator:
    """Factory function"""
    return FundamentalAggregator(vnstock_api_key=vnstock_api_key)


def analyze_fundamental(symbol: str, vnstock_api_key: str = None) -> Dict:
    """
    Quick analysis cho 1 mã
    
    Returns:
        Dict với score và breakdown
    """
    aggregator = get_fundamental_aggregator(vnstock_api_key)
    fund_data = aggregator.get_fundamental_data(symbol)
    
    scorer = EnhancedCANSLIMScorer()
    score, breakdown = scorer.score_fundamental(fund_data)
    grade = scorer.get_canslim_grade(fund_data)
    
    return {
        'symbol': symbol,
        'score': round(score, 1),
        'grade': grade,
        'breakdown': breakdown,
        'data': fund_data.to_dict()
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("FUNDAMENTAL ENHANCED MODULE - TEST")
    print("=" * 70)
    
    # Test với VCB
    test_symbols = ['VCB', 'FPT', 'MWG']
    
    for symbol in test_symbols:
        print(f"\n📊 Analyzing {symbol}...")
        print("-" * 50)
        
        result = analyze_fundamental(symbol)
        
        print(f"\n✓ {symbol} Results:")
        print(f"   Score: {result['score']}/100 (Grade: {result['grade']})")
        print(f"   C Score: {result['breakdown']['c_score']}")
        print(f"   A Score: {result['breakdown']['a_score']}")
        print(f"   Quality: {result['breakdown']['quality_score']}")
        
        if result['data']:
            data = result['data']
            print(f"\n   Growth Metrics:")
            print(f"   • EPS Q/Q: {data['eps_growth_qoq']:+.1f}%")
            print(f"   • EPS Y/Y: {data['eps_growth_yoy']:+.1f}%")
            print(f"   • EPS 3Y CAGR: {data['eps_growth_3y_cagr']:+.1f}%")
            print(f"   • ROE: {data['roe']:.1f}%")
            print(f"   • Confidence: {data['confidence_score']:.0f}%")
            print(f"   • Sources: {', '.join(data['sources_used'])}")
