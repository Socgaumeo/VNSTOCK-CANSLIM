# Phase 03: Enhanced Fundamental Analysis (C & A Fix)

## Overview
- **Priority:** P0 - Critical
- **Status:** Pending
- **Mô tả:** Fix lỗ hổng nghiêm trọng nhất - dữ liệu Fundamental (C & A trong CANSLIM). Fundamental score hiện chỉ đạt 6/100 cho hầu hết mã do data thiếu hoặc parse sai.

## Key Insights
- PROJECT_EVALUATION rating: "Thiếu C & A là mất 50% sức mạnh CANSLIM"
- V3 FundamentalAggregator đã có nhưng confidence_score thấp
- vnstock premium API cung cấp income_statement, balance_sheet, cash_flow đầy đủ
- Vấn đề chính: column name parsing sai do MultiIndex phức tạp của vnstock
- CafeF/VietStock scraping không ổn định, hay bị block

## Root Cause Analysis

### Tại sao Fundamental Score = 6?
1. `get_financial_flow()` return 0 cho eps_growth vì column name mismatch
2. `get_financial_ratios()` parse MultiIndex sai → ROE/ROA = 0
3. V3 aggregator try CafeF scraping → bị rate limit → fallback → default 0
4. `_calc_c_score()` nhận toàn 0 → return 0-10 điểm

### Fix Strategy
1. Fix vnstock column parsing (primary - reliable)
2. Tăng cường cache để tránh repeated failures
3. Tính toán EPS growth từ raw income statement thay vì dựa ratio API
4. Thêm quarterly earning acceleration tracking

## Requirements

### Functional
- EPS quarterly growth (QoQ, YoY) chính xác từ income statement
- Revenue growth (QoQ, YoY) chính xác
- EPS 3-year CAGR, 5-year CAGR từ annual data
- ROE, ROA, Gross Margin tracking 8+ quý
- Cash Flow quality (OCF/Profit ratio)
- Earnings Acceleration detection (tốc độ tăng EPS đang tăng?)
- Consecutive positive quarters counting

### Non-functional
- Confidence score > 70% cho ≥ 80% mã trên sàn
- Data freshness: < 7 ngày cho quarterly data

## Implementation Steps

### 1. Fix vnstock column parsing trong data_collector.py

Vấn đề hiện tại:
```python
# HIỆN TẠI (sai): Dùng string key cho MultiIndex
result['roe'] = float(latest.get(('Chỉ tiêu khả năng sinh lợi', 'ROE (%)'), 0)) * 100
```

Fix:
```python
# CẦN LÀM: Iterate columns, find by partial match
def _find_column(df, *keywords):
    """Find column in MultiIndex by keyword matching"""
    for col in df.columns:
        col_str = str(col).lower()
        if all(kw.lower() in col_str for kw in keywords):
            return col
    return None
```

### 2. Tạo earnings_calculator.py

```python
class EarningsCalculator:
    """Tính EPS growth chính xác từ raw income statement"""

    def calc_eps_growth(self, symbol: str) -> Dict:
        """
        Fetch income_statement → extract LNST → tính EPS
        Returns: {
            'eps_current_q': float,
            'eps_growth_qoq': float,   # vs quý trước
            'eps_growth_yoy': float,   # vs cùng kỳ năm trước
            'eps_3y_cagr': float,
            'eps_5y_cagr': float,
            'eps_acceleration': float,  # growth rate đang tăng hay giảm
            'consecutive_growth_q': int,
            'earnings_stability': float,  # std_dev / mean
        }
        """

    def calc_revenue_growth(self, symbol: str) -> Dict:
        """Tương tự cho revenue"""

    def calc_cash_flow_quality(self, symbol: str) -> Dict:
        """
        OCF / Net Income ratio (should be > 0.8)
        Free Cash Flow trend
        Working capital changes
        """
```

### 3. Fix C Score calculation

