# 📊 BÁO CÁO SECTOR ROTATION + STOCK SCREENING
**Ngày:** 27/11/2025 20:38

---

## 📌 BƯỚC 1: VNINDEX BASELINE

| Chỉ số | Giá trị | Ý nghĩa |
|--------|---------|---------|
| VNIndex | 1,684 | Điểm hiện tại |
| Thay đổi 1D | +0.24% | Biến động trong ngày |
| Thay đổi 1M | +2.72% | **Benchmark để tính RS** |

**Logic:** RS (Relative Strength) = Performance ngành/cổ phiếu - Performance VNIndex

---

## 📌 BƯỚC 2: PHÂN TÍCH 7 NGÀNH

| Rank | Code | Tên | 1D | 1M | RS vs VNI | Phase |
|------|------|-----|----|----|-----------|-------|
| 1 | VNREAL | Bất động sản | +0.56% | +13.69% | +10.97% | 🚀 Leading |
| 2 | VNCONS | Tiêu dùng thiết yếu | -0.79% | +1.49% | -1.24% | ⛔ Lagging |
| 3 | VNMAT | Nguyên vật liệu | -0.49% | +0.00% | -2.72% | ⛔ Lagging |
| 4 | VNFIN | Tài chính | +0.06% | -2.40% | -5.13% | ⛔ Lagging |
| 5 | VNCOND | Tiêu dùng không thiết yếu | +0.50% | -3.12% | -5.84% | ⛔ Lagging |
| 6 | VNHEAL | Y tế | +0.83% | -4.10% | -6.82% | ⛔ Lagging |
| 7 | VNIT | Công nghệ | +0.57% | -3.85% | -6.57% | ⛔ Lagging |

### Logic xác định Phase:

| Phase | Điều kiện |
|-------|-----------|
| 🚀 Leading | RS > +3% VÀ momentum 5D > 0 |
| 📈 Improving | RS > 0% VÀ đang tăng tốc (5D > 1D) |
| 📉 Weakening | RS > 0% NHƯNG đang giảm tốc |
| ⛔ Lagging | RS < 0% |

### Chi tiết logic từng ngành:

**VNREAL (Bất động sản):**
- RS > +3% (+10.97%): Outperform mạnh
- 5D > 0: Momentum tích cực → LEADING

**VNCONS (Tiêu dùng thiết yếu):**
- RS < 0 (-1.24%): Underperform
- → LAGGING

**VNMAT (Nguyên vật liệu):**
- RS < 0 (-2.72%): Underperform
- → LAGGING

**VNFIN (Tài chính):**
- RS < 0 (-5.13%): Underperform
- → LAGGING

**VNCOND (Tiêu dùng không thiết yếu):**
- RS < 0 (-5.84%): Underperform
- → LAGGING

**VNHEAL (Y tế):**
- RS < 0 (-6.82%): Underperform
- → LAGGING

**VNIT (Công nghệ):**
- RS < 0 (-6.57%): Underperform
- → LAGGING

---

## 📌 BƯỚC 3: XÁC ĐỊNH NGÀNH MỤC TIÊU

| Loại | Ngành |
|------|-------|
| 🚀 Leading | VNREAL |
| 📈 Improving | Không có |
| ⛔ Không đầu tư | VNCONS, VNMAT, VNFIN, VNCOND, VNHEAL, VNIT |

**Quyết định:** Chỉ lọc cổ phiếu trong ngành **Leading + Improving**

---

## 📌 BƯỚC 4-5: LỌC CỔ PHIẾU

| Metric | Giá trị |
|--------|---------|
| Cổ phiếu trong ngành mục tiêu | 130 |
| Qua thanh khoản (>10 tỷ/phiên) | 93 |
| **API calls tiết kiệm** | ~370 |

---

## 📌 BƯỚC 6: WATCHLIST CHI TIẾT

### Tiêu chí CANSLIM & SEPA:

| Tiêu chí | Điều kiện | Ý nghĩa |
|----------|-----------|---------|
| Thanh khoản | > 10 tỷ/phiên | Đủ thanh khoản để giao dịch |
| SEPA Stage | Stage 2 | Uptrend (Giá > MA50 > MA150 > MA200) |
| RS Rating | > 70 | Outperform 70% thị trường |
| Near 52wH | < 25% | Gần đỉnh = không có kháng cự |

### TOP 20 CỔ PHIẾU:

