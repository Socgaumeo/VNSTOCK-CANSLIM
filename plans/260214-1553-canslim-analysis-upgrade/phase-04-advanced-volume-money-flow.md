# Phase 04: Advanced Volume & Money Flow Analysis

## Overview
- **Priority:** P1 - High
- **Status:** Pending
- **Mô tả:** Nâng cấp phân tích volume và dòng tiền: thêm bid/ask analysis, foreign flow trends, proprietary trading tracking, và volume divergence detection.

## Key Insights
- VN market: "Tin đồn & Game" → dòng tiền khối ngoại và tự doanh là chỉ báo dẫn dắt
- Hiện tại chỉ track foreign buy/sell hiện tại, không có trend analysis
- Thiếu dữ liệu giao dịch thỏa thuận (block trade) - rất quan trọng cho "tay to"
- Volume divergence (giá tăng + volume giảm) là signal mạnh nhưng chưa implement

## Requirements

### Functional
- Foreign flow 20-day trend analysis (tích lũy/phân phối)
- Volume-Price Divergence detection
- Distribution Day counting (theo O'Neil)
- Accumulation/Distribution indicator
- Money Flow Index (MFI) - kết hợp giá + volume
- On-Balance Volume (OBV) trend
- Block trade tracking (nếu data available)

### Non-functional
- Tất cả indicators tính từ cached data (Phase 01)
- Processing < 50ms cho 250 ngày

## Implementation Steps

### 1. Tạo money_flow_analyzer.py

```python
@dataclass
class MoneyFlowAnalysis:
    symbol: str

    # Foreign Flow Trend
    foreign_net_5d: float = 0.0      # Net 5 ngày gần nhất
    foreign_net_20d: float = 0.0     # Net 20 ngày
    foreign_trend: str = ""          # "ACCUMULATING", "DISTRIBUTING", "NEUTRAL"
    foreign_consecutive_buy: int = 0  # Số ngày mua ròng liên tiếp

    # Volume-Price Analysis
    volume_price_divergence: str = ""  # "BULLISH_DIV", "BEARISH_DIV", "NONE"
    distribution_days: int = 0         # Số ngày phân phối trong 25 phiên
    accumulation_days: int = 0

    # Indicators
    mfi_14: float = 50.0              # Money Flow Index
    obv_trend: str = ""               # "RISING", "FALLING", "FLAT"
    ad_line_trend: str = ""           # Accumulation/Distribution

    # Composite Score
    money_flow_score: float = 50.0    # 0-100

class MoneyFlowAnalyzer:
    def analyze(self, symbol: str, df: pd.DataFrame,
                foreign_data: pd.DataFrame = None) -> MoneyFlowAnalysis:
        """Full money flow analysis"""

    def _calc_foreign_trend(self, foreign_df) -> tuple:
        """
        20-day rolling sum of foreign net
        Trend = "ACCUMULATING" if 5d > 0 AND 20d > 0
        """

    def _detect_volume_price_divergence(self, df) -> str:
        """
        Bearish: Price making new highs + Volume declining
        Bullish: Price making new lows + Volume declining
        """

    def _count_distribution_days(self, df) -> int:
        """
        O'Neil: Distribution day = down > 0.2% on higher volume
        Count in last 25 trading days
        5+ distribution days = market under pressure
        """

    def _calc_mfi(self, df, period=14) -> float:
        """
        MFI = 100 - (100 / (1 + Money Ratio))
        Money Ratio = Positive Money Flow / Negative Money Flow
        Typical Price = (H + L + C) / 3
        """

    def _calc_obv(self, df) -> str:
        """
        OBV = cumulative volume (+ khi giá tăng, - khi giá giảm)
        Trend: 20-day slope of OBV
        """
```

### 2. Tích hợp vào Technical Score

```python
# Thêm money_flow_score vào TechnicalData
# Cập nhật weight:
# Technical = RS(25) + MA(20) + Distance(10) + RSI(10) + Volume(10) + MoneyFlow(25)
```

### 3. Foreign Flow Trend Dashboard

```python
# Trong báo cáo, thêm section:
# TOP 10 MÃ KHỐI NGOẠI MUA RÒNG MẠNH NHẤT 20 NGÀY
# TOP 10 MÃ KHỐI NGOẠI BÁN RÒNG MẠNH NHẤT 20 NGÀY
# Foreign flow trend theo ngành
```

### 4. Distribution Day Counter cho Market Timing

```python
# Tích hợp vào Module 1 Market Timing:
# distribution_days >= 5 → Market Color downgrade
# distribution_days >= 7 → Cảnh báo đỏ
```

## Related Code Files
- `v2_optimized/data_collector.py` - Thêm foreign flow fetch
- `v2_optimized/module1_market_timing_v2.py` - Distribution day counting
- `v2_optimized/module3_stock_screener_v1.py` - Technical score update
- NEW: `v2_optimized/money_flow_analyzer.py`

## Todo List
- [ ] Tạo money_flow_analyzer.py
- [ ] Implement foreign flow trend analysis
- [ ] Implement volume-price divergence detection
- [ ] Implement distribution day counting
- [ ] Implement MFI calculation
- [ ] Implement OBV trend
- [ ] Tích hợp vào Technical Score
- [ ] Update Market Timing với distribution days
- [ ] Thêm foreign flow section trong báo cáo
- [ ] Lưu foreign_flow vào SQLite (Phase 01)

## Success Criteria
- Distribution day counting chính xác vs manual count
- Foreign flow trend phát hiện accumulation 5+ ngày trước breakout
- Money flow score > 70 cho mã có dòng tiền mạnh

## Risk Assessment
- Foreign flow data có thể delay 1 ngày → cần xử lý
- Block trade data có thể không available qua vnstock free
