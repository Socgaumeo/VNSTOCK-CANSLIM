#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    VOLUME PROFILE ANALYSIS MODULE                            ║
║              POC | Value Area High | Value Area Low | HVN | LVN             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Volume Profile cho thấy:                                                    ║
║  - POC (Point of Control): Mức giá có volume lớn nhất = Support/Resistance  ║
║  - Value Area (70% volume): Vùng giá "fair value"                           ║
║  - HVN (High Volume Node): Vùng tích lũy/phân phối                          ║
║  - LVN (Low Volume Node): Vùng giá có thể breakout nhanh                    ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict
from datetime import datetime


# ══════════════════════════════════════════════════════════════════════════════
# DATA STRUCTURES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class VolumeProfileLevel:
    """Một mức giá trong Volume Profile"""
    price_low: float
    price_high: float
    price_mid: float
    volume: float
    volume_pct: float  # % of total volume
    is_poc: bool = False
    is_hvn: bool = False  # High Volume Node
    is_lvn: bool = False  # Low Volume Node
    is_value_area: bool = False


@dataclass
class VolumeProfileResult:
    """Kết quả phân tích Volume Profile"""
    symbol: str
    period_start: datetime
    period_end: datetime
    
    # Key levels
    poc: float = 0.0           # Point of Control
    poc_volume: float = 0.0    # Volume tại POC
    
    vah: float = 0.0           # Value Area High
    val: float = 0.0           # Value Area Low
    value_area_pct: float = 70.0  # % volume trong Value Area
    
    # Current price context
    current_price: float = 0.0
    price_vs_poc: str = ""     # Above/Below/At POC
    price_vs_va: str = ""      # Above VA / In VA / Below VA
    
    # High/Low Volume Nodes
    hvn_levels: List[float] = field(default_factory=list)  # High Volume Nodes
    lvn_levels: List[float] = field(default_factory=list)  # Low Volume Nodes
    
    # Support/Resistance from VP
    vp_support: List[float] = field(default_factory=list)
    vp_resistance: List[float] = field(default_factory=list)
    
    # Full profile
    profile: List[VolumeProfileLevel] = field(default_factory=list)
    
    # Trading signals
    signals: List[str] = field(default_factory=list)


# ══════════════════════════════════════════════════════════════════════════════
# VOLUME PROFILE CALCULATOR
# ══════════════════════════════════════════════════════════════════════════════

