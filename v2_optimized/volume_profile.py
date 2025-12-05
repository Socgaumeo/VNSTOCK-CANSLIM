#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         VOLUME PROFILE MODULE                                 ║
║              POC, Value Area, Support/Resistance Detection                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import pandas as pd
import numpy as np


@dataclass
class VolumeProfileResult:
    """Kết quả Volume Profile"""
    symbol: str = ""
    
    # Core levels
    poc: float = 0.0              # Point of Control
    vah: float = 0.0              # Value Area High
    val: float = 0.0              # Value Area Low
    
    # Price position
    price_vs_poc: str = ""        # "ABOVE" / "BELOW" / "AT"
    price_vs_va: str = ""         # "ABOVE_VA" / "IN_VA" / "BELOW_VA"
    
    # Key levels
    vp_support: List[float] = field(default_factory=list)
    vp_resistance: List[float] = field(default_factory=list)
    
    # Signals
    signals: List[str] = field(default_factory=list)
    
    # Raw data
    profile: pd.DataFrame = field(default_factory=pd.DataFrame)


class VolumeProfileCalculator:
    """
    Tính Volume Profile
    
    POC (Point of Control): Mức giá có volume cao nhất
    VAH (Value Area High): Cận trên vùng giá trị (70% volume)
    VAL (Value Area Low): Cận dưới vùng giá trị
    """
    
    def __init__(self, num_bins: int = 50, value_area_pct: float = 0.70):
        """
        Args:
            num_bins: Số bin để chia price range
            value_area_pct: Phần trăm volume cho Value Area (mặc định 70%)
        """
        self.num_bins = num_bins
        self.value_area_pct = value_area_pct
    
    def calculate(self, 
                  df: pd.DataFrame, 
                  symbol: str = "",
                  lookback_days: int = 20) -> VolumeProfileResult:
        """
        Tính Volume Profile từ OHLCV data
        
        Args:
            df: DataFrame với columns ['open', 'high', 'low', 'close', 'volume']
            symbol: Mã cổ phiếu
            lookback_days: Số ngày để tính VP
            
        Returns:
            VolumeProfileResult
        """
        result = VolumeProfileResult(symbol=symbol)
        
        if df.empty or len(df) < 5:
            return result
        
        # Lấy dữ liệu lookback
        df = df.tail(lookback_days).copy()
        
        # Cần có các cột cơ bản
        required_cols = ['high', 'low', 'close', 'volume']
        if not all(col in df.columns for col in required_cols):
            return result
        
        # Price range
        price_high = df['high'].max()
        price_low = df['low'].min()
        
        if price_high == price_low:
            return result
        
        # Tạo bins
        bin_size = (price_high - price_low) / self.num_bins
        bins = np.arange(price_low, price_high + bin_size, bin_size)
        
        # Phân bổ volume vào các bins
        volume_profile = np.zeros(len(bins) - 1)
        
        for _, row in df.iterrows():
            row_low = row['low']
            row_high = row['high']
            row_volume = row['volume']
            
            # Tìm các bins mà candle này thuộc về
            for i, (bin_low, bin_high) in enumerate(zip(bins[:-1], bins[1:])):
                if row_low <= bin_high and row_high >= bin_low:
                    # Overlap
                    overlap_low = max(row_low, bin_low)
                    overlap_high = min(row_high, bin_high)
                    overlap_pct = (overlap_high - overlap_low) / (row_high - row_low) if row_high > row_low else 1
                    volume_profile[i] += row_volume * overlap_pct
        
        # POC - bin có volume cao nhất
        poc_idx = np.argmax(volume_profile)
        result.poc = (bins[poc_idx] + bins[poc_idx + 1]) / 2
        
        # Value Area - 70% volume
        total_volume = volume_profile.sum()
        target_volume = total_volume * self.value_area_pct
        
        # Bắt đầu từ POC, mở rộng ra 2 phía
        cumulative = volume_profile[poc_idx]
        lower_idx = poc_idx
        upper_idx = poc_idx
        
        while cumulative < target_volume and (lower_idx > 0 or upper_idx < len(volume_profile) - 1):
            # So sánh volume 2 bên và chọn bên nhiều hơn
            lower_vol = volume_profile[lower_idx - 1] if lower_idx > 0 else 0
            upper_vol = volume_profile[upper_idx + 1] if upper_idx < len(volume_profile) - 1 else 0
            
            if lower_vol >= upper_vol and lower_idx > 0:
                lower_idx -= 1
                cumulative += lower_vol
            elif upper_idx < len(volume_profile) - 1:
                upper_idx += 1
                cumulative += upper_vol
            else:
                lower_idx -= 1
                cumulative += lower_vol
        
        result.val = bins[lower_idx]
        result.vah = bins[upper_idx + 1]
        
        # Current price position
        current_price = df['close'].iloc[-1]
        
        # vs POC
        if current_price > result.poc * 1.01:
            result.price_vs_poc = "ABOVE"
        elif current_price < result.poc * 0.99:
            result.price_vs_poc = "BELOW"
        else:
            result.price_vs_poc = "AT"
        
        # vs Value Area
        if current_price > result.vah:
            result.price_vs_va = "ABOVE_VA"
        elif current_price < result.val:
            result.price_vs_va = "BELOW_VA"
        else:
            result.price_vs_va = "IN_VA"
        
        # Support/Resistance levels (high volume nodes)
        threshold = np.percentile(volume_profile, 75)  # Top 25% volume
        high_vol_nodes = [(bins[i] + bins[i+1])/2 for i, v in enumerate(volume_profile) if v >= threshold]
        
        result.vp_support = [p for p in high_vol_nodes if p < current_price][-3:]  # 3 support gần nhất
        result.vp_resistance = [p for p in high_vol_nodes if p > current_price][:3]  # 3 resistance gần nhất
        
        # Generate signals
        result.signals = self._generate_signals(result, current_price)
        
        # Store profile
        result.profile = pd.DataFrame({
            'price_low': bins[:-1],
            'price_high': bins[1:],
            'volume': volume_profile
        })
        
        return result
    
    def _generate_signals(self, vp: VolumeProfileResult, price: float) -> List[str]:
        """Tạo tín hiệu từ Volume Profile"""
        signals = []
        
        # Price vs Value Area
        if vp.price_vs_va == "ABOVE_VA":
            signals.append(f"📈 Giá ({price:,.0f}) TRÊN Value Area ({vp.vah:,.0f})")
            signals.append("   → Momentum mạnh, có thể tiếp tục tăng")
            signals.append(f"   → Support tại VAH: {vp.vah:,.0f}")
        elif vp.price_vs_va == "BELOW_VA":
            signals.append(f"📉 Giá ({price:,.0f}) DƯỚI Value Area ({vp.val:,.0f})")
            signals.append("   → Momentum yếu, có thể tiếp tục giảm")
            signals.append(f"   → Resistance tại VAL: {vp.val:,.0f}")
        else:
            signals.append(f"📊 Giá ({price:,.0f}) TRONG Value Area ({vp.val:,.0f}-{vp.vah:,.0f})")
            signals.append("   → Vùng cân bằng, có thể sideway")
            signals.append(f"   → POC: {vp.poc:,.0f}")
        
        # POC signal
        if abs(price - vp.poc) / vp.poc < 0.02:
            signals.append(f"⚡ Giá gần POC ({vp.poc:,.0f}) - Key level!")
        
        return signals