| # | Mã | Ngành | Giá | Score | RS | Stage | vs52wH | Criteria |
|---|-----|-------|-----|-------|----|----|--------|----------|
| 1 | LGL | VNREAL | 6 | 100 | 99 | Stage 2 | 3.4% | 4/4 |
| 2 | VIC | VNREAL | 248 | 100 | 99 | Stage 2 | 2.0% | 4/4 |
| 3 | HLD | VNREAL | 18 | 92 | 61 | Stage 2 | 8.5% | 3/4 |
| 4 | V21 | VNREAL | 7 | 92 | 62 | Stage 2 | 9.2% | 3/4 |
| 5 | KDH | VNREAL | 35 | 91 | 59 | Stage 2 | 7.1% | 3/4 |
| 6 | PXL | VNREAL | 17 | 91 | 80 | Stage 2 | 20.0% | 4/4 |
| 7 | TIX | VNREAL | 47 | 91 | 58 | Stage 2 | 5.4% | 3/4 |
| 8 | TN1 | VNREAL | 16 | 91 | 58 | Stage 2 | 7.6% | 3/4 |
| 9 | KBC | VNREAL | 36 | 88 | 68 | Stage 2 | 17.2% | 3/4 |
| 10 | HDG | VNREAL | 32 | 85 | 75 | Stage 2 | 11.5% | 4/4 |
| 11 | SZL | VNREAL | 46 | 85 | 79 | Stage 1 | 2.5% | 3/4 |
| 12 | SZB | VNREAL | 38 | 83 | 66 | Stage 1 | 9.2% | 2/4 |
| 13 | VPI | VNREAL | 57 | 83 | 67 | Stage 1 | 8.2% | 2/4 |
| 14 | KOS | VNREAL | 39 | 82 | 63 | Stage 1 | 7.6% | 2/4 |
| 15 | D11 | VNREAL | 11 | 82 | 60 | Stage 2 | 12.4% | 3/4 |
| 16 | PRT | VNREAL | 12 | 81 | 84 | Stage 1 | 9.2% | 3/4 |
| 17 | SID | VNREAL | 19 | 81 | 58 | Stage 2 | 15.2% | 3/4 |
| 18 | LSG | VNREAL | 32 | 79 | 49 | Stage 2 | 14.9% | 3/4 |
| 19 | KHG | VNREAL | 8 | 75 | 28 | Stage 2 | 13.9% | 3/4 |
| 20 | THD | VNREAL | 30 | 73 | 68 | Stage 1 | 24.7% | 2/4 |

### Chi tiết logic từng cổ phiếu:


#### 1. LGL (Công ty Cổ phần Đầu tư và Phát...)

**Sector:** VNREAL (Bất động sản)

**Dữ liệu:**
| Metric | Giá trị |
|--------|---------|
| Giá | 6 |
| Thay đổi 1D | +0.16% |
| Thay đổi 5D | +10.41% |
| Thay đổi 1M | +33.19% |
| MA20 | 5 |
| MA50 | 5 |
| MA150 | 4 |
| MA200 | 4 |
| 52w High | 6 |
| vs 52wH | 3.4% |
| RS vs VNI | +30.47% |
| RS Rating | 99 |
| GTGD TB | 17778.4 tỷ/phiên |

**Logic phân tích:**
- Giá: 6
- MA50: 5 ✓
- MA150: 4 ✓
- MA200: 4 ✓
- → Stage 2 (Uptrend): Giá > MA50 > MA150 > MA200
- ✓ Thanh khoản: 17778.4 tỷ/phiên
- ✓ SEPA: Stage 2
- ✓ RS Rating: 99
- ✓ vs 52wH: 3.4%

**Kết luận:** Score = 100/100

#### 2. VIC (Tập đoàn Vingroup - Công ty CP...)

**Sector:** VNREAL (Bất động sản)

**Dữ liệu:**
| Metric | Giá trị |
|--------|---------|
| Giá | 248 |
| Thay đổi 1D | +1.22% |
| Thay đổi 5D | +7.97% |
| Thay đổi 1M | +29.84% |
| MA20 | 216 |
| MA50 | 199 |
| MA150 | 136 |
| MA200 | 115 |
| 52w High | 253 |
| vs 52wH | 2.0% |
| RS vs VNI | +27.12% |
| RS Rating | 99 |
| GTGD TB | 4960.0 tỷ/phiên |