class VolumeProfileCalculator:
    """
    Tính toán Volume Profile
    
    Usage:
        calculator = VolumeProfileCalculator()
        result = calculator.calculate(df, num_bins=50, value_area_pct=0.70)
    """
    
    def __init__(self, 
                 num_bins: int = 50,
                 value_area_pct: float = 0.70,
                 hvn_threshold: float = 0.05,
                 lvn_threshold: float = 0.01):
        """
        Args:
            num_bins: Số mức giá (bins) để phân tích
            value_area_pct: % volume cho Value Area (mặc định 70%)
            hvn_threshold: Ngưỡng % volume để xác định HVN
            lvn_threshold: Ngưỡng % volume để xác định LVN
        """
        self.num_bins = num_bins
        self.value_area_pct = value_area_pct
        self.hvn_threshold = hvn_threshold
        self.lvn_threshold = lvn_threshold
    
    def calculate(self, 
                  df: pd.DataFrame,
                  symbol: str = "",
                  lookback_days: int = None) -> VolumeProfileResult:
        """
        Tính Volume Profile từ DataFrame OHLCV
        
        Args:
            df: DataFrame với columns: open, high, low, close, volume
            symbol: Mã cổ phiếu
            lookback_days: Số ngày để tính (None = toàn bộ)
            
        Returns:
            VolumeProfileResult với đầy đủ metrics
        """
        if df.empty:
            return VolumeProfileResult(symbol=symbol, 
                                       period_start=datetime.now(),
                                       period_end=datetime.now())
        
        # Filter by lookback
        if lookback_days and len(df) > lookback_days:
            df = df.tail(lookback_days).copy()
        
        result = VolumeProfileResult(
            symbol=symbol,
            period_start=pd.to_datetime(df.index[0]) if hasattr(df.index[0], 'date') else datetime.now(),
            period_end=pd.to_datetime(df.index[-1]) if hasattr(df.index[-1], 'date') else datetime.now(),
            current_price=df['close'].iloc[-1]
        )
        
        # 1. Xác định price range
        price_min = df['low'].min()
        price_max = df['high'].max()
        
        # 2. Tạo bins (price levels)
        bins = np.linspace(price_min, price_max, self.num_bins + 1)
        bin_width = (price_max - price_min) / self.num_bins
        
        # 3. Phân bổ volume vào từng bin
        # Sử dụng phương pháp TPO: phân bổ volume của mỗi nến vào các mức giá nó đi qua
        volume_profile = np.zeros(self.num_bins)
        
        for _, row in df.iterrows():
            candle_low = row['low']
            candle_high = row['high']
            candle_volume = row['volume']
            
            # Tìm các bins mà nến đi qua
            for i in range(self.num_bins):
                bin_low = bins[i]
                bin_high = bins[i + 1]
                
                # Kiểm tra overlap
                if candle_high >= bin_low and candle_low <= bin_high:
                    # Tính % overlap
                    overlap_low = max(candle_low, bin_low)
                    overlap_high = min(candle_high, bin_high)
                    
                    if candle_high > candle_low:
                        overlap_pct = (overlap_high - overlap_low) / (candle_high - candle_low)
                    else:
                        overlap_pct = 1.0
                    
                    # Phân bổ volume
                    volume_profile[i] += candle_volume * overlap_pct
        
        # 4. Tính % volume cho mỗi bin
        total_volume = volume_profile.sum()
        if total_volume == 0:
            return result
        
        volume_pct = volume_profile / total_volume
        
        # 5. Tìm POC (Point of Control)
        poc_idx = np.argmax(volume_profile)
        result.poc = (bins[poc_idx] + bins[poc_idx + 1]) / 2
        result.poc_volume = volume_profile[poc_idx]
        
        # 6. Tính Value Area (70% volume)
        result.vah, result.val = self._calculate_value_area(
            bins, volume_profile, poc_idx, self.value_area_pct
        )
        
        # 7. Xác định HVN và LVN
        hvn_indices = np.where(volume_pct >= self.hvn_threshold)[0]
        lvn_indices = np.where(volume_pct <= self.lvn_threshold)[0]
        
        result.hvn_levels = [(bins[i] + bins[i + 1]) / 2 for i in hvn_indices]
        result.lvn_levels = [(bins[i] + bins[i + 1]) / 2 for i in lvn_indices]
        
        # 8. Xác định Support/Resistance từ VP
        current = result.current_price
        
        # HVN dưới giá hiện tại = Support
        result.vp_support = sorted([p for p in result.hvn_levels if p < current], reverse=True)[:3]
        
        # HVN trên giá hiện tại = Resistance
        result.vp_resistance = sorted([p for p in result.hvn_levels if p > current])[:3]
        
        # 9. Xác định vị trí giá hiện tại
        if current > result.poc * 1.005:
            result.price_vs_poc = "ABOVE_POC"
        elif current < result.poc * 0.995:
            result.price_vs_poc = "BELOW_POC"
        else:
            result.price_vs_poc = "AT_POC"
        
        if current > result.vah:
            result.price_vs_va = "ABOVE_VA"
        elif current < result.val:
            result.price_vs_va = "BELOW_VA"
        else:
            result.price_vs_va = "IN_VALUE_AREA"
        
        # 10. Tạo trading signals
        result.signals = self._generate_signals(result)
        
        # 11. Build full profile
        result.profile = []
        for i in range(self.num_bins):
            level = VolumeProfileLevel(
                price_low=bins[i],
                price_high=bins[i + 1],
                price_mid=(bins[i] + bins[i + 1]) / 2,
                volume=volume_profile[i],
                volume_pct=volume_pct[i] * 100,
                is_poc=(i == poc_idx),
                is_hvn=(volume_pct[i] >= self.hvn_threshold),
                is_lvn=(volume_pct[i] <= self.lvn_threshold),
                is_value_area=(bins[i] >= result.val and bins[i + 1] <= result.vah)
            )
            result.profile.append(level)
        
        return result
    
    def _calculate_value_area(self, 
                               bins: np.ndarray, 
                               volume_profile: np.ndarray,
                               poc_idx: int,
                               target_pct: float) -> Tuple[float, float]:
        """Tính Value Area High và Low"""
        total_volume = volume_profile.sum()
        target_volume = total_volume * target_pct
        
        # Bắt đầu từ POC, mở rộng ra 2 bên
        va_volume = volume_profile[poc_idx]
        upper_idx = poc_idx
        lower_idx = poc_idx
        
        while va_volume < target_volume:
            # So sánh volume của bin phía trên và phía dưới
            upper_vol = volume_profile[upper_idx + 1] if upper_idx + 1 < len(volume_profile) else 0
            lower_vol = volume_profile[lower_idx - 1] if lower_idx > 0 else 0
            
            if upper_vol == 0 and lower_vol == 0:
                break
            
            if upper_vol >= lower_vol and upper_idx + 1 < len(volume_profile):
                upper_idx += 1
                va_volume += upper_vol
            elif lower_idx > 0:
                lower_idx -= 1
                va_volume += lower_vol
            else:
                break
        
        vah = bins[upper_idx + 1] if upper_idx + 1 <= len(bins) - 1 else bins[-1]
        val = bins[lower_idx]
        
        return vah, val
    
    def _generate_signals(self, result: VolumeProfileResult) -> List[str]:
        """Tạo trading signals từ Volume Profile"""
        signals = []
        current = result.current_price
        
        # 1. POC signals
        poc_distance = abs(current - result.poc) / result.poc * 100
        
        if result.price_vs_poc == "AT_POC":
            signals.append(f"📍 Giá tại POC ({result.poc:,.0f}) - Vùng cân bằng, chờ breakout")
        elif poc_distance < 2:
            signals.append(f"📍 Giá gần POC ({result.poc:,.0f}) - Có thể test POC")
        
        # 2. Value Area signals
        if result.price_vs_va == "ABOVE_VA":
            signals.append(f"📈 Giá TRÊN Value Area (VAH={result.vah:,.0f}) - Bullish bias")
            signals.append(f"   → Nếu pullback, VAH là support tiềm năng")
        elif result.price_vs_va == "BELOW_VA":
            signals.append(f"📉 Giá DƯỚI Value Area (VAL={result.val:,.0f}) - Bearish bias")
            signals.append(f"   → Nếu rebound, VAL là resistance tiềm năng")
        else:
            signals.append(f"📊 Giá TRONG Value Area ({result.val:,.0f}-{result.vah:,.0f}) - Consolidation")
        
        # 3. HVN/LVN signals
        if result.vp_support:
            signals.append(f"🟢 VP Support: {', '.join([f'{p:,.0f}' for p in result.vp_support[:2]])}")
        
        if result.vp_resistance:
            signals.append(f"🔴 VP Resistance: {', '.join([f'{p:,.0f}' for p in result.vp_resistance[:2]])}")
        
        # 4. LVN breakout potential
        for lvn in result.lvn_levels:
            if abs(current - lvn) / lvn < 0.02:  # Gần LVN
                signals.append(f"⚡ Gần LVN ({lvn:,.0f}) - Có thể breakout nhanh qua vùng này")
                break
        
        return signals


