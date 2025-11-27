#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     MODULE 2 COMBINED: SECTOR ROTATION + STOCK SCREENING                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Kết hợp:                                                                    ║
║  - Module 2: Sector Rotation (xác định ngành mạnh/yếu)                       ║
║  - Module 2.5: Stock Screening (lọc cổ phiếu trong ngành mạnh)               ║
║                                                                              ║
║  Output: Báo cáo chi tiết với logic từng bước                               ║
║                                                                              ║
║  Logic Phase: THỐNG NHẤT với module2_sector_rotation_v2.py                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

from config import get_config
from data_collector import get_data_collector, EnhancedStockData

# Import AI
try:
    from ai_providers import AIProvider, AIConfig
except ImportError:
    AIProvider = None


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR → ICB MAPPING
# ══════════════════════════════════════════════════════════════════════════════

SECTOR_INFO = {
    'VNFIN': {
        'name': 'Tài chính',
        'icb': ['Ngân hàng', 'Dịch vụ tài chính', 'Bảo hiểm'],
        'description': 'Ngân hàng, chứng khoán, bảo hiểm'
    },
    'VNREAL': {
        'name': 'Bất động sản',
        'icb': ['Bất động sản'],
        'description': 'Phát triển, đầu tư, môi giới BĐS'
    },
    'VNMAT': {
        'name': 'Nguyên vật liệu',
        'icb': ['Xây dựng và Vật liệu', 'Tài nguyên Cơ bản', 'Hóa chất'],
        'description': 'Xây dựng, thép, xi măng, hóa chất'
    },
    'VNIT': {
        'name': 'Công nghệ',
        'icb': ['Công nghệ Thông tin', 'Viễn thông'],
        'description': 'Phần mềm, viễn thông, IT'
    },
    'VNHEAL': {
        'name': 'Y tế',
        'icb': ['Y tế'],
        'description': 'Dược phẩm, bệnh viện, thiết bị y tế'
    },
    'VNCOND': {
        'name': 'Tiêu dùng không thiết yếu',
        'icb': ['Bán lẻ', 'Du lịch và Giải trí', 'Ô tô và phụ tùng', 'Hàng cá nhân & Gia dụng'],
        'description': 'Bán lẻ, du lịch, ô tô, hàng tiêu dùng'
    },
    'VNCONS': {
        'name': 'Tiêu dùng thiết yếu',
        'icb': ['Thực phẩm và đồ uống'],
        'description': 'Thực phẩm, đồ uống, nhu yếu phẩm'
    },
}

# Reverse mapping
ICB_TO_SECTOR = {}
for sector, info in SECTOR_INFO.items():
    for icb in info['icb']:
        ICB_TO_SECTOR[icb] = sector


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS & DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

class SectorPhase(Enum):
    LEADING = "🚀 Leading"
    IMPROVING = "📈 Improving"
    WEAKENING = "📉 Weakening"
    LAGGING = "⛔ Lagging"


@dataclass
class SectorAnalysis:
    """Phân tích chi tiết 1 ngành"""
    code: str
    name: str
    
    # Performance
    change_1d: float = 0.0
    change_5d: float = 0.0
    change_1m: float = 0.0
    
    # RS vs VNIndex
    rs_vs_vnindex: float = 0.0
    
    # Technical
    rsi: float = 50.0
    above_ma20: bool = False
    above_ma50: bool = False
    
    # Phase & Score
    phase: SectorPhase = SectorPhase.LAGGING
    score: float = 0.0
    rank: int = 0
    
    # Logic giải thích
    logic_notes: List[str] = field(default_factory=list)


@dataclass
class StockAnalysis:
    """Phân tích chi tiết 1 cổ phiếu"""
    symbol: str
    name: str
    sector: str
    icb_name: str
    
    # Price
    price: float = 0.0
    change_1d: float = 0.0
    change_5d: float = 0.0
    change_1m: float = 0.0
    
    # MA & SEPA
    ma20: float = 0.0
    ma50: float = 0.0
    ma150: float = 0.0
    ma200: float = 0.0
    sepa_stage: str = "N/A"
    
    # RS
    rs_vs_vnindex: float = 0.0
    rs_rating: int = 0
    
    # 52 week
    high_52w: float = 0.0
    low_52w: float = 0.0
    pct_from_high: float = 0.0
    pct_from_low: float = 0.0
    
    # Volume
    avg_value_20d: float = 0.0  # tỷ VNĐ
    
    # Fundamentals (ước tính)
    eps_growth: float = 0.0
    roe: float = 0.0
    
    # Scoring
    criteria: Dict[str, bool] = field(default_factory=dict)
    score: int = 0
    rank: int = 0
    
    # Logic giải thích
    logic_notes: List[str] = field(default_factory=list)


