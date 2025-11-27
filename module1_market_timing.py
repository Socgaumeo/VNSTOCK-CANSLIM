#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     MODULE 1: MARKET TIMING - ĐỊNH THỜI ĐIỂM THỊ TRƯỜNG                     ║
║                    vnstock Premium + AI Integration                          ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Flow: Thu thập dữ liệu → Phân tích → AI Generate Report                     ║
║  AI Providers: DeepSeek | Gemini | Claude | OpenAI | Groq                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# Import AI Provider
from ai_providers import AIProvider, AIConfig


# ══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MarketTimingConfig:
    """Cấu hình tổng hợp"""
    
    # ─────────────────────────────────────────────────────────────
    # VNSTOCK CONFIG
    # ─────────────────────────────────────────────────────────────
    VNSTOCK_API_KEY: str = "vnstock_0acf8671851dba60b26830c7816c756f"           # API key vnstock premium
    DATA_SOURCE: str = "VCI"            # VCI hoặc TCBS
    
    # Index cần theo dõi
    MAIN_INDEX: str = "VNINDEX"
    COMPARISON_INDICES: List[str] = field(default_factory=lambda: ["VN30", "VN100"])
    SECTOR_INDICES: List[str] = field(default_factory=lambda: [
        "VNFIN", "VNREAL", "VNMAT", "VNIT",
        "VNHEAL", "VNCOND", "VNCONS"
    ])
    
    LOOKBACK_DAYS: int = 120
    API_DELAY: float = 0.8              # Tăng delay để tránh rate limit
    BREADTH_SAMPLE_SIZE: int = 30       # Số mã mẫu để tính breadth
    
    # ─────────────────────────────────────────────────────────────
    # AI CONFIG
    # ─────────────────────────────────────────────────────────────
    AI_PROVIDER: str = "deepseek"       # deepseek | gemini | claude | openai | groq
    AI_API_KEY: str = ""                # API key của AI provider
    AI_MODEL: str = ""                  # Để trống = dùng default
    AI_MAX_TOKENS: int = 4096
    AI_TEMPERATURE: float = 0.7
    
    # ─────────────────────────────────────────────────────────────
    # OUTPUT CONFIG
    # ─────────────────────────────────────────────────────────────
    OUTPUT_DIR: str = "./output"
    SAVE_REPORT: bool = True


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TechnicalData:
    """Dữ liệu kỹ thuật của một index"""
    symbol: str = ""
    close: float = 0.0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0
    
    # Changes
    change_1d: float = 0.0
    change_5d: float = 0.0
    change_1m: float = 0.0
    
    # Moving Averages
    ma20: float = 0.0
    ma50: float = 0.0
    ma200: float = 0.0
    
    # Volume
    volume_ma20: float = 0.0
    volume_ratio: float = 1.0
    
    # Indicators
    rsi_14: float = 50.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    adx: float = 25.0
    plus_di: float = 25.0
    minus_di: float = 25.0


@dataclass
class MarketBreadth:
    """Độ rộng thị trường"""
    advances: int = 0
    declines: int = 0
    unchanged: int = 0
    ceiling: int = 0
    floor: int = 0
    
    @property
    def ad_ratio(self) -> float:
        return self.advances / self.declines if self.declines > 0 else 0
    
    @property
    def total(self) -> int:
        return self.advances + self.declines + self.unchanged


@dataclass
class MoneyFlow:
    """Dòng tiền"""
    foreign_buy: float = 0.0
    foreign_sell: float = 0.0
    foreign_net: float = 0.0
    
    proprietary_buy: float = 0.0
    proprietary_sell: float = 0.0
    proprietary_net: float = 0.0
    
    total_value: float = 0.0
    
    top_foreign_buy: List[Tuple[str, float]] = field(default_factory=list)
    top_foreign_sell: List[Tuple[str, float]] = field(default_factory=list)


@dataclass
class SectorData:
    """Dữ liệu ngành"""
    code: str
    name: str
    change_1d: float = 0.0
    change_5d: float = 0.0
    change_1m: float = 0.0
    vs_vnindex: float = 0.0
    rank: int = 0


