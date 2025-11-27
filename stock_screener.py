#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     MODULE 2.5: STOCK SCREENER - LỌC CỔ PHIẾU CANSLIM & SEPA                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Mục tiêu: Từ ~1600 mã → Lọc ra Top 20 "Siêu cổ phiếu" tiềm năng            ║
║                                                                              ║
║  Tiêu chí lọc (CANSLIM + SEPA):                                             ║
║  1. Thanh khoản: GTGD TB 20 phiên > 10 tỷ                                   ║
║  2. Trend (SEPA): Giá > MA50 > MA150 > MA200                                ║
║  3. RS Rating: RS vs VNIndex > 70                                            ║
║  4. Định giá: Giá trong vùng 25% từ đỉnh 52 tuần                            ║
║  5. C (Current Earnings): EPS quý gần nhất tăng > 15% YoY                   ║
║  6. A (Annual): ROE > 15%                                                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import time
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# Import từ config chung
from config import get_config, UnifiedConfig

# Import AI Provider
try:
    from ai_providers import AIProvider, AIConfig
except ImportError:
    AIProvider = None


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ScreenerConfig:
    """Config cho Stock Screener"""
    
    # API
    DATA_SOURCE: str = "VCI"
    API_DELAY: float = 0.3
    
    # Tiêu chí lọc
    MIN_LIQUIDITY: float = 10_000_000_000  # 10 tỷ VNĐ/phiên
    MIN_RS_RATING: int = 70                 # RS Rating > 70
    MAX_FROM_52W_HIGH: float = 0.25         # Trong vùng 25% từ đỉnh 52 tuần
    MIN_EPS_GROWTH: float = 0.15            # EPS tăng > 15% YoY
    MIN_ROE: float = 0.15                   # ROE > 15%
    
    # Lookback
    LOOKBACK_DAYS: int = 365
    
    # Output
    TOP_N: int = 20
    OUTPUT_DIR: str = "./output"
    SAVE_REPORT: bool = True
    
    # AI
    AI_PROVIDER: str = ""
    AI_API_KEY: str = ""


def create_config_from_unified() -> ScreenerConfig:
    """Tạo ScreenerConfig từ UnifiedConfig"""
    unified = get_config()
    
    config = ScreenerConfig()
    config.DATA_SOURCE = unified.get_data_source()
    config.API_DELAY = unified.rate_limit.API_DELAY
    config.OUTPUT_DIR = unified.output.OUTPUT_DIR
    config.SAVE_REPORT = unified.output.SAVE_REPORTS
    
    ai_provider, ai_key = unified.get_ai_provider()
    config.AI_PROVIDER = ai_provider
    config.AI_API_KEY = ai_key
    
    return config


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class StockCandidate:
    """Ứng viên cổ phiếu qua sàng lọc"""
    symbol: str
    name: str = ""
    sector: str = ""
    
    # Price data
    price: float = 0.0
    change_1d: float = 0.0
    change_1m: float = 0.0
    
    # MA data
    ma50: float = 0.0
    ma150: float = 0.0
    ma200: float = 0.0
    
    # SEPA Stage
    sepa_stage: str = "N/A"
    trend_score: int = 0  # 0-100
    
    # RS Rating
    rs_rating: int = 0  # 0-99
    rs_vs_vnindex: float = 0.0
    
    # 52 week
    high_52w: float = 0.0
    low_52w: float = 0.0
    pct_from_high: float = 0.0
    
    # Liquidity
    avg_volume_20d: float = 0.0
    avg_value_20d: float = 0.0  # VNĐ
    
    # Fundamentals
    eps_growth_yoy: float = 0.0
    roe: float = 0.0
    pe: float = 0.0
    market_cap: float = 0.0  # tỷ VNĐ
    
    # Scoring
    canslim_score: int = 0  # 0-100
    overall_score: int = 0  # 0-100
    
    # Pass criteria
    pass_liquidity: bool = False
    pass_trend: bool = False
    pass_rs: bool = False
    pass_near_high: bool = False
    pass_eps: bool = False
    pass_roe: bool = False
    
    @property
    def criteria_passed(self) -> int:
        """Số tiêu chí đạt"""
        return sum([
            self.pass_liquidity,
            self.pass_trend,
            self.pass_rs,
            self.pass_near_high,
            self.pass_eps,
            self.pass_roe
        ])


