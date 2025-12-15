# 📊 Hướng dẫn đọc Volume Confirmation

## Giới thiệu

Volume Confirmation là tính năng phân tích hành vi volume để xác nhận độ tin cậy của các pattern kỹ thuật (VCP, Cup&Handle, Flat Base). Theo phương pháp **IBD/Minervini**, pattern giá chỉ đáng tin cậy khi được xác nhận bởi volume.

---

## 📌 Ý nghĩa các Icon

| Icon | Tên | Điều kiện | Điểm Volume | Độ tin cậy |
|------|-----|-----------|-------------|------------|
| 🚀 | **Breakout Ready** | Có cả Shakeout + Dry-up | 60-80 | ⭐⭐⭐⭐⭐ |
| ✓ | **Partial Confirmed** | Có Shakeout HOẶC Dry-up | 15-40 | ⭐⭐⭐ |
| ⭕ | **No Confirmation** | Không có cả hai | 0-15 | ⭐⭐ |

---

## 🔍 Chi tiết từng thành phần

### 1. ✅ Shakeout (Phiên rũ bỏ)

```
Điều kiện: Volume > 150% trung bình 50 ngày + Giá giảm > 2%
```

**Ý nghĩa theo VSA (Volume Spread Analysis):**
- "Smart Money" cố tình đẩy giá xuống mạnh để "rũ" các tay yếu (weak hands) ra khỏi cổ phiếu
- Volume lớn + giá giảm = nhiều người hoảng loạn bán
- **Sau shakeout**, nguồn cung cạn kiệt → giá dễ tăng mạnh

**Điểm cộng:** +15 đến +20 điểm

---

### 2. ✅ Dry-up (Volume cạn kiệt)

```
Điều kiện: Volume 5 ngày gần nhất < 60% trung bình 20 ngày
```

**Ý nghĩa:**
- Nguồn cung (người bán) đã cạn kiệt gần pivot point
- Không còn ai muốn bán nữa → chỉ cần lực cầu nhỏ cũng đẩy giá lên
- **Đây là tín hiệu breakout sắp xảy ra**

**Điểm cộng:** +15 đến +25 điểm

---

### 3. 🚀 Breakout Ready (Sẵn sàng bứt phá)

```
Điều kiện: Có CẢ Shakeout + Dry-up
```

**Ý nghĩa:**
- Đây là **setup lý tưởng nhất** theo Minervini
- Weak hands đã bị rũ bỏ (shakeout) + Nguồn cung cạn kiệt (dry-up)
- **Chỉ cần một volume spike khi giá vượt pivot = breakout thành công**

**Điểm cộng:** +20 điểm bonus

---

### 4. Volume Declining (Volume giảm dần)

```
Điều kiện: Volume nửa sau 20 ngày < 80% volume nửa đầu
```

**Ý nghĩa:**
- Trong base, volume nên giảm dần
- Cho thấy nguồn cung đang cạn dần
- Không bắt buộc nhưng là dấu hiệu tốt

**Điểm cộng:** +8 đến +15 điểm

---

## 📈 Hướng dẫn sử dụng trong giao dịch

### Quy tắc mua theo Volume Status

| Volume Status | Hành động | Size Position |
|---------------|-----------|---------------|
| 🚀 **Breakout Ready** | **MUA ngay** khi vượt Buy Point với volume > 1.4x | 100% planned position |
| ✓ **Partial** (Shakeout) | Mua pilot, chờ thêm dry-up | 30-50% position |
| ✓ **Partial** (Dry-up) | Mua pilot nếu RS > 90 | 30-50% position |
| ⭕ **No Confirmation** | KHÔNG MUA - chỉ watchlist | 0% |

### Quy tắc đơn giản

```
┌─────────────────────────────────────────────────────────────┐
│  1. 🚀 BREAKOUT READY → Mua 100% position khi vượt pivot   │
│  2. ✓ PARTIAL        → Mua 30-50% pilot, đợi confirm thêm  │
│  3. ⭕ NO CONFIRM     → KHÔNG MUA, chỉ watchlist            │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Cách đọc Volume Score

Volume Score từ **0-80 điểm**, được tính như sau:

| Thành phần | Điểm |
|------------|------|
| Shakeout detected | +15-20 |
| Dry-up confirmed | +15-25 |
| Volume declining trong base | +8-15 |
| Breakout Ready bonus | +20 |

### Đánh giá theo Score

| Score | Đánh giá | Hành động |
|-------|----------|-----------|
| **60-80** | Excellent | Mua confident, full position |
| **30-59** | Good | Mua pilot position 50% |
| **15-29** | Fair | Watchlist, chờ thêm tín hiệu |
| **0-14** | Poor | Không nên mua |

---

## 📋 Ví dụ thực tế

### Ví dụ 1: MSH - Breakout Ready 🚀

```
Pattern: Cup & Handle (Quality: 85)
- 📊 Volume Score: 60/80
- ✅ Shakeout detected (ngày 25/11 volume spike -3%)
- ✅ Dry-up confirmed (vol 5 ngày = 45% avg)
- 🚀 BREAKOUT READY

→ Hành động: MUA ngay khi vượt Buy Point với volume > 1.4x
→ Position: 100% planned size
```

### Ví dụ 2: FRT - Partial Confirmed ✓

```
Pattern: Cup & Handle (Quality: 94)
- 📊 Volume Score: 15/80
- ✅ Shakeout detected
- ⭕ No dry-up

→ Hành động: Mua pilot position, chờ dry-up
→ Position: 30-50% planned size
```

### Ví dụ 3: MIG - No Confirmation ⭕

```
Pattern: Cup & Handle (Quality: 85)
- 📊 Volume Score: 8/80
- ⭕ No shakeout
- ⭕ No dry-up

→ Hành động: KHÔNG MUA, thêm vào watchlist
→ Position: 0%
```

---

## ⚠️ Lưu ý quan trọng

1. **Volume Confirmation là FILTER, không phải TRIGGER**
   - Dùng để loại bỏ pattern yếu
   - Không phải tín hiệu mua/bán độc lập

2. **Kết hợp với các yếu tố khác:**
   - RS Rating >= 70
   - Market Score >= 40
   - Sector đang Improving/Leading

3. **Breakout phải có volume:**
   - Ngày breakout volume >= 1.4x average
   - Nếu breakout low volume → có thể là fake breakout

---

## 📚 Tham khảo

- **Mark Minervini** - Trade Like a Stock Market Wizard
- **William O'Neil** - How to Make Money in Stocks (CANSLIM)
- **Tom Williams** - Master the Markets (VSA)

---

*Tài liệu này là một phần của hệ thống CANSLIM Scanner.*
*Cập nhật: 2025-12-09*
