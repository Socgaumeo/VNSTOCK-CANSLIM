# VNSTOCK-CANSLIM: KẾ HOẠCH NÂNG CẤP PHÂN TÍCH DỮ LIỆU V4

**Ngày tạo:** 2026-02-14
**Mục tiêu:** Nâng cấp hệ thống phân tích dữ liệu lịch sử thực tế (nến, giá trị mua bán, volume, chỉ báo) để lọc cổ phiếu tiềm năng, theo dõi hiệu quả, quản lý danh mục.

---

## TỔNG QUAN DỰ ÁN HIỆN TẠI

### Điểm mạnh
- Volume Profile (POC, VAH, VAL) triển khai tốt
- RS Rating IBD-style chuẩn (40-30-20-10)
- Market Timing + Sector Rotation logic vững
- AI Debate (Bull/Bear/Judge) sáng tạo
- Volume Confirmation (shakeout/dry-up) theo Minervini
- Multi-source data fallback (VCI → TCBS → SSI)

### Điểm yếu nghiêm trọng (từ PROJECT_EVALUATION.md)
1. **C & A trong CANSLIM rất yếu** - Fundamental score chỉ đạt 6/100 cho hầu hết mã
2. **Không lưu trữ dữ liệu lịch sử** - Fetch mới mỗi lần, mất context dài hạn
3. **Thiếu phân tích nến (candlestick)** - Chỉ dùng OHLCV thô, không nhận diện mẫu nến
4. **Position sizing/Portfolio management chưa có** - Chỉ gợi ý mua, không quản lý vị thế
5. **Backtesting hoàn toàn thiếu** - Không biết hiệu quả thực tế của các tín hiệu
6. **Thiếu dữ liệu tự doanh & giao dịch thỏa thuận** - Quan trọng cho VN market

---

## CÁC PHASE TRIỂN KHAI

| Phase | Tên | Trạng thái | Ưu tiên |
|-------|-----|-----------|---------|
| 01 | SQLite Historical Data Store | **DONE** | P0 - Critical |
| 02 | Candlestick Pattern Recognition | **DONE** | P0 - Critical |
| 03 | Enhanced Fundamental (C&A Fix) | **DONE** | P0 - Critical |
| 04 | Advanced Volume & Money Flow | **DONE** | P1 - High |
| 05 | Portfolio Management & Position Sizing | **DONE** | P1 - High |
| 06 | Backtesting & Performance Tracking | **DONE** | P1 - High |
| 07 | Indicator Optimization for VN Market | **DONE** | P2 - Medium |

---

## DEPENDENCIES

```
Phase 01 (Database) ──┬──> Phase 02 (Candlestick)
                      ├──> Phase 03 (Fundamental)
                      ├──> Phase 04 (Volume/Money Flow)
                      └──> Phase 06 (Backtesting)

Phase 02 + 03 + 04 ──> Phase 05 (Portfolio)
Phase 01 + 05 ──> Phase 06 (Backtesting)
Phase 01-06 ──> Phase 07 (Optimization)
```

---

## ƯỚC TÍNH TÁC ĐỘNG

| Metric | Hiện tại | Sau nâng cấp |
|--------|----------|-------------|
| Fundamental Score trung bình | 6/100 | 40-70/100 |
| Patterns nhận diện | 3 (VCP, Cup&Handle, Flat) | 12+ (thêm nến) |
| Dữ liệu lịch sử | 0 ngày (chỉ fetch live) | 5+ năm |
| Portfolio management | Không có | Pyramiding + Trailing Stop |
| Backtesting | Không có | Win rate, drawdown, Sharpe |
| Thời gian phân tích 1 lần | 15-25 phút | 3-5 phút (cached) |

---

## CHI TIẾT TỪNG PHASE

- [Phase 01: SQLite Historical Data Store](phase-01-sqlite-historical-data-store.md)
- [Phase 02: Candlestick Pattern Recognition](phase-02-candlestick-pattern-recognition.md)
- [Phase 03: Enhanced Fundamental Analysis](phase-03-enhanced-fundamental-analysis.md)
- [Phase 04: Advanced Volume & Money Flow](phase-04-advanced-volume-money-flow.md)
- [Phase 05: Portfolio Management & Position Sizing](phase-05-portfolio-management-position-sizing.md)
- [Phase 06: Backtesting & Performance Tracking](phase-06-backtesting-performance-tracking.md)
- [Phase 07: Indicator Optimization for VN Market](phase-07-indicator-optimization-vn-market.md)
