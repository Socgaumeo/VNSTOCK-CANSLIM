# 📊 BÁO CÁO SECTOR ROTATION + STOCK SCREENING
**Ngày:** 27/11/2025 19:15

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

Chào bạn, với tư cách là một chuyên gia phân tích theo phương pháp **CANSLIM**, tôi xin phân tích báo cáo thị trường ngày 27/11/2025 dựa trên dữ liệu bạn cung cấp như sau:

---

### 1. Nhận định chung về Rotation Ngành (Chữ M - Market Direction)

**Bối cảnh:** VNIndex đang ở mức cao 1,684 điểm (tăng trưởng tốt +2.72% trong 1 tháng). Tuy nhiên, bức tranh dòng tiền đang cho thấy sự **cực đoan và rủi ro tiềm ẩn**.

*   **Sự thống trị đơn độc của VNREAL (Bất động sản):** Đây là điểm nhấn quan trọng nhất. VNREAL là nhóm ngành **duy nhất** nằm trong vùng "Leading" với RS dương cực mạnh (+10.97%).
*   **Sự suy yếu của toàn bộ thị trường còn lại:** 6/7 nhóm ngành còn lại (VNCONS, VNMAT, VNFIN, VNCOND, VNHEAL, VNIT) đều có RS âm và nằm ở vùng "Lagging". Đặc biệt là VNFIN (Tài chính/Bank/Chứng khoán) và VNIT (Công nghệ) đang suy yếu.
*   **Kết luận về dòng tiền:** Dòng tiền đầu cơ và dòng tiền lớn đang đổ dồn toàn lực vào Bất động sản ("All-in"). Hiện tượng này gọi là **"Sự phân hóa cực đại"**. Thị trường đang tăng điểm chủ yếu nhờ lực kéo từ nhóm Bất động sản (đặc biệt là VIC).
    *   *Tích cực:* Sóng ngành Bất động sản cực kỳ mạnh, là cơ hội kiếm lời nhanh nhất hiện tại.
    *   *Tiêu cực:* Độ rộng thị trường (Market Breadth) rất hẹp. Nếu nhóm VNREAL điều chỉnh, VNIndex sẽ không có nhóm ngành nào khác đỡ chỉ số, dẫn đến rủi ro sập hầm (bull trap) cao.

---

### 2. Top 3 Cổ phiếu Tiềm năng nhất (Chữ L - Leader)

Dựa trên tiêu chí CANSLIM (ưu tiên RS > 80, Score cao và đang ở Stage 2), tôi chọn ra 3 cổ phiếu sau từ danh sách Top 10:

#### **#1. LGL (Long Giang Land) - Nhóm Speculative Leader**
*   **Thông số:** Score 100 | RS 99 | Stage 2.
*   **Lý do chọn:**
    *   **Sức mạnh tuyệt đối:** Đạt điểm tuyệt đối cả về Score và RS. RS = 99 cho thấy nó đang mạnh hơn 99% cổ phiếu trên thị trường.
    *   **Tính chất sóng:** Với đặc thù vốn hóa vừa và nhỏ, LGL thường chạy rất "bốc" khi sóng Bất động sản vào nhịp chính. Đây là đại diện cho dòng tiền đầu cơ hạng nặng.

#### **#2. VIC (Vingroup) - Nhóm Institutional Leader (Big Cap)**
*   **Thông số:** Score 100 | RS 99 | Stage 2.
*   **Lý do chọn:**
    *   **Dẫn dắt chỉ số:** Khi một Bluechip như VIC đạt RS 99, nghĩa là "Smart Money" (dòng tiền tổ chức) đang dùng mã này để đẩy VNIndex.
    *   **Xác nhận xu hướng:** VIC tăng mạnh thường xác nhận sóng Bất động sản là sóng thật chứ không chỉ là sóng penny. Tuy nhiên, VIC thường khó giao dịch hơn do tính điều tiết chỉ số.

#### **#3. PXL (KCN Dầu khí Long Sơn) - Nhóm Breakout Tiềm năng**
*   **Thông số:** Score 91 | RS 80 | Stage 2.
*   **Lý do chọn:**
    *   **RS chuẩn CANSLIM:** RS 80 là ngưỡng chuẩn của một cổ phiếu dẫn đầu (Leader). Trong khi các mã khác như KDH, KBC có RS dưới 70 (hơi yếu), thì PXL giữ được sức mạnh giá rất tốt.
    *   **Score cao (91):** Cho thấy nền tảng cơ bản và kỹ thuật kết hợp đều ổn định.

