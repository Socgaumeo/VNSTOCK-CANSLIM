# BÁO CÁO THẨM ĐỊNH DỰ ÁN: VNSTOCK-CANSLIM
**Người thực hiện:** Antigravity (Vai trò: Quản lý quỹ 20 năm kinh nghiệm)
**Ngày:** 04/12/2025

---

## 1. ĐÁNH GIÁ TỔNG QUAN & TÍNH KHẢ THI TẠI VIỆT NAM

### 🌟 Nhận định chung
Dự án có **khung sườn kỹ thuật (Technical Framework) rất tốt**. Việc kết hợp **Volume Profile** và **Market Timing** là điểm sáng, cho thấy tư duy giao dịch hiện đại, không chỉ rập khuôn sách giáo khoa.

Tuy nhiên, để gọi là "CANSLIM" đúng nghĩa thì dự án đang **thiếu "trái tim"**, đó là dữ liệu Cơ bản (Fundamental Data - C & A). Hiện tại code đang dùng dữ liệu giả lập (placeholder) hoặc tính toán sơ sài cho các chỉ số tài chính.

### 🇻🇳 Tính phù hợp với thị trường Việt Nam
*   **Độ trễ T+2.5:** Hệ thống hiện tại thiên về phân tích cuối ngày (EOD), phù hợp.
*   **Dòng tiền đầu cơ:** Module Market Timing và Sector Rotation rất quan trọng ở VN vì dòng tiền luân chuyển nhanh. Dự án đã làm tốt phần này.
*   **Tin đồn & "Game":** Module News có tích hợp AI để đọc tin là hướng đi đúng, nhưng cần filter kỹ hơn vì báo chí VN thường "ra tin là bán".

---

## 2. PHÂN TÍCH CHI TIẾT TIÊU CHÍ CANSLIM

| Tiêu chí | Trạng thái trong Code | Đánh giá của Quản lý quỹ |
| :--- | :--- | :--- |
| **C (Current Earnings)** | 🔴 **YẾU** | Code hiện tại (`FundamentalAnalyzer`) đang dùng logic giả định hoặc thiếu nguồn data EPS quý/năm chuẩn. Ở VN, EPS tăng trưởng >20% là key driver, thiếu cái này là mất 50% sức mạnh CANSLIM. |
| **A (Annual Earnings)** | 🔴 **YẾU** | Tương tự C. Cần data lịch sử 3 năm. |
| **N (New)** | 🟡 **TRUNG BÌNH** | Đã có logic `Distance from 52w High` (New Highs). Phần "New Products/Management" dựa vào News AI là sáng tạo nhưng độ chính xác phụ thuộc vào nguồn tin. |
| **S (Supply/Demand)** | 🟢 **TỐT** | Có Volume Profile, Volume Ratio. Đây là điểm mạnh nhất của dự án. Nhận diện được vùng cung cầu. |
| **L (Leader)** | 🟢 **TỐT** | Logic tính RS Rating (Relative Strength) mô phỏng IBD (trọng số 40-30-20-10) là rất chuẩn. Đây là vũ khí mạnh nhất để lọc cổ phiếu dẫn dắt. |
| **I (Institutional)** | 🟡 **KHÁ** | Theo dõi được Khối ngoại. Tuy nhiên thiếu dữ liệu **Tự doanh** và **Giao dịch thỏa thuận** - hai ẩn số lớn của "tay to" tại VN. |
| **M (Market)** | 🟢 **TỐT** | Module 1 dùng MA + Volume Profile + Breadth để định thời điểm thị trường là hợp lý. |

---

## 3. ĐÁNH GIÁ MẪU HÌNH GIÁ (PATTERN RECOGNITION)

File `module3_stock_screener_v1.py` có logic phát hiện:
1.  **VCP (Volatility Contraction):** Logic đếm số lần co hẹp (contractions) và độ sâu (depth).
    *   *Nhận xét:* Logic ổn về mặt toán học. Tuy nhiên thực tế VCP ở Việt Nam thường biến thể lỏng lẻo hơn sách Mark Minervini. Cần nới lỏng tham số `quality`.