**Logic phân tích:**
- Giá: 248
- MA50: 199 ✓
- MA150: 136 ✓
- MA200: 115 ✓
- → Stage 2 (Uptrend): Giá > MA50 > MA150 > MA200
- ✓ Thanh khoản: 4960.0 tỷ/phiên
- ✓ SEPA: Stage 2
- ✓ RS Rating: 99
- ✓ vs 52wH: 2.0%

**Kết luận:** Score = 100/100

#### 3. HLD (Công ty Cổ phần Đầu tư và Phát...)

**Sector:** VNREAL (Bất động sản)

**Dữ liệu:**
| Metric | Giá trị |
|--------|---------|
| Giá | 18 |
| Thay đổi 1D | +0.00% |
| Thay đổi 5D | +0.00% |
| Thay đổi 1M | -0.54% |
| MA20 | 18 |
| MA50 | 18 |
| MA150 | 16 |
| MA200 | 16 |
| 52w High | 20 |
| vs 52wH | 8.5% |
| RS vs VNI | -3.27% |
| RS Rating | 61 |
| GTGD TB | 36.6 tỷ/phiên |

**Logic phân tích:**
- Giá: 18
- MA50: 18 ✓
- MA150: 16 ✓
- MA200: 16 ✓
- → Stage 2 (Uptrend): Giá > MA50 > MA150 > MA200
- ✓ Thanh khoản: 36.6 tỷ/phiên
- ✓ SEPA: Stage 2
- ✗ RS Rating: 61
- ✓ vs 52wH: 8.5%

**Kết luận:** Score = 92/100

#### 4. V21 (Công ty Cổ phần Vinaconex 21...)

**Sector:** VNREAL (Bất động sản)

**Dữ liệu:**
| Metric | Giá trị |
|--------|---------|
| Giá | 7 |
| Thay đổi 1D | +1.47% |
| Thay đổi 5D | -1.43% |
| Thay đổi 1M | +0.00% |
| MA20 | 7 |
| MA50 | 7 |
| MA150 | 7 |
| MA200 | 7 |
| 52w High | 8 |
| vs 52wH | 9.2% |
| RS vs VNI | -2.72% |
| RS Rating | 62 |
| GTGD TB | 13.8 tỷ/phiên |

**Logic phân tích:**
- Giá: 7
- MA50: 7 ✓
- MA150: 7 ✓
- MA200: 7 ✓
- → Stage 2 (Uptrend): Giá > MA50 > MA150 > MA200
- ✓ Thanh khoản: 13.8 tỷ/phiên
- ✓ SEPA: Stage 2
- ✗ RS Rating: 62
- ✓ vs 52wH: 9.2%

**Kết luận:** Score = 92/100

#### 5. KDH (Công ty Cổ phần Đầu tư và Kinh...)

**Sector:** VNREAL (Bất động sản)

**Dữ liệu:**
| Metric | Giá trị |
|--------|---------|
| Giá | 35 |
| Thay đổi 1D | +0.00% |
| Thay đổi 5D | +1.58% |
| Thay đổi 1M | -1.26% |
| MA20 | 34 |
| MA50 | 34 |
| MA150 | 31 |
| MA200 | 30 |
| 52w High | 38 |
| vs 52wH | 7.1% |
| RS vs VNI | -3.98% |
| RS Rating | 59 |
| GTGD TB | 3540.0 tỷ/phiên |

**Logic phân tích:**
- Giá: 35
- MA50: 34 ✓
- MA150: 31 ✓
- MA200: 30 ✓
- → Stage 2 (Uptrend): Giá > MA50 > MA150 > MA200
- ✓ Thanh khoản: 3540.0 tỷ/phiên
- ✓ SEPA: Stage 2
- ✗ RS Rating: 59
- ✓ vs 52wH: 7.1%

**Kết luận:** Score = 91/100

#### 6. PXL (Công ty Cổ phần Đầu tư Khu Côn...)

**Sector:** VNREAL (Bất động sản)

**Dữ liệu:**
| Metric | Giá trị |
|--------|---------|
| Giá | 17 |
| Thay đổi 1D | +1.20% |
| Thay đổi 5D | +3.70% |
| Thay đổi 1M | +6.33% |
| MA20 | 16 |
| MA50 | 16 |
| MA150 | 15 |
| MA200 | 15 |
| 52w High | 21 |
| vs 52wH | 20.0% |
| RS vs VNI | +3.60% |
| RS Rating | 80 |
| GTGD TB | 33.6 tỷ/phiên |