@dataclass
class CombinedReport:
    """Báo cáo kết hợp"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # VNIndex baseline
    vnindex_price: float = 0.0
    vnindex_change_1d: float = 0.0
    vnindex_change_1m: float = 0.0
    
    # Sector Analysis
    sectors: List[SectorAnalysis] = field(default_factory=list)
    leading_sectors: List[str] = field(default_factory=list)
    improving_sectors: List[str] = field(default_factory=list)
    weakening_sectors: List[str] = field(default_factory=list)
    lagging_sectors: List[str] = field(default_factory=list)
    
    # Stock Screening
    total_stocks_in_target: int = 0
    pass_liquidity: int = 0
    watchlist: List[StockAnalysis] = field(default_factory=list)
    
    # Stats
    api_calls_saved: int = 0
    
    # AI
    ai_analysis: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# COMBINED ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class CombinedAnalyzer:
    """Phân tích kết hợp Sector + Stock - SỬ DỤNG DATA_COLLECTOR THỐNG NHẤT"""
    
    def __init__(self):
        self.config = get_config()
        self._init_vnstock()
        # Sử dụng data_collector giống module2_sector_rotation_v2
        self.collector = get_data_collector(enable_volume_profile=True)
    
    def _init_vnstock(self):
        try:
            from vnstock import Vnstock, Listing
            self.listing = Listing()
            self.vnstock = Vnstock()
            self.source = self.config.get_data_source()
            print("✓ Kết nối vnstock thành công")
        except Exception as e:
            print(f"❌ Lỗi: {e}")
    
    def analyze(self) -> CombinedReport:
        """Chạy phân tích kết hợp"""
        print("\n" + "="*70)
        print("📊 MODULE 2 COMBINED: SECTOR ROTATION + STOCK SCREENING")
        print("="*70)
        
        report = CombinedReport()
        
        # ══════════════════════════════════════════════════════════════════════
        # BƯỚC 1: LẤY VNINDEX BASELINE
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "─"*60)
        print("📌 BƯỚC 1: VNINDEX BASELINE")
        print("─"*60)
        
        # Sử dụng data_collector giống module2_sector_rotation_v2
        vni_data = self.collector.get_stock_data("VNINDEX", lookback_days=90, include_vp=False)
        report.vnindex_price = vni_data.price
        report.vnindex_change_1d = vni_data.change_1d
        report.vnindex_change_1m = vni_data.change_1m
        
        print(f"   VNIndex: {report.vnindex_price:,.0f}")
        print(f"   1D: {report.vnindex_change_1d:+.2f}% | 1M: {report.vnindex_change_1m:+.2f}%")
        print(f"   → Đây là benchmark để tính RS (Relative Strength)")
        
        # ══════════════════════════════════════════════════════════════════════
        # BƯỚC 2: PHÂN TÍCH 7 NGÀNH
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "─"*60)
        print("📌 BƯỚC 2: PHÂN TÍCH 7 NGÀNH")
        print("─"*60)
        
        for code, info in SECTOR_INFO.items():
            print(f"\n   [{code}] {info['name']}...", end=" ")
            
            sector = self._analyze_sector(code, info, report.vnindex_change_1m)
            report.sectors.append(sector)
            
            print(f"RS={sector.rs_vs_vnindex:+.2f}% → {sector.phase.value}")
        
        # Sort và phân loại
        report.sectors.sort(key=lambda x: x.score, reverse=True)
        for i, s in enumerate(report.sectors, 1):
            s.rank = i
            
            if s.phase == SectorPhase.LEADING:
                report.leading_sectors.append(s.code)
            elif s.phase == SectorPhase.IMPROVING:
                report.improving_sectors.append(s.code)
            elif s.phase == SectorPhase.WEAKENING:
                report.weakening_sectors.append(s.code)
            else:
                report.lagging_sectors.append(s.code)
        
        print(f"\n\n   📊 KẾT QUẢ XẾP HẠNG NGÀNH:")
        print(f"   {'Rank':<5} {'Code':<8} {'Tên':<25} {'1M':>8} {'RS':>8} {'Phase':<15}")
        print("   " + "-"*70)
        for s in report.sectors:
            print(f"   {s.rank:<5} {s.code:<8} {s.name:<25} {s.change_1m:>+7.2f}% {s.rs_vs_vnindex:>+7.2f}% {s.phase.value:<15}")
        
        # ══════════════════════════════════════════════════════════════════════
        # BƯỚC 3: XÁC ĐỊNH NGÀNH MỤC TIÊU
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "─"*60)
        print("📌 BƯỚC 3: XÁC ĐỊNH NGÀNH MỤC TIÊU")
        print("─"*60)
        
        target_sectors = report.leading_sectors + report.improving_sectors
        
        print(f"   🚀 Leading: {report.leading_sectors or ['Không có']}")
        print(f"   📈 Improving: {report.improving_sectors or ['Không có']}")
        print(f"   → Ngành mục tiêu: {target_sectors}")
        
        if not target_sectors:
            print("   ⚠️ Không có ngành mạnh, sử dụng 2 ngành đứng đầu")
            target_sectors = [report.sectors[0].code, report.sectors[1].code]
        
        # ══════════════════════════════════════════════════════════════════════
        # BƯỚC 4: LẤY CỔ PHIẾU TRONG NGÀNH MỤC TIÊU
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "─"*60)
        print("📌 BƯỚC 4: LẤY CỔ PHIẾU TRONG NGÀNH MỤC TIÊU")
        print("─"*60)
        
        stocks_in_target = self._get_stocks_in_sectors(target_sectors)
        report.total_stocks_in_target = len(stocks_in_target)
        report.api_calls_saved = 500 - report.total_stocks_in_target
        
        print(f"   Tổng cổ phiếu trong ngành: {report.total_stocks_in_target}")
        print(f"   API calls tiết kiệm: ~{report.api_calls_saved} (vs scan toàn thị trường)")
        
        # ══════════════════════════════════════════════════════════════════════
        # BƯỚC 5: LỌC THANH KHOẢN
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "─"*60)
        print("📌 BƯỚC 5: LỌC THANH KHOẢN (>10 tỷ/phiên)")
        print("─"*60)
        
        liquid_stocks = self._filter_liquidity(stocks_in_target)
        report.pass_liquidity = len(liquid_stocks)
        
        print(f"   Qua thanh khoản: {report.pass_liquidity}/{report.total_stocks_in_target}")
        
        # ══════════════════════════════════════════════════════════════════════
        # BƯỚC 6: PHÂN TÍCH CHI TIẾT & SCORING
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "─"*60)
        print("📌 BƯỚC 6: PHÂN TÍCH CHI TIẾT & SCORING")
        print("─"*60)
        
        candidates = self._analyze_stocks(liquid_stocks, report.vnindex_change_1m)
        
        # Sort và lấy top 20
        candidates.sort(key=lambda x: x.score, reverse=True)
        report.watchlist = candidates[:20]
        
        for i, s in enumerate(report.watchlist, 1):
            s.rank = i
        
        print(f"   Đã phân tích: {len(candidates)} mã")
        print(f"   Watchlist cuối: {len(report.watchlist)} mã")
        
        return report
    
    def _get_index_data(self, symbol: str) -> Dict:
        """Lấy dữ liệu index"""
        try:
            stock = self.vnstock.stock(symbol=symbol, source=self.source)
            end = datetime.now().strftime('%Y-%m-%d')
            start = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
            
            df = stock.quote.history(start=start, end=end, interval='1D')
            
            if df is not None and len(df) >= 20:
                return {
                    'price': df['close'].iloc[-1],
                    'change_1d': (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100,
                    'change_5d': (df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100 if len(df) >= 5 else 0,
                    'change_1m': (df['close'].iloc[-1] - df['close'].iloc[-20]) / df['close'].iloc[-20] * 100,
                }
        except:
            pass
        return {'price': 0, 'change_1d': 0, 'change_5d': 0, 'change_1m': 0}
    
    def _analyze_sector(self, code: str, info: Dict, vnindex_1m: float) -> SectorAnalysis:
        """Phân tích 1 ngành - SỬ DỤNG DATA_COLLECTOR GIỐNG module2_sector_rotation_v2"""
        sector = SectorAnalysis(code=code, name=info['name'])
        
        # Sử dụng data_collector thay vì _get_index_data để có dữ liệu nhất quán
        data = self.collector.get_stock_data(code, lookback_days=90, include_vp=False)
        
        if data.price == 0:
            return sector
        
        sector.change_1d = data.change_1d
        sector.change_5d = data.change_5d
        sector.change_1m = data.change_1m
        sector.rsi = data.rsi_14
        sector.above_ma20 = data.above_ma20
        sector.above_ma50 = data.above_ma50
        
        # RS vs VNIndex
        sector.rs_vs_vnindex = sector.change_1m - vnindex_1m
        
        # Xác định Phase - LOGIC GIỐNG module2_sector_rotation_v2
        sector.logic_notes = []
        rs = sector.rs_vs_vnindex
        momentum = sector.change_5d
        
        # Logic từ module2_sector_rotation_v2._determine_phase():
        # if rs > 3 and momentum > 0 and sector.above_ma20:
        #     return LEADING
        # elif rs > 0 and momentum > sector.change_1d:
        #     return IMPROVING
        # elif rs > 0 and momentum < 0:
        #     return WEAKENING
        # else:
        #     return LAGGING
        
        if rs > 3 and momentum > 0 and sector.above_ma20:
            sector.phase = SectorPhase.LEADING
            sector.logic_notes.append(f"RS > +3% ({rs:+.2f}%): Outperform mạnh")
            sector.logic_notes.append(f"5D > 0 ({momentum:+.2f}%): Momentum tích cực")
            sector.logic_notes.append(f"Giá > MA20: {'✓' if sector.above_ma20 else '✗'}")
            sector.logic_notes.append("→ LEADING")
        elif rs > 0 and momentum > sector.change_1d:
            sector.phase = SectorPhase.IMPROVING
            sector.logic_notes.append(f"RS > 0 ({rs:+.2f}%): Outperform nhẹ")
            sector.logic_notes.append(f"5D ({momentum:+.2f}%) > 1D ({sector.change_1d:+.2f}%): Đang tăng tốc")
            sector.logic_notes.append("→ IMPROVING")
        elif rs > 0 and momentum < 0:
            sector.phase = SectorPhase.WEAKENING
            sector.logic_notes.append(f"RS > 0 ({rs:+.2f}%): Vẫn outperform")
            sector.logic_notes.append(f"5D < 0 ({momentum:+.2f}%): Nhưng momentum đang giảm")
            sector.logic_notes.append("→ WEAKENING")
        else:
            sector.phase = SectorPhase.LAGGING
            sector.logic_notes.append(f"RS < 0 ({rs:+.2f}%): Underperform")
            sector.logic_notes.append("→ LAGGING")
        
        # Score - giống module2_sector_rotation_v2._calc_score()
        score = 0
        
        # 1M Performance (30%)
        score += max(-30, min(30, sector.change_1m * 2))
        
        # RS vs VNIndex (30%)
        score += max(-30, min(30, rs * 3))
        
        # RSI position (20%)
        if 50 <= sector.rsi <= 70:
            score += 20
        elif sector.rsi > 70:
            score += 10
        elif sector.rsi < 30:
            score += 15
        
        # MA alignment (20%)
        if sector.above_ma20 and sector.above_ma50:
            score += 20
        elif sector.above_ma20:
            score += 10
        
        sector.score = max(0, min(100, 50 + score))
        
        return sector
    
    def _get_stocks_in_sectors(self, sectors: List[str]) -> List[Dict]:
        """Lấy cổ phiếu trong các ngành mục tiêu"""
        stocks = []
        
        try:
            all_stocks = self.listing.symbols_by_industries()
            
            target_icbs = []
            for sector in sectors:
                if sector in SECTOR_INFO:
                    target_icbs.extend(SECTOR_INFO[sector]['icb'])
            
            for _, row in all_stocks.iterrows():
                icb = row.get('icb_name2', '')
                symbol = row['symbol']
                
                if icb in target_icbs and len(symbol) == 3:
                    stocks.append({
                        'symbol': symbol,
                        'name': row.get('organ_name', ''),
                        'sector': ICB_TO_SECTOR.get(icb, ''),
                        'icb': icb
                    })
        except Exception as e:
            print(f"   ⚠️ Lỗi: {e}")
        
        return stocks
    
    def _filter_liquidity(self, stocks: List[Dict]) -> List[Dict]:
        """Lọc theo thanh khoản"""
        liquid = []
        symbols = [s['symbol'] for s in stocks]
        min_value = 10_000_000_000  # 10 tỷ
        
        batch_size = 50
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            print(f"   Batch {i//batch_size + 1}...", end=" ")
            
            try:
                stock = self.vnstock.stock(symbol=batch[0], source=self.source)
                df = stock.trading.price_board(symbols_list=batch)
                
                if df is not None:
                    for _, row in df.iterrows():
                        try:
                            sym = row[('listing', 'symbol')]
                            vol = row[('match', 'match_vol')]
                            price = row[('match', 'match_price')]
                            value = vol * price * 1000 * 20
                            
                            if value >= min_value:
                                # Find stock info
                                for s in stocks:
                                    if s['symbol'] == sym:
                                        s['price'] = price
                                        s['value'] = value
                                        s['change_1d'] = ((price - row[('listing', 'ref_price')]) / 
                                                        row[('listing', 'ref_price')] * 100)
                                        liquid.append(s)
                                        break
                        except:
                            pass
                print(f"✓ {len(liquid)}")
            except Exception as e:
                print(f"✗")
            
            time.sleep(0.3)
        
        return liquid
    
    def _analyze_stocks(self, stocks: List[Dict], vnindex_1m: float) -> List[StockAnalysis]:
        """Phân tích chi tiết các cổ phiếu"""
        result = []
        total = len(stocks)
        
        for i, s in enumerate(stocks):
            if i % 20 == 0:
                print(f"   Đang phân tích: {i}/{total}...", end="\r")
            
            try:
                analysis = self._analyze_single_stock(s, vnindex_1m)
                if analysis:
                    result.append(analysis)
            except:
                pass
            
            time.sleep(0.1)
        
        print(f"   Đang phân tích: {total}/{total} hoàn thành!")
        return result
    
    def _analyze_single_stock(self, stock_info: Dict, vnindex_1m: float) -> Optional[StockAnalysis]:
        """Phân tích chi tiết 1 cổ phiếu"""
        symbol = stock_info['symbol']
        
        analysis = StockAnalysis(
            symbol=symbol,
            name=stock_info.get('name', ''),
            sector=stock_info.get('sector', ''),
            icb_name=stock_info.get('icb', ''),
            price=stock_info.get('price', 0),
            change_1d=stock_info.get('change_1d', 0),
            avg_value_20d=stock_info.get('value', 0) / 1e9  # Convert to tỷ
        )
        
        # Lấy dữ liệu giá chi tiết
        try:
            stock = self.vnstock.stock(symbol=symbol, source=self.source)
            end = datetime.now().strftime('%Y-%m-%d')
            start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            
            df = stock.quote.history(start=start, end=end, interval='1D')
            
            if df is None or len(df) < 50:
                return None
            
            # Price & Change
            analysis.price = df['close'].iloc[-1]
            analysis.change_5d = (df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100 if len(df) >= 5 else 0
            analysis.change_1m = (df['close'].iloc[-1] - df['close'].iloc[-20]) / df['close'].iloc[-20] * 100 if len(df) >= 20 else 0
            
            # MA
            analysis.ma20 = df['close'].rolling(20).mean().iloc[-1]
            analysis.ma50 = df['close'].rolling(50).mean().iloc[-1]
            analysis.ma150 = df['close'].rolling(150).mean().iloc[-1] if len(df) >= 150 else 0
            analysis.ma200 = df['close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else 0
            
            # 52 week
            analysis.high_52w = df['high'].max()
            analysis.low_52w = df['low'].min()
            
            if analysis.high_52w > 0:
                analysis.pct_from_high = (analysis.high_52w - analysis.price) / analysis.high_52w
            if analysis.low_52w > 0:
                analysis.pct_from_low = (analysis.price - analysis.low_52w) / analysis.low_52w
            
            # RS
            analysis.rs_vs_vnindex = analysis.change_1m - vnindex_1m
            analysis.rs_rating = min(99, max(0, 70 + int(analysis.rs_vs_vnindex * 3)))
            
            # SEPA Stage với logic
            analysis.sepa_stage, sepa_notes = self._determine_sepa_stage(analysis)
            analysis.logic_notes.extend(sepa_notes)
            
            # Criteria check với logic
            analysis.criteria, criteria_notes = self._check_criteria(analysis)
            analysis.logic_notes.extend(criteria_notes)
            
            # Score
            analysis.score = self._calculate_score(analysis)
            
        except:
            return None
        
        return analysis
    
    def _determine_sepa_stage(self, stock: StockAnalysis) -> Tuple[str, List[str]]:
        """Xác định SEPA Stage với logic giải thích"""
        notes = []
        p = stock.price
        ma50 = stock.ma50
        ma150 = stock.ma150
        ma200 = stock.ma200
        
        if ma50 == 0 or ma150 == 0 or ma200 == 0:
            notes.append("⚠️ Thiếu dữ liệu MA → Không xác định Stage")
            return "N/A", notes
        
        # Check conditions
        price_above_ma50 = p > ma50
        price_above_ma150 = p > ma150
        price_above_ma200 = p > ma200
        ma50_above_ma150 = ma50 > ma150
        ma150_above_ma200 = ma150 > ma200
        
        notes.append(f"Giá: {p:,.0f}")
        notes.append(f"MA50: {ma50:,.0f} {'✓' if price_above_ma50 else '✗'}")
        notes.append(f"MA150: {ma150:,.0f} {'✓' if price_above_ma150 else '✗'}")
        notes.append(f"MA200: {ma200:,.0f} {'✓' if price_above_ma200 else '✗'}")
        
        # Stage 2: Uptrend
        if price_above_ma50 and price_above_ma150 and price_above_ma200 and ma50_above_ma150 and ma150_above_ma200:
            notes.append("→ Stage 2 (Uptrend): Giá > MA50 > MA150 > MA200")
            return "Stage 2", notes
        
        # Stage 4: Downtrend
        if not price_above_ma50 and not price_above_ma150 and not price_above_ma200:
            notes.append("→ Stage 4 (Downtrend): Giá < MA50 < MA150 < MA200")
            return "Stage 4", notes
        
        # Stage 1: Accumulation
        if ma50_above_ma150 and not ma150_above_ma200:
            notes.append("→ Stage 1 (Accumulation): MA50 > MA150, đang tích lũy")
            return "Stage 1", notes
        
        # Stage 3: Distribution
        if not ma50_above_ma150 and ma150_above_ma200:
            notes.append("→ Stage 3 (Distribution): MA50 < MA150, đang phân phối")
            return "Stage 3", notes
        
        notes.append("→ Transition: Đang chuyển giai đoạn")
        return "Transition", notes
    
    def _check_criteria(self, stock: StockAnalysis) -> Tuple[Dict[str, bool], List[str]]:
        """Kiểm tra tiêu chí với logic giải thích"""
        notes = []
        criteria = {}
        
        # 1. Thanh khoản
        criteria['liquidity'] = stock.avg_value_20d >= 0.5  # >500 tỷ/tháng = >25 tỷ/ngày
        notes.append(f"{'✓' if criteria['liquidity'] else '✗'} Thanh khoản: {stock.avg_value_20d:.1f} tỷ/phiên")
        
        # 2. SEPA Stage 2
        criteria['stage2'] = stock.sepa_stage == "Stage 2"
        notes.append(f"{'✓' if criteria['stage2'] else '✗'} SEPA: {stock.sepa_stage}")
        
        # 3. RS Rating > 70
        criteria['rs'] = stock.rs_rating >= 70
        notes.append(f"{'✓' if criteria['rs'] else '✗'} RS Rating: {stock.rs_rating}")
        
        # 4. Near 52w high (<25%)
        criteria['near_high'] = stock.pct_from_high <= 0.25
        notes.append(f"{'✓' if criteria['near_high'] else '✗'} vs 52wH: {stock.pct_from_high*100:.1f}%")
        
        return criteria, notes
    
    def _calculate_score(self, stock: StockAnalysis) -> int:
        """Tính điểm tổng hợp"""
        score = 50  # Base
        
        # Stage 2 bonus
        if stock.sepa_stage == "Stage 2":
            score += 25
        elif stock.sepa_stage == "Stage 1":
            score += 10
        
        # RS Rating bonus
        score += (stock.rs_rating - 50) // 5
        
        # Near high bonus
        if stock.pct_from_high <= 0.10:
            score += 15
        elif stock.pct_from_high <= 0.25:
            score += 5
        
        # Momentum bonus
        if stock.change_5d > 0 and stock.change_1m > 0:
            score += 5
        
        return min(100, max(0, score))


# ══════════════════════════════════════════════════════════════════════════════
# REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class ReportGenerator:
    """Tạo báo cáo chi tiết"""
    
    def __init__(self, config):
        self.config = config
        self.ai = self._init_ai()
    
    def _init_ai(self):
        ai_provider, ai_key = self.config.get_ai_provider()
        if not ai_key or AIProvider is None:
            return None
        try:
            return AIProvider(AIConfig(
                provider=ai_provider,
                api_key=ai_key,
                system_prompt="Bạn là chuyên gia phân tích chứng khoán CANSLIM."
            ))
        except:
            return None
    
    def generate_ai_summary(self, report: CombinedReport) -> str:
        """Tạo tóm tắt AI"""
        if not self.ai:
            return "⚠️ AI chưa cấu hình"
        
        # Build sector summary
        sector_summary = "\n".join([
            f"{s.rank}. {s.code} ({s.name}): RS={s.rs_vs_vnindex:+.2f}% | {s.phase.value}"
            for s in report.sectors
        ])
        
        # Build watchlist summary
        watchlist_summary = "\n".join([
            f"{s.rank}. {s.symbol} ({s.sector}): Score={s.score} | RS={s.rs_rating} | {s.sepa_stage}"
            for s in report.watchlist[:10]
        ])
        
        prompt = f"""
