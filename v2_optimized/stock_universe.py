#!/usr/bin/env python3
"""
Stock Universe Manager - Quản lý danh sách cổ phiếu toàn thị trường

Tính năng:
- Lấy toàn bộ mã từ VNStock API (HoSE, HNX)
- Filter theo volume, market cap
- Phân loại theo ngành ICB
- Cache danh sách với TTL 7 ngày
"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
import warnings

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# Import config
try:
    from config import get_config, APIKeys
except ImportError:
    get_config = None
    APIKeys = None


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class StockUniverseConfig:
    """Config cho Stock Universe Manager"""

    # Filter settings
    MIN_VOLUME: int = 100_000              # Volume TB tối thiểu (cp/ngày)
    MIN_MARKET_CAP: float = 0              # Vốn hóa tối thiểu (VND) - 0 = không filter
    EXCHANGES: List[str] = field(default_factory=lambda: ['HSX', 'HNX'])
    EXCLUDE_TYPES: List[str] = field(default_factory=lambda: ['FUND', 'ETF', 'CW', 'BOND'])

    # Cache settings
    CACHE_DIR: str = "./cache"
    CACHE_TTL_DAYS: int = 7                # Cache danh sách 7 ngày

    # Sector mapping (ICB Level 2 → Internal code)
    # Map tên ngành ICB tiếng Việt sang code nội bộ
    ICB_TO_SECTOR: Dict[str, str] = field(default_factory=lambda: {
        # Tài chính
        'Ngân hàng': 'VNFIN',
        'Dịch vụ tài chính': 'VNFIN',
        'Bảo hiểm': 'VNFIN',
        'Tài chính': 'VNFIN',

        # Bất động sản
        'Bất động sản': 'VNREAL',
        'Phát triển bất động sản': 'VNREAL',
        'Dịch vụ bất động sản': 'VNREAL',

        # Nguyên vật liệu
        'Tài nguyên cơ bản': 'VNMAT',
        'Hóa chất': 'VNMAT',
        'Vật liệu xây dựng': 'VNMAT',
        'Khai khoáng': 'VNMAT',
        'Kim loại': 'VNMAT',
        'Thép': 'VNMAT',

        # Công nghệ
        'Công nghệ thông tin': 'VNIT',
        'Công nghệ': 'VNIT',
        'Phần mềm': 'VNIT',
        'Viễn thông': 'VNIT',

        # Y tế
        'Y tế': 'VNHEAL',
        'Dược phẩm': 'VNHEAL',
        'Thiết bị y tế': 'VNHEAL',
        'Chăm sóc sức khỏe': 'VNHEAL',

        # Tiêu dùng không thiết yếu
        'Hàng & Dịch vụ tiêu dùng': 'VNCOND',
        'Bán lẻ': 'VNCOND',
        'Du lịch & Giải trí': 'VNCOND',
        'Ô tô & phụ tùng': 'VNCOND',
        'Hàng cá nhân & gia dụng': 'VNCOND',
        'Truyền thông': 'VNCOND',

        # Tiêu dùng thiết yếu
        'Thực phẩm & Đồ uống': 'VNCONS',
        'Đồ uống': 'VNCONS',
        'Thực phẩm': 'VNCONS',
        'Nông nghiệp': 'VNCONS',
        'Thuỷ sản': 'VNCONS',
        'Chăn nuôi': 'VNCONS',

        # Các ngành khác (map vào ngành gần nhất)
        'Xây dựng & Vật liệu': 'VNMAT',
        'Hàng & Dịch vụ công nghiệp': 'VNMAT',
        'Điện, nước & xăng dầu khí đốt': 'VNMAT',
        'Dầu khí': 'VNMAT',
    })


# ══════════════════════════════════════════════════════════════════════════════
# STOCK UNIVERSE MANAGER
# ══════════════════════════════════════════════════════════════════════════════

class StockUniverse:
    """
    Quản lý danh sách cổ phiếu toàn thị trường

    Usage:
        universe = StockUniverse()
        all_stocks = universe.get_full_universe()
        fin_stocks = universe.get_stocks_by_sector('VNFIN')
    """

    def __init__(self, config: StockUniverseConfig = None):
        self.config = config or StockUniverseConfig()
        self.cache_dir = Path(self.config.CACHE_DIR)
        self.cache_dir.mkdir(exist_ok=True)

        # Cache files
        self.universe_cache_file = self.cache_dir / "stock_universe.json"
        self.sector_cache_file = self.cache_dir / "stock_by_sector.json"
        self.volume_cache_file = self.cache_dir / "stock_volume_avg.json"

        # Initialize vnstock
        self._init_vnstock()

        # In-memory cache
        self._universe_df: Optional[pd.DataFrame] = None
        self._sector_map: Optional[Dict[str, List[str]]] = None
        self._volume_map: Optional[Dict[str, float]] = None

    def _init_vnstock(self):
        """Khởi tạo vnstock"""
        try:
            if get_config:
                api_key = APIKeys.VNSTOCK if APIKeys else None
                if api_key:
                    os.environ['VNSTOCK_API_KEY'] = api_key

            from vnstock import Vnstock, Listing
            self.Vnstock = Vnstock
            self.Listing = Listing
            self._vnstock_available = True
        except ImportError as e:
            print(f"⚠️ vnstock not available: {e}")
            self._vnstock_available = False

    # ──────────────────────────────────────────────────────────────────────────
    # CACHE METHODS
    # ──────────────────────────────────────────────────────────────────────────

    def _load_cache(self, cache_file: Path, max_age_days: int = None) -> Optional[dict]:
        """Load cache nếu còn valid"""
        if max_age_days is None:
            max_age_days = self.config.CACHE_TTL_DAYS

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check age
            cached_time = datetime.fromisoformat(data.get('timestamp', '2000-01-01'))
            if (datetime.now() - cached_time).days > max_age_days:
                return None  # Expired

            return data
        except Exception as e:
            print(f"⚠️ Error loading cache {cache_file}: {e}")
            return None

    def _save_cache(self, cache_file: Path, data: dict):
        """Save to cache"""
        try:
            data['timestamp'] = datetime.now().isoformat()
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving cache {cache_file}: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # GET STOCK UNIVERSE
    # ──────────────────────────────────────────────────────────────────────────

    def get_full_universe(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Lấy toàn bộ danh sách cổ phiếu từ HoSE và HNX

        Returns:
            DataFrame với columns: [symbol, organ_name, exchange, icb_name, sector_code]
        """
        # Check in-memory cache
        if self._universe_df is not None and not force_refresh:
            return self._universe_df

        # Check file cache
        if not force_refresh:
            cached = self._load_cache(self.universe_cache_file)
            if cached and 'data' in cached:
                self._universe_df = pd.DataFrame(cached['data'])
                print(f"📦 Loaded {len(self._universe_df)} stocks from cache")
                return self._universe_df

        # Fetch from API
        print("🔄 Fetching full stock universe from VNStock API...")

        if not self._vnstock_available:
            print("❌ VNStock not available")
            return pd.DataFrame()

        try:
            listing = self.Listing(source='vci')

            # Get stocks by exchange
            df_exchange = listing.symbols_by_exchange()

            # Filter by exchange (HSX = HoSE, HNX)
            df_filtered = df_exchange[
                (df_exchange['exchange'].isin(self.config.EXCHANGES)) &
                (df_exchange['type'] == 'STOCK')
            ].copy()

            # Get industry info
            try:
                df_industry = listing.symbols_by_industries(lang='vi')
                df_filtered = df_filtered.merge(
                    df_industry[['symbol', 'icb_name2', 'icb_name3']],
                    on='symbol',
                    how='left'
                )
            except Exception as e:
                print(f"⚠️ Could not get industry data: {e}")
                df_filtered['icb_name2'] = ''
                df_filtered['icb_name3'] = ''

            # Map to internal sector codes
            df_filtered['sector_code'] = df_filtered['icb_name2'].apply(
                lambda x: self._map_icb_to_sector(x) if pd.notna(x) else 'OTHER'
            )

            # Select columns
            columns = ['symbol', 'organ_name', 'exchange', 'icb_name2', 'icb_name3', 'sector_code']
            df_result = df_filtered[[c for c in columns if c in df_filtered.columns]].copy()

            print(f"✅ Found {len(df_result)} stocks on {', '.join(self.config.EXCHANGES)}")

            # Print sector breakdown
            sector_counts = df_result['sector_code'].value_counts()
            print("\n📊 Breakdown by sector:")
            for sector, count in sector_counts.items():
                print(f"   {sector}: {count} stocks")

            # Save to cache
            self._save_cache(self.universe_cache_file, {
                'data': df_result.to_dict('records')
            })

            self._universe_df = df_result
            return df_result

        except Exception as e:
            print(f"❌ Error fetching stock universe: {e}")
            return pd.DataFrame()

    def _map_icb_to_sector(self, icb_name: str) -> str:
        """Map tên ngành ICB sang sector code nội bộ"""
        if not icb_name:
            return 'OTHER'

        icb_lower = icb_name.lower()

        for icb_key, sector_code in self.config.ICB_TO_SECTOR.items():
            if icb_key.lower() in icb_lower or icb_lower in icb_key.lower():
                return sector_code

        return 'OTHER'

    # ──────────────────────────────────────────────────────────────────────────
    # GET STOCKS BY SECTOR
    # ──────────────────────────────────────────────────────────────────────────

    def get_stocks_by_sector(self, sector_code: str = None,
                             min_volume: int = None) -> Dict[str, List[str]]:
        """
        Lấy danh sách cổ phiếu theo ngành

        Args:
            sector_code: Mã ngành (VNFIN, VNREAL, etc.). None = tất cả
            min_volume: Volume tối thiểu. None = dùng config

        Returns:
            Dict[sector_code, List[symbol]]
        """
        # Get full universe first
        df = self.get_full_universe()
        if df.empty:
            return {}

        # Filter by volume if needed
        if min_volume is None:
            min_volume = self.config.MIN_VOLUME

        if min_volume > 0:
            # Load volume data
            volume_map = self._get_volume_data()
            if volume_map:
                df = df[df['symbol'].apply(
                    lambda s: volume_map.get(s, 0) >= min_volume
                )]
                print(f"📊 After volume filter (≥{min_volume:,}): {len(df)} stocks")

        # Group by sector
        result = {}
        for sector, group in df.groupby('sector_code'):
            if sector != 'OTHER':  # Bỏ qua ngành OTHER
                result[sector] = group['symbol'].tolist()

        # Filter specific sector if requested
        if sector_code:
            return {sector_code: result.get(sector_code, [])}

        return result

    def get_all_sectors(self) -> List[str]:
        """Lấy danh sách tất cả sector codes"""
        return ['VNFIN', 'VNREAL', 'VNMAT', 'VNIT', 'VNHEAL', 'VNCOND', 'VNCONS']

    # ──────────────────────────────────────────────────────────────────────────
    # VOLUME DATA
    # ──────────────────────────────────────────────────────────────────────────

    def _get_volume_data(self, force_refresh: bool = False) -> Dict[str, float]:
        """
        Lấy volume trung bình 20 ngày của tất cả cổ phiếu
        Cache 1 ngày
        """
        # Check cache
        if self._volume_map and not force_refresh:
            return self._volume_map

        # Check file cache (1 day TTL)
        cached = self._load_cache(self.volume_cache_file, max_age_days=1)
        if cached and 'data' in cached and not force_refresh:
            self._volume_map = cached['data']
            return self._volume_map

        print("🔄 Fetching volume data (this may take a while)...")

        # Get universe
        df = self.get_full_universe()
        if df.empty:
            return {}

        volume_map = {}
        total = len(df)

        for i, symbol in enumerate(df['symbol'].tolist()):
            try:
                stock = self.Vnstock().stock(symbol=symbol, source='KBS')
                hist = stock.quote.history(start='2025-01-01', end=datetime.now().strftime('%Y-%m-%d'))

                if hist is not None and not hist.empty and 'volume' in hist.columns:
                    avg_vol = hist['volume'].tail(20).mean()
                    volume_map[symbol] = float(avg_vol) if not pd.isna(avg_vol) else 0

                # Progress
                if (i + 1) % 50 == 0:
                    print(f"   Progress: {i+1}/{total} ({(i+1)/total*100:.1f}%)")

            except Exception as e:
                volume_map[symbol] = 0

        # Save cache
        self._save_cache(self.volume_cache_file, {'data': volume_map})
        self._volume_map = volume_map

        print(f"✅ Loaded volume for {len(volume_map)} stocks")
        return volume_map

    def filter_by_liquidity(self, symbols: List[str],
                           min_volume: int = None) -> List[str]:
        """
        Lọc danh sách cổ phiếu theo thanh khoản

        Args:
            symbols: Danh sách mã cần lọc
            min_volume: Volume tối thiểu

        Returns:
            List symbols đạt yêu cầu
        """
        if min_volume is None:
            min_volume = self.config.MIN_VOLUME

        volume_map = self._get_volume_data()

        return [s for s in symbols if volume_map.get(s, 0) >= min_volume]

    # ──────────────────────────────────────────────────────────────────────────
    # UTILITY METHODS
    # ──────────────────────────────────────────────────────────────────────────

    def get_stock_info(self, symbol: str) -> Optional[dict]:
        """Lấy thông tin của một cổ phiếu"""
        df = self.get_full_universe()
        if df.empty:
            return None

        row = df[df['symbol'] == symbol]
        if row.empty:
            return None

        return row.iloc[0].to_dict()

    def get_sector_for_stock(self, symbol: str) -> str:
        """Lấy sector code của một cổ phiếu"""
        info = self.get_stock_info(symbol)
        return info.get('sector_code', 'OTHER') if info else 'OTHER'

    def clear_cache(self):
        """Xóa tất cả cache"""
        for cache_file in [self.universe_cache_file, self.sector_cache_file, self.volume_cache_file]:
            if cache_file.exists():
                cache_file.unlink()

        self._universe_df = None
        self._sector_map = None
        self._volume_map = None
        print("✅ Cache cleared")

    def get_stats(self) -> dict:
        """Lấy thống kê về universe"""
        df = self.get_full_universe()
        if df.empty:
            return {}

        return {
            'total_stocks': len(df),
            'by_exchange': df['exchange'].value_counts().to_dict(),
            'by_sector': df['sector_code'].value_counts().to_dict(),
            'cache_age_days': self._get_cache_age_days(),
        }

    def _get_cache_age_days(self) -> int:
        """Tính tuổi cache (ngày)"""
        cached = self._load_cache(self.universe_cache_file, max_age_days=365)
        if cached:
            cached_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
            return (datetime.now() - cached_time).days
        return -1


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

_universe_instance: Optional[StockUniverse] = None

def get_stock_universe(config: StockUniverseConfig = None) -> StockUniverse:
    """Lấy singleton instance của StockUniverse"""
    global _universe_instance
    if _universe_instance is None:
        _universe_instance = StockUniverse(config)
    return _universe_instance


# ══════════════════════════════════════════════════════════════════════════════
# CLI TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("STOCK UNIVERSE MANAGER - TEST")
    print("=" * 60)

    universe = StockUniverse()

    # Test 1: Get full universe
    print("\n[1] Getting full stock universe...")
    df = universe.get_full_universe()
    print(f"Total stocks: {len(df)}")

    # Test 2: Get stocks by sector
    print("\n[2] Stocks by sector:")
    sector_stocks = universe.get_stocks_by_sector()
    for sector, stocks in sector_stocks.items():
        print(f"   {sector}: {len(stocks)} stocks - {stocks[:5]}...")

    # Test 3: Stats
    print("\n[3] Statistics:")
    stats = universe.get_stats()
    print(f"   Total: {stats.get('total_stocks', 0)}")
    print(f"   By exchange: {stats.get('by_exchange', {})}")
    print(f"   Cache age: {stats.get('cache_age_days', -1)} days")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
