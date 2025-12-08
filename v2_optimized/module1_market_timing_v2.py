#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     MODULE 1 v2: MARKET TIMING - ĐỊNH THỜI ĐIỂM THỊ TRƯỜNG                  ║
║              Sử dụng Config chung + Volume Profile + vnstock_ta             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  - Đọc API keys từ config.py (không hardcode)                                ║
║  - Tích hợp Volume Profile (POC, VAH, VAL)                                  ║
║  - Sử dụng vnstock_ta cho Technical Analysis                                 ║
║  - Chỉ phân tích TOP 3 ngành (chi tiết chuyển cho Module 2)                 ║
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

# Import từ các module chung
from config import get_config, APIKeys, UnifiedConfig
from data_collector import EnhancedDataCollector, get_data_collector, EnhancedStockData
from volume_profile import VolumeProfileFormatter, calculate_volume_profile

# Import AI Provider
try:
    from .ai_providers import AIProvider, AIConfig
    HAS_AI = True
except ImportError:
    try:
        from ai_providers import AIProvider, AIConfig
        HAS_AI = True
    except ImportError:
        HAS_AI = False
        print("⚠️ Could not import AIProvider")


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG ADAPTER
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class MarketTimingConfig:
    """Config cho Module 1 - tạo từ UnifiedConfig"""
    
    # API (đọc từ config.py)
    VNSTOCK_API_KEY: str = ""
    DATA_SOURCE: str = "VCI"
    
    # Indices
    MAIN_INDEX: str = "VNINDEX"
    COMPARISON_INDICES: List[str] = field(default_factory=lambda: ["VN30", "VN100"])
    
    # Sector indices - CHỈ 7 NGÀNH HỢP LỆ (đã test)
    SECTOR_INDICES: List[str] = field(default_factory=lambda: [
        "VNFIN", "VNREAL", "VNMAT", "VNIT",
        "VNHEAL", "VNCOND", "VNCONS"
    ])
    
    # Lookback
    LOOKBACK_DAYS: int = 120
    API_DELAY: float = 0.5
    
    # AI
    AI_PROVIDER: str = ""
    AI_API_KEY: str = ""
    AI_MODEL: str = ""
    AI_MAX_TOKENS: int = 8192
    AI_TEMPERATURE: float = 0.1
    
    # Volume Profile
    ENABLE_VOLUME_PROFILE: bool = True
    VP_LOOKBACK_DAYS: int = 20
    
    # Output
    OUTPUT_DIR: str = "./output"
    SAVE_REPORT: bool = True


def create_config_from_unified() -> MarketTimingConfig:
    """Tạo MarketTimingConfig từ UnifiedConfig trong config.py"""
    unified = get_config()
    
    config = MarketTimingConfig()
    config.VNSTOCK_API_KEY = unified.get_vnstock_key()
    config.DATA_SOURCE = unified.get_data_source()
    config.API_DELAY = unified.rate_limit.API_DELAY
    
    ai_provider, ai_key = unified.get_ai_provider()
    config.AI_PROVIDER = ai_provider
    config.AI_API_KEY = ai_key
    
    config.LOOKBACK_DAYS = unified.analysis.LOOKBACK_DAYS
    config.OUTPUT_DIR = unified.output.OUTPUT_DIR
    config.SAVE_REPORT = unified.output.SAVE_REPORTS
    
    config.ENABLE_VOLUME_PROFILE = True
    config.VP_LOOKBACK_DAYS = unified.volume_profile.LOOKBACK_DAYS
    
    return config


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

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


@dataclass
class MoneyFlow:
    """Dòng tiền"""
    foreign_buy: float = 0.0
    foreign_sell: float = 0.0
    foreign_net: float = 0.0
    proprietary_net: float = 0.0
    total_value: float = 0.0
    top_foreign_buy: List[Tuple[str, float]] = field(default_factory=list)
    top_foreign_sell: List[Tuple[str, float]] = field(default_factory=list)


@dataclass
class SectorData:
    """Dữ liệu ngành (rút gọn cho Module 1)"""
    code: str
    name: str
    change_1d: float = 0.0


