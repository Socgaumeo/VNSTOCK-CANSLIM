#!/usr/bin/env python3
"""
Smart Cache System - Cache thông minh với TTL khác nhau theo loại dữ liệu

Tính năng:
- TTL khác nhau cho từng loại dữ liệu
- Auto-refresh theo mùa BCTC
- Force refresh khi có BCTC mới
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import warnings

warnings.filterwarnings('ignore')


# ══════════════════════════════════════════════════════════════════════════════
# CACHE DATA TYPES & TTL
# ══════════════════════════════════════════════════════════════════════════════

class CacheDataType(Enum):
    """Loại dữ liệu và TTL tương ứng"""

    # Dữ liệu thay đổi theo quý (BCTC)
    QUARTERLY_FINANCIALS = "quarterly_financials"     # EPS, Revenue, Profit
    CASH_FLOW = "cash_flow"                          # Operating CF, Investing CF
    FINANCIAL_RATIOS = "financial_ratios"            # ROE, ROA, PE, PB

    # Dữ liệu ít thay đổi
    STOCK_LIST = "stock_list"                        # Danh sách cổ phiếu
    SECTOR_MAPPING = "sector_mapping"                # ICB → Sector code
    COMPANY_INFO = "company_info"                    # Thông tin công ty

    # Dữ liệu thay đổi hàng ngày (không cache lâu)
    DAILY_PRICE = "daily_price"                      # Giá, Volume
    VOLUME_AVERAGE = "volume_average"                # Volume TB 20 ngày

    # Historical data tracking (NEW)
    DAILY_PRICE_SNAPSHOT = "daily_price_snapshot"    # Daily OHLCV + indicators (30 ngày)
    DAILY_FOREIGN_FLOW = "daily_foreign_flow"        # Daily foreign buy/sell (30 ngày)
    RECOMMENDATION_HISTORY = "recommendation_history" # Daily picks + tracking


# TTL mặc định cho từng loại dữ liệu (ngày)
DEFAULT_TTL = {
    CacheDataType.QUARTERLY_FINANCIALS: 30,      # 30 ngày - update theo BCTC quý
    CacheDataType.CASH_FLOW: 30,                 # 30 ngày
    CacheDataType.FINANCIAL_RATIOS: 30,          # 30 ngày
    CacheDataType.STOCK_LIST: 7,                 # 7 ngày
    CacheDataType.SECTOR_MAPPING: 30,            # 30 ngày - rất ít thay đổi
    CacheDataType.COMPANY_INFO: 30,              # 30 ngày
    CacheDataType.DAILY_PRICE: 0,                # Không cache (0 = always fetch)
    CacheDataType.VOLUME_AVERAGE: 1,             # 1 ngày
    # Historical data (keep 30-90 days of snapshots)
    CacheDataType.DAILY_PRICE_SNAPSHOT: 30,      # Giữ 30 ngày snapshot
    CacheDataType.DAILY_FOREIGN_FLOW: 30,        # Giữ 30 ngày foreign flow
    CacheDataType.RECOMMENDATION_HISTORY: 90,    # Giữ 90 ngày recommendations
}


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class SmartCacheConfig:
    """Config cho Smart Cache"""

    CACHE_DIR: str = "./cache"

    # Custom TTL (override DEFAULT_TTL)
    CUSTOM_TTL: Dict[CacheDataType, int] = field(default_factory=dict)

    # Mùa BCTC - sau các mốc này sẽ force refresh fundamental data
    # (tháng, ngày) - thường BCTC công bố ~15-20 ngày sau khi kết thúc quý
    EARNINGS_DATES: list = field(default_factory=lambda: [
        (1, 25),    # Q4 năm trước
        (4, 25),    # Q1
        (7, 25),    # Q2
        (10, 25),   # Q3
    ])

    # Enable earnings season auto-refresh
    ENABLE_EARNINGS_REFRESH: bool = True


# ══════════════════════════════════════════════════════════════════════════════
# SMART CACHE MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class SmartCache:
    """
    Smart Cache Manager với TTL khác nhau theo loại dữ liệu

    Usage:
        cache = SmartCache()

        # Save fundamental data (30-day TTL)
        cache.set("VCB", CacheDataType.QUARTERLY_FINANCIALS, data)

        # Get with auto-expiry check
        data = cache.get("VCB", CacheDataType.QUARTERLY_FINANCIALS)
    """

    def __init__(self, config: SmartCacheConfig = None):
        self.config = config or SmartCacheConfig()
        self.cache_dir = Path(self.config.CACHE_DIR)
        self.cache_dir.mkdir(exist_ok=True)

        # In-memory cache
        self._memory_cache: Dict[str, dict] = {}

        # Stats
        self.stats = {
            'hits': 0,
            'misses': 0,
            'expired': 0,
            'earnings_refresh': 0,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # CORE METHODS
    # ──────────────────────────────────────────────────────────────────────────

    def get(self, symbol: str, data_type: CacheDataType,
            force_refresh: bool = False) -> Optional[Any]:
        """
        Lấy dữ liệu từ cache

        Args:
            symbol: Mã cổ phiếu
            data_type: Loại dữ liệu
            force_refresh: Bỏ qua cache, luôn trả về None

        Returns:
            Data nếu cache còn valid, None nếu expired hoặc không có
        """
        if force_refresh:
            return None

        cache_key = self._get_cache_key(symbol, data_type)

        # Check memory cache first
        if cache_key in self._memory_cache:
            cached = self._memory_cache[cache_key]
            if self._is_valid(cached, data_type):
                self.stats['hits'] += 1
                return cached.get('data')
            else:
                self.stats['expired'] += 1
                del self._memory_cache[cache_key]

        # Check file cache
        cache_file = self._get_cache_file(symbol, data_type)
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)

                if self._is_valid(cached, data_type):
                    self._memory_cache[cache_key] = cached
                    self.stats['hits'] += 1
                    return cached.get('data')
                else:
                    self.stats['expired'] += 1
            except Exception as e:
                pass

        self.stats['misses'] += 1
        return None

    def set(self, symbol: str, data_type: CacheDataType, data: Any) -> bool:
        """
        Lưu dữ liệu vào cache

        Args:
            symbol: Mã cổ phiếu
            data_type: Loại dữ liệu
            data: Dữ liệu cần cache

        Returns:
            True nếu thành công
        """
        cache_key = self._get_cache_key(symbol, data_type)
        cache_file = self._get_cache_file(symbol, data_type)

        cached = {
            'symbol': symbol,
            'data_type': data_type.value,
            'timestamp': datetime.now().isoformat(),
            'data': data,
        }

        # Save to memory
        self._memory_cache[cache_key] = cached

        # Save to file
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cached, f, ensure_ascii=False, indent=2, default=str)
            return True
        except Exception as e:
            print(f"⚠️ Error saving cache for {symbol}: {e}")
            return False

    def delete(self, symbol: str, data_type: CacheDataType) -> bool:
        """Xóa cache cho một symbol và data type"""
        cache_key = self._get_cache_key(symbol, data_type)
        cache_file = self._get_cache_file(symbol, data_type)

        # Remove from memory
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]

        # Remove file
        if cache_file.exists():
            cache_file.unlink()
            return True

        return False

    def get_or_fetch(self, symbol: str, data_type: CacheDataType,
                     fetch_func: Callable[[], Any],
                     force_refresh: bool = False) -> Optional[Any]:
        """
        Lấy từ cache hoặc fetch nếu không có

        Args:
            symbol: Mã cổ phiếu
            data_type: Loại dữ liệu
            fetch_func: Function để fetch dữ liệu nếu cache miss
            force_refresh: Bỏ qua cache

        Returns:
            Data từ cache hoặc từ fetch_func
        """
        # Try cache first
        if not force_refresh:
            cached = self.get(symbol, data_type)
            if cached is not None:
                return cached

        # Fetch new data
        try:
            data = fetch_func()
            if data is not None:
                self.set(symbol, data_type, data)
            return data
        except Exception as e:
            print(f"⚠️ Error fetching {data_type.value} for {symbol}: {e}")
            return None

    # ──────────────────────────────────────────────────────────────────────────
    # VALIDATION
    # ──────────────────────────────────────────────────────────────────────────

    def _is_valid(self, cached: dict, data_type: CacheDataType) -> bool:
        """Kiểm tra cache còn valid không"""
        if not cached or 'timestamp' not in cached:
            return False

        try:
            cached_time = datetime.fromisoformat(cached['timestamp'])
        except:
            return False

        # Get TTL
        ttl_days = self._get_ttl(data_type)

        # TTL = 0 means no caching
        if ttl_days == 0:
            return False

        # Check basic expiry
        if (datetime.now() - cached_time).days > ttl_days:
            return False

        # Check earnings season refresh for fundamental data
        if self.config.ENABLE_EARNINGS_REFRESH:
            if data_type in [CacheDataType.QUARTERLY_FINANCIALS,
                            CacheDataType.CASH_FLOW,
                            CacheDataType.FINANCIAL_RATIOS]:
                if self._should_refresh_for_earnings(cached_time):
                    self.stats['earnings_refresh'] += 1
                    return False

        return True

    def _should_refresh_for_earnings(self, cached_time: datetime) -> bool:
        """
        Kiểm tra có cần refresh do mùa BCTC không

        Logic: Nếu cache từ trước mùa BCTC và đã qua mùa BCTC → refresh
        """
        today = datetime.now()

        for month, day in self.config.EARNINGS_DATES:
            # Tạo ngày công bố BCTC năm nay
            earnings_date = datetime(today.year, month, day)

            # Nếu cache từ TRƯỚC ngày BCTC và hiện tại đã QUA ngày BCTC
            if cached_time < earnings_date <= today:
                return True

            # Kiểm tra cả năm trước (cho Q4)
            if month == 1:
                earnings_date_prev = datetime(today.year - 1, month, day)
                if cached_time < earnings_date_prev <= today:
                    return True

        return False

    def _get_ttl(self, data_type: CacheDataType) -> int:
        """Lấy TTL cho data type"""
        # Custom TTL có độ ưu tiên cao hơn
        if data_type in self.config.CUSTOM_TTL:
            return self.config.CUSTOM_TTL[data_type]

        return DEFAULT_TTL.get(data_type, 7)

    # ──────────────────────────────────────────────────────────────────────────
    # HELPER METHODS
    # ──────────────────────────────────────────────────────────────────────────

    def _get_cache_key(self, symbol: str, data_type: CacheDataType) -> str:
        """Tạo cache key"""
        return f"{symbol}_{data_type.value}"

    def _get_cache_file(self, symbol: str, data_type: CacheDataType) -> Path:
        """Lấy path file cache"""
        return self.cache_dir / f"smart_{symbol}_{data_type.value}.json"

    def get_cache_info(self, symbol: str, data_type: CacheDataType) -> Optional[dict]:
        """Lấy thông tin về cache entry"""
        cache_file = self._get_cache_file(symbol, data_type)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)

            cached_time = datetime.fromisoformat(cached['timestamp'])
            ttl_days = self._get_ttl(data_type)
            age_days = (datetime.now() - cached_time).days
            is_valid = self._is_valid(cached, data_type)

            return {
                'symbol': symbol,
                'data_type': data_type.value,
                'cached_at': cached['timestamp'],
                'age_days': age_days,
                'ttl_days': ttl_days,
                'expires_in_days': max(0, ttl_days - age_days),
                'is_valid': is_valid,
            }
        except:
            return None

    def clear_all(self, data_type: CacheDataType = None):
        """Xóa tất cả cache hoặc theo data type"""
        pattern = f"smart_*_{data_type.value}.json" if data_type else "smart_*.json"

        count = 0
        for cache_file in self.cache_dir.glob(pattern):
            cache_file.unlink()
            count += 1

        self._memory_cache.clear()
        print(f"✅ Cleared {count} cache files")

    def clear_expired(self) -> int:
        """Xóa các cache đã hết hạn"""
        count = 0
        for cache_file in self.cache_dir.glob("smart_*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)

                data_type_str = cached.get('data_type', '')
                try:
                    data_type = CacheDataType(data_type_str)
                except ValueError:
                    continue

                if not self._is_valid(cached, data_type):
                    cache_file.unlink()
                    count += 1
            except:
                pass

        return count

    def get_stats(self) -> dict:
        """Lấy thống kê cache"""
        total_files = len(list(self.cache_dir.glob("smart_*.json")))

        return {
            **self.stats,
            'total_files': total_files,
            'memory_entries': len(self._memory_cache),
            'hit_rate': self.stats['hits'] / max(1, self.stats['hits'] + self.stats['misses']) * 100,
        }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

_cache_instance: Optional[SmartCache] = None

def get_smart_cache(config: SmartCacheConfig = None) -> SmartCache:
    """Lấy singleton instance của SmartCache"""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = SmartCache(config)
    return _cache_instance


# ══════════════════════════════════════════════════════════════════════════════
# CLI TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("SMART CACHE SYSTEM - TEST")
    print("=" * 60)

    cache = SmartCache()

    # Test 1: Set and Get
    print("\n[1] Testing set/get...")
    test_data = {
        'eps': 5000,
        'revenue': 100_000_000_000,
        'profit': 10_000_000_000,
    }
    cache.set("VCB", CacheDataType.QUARTERLY_FINANCIALS, test_data)

    retrieved = cache.get("VCB", CacheDataType.QUARTERLY_FINANCIALS)
    print(f"   Set: {test_data}")
    print(f"   Get: {retrieved}")
    print(f"   Match: {test_data == retrieved}")

    # Test 2: Cache info
    print("\n[2] Cache info:")
    info = cache.get_cache_info("VCB", CacheDataType.QUARTERLY_FINANCIALS)
    print(f"   {info}")

    # Test 3: TTL check
    print("\n[3] TTL by data type:")
    for dt in CacheDataType:
        ttl = cache._get_ttl(dt)
        print(f"   {dt.value}: {ttl} days")

    # Test 4: Stats
    print("\n[4] Stats:")
    stats = cache.get_stats()
    for k, v in stats.items():
        print(f"   {k}: {v}")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