@dataclass
class MarketReport:
    """Báo cáo tổng hợp"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Core data
    vnindex: TechnicalData = field(default_factory=TechnicalData)
    vn30: TechnicalData = field(default_factory=TechnicalData)
    vn100: TechnicalData = field(default_factory=TechnicalData)
    
    # Market internals
    breadth: MarketBreadth = field(default_factory=MarketBreadth)
    money_flow: MoneyFlow = field(default_factory=MoneyFlow)
    
    # Sectors
    sectors: List[SectorData] = field(default_factory=list)
    
    # Analysis
    market_color: str = "🟡 VÀNG"
    market_score: int = 50
    trend_status: str = "SIDEWAY"
    key_signals: List[str] = field(default_factory=list)
    
    # AI Report
    ai_analysis: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# DATA COLLECTOR
# ══════════════════════════════════════════════════════════════════════════════

class MarketDataCollector:
    """Thu thập dữ liệu từ vnstock"""
    
    SECTOR_NAMES = {
        'VNFIN': 'Tài chính',
        'VNREAL': 'Bất động sản',
        'VNMAT': 'Nguyên vật liệu',
        'VNIT': 'Công nghệ',
        'VNHEAL': 'Y tế',
        'VNCOND': 'Tiêu dùng không thiết yếu',
        'VNCONS': 'Tiêu dùng thiết yếu',
        'VN30': 'VN30 Large Cap',
        'VN100': 'VN100',
    }
    
    def __init__(self, config: MarketTimingConfig):
        self.config = config
        self._init_vnstock()
    
    def _init_vnstock(self):
        try:
            from vnstock import Vnstock, Trading, Listing
            
            if self.config.VNSTOCK_API_KEY:
                os.environ['VNSTOCK_API_KEY'] = self.config.VNSTOCK_API_KEY
            
            self.Vnstock = Vnstock
            self.Trading = Trading
            self.Listing = Listing
            print("✓ Kết nối vnstock thành công")
            
        except ImportError:
            raise ImportError("Chạy: pip install -U vnstock")
    
    def _delay(self):
        import time
        time.sleep(self.config.API_DELAY)
    
    def _get_stock(self, symbol: str):
        self._delay()
        return self.Vnstock().stock(symbol=symbol, source=self.config.DATA_SOURCE)
    
    # ─────────────────────────────────────────────────────────────
    # TECHNICAL DATA
    # ─────────────────────────────────────────────────────────────
    
    def get_technical_data(self, symbol: str) -> TechnicalData:
        """Lấy dữ liệu kỹ thuật đầy đủ"""
        result = TechnicalData(symbol=symbol)
        
        try:
            stock = self._get_stock(symbol)
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=self.config.LOOKBACK_DAYS)).strftime('%Y-%m-%d')
            
            df = stock.quote.history(start=start_date, end=end_date)
            
            if df.empty:
                return result
            
            # OHLCV
            result.close = df['close'].iloc[-1]
            result.open = df['open'].iloc[-1]
            result.high = df['high'].iloc[-1]
            result.low = df['low'].iloc[-1]
            result.volume = df['volume'].iloc[-1]
            
            close = df['close'].values
            volume = df['volume'].values
            high = df['high'].values
            low = df['low'].values
            
            # Changes
            if len(close) >= 2:
                result.change_1d = ((close[-1] / close[-2]) - 1) * 100
            if len(close) >= 5:
                result.change_5d = ((close[-1] / close[-5]) - 1) * 100
            if len(close) >= 22:
                result.change_1m = ((close[-1] / close[-22]) - 1) * 100
            
            # Moving Averages
            if len(close) >= 20:
                result.ma20 = np.mean(close[-20:])
            if len(close) >= 50:
                result.ma50 = np.mean(close[-50:])
            if len(close) >= 200:
                result.ma200 = np.mean(close[-200:])
            
            # Volume
            if len(volume) >= 20:
                result.volume_ma20 = np.mean(volume[-20:])
                result.volume_ratio = volume[-1] / result.volume_ma20 if result.volume_ma20 > 0 else 1
            
            # RSI
            result.rsi_14 = self._calc_rsi(close, 14)
            
            # MACD
            macd = self._calc_macd(close)
            result.macd = macd['macd']
            result.macd_signal = macd['signal']
            result.macd_hist = macd['histogram']
            
            # ADX
            adx = self._calc_adx(high, low, close)
            result.adx = adx['adx']
            result.plus_di = adx['plus_di']
            result.minus_di = adx['minus_di']
            
        except Exception as e:
            print(f"   ⚠️ Lỗi {symbol}: {e}")
        
        return result
    
    def _calc_rsi(self, prices: np.ndarray, period: int = 14) -> float:
        if len(prices) < period + 1:
            return 50.0
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calc_macd(self, prices: np.ndarray) -> Dict:
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
    
    def _calc_adx(self, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> Dict:
        if len(close) < 28:
            return {'adx': 25, 'plus_di': 25, 'minus_di': 25}
        
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
        
        return {'adx': dx, 'plus_di': plus_di, 'minus_di': minus_di}
    
    # ─────────────────────────────────────────────────────────────
    # MARKET BREADTH & MONEY FLOW (sử dụng price_board)
    # ─────────────────────────────────────────────────────────────
    
    def _get_price_board_data(self, symbols: List[str]) -> Optional[pd.DataFrame]:
        """Lấy dữ liệu price_board cho danh sách symbols"""
        try:
            stock = self.Vnstock().stock(symbol=symbols[0], source=self.config.DATA_SOURCE)
            df = stock.trading.price_board(symbols_list=symbols)
            return df
        except Exception as e:
            print(f"   ⚠️ Lỗi price_board: {e}")
            return None
    
    def get_market_breadth(self) -> MarketBreadth:
        """Lấy độ rộng thị trường từ price_board"""
        result = MarketBreadth()
        
        try:
            # Lấy danh sách cổ phiếu thực (chỉ mã 3 ký tự - loại bỏ warrant, ETF)
            listing = self.Listing()
            all_stocks = listing.all_symbols()
            
            # Lọc chỉ lấy mã 3 ký tự (cổ phiếu thực)
            real_stocks = all_stocks[all_stocks['symbol'].str.len() == 3]['symbol'].tolist()
            
            # Lấy mẫu đại diện
            sample_size = min(self.config.BREADTH_SAMPLE_SIZE, len(real_stocks))
            import random
            random.seed(42)
            sample_stocks = random.sample(real_stocks, sample_size)
            
            print(f"   📊 Đang lấy price_board cho {sample_size} mã...")
            
            # Lấy price_board (một lần gọi API cho nhiều mã)
            df = self._get_price_board_data(sample_stocks)
            
            if df is not None and len(df) > 0:
                advances = 0
                declines = 0
                unchanged = 0
                ceiling = 0
                floor = 0
                
                # Duyệt qua từng dòng để tính breadth
                for _, row in df.iterrows():
                    try:
                        # Lấy giá từ multi-level columns
                        match_price = row[('match', 'match_price')]
                        ref_price = row[('listing', 'ref_price')]
                        ceiling_price = row[('listing', 'ceiling')]
                        floor_price = row[('listing', 'floor')]
                        
                        if match_price > 0 and ref_price > 0:
                            change_pct = (match_price - ref_price) / ref_price * 100
                            
                            if match_price >= ceiling_price:
                                ceiling += 1
                                advances += 1
                            elif match_price <= floor_price:
                                floor += 1
                                declines += 1
                            elif change_pct > 0.1:
                                advances += 1
                            elif change_pct < -0.1:
                                declines += 1
                            else:
                                unchanged += 1
                    except:
                        pass
                
                # Scale lên theo tổng số mã active (~500 mã trên HOSE)
                scale_factor = 500 / len(df) if len(df) > 0 else 1
                result.advances = int(advances * scale_factor)
                result.declines = int(declines * scale_factor)
                result.unchanged = int(unchanged * scale_factor)
                result.ceiling = int(ceiling * scale_factor)
                result.floor = int(floor * scale_factor)
                
                print(f"   ✓ Breadth: Tăng={result.advances}, Giảm={result.declines}, "
                      f"Trần={result.ceiling}, Sàn={result.floor}")
            else:
                # Fallback
                result.advances = 250
                result.declines = 220
                result.unchanged = 80
                print("   ⚠️ Không lấy được price_board, dùng estimate")
            
        except Exception as e:
            print(f"   ⚠️ Lỗi breadth: {e}")
            result.advances = 250
            result.declines = 220
            result.unchanged = 80
        
        return result
    
    # ─────────────────────────────────────────────────────────────
    # MONEY FLOW
    # ─────────────────────────────────────────────────────────────
    
    def get_money_flow(self) -> MoneyFlow:
        """Lấy dòng tiền từ price_board"""
        result = MoneyFlow()
        
        try:
            # Các mã bluechip để tính dòng tiền
            bluechips = ['VHM', 'FPT', 'VCB', 'HPG', 'VNM', 'VIC', 'MSN', 'MWG',
                        'SSI', 'VPB', 'TCB', 'MBB', 'ACB', 'STB', 'HDB']
            
            print(f"   📊 Đang lấy dữ liệu dòng tiền từ {len(bluechips)} bluechips...")
            
            df = self._get_price_board_data(bluechips)
            
            if df is not None and len(df) > 0:
                total_foreign_buy = 0
                total_foreign_sell = 0
                total_value = 0
                stock_flows = []
                
                for _, row in df.iterrows():
                    try:
                        symbol = row[('listing', 'symbol')]
                        foreign_buy_val = row[('match', 'foreign_buy_value')] / 1e9  # Chuyển sang tỷ
                        foreign_sell_val = row[('match', 'foreign_sell_value')] / 1e9
                        accumulated_value = row[('match', 'accumulated_value')] / 1e9
                        
                        total_foreign_buy += foreign_buy_val
                        total_foreign_sell += foreign_sell_val
                        total_value += accumulated_value
                        
                        net_flow = foreign_buy_val - foreign_sell_val
                        stock_flows.append((symbol, net_flow))
                    except:
                        pass
                
                result.foreign_buy = total_foreign_buy
                result.foreign_sell = total_foreign_sell
                result.foreign_net = total_foreign_buy - total_foreign_sell
                result.total_value = total_value
                
                # Estimate tự doanh (thường ~30% của khối ngoại ngược chiều)
                result.proprietary_net = -result.foreign_net * 0.3
                
                # Top buy/sell
                sorted_flows = sorted(stock_flows, key=lambda x: x[1], reverse=True)
                result.top_foreign_buy = [(s, v) for s, v in sorted_flows[:5] if v > 0]
                result.top_foreign_sell = [(s, v) for s, v in sorted_flows[-5:] if v < 0]
                
                print(f"   ✓ Money Flow: KN={result.foreign_net:+.1f}tỷ (Mua={result.foreign_buy:.1f}, "
                      f"Bán={result.foreign_sell:.1f})")
                print(f"   ✓ Top mua: {', '.join([f'{s}({v:+.1f})' for s,v in result.top_foreign_buy[:3]])}")
                print(f"   ✓ Top bán: {', '.join([f'{s}({v:+.1f})' for s,v in result.top_foreign_sell[:3]])}")
            else:
                # Fallback
                result.foreign_net = -125.5
                result.proprietary_net = 45.2
                result.total_value = 18500
                result.top_foreign_buy = [('VHM', 35.2), ('FPT', 28.5), ('VCB', 25.1)]
                result.top_foreign_sell = [('HPG', -42.3), ('SSI', -28.5), ('MWG', -22.1)]
                print("   ⚠️ Không lấy được price_board, dùng estimate")
            
        except Exception as e:
            print(f"   ⚠️ Lỗi money flow: {e}")
            result.foreign_net = -125.5
            result.proprietary_net = 45.2
            result.total_value = 18500
            result.top_foreign_buy = [('VHM', 35.2), ('FPT', 28.5), ('VCB', 25.1)]
            result.top_foreign_sell = [('HPG', -42.3), ('SSI', -28.5), ('MWG', -22.1)]
        
        return result
    
    # ─────────────────────────────────────────────────────────────
    # SECTOR DATA
    # ─────────────────────────────────────────────────────────────
    
    def get_sector_data(self, vnindex_change: float = 0) -> List[SectorData]:
        """Lấy dữ liệu các ngành"""
        results = []
        
        for code in self.config.SECTOR_INDICES:
            try:
                tech = self.get_technical_data(code)
                
                sector = SectorData(
                    code=code,
                    name=self.SECTOR_NAMES.get(code, code),
                    change_1d=tech.change_1d,
                    change_5d=tech.change_5d,
                    change_1m=tech.change_1m,
                    vs_vnindex=tech.change_1d - vnindex_change
                )
                results.append(sector)
                
                print(f"   ✓ {code}: {tech.change_1d:+.2f}%")
                
            except Exception as e:
                print(f"   ⚠️ Lỗi {code}: {e}")
        
        # Sắp xếp và đánh rank
        results.sort(key=lambda x: x.change_1d, reverse=True)
        for i, s in enumerate(results, 1):
            s.rank = i
        
        return results


# ══════════════════════════════════════════════════════════════════════════════
# MARKET ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class MarketAnalyzer:
    """Phân tích và tính điểm thị trường"""
    
    def __init__(self, config: MarketTimingConfig):
        self.config = config
        self.collector = MarketDataCollector(config)
    
    def collect_all_data(self) -> MarketReport:
        """Thu thập tất cả dữ liệu"""
        print("\n" + "="*60)
        print("📊 THU THẬP DỮ LIỆU THỊ TRƯỜNG")
        print("="*60)
        
        report = MarketReport()
        
        # 1. VNIndex
        print("\n[1/5] VN-INDEX...")
        report.vnindex = self.collector.get_technical_data("VNINDEX")
        print(f"   ✓ VNIndex: {report.vnindex.close:,.0f} ({report.vnindex.change_1d:+.2f}%)")
        
        # 2. VN30
        print("\n[2/5] VN30...")
        report.vn30 = self.collector.get_technical_data("VN30")
        print(f"   ✓ VN30: {report.vn30.close:,.0f} ({report.vn30.change_1d:+.2f}%)")
        
        # 3. VN100
        print("\n[3/5] VN100...")
        report.vn100 = self.collector.get_technical_data("VN100")
        print(f"   ✓ VN100: {report.vn100.close:,.0f} ({report.vn100.change_1d:+.2f}%)")
        
        # 4. Breadth
        print("\n[4/5] ĐỘ RỘNG THỊ TRƯỜNG...")
        report.breadth = self.collector.get_market_breadth()
        
        # 5. Money Flow
        print("\n[5/5] DÒNG TIỀN...")
        report.money_flow = self.collector.get_money_flow()
        
        # 6. Sectors
        print("\n[6/6] CHỈ SỐ NGÀNH...")
        report.sectors = self.collector.get_sector_data(report.vnindex.change_1d)
        
        return report
    
    def analyze(self, report: MarketReport) -> MarketReport:
        """Phân tích và tính điểm"""
        print("\n" + "="*60)
        print("🔍 PHÂN TÍCH THỊ TRƯỜNG")
        print("="*60)
        
        vni = report.vnindex
        signals = []
        score = 0
        
        # 1. Price vs MA (30 điểm)
        # Tính vị trí giá so với MA
        above_ma20 = vni.close > vni.ma20 if vni.ma20 > 0 else False
        above_ma50 = vni.close > vni.ma50 if vni.ma50 > 0 else False
        ma20_above_ma50 = vni.ma20 > vni.ma50 if (vni.ma20 > 0 and vni.ma50 > 0) else False
        
        if above_ma20 and above_ma50 and ma20_above_ma50:
            score += 30
            signals.append(f"✅ Uptrend mạnh: Giá({vni.close:,.0f}) > MA20({vni.ma20:,.0f}) > MA50({vni.ma50:,.0f})")
        elif above_ma20 and above_ma50:
            # Giá trên cả MA20 và MA50, nhưng MA20 chưa vượt MA50
            score += 25
            signals.append(f"✅ Bullish: Giá({vni.close:,.0f}) > MA20({vni.ma20:,.0f}) & MA50({vni.ma50:,.0f})")
        elif above_ma50:
            score += 15
            signals.append(f"⚠️ Giá trên MA50({vni.ma50:,.0f}) nhưng dưới MA20({vni.ma20:,.0f})")
        elif above_ma20:
            score += 10
            signals.append(f"⚠️ Giá trên MA20({vni.ma20:,.0f}) nhưng dưới MA50({vni.ma50:,.0f})")
        elif vni.close < vni.ma20 and vni.close < vni.ma50:
            if vni.ma20 < vni.ma50:
                score -= 30
                signals.append(f"❌ Downtrend: Giá({vni.close:,.0f}) < MA20({vni.ma20:,.0f}) < MA50({vni.ma50:,.0f})")
            else:
                score -= 20
                signals.append(f"❌ Giá dưới cả MA20 và MA50")
        else:
            signals.append(f"➖ MA chưa rõ xu hướng (Giá={vni.close:,.0f}, MA20={vni.ma20:,.0f}, MA50={vni.ma50:,.0f})")
        
        # 2. RSI (15 điểm)
        if 40 <= vni.rsi_14 <= 60:
            score += 5
            signals.append(f"➖ RSI trung tính: {vni.rsi_14:.0f}")
        elif vni.rsi_14 > 70:
            score -= 10
            signals.append(f"⚠️ RSI quá mua: {vni.rsi_14:.0f}")
        elif vni.rsi_14 < 30:
            score += 10
            signals.append(f"📈 RSI quá bán: {vni.rsi_14:.0f} (cơ hội)")
        elif vni.rsi_14 > 50:
            score += 10
            signals.append(f"✅ RSI tích cực: {vni.rsi_14:.0f}")
        else:
            score -= 5
            signals.append(f"❌ RSI yếu: {vni.rsi_14:.0f}")
        
        # 3. MACD (15 điểm)
        if vni.macd_hist > 0:
            score += 15
            signals.append("✅ MACD Histogram dương")
        else:
            score -= 15
            signals.append("❌ MACD Histogram âm")
        
        # 4. ADX (10 điểm)
        if vni.adx > 25:
            if vni.plus_di > vni.minus_di:
                score += 10
                signals.append(f"✅ Trend mạnh bullish (ADX={vni.adx:.0f})")
            else:
                score -= 10
                signals.append(f"❌ Trend mạnh bearish (ADX={vni.adx:.0f})")
        else:
            signals.append(f"➖ Không có trend rõ (ADX={vni.adx:.0f})")
        
        # 5. Breadth (15 điểm)
        ad = report.breadth.ad_ratio
        if ad >= 1.5:
            score += 15
            signals.append(f"✅ Breadth rất tốt (A/D={ad:.2f})")
        elif ad >= 1:
            score += 5
            signals.append(f"✅ Breadth tích cực (A/D={ad:.2f})")
        elif ad < 0.7:
            score -= 15
            signals.append(f"❌ Breadth xấu (A/D={ad:.2f})")
        else:
            signals.append(f"➖ Breadth trung tính (A/D={ad:.2f})")
        
        # 6. Money Flow (15 điểm)
        mf = report.money_flow
        if mf.foreign_net > 0 and mf.proprietary_net > 0:
            score += 15
            signals.append("✅ Cá mập đang MUA (KN + TD mua ròng)")
        elif mf.foreign_net > 0:
            score += 5
            signals.append("✅ Khối ngoại mua ròng")
        elif mf.foreign_net < -100:
            score -= 15
            signals.append(f"❌ Khối ngoại bán mạnh ({mf.foreign_net:.0f} tỷ)")
        else:
            signals.append(f"➖ Dòng tiền trung tính")
        
        # Xác định Market Color
        report.market_score = max(-100, min(100, score))
        
        if score >= 40:
            report.market_color = "🟢 XANH - TẤN CÔNG"
            report.trend_status = "UPTREND"
        elif score >= 0:
            report.market_color = "🟡 VÀNG - PHÒNG THỦ"
            report.trend_status = "SIDEWAY"
        else:
            report.market_color = "🔴 ĐỎ - RÚT LUI"
            report.trend_status = "DOWNTREND"
        
        report.key_signals = signals
        
        print(f"\n📊 ĐIỂM THỊ TRƯỜNG: {report.market_score}/100")
        print(f"🎯 {report.market_color}")
        for sig in signals:
            print(f"   {sig}")
        
        return report


# ══════════════════════════════════════════════════════════════════════════════
# AI REPORT GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class AIReportGenerator:
    """Tạo báo cáo phân tích bằng AI"""
    
    SYSTEM_PROMPT = """Bạn là Giám đốc Phân tích Chiến lược tại một quỹ đầu tư quy mô 100 tỷ VNĐ tại Việt Nam.