BÁO CÁO SECTOR ROTATION + STOCK SCREENING - {report.timestamp.strftime('%d/%m/%Y')}

═══════════════════════════════════════════════════════════════
VNIndex: {report.vnindex_price:,.0f} | 1D: {report.vnindex_change_1d:+.2f}% | 1M: {report.vnindex_change_1m:+.2f}%

SECTOR ROTATION:
{sector_summary}

🚀 Leading: {report.leading_sectors}
📈 Improving: {report.improving_sectors}

TOP 10 WATCHLIST:
{watchlist_summary}

═══════════════════════════════════════════════════════════════

Hãy phân tích:
1. Nhận định chung về rotation ngành
2. Top 3 cổ phiếu tiềm năng nhất và lý do
3. Chiến lược vào lệnh cụ thể
4. Cảnh báo rủi ro
"""
        
        try:
            return self.ai.chat(prompt)
        except Exception as e:
            return f"❌ {e}"
    
    def generate_markdown(self, report: CombinedReport) -> str:
        """Tạo báo cáo Markdown chi tiết"""
        
        # Header
        content = f"""# 📊 BÁO CÁO SECTOR ROTATION + STOCK SCREENING
**Ngày:** {report.timestamp.strftime('%d/%m/%Y %H:%M')}

---

## 📌 BƯỚC 1: VNINDEX BASELINE