**Logic phân tích:**
- Giá: 17
- MA50: 16 ✓
- MA150: 15 ✓
- MA200: 15 ✓
- → Stage 2 (Uptrend): Giá > MA50 > MA150 > MA200
- ✓ Thanh khoản: 33.6 tỷ/phiên
- ✓ SEPA: Stage 2
- ✓ RS Rating: 80
- ✓ vs 52wH: 20.0%

**Kết luận:** Score = 91/100

#### 7. TIX (Công ty Cổ phần Sản xuất Kinh ...)

**Sector:** VNREAL (Bất động sản)

**Dữ liệu:**
| Metric | Giá trị |
|--------|---------|
| Giá | 47 |
| Thay đổi 1D | +1.40% |
| Thay đổi 5D | +1.40% |
| Thay đổi 1M | -1.49% |
| MA20 | 47 |
| MA50 | 45 |
| MA150 | 40 |
| MA200 | 39 |
| 52w High | 50 |
| vs 52wH | 5.4% |
| RS vs VNI | -4.21% |
| RS Rating | 58 |
| GTGD TB | 282.0 tỷ/phiên |

**Logic phân tích:**
- Giá: 47
- MA50: 45 ✓
- MA150: 40 ✓
- MA200: 39 ✓
- → Stage 2 (Uptrend): Giá > MA50 > MA150 > MA200
- ✓ Thanh khoản: 282.0 tỷ/phiên
- ✓ SEPA: Stage 2
- ✗ RS Rating: 58
- ✓ vs 52wH: 5.4%

**Kết luận:** Score = 91/100

#### 8. TN1 (Công ty Cổ phần Rox Key Holdin...)

**Sector:** VNREAL (Bất động sản)

**Dữ liệu:**
| Metric | Giá trị |
|--------|---------|
| Giá | 16 |
| Thay đổi 1D | +6.80% |
| Thay đổi 5D | +6.08% |
| Thay đổi 1M | -1.57% |
| MA20 | 15 |
| MA50 | 15 |
| MA150 | 12 |
| MA200 | 11 |
| 52w High | 17 |
| vs 52wH | 7.6% |
| RS vs VNI | -4.29% |
| RS Rating | 58 |
| GTGD TB | 282.6 tỷ/phiên |

**Logic phân tích:**
- Giá: 16
- MA50: 15 ✓
- MA150: 12 ✓
- MA200: 11 ✓
- → Stage 2 (Uptrend): Giá > MA50 > MA150 > MA200
- ✓ Thanh khoản: 282.6 tỷ/phiên
- ✓ SEPA: Stage 2
- ✗ RS Rating: 58
- ✓ vs 52wH: 7.6%

**Kết luận:** Score = 91/100

#### 9. KBC (Tổng Công ty Phát triển Đô thị...)

**Sector:** VNREAL (Bất động sản)

**Dữ liệu:**
| Metric | Giá trị |
|--------|---------|
| Giá | 36 |
| Thay đổi 1D | -0.70% |
| Thay đổi 5D | +2.29% |
| Thay đổi 1M | +2.00% |
| MA20 | 35 |
| MA50 | 35 |
| MA150 | 32 |
| MA200 | 31 |
| 52w High | 43 |
| vs 52wH | 17.2% |
| RS vs VNI | -0.72% |
| RS Rating | 68 |
| GTGD TB | 214.2 tỷ/phiên |

**Logic phân tích:**
- Giá: 36
- MA50: 35 ✓
- MA150: 32 ✓
- MA200: 31 ✓
- → Stage 2 (Uptrend): Giá > MA50 > MA150 > MA200
- ✓ Thanh khoản: 214.2 tỷ/phiên
- ✓ SEPA: Stage 2
- ✗ RS Rating: 68
- ✓ vs 52wH: 17.2%

**Kết luận:** Score = 88/100

#### 10. HDG (Công ty Cổ phần Tập đoàn Hà Đô...)

**Sector:** VNREAL (Bất động sản)

**Dữ liệu:**
| Metric | Giá trị |
|--------|---------|
| Giá | 32 |
| Thay đổi 1D | -0.92% |
| Thay đổi 5D | -0.31% |
| Thay đổi 1M | +4.55% |
| MA20 | 32 |
| MA50 | 32 |
| MA150 | 28 |
| MA200 | 27 |
| 52w High | 36 |
| vs 52wH | 11.5% |
| RS vs VNI | +1.82% |
| RS Rating | 75 |
| GTGD TB | 128.8 tỷ/phiên |

