#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     TA ANALYZER - PHÂN TÍCH KỸ THUẬT SỬ DỤNG VNSTOCK_TA                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Sử dụng vnstock_ta v0.1.2 để tính các chỉ báo kỹ thuật:                    ║
║  - Trend: SMA, EMA, VWAP, ADX, PSAR, SuperTrend                             ║
║  - Momentum: RSI, MACD, Stochastic, CCI                                     ║
║  - Volatility: BB, ATR, Keltner Channel                                     ║
║  - Volume: OBV, MFI, VWAP                                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import warnings
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')

# Import từ config
from config import get_config

# Import pta_reload (pandas-ta reload) trực tiếp
try:
    from pta_reload import ta
    HAS_TA = True
except ImportError as e:
    print(f"⚠️ pta_reload chưa cài: {e}")
    HAS_TA = False

# Import vnstock
try:
    from vnstock import Vnstock
    HAS_VNSTOCK = True
except ImportError:
    HAS_VNSTOCK = False


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TAConfig:
    """Config cho TA Analyzer"""
    DATA_SOURCE: str = "VCI"
    LOOKBACK_DAYS: int = 365
    OUTPUT_DIR: str = "./output"


def create_config() -> TAConfig:
    unified = get_config()
    config = TAConfig()
    config.DATA_SOURCE = unified.get_data_source()
    config.OUTPUT_DIR = unified.output.OUTPUT_DIR
    return config


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TAResult:
    """Kết quả phân tích kỹ thuật"""
    symbol: str
    
    # Price
    price: float = 0.0
    change_1d: float = 0.0
    
    # Trend
    sma_20: float = 0.0
    sma_50: float = 0.0
    sma_200: float = 0.0
    ema_12: float = 0.0
    ema_26: float = 0.0
    vwap: float = 0.0
    adx: float = 0.0
    adx_trend: str = ""  # Strong/Weak
    psar: float = 0.0
    psar_signal: str = ""  # Buy/Sell
    supertrend: float = 0.0
    supertrend_signal: str = ""
    
    # Momentum
    rsi_14: float = 0.0
    rsi_zone: str = ""  # Overbought/Oversold/Neutral
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    macd_cross: str = ""  # Bullish/Bearish
    stoch_k: float = 0.0
    stoch_d: float = 0.0
    cci: float = 0.0
    
    # Volatility
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_position: str = ""  # Upper/Middle/Lower
    atr: float = 0.0
    atr_pct: float = 0.0  # % of price
    
    # Volume
    obv: float = 0.0
    obv_trend: str = ""
    mfi: float = 0.0
    
    # Score
    trend_score: int = 0  # -100 to 100
    momentum_score: int = 0
    overall_score: int = 0
    signal: str = ""  # Strong Buy/Buy/Hold/Sell/Strong Sell