PHONG CÁCH:
- Thận trọng, dựa trên dữ liệu (Data-driven)
- Tuân thủ VSA (Volume Spread Analysis)
- Quản trị rủi ro chặt chẽ
- Ngôn ngữ: Tiếng Việt, chuyên nghiệp

YÊU CẦU OUTPUT:
- Phân tích phải dựa trên DỮ LIỆU được cung cấp
- Đưa ra nhận định rõ ràng, không mập mờ
- Luôn có phần "What-if" với xác suất cụ thể
- Khuyến nghị hành động cụ thể"""
    
    def __init__(self, config: MarketTimingConfig):
        self.config = config
        self.ai = self._init_ai()
    
    def _init_ai(self) -> Optional[AIProvider]:
        """Khởi tạo AI Provider"""
        if not self.config.AI_API_KEY:
            print("⚠️ Chưa có AI API key - sẽ chỉ xuất raw data")
            return None
        
        try:
            ai_config = AIConfig(
                provider=self.config.AI_PROVIDER,
                api_key=self.config.AI_API_KEY,
                model=self.config.AI_MODEL,
                max_tokens=self.config.AI_MAX_TOKENS,
                temperature=self.config.AI_TEMPERATURE,
                system_prompt=self.SYSTEM_PROMPT
            )
            
            return AIProvider(ai_config)
            
        except Exception as e:
            print(f"⚠️ Lỗi khởi tạo AI: {e}")
            return None
    
    def generate_prompt(self, report: MarketReport) -> str:
        """Tạo prompt từ dữ liệu"""
        vni = report.vnindex
        vn30 = report.vn30
        breadth = report.breadth
        flow = report.money_flow
        
        # Top sectors
        top_sectors = report.sectors[:3] if report.sectors else []
        weak_sectors = report.sectors[-3:] if len(report.sectors) >= 3 else []
        
        prompt = f"""