**Logic phân tích:**
- Giá: 32
- MA50: 32 ✓
- MA150: 28 ✓
- MA200: 27 ✓
- → Stage 2 (Uptrend): Giá > MA50 > MA150 > MA200
- ✓ Thanh khoản: 128.8 tỷ/phiên
- ✓ SEPA: Stage 2
- ✓ RS Rating: 75
- ✓ vs 52wH: 11.5%

**Kết luận:** Score = 85/100

---

## 🤖 AI ANALYSIS

Chào bạn, với tư cách là chuyên gia phân tích theo phương pháp CANSLIM, tôi xin đưa ra những nhận định chi tiết dựa trên báo cáo dữ liệu ngày 27/11/2025 như sau:

### 1. NHẬN ĐỊNH CHUNG VỀ MARKET & SECTOR ROTATION

**Bối cảnh thị trường (Market Direction - M):**
*   **VNIndex:** 1,684 điểm, xu hướng tăng (+2.72% trong 1 tháng) cho thấy thị trường đang ở trong **Uptrend (Xu hướng tăng)** được xác nhận. Mốc 1,684 là vùng điểm số cao, tâm lý thị trường đang hưng phấn.
*   **Dòng tiền (Sector Rotation):** Đây là điểm **đáng báo động và cũng là cơ hội lớn nhất**. Chúng ta đang chứng kiến trạng thái **"Độc trụ" (One-Pillar Market)**.
    *   Chỉ duy nhất nhóm **VNREAL (Bất động sản)** là Leading với RS dương cực lớn (+10.97%).
    *   Toàn bộ 6 nhóm ngành còn lại (Tài chính, Công nghệ, Vật liệu...) đều đang Lagging (Suy yếu) với RS âm.
*   **Kết luận:** Dòng tiền thông minh (Smart Money) đang rút khỏi các nhóm ngành khác để tập trung "đánh thốc" nhóm Bất động sản. Đây là giai đoạn **siêu kiếm tiền** nếu bạn cầm Bất động sản, nhưng là **rủi ro lớn** nếu thị trường điều chỉnh, vì không có dòng nào khác đỡ chỉ số.

### 2. TOP 3 CỔ PHIẾU TIỀM NĂNG NHẤT (THEO TIÊU CHÍ CANSLIM)

Dựa trên danh sách Top 10 đều thuộc VNREAL và đang ở Stage 2 (Giai đoạn tăng giá), tôi chọn ra 3 cổ phiếu đại diện cho 3 khẩu vị rủi ro, ưu tiên chỉ số RS (Sức mạnh giá) và Score tổng hợp:

#### **#1. VIC (Vingroup) - The Big Leader (Leader Vốn hóa lớn)**
*   **Dữ liệu:** Score: 100 | RS: 99 | Stage 2.
*   **Lý do chọn:**
    *   **RS 99 & Score 100:** Đây là chỉ số tuyệt đối. VIC đang là cổ phiếu mạnh nhất thị trường hiện tại. Trong CANSLIM, chúng ta mua cổ phiếu mạnh nhất, không mua cổ phiếu rẻ nhất.
    *   **Vai trò dẫn dắt:** Với RS ngành VNREAL +10.97%, VIC chắc chắn là đầu tàu kéo cả Index vượt 1,684. Dòng tiền tổ chức (Institutional Sponsorship) đang nằm tại đây.
*   **Phù hợp:** Nhà đầu tư NAV lớn, thích sự an toàn của Bluechip nhưng vẫn muốn biên lợi nhuận cao theo đà tăng trưởng nóng.

#### **#2. LGL (Long Giang Land) - The High Growth (Mid-cap Bứt phá)**
*   **Dữ liệu:** Score: 100 | RS: 99 | Stage 2.
*   **Lý do chọn:**
    *   **Đồng hạng nhất:** Cùng Score và RS với VIC nhưng là Mid-cap/Small-cap, LGL sẽ có độ "bay" (Beta) cao hơn. Khi sóng ngành vào giai đoạn cực thịnh, các mã Mid-cap có chỉ số RS 99 thường mang lại lợi nhuận tính bằng lần nhanh nhất.
    *   **Sự đồng thuận:** Việc cả Bluechip (VIC) và Midcap (LGL) đều max điểm cho thấy sóng BĐS lan tỏa đều từ lớn đến nhỏ.