class VolumeProfileFormatter:
    """Format Volume Profile để hiển thị"""
    
    @staticmethod
    def to_markdown(vp: VolumeProfileResult) -> str:
        """Format thành markdown"""
        if vp.poc == 0:
            return "Volume Profile: N/A"
        
        md = f"""## Volume Profile
| Level | Giá |
|-------|-----|
| **POC** | {vp.poc:,.0f} |
| **VAH** | {vp.vah:,.0f} |
| **VAL** | {vp.val:,.0f} |
| **Position** | {vp.price_vs_va} |

**Support:** {', '.join([f'{p:,.0f}' for p in vp.vp_support]) if vp.vp_support else 'N/A'}
**Resistance:** {', '.join([f'{p:,.0f}' for p in vp.vp_resistance]) if vp.vp_resistance else 'N/A'}
"""
        return md
    
    @staticmethod
    def to_dict(vp: VolumeProfileResult) -> dict:
        """Convert to dictionary"""
        return {
            'poc': vp.poc,
            'vah': vp.vah,
            'val': vp.val,
            'price_vs_poc': vp.price_vs_poc,
            'price_vs_va': vp.price_vs_va,
            'support': vp.vp_support,
            'resistance': vp.vp_resistance,
            'signals': vp.signals
        }


def calculate_volume_profile(df: pd.DataFrame, 
                             lookback_days: int = 20,
                             symbol: str = "") -> VolumeProfileResult:
    """
    Function tiện ích để tính Volume Profile
    
    Args:
        df: DataFrame với OHLCV
        lookback_days: Số ngày
        symbol: Mã cổ phiếu
        
    Returns:
        VolumeProfileResult
    """
    calculator = VolumeProfileCalculator()
    return calculator.calculate(df, symbol=symbol, lookback_days=lookback_days)


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Testing Volume Profile...")
    
    # Tạo dữ liệu test
    np.random.seed(42)
    n = 50
    
    prices = 100 + np.cumsum(np.random.randn(n) * 2)
    
    df = pd.DataFrame({
        'open': prices + np.random.randn(n),
        'high': prices + abs(np.random.randn(n)) * 2,
        'low': prices - abs(np.random.randn(n)) * 2,
        'close': prices,
        'volume': np.random.randint(100000, 1000000, n)
    })
    
    # Tính VP
    vp = calculate_volume_profile(df, symbol="TEST")
    
    print(f"\n📊 Volume Profile Results:")
    print(f"   POC: {vp.poc:,.0f}")
    print(f"   Value Area: {vp.val:,.0f} - {vp.vah:,.0f}")
    print(f"   Position: {vp.price_vs_va}")
    print(f"\n📝 Signals:")
    for sig in vp.signals:
        print(f"   {sig}")