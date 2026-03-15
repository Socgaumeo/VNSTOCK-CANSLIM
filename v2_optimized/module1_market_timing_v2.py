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
import importlib.util
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


def _load_kebab_module(module_path: str, module_name: str):
    """Helper to import kebab-case module files."""
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    except Exception as e:
        print(f"⚠️ Could not load {module_name}: {e}")
    return None


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
    COMPARISON_INDICES: List[str] = field(default_factory=lambda: ["VN30", "VN100", "VNMID", "VNSML"])
    
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
    
    # Mid-Session flag
    IS_MID_SESSION: bool = False
    
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
    # Extended breadth fields (Phase 02)
    breadth_thrust: float = 0.0
    net_breadth_score: float = 0.0
    breadth_signal: str = ""

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
    vnmid: EnhancedStockData = None
    vnsml: EnhancedStockData = None
    
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

    # Valuation context from vnstock_data (PE/PB)
    valuation_context: Optional[Dict] = None


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
    'VNMID': 'VNMidCap',
    'VNSML': 'VNSmallCap',
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
        print("\n[1/7] VN-INDEX...")
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
        print("\n[2/7] VN30...")
        report.vn30 = self.collector.get_stock_data("VN30", include_vp=False)
        if report.vn30.price > 0:
            print(f"   ✓ VN30: {report.vn30.price:,.0f} ({report.vn30.change_1d:+.2f}%)")
        
        # 3. VN100
        print("\n[3/7] VN100...")
        report.vn100 = self.collector.get_stock_data("VN100", include_vp=False)
        if report.vn100 and report.vn100.price > 0:
            print(f"   ✓ VN100: {report.vn100.price:,.0f} ({report.vn100.change_1d:+.2f}%)")

        # 3b. VNMID (Mid Cap)
        print("\n[4/7] VNMID...")
        try:
            report.vnmid = self.collector.get_stock_data("VNMID", include_vp=False)
            if report.vnmid and report.vnmid.price > 0:
                print(f"   ✓ VNMID: {report.vnmid.price:,.0f} ({report.vnmid.change_1d:+.2f}%)")
            else:
                print("   ⚠️ VNMID: No data")
        except Exception as e:
            print(f"   ⚠️ VNMID failed: {e}")

        # 3c. VNSML (Small Cap)
        print("\n[5/7] VNSML...")
        try:
            report.vnsml = self.collector.get_stock_data("VNSML", include_vp=False)
            if report.vnsml and report.vnsml.price > 0:
                print(f"   ✓ VNSML: {report.vnsml.price:,.0f} ({report.vnsml.change_1d:+.2f}%)")
            else:
                print("   ⚠️ VNSML: No data")
        except Exception as e:
            print(f"   ⚠️ VNSML failed: {e}")

        # 4. Market Internals (Breadth + Money Flow)
        print("\n[6/7] MARKET INTERNALS (Breadth & Money Flow)...")
        report.breadth, report.money_flow = self._get_market_internals()
        
        print(f"   ✓ Breadth: Tăng={report.breadth.advances}, Giảm={report.breadth.declines}")
        print(f"   ✓ Money Flow: KN={report.money_flow.foreign_net:+.1f}tỷ")
        
        # 6. Top 3 sectors (chỉ lấy để hiển thị, chi tiết ở Module 2)
        print("\n[7/7] TOP NGÀNH...")
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
            #    KBS không hỗ trợ foreign_trade() → dùng VCI
            # ═══════════════════════════════════════════════════════════════════════
            # Chọn source hỗ trợ trading APIs (foreign_trade, price_board)
            # KBS không hỗ trợ → ưu tiên VCI, fallback TCBS
            trading_source = self.config.DATA_SOURCE
            if trading_source == "KBS":
                trading_source = "VCI"

            # ═══════════════════════════════════════════════════════════════════════
            # 2+3. TÍNH BREADTH + KHỐI NGOẠI TỪ PRICE_BOARD (1 lần fetch)
            #      KBS không hỗ trợ price_board() → dùng VCI
            # ═══════════════════════════════════════════════════════════════════════
            import time as _time
            chunk_size = 200  # VCI supports large chunks
            all_dfs = []
            stock = Vnstock().stock(symbol='VCB', source=trading_source)

            for i in range(0, len(hose_stocks), chunk_size):
                chunk = hose_stocks[i:i+chunk_size]
                try:
                    if i > 0:
                        _time.sleep(2)  # Tránh rate limit VCI
                    df = stock.trading.price_board(symbols_list=chunk)
                    if df is not None and not df.empty:
                        all_dfs.append(df)
                except Exception as chunk_err:
                    print(f"   ⚠️ price_board chunk {i//chunk_size+1} failed ({trading_source}): {chunk_err}")
                    _time.sleep(5)  # Wait longer on error

            if all_dfs:
                full_df = pd.concat(all_dfs, ignore_index=True)

                total_foreign_buy = 0
                total_foreign_sell = 0

                for _, row in full_df.iterrows():
                    try:
                        match_price = row.get(('match', 'match_price'), 0)
                        ref_price = row.get(('listing', 'ref_price'), 0)
                        # VCI dùng 'ceiling'/'floor', fallback 'ceil_price'/'floor_price'
                        ceil_price = row.get(('listing', 'ceiling'), 0) or row.get(('listing', 'ceil_price'), 0)
                        floor_price = row.get(('listing', 'floor'), 0) or row.get(('listing', 'floor_price'), 0)

                        if match_price == 0: match_price = ref_price

                        if match_price > 0 and ref_price > 0:
                            change = match_price - ref_price

                            if match_price == ceil_price: breadth.ceiling += 1
                            if match_price == floor_price: breadth.floor += 1

                            if change > 0: breadth.advances += 1
                            elif change < 0: breadth.declines += 1
                            else: breadth.unchanged += 1

                        # Foreign flow (from same price_board data)
                        f_buy = row.get(('match', 'foreign_buy_value'), 0)
                        f_sell = row.get(('match', 'foreign_sell_value'), 0)
                        if pd.isna(f_buy): f_buy = 0
                        if pd.isna(f_sell): f_sell = 0
                        total_foreign_buy += f_buy
                        total_foreign_sell += f_sell
                    except Exception:
                        continue

                # Convert to tỷ VND
                money_flow.foreign_buy = total_foreign_buy / 1e9
                money_flow.foreign_sell = total_foreign_sell / 1e9
                money_flow.foreign_net = money_flow.foreign_buy - money_flow.foreign_sell
            
            # Calculate extended breadth metrics (Phase 02)
            try:
                breadth_mod = _load_kebab_module(
                    os.path.join(os.path.dirname(__file__), "market-breadth-analyzer.py"),
                    "market_breadth_analyzer"
                )
                if breadth_mod:
                    analyzer = breadth_mod.MarketBreadthAnalyzer()
                    bm = analyzer.calculate_breadth_metrics(
                        advances=breadth.advances,
                        declines=breadth.declines,
                        unchanged=breadth.unchanged,
                        ceiling=breadth.ceiling,
                        floor=breadth.floor,
                    )
                    breadth.breadth_thrust = bm["breadth_thrust"]
                    breadth.net_breadth_score = bm["net_breadth_score"]
                    breadth.breadth_signal = bm["breadth_signal"]
                    thrust_note = " 🚀 Breadth Thrust!" if bm["is_thrust_bullish"] else ""
                    print(f"   ✓ Extended Breadth: A/D={bm['ad_ratio']:.2f} ({bm['breadth_signal']}){thrust_note}")
            except Exception as e:
                print(f"   ⚠️ Extended breadth failed: {e}")

            print(f"   ✓ Breadth: Tăng={breadth.advances}, Giảm={breadth.declines}")
            print(f"   ✓ Money Flow: KN={money_flow.foreign_net:+.1f}tỷ")

        except Exception as e:
            print(f"   ⚠️ Lỗi market internals: {e}")
            # Không dùng dummy data — giữ giá trị 0 để báo cáo biết dữ liệu bị thiếu

        return breadth, money_flow
    
    def _calculate_foreign_from_price_board(self, hose_stocks: List[str]) -> MoneyFlow:
        """
        Fallback: Tính dòng tiền khối ngoại từ price_board (kém chính xác hơn)
        KBS không hỗ trợ price_board() → dùng VCI/TCBS
        """
        money_flow = MoneyFlow()

        try:
            from vnstock import Vnstock

            # KBS không hỗ trợ price_board → dùng VCI
            pb_source = self.config.DATA_SOURCE
            if pb_source == "KBS":
                pb_source = "VCI"

            chunk_size = 100
            all_dfs = []
            stock = Vnstock().stock(symbol='VCB', source=pb_source)
            
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
    
    def collect_technical_signals(self, report: MarketReport) -> MarketReport:
        """
        Thu thập tín hiệu kỹ thuật (KHÔNG chấm điểm - để AI chấm)
        Trả về report với key_signals được điền
        """
        print("\n" + "="*60)
        print("🔍 THU THẬP TÍN HIỆU KỸ THUẬT")
        print("="*60)
        
        vni = report.vnindex
        if vni is None or vni.price == 0:
            return report
        
        signals = []
        
        # 1. Price vs MA - Thu thập trạng thái
        above_ma20 = vni.price > vni.ma20 if vni.ma20 > 0 else False
        above_ma50 = vni.price > vni.ma50 if vni.ma50 > 0 else False
        ma20_above_ma50 = vni.ma20 > vni.ma50 if (vni.ma20 > 0 and vni.ma50 > 0) else False
        
        if above_ma20 and above_ma50 and ma20_above_ma50:
            signals.append(f"📊 MA Structure: Giá({vni.price:,.0f}) > MA20({vni.ma20:,.0f}) > MA50({vni.ma50:,.0f}) → Uptrend mạnh")
        elif above_ma20 and above_ma50:
            signals.append(f"📊 MA Structure: Giá > MA20 & MA50, nhưng MA20 < MA50 → Bullish có điều kiện")
        elif above_ma50:
            signals.append(f"📊 MA Structure: Giá > MA50 nhưng < MA20 → Pullback trong uptrend")
        elif above_ma20:
            signals.append(f"📊 MA Structure: Giá > MA20 nhưng < MA50 → Recovery yếu")
        elif vni.price < vni.ma20 and vni.price < vni.ma50:
            signals.append(f"📊 MA Structure: Giá < MA20 & MA50 → Downtrend rõ ràng")
        else:
            signals.append(f"📊 MA Structure: Chưa rõ xu hướng")
        
        # 2. RSI - Thu thập trạng thái
        if vni.rsi_14 > 70:
            signals.append(f"📈 RSI(14): {vni.rsi_14:.0f} → Quá mua, cần cẩn thận")
        elif vni.rsi_14 < 30:
            signals.append(f"📉 RSI(14): {vni.rsi_14:.0f} → Quá bán, cơ hội phục hồi")
        elif vni.rsi_14 > 50:
            signals.append(f"📊 RSI(14): {vni.rsi_14:.0f} → Tích cực (>50)")
        else:
            signals.append(f"📊 RSI(14): {vni.rsi_14:.0f} → Yếu (<50)")
        
        # 3. MACD - Thu thập trạng thái
        if vni.macd_hist > 0:
            signals.append(f"📈 MACD Histogram: {vni.macd_hist:+.2f} → Dương (momentum tăng)")
        else:
            signals.append(f"📉 MACD Histogram: {vni.macd_hist:+.2f} → Âm (momentum giảm)")
        
        # 4. ADX - Thu thập trạng thái
        if vni.adx > 25:
            signals.append(f"💪 ADX: {vni.adx:.0f} → Trend mạnh (>25)")
        else:
            signals.append(f"➖ ADX: {vni.adx:.0f} → Trend yếu, sideway")
        
        # 5. Breadth - Thu thập trạng thái
        ad = report.breadth.ad_ratio
        if ad >= 1.5:
            signals.append(f"🟢 Breadth: A/D={ad:.2f} → Độ rộng rất tốt (>1.5)")
        elif ad >= 1:
            signals.append(f"🟡 Breadth: A/D={ad:.2f} → Độ rộng tích cực (>1)")
        else:
            signals.append(f"🔴 Breadth: A/D={ad:.2f} → Độ rộng yếu (<1)")
        
        # 6. Money Flow - Thu thập trạng thái
        mf = report.money_flow
        if mf.foreign_net > 0:
            signals.append(f"💰 Khối ngoại: Mua ròng {mf.foreign_net:+.0f} tỷ")
        else:
            signals.append(f"💸 Khối ngoại: Bán ròng {mf.foreign_net:+.0f} tỷ")
        
        # 7. Volume Profile signals
        if vni.poc > 0:
            if vni.price_vs_va == "ABOVE_VA":
                signals.append(f"📊 Volume Profile: Giá TRÊN Value Area (VAH={vni.vah:,.0f}) → Bullish")
            elif vni.price_vs_va == "BELOW_VA":
                signals.append(f"📊 Volume Profile: Giá DƯỚI Value Area (VAL={vni.val:,.0f}) → Bearish")
            else:
                signals.append(f"📊 Volume Profile: Giá TRONG Value Area ({vni.val:,.0f}-{vni.vah:,.0f}) → Neutral")
        
        report.key_signals = signals
        
        # Print signals
        print("\n📋 CÁC TÍN HIỆU ĐÃ THU THẬP:")
        for sig in signals:
            print(f"   {sig}")
        
        return report


