# 📊 BÁO CÁO SECTOR ROTATION + STOCK SCREENING
**Ngày:** 27/11/2025 20:51

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
| 1 | VNREAL | Bất động sản | +0.56% | +6.56% | +3.83% | 🚀 Leading |
| 2 | VNCONS | Tiêu dùng thiết yếu | -0.79% | +1.84% | -0.88% | ⛔ Lagging |
| 3 | VNCOND | Tiêu dùng không thiết yếu | +0.50% | -4.16% | -6.88% | ⛔ Lagging |
| 4 | VNMAT | Nguyên vật liệu | -0.49% | -1.07% | -3.79% | ⛔ Lagging |
| 5 | VNFIN | Tài chính | +0.06% | -5.67% | -8.40% | ⛔ Lagging |
| 6 | VNIT | Công nghệ | +0.57% | -1.79% | -4.52% | ⛔ Lagging |
| 7 | VNHEAL | Y tế | +0.83% | -1.85% | -4.58% | ⛔ Lagging |

### Logic xác định Phase:

| Phase | Điều kiện |
|-------|-----------|
| 🚀 Leading | RS > +3% VÀ momentum 5D > 0 |
| 📈 Improving | RS > 0% VÀ đang tăng tốc (5D > 1D) |
| 📉 Weakening | RS > 0% NHƯNG đang giảm tốc |
| ⛔ Lagging | RS < 0% |

### Chi tiết logic từng ngành:

**VNREAL (Bất động sản):**
- RS > +3% (+3.83%): Outperform mạnh
- 5D > 0 (+4.90%): Momentum tích cực
- Giá > MA20: ✓
- → LEADING

**VNCONS (Tiêu dùng thiết yếu):**
- RS < 0 (-0.88%): Underperform
- → LAGGING

**VNCOND (Tiêu dùng không thiết yếu):**
- RS < 0 (-6.88%): Underperform
- → LAGGING

**VNMAT (Nguyên vật liệu):**
- RS < 0 (-3.79%): Underperform
- → LAGGING

**VNFIN (Tài chính):**
- RS < 0 (-8.40%): Underperform
- → LAGGING

**VNIT (Công nghệ):**
- RS < 0 (-4.52%): Underperform
- → LAGGING

**VNHEAL (Y tế):**
- RS < 0 (-4.58%): Underperform
- → LAGGING

---

## 📌 BƯỚC 3: XÁC ĐỊNH NGÀNH MỤC TIÊU

| Loại | Ngành |
|------|-------|
| 🚀 Leading | VNREAL |
| 📈 Improving | Không có |
| ⛔ Không đầu tư | VNCONS, VNCOND, VNMAT, VNFIN, VNIT, VNHEAL |

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

Chào bạn, với tư cách là một chuyên gia phân tích theo phương pháp **CANSLIM** của William O'Neil, dựa trên dữ liệu báo cáo ngày 27/11/2025 bạn cung cấp, tôi xin đưa ra những phân tích chuyên sâu như sau:

### 1. Nhận định chung về Rotation Ngành (Luân chuyển dòng tiền)

**Tình trạng thị trường: "Độc mã" (Single-Sector Rally)**

*   **Chữ M (Market Direction - Xu hướng thị trường):** VNIndex ở mức 1,684 điểm với đà tăng 1 tháng là +2.72% cho thấy thị trường đang trong xu hướng tăng (Uptrend). Tuy nhiên, chất lượng xu hướng đang có vấn đề lớn.
*   **Sự tập trung cực đoan:** Bức tranh Sector Rotation cho thấy sự mất cân bằng nghiêm trọng. Chỉ duy nhất **VNREAL (Bất động sản)** nằm trong vùng **Leading** với RS dương (+3.83%). Tất cả 6 nhóm ngành còn lại (Tài chính, Thép, Chứng khoán, Công nghệ...) đều ở vùng **Lagging** với RS âm nặng.
*   **Ý nghĩa theo CANSLIM:** Đây là dấu hiệu của việc dòng tiền đầu cơ cực mạnh đang đổ dồn vào một nhóm ngành duy nhất. Trong phương pháp CANSLIM, chúng ta luôn tìm kiếm "nhóm ngành dẫn dắt" (Leading Group). Hiện tại, không có bất kỳ sự nghi ngờ nào: **Bất động sản là vua.**
*   **Cơ hội và Rủi ro:** Cơ hội sinh lời trong nhóm Bất động sản là cực lớn (siêu kiếm tiền), nhưng rủi ro thị trường chung điều chỉnh là cao vì "một cây làm chẳng nên non". Nếu VNREAL điều chỉnh, VNIndex sẽ không có trụ đỡ từ các nhóm Bank hay Thép.

### 2. Top 3 Cổ phiếu tiềm năng nhất và Lý do

Dựa trên tiêu chí CANSLIM (đặc biệt là yếu tố L - Leader và RS - Relative Strength), và danh sách Watchlist toàn bộ là BĐS, tôi chọn ra 3 cổ phiếu sau:

#### **Top 1: VIC (Vingroup)**
*   **Thông số:** Score 100 | RS 99 | Stage 2
*   **Lý do chọn:**
    *   **RS 99:** Đây là chỉ số sức mạnh tương đối tuyệt đối. VIC đang mạnh hơn 99% cổ phiếu trên thị trường.
    *   **Vai trò Leader:** Với vốn hóa lớn nhất ngành, khi VIC có RS 99 và Score 100, nó chính là "nhạc trưởng" kéo cả ngành BĐS và VNIndex đi lên.
    *   **Yếu tố Institutional Sponsorship (I):** VIC luôn là khẩu vị của các quỹ lớn. Khi dòng tiền lớn quay lại VIC, xu hướng thường rất bền vững.