@dataclass 
class ScreenerReport:
    """Báo cáo Stock Screener"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Stats
    total_stocks: int = 0
    pass_liquidity: int = 0
    pass_trend: int = 0
    pass_all: int = 0
    
    # VNIndex reference
    vnindex_change_1m: float = 0.0
    
    # Results
    watchlist: List[StockCandidate] = field(default_factory=list)
    
    # By sector
    sector_distribution: Dict[str, int] = field(default_factory=dict)
    
    # AI
    ai_analysis: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# STOCK SCREENER
# ══════════════════════════════════════════════════════════════════════════════

class StockScreener:
    """Sàng lọc cổ phiếu theo CANSLIM & SEPA"""
    
    def __init__(self, config: ScreenerConfig):
        self.config = config
        self.stock = None
        self.listing = None
        self._init_vnstock()
    
    def _init_vnstock(self):
        """Khởi tạo vnstock"""
        try:
            from vnstock import Vnstock, Listing
            self.listing = Listing()
            self.stock = Vnstock().stock(symbol="VNM", source=self.config.DATA_SOURCE)
            print("✓ Kết nối vnstock thành công")
        except Exception as e:
            print(f"❌ Lỗi vnstock: {e}")
    
    def screen(self) -> ScreenerReport:
        """Thực hiện sàng lọc"""
        print("\n" + "="*70)
        print("📊 MODULE 2.5: STOCK SCREENER - CANSLIM & SEPA")
        print("="*70)
        
        report = ScreenerReport()
        
        # 1. Lấy danh sách cổ phiếu
        print("\n[1/5] Lấy danh sách cổ phiếu...")
        all_stocks = self._get_all_stocks()
        report.total_stocks = len(all_stocks)
        print(f"   ✓ Tổng: {report.total_stocks} mã")
        
        # 2. Lấy VNIndex reference
        print("\n[2/5] Lấy VNIndex baseline...")
        report.vnindex_change_1m = self._get_vnindex_change()
        print(f"   ✓ VNIndex 1M: {report.vnindex_change_1m:+.2f}%")
        
        # 3. Lọc sơ bộ theo thanh khoản
        print("\n[3/5] Lọc theo thanh khoản...")
        liquid_stocks = self._filter_by_liquidity(all_stocks)
        report.pass_liquidity = len(liquid_stocks)
        print(f"   ✓ Qua thanh khoản: {report.pass_liquidity} mã")
        
        # 4. Phân tích chi tiết
        print("\n[4/5] Phân tích CANSLIM & SEPA...")
        candidates = self._analyze_stocks(liquid_stocks, report.vnindex_change_1m)
        
        # 5. Lọc theo tiêu chí
        print("\n[5/5] Áp dụng tiêu chí lọc...")
        report.watchlist = self._apply_criteria(candidates)
        report.pass_all = len(report.watchlist)
        
        # Sector distribution
        for stock in report.watchlist:
            sector = stock.sector or "Khác"
            report.sector_distribution[sector] = report.sector_distribution.get(sector, 0) + 1
        
        print(f"\n✓ KẾT QUẢ: {report.pass_all} mã đạt tiêu chí")
        
        return report
    
    def _get_all_stocks(self) -> List[str]:
        """Lấy danh sách tất cả cổ phiếu"""
        try:
            df = self.listing.all_symbols()
            # Lọc mã 3 ký tự (loại trừ ETF, covered warrant, etc.)
            stocks = df[df['symbol'].str.len() == 3]['symbol'].tolist()
            return stocks
        except Exception as e:
            print(f"   ⚠️ Lỗi: {e}")
            return []
    
    def _get_vnindex_change(self) -> float:
        """Lấy % thay đổi 1 tháng của VNIndex"""
        try:
            from vnstock import Vnstock
            stock = Vnstock().stock(symbol="VNINDEX", source=self.config.DATA_SOURCE)
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d')
            
            df = stock.quote.history(start=start_date, end=end_date, interval='1D')
            
            if df is not None and len(df) >= 20:
                current = df['close'].iloc[-1]
                month_ago = df['close'].iloc[-20]
                return (current - month_ago) / month_ago * 100
        except:
            pass
        return 0.0
    
    def _filter_by_liquidity(self, stocks: List[str]) -> List[str]:
        """Lọc theo thanh khoản"""
        liquid_stocks = []
        
        # Lấy mẫu để test nhanh
        batch_size = 50
        stocks_to_check = stocks[:500]  # Giới hạn để test
        
        for i in range(0, len(stocks_to_check), batch_size):
            batch = stocks_to_check[i:i+batch_size]
            print(f"   Checking batch {i//batch_size + 1}...", end=" ")
            
            try:
                from vnstock import Vnstock
                stock = Vnstock().stock(symbol=batch[0], source=self.config.DATA_SOURCE)
                df = stock.trading.price_board(symbols_list=batch)
                
                if df is not None:
                    for _, row in df.iterrows():
                        try:
                            symbol = row[('listing', 'symbol')]
                            match_vol = row[('match', 'match_vol')]
                            match_price = row[('match', 'match_price')]
                            
                            value = match_vol * match_price * 1000  # VNĐ
                            
                            # Ước tính GTGD 20 phiên = giá trị hôm nay * 20
                            if value * 20 >= self.config.MIN_LIQUIDITY:
                                liquid_stocks.append(symbol)
                        except:
                            pass
                    
                print(f"✓ Found {len(liquid_stocks)}")
            except Exception as e:
                print(f"✗ {e}")
            
            time.sleep(self.config.API_DELAY)
        
        return list(set(liquid_stocks))
    
    def _analyze_stocks(self, stocks: List[str], vnindex_change: float) -> List[StockCandidate]:
        """Phân tích chi tiết từng cổ phiếu"""
        candidates = []
        
        total = len(stocks)
        for i, symbol in enumerate(stocks):
            print(f"   [{i+1}/{total}] {symbol}...", end=" ")
            
            try:
                candidate = self._analyze_single_stock(symbol, vnindex_change)
                if candidate:
                    candidates.append(candidate)
                    print(f"✓ Score={candidate.overall_score}")
                else:
                    print("✗")
            except Exception as e:
                print(f"✗ {e}")
            
            time.sleep(self.config.API_DELAY * 0.5)
        
        return candidates
    
    def _analyze_single_stock(self, symbol: str, vnindex_change: float) -> Optional[StockCandidate]:
        """Phân tích 1 cổ phiếu"""
        from vnstock import Vnstock
        
        candidate = StockCandidate(symbol=symbol)
        
        # 1. Lấy dữ liệu giá
        try:
            stock = Vnstock().stock(symbol=symbol, source=self.config.DATA_SOURCE)
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=self.config.LOOKBACK_DAYS)).strftime('%Y-%m-%d')
            
            df = stock.quote.history(start=start_date, end=end_date, interval='1D')
            
            if df is None or len(df) < 50:
                return None
            
            # Price
            candidate.price = df['close'].iloc[-1]
            candidate.change_1d = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100 if len(df) > 1 else 0
            
            if len(df) >= 20:
                candidate.change_1m = (df['close'].iloc[-1] - df['close'].iloc[-20]) / df['close'].iloc[-20] * 100
            
            # MA
            candidate.ma50 = df['close'].rolling(50).mean().iloc[-1] if len(df) >= 50 else 0
            candidate.ma150 = df['close'].rolling(150).mean().iloc[-1] if len(df) >= 150 else 0
            candidate.ma200 = df['close'].rolling(200).mean().iloc[-1] if len(df) >= 200 else 0
            
            # 52 week high/low
            candidate.high_52w = df['high'].max()
            candidate.low_52w = df['low'].min()
            candidate.pct_from_high = (candidate.high_52w - candidate.price) / candidate.high_52w if candidate.high_52w > 0 else 1
            
            # Volume
            if len(df) >= 20:
                candidate.avg_volume_20d = df['volume'].tail(20).mean()
                candidate.avg_value_20d = (df['volume'] * df['close']).tail(20).mean() * 1000
            
            # RS vs VNIndex
            candidate.rs_vs_vnindex = candidate.change_1m - vnindex_change
            candidate.rs_rating = self._calc_rs_rating(candidate.rs_vs_vnindex)
            
            # SEPA Stage
            candidate.sepa_stage = self._determine_sepa_stage(candidate)
            candidate.trend_score = self._calc_trend_score(candidate)
            
        except Exception as e:
            return None
        
        # 2. Lấy dữ liệu tài chính
        try:
            # Thử lấy financial ratios
            finance = stock.finance
            
            # ROE
            try:
                roe_df = finance.ratio(period='quarter', lang='vi')
                if roe_df is not None and len(roe_df) > 0:
                    candidate.roe = roe_df.get('ROE', pd.Series([0])).iloc[0] / 100
            except:
                candidate.roe = 0.10  # Default
            
            # EPS Growth - cần so sánh 2 quý
            try:
                income_df = finance.income_statement(period='quarter')
                if income_df is not None and len(income_df) >= 4:
                    eps_current = income_df['eps'].iloc[0] if 'eps' in income_df else 0
                    eps_yoy = income_df['eps'].iloc[4] if len(income_df) > 4 else eps_current
                    candidate.eps_growth_yoy = (eps_current - eps_yoy) / abs(eps_yoy) if eps_yoy != 0 else 0
            except:
                candidate.eps_growth_yoy = 0.10  # Default
                
        except:
            candidate.roe = 0.10
            candidate.eps_growth_yoy = 0.10
        
        # 3. Check criteria
        candidate.pass_liquidity = candidate.avg_value_20d >= self.config.MIN_LIQUIDITY
        candidate.pass_trend = candidate.sepa_stage == "Stage 2"
        candidate.pass_rs = candidate.rs_rating >= self.config.MIN_RS_RATING
        candidate.pass_near_high = candidate.pct_from_high <= self.config.MAX_FROM_52W_HIGH
        candidate.pass_eps = candidate.eps_growth_yoy >= self.config.MIN_EPS_GROWTH
        candidate.pass_roe = candidate.roe >= self.config.MIN_ROE
        
        # 4. Overall score
        candidate.canslim_score = self._calc_canslim_score(candidate)
        candidate.overall_score = (candidate.trend_score + candidate.canslim_score + candidate.rs_rating) // 3
        
        return candidate
    
    def _calc_rs_rating(self, rs_vs_vnindex: float) -> int:
        """Tính RS Rating (0-99)"""
        # Giản lược: chuyển đổi RS vs VNIndex sang thang 0-99
        if rs_vs_vnindex >= 20:
            return 99
        elif rs_vs_vnindex >= 10:
            return 90 + int((rs_vs_vnindex - 10) * 0.9)
        elif rs_vs_vnindex >= 5:
            return 80 + int((rs_vs_vnindex - 5) * 2)
        elif rs_vs_vnindex >= 0:
            return 70 + int(rs_vs_vnindex * 2)
        elif rs_vs_vnindex >= -5:
            return 50 + int((rs_vs_vnindex + 5) * 4)
        else:
            return max(0, 50 + int(rs_vs_vnindex * 2))
    
    def _determine_sepa_stage(self, stock: StockCandidate) -> str:
        """Xác định SEPA Stage"""
        price = stock.price
        ma50 = stock.ma50
        ma150 = stock.ma150
        ma200 = stock.ma200
        
        if ma50 == 0 or ma150 == 0 or ma200 == 0:
            return "N/A"
        
        # Stage 2: Uptrend (Giá > MA50 > MA150 > MA200)
        if price > ma50 > ma150 > ma200:
            return "Stage 2"
        
        # Stage 1: Accumulation (MA50 > MA200, giá gần MA)
        elif ma50 > ma200 and abs(price - ma50) / ma50 < 0.1:
            return "Stage 1"
        
        # Stage 4: Downtrend (Giá < MA50 < MA150 < MA200)
        elif price < ma50 < ma150 < ma200:
            return "Stage 4"
        
        # Stage 3: Distribution
        elif price < ma50 and ma50 > ma200:
            return "Stage 3"
        
        return "Transition"
    
    def _calc_trend_score(self, stock: StockCandidate) -> int:
        """Tính điểm xu hướng (0-100)"""
        score = 0
        
        # Price vs MA
        if stock.price > stock.ma50:
            score += 30
        if stock.price > stock.ma150:
            score += 20
        if stock.price > stock.ma200:
            score += 10
        
        # MA alignment
        if stock.ma50 > stock.ma150:
            score += 15
        if stock.ma150 > stock.ma200:
            score += 10
        if stock.ma50 > stock.ma200:
            score += 5
        
        # Near high
        if stock.pct_from_high <= 0.10:
            score += 10
        elif stock.pct_from_high <= 0.25:
            score += 5
        
        return min(100, score)
    
    def _calc_canslim_score(self, stock: StockCandidate) -> int:
        """Tính điểm CANSLIM (0-100)"""
        score = 0
        
        # C - Current Earnings (25 điểm)
        if stock.eps_growth_yoy >= 0.25:
            score += 25
        elif stock.eps_growth_yoy >= 0.15:
            score += 20
        elif stock.eps_growth_yoy >= 0.10:
            score += 10
        
        # A - Annual ROE (25 điểm)
        if stock.roe >= 0.20:
            score += 25
        elif stock.roe >= 0.15:
            score += 20
        elif stock.roe >= 0.10:
            score += 10
        
        # N - Near 52w high (25 điểm)
        if stock.pct_from_high <= 0.10:
            score += 25
        elif stock.pct_from_high <= 0.25:
            score += 20
        elif stock.pct_from_high <= 0.40:
            score += 10
        
        # L - Leader (RS Rating) (25 điểm)
        if stock.rs_rating >= 90:
            score += 25
        elif stock.rs_rating >= 80:
            score += 20
        elif stock.rs_rating >= 70:
            score += 15
        
        return min(100, score)
    
    def _apply_criteria(self, candidates: List[StockCandidate]) -> List[StockCandidate]:
        """Áp dụng tiêu chí và xếp hạng"""
        # Lọc những mã đạt ít nhất 4/6 tiêu chí
        qualified = [c for c in candidates if c.criteria_passed >= 4]
        
        # Sort theo overall_score
        qualified.sort(key=lambda x: x.overall_score, reverse=True)
        
        # Lấy top N
        return qualified[:self.config.TOP_N]


# ══════════════════════════════════════════════════════════════════════════════
# AI GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class ScreenerAIGenerator:
    """Tạo phân tích AI cho watchlist"""
    
    def __init__(self, config: ScreenerConfig):
        self.config = config
        self.ai = self._init_ai()
    
    def _init_ai(self):
        if not self.config.AI_API_KEY or AIProvider is None:
            return None
        
        try:
            ai_config = AIConfig(
                provider=self.config.AI_PROVIDER,
                api_key=self.config.AI_API_KEY,
                system_prompt="Bạn là chuyên gia phân tích cổ phiếu theo CANSLIM."
            )
            return AIProvider(ai_config)
        except:
            return None
    
    def generate(self, report: ScreenerReport) -> str:
        """Tạo phân tích AI"""
        if not self.ai:
            return "⚠️ AI chưa cấu hình"
        
        # Build watchlist table
        table = ""
        for i, s in enumerate(report.watchlist, 1):
            table += f"\n{i}. {s.symbol}: Score={s.overall_score} | RS={s.rs_rating} | Stage={s.sepa_stage}"
            table += f"\n   Price={s.price:,.0f} | vs52wH={s.pct_from_high*100:.1f}% | EPS={s.eps_growth_yoy*100:+.1f}% | ROE={s.roe*100:.1f}%"
        
        prompt = f"""
