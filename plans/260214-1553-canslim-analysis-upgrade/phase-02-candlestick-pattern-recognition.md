# Phase 02: Candlestick Pattern Recognition

## Overview
- **Priority:** P0 - Critical
- **Status:** Pending
- **Mô tả:** Thêm nhận diện mẫu nến Nhật Bản, đặc biệt các mẫu đảo chiều tại vùng Volume Profile (POC/VAH/VAL), cải thiện điểm entry/exit.

## Key Insights
- PROJECT_EVALUATION.md ghi nhận: "Code hiện tại thuần túy dựa trên hình học giá, chưa kết hợp với hành vi Volume tại các điểm then chốt"
- VN market có đặc thù: price limit ±7% (HOSE), nến doji/hammer gần ceiling/floor có ý nghĩa đặc biệt
- Cần tập trung vào MẪU NẾN + VOLUME + VỊ TRÍ (tại VP zone) thay vì chỉ mẫu nến đơn lẻ

## Requirements

### Functional
- Nhận diện 12 mẫu nến phổ biến và hiệu quả nhất cho VN market
- Kết hợp mẫu nến với vị trí Volume Profile (tại POC/VAH/VAL)
- Volume confirmation cho mỗi mẫu nến
- Phân loại: Bullish Reversal, Bearish Reversal, Continuation
- Tích hợp vào PatternDetector scoring

### Non-functional
- Xử lý < 10ms cho 250 ngày data 1 mã
- False positive rate < 30% khi kết hợp VP

## Architecture

```
v2_optimized/
├── candlestick_analyzer.py    # Core candlestick detection
└── (update) module3_stock_screener_v1.py  # Integrate scoring
```

## 12 Mẫu Nến Ưu Tiên

### Bullish Reversal (Đảo chiều tăng)
1. **Hammer** - Thân nhỏ, bóng dưới dài ≥2x thân, ở đáy downtrend
2. **Bullish Engulfing** - Nến xanh bao trùm nến đỏ trước, volume tăng
3. **Morning Star** - 3 nến: đỏ dài + doji/thân nhỏ + xanh dài
4. **Piercing Line** - Nến xanh mở gap down nhưng đóng > 50% thân nến đỏ trước
5. **Three White Soldiers** - 3 nến xanh liên tiếp, mỗi nến đóng cao hơn

### Bearish Reversal (Đảo chiều giảm)
6. **Shooting Star** - Thân nhỏ, bóng trên dài ≥2x thân, ở đỉnh uptrend
7. **Bearish Engulfing** - Nến đỏ bao trùm nến xanh trước, volume tăng
8. **Evening Star** - 3 nến: xanh dài + doji/thân nhỏ + đỏ dài
9. **Dark Cloud Cover** - Nến đỏ mở gap up nhưng đóng < 50% thân nến xanh trước

### Continuation & Context
10. **Doji** - Thân rất nhỏ (open ≈ close), tại VP zone = indecision signal
11. **Spinning Top** - Thân nhỏ, bóng 2 bên, lực cân bằng
12. **Marubozu** - Thân dài không bóng, momentum mạnh

## Implementation Steps

### 1. Tạo candlestick_analyzer.py

```python
@dataclass
class CandlestickSignal:
    pattern_name: str           # "Hammer", "Bullish Engulfing"
    signal_type: str            # "bullish_reversal", "bearish_reversal", "continuation"
    confidence: float           # 0-100
    volume_confirmed: bool
    vp_zone: str               # "AT_POC", "AT_VAH", "AT_VAL", "NONE"
    context_score: float       # Điểm kết hợp: nến + volume + vị trí
    date: str
    description: str

class CandlestickAnalyzer:
    def analyze(self, df, vp_result=None) -> List[CandlestickSignal]:
        """Phân tích mẫu nến trên 20 ngày gần nhất"""

    def _is_hammer(self, row, prev_rows) -> Optional[CandlestickSignal]:
        """
        Hammer: body_size < range/3, lower_shadow >= 2*body, upper_shadow < body
        Context: Phải ở đáy (giá < MA20 hoặc RSI < 35)
        """

    def _is_bullish_engulfing(self, current, previous) -> Optional[CandlestickSignal]:
        """
        Engulfing: current.open < prev.close AND current.close > prev.open
        Volume: current.volume > previous.volume * 1.3
        """

    def _calc_context_score(self, signal, vp_result, volume_ratio) -> float:
        """
        Context score = base_confidence * volume_mult * vp_mult
        volume_mult: 1.0 (normal), 1.3 (high volume), 0.7 (low volume)
        vp_mult: 1.5 (at POC/VAH/VAL), 1.0 (in VA), 0.8 (outside VA)
        """
```

### 2. Tích hợp vào PatternDetector

Thêm candlestick score vào `PatternData`:
```python
# Trong PatternData, thêm:
candlestick_signals: List[CandlestickSignal]
candlestick_score: float  # 0-30 điểm bonus
```

### 3. Cập nhật Scoring

Trong `_calc_pattern_score()`:
```python
# Hiện tại: pattern_quality + VCP bonus + buy_point bonus
# Thêm: + candlestick_score (0-30)
# candlestick_score = context_score của tín hiệu mạnh nhất gần nhất (5 ngày)
```

### 4. Đặc biệt cho VN Market

- **Ceiling/Floor logic:** Nến đóng tại trần (ceiling) với volume lớn = demand rất mạnh
- **T+2.5 effect:** Hammer ngày T → có thể mua T+1 → settle T+3.5
- **ATC effect:** Nến cuối phiên ATC thường bị méo, cần lọc
- **Gap analysis:** VN hay có gap lớn do ATO, cần tính overlap

## Todo List
- [ ] Tạo candlestick_analyzer.py với 12 patterns
- [ ] Implement từng pattern detection function
- [ ] Thêm VP zone detection cho mỗi signal
- [ ] Thêm volume confirmation logic
- [ ] Tích hợp vào PatternDetector class
- [ ] Cập nhật PatternData dataclass
- [ ] Cập nhật scoring weights
- [ ] Thêm VN-specific rules (ceiling/floor, ATC)
- [ ] Test với dữ liệu thực tế 10 mã

## Success Criteria
- Nhận diện ≥ 10/12 mẫu nến chính xác
- Context score tại VP zone > 70 cho signals thực sự mạnh
- Tích hợp mượt vào scoring system hiện tại
- Không làm chậm pipeline > 5%

## Risk Assessment
- Over-fitting: quá nhiều signals → noise. Mitigation: chỉ lấy top 3 signals gần nhất
- False signals tại ceiling/floor cần xử lý riêng