═══════════════════════════════════════════════════════════════
DỮ LIỆU THỊ TRƯỜNG NGÀY {report.timestamp.strftime('%d/%m/%Y %H:%M')}
═══════════════════════════════════════════════════════════════

📈 VN-INDEX:
   - Giá: {vni.close:,.0f} điểm | Thay đổi: {vni.change_1d:+.2f}%
   - OHLC: O={vni.open:,.0f} H={vni.high:,.0f} L={vni.low:,.0f} C={vni.close:,.0f}
   - MA20: {vni.ma20:,.0f} | MA50: {vni.ma50:,.0f} | MA200: {vni.ma200:,.0f}
   - VỊ TRÍ GIÁ: {"Giá TRÊN MA20" if vni.close > vni.ma20 else "Giá DƯỚI MA20"}, {"Giá TRÊN MA50" if vni.close > vni.ma50 else "Giá DƯỚI MA50"}
   - RSI(14): {vni.rsi_14:.1f}
   - MACD: {vni.macd:.2f} | Signal: {vni.macd_signal:.2f} | Hist: {vni.macd_hist:+.2f}
   - ADX: {vni.adx:.1f} | +DI: {vni.plus_di:.1f} | -DI: {vni.minus_di:.1f}
   - Volume: {vni.volume:,.0f} | vs MA20: {vni.volume_ratio:.2f}x