| Chỉ số | Giá trị | Ý nghĩa |
|--------|---------|---------|
| VNIndex | {report.vnindex_price:,.0f} | Điểm hiện tại |
| Thay đổi 1D | {report.vnindex_change_1d:+.2f}% | Biến động trong ngày |
| Thay đổi 1M | {report.vnindex_change_1m:+.2f}% | **Benchmark để tính RS** |

**Logic:** RS (Relative Strength) = Performance ngành/cổ phiếu - Performance VNIndex

---

## 📌 BƯỚC 2: PHÂN TÍCH 7 NGÀNH

| Rank | Code | Tên | 1D | 1M | RS vs VNI | Phase |
|------|------|-----|----|----|-----------|-------|
"""
        
        # Sector table
        for s in report.sectors:
            content += f"| {s.rank} | {s.code} | {s.name} | {s.change_1d:+.2f}% | {s.change_1m:+.2f}% | {s.rs_vs_vnindex:+.2f}% | {s.phase.value} |\n"
        
        # Logic giải thích phase
        content += """
### Logic xác định Phase:

| Phase | Điều kiện |
|-------|-----------|
| 🚀 Leading | RS > +3% VÀ momentum 5D > 0 |
| 📈 Improving | RS > 0% VÀ đang tăng tốc (5D > 1D) |
| 📉 Weakening | RS > 0% NHƯNG đang giảm tốc |
| ⛔ Lagging | RS < 0% |