@dataclass
class TAReport:
    """Báo cáo TA"""
    timestamp: datetime = field(default_factory=datetime.now)
    results: List[TAResult] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# TA ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class TAAnalyzer:
    """Phân tích kỹ thuật sử dụng vnstock_ta"""
    
    def __init__(self, config: TAConfig):
        self.config = config
        self.vnstock = Vnstock() if HAS_VNSTOCK else None
    
    def analyze(self, symbols: List[str]) -> TAReport:
        """Phân tích danh sách cổ phiếu"""
        print("\n" + "="*60)
        print("📊 TA ANALYZER - PHÂN TÍCH KỸ THUẬT")
        print("="*60)
        
        report = TAReport()
        
        if not HAS_TA:
            print("❌ vnstock_ta chưa cài đặt!")
            return report
        
        total = len(symbols)
        for i, symbol in enumerate(symbols, 1):
            print(f"   [{i}/{total}] {symbol}...", end=" ")
            
            try:
                result = self._analyze_single(symbol)
                if result:
                    report.results.append(result)
                    print(f"✓ Score={result.overall_score} | {result.signal}")
                else:
                    print("✗")
            except Exception as e:
                print(f"✗ {e}")
        
        return report
    
    def _analyze_single(self, symbol: str) -> Optional[TAResult]:
        """Phân tích 1 cổ phiếu"""
        result = TAResult(symbol=symbol)
        
        # Lấy dữ liệu giá
        df = self._get_price_data(symbol)
        if df is None or len(df) < 50:
            return None
        
        # Price
        result.price = df['close'].iloc[-1]
        result.change_1d = (df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100
        
        # === TREND (dùng pta_reload/ta) ===
        try:
            # SMA
            result.sma_20 = ta.sma(df['close'], length=20).iloc[-1]
            result.sma_50 = ta.sma(df['close'], length=50).iloc[-1]
            if len(df) >= 200:
                result.sma_200 = ta.sma(df['close'], length=200).iloc[-1]
            
            # EMA
            result.ema_12 = ta.ema(df['close'], length=12).iloc[-1]
            result.ema_26 = ta.ema(df['close'], length=26).iloc[-1]
            
            # VWAP
            result.vwap = ta.vwap(df['high'], df['low'], df['close'], df['volume']).iloc[-1]
            
            # ADX
            adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
            result.adx = adx_df['ADX_14'].iloc[-1]
            result.adx_trend = "Strong" if result.adx > 25 else "Weak"
            
            # PSAR
            psar_df = ta.psar(df['high'], df['low'], df['close'])
            psar_l = psar_df['PSARl_0.02_0.2'].iloc[-1]
            psar_s = psar_df['PSARs_0.02_0.2'].iloc[-1]
            
            if not pd.isna(psar_l):
                result.psar = psar_l
                result.psar_signal = "Buy"
            else:
                result.psar = psar_s
                result.psar_signal = "Sell"
            
            # SuperTrend
            st_df = ta.supertrend(df['high'], df['low'], df['close'], length=10, multiplier=3)
            result.supertrend = st_df['SUPERT_10_3.0'].iloc[-1]
            result.supertrend_signal = "Buy" if result.price > result.supertrend else "Sell"
            
        except Exception as e:
            pass
        
        # === MOMENTUM ===
        try:
            # RSI
            rsi = ta.rsi(df['close'], length=14)
            result.rsi_14 = rsi.iloc[-1]
            if result.rsi_14 > 70:
                result.rsi_zone = "Overbought"
            elif result.rsi_14 < 30:
                result.rsi_zone = "Oversold"
            else:
                result.rsi_zone = "Neutral"
            
            # MACD
            macd_df = ta.macd(df['close'], fast=12, slow=26, signal=9)
            result.macd = macd_df['MACD_12_26_9'].iloc[-1]
            result.macd_signal = macd_df['MACDs_12_26_9'].iloc[-1]
            result.macd_hist = macd_df['MACDh_12_26_9'].iloc[-1]
            
            prev_hist = macd_df['MACDh_12_26_9'].iloc[-2]
            if result.macd_hist > 0 and prev_hist <= 0:
                result.macd_cross = "Bullish"
            elif result.macd_hist < 0 and prev_hist >= 0:
                result.macd_cross = "Bearish"
            else:
                result.macd_cross = "None"
            
            # Stochastic
            stoch_df = ta.stoch(df['high'], df['low'], df['close'], k=14, d=3)
            result.stoch_k = stoch_df['STOCHk_14_3_3'].iloc[-1]
            result.stoch_d = stoch_df['STOCHd_14_3_3'].iloc[-1]
            
            # CCI
            result.cci = ta.cci(df['high'], df['low'], df['close'], length=20).iloc[-1]
            
        except Exception as e:
            pass
        
        # === VOLATILITY ===
        try:
            # Bollinger Bands
            bb_df = ta.bbands(df['close'], length=20, std=2)
            result.bb_upper = bb_df['BBU_20_2.0'].iloc[-1]
            result.bb_middle = bb_df['BBM_20_2.0'].iloc[-1]
            result.bb_lower = bb_df['BBL_20_2.0'].iloc[-1]
            
            if result.price >= result.bb_upper:
                result.bb_position = "Upper"
            elif result.price <= result.bb_lower:
                result.bb_position = "Lower"
            else:
                result.bb_position = "Middle"
            
            # ATR
            result.atr = ta.atr(df['high'], df['low'], df['close'], length=14).iloc[-1]
            result.atr_pct = result.atr / result.price * 100
            
        except Exception as e:
            pass
        
        # === VOLUME ===
        try:
            # OBV
            obv = ta.obv(df['close'], df['volume'])
            result.obv = obv.iloc[-1]
            result.obv_trend = "Up" if obv.iloc[-1] > obv.iloc[-5] else "Down"
            
            # MFI
            result.mfi = ta.mfi(df['high'], df['low'], df['close'], df['volume'], length=14).iloc[-1]
            
        except Exception as e:
            pass
        
        # === SCORING ===
        result = self._calculate_scores(result)
        
        return result
    
    def _get_price_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Lấy dữ liệu giá"""
        try:
            stock = self.vnstock.stock(symbol=symbol, source=self.config.DATA_SOURCE)
            end = datetime.now().strftime('%Y-%m-%d')
            start = (datetime.now() - timedelta(days=self.config.LOOKBACK_DAYS)).strftime('%Y-%m-%d')
            
            df = stock.quote.history(start=start, end=end, interval='1D')
            return df
        except:
            return None
    
    def _calculate_scores(self, result: TAResult) -> TAResult:
        """Tính điểm"""
        trend_score = 0
        momentum_score = 0
        
        # Trend Score
        if result.price > result.sma_20:
            trend_score += 20
        if result.price > result.sma_50:
            trend_score += 20
        if result.sma_20 > result.sma_50:
            trend_score += 10
        if result.adx > 25:
            trend_score += 20
        if result.supertrend_signal == "Buy":
            trend_score += 15
        if result.psar_signal == "Buy":
            trend_score += 15
        
        # Momentum Score
        if 40 <= result.rsi_14 <= 60:
            momentum_score += 20
        elif result.rsi_14 < 30:
            momentum_score += 30  # Oversold = opportunity
        elif result.rsi_14 > 70:
            momentum_score -= 10  # Overbought
        
        if result.macd_hist > 0:
            momentum_score += 20
        if result.macd_cross == "Bullish":
            momentum_score += 20
        
        if result.stoch_k > result.stoch_d:
            momentum_score += 10
        
        if result.obv_trend == "Up":
            momentum_score += 10
        
        if result.mfi > 50:
            momentum_score += 10
        
        result.trend_score = max(-100, min(100, trend_score))
        result.momentum_score = max(-100, min(100, momentum_score))
        result.overall_score = (result.trend_score + result.momentum_score) // 2
        
        # Signal
        if result.overall_score >= 70:
            result.signal = "Strong Buy"
        elif result.overall_score >= 40:
            result.signal = "Buy"
        elif result.overall_score >= -20:
            result.signal = "Hold"
        elif result.overall_score >= -50:
            result.signal = "Sell"
        else:
            result.signal = "Strong Sell"
        
        return result


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

class TAAnalyzerModule:
    """Module TA Analyzer"""
    
    def __init__(self):
        self.config = create_config()
        self.analyzer = TAAnalyzer(self.config)
        self.report: TAReport = None
    
    def run(self, symbols: List[str] = None) -> TAReport:
        """Chạy module"""
        print("""
╔══════════════════════════════════════════════════════════════╗
║     TA ANALYZER - PHÂN TÍCH KỸ THUẬT                         ║
║     Sử dụng vnstock_ta v0.1.2                                ║
╚══════════════════════════════════════════════════════════════╝
        """)
        
        # Nếu không có symbols, đọc từ watchlist.csv
        if not symbols:
            watchlist_file = os.path.join(self.config.OUTPUT_DIR, "watchlist.csv")
            if os.path.exists(watchlist_file):
                df = pd.read_csv(watchlist_file)
                symbols = df['symbol'].tolist()[:10]  # Top 10
                print(f"📋 Đọc {len(symbols)} mã từ watchlist.csv")
            else:
                symbols = ['VIC', 'VNM', 'FPT', 'VCB', 'HPG']
                print(f"📋 Dùng danh sách mặc định: {symbols}")
        
        # Analyze
        self.report = self.analyzer.analyze(symbols)
        
        # Print & Save
        self._print_report()
        self._save_report()
        
        return self.report
    
    def _print_report(self):
        print("\n" + "="*70)
        print("📊 KẾT QUẢ PHÂN TÍCH KỸ THUẬT")
        print("="*70)
        
        print(f"\n{'MÃ':<6} {'GIÁ':>10} {'RSI':>6} {'ADX':>6} {'MACD':>8} {'TREND':>10} {'SIGNAL':<12}")
        print("-"*65)
        
        for r in self.report.results:
            print(f"{r.symbol:<6} {r.price:>10,.0f} {r.rsi_14:>6.1f} {r.adx:>6.1f} "
                  f"{r.macd_hist:>+8.2f} {r.trend_score:>+10} {r.signal:<12}")
    
    def _save_report(self):
        os.makedirs(self.config.OUTPUT_DIR, exist_ok=True)
        
        filename = os.path.join(
            self.config.OUTPUT_DIR,
            f"ta_analysis_{self.report.timestamp.strftime('%Y%m%d_%H%M')}.md"
        )
        
        rows = "\n".join([
            f"| {r.symbol} | {r.price:,.0f} | {r.rsi_14:.1f} | {r.rsi_zone} | {r.adx:.1f} | {r.macd_hist:+.2f} | {r.overall_score} | {r.signal} |"
            for r in self.report.results
        ])
        
        content = f"""# PHÂN TÍCH KỸ THUẬT
**Ngày:** {self.report.timestamp.strftime('%d/%m/%Y %H:%M')}

## KẾT QUẢ

| Mã | Giá | RSI | Zone | ADX | MACD Hist | Score | Signal |
|----|-----|-----|------|-----|-----------|-------|--------|
{rows}

## CHÚ THÍCH
- RSI > 70: Overbought (quá mua)
- RSI < 30: Oversold (quá bán)
- ADX > 25: Trend mạnh
- MACD Hist > 0: Momentum tích cực
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\n✓ Đã lưu: {filename}")


if __name__ == "__main__":
    module = TAAnalyzerModule()
    report = module.run()