# ══════════════════════════════════════════════════════════════════════════════
# VOLUME PROFILE FORMATTER
# ══════════════════════════════════════════════════════════════════════════════

class VolumeProfileFormatter:
    """Format Volume Profile để hiển thị"""
    
    @staticmethod
    def format_summary(result: VolumeProfileResult) -> str:
        """Format summary ngắn gọn"""
        return f"""
📊 VOLUME PROFILE - {result.symbol}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 POC (Point of Control): {result.poc:,.0f}
📈 Value Area High (VAH):  {result.vah:,.0f}
📉 Value Area Low (VAL):   {result.val:,.0f}
💰 Current Price:          {result.current_price:,.0f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 Position: {result.price_vs_va} | {result.price_vs_poc}
"""
    
    @staticmethod
    def format_signals(result: VolumeProfileResult) -> str:
        """Format trading signals"""
        if not result.signals:
            return "Không có tín hiệu đặc biệt"
        
        return "\n".join(result.signals)
    
    @staticmethod
    def format_ascii_profile(result: VolumeProfileResult, width: int = 40) -> str:
        """Tạo biểu đồ ASCII của Volume Profile"""
        if not result.profile:
            return ""
        
        lines = []
        lines.append("PRICE     │ VOLUME PROFILE")
        lines.append("──────────┼" + "─" * width)
        
        max_vol_pct = max(p.volume_pct for p in result.profile)
        
        for level in reversed(result.profile):  # Từ cao xuống thấp
            # Bar length
            bar_len = int(level.volume_pct / max_vol_pct * (width - 5)) if max_vol_pct > 0 else 0
            
            # Markers
            marker = ""
            if level.is_poc:
                marker = "◀POC"
                bar_char = "█"
            elif level.is_hvn:
                bar_char = "▓"
            elif level.is_lvn:
                bar_char = "░"
            else:
                bar_char = "▒"
            
            # Value Area highlight
            if level.is_value_area:
                bar_char = "█" if not level.is_poc else bar_char
            
            # Current price marker
            if level.price_low <= result.current_price <= level.price_high:
                marker = marker or "◀NOW"
            
            bar = bar_char * bar_len
            line = f"{level.price_mid:>9,.0f} │{bar} {marker}"
            lines.append(line)
        
        return "\n".join(lines)
    
    @staticmethod
    def format_for_ai_prompt(result: VolumeProfileResult) -> str:
        """Format cho AI prompt"""
        return f"""
VOLUME PROFILE DATA - {result.symbol}:
- POC (Point of Control): {result.poc:,.0f} (Mức giá có volume lớn nhất)
- Value Area: {result.val:,.0f} - {result.vah:,.0f} (Vùng chứa 70% volume)
- Current Price: {result.current_price:,.0f}
- Price vs POC: {result.price_vs_poc}
- Price vs Value Area: {result.price_vs_va}
- VP Support levels: {', '.join([f'{p:,.0f}' for p in result.vp_support]) or 'N/A'}
- VP Resistance levels: {', '.join([f'{p:,.0f}' for p in result.vp_resistance]) or 'N/A'}
- High Volume Nodes (HVN): {', '.join([f'{p:,.0f}' for p in result.hvn_levels[:5]]) or 'N/A'}
- Low Volume Nodes (LVN): {', '.join([f'{p:,.0f}' for p in result.lvn_levels[:5]]) or 'N/A'}
"""