#### **Top 2: LGL (Long Giang Land)**
*   **Thông số:** Score 100 | RS 99 | Stage 2
*   **Lý do chọn:**
    *   **Small-cap Leader:** Trong khi VIC là trụ, thì LGL đại diện cho nhóm Mid/Small-cap có tính đầu cơ cao (High Beta).
    *   **Score 100:** Điểm số tuyệt đối cho thấy các chỉ báo kỹ thuật và cơ bản (cần check thêm C & A) đang đồng thuận.
    *   **Đặc tính CANSLIM:** O'Neil rất thích những cổ phiếu vốn hóa vừa và nhỏ có tốc độ tăng trưởng giá "điên cuồng" trong giai đoạn thị trường tăng tốc.

#### **Top 3: HDG (Hà Đô Group)**
*   **Thông số:** Score 85 | RS 75 | Stage 2
*   **Lý do chọn:**
    *   **Sự bền vững:** Mặc dù Score và RS thấp hơn VIC/LGL, nhưng HDG thường có cơ bản (C & A) rất tốt nhờ mảng Năng lượng bổ trợ cho BĐS. Đây là lựa chọn an toàn hơn cho danh mục.
    *   **Dư địa tăng:** RS 75 cho thấy cổ phiếu đang mạnh nhưng chưa bị "quá nóng" (Overbought) như nhóm RS 99. Đây có thể là điểm mua pullback hoặc xây nền giá mới an toàn hơn.

*(Lưu ý: KBC cũng là ứng viên tốt, nhưng HDG thường có cấu trúc tài chính ổn định hơn trong mắt các nhà đầu tư CANSLIM thận trọng).*

### 3. Chiến lược vào lệnh cụ thể (Action Plan)

Vì toàn bộ thị trường đang phụ thuộc vào VNREAL, chiến lược cần **Aggressive (Quyết liệt)** nhưng **Discipline (Kỷ luật)**:

*   **Mẫu hình (Chart Pattern):** Chỉ mua khi các cổ phiếu trên (VIC, LGL, HDG) break out khỏi các nền giá kiến tạo:
    *   *Cốc tay cầm (Cup with Handle)*
    *   *Nền giá phẳng (Flat Base)*
    *   *Mô hình hai đáy (Double Bottom)*
*   **Điểm mua (Pivot Point):**
    *   Mua khi giá vượt qua điểm Pivot với khối lượng (Volume) tăng đột biến (ít nhất +40-50% so với trung bình 50 phiên).
    *   Phạm vi mua: Chỉ mua trong biên độ **5% từ điểm Pivot**. Không được đuổi giá (Chase) nếu giá đã chạy quá 5%.
*   **Cách đi vốn (Pyramiding):**
    *   Lệnh 1: 50% tỷ trọng dự kiến ngay tại điểm Breakout.
    *   Lệnh 2: 30% khi giá tăng 2-3% từ điểm mua 1.
    *   Lệnh 3: 20% khi hàng về và có lãi đệm.
*   **Lưu ý đặc biệt:** Vì VNREAL đang có RS cực cao (+3.83%), khả năng nhiều mã đã chạy nước rút (Climax Run). Hãy ưu tiên các mã **mới thoát khỏi nền giá số 1 hoặc số 2**. Tránh xa các mã đã tăng >20% từ nền giá gần nhất mà chưa tích lũy lại.

### 4. Cảnh báo rủi ro (Risk Management)

Là một nhà giao dịch CANSLIM, bạn cần nhìn thấy những rủi ro sau trong báo cáo này:

1.  **Rủi ro "Chân đơn" (Market Breadth):** Thị trường tăng điểm nhưng chỉ có 1 ngành tăng (VNREAL), trong khi Tài chính (VNFIN) và Công nghệ (VNIT) giảm mạnh. Đây là trạng thái rất mong manh. Nếu Bất động sản bị chốt lời, VNIndex sẽ sập mạnh vì không có dòng khác đỡ.
    *   *Hành động:* **Tuyệt đối tuân thủ quy tắc cắt lỗ 7-8% không ngoại lệ.**
2.  **Kiểm tra Yếu tố Cơ bản (C & A):** Báo cáo trên thuần túy về kỹ thuật (Technical & Screening).
    *   Cần kiểm tra ngay: VIC, LGL, HDG có tăng trưởng lợi nhuận quý gần nhất (EPS Quý) > 25% hay không? Có câu chuyện mới (New Product/Service) không? Nếu chỉ tăng vì dòng tiền đầu cơ mà không có lợi nhuận (Earnings) hỗ trợ, giá sẽ sụp đổ rất nhanh sau đó.
3.  **RS quá cao (Overheating):** Các mã Top đầu đều có RS 99. Điều này thường xuất hiện ở giai đoạn cuối của một chu kỳ tăng giá ngắn hạn. Hãy cảnh giác với các phiên phân phối khối lượng lớn mà giá không tăng (Churning).

**Kết luận:** Dồn toàn lực theo dõi nhóm **VNREAL**. Mở vị thế mua nếu xuất hiện điểm phá vỡ nền giá chuẩn. Tuy nhiên, hãy giữ tỷ trọng tiền mặt nhất định và sẵn sàng thoát hàng ngay lập tức nếu nhóm Bất động sản có dấu hiệu tạo đỉnh, vì không còn nhóm ngành nào khác để trú ẩn lúc này.

---

## 📋 TÓM TẮT

- **Ngành mạnh:** VNREAL
- **Watchlist:** LGL, VIC, HLD, V21, KDH, PXL, TIX, TN1, KBC, HDG
- **API tiết kiệm:** ~370 calls

**Lưu ý:** Đây chỉ là công cụ sàng lọc. Cần phân tích chi tiết trước khi đầu tư.