WATCHLIST CANSLIM - {report.timestamp.strftime('%d/%m/%Y')}
Tổng: {report.total_stocks} mã → Lọc: {report.pass_all} mã

TOP {len(report.watchlist)} CỔ PHIẾU:
{table}

SECTOR PHÂN BỔ: {report.sector_distribution}

Hãy phân tích:
1. Nhận xét về chất lượng watchlist
2. TOP 3 mã tiềm năng nhất và lý do
3. Cảnh báo rủi ro
4. Chiến lược vào lệnh cho Module 3
"""
        
        try:
            return self.ai.chat(prompt)
        except Exception as e:
            return f"❌ Lỗi AI: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MODULE
# ══════════════════════════════════════════════════════════════════════════════

class StockScreenerModule:
    """Module Stock Screener"""
    
    def __init__(self, config: ScreenerConfig = None):
        self.config = config or create_config_from_unified()
        self.screener = StockScreener(self.config)
        self.ai_generator = ScreenerAIGenerator(self.config)
        self.report: ScreenerReport = None
    
    def run(self) -> ScreenerReport:
        """Chạy module"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║     MODULE 2.5: STOCK SCREENER - CANSLIM & SEPA              ║
║     Lọc "Siêu cổ phiếu" tiềm năng                            ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # 1. Screen
        self.report = self.screener.screen()
        
        # 2. AI Analysis
        print("\n[6/6] AI Analysis...")
        self.report.ai_analysis = self.ai_generator.generate(self.report)
        
        # 3. Print
        self._print_report()
        
        # 4. Save
        if self.config.SAVE_REPORT:
            self._save_report()
        
        return self.report
    
    def _print_report(self):
        """In báo cáo"""
        print("\n" + "="*70)
        print("📊 WATCHLIST - SIÊU CỔ PHIẾU TIỀM NĂNG")
        print("="*70)
        
        print(f"\n{'#':<3} {'MÃ':<6} {'SCORE':<6} {'RS':<4} {'STAGE':<10} {'vs52wH':<8} {'CRITERIA':<10}")
        print("-"*60)
        
        for i, s in enumerate(self.report.watchlist, 1):
            criteria = f"{s.criteria_passed}/6"
            print(f"{i:<3} {s.symbol:<6} {s.overall_score:<6} {s.rs_rating:<4} {s.sepa_stage:<10} "
                  f"{s.pct_from_high*100:>6.1f}% {criteria:<10}")
        
        print("\n" + "-"*70)
        print("🤖 AI ANALYSIS:")
        print("-"*70)
        print(self.report.ai_analysis)
    
    def _save_report(self):
        """Lưu báo cáo"""
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        
        filename = os.path.join(
            self.config.OUTPUT_DIR,
            f"stock_screener_{self.report.timestamp.strftime('%Y%m%d_%H%M')}.md"
        )
        
        # Build table
        table_rows = ""
        for i, s in enumerate(self.report.watchlist, 1):
            table_rows += f"| {i} | {s.symbol} | {s.overall_score} | {s.rs_rating} | {s.sepa_stage} | "
            table_rows += f"{s.pct_from_high*100:.1f}% | {s.eps_growth_yoy*100:+.1f}% | {s.roe*100:.1f}% | {s.criteria_passed}/6 |\n"
        
        content = f"""# WATCHLIST - SIÊU CỔ PHIẾU TIỀM NĂNG
**Ngày:** {self.report.timestamp.strftime('%d/%m/%Y %H:%M')}

## THỐNG KÊ
- Tổng cổ phiếu: {self.report.total_stocks}
- Qua thanh khoản: {self.report.pass_liquidity}
- Đạt tiêu chí: {self.report.pass_all}

## TIÊU CHÍ LỌC
1. Thanh khoản: GTGD > 10 tỷ/phiên
2. Trend (SEPA): Stage 2 (Giá > MA50 > MA150 > MA200)
3. RS Rating: > 70
4. Định giá: Trong vùng 25% từ đỉnh 52 tuần
5. EPS Growth: > 15% YoY
6. ROE: > 15%

## TOP {len(self.report.watchlist)} CỔ PHIẾU

| # | Mã | Score | RS | Stage | vs52wH | EPS | ROE | Criteria |
|---|-----|-------|----|----|--------|-----|-----|----------|
{table_rows}

## SECTOR PHÂN BỔ
{self.report.sector_distribution}

## AI ANALYSIS
{self.report.ai_analysis}
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✓ Đã lưu: {filename}")
        
        # Lưu thêm file watchlist.csv cho Module 3
        csv_filename = os.path.join(self.config.OUTPUT_DIR, "watchlist.csv")
        df = pd.DataFrame([{
            'symbol': s.symbol,
            'score': s.overall_score,
            'rs_rating': s.rs_rating,
            'sepa_stage': s.sepa_stage,
            'pct_from_high': s.pct_from_high,
            'eps_growth': s.eps_growth_yoy,
            'roe': s.roe,
            'criteria_passed': s.criteria_passed
        } for s in self.report.watchlist])
        df.to_csv(csv_filename, index=False)
        print(f"✓ Đã lưu watchlist: {csv_filename}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    module = StockScreenerModule()
    report = module.run()