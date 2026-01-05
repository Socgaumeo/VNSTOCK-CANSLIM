#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           VWAP INDICATOR MODULE                              ║
║               Volume-Weighted Average Price for Buy Point ID                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Features:                                                                   ║
║  - Calculate VWAP using pandas_ta                                           ║
║  - Generate buy signals based on VWAP crossover                             ║
║  - Support for anchored VWAP                                                ║
║  - VWAP bands for deviation analysis                                        ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import pandas as pd
import numpy as np

# Add parent directory to path for config import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from v2_optimized.config import get_config, APIKeys
except ImportError:
    from config import get_config, APIKeys

# Set API key
os.environ['VNSTOCK_API_KEY'] = APIKeys.VNSTOCK

try:
    import pandas_ta as ta
    HAS_PANDAS_TA = True
except ImportError:
    HAS_PANDAS_TA = False
    print("⚠️ pandas_ta not available. Install with: pip install pandas-ta")

try:
    from vnstock import Quote
    HAS_VNSTOCK = True
except ImportError:
    HAS_VNSTOCK = False


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class VWAPResult:
    """Kết quả tính toán VWAP"""
    symbol: str = ""
    date: datetime = None
    
    # Current values
    current_price: float = 0.0
    vwap: float = 0.0
    vwap_upper: float = 0.0  # +1 std
    vwap_lower: float = 0.0  # -1 std
    
    # Position relative to VWAP
    price_vs_vwap: str = ""  # "ABOVE", "BELOW", "AT"
    deviation_pct: float = 0.0  # % deviation from VWAP
    
    # Signals
    buy_signal: bool = False
    bullish_cross: bool = False  # Price crossed above VWAP
    bearish_cross: bool = False  # Price crossed below VWAP
    
    # VWAP Trend
    vwap_slope: str = ""  # "RISING", "FALLING", "FLAT"
    
    # Score
    vwap_score: float = 50.0  # 0-100


# ══════════════════════════════════════════════════════════════════════════════
# VWAP CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