"""
        
        # Sector detail
        content += "### Chi tiết logic từng ngành:\n\n"
        for s in report.sectors:
            content += f"**{s.code} ({s.name}):**\n"
            for note in s.logic_notes:
                content += f"- {note}\n"
            content += "\n"
        
        # Bước 3
        content += f"""---

## 📌 BƯỚC 3: XÁC ĐỊNH NGÀNH MỤC TIÊU

| Loại | Ngành |
|------|-------|
| 🚀 Leading | {', '.join(report.leading_sectors) or 'Không có'} |
| 📈 Improving | {', '.join(report.improving_sectors) or 'Không có'} |
| ⛔ Không đầu tư | {', '.join(report.lagging_sectors) or 'Không có'} |

**Quyết định:** Chỉ lọc cổ phiếu trong ngành **Leading + Improving**

---

## 📌 BƯỚC 4-5: LỌC CỔ PHIẾU

| Metric | Giá trị |
|--------|---------|
| Cổ phiếu trong ngành mục tiêu | {report.total_stocks_in_target} |
| Qua thanh khoản (>10 tỷ/phiên) | {report.pass_liquidity} |
| **API calls tiết kiệm** | ~{report.api_calls_saved} |

---

## 📌 BƯỚC 6: WATCHLIST CHI TIẾT