2.  **Cup & Handle:** Logic check độ sâu 12-35% và thời gian.
    *   *Nhận xét:* Tốt. Nhưng cần thêm check volume ở phần đáy cốc (phải cạn kiệt) và phần tay cầm (phải thấp).
3.  **Flat Base:** Biên độ < 15%.
    *   *Nhận xét:* Phù hợp để bắt các cổ phiếu kênh trên (Upper Channel).

**Điểm trừ:** Code hiện tại thuần túy dựa trên hình học (geometry) của giá, chưa kết hợp chặt chẽ với hành vi Volume tại các điểm then chốt (ví dụ: phiên rũ bỏ volume phải lớn, phiên test cung volume phải nhỏ).

---

## 4. CẢI TIẾN ĐỀ XUẤT (TỪ GÓC ĐỘ QUẢN LÝ QUỸ 10 TỶ)

Để quản lý 10 tỷ hiệu quả (size không quá lớn nhưng cần thanh khoản), bạn cần nâng cấp:

### 🚀 1. Fix ngay dữ liệu Fundamental (C & A)
*   **Giải pháp:** Đừng chỉ dựa vào `vnstock` free nếu nó thiếu data tài chính sâu. Hãy cân nhắc crawl data từ CafeF hoặc Vietstock (cẩn thận policy) hoặc mua data feed rẻ (như WiChart/FiinTrade API nếu có budget).
*   **Chỉ số cần thêm:** Tăng trưởng Lợi nhuận gộp (Gross Margin Expansion) - dấu hiệu sớm của siêu cổ phiếu trước khi EPS tăng.

### 🛡️ 2. Quản trị rủi ro & Đi vốn (Position Sizing)
*   Hệ thống hiện tại chỉ đưa ra điểm mua. Với 10 tỷ, bạn không thể "all-in" một lệnh.
*   **Thêm logic Pyramiding:**
    *   Mua thăm dò 30% tại điểm Pocket Pivot (trong nền giá).
    *   Mua gia tăng 50% tại điểm Breakout.
    *   Mua nốt 20% khi test lại thành công.
*   **Thêm logic Cắt lỗ động (Trailing Stop):** Dùng MA10 hoặc MA20 làm đường trailing stop khi cổ phiếu đã vào pha chạy nước rút.

### 🧠 3. Tinh chỉnh cho "Chất Việt Nam"
*   **Bộ lọc Thanh khoản:** Với NAV 10 tỷ, tránh xa các mã Volume < 5 tỷ/phiên. Code hiện tại `MIN_VOLUME_AVG = 100000` là hơi thấp với các mã thị giá nhỏ. Nên lọc theo `Average Traded Value` (Giá trị giao dịch TB) > 10-20 tỷ VND.
*   **Ngành (Sector):** Việt Nam chạy theo sóng ngành rất rõ. Hãy tăng trọng số cho `Sector RS` (Sức mạnh ngành). Một cổ phiếu trung bình trong một ngành dẫn dắt vẫn tốt hơn cổ phiếu tốt trong ngành suy yếu.

### 🤖 4. AI Agent nâng cao
*   Hiện tại AI chỉ tóm tắt tin. Hãy train/prompt AI để nó đóng vai "Soi lệnh" (Tape Reading).
*   Cho AI phân tích các mẫu hình nến đảo chiều (Candlestick patterns) tại vùng Supply/Demand của Volume Profile để tối ưu điểm entry T+.

---

## KẾT LUẬN
Dự án này là một **MVP (Minimum Viable Product) rất tiềm năng**. Nó đã giải quyết tốt phần "Lọc thô" (Screener). Để trở thành một hệ thống "Trading" kiếm tiền thật, bạn cần lấp đầy lỗ hổng dữ liệu Cơ bản và thêm module Quản lý vốn.

**Rating:** 7.5/10 (Khả thi cao nếu fix được Data).