class VWAPIndicator:
    """
    Volume-Weighted Average Price (VWAP) calculator
    
    VWAP = Σ(Typical Price × Volume) / Σ(Volume)
    Typical Price = (High + Low + Close) / 3
    
    Use cases:
    - Buy signal: Price crosses ABOVE VWAP with volume confirmation
    - Institutional buying: Trades above VWAP indicate buying pressure
    - Support/Resistance: VWAP acts as dynamic support in uptrends
    """
    
    def __init__(self, lookback_days: int = 20):
        self.lookback_days = lookback_days
        
        if HAS_PANDAS_TA:
            print("✓ VWAPIndicator initialized with pandas_ta")
        else:
            print("⚠️ VWAPIndicator running with manual VWAP calculation")
    
    def calculate(self, symbol: str) -> VWAPResult:
        """
        Calculate VWAP cho một mã cổ phiếu
        
        Args:
            symbol: Mã cổ phiếu (VD: VCB, FPT)
            
        Returns:
            VWAPResult với VWAP values và signals
        """
        result = VWAPResult(symbol=symbol, date=datetime.now())
        
        if not HAS_VNSTOCK:
            return result
        
        print(f"   📊 Calculating VWAP for {symbol}...")
        
        try:
            # Fetch OHLCV data
            df = self._get_ohlcv_data(symbol)
            
            if df is None or df.empty:
                print(f"      ✗ No data for {symbol}")
                return result
            
            return self.calculate_from_df(symbol, df)
            
        except Exception as e:
            print(f"      ✗ Error: {e}")
        
        return result
    
    def calculate_from_df(self, symbol: str, df: pd.DataFrame) -> VWAPResult:
        """
        Calculate VWAP from pre-fetched DataFrame (no API call)
        
        Args:
            symbol: Mã cổ phiếu
            df: DataFrame with OHLCV data (columns: open, high, low, close, volume)
            
        Returns:
            VWAPResult với VWAP values và signals
        """
        result = VWAPResult(symbol=symbol, date=datetime.now())
        
        if df is None or df.empty:
            return result
        
        try:
            # Ensure lowercase columns
            df = df.copy()
            df.columns = df.columns.str.lower()
            
            # Calculate VWAP
            if HAS_PANDAS_TA:
                df = self._calculate_vwap_pandas_ta(df)
            else:
                df = self._calculate_vwap_manual(df)
            
            # Get latest values
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest
            
            result.current_price = float(latest['close'])
            result.vwap = float(latest['vwap']) if 'vwap' in latest else 0.0
            result.vwap_upper = float(latest['vwap_upper']) if 'vwap_upper' in latest else result.vwap * 1.02
            result.vwap_lower = float(latest['vwap_lower']) if 'vwap_lower' in latest else result.vwap * 0.98
            
            # Price vs VWAP
            if result.vwap > 0:
                result.deviation_pct = ((result.current_price - result.vwap) / result.vwap) * 100
                
                if result.current_price > result.vwap * 1.005:
                    result.price_vs_vwap = "ABOVE"
                elif result.current_price < result.vwap * 0.995:
                    result.price_vs_vwap = "BELOW"
                else:
                    result.price_vs_vwap = "AT"
            
            # Crossover detection
            prev_vwap = float(prev['vwap']) if 'vwap' in prev else result.vwap
            prev_close = float(prev['close'])
            
            result.bullish_cross = (prev_close <= prev_vwap) and (result.current_price > result.vwap)
            result.bearish_cross = (prev_close >= prev_vwap) and (result.current_price < result.vwap)
            
            # VWAP slope
            if len(df) >= 5 and 'vwap' in df.columns:
                vwap_5d = df['vwap'].tail(5).values
                slope = (vwap_5d[-1] - vwap_5d[0]) / vwap_5d[0] * 100 if vwap_5d[0] > 0 else 0
                
                if slope > 0.5:
                    result.vwap_slope = "RISING"
                elif slope < -0.5:
                    result.vwap_slope = "FALLING"
                else:
                    result.vwap_slope = "FLAT"
            
            # Buy signal: Bullish cross with rising VWAP
            result.buy_signal = result.bullish_cross and result.vwap_slope == "RISING"
            
            # Calculate VWAP score
            result.vwap_score = self._calculate_vwap_score(result, df)
            
            # Silent - only print in standalone mode
            # print(f"      ✓ VWAP: {result.vwap:,.0f} | Price: {result.current_price:,.0f} ({result.price_vs_vwap})")

            
        except Exception as e:
            print(f"      ✗ VWAP error: {e}")
        
        return result

    
    def _get_ohlcv_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data từ vnstock"""
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=self.lookback_days + 10)
            
            quote = Quote(symbol=symbol, source='VCI')
            df = quote.history(
                start=start_date.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval='1D'
            )
            
            if df is None or df.empty:
                return None
            
            # Standardize column names
            df.columns = df.columns.str.lower()
            
            # Ensure required columns exist
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    return None
            
            return df.tail(self.lookback_days)
            
        except Exception as e:
            print(f"      ✗ Data fetch error: {e}")
            return None
    
    def _calculate_vwap_pandas_ta(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate VWAP using pandas_ta"""
        # pandas_ta expects a certain format
        df_calc = df.copy()
        
        # Calculate VWAP with bands
        vwap_result = ta.vwap(
            high=df_calc['high'],
            low=df_calc['low'],
            close=df_calc['close'],
            volume=df_calc['volume'],
            anchor='D'  # Daily anchor
        )
        
        if vwap_result is not None:
            if isinstance(vwap_result, pd.DataFrame):
                df_calc['vwap'] = vwap_result.iloc[:, 0]
            else:
                df_calc['vwap'] = vwap_result
        else:
            # Fallback to manual calculation
            df_calc = self._calculate_vwap_manual(df_calc)
        
        # Calculate VWAP bands (±1 standard deviation)
        if 'vwap' in df_calc.columns:
            typical_price = (df_calc['high'] + df_calc['low'] + df_calc['close']) / 3
            squared_diff = ((typical_price - df_calc['vwap']) ** 2 * df_calc['volume']).cumsum()
            cum_volume = df_calc['volume'].cumsum()
            
            std_dev = np.sqrt(squared_diff / cum_volume)
            df_calc['vwap_upper'] = df_calc['vwap'] + std_dev
            df_calc['vwap_lower'] = df_calc['vwap'] - std_dev
        
        return df_calc
    
    def _calculate_vwap_manual(self, df: pd.DataFrame) -> pd.DataFrame:
        """Manual VWAP calculation"""
        df_calc = df.copy()
        
        # Typical Price = (High + Low + Close) / 3
        df_calc['typical_price'] = (df_calc['high'] + df_calc['low'] + df_calc['close']) / 3
        
        # VWAP = Cumulative(TP * Volume) / Cumulative(Volume)
        df_calc['tp_vol'] = df_calc['typical_price'] * df_calc['volume']
        df_calc['cum_tp_vol'] = df_calc['tp_vol'].cumsum()
        df_calc['cum_vol'] = df_calc['volume'].cumsum()
        df_calc['vwap'] = df_calc['cum_tp_vol'] / df_calc['cum_vol']
        
        # Simple bands (±2%)
        df_calc['vwap_upper'] = df_calc['vwap'] * 1.02
        df_calc['vwap_lower'] = df_calc['vwap'] * 0.98
        
        return df_calc
    
    def _calculate_vwap_score(self, result: VWAPResult, df: pd.DataFrame) -> float:
        """
        Calculate VWAP score (0-100)
        
        Scoring logic:
        - Price above VWAP: Base +20
        - Bullish crossover: +20
        - Rising VWAP: +15
        - Close to VWAP (support): +10
        - Price in upper band: +5
        """
        base = 50
        score_adjustments = 0
        
        # Price position
        if result.price_vs_vwap == "ABOVE":
            score_adjustments += 20
        elif result.price_vs_vwap == "BELOW":
            score_adjustments -= 15
        
        # Crossover
        if result.bullish_cross:
            score_adjustments += 20
        elif result.bearish_cross:
            score_adjustments -= 15
        
        # VWAP trend
        if result.vwap_slope == "RISING":
            score_adjustments += 15
        elif result.vwap_slope == "FALLING":
            score_adjustments -= 10
        
        # Deviation from VWAP
        if 0 < result.deviation_pct <= 2:
            # Near VWAP but above - good support
            score_adjustments += 10
        elif -2 <= result.deviation_pct < 0:
            # Near VWAP but below - potential bounce
            score_adjustments += 5
        elif result.deviation_pct > 5:
            # Extended above VWAP - potential pullback
            score_adjustments -= 5
        
        return max(0, min(100, base + score_adjustments))
    
    def get_buy_zone(self, symbol: str) -> Dict:
        """
        Xác định vùng mua dựa trên VWAP
        
        Returns:
            Dict với buy_zone, stop_loss, và targets
        """
        result = self.calculate(symbol)
        
        if result.vwap == 0:
            return {
                'symbol': symbol,
                'valid': False,
                'message': 'VWAP calculation failed'
            }
        
        # Buy zone: VWAP to VWAP + 1%
        buy_point = result.vwap
        buy_zone_high = result.vwap * 1.01
        
        # Stop loss: Below VWAP - 3%
        stop_loss = result.vwap * 0.97
        
        # Targets based on VWAP deviation
        target_1 = result.vwap * 1.05  # +5%
        target_2 = result.vwap * 1.10  # +10%
        
        return {
            'symbol': symbol,
            'valid': True,
            'current_price': result.current_price,
            'vwap': result.vwap,
            'buy_point': buy_point,
            'buy_zone': (buy_point, buy_zone_high),
            'stop_loss': stop_loss,
            'target_1': target_1,
            'target_2': target_2,
            'signal': 'BUY' if result.buy_signal else ('WATCH' if result.price_vs_vwap == "AT" else 'WAIT'),
            'vwap_score': result.vwap_score
        }


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def calculate_vwap(symbol: str, lookback_days: int = 20) -> Dict:
    """
    Quick VWAP calculation cho một mã
    
    Returns:
        Dict với VWAP values và signals
    """
    indicator = VWAPIndicator(lookback_days=lookback_days)
    result = indicator.calculate(symbol)
    
    return {
        'symbol': result.symbol,
        'current_price': result.current_price,
        'vwap': result.vwap,
        'vwap_upper': result.vwap_upper,
        'vwap_lower': result.vwap_lower,
        'position': result.price_vs_vwap,
        'deviation_pct': result.deviation_pct,
        'buy_signal': result.buy_signal,
        'bullish_cross': result.bullish_cross,
        'bearish_cross': result.bearish_cross,
        'vwap_slope': result.vwap_slope,
        'vwap_score': result.vwap_score
    }