### Tiêu chí CANSLIM & SEPA:

| Tiêu chí | Điều kiện | Ý nghĩa |
|----------|-----------|---------|
| Thanh khoản | > 10 tỷ/phiên | Đủ thanh khoản để giao dịch |
| SEPA Stage | Stage 2 | Uptrend (Giá > MA50 > MA150 > MA200) |
| RS Rating | > 70 | Outperform 70% thị trường |
| Near 52wH | < 25% | Gần đỉnh = không có kháng cự |

### TOP {len(report.watchlist)} CỔ PHIẾU:

| # | Mã | Ngành | Giá | Score | RS | Stage | vs52wH | Criteria |
|---|-----|-------|-----|-------|----|----|--------|----------|
"""
        
        # Watchlist table
        for s in report.watchlist:
            criteria_str = f"{sum(s.criteria.values())}/{len(s.criteria)}"
            content += f"| {s.rank} | {s.symbol} | {s.sector} | {s.price:,.0f} | {s.score} | {s.rs_rating} | {s.sepa_stage} | {s.pct_from_high*100:.1f}% | {criteria_str} |\n"
        
        # Chi tiết từng mã
        content += "\n### Chi tiết logic từng cổ phiếu:\n\n"
        
        for s in report.watchlist[:10]:  # Top 10 chi tiết
            content += f"""