# ══════════════════════════════════════════════════════════════════════════════
# AI GENERATOR
# ══════════════════════════════════════════════════════════════════════════════

class MarketTimingAIGenerator:
    """Tạo báo cáo AI với Gemini 3.0 Pro - Bao gồm AI Scoring"""
    
    SYSTEM_PROMPT = """Bạn là chuyên gia phân tích chứng khoán Việt Nam theo trường phái VSA (Volume Spread Analysis).
Phong cách phân tích: Chuyên nghiệp, khách quan, đào sâu vào bản chất dòng tiền và cấu trúc giá.
Khi được yêu cầu chấm điểm market timing, hãy phân tích đa chiều trước khi đưa ra con số.
Luôn trả lời bằng tiếng Việt."""
    
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
    
    def _build_market_data_context(self, report: MarketReport) -> str:
        """Tạo context dữ liệu thị trường cho AI"""
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
        
        # Valuation section (PE/PB from vnstock_data)
        val_section = ""
        val = getattr(report, 'valuation_context', None)
        if val and val.get("pe_current"):
            pe = val["pe_current"]
            pe_avg = val.get("pe_1y_avg", pe)
            pe_min = val.get("pe_1y_min", "N/A")
            pe_max = val.get("pe_1y_max", "N/A")
            pb = val.get("pb_current", "N/A")
            val_section = f"""
📊 VALUATION (VN-Index):
   - PE hiện tại: {pe} (1Y: min={pe_min}, max={pe_max}, TB={pe_avg})
   - PB hiện tại: {pb}
   - Vùng PE: {"DƯỚI TB 1Y -> Undervalued" if pe < pe_avg * 0.9 else "TRÊN TB 1Y -> Expensive" if pe > pe_avg * 1.1 else "QUANH TB 1Y -> Fair value"}
"""

        # Signals section
        signals_str = "\n".join([f"   - {s}" for s in report.key_signals])
        
        # Top sectors
        top_str = "\n".join([f"   - {s.name}: {s.change_1d:+.2f}%" for s in report.top_sectors])
        weak_str = "\n".join([f"   - {s.name}: {s.change_1d:+.2f}%" for s in report.weak_sectors])
        
        context = f"""
📈 VN-INDEX:
   - Giá: {vni.price:,.0f} | Thay đổi: {vni.change_1d:+.2f}%
   - OHLC: O={vni.open:,.0f} H={vni.high:,.0f} L={vni.low:,.0f} C={vni.price:,.0f}
   - MA20: {vni.ma20:,.0f} | MA50: {vni.ma50:,.0f}
   - VỊ TRÍ GIÁ: {"TRÊN MA20" if vni.price > vni.ma20 else "DƯỚI MA20"}, {"TRÊN MA50" if vni.price > vni.ma50 else "DƯỚI MA50"}
   - RSI(14): {vni.rsi_14:.1f}
   - MACD Histogram: {vni.macd_hist:+.2f}
   - ADX: {vni.adx:.1f}
   - Volume Ratio: {vni.volume_ratio:.2f}x
{vp_section}{val_section}
📊 VN30: {vn30.price:,.0f} ({vn30.change_1d:+.2f}%)

📉 ĐỘ RỘNG: Tăng={report.breadth.advances} | Giảm={report.breadth.declines} | A/D={report.breadth.ad_ratio:.2f}

💰 DÒNG TIỀN:
   - Khối ngoại: {report.money_flow.foreign_net:+.1f} tỷ

🏭 TOP 3 NGÀNH MẠNH:
{top_str}

📉 TOP 3 NGÀNH YẾU:
{weak_str}

📋 TÍN HIỆU KỸ THUẬT:
{signals_str}
"""
        return context

    def score_market(self, report: MarketReport, history_context: str = "") -> dict:
        """
        Yêu cầu AI chấm điểm thị trường
        
        Returns:
            dict với: score (0-100), color, trend, reasoning
        """
        if not self.ai:
            print("⚠️ AI không khả dụng, sử dụng fallback scoring")
            return self._fallback_scoring(report)
        
        print("\n" + "="*60)
        print(f"🤖 AI ĐANG CHẤM ĐIỂM THỊ TRƯỜNG ({self.config.AI_PROVIDER.upper()})...")
        print("="*60)
        
        market_data = self._build_market_data_context(report)
        mid_session_ctx = ""
        if self.config.IS_MID_SESSION:
            mid_session_ctx = """
⚠️ CHÚ Ý: ĐÂY LÀ DỮ LIỆU ĐANG TRONG PHIÊN (MID-SESSION). 
- Volume hiện tại chưa đầy đủ và CHƯA THỂ so sánh trực tiếp với trung bình 20 phiên.
- Hãy tập trung vào Cấu trúc giá, RSI, MACD và Độ rộng thị trường.
- Đánh giá Volume dựa trên tương quan với thời gian đã trôi qua của phiên giao dịch.
"""

        prompt = f"""
{mid_session_ctx}

═══════════════════════════════════════════════════════════════
DỮ LIỆU THỊ TRƯỜNG - {report.timestamp.strftime('%d/%m/%Y %H:%M')}
═══════════════════════════════════════════════════════════════

{history_context}

{market_data}

═══════════════════════════════════════════════════════════════

YÊU CẦU: Phân tích dữ liệu trên và CHẤM ĐIỂM THỊ TRƯỜNG.

TRẢ LỜI THEO ĐÚNG FORMAT JSON DƯỚI ĐÂY (VÀ CHỈ CÓ JSON):
```json
{{
    "score": <số từ 0-100>,
    "color": "<XANH hoặc VÀNG hoặc ĐỎ>",
    "trend": "<UPTREND hoặc SIDEWAY hoặc DOWNTREND>",
    "reasoning": "<giải thích ngắn gọn 1-2 câu quan trọng nhất>"
}}
```

HƯỚNG DẪN CHẤM ĐIỂM:
- 70-100: Thị trường mạnh, có thể tấn công mạnh → XANH
- 40-69: Thị trường trung bình, thận trọng → VÀNG  
- 0-39: Thị trường yếu, nên rút lui → ĐỎ

CÁC YẾU TỐ CẦN CÂN NHẮC:
1. Vị trí giá so với MA20/MA50 (quan trọng nhất)
2. RSI, MACD, ADX
3. Độ rộng thị trường (A/D ratio)
4. Dòng tiền khối ngoại
5. Volume Profile
6. So sánh với Historical Context (nếu có)

CHỈ TRẢ LỜI JSON, KHÔNG CÓ TEXT KHÁC.
"""
        
        try:
            import json
            import re
            
            response = self.ai.chat(prompt)
            
            # Parse JSON from response
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                
                # Validate and normalize
                score = int(result.get('score', 50))
                score = max(0, min(100, score))  # Clamp to 0-100
                
                color = result.get('color', 'VÀNG').upper()
                if 'XANH' in color:
                    color_full = "🟢 XANH - TẤN CÔNG"
                elif 'ĐỎ' in color:
                    color_full = "🔴 ĐỎ - RÚT LUI"
                else:
                    color_full = "🟡 VÀNG - PHÒNG THỦ"
                
                trend = result.get('trend', 'SIDEWAY').upper()
                if trend not in ['UPTREND', 'SIDEWAY', 'DOWNTREND']:
                    trend = 'SIDEWAY'
                
                reasoning = result.get('reasoning', '')
                
                print(f"✓ AI Score: {score}/100 | {color_full}")
                print(f"  Reasoning: {reasoning}")
                
                return {
                    'score': score,
                    'color': color_full,
                    'trend': trend,
                    'reasoning': reasoning
                }
            else:
                print("⚠️ Không parse được JSON, sử dụng fallback")
                return self._fallback_scoring(report)
                
        except Exception as e:
            print(f"⚠️ Lỗi AI scoring: {e}, sử dụng fallback")
            return self._fallback_scoring(report)
    
    def _fallback_scoring(self, report: MarketReport) -> dict:
        """
        Fallback scoring khi AI không khả dụng
        Sử dụng logic đơn giản hóa
        """
        vni = report.vnindex
        score = 50  # Base score
        
        # MA position (+/- 20)
        if vni.price > vni.ma20 and vni.price > vni.ma50:
            score += 20
        elif vni.price < vni.ma20 and vni.price < vni.ma50:
            score -= 20
        
        # RSI (+/- 10)
        if 50 < vni.rsi_14 < 70:
            score += 10
        elif vni.rsi_14 > 70:
            score -= 5
        elif vni.rsi_14 < 30:
            score += 5
        else:
            score -= 10
        
        # MACD (+/- 10)
        if vni.macd_hist > 0:
            score += 10
        else:
            score -= 10
        
        # Breadth (+/- 10)
        if report.breadth.ad_ratio >= 1:
            score += 10
        else:
            score -= 10
        
        score = max(0, min(100, score))
        
        if score >= 60:
            color = "🟢 XANH - TẤN CÔNG"
            trend = "UPTREND"
        elif score >= 40:
            color = "🟡 VÀNG - PHÒNG THỦ"
            trend = "SIDEWAY"
        else:
            color = "🔴 ĐỎ - RÚT LUI"
            trend = "DOWNTREND"
        
        print(f"⚠️ Fallback Score: {score}/100 | {color}")
        
        return {
            'score': score,
            'color': color,
            'trend': trend,
            'reasoning': "Fallback scoring (AI không khả dụng)"
        }
    

    def critique_market(self, report: MarketReport, peer_analysis: str) -> str:
        """
        [NEW] Claude critique Gemini's analysis
        """
        if not self.ai:
            return "⚠️ AI Reviewer not available."
            
        market_data = self._build_market_data_context(report)
        
        prompt = f"""
Bạn là Senior Portfolio Manager với 20 năm kinh nghiệm trên thị trường chứng khoán Việt Nam.
Dưới đây là dữ liệu thị trường và phân tích từ một Analyst (Junior) trong team.

NHIỆM VỤ CỦA BẠN:
1. Đọc dữ liệu thị trường (Fact).
2. Đọc phân tích của Analyst (Opinion).
3. Đưa ra nhận định ĐỘC LẬP của bạn (Senior Verdict).
4. Chỉ ra điểm bạn ĐỒNG Ý và KHÔNG ĐỒNG Ý với Analyst.
5. Kết luận cuối cùng về hành động cần làm.

═══════════════════════════════════════════════════════════════
DỮ LIỆU THỊ TRƯỜNG (FACT):
{market_data}
═══════════════════════════════════════════════════════════════

PHÂN TÍCH CỦA ANALYST (OPINION):
```
{peer_analysis}
```
═══════════════════════════════════════════════════════════════

HÃY VIẾT BÁO CÁO PHẢN BIỆN (DEBATE REPORT):
- Giọng văn: Chuyên gia, gãy gọn, tập trung vào rủi ro và cơ hội thực tế.
- Format:
  ### 🧐 Senior Review
  **1. Đánh giá tình hình:** (Nhận định riêng của bạn)
  **2. Critique Analyst:** (Đồng ý/Phản đối điểm nào? Analyst có lạc quan/bi quan quá không?)
  **3. Action Plan:** (Hành động cụ thể cho NĐT cá nhân)
  """
        return self.ai.chat(prompt)

    def risk_review(self, report: MarketReport, gemini_analysis: str, claude_critique: str) -> str:
        """
        [NEW] DeepSeek Risk Manager - Challenge both analyses
        Focus: Worst-case scenarios, hidden risks, contrarian view
        """
        if not self.ai:
            return "⚠️ AI Risk Manager not available."
            
        market_data = self._build_market_data_context(report)
        
        prompt = f"""
Bạn là CHIEF RISK OFFICER với 25 năm kinh nghiệm quản lý rủi ro trên thị trường chứng khoán Việt Nam.
Bạn vừa nhận được 2 báo cáo từ team phân tích:
1. Junior Analyst (Gemini) - Phân tích ban đầu
2. Senior Reviewer (Claude) - Phản biện

NHIỆM VỤ CỦA BẠN (Critical):
⚠️ BẠN ĐƯỢC THƯỞNG KHI TÌM RA RỦI RO MÀ CẢ 2 ANALYST ĐÃ BỎ SÓT.
⚠️ NẾU CẢ 2 ĐỒNG Ý VỚI NHAU → Tìm lý do họ có thể CÙNG SAI.

═══════════════════════════════════════════════════════════════
DỮ LIỆU THỊ TRƯỜNG (FACT):
{market_data}
═══════════════════════════════════════════════════════════════

PHÂN TÍCH CỦA JUNIOR ANALYST (Gemini):
```
{gemini_analysis[:3000]}
```

PHẢN BIỆN CỦA SENIOR REVIEWER (Claude):
```
{claude_critique[:3000]}
```
═══════════════════════════════════════════════════════════════

HÃY VIẾT BÁO CÁO RỦI RO (RISK REPORT):
Format:
### ⚠️ Risk Manager Review

**1. RỦI RO BỎ SÓT:**
- Liệt kê các rủi ro mà cả 2 analyst chưa đề cập hoặc đánh giá thấp

**2. WORST-CASE SCENARIO:**
- Kịch bản xấu nhất có thể xảy ra trong 1-2 tuần tới
- Trigger conditions (điều kiện kích hoạt)

**3. PHẢN BIỆN CẢ HAI:**
| Analyst | Điểm có thể sai | Lý do |
|---------|-----------------|-------|
| Gemini  | ...             | ...   |
| Claude  | ...             | ...   |

**4. VỊ THẾ PHÒNG THỦ TỐI ƯU:**
- Tỷ trọng tiền mặt khuyến nghị
- Cổ phiếu nên cắt giảm ngay
- Trigger để cắt lỗ toàn bộ

**5. CONSENSUS RECOMMENDATION:**
- Kết luận cuối cùng sau khi cân nhắc cả 3 góc nhìn
"""
        return self.ai.chat(prompt)

    def generate_prompt(self, report: MarketReport, history_context: str = "") -> str:

        """Tạo prompt cho báo cáo chi tiết (sau khi đã có score)"""
        market_data = self._build_market_data_context(report)
        mid_session_ctx = ""
        if self.config.IS_MID_SESSION:
            mid_session_ctx = """
⚠️ CHÚ Ý: ĐÂY LÀ BÁO CÁO GIỮA PHIÊN (MID-SESSION).
- Phân tích VSA cần lưu ý volume hiện tại chỉ mới phản ánh một phần phiên giao dịch.
- Ưu tiên kịch bản dựa trên biến động giá và sức mạnh nội tại (Relative Strength).
"""

        prompt = f"""
{mid_session_ctx}

═══════════════════════════════════════════════════════════════
DỮ LIỆU THỊ TRƯỜNG - {report.timestamp.strftime('%d/%m/%Y %H:%M')}
═══════════════════════════════════════════════════════════════

{history_context}

{market_data}

🎯 ĐÁNH GIÁ (AI Scoring): {report.market_color} | Score: {report.market_score}/100

═══════════════════════════════════════════════════════════════

YÊU CẦU: Viết BÁO CÁO CHIẾN LƯỢC NGÀY với cấu trúc:

1. TỔNG QUAN THỊ TRƯỜNG
   - Xu hướng chính, phân tích VSA.
   - **SO SÁNH CHI TIẾT** với phiên GẦN NHẤT (Latest Session) trong Historical Context: Những gì đã thay đổi? (Điểm số, Price Action, Volume).
   - Đánh giá tính liên tục của xu hướng.

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
        return self.ai.chat(prompt)

    def generate(self, report: MarketReport, history_context: str = "") -> Optional[str]:
        """Tao bao cao AI chi tiet. Returns None if AI unavailable/failed."""
        if not self.ai:
            print("⚠️ AI chua duoc cau hinh - rule-based fallback will be used")
            return None

        print("\n" + "="*60)
        print(f"AI DANG TAO BAO CAO ({self.config.AI_PROVIDER.upper()})...")
        print("="*60)

        prompt = self.generate_prompt(report, history_context)

        try:
            response = self.ai.chat(prompt)
            if response:
                print("Hoan thanh!")
            else:
                print("⚠️ AI returned None - rule-based fallback will be used")
            return response
        except Exception as e:
            print(f"⚠️ AI generate error: {e}")
            return None


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
    
    def run(self, history_context: str = "", memo=None) -> MarketReport:
        """Chạy module với AI-based scoring"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║     MODULE 1: MARKET TIMING + AI SCORING                     ║
