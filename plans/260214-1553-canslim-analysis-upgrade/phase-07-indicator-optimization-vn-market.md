# Phase 07: Indicator Optimization for VN Market

## Overview
- **Priority:** P2 - Medium
- **Status:** Pending
- **Mô tả:** Tinh chỉnh các chỉ báo và tham số cho đặc thù thị trường Việt Nam: price limit bands, T+2.5, liquidity thresholds, sector-specific tuning.

## Key Insights
- VN market có price limit ±7% HOSE → RSI oversold/overbought thresholds cần điều chỉnh
- T+2.5 settlement → entry timing phải tính trước 2.5 ngày
- Thanh khoản: với 10 tỷ NAV, cần lọc mã có GTGD > 10 tỷ/phiên
- Ngành rotation VN rõ ràng hơn US: BĐS → Ngân hàng → Thép → Tech theo chu kỳ
- "Ra tin là bán" - news sentiment cần inverse logic cho một số trường hợp

## Requirements

### Functional
- Liquidity filter: Average Traded Value > configurable threshold
- RSI adjustment cho price limit bands
- Scoring weight tuning dựa trên backtest results (Phase 06)
- Sector-specific thresholds (PE acceptable range khác nhau theo ngành)
- T+2.5 aware buy/sell timing
- Ceiling/Floor detection signals

### Non-functional
- Tham số phải configurable, không hardcode
- A/B test framework cho parameter tuning

## Implementation Steps

### 1. Liquidity Filter Upgrade

```python
# HIỆN TẠI: MIN_VOLUME_AVG = 100000 (shares)
# VẤN ĐỀ: Mã giá 5,000 vs mã giá 100,000 cùng 100k shares rất khác

# MỚI: Lọc theo Average Traded Value (giá trị)
class LiquidityConfig:
    # NAV 5-10 tỷ:
    MIN_AVG_VALUE_20D = 10_000_000_000   # 10 tỷ VND/phiên
    # NAV 10-20 tỷ:
    # MIN_AVG_VALUE_20D = 20_000_000_000

    # Percentage of daily value we can trade without impact
    MAX_PARTICIPATION_RATE = 0.05  # Max 5% of daily volume
```

### 2. RSI Adjustment cho VN

```python
# VN market price limit ±7% → RSI moves slower
# Standard RSI zones (30-70) quá rộng cho VN

class VNMarketRSI:
    # Adjusted for ±7% daily limit
    OVERSOLD = 35           # (vs standard 30)
    OVERBOUGHT = 65         # (vs standard 70)
    EXTREME_OVERSOLD = 25
    EXTREME_OVERBOUGHT = 75

    # RSI scoring adjustment
    OPTIMAL_RANGE = (45, 65)  # Best entry zone cho VN
```

### 3. Sector-Specific PE Thresholds

```python
# PE acceptable range khác nhau theo ngành VN
SECTOR_PE_RANGES = {
    'VNFIN': (5, 15),      # Ngân hàng: PE thấp
    'VNREAL': (8, 25),     # BĐS: PE cao hơn
    'VNMAT': (5, 12),      # Nguyên vật liệu: PE thấp
    'VNIT': (15, 35),      # Tech: PE cao nhất
    'VNHEAL': (10, 25),    # Y tế: PE trung bình-cao
    'VNCOND': (10, 20),    # Tiêu dùng KTY: trung bình
    'VNCONS': (15, 30),    # Tiêu dùng TY: ổn định, PE cao
}

# Scoring: PE trong range → bonus, ngoài range → penalty
```

### 4. Ceiling/Floor Signals

```python
class CeilingFloorDetector:
    """
    VN-specific signals:
    - Cổ phiếu đóng trần (ceiling) + volume spike = demand cực mạnh
    - Cổ phiếu đóng sàn (floor) + volume spike = panic selling
    - Đóng trần liên tiếp 2+ phiên = momentum trade
    """

    CEILING_PCT = 0.07   # HOSE: +7%
    FLOOR_PCT = -0.07    # HOSE: -7%

    def detect(self, df) -> Dict:
        """
        Returns:
        - ceiling_count_5d: Số lần chạm trần 5 phiên
        - floor_count_5d: Số lần chạm sàn 5 phiên
        - at_ceiling_today: bool
        - at_floor_today: bool
        - ceiling_with_volume: bool (trần + vol > 2x avg)
        """
```

### 5. Scoring Weight Optimization

```python
# Dựa trên backtest results (Phase 06):
# Nếu Pattern win rate > Fundamental:
#   → Tăng WEIGHT_PATTERN, giảm WEIGHT_FUNDAMENTAL
# Nếu Foreign flow signal mạnh:
#   → Tăng money_flow component trong Technical

class AdaptiveWeights:
    """Tự động điều chỉnh weights dựa trên performance"""

    def calc_optimal_weights(self, performance_data) -> Dict:
        """
        Simple: weight proportional to component's win rate
        W_i = win_rate_i / sum(all_win_rates)
        """
```

### 6. T+2.5 Timing Logic

```python
class TradingTimingAdvisor:
    """
    T+2.5 considerations:
    - Mua ngày T → tiền trừ T+2.5
    - Bán T → tiền về T+2.5
    - Nếu cần cash: phải bán trước 2.5 ngày

    Impact on strategy:
    - Stop loss trigger → bán sớm 1 ngày (trước khi hit)
    - Breakout confirm → có thể mua T+1 nếu volume confirm T
    """

    def suggest_action_timing(self, signal, current_time) -> str:
        """
        ATO (9:00-9:15): Tốt cho mua breakout
        Morning session (9:15-11:30): Monitor, quyết định mua
        ATC (14:30-14:45): KHÔNG mua (bị manipulate)
        """
```

## Todo List
- [ ] Implement LiquidityConfig với Average Traded Value
- [ ] Adjust RSI thresholds cho VN market
- [ ] Implement sector-specific PE ranges
- [ ] Tạo CeilingFloorDetector
- [ ] Implement AdaptiveWeights (sau khi có Phase 06 data)
- [ ] Implement TradingTimingAdvisor
- [ ] Update config.py với VN-specific defaults
- [ ] Test: compare performance trước/sau optimization

## Success Criteria
- Liquidity filter loại bỏ 100% mã thanh khoản thấp
- Sector PE scoring hợp lý (không penalize VNIT vì PE cao)
- Ceiling/floor signals phát hiện chính xác

## Risk Assessment
- Over-optimization (curve fitting) → cần out-of-sample test
- Sector PE ranges cần update khi market regime thay đổi
- T+2.5 rules có thể thay đổi (VN đang hướng T+2 hoặc T+0)
