#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     STOCK SCREENER OPTIMIZED - LỌC CỔ PHIẾU TRONG NGÀNH MẠNH               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Workflow tối ưu:                                                            ║
║  1. Đọc output từ Module 2 (sector_rotation) → ngành mạnh                   ║
║  2. Chỉ lọc cổ phiếu TRONG các ngành mạnh (Leading/Improving)               ║
║  3. Áp dụng tiêu chí CANSLIM & SEPA                                         ║
║                                                                              ║
║  Tiết kiệm: ~500 API calls → ~50-100 API calls                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

from config import get_config


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR → ICB MAPPING
# ══════════════════════════════════════════════════════════════════════════════

# Mapping giữa Sector Index và ICB_NAME2 (level 2)
SECTOR_TO_ICB = {
    'VNFIN': ['Ngân hàng', 'Dịch vụ tài chính', 'Bảo hiểm'],
    'VNREAL': ['Bất động sản'],
    'VNMAT': ['Xây dựng và Vật liệu', 'Tài nguyên Cơ bản', 'Hóa chất'],
    'VNIT': ['Công nghệ Thông tin', 'Viễn thông'],
    'VNHEAL': ['Y tế'],
    'VNCOND': ['Bán lẻ', 'Du lịch và Giải trí', 'Ô tô và phụ tùng', 'Hàng cá nhân & Gia dụng'],
    'VNCONS': ['Thực phẩm và đồ uống'],
}

# Reverse mapping: ICB → Sector
ICB_TO_SECTOR = {}
for sector, icbs in SECTOR_TO_ICB.items():
    for icb in icbs:
        ICB_TO_SECTOR[icb] = sector


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScreenerConfig:
    DATA_SOURCE: str = "VCI"
    API_DELAY: float = 0.3
    
    # Tiêu chí
    MIN_LIQUIDITY: float = 10_000_000_000
    MIN_RS_RATING: int = 70
    MAX_FROM_52W_HIGH: float = 0.25
    
    # Output
    TOP_N: int = 20
    OUTPUT_DIR: str = "./output"
    
    AI_PROVIDER: str = ""
    AI_API_KEY: str = ""


def create_config() -> ScreenerConfig:
    unified = get_config()
    config = ScreenerConfig()
    config.DATA_SOURCE = unified.get_data_source()
    config.OUTPUT_DIR = unified.output.OUTPUT_DIR
    ai_provider, ai_key = unified.get_ai_provider()
    config.AI_PROVIDER = ai_provider
    config.AI_API_KEY = ai_key
    return config


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class StockCandidate:
    symbol: str
    name: str = ""
    sector: str = ""
    icb_name: str = ""
    
    price: float = 0.0
    change_1d: float = 0.0
    change_1m: float = 0.0
    
    ma50: float = 0.0
    ma150: float = 0.0
    ma200: float = 0.0
    
    sepa_stage: str = "N/A"
    rs_rating: int = 0
    
    high_52w: float = 0.0
    pct_from_high: float = 0.0
    
    avg_value_20d: float = 0.0
    
    overall_score: int = 0
    criteria_passed: int = 0


@dataclass
class OptimizedScreenerReport:
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Stats
    leading_sectors: List[str] = field(default_factory=list)
    improving_sectors: List[str] = field(default_factory=list)
    stocks_in_sectors: int = 0
    pass_liquidity: int = 0
    final_count: int = 0
    
    # Results
    watchlist: List[StockCandidate] = field(default_factory=list)
    
    # Savings
    api_calls_saved: int = 0
    
    ai_analysis: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# OPTIMIZED SCREENER
# ══════════════════════════════════════════════════════════════════════════════