*(Lưu ý: Tôi loại KDH, KBC, HDG khỏi Top 3 vì RS < 80, cho thấy chúng đang chạy theo sau (laggards) so với những con dẫn đầu như LGL, VIC).*

---

### 3. Chiến lược vào lệnh cụ thể (Timing)

Vì toàn bộ Top 10 đều ở **Stage 2 (Giai đoạn tăng giá)**, chiến lược phù hợp nhất là **Trend Following (Đu theo xu hướng) và Breakout**.

*   **Điểm mua (Pivot Point):**
    *   Chỉ mua khi giá vượt qua điểm Pivot của các mẫu hình củng cố (Nền giá phẳng, Cốc tay cầm, hoặc 2 đáy).
    *   **Khối lượng:** Phiên bùng nổ phải có Volume > 40-50% so với trung bình 20 phiên.
    *   **Vùng mua hợp lý:** Chỉ mua trong biên độ 5% từ điểm Pivot. Không được mua đuổi (Chase) khi giá đã chạy quá 5% từ nền, vì RS 99 báo hiệu giá đã tăng nóng.

*   **Chiến lược giải ngân (Pyramiding):**
    *   Lần 1: 50% vị thế tại điểm Breakout chuẩn.
    *   Lần 2: 30% vị thế khi giá tăng tiếp 2-3% và giữ vững trên nền.
    *   Lần 3: 20% còn lại khi xu hướng được xác nhận hoàn toàn.

*   **Lưu ý đặc biệt với nhóm VNREAL hiện tại:** Do RS ngành quá cao (+10.97%), hãy canh các nhịp **Pullback (kéo ngược)** về đường MA10 hoặc MA20 với volume thấp để mở vị thế mua mới, thay vì mua đuổi giá trần.

---

### 4. Cảnh báo Rủi ro (Risk Management)

Dưới góc nhìn CANSLIM, dù cơ hội lớn nhưng rủi ro đang ở mức **BÁO ĐỘNG ĐỎ** vì các lý do sau:

1.  **Mất cân bằng nghiêm trọng:** Chỉ có 1 trụ đỡ là Bất động sản. Nếu có tin tức vĩ mô xấu về lãi suất hoặc pháp lý bất động sản, thị trường sẽ không có nhóm ngành nào khác (như Bank hay Chứng khoán) để đỡ giá -> VNIndex có thể giảm rất sâu và nhanh.
2.  **Rủi ro từ VIC:** VIC đạt RS 99 là tín hiệu rất mạnh nhưng cũng rất nguy hiểm. Trong quá khứ, khi VIC chạy nước rút thường là giai đoạn cuối của một chu kỳ tăng ngắn hạn (Blow-off top).
3.  **RS quá nhiệt:** LGL và VIC đều có RS 99. Theo thống kê, khi RS đạt mức cực đại này, cổ phiếu thường dễ gặp áp lực chốt lời ngắn hạn.
4.  **Quy tắc cắt lỗ:** Tuyệt đối tuân thủ quy tắc cắt lỗ **7-8%**. Với thị trường chỉ có 1 chân trụ, khi đảo chiều sẽ rất khốc liệt (sàn hàng loạt).

**Khuyến nghị:** Giải ngân tỷ trọng vừa phải, tập trung tối đa vào VNREAL nhưng phải theo sát diễn biến trong phiên. Tuyệt đối không bắt đáy các nhóm ngành đang Lagging (Bank, Thép, Chứng khoán) lúc này vì quy tắc "Yếu thì thường sẽ yếu thêm".

---

## 📋 TÓM TẮT

- **Ngành mạnh:** VNREAL
- **Watchlist:** LGL, VIC, HLD, V21, KDH, PXL, TIX, TN1, KBC, HDG
- **API tiết kiệm:** ~370 calls

**Lưu ý:** Đây chỉ là công cụ sàng lọc. Cần phân tích chi tiết trước khi đầu tư.