@dataclass
class MarketReport:
    """Báo cáo tổng hợp"""
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Index data (sử dụng EnhancedStockData)
    vnindex: EnhancedStockData = None
    vn30: EnhancedStockData = None
    vn100: EnhancedStockData = None
    
    # Market internals
    breadth: MarketBreadth = field(default_factory=MarketBreadth)
    money_flow: MoneyFlow = field(default_factory=MoneyFlow)
    
    # Top 3 sectors only (chi tiết chuyển cho Module 2)
    top_sectors: List[SectorData] = field(default_factory=list)
    weak_sectors: List[SectorData] = field(default_factory=list)
    
    # Analysis
    market_color: str = "🟡 VÀNG"
    market_score: int = 50
    trend_status: str = "SIDEWAY"
    key_signals: List[str] = field(default_factory=list)
    
    # AI
    ai_analysis: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# SECTOR NAMES
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# MARKET ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class MarketTimingAnalyzer:
    """Phân tích Market Timing với Volume Profile"""
    
    def __init__(self, config: MarketTimingConfig):
        self.config = config
        self.collector = get_data_collector(
            enable_volume_profile=config.ENABLE_VOLUME_PROFILE
        )
    
    def collect_data(self) -> MarketReport:
        """Thu thập dữ liệu"""
        print("\n" + "="*60)
        print("📊 THU THẬP DỮ LIỆU THỊ TRƯỜNG")
        print("="*60)
        
        report = MarketReport()
        
        # 1. VNIndex với Volume Profile
        print("\n[1/5] VN-INDEX...")
        report.vnindex = self.collector.get_stock_data(
            "VNINDEX", 
            lookback_days=self.config.LOOKBACK_DAYS,
            include_vp=self.config.ENABLE_VOLUME_PROFILE
        )
        
        if report.vnindex.price > 0:
            print(f"   ✓ VNIndex: {report.vnindex.price:,.0f} ({report.vnindex.change_1d:+.2f}%)")
            if report.vnindex.poc > 0:
                print(f"   📊 Volume Profile: POC={report.vnindex.poc:,.0f} | "
                      f"VA={report.vnindex.val:,.0f}-{report.vnindex.vah:,.0f}")
        
        # 2. VN30
        print("\n[2/5] VN30...")
        report.vn30 = self.collector.get_stock_data("VN30", include_vp=False)
        if report.vn30.price > 0:
            print(f"   ✓ VN30: {report.vn30.price:,.0f} ({report.vn30.change_1d:+.2f}%)")
        
        # 3. VN100
        print("\n[3/5] VN100...")
        report.vn100 = self.collector.get_stock_data("VN100", include_vp=False)
        if report.vn100 and report.vn100.price > 0:
            print(f"   ✓ VN100: {report.vn100.price:,.0f} ({report.vn100.change_1d:+.2f}%)")
        
        # 4. Market Internals (Breadth + Money Flow)
        print("\n[4/5] MARKET INTERNALS (Breadth & Money Flow)...")
        report.breadth, report.money_flow = self._get_market_internals()
        
        print(f"   ✓ Breadth: Tăng={report.breadth.advances}, Giảm={report.breadth.declines}")
        print(f"   ✓ Money Flow: KN={report.money_flow.foreign_net:+.1f}tỷ")
        
        # 6. Top 3 sectors (chỉ lấy để hiển thị, chi tiết ở Module 2)
        print("\n[6/6] TOP NGÀNH...")
        all_sectors = []
        for code in self.config.SECTOR_INDICES:
            data = self.collector.get_stock_data(code, lookback_days=30, include_vp=False)
            if data.price > 0:
                sector = SectorData(
                    code=code,
                    name=SECTOR_NAMES.get(code, code),
                    change_1d=data.change_1d
                )
                all_sectors.append(sector)
                print(f"   ✓ {code}: {data.change_1d:+.2f}%")
        
        # Sort và lấy top 3 / weak 3
        all_sectors.sort(key=lambda x: x.change_1d, reverse=True)
        report.top_sectors = all_sectors[:3]
        report.weak_sectors = all_sectors[-3:] if len(all_sectors) >= 3 else []
        
        return report
    
    def _get_market_internals(self) -> Tuple[MarketBreadth, MoneyFlow]:
        """
        Lấy độ rộng thị trường và dòng tiền từ TOÀN BỘ thị trường (HOSE)
        Sử dụng API trading.foreign_trade() cho dữ liệu khối ngoại chính xác
        """
        breadth = MarketBreadth()
        money_flow = MoneyFlow()
        
        try:
            from vnstock import Vnstock, Listing
            from datetime import datetime, timedelta
            
            # ═══════════════════════════════════════════════════════════════════════
            # 1. LẤY DANH SÁCH CỔ PHIẾU HOSE
            # ═══════════════════════════════════════════════════════════════════════
            listing = Listing()
            try:
                df_sym = listing.symbols_by_exchange()
                hose_stocks = df_sym[
                    (df_sym['exchange'] == 'HSX') & 
                    (df_sym['type'] == 'STOCK')
                ]['symbol'].tolist()
                print(f"   📊 Scanning {len(hose_stocks)} HOSE stocks (Filtered by HSX/STOCK)...")
            except Exception as e:
                print(f"   ⚠️ symbols_by_exchange failed ({e}), trying fallback...")
                all_stocks = listing.all_symbols()
                hose_stocks = all_stocks[all_stocks['symbol'].str.len() == 3]['symbol'].tolist()
            
            # ═══════════════════════════════════════════════════════════════════════
            # 2. LẤY KHỐI NGOẠI TỪ VNINDEX - trading.foreign_trade() (CHÍNH XÁC)
            # ═══════════════════════════════════════════════════════════════════════
            try:
                today = datetime.now().strftime('%Y-%m-%d')
                # Lấy 3 ngày gần nhất để đảm bảo có dữ liệu (cuối tuần không có giao dịch)
                start_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
                
                # Sử dụng VNINDEX để lấy tổng dòng tiền cả thị trường
                stock = Vnstock().stock(symbol='VNINDEX', source=self.config.DATA_SOURCE)
                foreign_df = stock.trading.foreign_trade(start=start_date, end=today)
                
                if foreign_df is not None and not foreign_df.empty:
                    # Lấy dữ liệu ngày gần nhất (cuối cùng)
                    latest = foreign_df.iloc[-1]
                    
                    # fr_buy_value, fr_sell_value đã tính bằng VND
                    money_flow.foreign_buy = latest.get('fr_buy_value', 0) / 1e9  # Convert to tỷ
                    money_flow.foreign_sell = latest.get('fr_sell_value', 0) / 1e9
                    money_flow.foreign_net = latest.get('fr_net_value', 0) / 1e9
                    
                    print(f"   ✓ Foreign Trade API: Buy={money_flow.foreign_buy:.1f}tỷ, Sell={money_flow.foreign_sell:.1f}tỷ, Net={money_flow.foreign_net:+.1f}tỷ")
                else:
                    print(f"   ⚠️ foreign_trade() returned empty, fallback to price_board calculation")
                    raise Exception("Empty foreign_trade data")
                    
            except Exception as e:
                print(f"   ⚠️ foreign_trade API failed: {e}, calculating from price_board...")
                # Fallback: Tính từ price_board (code cũ)
                money_flow = self._calculate_foreign_from_price_board(hose_stocks)
            
            # ═══════════════════════════════════════════════════════════════════════
            # 3. TÍNH BREADTH TỪ PRICE_BOARD
            # ═══════════════════════════════════════════════════════════════════════
            chunk_size = 100
            all_dfs = []
            stock = Vnstock().stock(symbol='VCB', source=self.config.DATA_SOURCE)
            
            for i in range(0, len(hose_stocks), chunk_size):
                chunk = hose_stocks[i:i+chunk_size]
                try:
                    df = stock.trading.price_board(symbols_list=chunk)
                    if df is not None and not df.empty:
                        all_dfs.append(df)
                except Exception:
                    pass
            
            if all_dfs:
                full_df = pd.concat(all_dfs, ignore_index=True)
                
                for _, row in full_df.iterrows():
                    try:
                        match_price = row.get(('match', 'match_price'), 0)
                        ref_price = row.get(('listing', 'ref_price'), 0)
                        ceil_price = row.get(('listing', 'ceil_price'), 0)
                        floor_price = row.get(('listing', 'floor_price'), 0)
                        
                        if match_price == 0: match_price = ref_price
                        
                        if match_price > 0 and ref_price > 0:
                            change = match_price - ref_price
                            
                            if match_price == ceil_price: breadth.ceiling += 1
                            if match_price == floor_price: breadth.floor += 1
                            
                            if change > 0: breadth.advances += 1
                            elif change < 0: breadth.declines += 1
                            else: breadth.unchanged += 1
                    except Exception:
                        continue
            
            print(f"   ✓ Breadth: Tăng={breadth.advances}, Giảm={breadth.declines}")
            print(f"   ✓ Money Flow: KN={money_flow.foreign_net:+.1f}tỷ")
            
        except Exception as e:
            print(f"   ⚠️ Lỗi market internals: {e}")
            breadth.advances = 100
            breadth.declines = 100
        
        return breadth, money_flow
    
    def _calculate_foreign_from_price_board(self, hose_stocks: List[str]) -> MoneyFlow:
        """
        Fallback: Tính dòng tiền khối ngoại từ price_board (kém chính xác hơn)
        """
        money_flow = MoneyFlow()
        
        try:
            from vnstock import Vnstock
            
            chunk_size = 100
            all_dfs = []
            stock = Vnstock().stock(symbol='VCB', source=self.config.DATA_SOURCE)
            
            for i in range(0, len(hose_stocks), chunk_size):
                chunk = hose_stocks[i:i+chunk_size]
                try:
                    df = stock.trading.price_board(symbols_list=chunk)
                    if df is not None and not df.empty:
                        all_dfs.append(df)
                except Exception:
                    pass
            
            if all_dfs:
                full_df = pd.concat(all_dfs, ignore_index=True)
                
                for _, row in full_df.iterrows():
                    try:
                        f_buy = row.get(('match', 'foreign_buy_value'), 0)
                        f_sell = row.get(('match', 'foreign_sell_value'), 0)
                        
                        if pd.isna(f_buy): f_buy = 0
                        if pd.isna(f_sell): f_sell = 0
                        
                        money_flow.foreign_buy += f_buy
                        money_flow.foreign_sell += f_sell
                    except Exception:
                        continue
                
                money_flow.foreign_buy /= 1e9
                money_flow.foreign_sell /= 1e9
                money_flow.foreign_net = money_flow.foreign_buy - money_flow.foreign_sell
                
        except Exception as e:
            print(f"   ⚠️ Fallback failed: {e}")
        
        return money_flow
    
    def analyze(self, report: MarketReport) -> MarketReport:
        """Phân tích và tính điểm"""
        print("\n" + "="*60)
        print("🔍 PHÂN TÍCH THỊ TRƯỜNG")
        print("="*60)
        
        vni = report.vnindex
        if vni is None or vni.price == 0:
            return report
        
        signals = []
        score = 0
        
        # 1. Price vs MA (30 điểm) - Logic đã sửa
        above_ma20 = vni.price > vni.ma20 if vni.ma20 > 0 else False
        above_ma50 = vni.price > vni.ma50 if vni.ma50 > 0 else False
        ma20_above_ma50 = vni.ma20 > vni.ma50 if (vni.ma20 > 0 and vni.ma50 > 0) else False
        
        if above_ma20 and above_ma50 and ma20_above_ma50:
            score += 30
            signals.append(f"✅ Uptrend mạnh: Giá({vni.price:,.0f}) > MA20({vni.ma20:,.0f}) > MA50({vni.ma50:,.0f})")
        elif above_ma20 and above_ma50:
            score += 25
            signals.append(f"✅ Bullish: Giá({vni.price:,.0f}) > MA20({vni.ma20:,.0f}) & MA50({vni.ma50:,.0f})")
        elif above_ma50:
            score += 15
            signals.append(f"⚠️ Giá trên MA50({vni.ma50:,.0f}) nhưng dưới MA20")
        elif above_ma20:
            score += 10
            signals.append(f"⚠️ Giá trên MA20 nhưng dưới MA50")
        elif vni.price < vni.ma20 and vni.price < vni.ma50:
            score -= 30
            signals.append(f"❌ Downtrend: Giá < MA20 & MA50")
        else:
            signals.append(f"➖ MA chưa rõ xu hướng")
        
        # 2. RSI (15 điểm)
        if vni.rsi_14 > 70:
            score -= 10
            signals.append(f"⚠️ RSI quá mua: {vni.rsi_14:.0f}")
        elif vni.rsi_14 < 30:
            score += 10
            signals.append(f"📈 RSI quá bán: {vni.rsi_14:.0f}")
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
            score += 10
            signals.append(f"✅ Trend mạnh (ADX={vni.adx:.0f})")
        else:
            signals.append(f"➖ Trend yếu (ADX={vni.adx:.0f})")
        
        # 5. Breadth (15 điểm)
        ad = report.breadth.ad_ratio
        if ad >= 1.5:
            score += 15
            signals.append(f"✅ Breadth rất tốt (A/D={ad:.2f})")
        elif ad >= 1:
            score += 5
            signals.append(f"✅ Breadth tích cực (A/D={ad:.2f})")
        else:
            score -= 10
            signals.append(f"❌ Breadth yếu (A/D={ad:.2f})")
        
        # 6. Money Flow (15 điểm)
        mf = report.money_flow
        if mf.foreign_net > 0:
            score += 10
            signals.append(f"✅ Khối ngoại mua ròng ({mf.foreign_net:+.0f} tỷ)")
        else:
            score -= 10
            signals.append(f"❌ Khối ngoại bán ({mf.foreign_net:+.0f} tỷ)")
        
        # 7. Volume Profile signals (bonus)
        if vni.poc > 0:
            if vni.price_vs_va == "ABOVE_VA":
                score += 5
                signals.append(f"📈 Giá TRÊN Value Area (VAH={vni.vah:,.0f})")
            elif vni.price_vs_va == "BELOW_VA":
                score -= 5
                signals.append(f"📉 Giá DƯỚI Value Area (VAL={vni.val:,.0f})")
            else:
                signals.append(f"📊 Giá TRONG Value Area ({vni.val:,.0f}-{vni.vah:,.0f})")
        
        # Market Color
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
        
        # Print
        print(f"\n📊 ĐIỂM THỊ TRƯỜNG: {report.market_score}/100")
        print(f"🎯 {report.market_color}")
        for sig in signals:
            print(f"   {sig}")
        
        return report


