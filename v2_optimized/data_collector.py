#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    MULTI-SOURCE DATA COLLECTOR                               ║
║              VCI → TCBS → SSI Fallback + Volume Profile                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Tự động chuyển nguồn dữ liệu khi gặp lỗi:                                  ║
║  - VCI: Nguồn chính, đầy đủ nhất                                            ║
║  - TCBS: Backup, ổn định                                                     ║
║  - SSI: Fallback cuối                                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import time
import json
from pathlib import Path
import warnings
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# Import config
try:
    from config import get_config, APIKeys
except ImportError:
    get_config = None
    APIKeys = None

# Import Volume Profile
try:
    from volume_profile import VolumeProfileCalculator, VolumeProfileResult
except ImportError:
    VolumeProfileCalculator = None
    VolumeProfileResult = None

# Import Database
try:
    from database import get_db, PriceStore, FundamentalStore, ForeignFlowStore
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False


# ══════════════════════════════════════════════════════════════════════════════
# DATA SOURCE MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class DataSourceManager:
    """
    Quản lý nhiều nguồn dữ liệu với auto-fallback
    
    Usage:
        manager = DataSourceManager()
        df = manager.get_price_history("VCB", days=60)
    """
    
    SOURCES = ["VCI", "TCBS", "SSI"]
    
    def __init__(self, 
                 primary_source: str = "VCI",
                 api_key: str = None,
                 auto_fallback: bool = True):
        """
        Args:
            primary_source: Nguồn dữ liệu chính
            api_key: API key cho vnstock premium
            auto_fallback: Tự động chuyển nguồn khi lỗi
        """
        self.primary_source = primary_source
        self.current_source = primary_source
        self.auto_fallback = auto_fallback
        self.failed_sources: Dict[str, datetime] = {}
        
        # Load từ config nếu có
        if get_config and not api_key:
            api_key = APIKeys.VNSTOCK if APIKeys else None
        
        self._init_vnstock(api_key)

        # SQLite price cache
        self._price_store = None
        if _DB_AVAILABLE:
            try:
                self._price_store = PriceStore()
            except Exception as e:
                print(f"   ⚠️ Price store init failed: {e}")

        # Statistics
        self.stats = {
            'requests': 0,
            'success': 0,
            'failures': 0,
            'fallbacks': 0
        }
    
    def _init_vnstock(self, api_key: str = None):
        """Khởi tạo vnstock"""
        try:
            # Set API key BEFORE importing vnstock
            if api_key:
                os.environ['VNSTOCK_API_KEY'] = api_key
            
            from vnstock import Vnstock, Listing
            
            self.Vnstock = Vnstock
            self.Listing = Listing
            self._vnstock_available = True
            
            print(f"✓ Vnstock initialized | Primary: {self.primary_source}")
            
        except ImportError:
            self._vnstock_available = False
            print("✗ vnstock not available: pip install -U vnstock")
    
    def _get_stock(self, symbol: str, source: str = None):
        """Tạo stock object với source cụ thể"""
        if not self._vnstock_available:
            return None
        
        source = source or self.current_source
        return self.Vnstock().stock(symbol=symbol, source=source)
    
    def _should_skip_source(self, source: str) -> bool:
        """Kiểm tra xem source có đang trong thời gian cooldown không"""
        if source not in self.failed_sources:
            return False
        
        fail_time = self.failed_sources[source]
        cooldown = timedelta(minutes=5)  # 5 phút cooldown
        
        return datetime.now() - fail_time < cooldown
    
    def _mark_source_failed(self, source: str):
        """Đánh dấu source bị lỗi"""
        self.failed_sources[source] = datetime.now()
        self.stats['failures'] += 1
    
    def _get_next_source(self, current: str) -> Optional[str]:
        """Lấy source tiếp theo trong danh sách"""
        try:
            idx = self.SOURCES.index(current)
            for next_source in self.SOURCES[idx + 1:]:
                if not self._should_skip_source(next_source):
                    return next_source
        except ValueError:
            pass
        
        # Quay lại từ đầu nếu cần
        for source in self.SOURCES:
            if source != current and not self._should_skip_source(source):
                return source
        
        return None
    
    # ─────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────
    
    def get_price_history(self,
                          symbol: str,
                          days: int = 120,
                          source: str = None) -> pd.DataFrame:
        """
        Lấy lịch sử giá với auto-fallback + SQLite cache.

        Flow:
        1. Check SQLite cache for existing data
        2. Only fetch missing dates from API
        3. Save new data to SQLite
        4. Return combined result
        """
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Try SQLite cache first
        if _DB_AVAILABLE and self._price_store:
            cached_df = self._price_store.get_prices(symbol, start=start_date, end=end_date)
            latest = self._price_store.get_latest_date(symbol)

            # If we have enough cached data and it's recent (within 1 day)
            if not cached_df.empty and latest:
                days_old = (datetime.now() - datetime.strptime(latest, '%Y-%m-%d')).days
                if days_old <= 1 and len(cached_df) >= days * 0.6:
                    self.stats['requests'] += 1
                    self.stats['success'] += 1
                    return cached_df

                # Incremental: only fetch from latest cached date
                if len(cached_df) > 20:
                    start_date = latest

        # Fetch from API
        df = self._fetch_price_from_api(symbol, start_date, end_date, source)

        # Save to SQLite cache
        if not df.empty and _DB_AVAILABLE and self._price_store:
            try:
                self._price_store.save_prices(symbol, df)
                # If incremental fetch, combine with cached data
                if not cached_df.empty and start_date != (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d'):
                    full_start = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
                    df = self._price_store.get_prices(symbol, start=full_start, end=end_date)
            except Exception as e:
                print(f"   ⚠️ DB cache save error: {e}")

        return df

    def _fetch_price_from_api(
        self, symbol: str, start_date: str, end_date: str, source: str = None
    ) -> pd.DataFrame:
        """Fetch price data from API with fallback."""
        sources_to_try = [source] if source else [self.current_source]

        if self.auto_fallback and not source:
            for s in self.SOURCES:
                if s not in sources_to_try and not self._should_skip_source(s):
                    sources_to_try.append(s)

        last_error = None

        for src in sources_to_try:
            try:
                self.stats['requests'] += 1

                stock = self._get_stock(symbol, src)
                if stock is None:
                    continue

                df = stock.quote.history(start=start_date, end=end_date)

                if not df.empty:
                    self.stats['success'] += 1

                    if src != self.current_source:
                        self.stats['fallbacks'] += 1
                        print(f"   ⚠️ Fallback: {self.current_source} → {src}")
                        self.current_source = src

                    return df

            except Exception as e:
                last_error = e
                self._mark_source_failed(src)

                if self.auto_fallback:
                    next_src = self._get_next_source(src)
                    if next_src:
                        continue

                break

        print(f"   ✗ Không lấy được dữ liệu {symbol}: {last_error}")
        return pd.DataFrame()
    
    def get_intraday_history(self,
                             symbol: str,
                             days: int = 5) -> pd.DataFrame:
        """Lấy dữ liệu intraday"""
        try:
            stock = self._get_stock(symbol)
            if stock is None:
                return pd.DataFrame()
            
            # Một số nguồn hỗ trợ intraday
            df = stock.quote.intraday()
            return df
            
        except Exception as e:
            print(f"   ⚠️ Intraday không khả dụng cho {symbol}")
            return pd.DataFrame()
    
    def get_listing(self) -> 'Listing':
        """Lấy Listing object"""
        if not self._vnstock_available:
            return None
        return self.Listing()
    
    def get_all_symbols(self) -> pd.DataFrame:
        """Lấy danh sách tất cả mã"""
        try:
            listing = self.get_listing()
            if listing:
                return listing.all_symbols()
        except Exception as e:
            print(f"   ✗ Lỗi lấy symbols: {e}")
        
        return pd.DataFrame()
    
    def print_stats(self):
        """In thống kê"""
        print(f"\n📊 Data Source Stats:")
        print(f"   Current: {self.current_source}")
        print(f"   Requests: {self.stats['requests']}")
        print(f"   Success: {self.stats['success']}")
        print(f"   Failures: {self.stats['failures']}")
        print(f"   Fallbacks: {self.stats['fallbacks']}")


# ══════════════════════════════════════════════════════════════════════════════
# ENHANCED DATA COLLECTOR
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EnhancedStockData:
    """Dữ liệu cổ phiếu đầy đủ bao gồm Volume Profile"""
    symbol: str
    name: str = ""
    
    # Price
    price: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    
    # Changes
    change_1d: float = 0.0
    change_5d: float = 0.0
    change_1m: float = 0.0
    change_3m: float = 0.0
    
    # Moving Averages
    ma20: float = 0.0
    ma50: float = 0.0
    ma200: float = 0.0
    above_ma20: bool = False
    above_ma50: bool = False
    
    # Technical Indicators
    rsi_14: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    adx: float = 25.0
    
    # Volume
    volume: float = 0.0
    volume_ma20: float = 0.0
    volume_ratio: float = 1.0
    avg_value_20d: float = 0.0  # Tỷ VND
    
    # Foreign Trade (Current Session)
    foreign_buy_value: float = 0.0  # VND
    foreign_sell_value: float = 0.0 # VND
    foreign_net_value: float = 0.0  # VND
    
    # Volume Profile
    poc: float = 0.0            # Point of Control
    vah: float = 0.0            # Value Area High
    val: float = 0.0            # Value Area Low
    price_vs_poc: str = ""      # Above/Below/At
    price_vs_va: str = ""       # Above/In/Below Value Area
    vp_support: List[float] = field(default_factory=list)
    vp_resistance: List[float] = field(default_factory=list)
    vp_signals: List[str] = field(default_factory=list)
    
    # Raw data
    df: pd.DataFrame = field(default_factory=pd.DataFrame)


class EnhancedDataCollector:
    """
    Data Collector nâng cao với:
    - Multi-source fallback
    - Volume Profile integration
    - Rate limiting
    - Caching (optional)
    """
    
    def __init__(self, 
                 api_key: str = None,
                 primary_source: str = "VCI",
                 api_delay: float = 0.3,
                 enable_volume_profile: bool = True):
        """
        Args:
            api_key: vnstock API key (None = lấy từ config)
            primary_source: Nguồn dữ liệu chính
            api_delay: Delay giữa các request
            enable_volume_profile: Tính Volume Profile
        """
        # Load từ config
        if get_config and not api_key:
            config = get_config()
            api_key = config.get_vnstock_key()
            api_delay = config.rate_limit.API_DELAY
        
        self.data_manager = DataSourceManager(
            primary_source=primary_source,
            api_key=api_key,
            auto_fallback=True
        )
        
        self.api_delay = api_delay
        self.enable_volume_profile = enable_volume_profile
        self.request_count = 0
        
        # Volume Profile calculator
        if enable_volume_profile and VolumeProfileCalculator:
            self.vp_calculator = VolumeProfileCalculator(
                num_bins=50,
                value_area_pct=0.70
            )
        else:
            self.vp_calculator = None
            
        # Caching (JSON legacy + SQLite)
        self.cache_dir = Path("data_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "fundamental_cache.json"
        self.cache_data = self._load_cache()

        # SQLite stores
        self._fundamental_store = None
        self._foreign_flow_store = None
        if _DB_AVAILABLE:
            try:
                self._fundamental_store = FundamentalStore()
                self._foreign_flow_store = ForeignFlowStore()
            except Exception as e:
                print(f"   ⚠️ DB stores init failed: {e}")
    
    def _load_cache(self) -> Dict:
        """Load cache from file"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"   ⚠️ Error loading cache: {e}")
        return {}

    def _save_cache(self):
        """Save cache to file"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"   ⚠️ Error saving cache: {e}")

    def _delay(self):
        """Rate limiting"""
        self.request_count += 1
        time.sleep(self.api_delay)
        
        # Nghỉ dài hơn sau mỗi 20 requests
        if self.request_count % 20 == 0:
            print(f"   💤 Đã xử lý {self.request_count} requests...")
            time.sleep(2)
    
    def get_stock_data(self, 
                       symbol: str, 
                       lookback_days: int = 120,
                       include_vp: bool = True) -> EnhancedStockData:
        """
        Lấy dữ liệu đầy đủ của một cổ phiếu
        
        Args:
            symbol: Mã cổ phiếu
            lookback_days: Số ngày lịch sử
            include_vp: Tính Volume Profile
            
        Returns:
            EnhancedStockData với đầy đủ metrics
        """
        self._delay()
        
        result = EnhancedStockData(symbol=symbol)
        
        # 1. Lấy dữ liệu giá
        df = self.data_manager.get_price_history(symbol, days=lookback_days)
        
        if df.empty or len(df) < 20:
            return result
        
        result.df = df
        
        # 2. Tính các metrics cơ bản
        close = df['close'].values
        volume = df['volume'].values
        high = df['high'].values
        low = df['low'].values
        
        result.price = close[-1]
        result.open = df['open'].iloc[-1]
        result.high = high[-1]
        result.low = low[-1]
        result.volume = volume[-1]
        
        # Changes
        if len(close) >= 2:
            result.change_1d = ((close[-1] / close[-2]) - 1) * 100
        if len(close) >= 5:
            result.change_5d = ((close[-1] / close[-5]) - 1) * 100
        if len(close) >= 22:
            result.change_1m = ((close[-1] / close[-22]) - 1) * 100
        if len(close) >= 66:
            result.change_3m = ((close[-1] / close[-66]) - 1) * 100
        
        # Moving Averages
        result.ma20 = np.mean(close[-20:])
        result.ma50 = np.mean(close[-50:]) if len(close) >= 50 else result.ma20
        result.ma200 = np.mean(close[-200:]) if len(close) >= 200 else result.ma50
        result.above_ma20 = close[-1] > result.ma20
        result.above_ma50 = close[-1] > result.ma50
        
        # RSI
        result.rsi_14 = self._calc_rsi(close)
        
        # MACD
        macd_data = self._calc_macd(close)
        result.macd = macd_data['macd']
        result.macd_signal = macd_data['signal']
        result.macd_hist = macd_data['histogram']
        
        # ADX
        result.adx = self._calc_adx(high, low, close)
        
        # Volume metrics
        result.volume_ma20 = np.mean(volume[-20:])
        result.volume_ratio = volume[-1] / result.volume_ma20 if result.volume_ma20 > 0 else 1
        result.avg_value_20d = np.mean(close[-20:] * volume[-20:]) / 1e9  # Tỷ VND
        
        # 3. Volume Profile
        if include_vp and self.vp_calculator and self.enable_volume_profile:
            vp_result = self.vp_calculator.calculate(df, symbol=symbol, lookback_days=20)
            
            result.poc = vp_result.poc
            result.vah = vp_result.vah
            result.val = vp_result.val
            result.price_vs_poc = vp_result.price_vs_poc
            result.price_vs_va = vp_result.price_vs_va
            result.vp_support = vp_result.vp_support
            result.vp_resistance = vp_result.vp_resistance
            result.vp_signals = vp_result.signals
        
        # 4. Lấy dữ liệu khối ngoại trong phiên (Foreign Trade)
        self._fetch_foreign_data_from_price_board(result)
        
        return result
    
    def _calc_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        """
        Tính RSI theo công thức Wilder (chuẩn)
        
        Sử dụng Wilder's Smoothed Moving Average (SMMA):
        - Bước 1: Tính SMA cho period đầu tiên
        - Bước 2: Sử dụng SMMA: Avg = (Prev_Avg * (period-1) + Current) / period
        """
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Wilder's SMMA implementation
        # Bước 1: SMA cho period đầu tiên
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        
        # Bước 2: Áp dụng SMMA cho các giá trị tiếp theo
        for i in range(period, len(gains)):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _fetch_foreign_data_from_price_board(self, result: EnhancedStockData):
        """Lấy dữ liệu khối ngoại từ price_board API (thời gian thực/trong phiên)"""
        try:
            stock = self.data_manager._get_stock(result.symbol)
            if stock:
                # price_board trả về DataFrame với MultiIndex. Cần truyền danh sách mã.
                df_pb = stock.trading.price_board(symbols_list=[result.symbol])
                if df_pb is not None and not df_pb.empty:
                    # Lấy dòng đầu tiên (thường chỉ có 1 dòng cho 1 mã)
                    row = df_pb.iloc[0]
                    
                    # Columns in vnstock can be complex, usually ('match', 'foreign_buy_value')
                    f_buy = row.get(('match', 'foreign_buy_value'), 0)
                    f_sell = row.get(('match', 'foreign_sell_value'), 0)
                    
                    if pd.notna(f_buy): result.foreign_buy_value = float(f_buy)
                    if pd.notna(f_sell): result.foreign_sell_value = float(f_sell)
                    result.foreign_net_value = result.foreign_buy_value - result.foreign_sell_value
        except Exception as e:
            # Silent fail for optional data
            pass
    
    def _calc_macd(self, prices: np.ndarray) -> Dict:
        """Tính MACD"""
        if len(prices) < 35:
            return {'macd': 0, 'signal': 0, 'histogram': 0}
        
        def ema(data, period):
            alpha = 2 / (period + 1)
            result = [data[0]]
            for price in data[1:]:
                result.append(alpha * price + (1 - alpha) * result[-1])
            return np.array(result)
        
        ema12 = ema(prices, 12)
        ema26 = ema(prices, 26)
        macd_line = ema12 - ema26
        signal_line = ema(macd_line, 9)
        
        return {
            'macd': macd_line[-1],
            'signal': signal_line[-1],
            'histogram': macd_line[-1] - signal_line[-1]
        }
    
    def _calc_adx(self, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> float:
        """Tính ADX đơn giản"""
        if len(close) < 28:
            return 25.0
        
        period = 14
        tr = np.maximum(high[1:] - low[1:],
                       np.maximum(abs(high[1:] - close[:-1]),
                                 abs(low[1:] - close[:-1])))
        
        plus_dm = np.where((high[1:] - high[:-1]) > (low[:-1] - low[1:]),
                          np.maximum(high[1:] - high[:-1], 0), 0)
        minus_dm = np.where((low[:-1] - low[1:]) > (high[1:] - high[:-1]),
                           np.maximum(low[:-1] - low[1:], 0), 0)
        
        atr = np.mean(tr[-period:])
        plus_di = 100 * np.mean(plus_dm[-period:]) / atr if atr > 0 else 25
        minus_di = 100 * np.mean(minus_dm[-period:]) / atr if atr > 0 else 25
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di) if (plus_di + minus_di) > 0 else 0
        
        return dx
    
    def get_index_data(self, symbol: str = "VNINDEX", days: int = 120) -> EnhancedStockData:
        """Lấy dữ liệu index"""
        return self.get_stock_data(symbol, lookback_days=days, include_vp=True)
    
    def _retry_request(self, func, *args, **kwargs):
        """Helper to retry requests on failure"""
        max_retries = 3
        base_delay = 5
        
        for i in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                error_msg = str(e).lower()
                if "429" in error_msg or "502" in error_msg or "rate limit" in error_msg:
                    wait_time = base_delay * (2 ** i)
                    print(f"   ⚠️ Rate limit/Error. Waiting {wait_time}s... ({i+1}/{max_retries})")
                    time.sleep(wait_time)
                else:
                    raise e
        return None

    def get_financial_ratios(self, symbol: str) -> Dict[str, float]:
        """
        Lấy các chỉ số tài chính cơ bản (PE, PB, ROE, ROA).
        Uses SQLite cache (7-day TTL), falls back to JSON cache, then API.
        """
        result = {
            'pe': 0.0, 'pb': 0.0, 'roe': 0.0, 'roa': 0.0,
            'book_value': 0.0
        }

        # Check SQLite cache first
        if self._fundamental_store and self._fundamental_store.is_fresh(symbol, max_days=7):
            latest = self._fundamental_store.get_latest_quarter(symbol)
            if latest and (latest.get('pe') or latest.get('roe')):
                result['pe'] = latest.get('pe', 0) or 0
                result['pb'] = latest.get('pb', 0) or 0
                result['roe'] = latest.get('roe', 0) or 0
                result['roa'] = latest.get('roa', 0) or 0
                return result

        # Check JSON cache
        cache_key = f"{symbol}_ratios"
        if cache_key in self.cache_data:
            cached = self.cache_data[cache_key]
            try:
                cached_time = datetime.strptime(cached['timestamp'], "%Y-%m-%d")
                if (datetime.now() - cached_time).days < 7:
                    return cached['data']
            except (ValueError, KeyError):
                pass

        try:
            stock = self.data_manager._get_stock(symbol)
            if stock:
                def fetch_ratio():
                    return stock.finance.ratio(period='quarter', lang='vi')

                df = self._retry_request(fetch_ratio)

                if df is not None and not df.empty:
                    latest = df.iloc[0]

                    try:
                        result['pe'] = float(latest.get(('Chỉ tiêu định giá', 'P/E'), 0))
                        result['pb'] = float(latest.get(('Chỉ tiêu định giá', 'P/B'), 0))
                        result['roe'] = float(latest.get(('Chỉ tiêu khả năng sinh lợi', 'ROE (%)'), 0)) * 100
                        result['roa'] = float(latest.get(('Chỉ tiêu khả năng sinh lợi', 'ROA (%)'), 0)) * 100
                        result['book_value'] = float(latest.get(('Chỉ tiêu định giá', 'BVPS (VND)'), 0))

                        # Save to JSON cache
                        self.cache_data[cache_key] = {
                            'data': result,
                            'timestamp': datetime.now().strftime("%Y-%m-%d")
                        }
                        self._save_cache()

                        # Save to SQLite cache
                        if self._fundamental_store:
                            self._save_ratios_to_db(symbol, df)

                    except Exception as e:
                        print(f"   ⚠️ Ratio parsing error {symbol}: {e}")

        except Exception as e:
            print(f"   ⚠️ Lỗi lấy ratio {symbol}: {e}")

        return result

    def _save_ratios_to_db(self, symbol: str, df: pd.DataFrame):
        """Save ratio DataFrame to SQLite fundamental_store."""
        try:
            records = []
            for idx, row in df.head(8).iterrows():
                period_str = str(idx) if isinstance(idx, str) else f"Q{idx}"
                pe = float(row.get(('Chỉ tiêu định giá', 'P/E'), 0) or 0)
                pb = float(row.get(('Chỉ tiêu định giá', 'P/B'), 0) or 0)
                roe = float(row.get(('Chỉ tiêu khả năng sinh lợi', 'ROE (%)'), 0) or 0) * 100
                roa = float(row.get(('Chỉ tiêu khả năng sinh lợi', 'ROA (%)'), 0) or 0) * 100
                records.append({
                    'period': period_str,
                    'pe': pe, 'pb': pb, 'roe': roe, 'roa': roa,
                })
            if records:
                self._fundamental_store.save_quarterly(symbol, records)
        except Exception:
            pass

    def get_historical_ratios(self, symbol: str, periods: int = 12) -> pd.DataFrame:
        """
        Lấy lịch sử chỉ số tài chính (PE, PB)
        Args:
            symbol: Mã cổ phiếu
            periods: Số kỳ (quý) cần lấy
        Returns:
            DataFrame với index là thời gian, columns là PE, PB
        """
        # Check cache
        cache_key = f"{symbol}_hist_ratios_{periods}"
        if cache_key in self.cache_data:
            cached = self.cache_data[cache_key]
            # Check expiry (7 days)
            cached_time = datetime.strptime(cached['timestamp'], "%Y-%m-%d")
            if (datetime.now() - cached_time).days < 7:
                try:
                    df = pd.DataFrame(cached['data'])
                    return df
                except:
                    pass

        try:
            stock = self.data_manager._get_stock(symbol)
            if stock:
                # Retry wrapper
                def fetch_ratio():
                    return stock.finance.ratio(period='quarter', lang='vi')
                
                df = self._retry_request(fetch_ratio)
                
                if df is not None and not df.empty:
                    # Lấy n dòng đầu tiên (mới nhất)
                    df_subset = df.head(periods).copy()
                    
                    result_data = []
                    for idx, row in df_subset.iterrows():
                        try:
                            # Extract PE, PB
                            pe = float(row.get(('Chỉ tiêu định giá', 'P/E'), 0))
                            pb = float(row.get(('Chỉ tiêu định giá', 'P/B'), 0))
                            
                            result_data.append({
                                'period': idx, 
                                'pe': pe,
                                'pb': pb
                            })
                        except:
                            pass
                    
                    result_df = pd.DataFrame(result_data)
                    
                    # Save to cache
                    self.cache_data[cache_key] = {
                        'data': result_df.to_dict(orient='records'),
                        'timestamp': datetime.now().strftime("%Y-%m-%d")
                    }
                    self._save_cache()
                    
                    return result_df
                        
        except Exception as e:
            print(f"   ⚠️ Lỗi lấy historical ratio {symbol}: {e}")
            
        return pd.DataFrame()

    def get_financial_flow(self, symbol: str) -> Dict[str, float]:
        """
        Lấy dữ liệu tăng trưởng doanh thu/lợi nhuận (Income Statement).
        Uses SQLite + JSON cache with 7-day TTL.
        """
        result = {
            'revenue_growth_qoq': 0.0,
            'revenue_growth_yoy': 0.0,
            'eps_growth_qoq': 0.0,
            'eps_growth_yoy': 0.0,
            'gross_margin': 0.0
        }

        # Check SQLite cache - if we have fresh fundamental data with revenue
        if self._fundamental_store and self._fundamental_store.is_fresh(symbol, max_days=7):
            eps_hist = self._fundamental_store.get_eps_history(symbol, periods=5)
            if len(eps_hist) >= 2:
                cur, prev = eps_hist[0], eps_hist[1]
                if prev.get('profit') and prev['profit'] != 0:
                    result['eps_growth_qoq'] = ((cur.get('profit', 0) - prev['profit']) / abs(prev['profit'])) * 100
                if prev.get('revenue') and prev['revenue'] != 0:
                    result['revenue_growth_qoq'] = ((cur.get('revenue', 0) - prev['revenue']) / abs(prev['revenue'])) * 100
                if any(v != 0 for v in result.values()):
                    return result

        # Check JSON cache
        cache_key = f"{symbol}_flow"
        if cache_key in self.cache_data:
            cached = self.cache_data[cache_key]
            try:
                cached_time = datetime.strptime(cached['timestamp'], "%Y-%m-%d")
                if (datetime.now() - cached_time).days < 7:
                    return cached['data']
            except (ValueError, KeyError):
                pass

        try:
            stock = self.data_manager._get_stock(symbol)
            if stock:
                df = stock.finance.income_statement(period='quarter', lang='vi')

                if not df.empty and len(df) >= 2:
                    col_rev_growth = 'Tăng trưởng doanh thu (%)'
                    col_prof_growth = 'Tăng trưởng lợi nhuận (%)'
                    col_profit = 'Lợi nhuận sau thuế của Cổ đông công ty mẹ (đồng)'
                    col_rev = 'Doanh thu (đồng)'

                    latest = df.iloc[0]
                    prev = df.iloc[1]

                    result['revenue_growth_yoy'] = float(latest.get(col_rev_growth, 0)) * 100
                    result['eps_growth_yoy'] = float(latest.get(col_prof_growth, 0)) * 100

                    prof_now = float(latest.get(col_profit, 0))
                    prof_prev = float(prev.get(col_profit, 0))

                    if prof_prev != 0:
                        result['eps_growth_qoq'] = ((prof_now - prof_prev) / abs(prof_prev)) * 100

                    rev_now = float(latest.get(col_rev, 0))
                    rev_prev = float(prev.get(col_rev, 0))

                    if rev_prev != 0:
                        result['revenue_growth_qoq'] = ((rev_now - rev_prev) / abs(rev_prev)) * 100

                    # Save to JSON cache
                    self.cache_data[cache_key] = {
                        'data': result,
                        'timestamp': datetime.now().strftime("%Y-%m-%d")
                    }
                    self._save_cache()

                    # Save to SQLite
                    if self._fundamental_store:
                        self._save_income_to_db(symbol, df)

        except Exception as e:
            print(f"   ⚠️ Lỗi lấy income statement {symbol}: {e}")

        return result

    def _save_income_to_db(self, symbol: str, df: pd.DataFrame):
        """Save income statement data to SQLite fundamental_store."""
        try:
            col_rev = 'Doanh thu (đồng)'
            col_profit = 'Lợi nhuận sau thuế của Cổ đông công ty mẹ (đồng)'

            records = []
            for idx, row in df.head(8).iterrows():
                period_str = str(idx) if isinstance(idx, str) else f"Q{idx}"
                records.append({
                    'period': period_str,
                    'revenue': float(row.get(col_rev, 0) or 0),
                    'profit': float(row.get(col_profit, 0) or 0),
                })
            if records:
                self._fundamental_store.save_quarterly(symbol, records)
        except Exception:
            pass

    def get_multiple_stocks(self, 
                            symbols: List[str], 
                            lookback_days: int = 120,
                            include_vp: bool = True) -> Dict[str, EnhancedStockData]:
        """Lấy dữ liệu nhiều mã cùng lúc"""
        results = {}
        
        for i, symbol in enumerate(symbols):
            print(f"   [{i+1}/{len(symbols)}] {symbol}...", end=" ")
            
            data = self.get_stock_data(symbol, lookback_days, include_vp)
            
            if data.price > 0:
                results[symbol] = data
                print(f"✓ {data.price:,.0f}")
            else:
                print("✗")
        
        return results


# ══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def get_data_collector(enable_volume_profile: bool = True) -> EnhancedDataCollector:
    """
    Factory function để tạo EnhancedDataCollector
    Tự động load config từ file config.py
    
    Usage:
        from data_collector import get_data_collector
        collector = get_data_collector()
        data = collector.get_stock_data("VCB")
    """
    config = get_config() if get_config else None
    
    api_key = config.get_vnstock_key() if config else None
    primary_source = config.get_data_source() if config else "VCI"
    api_delay = config.rate_limit.API_DELAY if config else 0.3
    
    return EnhancedDataCollector(
        api_key=api_key,
        primary_source=primary_source,
        api_delay=api_delay,
        enable_volume_profile=enable_volume_profile
    )


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Testing Enhanced Data Collector...")
    
    collector = get_data_collector()
    
    # Test single stock
    print("\n📈 Testing VCB...")
    data = collector.get_stock_data("VCB")
    
    if data.price > 0:
        print(f"\n✓ VCB Data:")
        print(f"   Price: {data.price:,.0f}")
        print(f"   Change 1D: {data.change_1d:+.2f}%")
        print(f"   RSI: {data.rsi_14:.1f}")
        print(f"   Above MA20: {data.above_ma20}")
        
        if data.poc > 0:
            print(f"\n📊 Volume Profile:")
            print(f"   POC: {data.poc:,.0f}")
            print(f"   VAH: {data.vah:,.0f}")
            print(f"   VAL: {data.val:,.0f}")
            print(f"   Position: {data.price_vs_va}")
    
    # Print stats
    collector.data_manager.print_stats()