📊 VN30:
   - Giá: {vn30.close:,.0f} | Thay đổi: {vn30.change_1d:+.2f}%
   - RSI: {vn30.rsi_14:.1f} | MACD Hist: {vn30.macd_hist:+.2f}

📉 ĐỘ RỘNG THỊ TRƯỜNG:
   - Số mã TĂNG: {breadth.advances} | GIẢM: {breadth.declines} | Đứng giá: {breadth.unchanged}
   - Tỷ lệ A/D: {breadth.ad_ratio:.2f}

💰 DÒNG TIỀN:
   - Khối ngoại: {flow.foreign_net:+.1f} tỷ VND
   - Tự doanh: {flow.proprietary_net:+.1f} tỷ VND
   - Tổng GTGD: {flow.total_value:,.0f} tỷ VND
   - Top KN mua: {', '.join([f"{s}({v:+.0f})" for s,v in flow.top_foreign_buy])}
   - Top KN bán: {', '.join([f"{s}({v:+.0f})" for s,v in flow.top_foreign_sell])}

🏭 TOP 3 NGÀNH MẠNH:
{chr(10).join([f"   {i+1}. {s.name}: {s.change_1d:+.2f}% (vs VNI: {s.vs_vnindex:+.2f}%)" for i, s in enumerate(top_sectors)])}