# ══════════════════════════════════════════════════════════════════════════════
# AI GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class MarketTimingAIGenerator:
    """Tạo báo cáo AI với Gemini 3.0 Pro"""
    
    SYSTEM_PROMPT = "Bạn là chuyên gia phân tích chứng khoán Việt Nam theo trường phái VSA."
    
    def __init__(self, config: MarketTimingConfig):
        self.config = config
        self.ai = self._init_ai()
    
    def _init_ai(self) -> Optional[AIProvider]:
        if not self.config.AI_API_KEY or AIProvider is None:
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
            print(f"⚠️ Lỗi AI: {e}")
            return None
    
    def generate_prompt(self, report: MarketReport, history_context: str = "") -> str:
        """Tạo prompt với Volume Profile và History"""
        vni = report.vnindex
        vn30 = report.vn30
        
        # Volume Profile section
        vp_section = ""
        if vni and vni.poc > 0:
            vp_section = f"""
📊 VOLUME PROFILE (20 ngày):
   - POC (Point of Control): {vni.poc:,.0f}
   - Value Area: {vni.val:,.0f} - {vni.vah:,.0f}
   - Giá vs POC: {vni.price_vs_poc}
   - Giá vs VA: {vni.price_vs_va}
   - VP Support: {', '.join([f'{p:,.0f}' for p in vni.vp_support[:3]]) if vni.vp_support else 'N/A'}
   - VP Resistance: {', '.join([f'{p:,.0f}' for p in vni.vp_resistance[:3]]) if vni.vp_resistance else 'N/A'}
"""
        
        # Top sectors
        top_str = "\n".join([f"   - {s.name}: {s.change_1d:+.2f}%" for s in report.top_sectors])
        weak_str = "\n".join([f"   - {s.name}: {s.change_1d:+.2f}%" for s in report.weak_sectors])
        
        prompt = f"""
═══════════════════════════════════════════════════════════════
DỮ LIỆU THỊ TRƯỜNG - {report.timestamp.strftime('%d/%m/%Y %H:%M')}
═══════════════════════════════════════════════════════════════

{history_context}

📈 VN-INDEX:
   - Giá: {vni.price:,.0f} | Thay đổi: {vni.change_1d:+.2f}%
   - OHLC: O={vni.open:,.0f} H={vni.high:,.0f} L={vni.low:,.0f} C={vni.price:,.0f}
   - MA20: {vni.ma20:,.0f} | MA50: {vni.ma50:,.0f}
   - VỊ TRÍ GIÁ: {"TRÊN MA20" if vni.price > vni.ma20 else "DƯỚI MA20"}, {"TRÊN MA50" if vni.price > vni.ma50 else "DƯỚI MA50"}
   - RSI(14): {vni.rsi_14:.1f}
   - MACD Histogram: {vni.macd_hist:+.2f}
   - ADX: {vni.adx:.1f}
   - Volume Ratio: {vni.volume_ratio:.2f}x
{vp_section}
📊 VN30: {vn30.price:,.0f} ({vn30.change_1d:+.2f}%)

📉 ĐỘ RỘNG: Tăng={report.breadth.advances} | Giảm={report.breadth.declines} | A/D={report.breadth.ad_ratio:.2f}

💰 DÒNG TIỀN:
   - Khối ngoại: {report.money_flow.foreign_net:+.1f} tỷ
   - Top mua: {', '.join([f'{s}({v:+.0f})' for s,v in report.money_flow.top_foreign_buy])}
   - Top bán: {', '.join([f'{s}({v:+.0f})' for s,v in report.money_flow.top_foreign_sell])}

🏭 TOP 3 NGÀNH MẠNH:
{top_str}

📉 TOP 3 NGÀNH YẾU:
{weak_str}

🎯 ĐÁNH GIÁ: {report.market_color} | Score: {report.market_score}/100

═══════════════════════════════════════════════════════════════

YÊU CẦU: Viết BÁO CÁO CHIẾN LƯỢC NGÀY với cấu trúc:

1. TỔNG QUAN THỊ TRƯỜNG
   - Xu hướng chính, phân tích VSA
   - Đánh giá sự thay đổi so với các phiên trước (dựa trên Historical Context)
   
2. PHÂN TÍCH CẤU TRÚC
   - So sánh VN30 vs VNIndex
   
3. VOLUME PROFILE INSIGHTS
   - Ý nghĩa POC, Value Area
   - Support/Resistance từ VP
   
4. DÒNG TIỀN
   - Hành động Khối ngoại
   
5. KỊCH BẢN "WHAT-IF" (3 kịch bản với xác suất %)
   - Điều kiện kích hoạt CỤ THỂ
   - Hành động tương ứng
   
6. KHUYẾN NGHỊ
   - Tỷ trọng CP/Tiền mặt
"""
        return prompt
    
    def generate(self, report: MarketReport, history_context: str = "") -> str:
        """Tạo báo cáo AI"""
        if not self.ai:
            return "⚠️ AI chưa được cấu hình. Điền API key vào config.py"
        
        print("\n" + "="*60)
        print(f"🤖 ĐANG TẠO BÁO CÁO AI ({self.config.AI_PROVIDER.upper()})...")
        print("="*60)
        
        prompt = self.generate_prompt(report, history_context)
        
        try:
            response = self.ai.chat(prompt)
            print("✓ Hoàn thành!")
            return response
        except Exception as e:
            return f"❌ Lỗi: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# MAIN MODULE
