# 🚀 CANSLIM SCANNER - VIETNAM STOCK MARKET

> **Version:** 2.0  
> **Update:** 11/2025  
> **Requires:** Python 3.8+, vnstock >= 3.2.0

---

## 📋 TỔNG QUAN

Hệ thống phân tích cổ phiếu Việt Nam theo phương pháp **CANSLIM** với tích hợp:
- ✅ **Multi-source data** (VCI → TCBS → SSI fallback)
- ✅ **Volume Profile** (POC, VAH, VAL)
- ✅ **AI Analysis** (DeepSeek, Gemini, Claude, OpenAI, Groq)
- ✅ **Unified Config** (Chỉ điền API 1 lần)

---

## 📁 CẤU TRÚC FILES

```
📦 CANSLIM Scanner
├── 📄 config.py                    # ⭐ CẤU HÌNH CHUNG (Điền API tại đây)
├── 📄 main.py                      # File chạy chính
│
├── 📂 Core Modules
│   ├── 📄 data_collector.py        # Thu thập dữ liệu (multi-source)
│   ├── 📄 volume_profile.py        # Phân tích Volume Profile
│   └── 📄 ai_providers.py          # Tích hợp AI
│
├── 📂 Analysis Modules
│   ├── 📄 module1_market_timing_v2.py   # Module 1: Market Timing
│   └── 📄 module2_sector_rotation_v2.py # Module 2: Sector Rotation
│
└── 📂 Output
    └── 📁 output/                  # Báo cáo được lưu tại đây
```

---

## 🚀 HƯỚNG DẪN CÀI ĐẶT

### Bước 1: Cài đặt dependencies

```bash
pip install -U vnstock openai google-generativeai anthropic groq
pip install pandas numpy openpyxl
```

### Bước 2: Cấu hình API Keys

Mở file **`config.py`** và điền API keys:

```python
class APIKeys:
    # VNSTOCK PREMIUM (Bắt buộc)
    VNSTOCK = "vnstock_xxxxxx"
    
    # AI PROVIDERS (Điền ít nhất 1 cái)
    DEEPSEEK = ""    # Rẻ nhất: $0.14/1M tokens
    GEMINI = ""      # Free tier: 60 req/phút
    GROQ = ""        # Nhanh nhất
    CLAUDE = ""      # Chất lượng cao nhất
    OPENAI = ""      # Phổ biến
```

### Bước 3: Chạy

```bash
# Chạy full workflow
python main.py

# Hoặc chạy từng module
python main.py --module 1    # Market Timing
python main.py --module 2    # Sector Rotation

# Kiểm tra config
python main.py --status
```

---

## 📊 WORKFLOW

```
┌─────────────────────────────────────────────────────────────────┐
│                     python main.py                               │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  MODULE 1: MARKET TIMING                                         │
│  ─────────────────────────                                       │
│  • Phân tích VNIndex + Volume Profile                           │
│  • Tính Market Score (0-100)                                     │
│  • Xác định Market Color:                                        │
│    🟢 XANH (>=40): Tấn công                                     │
│    🟡 VÀNG (0-39): Phòng thủ                                    │
│    🔴 ĐỎ (<0): Rút lui                                          │
│  • AI tạo báo cáo với What-If scenarios                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  MODULE 2: SECTOR ROTATION (nếu không phải 🔴)                   │
│  ─────────────────────────────────────────                       │
│  • Phân tích 9 chỉ số ngành (VNFIN, VNREAL, ...)                │
│  • Tính RS vs VNIndex                                           │
│  • Phân loại Phase:                                              │
│    🚀 Leading | 📈 Improving | 📉 Weakening | ⛔ Lagging        │
│  • AI khuyến nghị allocation                                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  MODULE 3: STOCK SELECTION (Coming Soon)                        │
│  MODULE 4: ENTRY POINT (Coming Soon)                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📈 VOLUME PROFILE

### Khái niệm chính:

| Thuật ngữ | Ý nghĩa |
|-----------|---------|
| **POC** (Point of Control) | Mức giá có volume lớn nhất = Support/Resistance mạnh |
| **VAH** (Value Area High) | Cận trên Value Area |
| **VAL** (Value Area Low) | Cận dưới Value Area |
| **Value Area** | Vùng giá chứa 70% volume = "Fair Value" |
| **HVN** (High Volume Node) | Vùng tích lũy/phân phối |
| **LVN** (Low Volume Node) | Vùng có thể breakout nhanh |

### Cách đọc:

```
Giá TRÊN Value Area → Bullish bias, VAH là support
Giá TRONG Value Area → Consolidation, chờ breakout
Giá DƯỚI Value Area → Bearish bias, VAL là resistance
Giá gần POC → Vùng cân bằng, chờ direction
```

---

## 🔄 MULTI-SOURCE DATA

Hệ thống tự động fallback khi nguồn dữ liệu bị lỗi:

```
VCI (Primary) → TCBS (Backup) → SSI (Fallback)
```

Cấu hình trong `config.py`:

```python
@dataclass
class DataSourceConfig:
    PRIORITY: List[str] = ["VCI", "TCBS", "SSI"]
    DEFAULT: str = "VCI"
    AUTO_FALLBACK: bool = True