#### {s.rank}. {s.symbol} ({s.name[:30]}...)

**Sector:** {s.sector} ({s.icb_name})

**Dữ liệu:**
| Metric | Giá trị |
|--------|---------|
| Giá | {s.price:,.0f} |
| Thay đổi 1D | {s.change_1d:+.2f}% |
| Thay đổi 5D | {s.change_5d:+.2f}% |
| Thay đổi 1M | {s.change_1m:+.2f}% |
| MA20 | {s.ma20:,.0f} |
| MA50 | {s.ma50:,.0f} |
| MA150 | {s.ma150:,.0f} |
| MA200 | {s.ma200:,.0f} |
| 52w High | {s.high_52w:,.0f} |
| vs 52wH | {s.pct_from_high*100:.1f}% |
| RS vs VNI | {s.rs_vs_vnindex:+.2f}% |
| RS Rating | {s.rs_rating} |
| GTGD TB | {s.avg_value_20d:.1f} tỷ/phiên |

**Logic phân tích:**
"""
            for note in s.logic_notes:
                content += f"- {note}\n"
            
            content += f"\n**Kết luận:** Score = {s.score}/100\n"
        
        # AI Analysis
        content += f"""
---

## 🤖 AI ANALYSIS

{report.ai_analysis}

---

## 📋 TÓM TẮT