# ══════════════════════════════════════════════════════════════════════════════

class MarketTimingModule:
    """Module 1: Market Timing"""
    
    def __init__(self, config: MarketTimingConfig = None):
        self.config = config or create_config_from_unified()
        self.analyzer = MarketTimingAnalyzer(self.config)
        self.ai_generator = MarketTimingAIGenerator(self.config)
        self.report: MarketReport = None
    
    def run(self, history_context: str = "") -> MarketReport:
        """Chạy module"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║     MODULE 1: MARKET TIMING + VOLUME PROFILE                 ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # 1. Thu thập
        self.report = self.analyzer.collect_data()
        
        # 2. Phân tích
        self.report = self.analyzer.analyze(self.report)
        
        # 3. AI
        self.report.ai_analysis = self.ai_generator.generate(self.report, history_context)
        
        # 4. Print
        self._print_report()
        
        # 5. Save
        if self.config.SAVE_REPORT:
            self._save_report()
        
        return self.report
    
    def _print_report(self):
        """In báo cáo"""
        print("\n" + "─"*70)
        print("🤖 PHÂN TÍCH TỪ AI:")
        print("─"*70)
        print(self.report.ai_analysis)
    
    def _save_report(self):
        """Lưu báo cáo"""
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        
        filename = os.path.join(
            self.config.OUTPUT_DIR,
            f"market_timing_{self.report.timestamp.strftime('%Y%m%d_%H%M')}.md"
        )
        
        vni = self.report.vnindex
        
        content = f"""# BÁO CÁO MARKET TIMING
**Ngày:** {self.report.timestamp.strftime('%d/%m/%Y %H:%M')}

## TỔNG QUAN
- **Market Color:** {self.report.market_color}
- **Score:** {self.report.market_score}/100
- **VNIndex:** {vni.price:,.0f} ({vni.change_1d:+.2f}%)

## VOLUME PROFILE
- **POC:** {vni.poc:,.0f}
- **Value Area:** {vni.val:,.0f} - {vni.vah:,.0f}
- **Position:** {vni.price_vs_va}

## TÍN HIỆU CHÍNH
{chr(10).join(['- ' + s for s in self.report.key_signals])}

## PHÂN TÍCH AI
{self.report.ai_analysis}
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"\n✓ Đã lưu: {filename}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    module = MarketTimingModule()
    report = module.run()