```python
def _calc_c_score(self, data: FundamentalData) -> float:
    """C Score: Current Quarterly Earnings"""
    score = 0

    # 1. EPS Q/Q Growth (40 điểm max)
    eps_qoq = data.eps_growth_qoq
    if eps_qoq >= 50: score += 40
    elif eps_qoq >= 25: score += 30
    elif eps_qoq >= 15: score += 20
    elif eps_qoq > 0: score += 10

    # 2. EPS Acceleration (20 điểm) - QUAN TRỌNG cho VN
    # Tốc độ tăng EPS đang tăng = cổ phiếu sắp "bay"
    if data.eps_acceleration > 10: score += 20
    elif data.eps_acceleration > 0: score += 10

    # 3. Revenue Growth support (20 điểm)
    if data.revenue_growth_qoq >= 25: score += 20
    elif data.revenue_growth_qoq >= 15: score += 15
    elif data.revenue_growth_qoq > 0: score += 10

    # 4. Cash Flow Quality (20 điểm) - VN market hay "đánh bóng" EPS
    if data.ocf_to_profit_ratio >= 0.8: score += 20
    elif data.ocf_to_profit_ratio >= 0.5: score += 10
    elif data.ocf_to_profit_ratio < 0.3: score -= 10  # Cảnh báo

    return min(100, max(0, score))
```

### 4. Fix A Score calculation

```python
def _calc_a_score(self, data: FundamentalData) -> float:
    """A Score: Annual Earnings Growth (3-5 năm)"""
    score = 0

    # 1. EPS 3Y CAGR (35 điểm)
    cagr = data.eps_growth_3y_cagr
    if cagr >= 25: score += 35
    elif cagr >= 15: score += 25
    elif cagr >= 10: score += 15
    elif cagr > 0: score += 5

    # 2. ROE (25 điểm) - Chất lượng doanh nghiệp
    if data.roe >= 25: score += 25
    elif data.roe >= 17: score += 20
    elif data.roe >= 12: score += 10

    # 3. Earnings Stability (20 điểm)
    # Số quý liên tiếp EPS tăng
    if data.consecutive_eps_growth >= 8: score += 20
    elif data.consecutive_eps_growth >= 4: score += 15
    elif data.consecutive_eps_growth >= 2: score += 10

    # 4. Gross Margin Expansion (20 điểm) - Dấu hiệu sớm
    # Nếu gross margin đang mở rộng → EPS sẽ tăng mạnh sau
    if data.gross_margin_expansion > 3: score += 20
    elif data.gross_margin_expansion > 0: score += 10

    return min(100, max(0, score))
```

### 5. Tích hợp vào SQLite (Phase 01)

Lưu tất cả quarterly data vào `financial_quarterly` table.
Lần chạy sau chỉ fetch quý mới nhất.

## Related Code Files
- `v2_optimized/data_collector.py` (lines 610-795) - Fix column parsing
- `v2_optimized/module3_stock_screener_v1.py` (lines 417-600) - Fix scoring
- `v3_enhanced/fundamental_enhanced_v3.py` (lines 200-600) - Improve aggregator
- NEW: `v2_optimized/earnings_calculator.py`

## Todo List
- [ ] Debug vnstock column parsing - log actual column names
- [ ] Implement _find_column() helper for MultiIndex
- [ ] Fix get_financial_ratios() column mapping
- [ ] Fix get_financial_flow() column mapping
- [ ] Tạo earnings_calculator.py
- [ ] Implement calc_eps_growth() từ raw income statement
- [ ] Implement calc_revenue_growth()
- [ ] Implement calc_cash_flow_quality()
- [ ] Fix _calc_c_score() với logic mới
- [ ] Fix _calc_a_score() với logic mới
- [ ] Thêm gross_margin_expansion tracking
- [ ] Integrate với SQLite store (Phase 01)
- [ ] Test: Fundamental score > 30 cho ≥ 50% mã blue-chip

## Success Criteria
- Fundamental score trung bình tăng từ 6 → 40+ cho blue-chips
- EPS growth data available cho > 80% mã trong universe
- OCF quality warning phát hiện ≥ 70% mã có vấn đề cash flow

## Risk Assessment
- vnstock API thay đổi column names → cần flexible parsing
- Quarterly data delay (công bố chậm 30-45 ngày) → cần xử lý lag
- Một số mã mid-cap thiếu data 5 năm → fallback sang 3 năm