# ══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def calculate_volume_profile(df: pd.DataFrame, 
                             symbol: str = "",
                             lookback_days: int = 20,
                             num_bins: int = 50) -> VolumeProfileResult:
    """
    Convenience function để tính Volume Profile
    
    Args:
        df: DataFrame với OHLCV
        symbol: Mã cổ phiếu
        lookback_days: Số ngày
        num_bins: Số mức giá
        
    Returns:
        VolumeProfileResult
    """
    calculator = VolumeProfileCalculator(num_bins=num_bins)
    return calculator.calculate(df, symbol=symbol, lookback_days=lookback_days)


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test với dummy data
    np.random.seed(42)
    
    dates = pd.date_range(end=datetime.now(), periods=60, freq='D')
    
    # Tạo OHLCV giả
    base_price = 25000
    prices = base_price + np.cumsum(np.random.randn(60) * 200)
    
    df = pd.DataFrame({
        'open': prices + np.random.randn(60) * 100,
        'high': prices + abs(np.random.randn(60) * 200),
        'low': prices - abs(np.random.randn(60) * 200),
        'close': prices,
        'volume': np.random.randint(100000, 1000000, 60)
    }, index=dates)
    
    # Tính Volume Profile
    result = calculate_volume_profile(df, symbol="TEST", lookback_days=20)
    
    # In kết quả
    formatter = VolumeProfileFormatter()
    print(formatter.format_summary(result))
    print("\n" + formatter.format_ascii_profile(result))
    print("\n🎯 TRADING SIGNALS:")
    print(formatter.format_signals(result))