class OptimizedStockScreener:
    """Stock Screener tối ưu - chỉ lọc trong ngành mạnh"""
    
    def __init__(self, config: ScreenerConfig):
        self.config = config
        self._init_vnstock()
    
    def _init_vnstock(self):
        try:
            from vnstock import Vnstock, Listing
            self.listing = Listing()
            self.vnstock = Vnstock()
            print("✓ Kết nối vnstock thành công")
        except Exception as e:
            print(f"❌ Lỗi: {e}")
    
    def screen(self, leading_sectors: List[str] = None, improving_sectors: List[str] = None) -> OptimizedScreenerReport:
        """Thực hiện sàng lọc trong ngành mạnh"""
        print("\n" + "="*70)
        print("📊 OPTIMIZED STOCK SCREENER - CHỈ LỌC TRONG NGÀNH MẠNH")
        print("="*70)
        
        report = OptimizedScreenerReport()
        
        # 1. Xác định ngành cần lọc
        if not leading_sectors and not improving_sectors:
            # Đọc từ file sector_rotation output
            leading_sectors, improving_sectors = self._read_sector_rotation_output()
        
        report.leading_sectors = leading_sectors or []
        report.improving_sectors = improving_sectors or []
        
        target_sectors = report.leading_sectors + report.improving_sectors
        print(f"\n[1/5] Ngành mục tiêu: {target_sectors}")
        
        if not target_sectors:
            print("   ⚠️ Không có ngành mạnh, dùng default: VNFIN, VNREAL")
            target_sectors = ['VNFIN', 'VNREAL']
        
        # 2. Lấy cổ phiếu trong các ngành mạnh
        print("\n[2/5] Lấy danh sách cổ phiếu trong ngành mạnh...")
        sector_stocks = self._get_stocks_in_sectors(target_sectors)
        report.stocks_in_sectors = len(sector_stocks)
        report.api_calls_saved = 500 - len(sector_stocks)  # Ước tính
        print(f"   ✓ Có {report.stocks_in_sectors} mã (tiết kiệm ~{report.api_calls_saved} API calls)")
        
        # 3. Lấy VNIndex baseline
        print("\n[3/5] Lấy VNIndex baseline...")
        vnindex_change = self._get_vnindex_change()
        print(f"   ✓ VNIndex 1M: {vnindex_change:+.2f}%")
        
        # 4. Lọc thanh khoản qua price_board
        print("\n[4/5] Lọc thanh khoản...")
        liquid_stocks = self._filter_by_liquidity(sector_stocks)
        report.pass_liquidity = len(liquid_stocks)
        print(f"   ✓ {report.pass_liquidity} mã qua thanh khoản")
        
        # 5. Phân tích chi tiết
        print("\n[5/5] Phân tích SEPA & scoring...")
        candidates = self._analyze_stocks(liquid_stocks, vnindex_change)
        
        # Sort và lấy top
        candidates.sort(key=lambda x: x.overall_score, reverse=True)
        report.watchlist = candidates[:self.config.TOP_N]
        report.final_count = len(report.watchlist)
        
        print(f"\n✓ KẾT QUẢ: {report.final_count} mã trong watchlist")
        
        return report
    
    def _read_sector_rotation_output(self) -> tuple:
        """Đọc output từ Module 2"""
        leading = []
        improving = []
        
        # Tìm file mới nhất
        output_dir = self.config.OUTPUT_DIR
        files = [f for f in os.listdir(output_dir) if f.startswith('sector_rotation_')]
        
        if files:
            files.sort(reverse=True)
            latest = os.path.join(output_dir, files[0])
            
            with open(latest, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # Parse Leading
                if '🚀 Leading:' in content:
                    line = [l for l in content.split('\n') if '🚀 Leading:' in l][0]
                    sectors = line.split(':')[1].strip()
                    for s in sectors.split(','):
                        s = s.strip()
                        for code, name in [('VNFIN', 'Tài chính'), ('VNREAL', 'Bất động sản'),
                                          ('VNMAT', 'Nguyên vật liệu'), ('VNIT', 'Công nghệ'),
                                          ('VNHEAL', 'Y tế'), ('VNCOND', 'Tiêu dùng không'), 
                                          ('VNCONS', 'Tiêu dùng thiết')]:
                            if name in s:
                                leading.append(code)
                
                # Parse Improving
                if '📈 Improving:' in content:
                    line = [l for l in content.split('\n') if '📈 Improving:' in l][0]
                    sectors = line.split(':')[1].strip()
                    for s in sectors.split(','):
                        s = s.strip()
                        for code, name in [('VNFIN', 'Tài chính'), ('VNREAL', 'Bất động sản'),
                                          ('VNMAT', 'Nguyên vật liệu'), ('VNIT', 'Công nghệ'),
                                          ('VNHEAL', 'Y tế'), ('VNCOND', 'Tiêu dùng không'), 
                                          ('VNCONS', 'Tiêu dùng thiết')]:
                            if name in s:
                                improving.append(code)
        
        print(f"   📁 Đọc từ sector_rotation: Leading={leading}, Improving={improving}")
        return leading, improving
    
    def _get_stocks_in_sectors(self, sectors: List[str]) -> List[StockCandidate]:
        """Lấy cổ phiếu trong các ngành mục tiêu"""
        stocks = []
        
        try:
            all_stocks = self.listing.symbols_by_industries()
            
            # Map sector → ICB names
            target_icbs = []
            for sector in sectors:
                if sector in SECTOR_TO_ICB:
                    target_icbs.extend(SECTOR_TO_ICB[sector])
            
            # Filter
            for _, row in all_stocks.iterrows():
                icb_name = row.get('icb_name2', '')
                
                if icb_name in target_icbs:
                    symbol = row['symbol']
                    if len(symbol) == 3:  # Chỉ lấy mã 3 ký tự
                        stock = StockCandidate(
                            symbol=symbol,
                            name=row.get('organ_name', ''),
                            sector=ICB_TO_SECTOR.get(icb_name, ''),
                            icb_name=icb_name
                        )
                        stocks.append(stock)
            
        except Exception as e:
            print(f"   ⚠️ Lỗi: {e}")
        
        return stocks
    
    def _get_vnindex_change(self) -> float:
        try:
            stock = self.vnstock.stock(symbol="VNINDEX", source=self.config.DATA_SOURCE)
            end = datetime.now().strftime('%Y-%m-%d')
            start = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            df = stock.quote.history(start=start, end=end, interval='1D')
            if df is not None and len(df) >= 20:
                return (df['close'].iloc[-1] - df['close'].iloc[-20]) / df['close'].iloc[-20] * 100
        except:
            pass
        return 0.0
    
    def _filter_by_liquidity(self, stocks: List[StockCandidate]) -> List[StockCandidate]:
        """Lọc theo thanh khoản"""
        liquid = []
        symbols = [s.symbol for s in stocks]
        
        # Batch processing
        batch_size = 50
        for i in range(0, len(symbols), batch_size):
            batch = symbols[i:i+batch_size]
            print(f"   Batch {i//batch_size + 1}...", end=" ")
            
            try:
                stock = self.vnstock.stock(symbol=batch[0], source=self.config.DATA_SOURCE)
                df = stock.trading.price_board(symbols_list=batch)
                
                if df is not None:
                    for _, row in df.iterrows():
                        try:
                            sym = row[('listing', 'symbol')]
                            vol = row[('match', 'match_vol')]
                            price = row[('match', 'match_price')]
                            value = vol * price * 1000 * 20
                            
                            if value >= self.config.MIN_LIQUIDITY:
                                # Find and update stock
                                for s in stocks:
                                    if s.symbol == sym:
                                        s.price = price
                                        s.avg_value_20d = value
                                        s.change_1d = ((price - row[('listing', 'ref_price')]) / 
                                                      row[('listing', 'ref_price')] * 100)
                                        liquid.append(s)
                                        break
                        except:
                            pass
                print(f"✓ {len(liquid)}")
            except Exception as e:
                print(f"✗ {e}")
            
            time.sleep(self.config.API_DELAY)
        
        return liquid
    
    def _analyze_stocks(self, stocks: List[StockCandidate], vnindex_change: float) -> List[StockCandidate]:
        """Phân tích chi tiết"""
        result = []
        total = len(stocks)
        
        for i, stock in enumerate(stocks):
            if i % 10 == 0:
                print(f"   Phân tích: {i}/{total}...", end="\r")
            
            try:
                data = self._get_stock_data(stock.symbol)
                if data:
                    stock.ma50 = data.get('ma50', 0)
                    stock.ma150 = data.get('ma150', 0)
                    stock.ma200 = data.get('ma200', 0)
                    stock.high_52w = data.get('high_52w', stock.price)
                    stock.change_1m = data.get('change_1m', 0)
                    
                    current = data.get('current_price', stock.price)
                    if current > 0:
                        stock.price = current
                    
                    if stock.high_52w > 0 and stock.price > 0:
                        stock.pct_from_high = max(0, min(1, (stock.high_52w - stock.price) / stock.high_52w))
                    
                    stock.sepa_stage = self._get_sepa_stage(stock)
                    
                    rs_diff = stock.change_1m - vnindex_change
                    stock.rs_rating = min(99, max(0, 70 + int(rs_diff * 3)))
                    
                    stock.criteria_passed = sum([
                        stock.avg_value_20d >= self.config.MIN_LIQUIDITY,
                        stock.sepa_stage == "Stage 2",
                        stock.rs_rating >= self.config.MIN_RS_RATING,
                        stock.pct_from_high <= self.config.MAX_FROM_52W_HIGH,
                    ])
                    
                    stock.overall_score = self._calc_score(stock)
                    result.append(stock)
            except:
                pass
            
            time.sleep(self.config.API_DELAY * 0.2)
        
        print(f"   Phân tích: {total}/{total} hoàn thành!")
        return result
    
    def _get_stock_data(self, symbol: str) -> Optional[Dict]:
        try:
            stock = self.vnstock.stock(symbol=symbol, source=self.config.DATA_SOURCE)
            end = datetime.now().strftime('%Y-%m-%d')
            start = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
            df = stock.quote.history(start=start, end=end, interval='1D')
            
            if df is None or len(df) < 50:
                return None
            
            current = df['close'].iloc[-1]
            high_52w = df['high'].max()
            
            if high_52w <= 0 or high_52w < current * 0.5:
                high_52w = current * 1.1
            
            return {
                'ma50': df['close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else 0,
                'ma150': df['close'].rolling(150).mean().iloc[-1] if len(df) >= 150 else 0,
                'ma200': df['close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else 0,
                'high_52w': high_52w,
                'current_price': current,
                'change_1m': (current - df['close'].iloc[-20]) / df['close'].iloc[-20] * 100 if len(df) >= 20 else 0
            }
        except:
            return None
    
    def _get_sepa_stage(self, stock: StockCandidate) -> str:
        p, ma50, ma150, ma200 = stock.price, stock.ma50, stock.ma150, stock.ma200
        
        if ma50 == 0 or ma150 == 0 or ma200 == 0:
            return "N/A"
        
        if p > ma50 > ma150 > ma200:
            return "Stage 2"
        elif p < ma50 < ma150 < ma200:
            return "Stage 4"
        elif ma50 > ma200:
            return "Stage 1"
        else:
            return "Stage 3"
    
    def _calc_score(self, stock: StockCandidate) -> int:
        score = 50
        if stock.sepa_stage == "Stage 2":
            score += 25
        score += (stock.rs_rating - 50) // 5
        if stock.pct_from_high <= 0.10:
            score += 15
        elif stock.pct_from_high <= 0.25:
            score += 5
        return min(100, max(0, score))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

class OptimizedScreenerModule:
    def __init__(self):
        self.config = create_config()
        self.screener = OptimizedStockScreener(self.config)
        self.report = None
    
    def run(self, leading_sectors: List[str] = None, improving_sectors: List[str] = None) -> OptimizedScreenerReport:
        print("""
╔══════════════════════════════════════════════════════════════╗
║     OPTIMIZED STOCK SCREENER                                  ║
║     Chỉ lọc trong ngành mạnh → Tiết kiệm API calls           ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        self.report = self.screener.screen(leading_sectors, improving_sectors)
        self._print_report()
        self._save_report()
        
        return self.report
    
    def _print_report(self):
        print("\n" + "="*70)
        print("📊 WATCHLIST - CỔ PHIẾU TRONG NGÀNH MẠNH")
        print("="*70)
        
        print(f"\n🏭 Leading: {', '.join(self.report.leading_sectors)}")
        print(f"📈 Improving: {', '.join(self.report.improving_sectors)}")
        print(f"📉 Tiết kiệm API: ~{self.report.api_calls_saved} calls")
        
        print(f"\n{'#':<3} {'MÃ':<6} {'SECTOR':<8} {'SCORE':<6} {'RS':<4} {'STAGE':<10} {'vs52wH':<8}")
        print("-"*55)
        
        for i, s in enumerate(self.report.watchlist, 1):
            print(f"{i:<3} {s.symbol:<6} {s.sector:<8} {s.overall_score:<6} {s.rs_rating:<4} "
                  f"{s.sepa_stage:<10} {s.pct_from_high*100:>6.1f}%")
    
    def _save_report(self):
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        
        filename = os.path.join(
            self.config.OUTPUT_DIR,
            f"watchlist_optimized_{self.report.timestamp.strftime('%Y%m%d_%H%M')}.md"
        )
        
        rows = "\n".join([
            f"| {i+1} | {s.symbol} | {s.sector} | {s.overall_score} | {s.rs_rating} | {s.sepa_stage} | {s.pct_from_high*100:.1f}% |"
            for i, s in enumerate(self.report.watchlist)
        ])
        
        content = f"""# WATCHLIST TỐI ƯU - CỔ PHIẾU TRONG NGÀNH MẠNH
**Ngày:** {self.report.timestamp.strftime('%d/%m/%Y %H:%M')}

## NGÀNH MỤC TIÊU
- 🚀 Leading: {', '.join(self.report.leading_sectors)}
- 📈 Improving: {', '.join(self.report.improving_sectors)}

## THỐNG KÊ
- Cổ phiếu trong ngành: {self.report.stocks_in_sectors}
- Qua thanh khoản: {self.report.pass_liquidity}
- Watchlist cuối: {self.report.final_count}
- **API calls tiết kiệm: ~{self.report.api_calls_saved}**

## TOP {len(self.report.watchlist)} CỔ PHIẾU

| # | Mã | Sector | Score | RS | Stage | vs52wH |
|---|-----|--------|-------|----|----|--------|
{rows}
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\n✓ Đã lưu: {filename}")
        
        # CSV
        csv_file = os.path.join(self.config.OUTPUT_DIR, "watchlist_optimized.csv")
        df = pd.DataFrame([{
            'symbol': s.symbol,
            'sector': s.sector,
            'score': s.overall_score,
            'rs_rating': s.rs_rating,
            'sepa_stage': s.sepa_stage,
            'pct_from_high': s.pct_from_high
        } for s in self.report.watchlist])
        df.to_csv(csv_file, index=False)
        print(f"✓ Đã lưu CSV: {csv_file}")


if __name__ == "__main__":
    module = OptimizedScreenerModule()
    report = module.run()