╚══════════════════════════════════════════════════════════════╝
        """)

        # 1. Thu thập dữ liệu
        self.report = self.analyzer.collect_data()

        # 2. Thu thập tín hiệu kỹ thuật (không chấm điểm)
        self.report = self.analyzer.collect_technical_signals(self.report)

        # 2b. Valuation context from vnstock_data (PE/PB)
        try:
            val_data = memo.read("market_pe") if memo else None
            if val_data and val_data.get("pe_current"):
                self.report.valuation_context = val_data
                pe = val_data["pe_current"]
                pe_avg = val_data.get("pe_1y_avg", pe)
                if pe < pe_avg * 0.9:
                    self.report.key_signals.append(f"PE={pe:.1f} (DUOI TB 1Y: {pe_avg:.1f}) -> Undervalued")
                elif pe > pe_avg * 1.1:
                    self.report.key_signals.append(f"PE={pe:.1f} (TREN TB 1Y: {pe_avg:.1f}) -> Expensive")
                else:
                    self.report.key_signals.append(f"PE={pe:.1f} (TB 1Y: {pe_avg:.1f}) -> Fair value")
                print(f"  Valuation: PE={pe:.1f} (1Y avg={pe_avg:.1f})")
        except Exception:
            pass  # Silent fail

        # 3. AI Scoring - để AI chấm điểm thị trường
        ai_score_result = self.ai_generator.score_market(self.report, history_context)
        self.report.market_score = ai_score_result['score']
        self.report.market_color = ai_score_result['color']
        self.report.trend_status = ai_score_result['trend']

        # 3b. Bond health adjustment (half weight, max ±5 points)
        try:
            bond_ctx = memo.read("bonds") if memo else None
            if bond_ctx and bond_ctx.get("bond_health"):
                bond_adj = bond_ctx["bond_health"].get("score", 0) * 0.5
                if bond_adj != 0:
                    old_score = self.report.market_score
                    self.report.market_score = max(0, min(100, round(old_score + bond_adj)))
                    print(
                        f"  Bond adjustment: {old_score} -> {self.report.market_score} "
                        f"(bond_score={bond_ctx['bond_health'].get('score', 0):+.1f})"
                    )
        except Exception as e:
            print(f"[WARN] Bond adjustment failed (skipping): {e}")

        # 4. AI Generate detailed report
        self.report.ai_analysis = self.ai_generator.generate(self.report, history_context)

        # 5. Save to context memo
        if memo:
            self._save_to_memo(memo)

        # 6. Print
        self._print_report()

        # 7. Save
        if self.config.SAVE_REPORT:
            self._save_report()

        return self.report

    def _save_to_memo(self, memo) -> None:
        """Save market context to context memo for downstream modules."""
        try:
            rpt = self.report
            breadth = rpt.breadth
            vnindex = rpt.vnindex

            memo_data = {
                "market_color": rpt.market_color,
                "market_score": rpt.market_score,
                "trend_status": rpt.trend_status,
                "breadth": {
                    "advances": breadth.advances,
                    "declines": breadth.declines,
                    "unchanged": breadth.unchanged,
                    "ceiling": breadth.ceiling,
                    "floor": breadth.floor,
                    "ad_ratio": round(breadth.ad_ratio, 2),
                    "breadth_thrust": breadth.breadth_thrust,
                    "net_breadth_score": breadth.net_breadth_score,
                    "breadth_signal": breadth.breadth_signal,
                },
                "top_sectors": [s.code for s in rpt.top_sectors[:5]],
                "foreign_net": rpt.money_flow.foreign_net,
                "key_signals": rpt.key_signals[:10],
            }

            if vnindex:
                memo_data["vnindex_price"] = getattr(vnindex, "price", 0)
                memo_data["vnindex_rsi"] = getattr(vnindex, "rsi_14", 0)

            memo.save("module1", memo_data)
            print("✓ Module1 context saved to memo")
        except Exception as e:
            print(f"[WARN] Module1 memo save failed: {e}")
    
    def run_critique(self, report: MarketReport, peer_analysis: str) -> str:
        """
        [NEW] Chạy chế độ phản biện (không thu thập lại dữ liệu)
        """
        print(f"\n[{self.config.AI_PROVIDER.upper()}] Running Critique Mode...")
        
        # Gọi AI để critique
        critique = self.ai_generator.critique_market(report, peer_analysis)
        
        print(f"✓ Critique Complete ({len(critique)} chars)")
        return critique
    
    def run_risk_review(self, report: MarketReport, gemini_analysis: str, claude_critique: str) -> str:
        """
        [NEW] Chạy chế độ Risk Manager (DeepSeek)
        """
        print(f"\n[{self.config.AI_PROVIDER.upper()}] Running Risk Review Mode...")
        
        # Gọi AI để risk review
        risk_review = self.ai_generator.risk_review(report, gemini_analysis, claude_critique)
        
        print(f"✓ Risk Review Complete ({len(risk_review)} chars)")
        return risk_review
    
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