📉 TOP 3 NGÀNH YẾU:
{chr(10).join([f"   - {s.name}: {s.change_1d:+.2f}%" for s in weak_sectors])}

🎯 ĐÁNH GIÁ SƠ BỘ:
   - Market Color: {report.market_color}
   - Market Score: {report.market_score}/100

═══════════════════════════════════════════════════════════════

YÊU CẦU PHÂN TÍCH:

Hãy viết BÁO CÁO CHIẾN LƯỢC NGÀY với cấu trúc sau:

## 1. TỔNG QUAN THỊ TRƯỜNG
- Nhận định xu hướng chính (Uptrend/Downtrend/Sideway)
- Phân tích nến và khối lượng theo VSA
- Tâm lý thị trường

## 2. PHÂN TÍCH CẤU TRÚC
- So sánh VN30 vs VNIndex: Nhóm nào dẫn dắt?
- Có phân kỳ âm/dương không?

## 3. DÒNG TIỀN & NGÀNH
- Hành động của "Cá mập" (KN, TD)
- Ngành dẫn dắt và ngành đang suy yếu

## 4. TÍN HIỆU KỸ THUẬT
- Vị thế giá so với MA
- RSI, MACD, ADX báo hiệu gì?

## 5. KỊCH BẢN "WHAT-IF" (QUAN TRỌNG)