def get_vwap_buy_zone(symbol: str) -> Dict:
    """Quick access to buy zone based on VWAP"""
    indicator = VWAPIndicator()
    return indicator.get_buy_zone(symbol)


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 70)
    print("VWAP INDICATOR - TEST")
    print("=" * 70)
    
    symbols = ['VCB', 'FPT', 'MWG']
    
    indicator = VWAPIndicator(lookback_days=20)
    
    for symbol in symbols:
        print(f"\n📊 Analyzing {symbol}...")
        print("-" * 50)
        
        result = indicator.calculate(symbol)
        
        print(f"\n✓ Results for {symbol}:")
        print(f"   Current: {result.current_price:,.0f}")
        print(f"   VWAP: {result.vwap:,.0f}")
        print(f"   Position: {result.price_vs_vwap} ({result.deviation_pct:+.2f}%)")
        print(f"   VWAP Slope: {result.vwap_slope}")
        print(f"   Buy Signal: {'✓ YES' if result.buy_signal else '✗ NO'}")
        print(f"   VWAP Score: {result.vwap_score:.1f}/100")
        
        # Get buy zone
        buy_zone = indicator.get_buy_zone(symbol)
        if buy_zone['valid']:
            print(f"\n   📈 Trading Plan:")
            print(f"      Buy Point: {buy_zone['buy_point']:,.0f}")
            print(f"      Buy Zone: {buy_zone['buy_zone'][0]:,.0f} - {buy_zone['buy_zone'][1]:,.0f}")
            print(f"      Stop Loss: {buy_zone['stop_loss']:,.0f}")
            print(f"      Target 1: {buy_zone['target_1']:,.0f}")
            print(f"      Target 2: {buy_zone['target_2']:,.0f}")
            print(f"      Signal: {buy_zone['signal']}")