- **Ngành mạnh:** {', '.join(report.leading_sectors + report.improving_sectors)}
- **Watchlist:** {', '.join([s.symbol for s in report.watchlist[:10]])}
- **API tiết kiệm:** ~{report.api_calls_saved} calls

**Lưu ý:** Đây chỉ là công cụ sàng lọc. Cần phân tích chi tiết trước khi đầu tư.
"""
        
        return content
    
    def save_report(self, report: CombinedReport, content: str):
        """Lưu báo cáo"""
        output_dir = self.config.output.OUTPUT_DIR
        os.makedirs(output_dir, exist_ok=True)
        
        filename = os.path.join(
            output_dir,
            f"sector_stock_combined_{report.timestamp.strftime('%Y%m%d_%H%M')}.md"
        )
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✓ Đã lưu báo cáo: {filename}")
        
        # CSV
        csv_file = os.path.join(output_dir, "watchlist_combined.csv")
        df = pd.DataFrame([{
            'rank': s.rank,
            'symbol': s.symbol,
            'sector': s.sector,
            'price': s.price,
            'change_1d': s.change_1d,
            'change_1m': s.change_1m,
            'rs_rating': s.rs_rating,
            'sepa_stage': s.sepa_stage,
            'pct_from_high': s.pct_from_high,
            'score': s.score
        } for s in report.watchlist])
        df.to_csv(csv_file, index=False)
        print(f"✓ Đã lưu CSV: {csv_file}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

class Module2CombinedRunner:
    """Runner cho Module 2 Combined"""
    
    def __init__(self):
        self.config = get_config()
        self.analyzer = CombinedAnalyzer()
        self.reporter = ReportGenerator(self.config)
    
    def run(self):
        print("""
╔══════════════════════════════════════════════════════════════╗
║     MODULE 2 COMBINED                                         ║
║     Sector Rotation + Stock Screening                         ║
║     Báo cáo chi tiết với logic từng bước                     ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # Analyze
        report = self.analyzer.analyze()
        
        # AI Summary
        print("\n" + "─"*60)
        print("📌 BƯỚC 7: AI ANALYSIS")
        print("─"*60)
        report.ai_analysis = self.reporter.generate_ai_summary(report)
        
        # Generate & Print
        content = self.reporter.generate_markdown(report)
        print("\n" + content[:3000] + "\n...(xem file đầy đủ)")
        
        # Save
        self.reporter.save_report(report, content)
        
        return report


if __name__ == "__main__":
    runner = Module2CombinedRunner()
    report = runner.run()