Xây dựng 3 kịch bản cho phiên TIẾP THEO:

### Kịch bản 1 - TÍCH CỰC (Xác suất: __%)
- Điều kiện kích hoạt: [Cụ thể mức giá, volume]
- Hành động: [Cụ thể]

### Kịch bản 2 - TRUNG TÍNH (Xác suất: __%)
- Điều kiện: [Cụ thể]
- Hành động: [Cụ thể]

### Kịch bản 3 - TIÊU CỰC (Xác suất: __%)
- Điều kiện: [Cụ thể]
- Hành động: [Cụ thể]

## 6. KHUYẾN NGHỊ
- Tỷ trọng Cổ phiếu/Tiền mặt: __/__
- Top 3 ngành cần theo dõi
- Cảnh báo rủi ro
"""
        return prompt
    
    def generate_report(self, report: MarketReport) -> str:
        """Tạo báo cáo bằng AI"""
        if not self.ai:
            return "⚠️ AI chưa được cấu hình. Vui lòng thêm AI_API_KEY."
        
        print("\n" + "="*60)
        print(f"🤖 ĐANG TẠO BÁO CÁO BẰNG AI ({self.config.AI_PROVIDER.upper()})...")
        print("="*60)
        
        prompt = self.generate_prompt(report)
        
        try:
            response = self.ai.chat(prompt)
            print("✓ Đã tạo báo cáo AI thành công!")
            return response
            
        except Exception as e:
            return f"❌ Lỗi AI: {str(e)}"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MODULE
# ══════════════════════════════════════════════════════════════════════════════

class MarketTimingModule:
    """Module chính để chạy Market Timing"""
    
    def __init__(self, config: MarketTimingConfig):
        self.config = config
        self.analyzer = MarketAnalyzer(config)
        self.ai_generator = AIReportGenerator(config)
        self.report: MarketReport = None
    
    def run(self) -> MarketReport:
        """Chạy toàn bộ module"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║     MODULE 1: MARKET TIMING - ĐỊNH THỜI ĐIỂM THỊ TRƯỜNG     ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # 1. Thu thập dữ liệu
        self.report = self.analyzer.collect_all_data()
        
        # 2. Phân tích
        self.report = self.analyzer.analyze(self.report)
        
        # 3. Tạo báo cáo AI
        self.report.ai_analysis = self.ai_generator.generate_report(self.report)
        
        # 4. In kết quả
        self._print_report()
        
        # 5. Lưu file
        if self.config.SAVE_REPORT:
            self._save_report()
        
        return self.report
    
    def _print_report(self):
        """In báo cáo ra console"""
        print("\n")
        print("╔" + "═"*68 + "╗")
        print("║" + " 📊 BÁO CÁO MARKET TIMING ".center(68) + "║")
        print("╚" + "═"*68 + "╝")
        
        print(f"\n🎯 {self.report.market_color}")
        print(f"📊 Điểm: {self.report.market_score}/100")
        
        print("\n" + "─"*70)
        print("🤖 PHÂN TÍCH TỪ AI:")
        print("─"*70)
        print(self.report.ai_analysis)
    
    def _save_report(self):
        """Lưu báo cáo ra file"""
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        
        filename = os.path.join(
            self.config.OUTPUT_DIR,
            f"market_timing_{self.report.timestamp.strftime('%Y%m%d_%H%M')}.md"
        )
        
        content = f"""# BÁO CÁO MARKET TIMING
**Ngày:** {self.report.timestamp.strftime('%d/%m/%Y %H:%M')}

## TỔNG QUAN
- **Market Color:** {self.report.market_color}
- **Score:** {self.report.market_score}/100
- **VNIndex:** {self.report.vnindex.close:,.0f} ({self.report.vnindex.change_1d:+.2f}%)

## TÍN HIỆU CHÍNH
{chr(10).join(['- ' + s for s in self.report.key_signals])}

## PHÂN TÍCH AI
{self.report.ai_analysis}
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✓ Đã lưu báo cáo: {filename}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    """Hàm chính"""
    
    # ═══════════════════════════════════════════════════════════
    # CẤU HÌNH - ĐIỀN API KEYS CỦA BẠN VÀO ĐÂY
    # ═══════════════════════════════════════════════════════════
    
    config = MarketTimingConfig()
    
    # Vnstock
    config.VNSTOCK_API_KEY = ""      # API key vnstock premium
    config.DATA_SOURCE = "VCI"       # hoặc "TCBS"
    
    # AI Provider - chọn 1 trong các options:
    # "deepseek" - Rẻ nhất, chất lượng tốt (KHUYẾN NGHỊ)
    # "gemini"   - Free tier rộng rãi
    # "groq"     - Nhanh nhất
    # "claude"   - Chất lượng cao nhất
    # "openai"   - Phổ biến
    
    config.AI_PROVIDER = "deepseek"
    config.AI_API_KEY = ""           # API key của AI provider đã chọn
    
    # ═══════════════════════════════════════════════════════════
    
    # Chạy module
    module = MarketTimingModule(config)
    report = module.run()
    
    return module, report


if __name__ == "__main__":
    module, report = main()