#### **#3. HDG (Tập đoàn Hà Đô) - The Stable Runner (Tăng trưởng bền vững)**
*   **Dữ liệu:** Score: 85 | RS: 75 | Stage 2.
*   **Lý do chọn:**
    *   Mặc dù KBC hay KDH là những tên tuổi lớn, nhưng **HDG có RS (75)** cao hơn KDH (59) và KBC (68). Trong phương pháp CANSLIM, sức mạnh giá tương đối là yếu tố then chốt.
    *   HDG thường có cơ bản tốt (C - Current Earnings & A - Annual Earnings thường ổn định nhờ mảng Năng lượng hỗ trợ BĐS). Đây là lựa chọn cân bằng giữa đầu cơ theo sóng và an toàn cơ bản.

### 3. CHIẾN LƯỢC VÀO LỆNH (ACTION PLAN)

Do toàn bộ Watchlist đều là **Stage 2** và RS rất cao, chiến lược phù hợp nhất là **Trend Following (Bám theo xu hướng)** và **Pyramiding (Nhồi lệnh)**:

*   **Điểm mua (Buy Point):**
    *   **Kịch bản 1 (Breakout):** Mua khi giá vượt qua đỉnh gần nhất (Pivot point) với khối lượng lớn hơn trung bình 50 phiên ít nhất 40-50%.
    *   **Kịch bản 2 (Pullback):** Do RS ngành quá cao (+10.97%), khả năng sẽ có nhịp chỉnh ngắn hạn. Canh mua khi cổ phiếu test lại đường **MA10 hoặc MA20** (đường trung bình 10/20 ngày) với khối lượng thấp (cạn cung).
*   **Phân bổ vốn:**
    *   Tập trung 100% tỷ trọng trading vào nhóm **VNREAL**. Tuyệt đối không bắt đáy các nhóm Lagging (Bank, Thép, Chứng khoán) lúc này vì chi phí cơ hội quá lớn.
    *   Chia vốn: 40% VIC, 30% HDG, 30% LGL.
*   **Cách đi lệnh:**
    *   Lần 1: Giải ngân 50% vị thế tại điểm mua chuẩn.
    *   Lần 2: Mua thêm 30% khi giá tăng 2-3% từ điểm mua.
    *   Lần 3: Mua nốt 20% còn lại khi xu hướng được khẳng định rõ ràng.

### 4. CẢNH BÁO RỦI RO (RISK MANAGEMENT)

Dù chỉ số rất đẹp, nhưng theo nguyên tắc CANSLIM, nhà đầu tư cần thận trọng các yếu tố sau tại thời điểm 27/11/2025:

1.  **Rủi ro tập trung (Concentration Risk):** Thị trường tăng chỉ nhờ 1 trụ duy nhất (VNREAL). Nếu có tin tức xấu về pháp lý Bất động sản hoặc lãi suất tăng, VNREAL quay đầu thì VNIndex sẽ sập mạnh vì không có dòng nào khác (Bank, Tech...) đủ sức đỡ chỉ số (do các dòng này đang Lagging).
2.  **Trạng thái quá mua (Overbought):** RS ngành +10.97% là con số rất cao, thường báo hiệu sự hưng phấn tột độ (Climax Top). Cần cảnh giác các phiên phân phối (Distribution Days) với khối lượng lớn nhưng giá không tăng.
3.  **Quy tắc cắt lỗ:** Tuân thủ kỷ luật sắt.
    *   Cắt lỗ **7-8%** từ điểm mua không ngoại lệ.
    *   Nếu cổ phiếu mất mốc **MA20** với khối lượng lớn, hãy thoát hàng ngay lập tức để bảo toàn vốn.

**Khuyến nghị cuối cùng:** "Trend is your friend". Hãy đánh mạnh vào Bất động sản ngay lúc này nhưng giữ tay trên nút "Bán" để sẵn sàng nhảy tàu khi dòng tiền đảo chiều.

---

## 📋 TÓM TẮT

- **Ngành mạnh:** VNREAL
- **Watchlist:** LGL, VIC, HLD, V21, KDH, PXL, TIX, TN1, KBC, HDG
- **API tiết kiệm:** ~370 calls

**Lưu ý:** Đây chỉ là công cụ sàng lọc. Cần phân tích chi tiết trước khi đầu tư.
