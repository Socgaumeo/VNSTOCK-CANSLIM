# VNSTOCK-CANSLIM: HỆ THỐNG PHÂN TÍCH CANSLIM CHO THỊ TRƯỜNG VIỆT NAM

## 📋 TỔNG QUAN

Hệ thống phân tích cổ phiếu Việt Nam theo phương pháp **CANSLIM** kết hợp với:
- **Volume Profile** (POC, VAH, VAL)
- **Technical Analysis** (MA, RSI, MACD, ADX)
- **AI Analysis** (Gemini 3.0 Pro Preview)
- **Market Breadth & Money Flow**

---

## 🗂️ CẤU TRÚC FILE

### Files Chính (SỬ DỤNG)

| File | Mục đích |
|------|----------|
| [`config.py`](config.py) | **Config tập trung** - API keys, settings |
| [`module1_market_timing_v2.py`](module1_market_timing_v2.py) | **Module 1**: Market Timing + Volume Profile |
| [`module2_sector_rotation_v2.py`](module2_sector_rotation_v2.py) | **Module 2**: Sector Rotation |
| [`stock_screener.py`](stock_screener.py) | **Module 2.5**: Stock Screener CANSLIM & SEPA |
| [`run_market_timing.py`](run_market_timing.py) | Quick start cho Module 1 |
| [`data_collector.py`](data_collector.py) | Thu thập dữ liệu từ VCI/TCBS/SSI |
| [`volume_profile.py`](volume_profile.py) | Tính Volume Profile (POC, VA) |
| [`ai_providers.py`](ai_providers.py) | Multi AI providers |

### Files Cũ (BACKUP)

| File | Ghi chú |
|------|---------|
| `module1_market_timing.py` | Phiên bản cũ, hardcode API keys |
| `files/` | Backup files gốc |
| `module 2/` | Phiên bản phát triển |

---

## ⚙️ CÀI ĐẶT

```bash
# 1. Clone repo
git clone https://github.com/your-repo/VNSTOCK-CANSLIM.git
cd VNSTOCK-CANSLIM

# 2. Tạo virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# hoặc: .venv\Scripts\activate  # Windows

# 3. Cài đặt dependencies
pip install -r requirements.txt
pip install vnstock  # vnstock premium

# 4. Điền API keys vào config.py
# Mở config.py và điền API keys
```

---

## 🚀 CHẠY

### Module 1: Market Timing
```bash
# Quick start
python run_market_timing.py

# Hoặc trực tiếp
python module1_market_timing_v2.py
```

### Module 2: Sector Rotation
```bash
python module2_sector_rotation_v2.py
```

---

## 🔑 API KEYS

Điền vào `config.py`:

```python
class APIKeys:
    VNSTOCK = "vnstock_xxxxx"  # từ vnstock.site
    GEMINI = "AIzaSyxxxxx"     # từ makersuite.google.com
    DEEPSEEK = ""              # từ platform.deepseek.com (optional)
```

---

## 📊 7 NGÀNH HỢP LỆ

Chỉ có 7 sector indices hoạt động với VCI:

| Code | Tên |
|------|-----|
| VNFIN | Tài chính |
| VNREAL | Bất động sản |
| VNMAT | Nguyên vật liệu |
| VNIT | Công nghệ |
| VNHEAL | Y tế |
| VNCOND | Tiêu dùng không thiết yếu |
| VNCONS | Tiêu dùng thiết yếu |

⚠️ **Không hoạt động**: VNENERGY, VNIND, VNUTI

---

## 📈 OUTPUT

Báo cáo lưu tại `./output/`:
- `market_timing_YYYYMMDD_HHMM.md`
- `sector_rotation_YYYYMMDD_HHMM.md`

---

## 💾 DATABASE ASSESSMENT

### Hiện tại: KHÔNG CẦN DATABASE

Lý do:
1. **Dữ liệu realtime** - vnstock API fetch mới mỗi lần chạy
2. **Output là markdown** - dễ đọc, không cần query
3. **Không có user session** - chạy local, đơn lẻ
4. **Volume nhỏ** - vài file output/ngày

### Khi nào CẦN DATABASE?

| Use Case | Database Đề xuất |
|----------|------------------|
| **Web App đơn giản** | SQLite (nhúng, không cài) |
| **Multi-user App** | PostgreSQL |
| **Realtime Dashboard** | Redis + PostgreSQL |
| **Portfolio Tracking** | PostgreSQL + TimescaleDB |

### Roadmap Khuyến nghị:

```
Hiện tại (Local CLI)
    ↓
Phase 1: SQLite
    - Lưu báo cáo lịch sử
    - Cache dữ liệu (giảm API calls)
    ↓
Phase 2: PostgreSQL (khi deploy web)
    - Multi-user support
    - Portfolio management
    - Historical analytics
```

### Schema gợi ý cho Phase 1:

```sql
-- market_reports
CREATE TABLE market_reports (
    id INTEGER PRIMARY KEY,
    timestamp DATETIME,
    market_color TEXT,
    market_score INTEGER,
    vnindex_price REAL,
    vnindex_change REAL,
    ai_analysis TEXT
);

-- sector_data
CREATE TABLE sector_data (
    id INTEGER PRIMARY KEY,
    report_id INTEGER,
    sector_code TEXT,
    change_1d REAL,
    change_1m REAL,
    rs_vs_vnindex REAL,
    phase TEXT
);
```

---

## 📝 VERSION HISTORY

| Version | Ngày | Thay đổi |
|---------|------|----------|
| 2.0 | 27/11/2024 | - Unified config.py<br>- Volume Profile integration<br>- Gemini 3.0 Pro Preview<br>- 7 sector indices fix |
| 1.0 | 26/11/2024 | Initial release |

---

## 🤝 DEPENDENCIES

```
vnstock>=3.3.0
vnstock_data>=2.1.7
vnstock_ta>=0.1.2
pandas>=2.0
numpy>=1.24
google-generativeai>=0.8
```

---

## 📄 LICENSE

MIT License