```

---

## 🤖 AI PROVIDERS

| Provider | Giá | Tốc độ | Chất lượng | Link |
|----------|-----|--------|------------|------|
| **DeepSeek** ⭐ | $0.14/1M | Nhanh | Tốt | [platform.deepseek.com](https://platform.deepseek.com/) |
| **Gemini** | Free | Nhanh | Tốt | [makersuite.google.com](https://makersuite.google.com/app/apikey) |
| **Groq** | Free | Siêu nhanh | Khá | [console.groq.com](https://console.groq.com/) |
| **Claude** | $3/1M | Trung bình | Xuất sắc | [console.anthropic.com](https://console.anthropic.com/) |
| **OpenAI** | $2.5/1M | Trung bình | Tốt | [platform.openai.com](https://platform.openai.com/) |

Hệ thống tự động chọn provider có API key theo thứ tự ưu tiên.

---

## 📤 OUTPUT MẪU

### Module 1: Market Timing

```
╔══════════════════════════════════════════════════════════════╗
║     MODULE 1: MARKET TIMING + VOLUME PROFILE                 ║
╚══════════════════════════════════════════════════════════════╝

📊 ĐIỂM THỊ TRƯỜNG: 40/100
🎯 🟢 XANH - TẤN CÔNG

✅ Bullish: Giá > MA20 & MA50
⚠️ RSI quá mua: 76
✅ MACD Histogram dương
✅ Trend mạnh (ADX=47)
📈 Giá TRÊN Value Area (VAH=1,680)

📊 VOLUME PROFILE:
   POC: 1,665  |  VA: 1,645 - 1,680
```

### Module 2: Sector Rotation

```
RANK  NGÀNH                1D        1M        RS       PHASE
──────────────────────────────────────────────────────────────
1     Tài chính         +0.75%    +5.23%    +2.10%   🚀 Dẫn dắt
2     Y tế              +0.61%    +3.45%    +0.32%   📈 Tăng tốc
3     Bất động sản      +0.35%    +4.12%    +1.00%   📈 Tăng tốc
4     Công nghệ         -0.65%    +1.20%    -1.93%   📉 Suy yếu
```

---

## ⚠️ LƯU Ý QUAN TRỌNG

1. **Rate Limiting**: Nếu bị lỗi "Too many requests", tăng `API_DELAY` trong config
2. **Dữ liệu breadth/money flow**: Đang dùng estimate, cần cấu hình thêm với vnstock premium
3. **Chạy trong giờ giao dịch**: Để có dữ liệu realtime mới nhất

---

## 📞 SUPPORT

- Lỗi vnstock: Kiểm tra API key và version (`pip show vnstock`)
- Lỗi AI: Kiểm tra API key và quota
- Lỗi khác: Chạy `python main.py --status` để debug

---

## 🗺️ ROADMAP

- [x] Module 1: Market Timing + Volume Profile
- [x] Module 2: Sector Rotation
- [ ] Module 3: Stock Selection (CANSLIM Scoring)
- [ ] Module 4: Entry Point Detection
- [ ] Module 5: Portfolio Management
- [ ] Telegram/Discord Alerts
- [ ] Web Dashboard

---

**Happy Trading! 📈**
