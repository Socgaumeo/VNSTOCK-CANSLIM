# 📐 KIẾN TRÚC HỆ THỐNG V3 - ĐÃ ĐIỀU CHỈNH

> **Điều chỉnh theo feedback:** Module 5 (Smart Money) chuyển về Layer 2 (Analysis)

---

## 🏗️ KIẾN TRÚC 3 LAYERS

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CANSLIM SCANNER v3.0                                 │
│                    "Data Flow & Context Analysis"                           │
└─────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
LAYER 1: DATA CONTEXT (Nền tảng dữ liệu + Vector hóa)
═══════════════════════════════════════════════════════════════════════════════
┌─────────────────────────────────────────────────────────────────────────────┐
│  MODULE 0: DATA CONTEXT LAYER                                               │
│  ├─ config.py          : API keys, settings (đã có)                         │
│  ├─ data_collector.py  : Multi-source + fallback (đã có)                    │
│  ├─ volume_profile.py  : POC, VAH, VAL (đã có)                              │
│  └─ data_context.py    : 🆕 Rolling Window, Vector hóa, Trend Slope         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
═══════════════════════════════════════════════════════════════════════════════
LAYER 2: ANALYSIS (Phân tích - Tất cả các góc nhìn)
═══════════════════════════════════════════════════════════════════════════════
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  MODULE 1   │ │  MODULE 2   │ │  MODULE 3   │ │  MODULE 4   │ │  MODULE 5   │
│   Market    │ │   Sector    │ │  CANSLIM    │ │  SEPA/VCP   │ │   Smart     │
│   Timing    │ │  Rotation   │ │ Fundamental │ │  Patterns   │ │   Money     │
├─────────────┤ ├─────────────┤ ├─────────────┤ ├─────────────┤ ├─────────────┤
│ • Traffic   │ │ • RS Rating │ │ • Chữ C     │ │ • VCP       │ │ • Foreign   │
│   Light     │ │ • Phase     │ │ • Chữ A     │ │ • Dry-up    │ │   Flow      │
│ • Dist Days │ │ • Rotation  │ │ • Score     │ │ • Pocket    │ │ • Prop      │
│ • FTD       │ │   Clock     │ │   100đ      │ │   Pivot     │ │ • CMF       │
│ • Regime    │ │ • Leaders   │ │             │ │ • Base      │ │ • AVWAP     │
└─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
       │               │               │               │               │
       └───────────────┴───────────────┴───────────────┴───────────────┘
                                    │
                                    ▼
═══════════════════════════════════════════════════════════════════════════════
LAYER 3: SIGNAL (Tín hiệu giao dịch)
═══════════════════════════════════════════════════════════════════════════════
┌─────────────────────────────────────┐ ┌─────────────────────────────────────┐
│  MODULE 6: ENTRY/EXIT TRIGGERS      │ │  MODULE 7: RISK MANAGEMENT          │
├─────────────────────────────────────┤ ├─────────────────────────────────────┤
│ • Fractal S/R                       │ │ • Initial Stop Loss                 │
│ • Breakout Validation               │ │ • Trailing Stop                     │
│ • Retest Setup                      │ │ • Position Sizing                   │
│ • False Break Filter                │ │ • Pyramiding Rules                  │
└─────────────────────────────────────┘ └─────────────────────────────────────┘
                                    │
                                    ▼
═══════════════════════════════════════════════════════════════════════════════
OUTPUT: Markdown + JSON (cho AI) + CSV
═══════════════════════════════════════════════════════════════════════════════
```

---

## 📊 LÝ DO SMART MONEY Ở LAYER 2

### Phân biệt DATA vs SIGNAL

| Loại | Ví dụ | Layer |
|------|-------|-------|
| **Data/Metric** | Khối ngoại mua ròng 100 tỷ hôm nay | Layer 2 |
| **Analysis** | Cumulative Foreign 20 ngày = +500 tỷ | Layer 2 |
| **Signal** | "Mua khi Foreign gom 5 phiên liên tiếp" | Layer 3 |

### Smart Money là PHÂN TÍCH, không phải TÍN HIỆU

```python
# Layer 2: Analysis (Module 5)
foreign_net_today = -41.2  # tỷ VNĐ (DATA)
cumulative_20d = +350      # tỷ VNĐ (ANALYSIS)
cmf = 0.15                 # (ANALYSIS)
price_vs_avwap = "ABOVE"   # (ANALYSIS)

# Layer 3: Signal (Module 6)
if cumulative_20d > 0 and price_vs_avwap == "ABOVE" and cmf > 0.1:
    signal = "ACCUMULATION_CONFIRMED"  # SIGNAL
```

---

## 📁 CẤU TRÚC FILES

```
canslim_scanner/
│
├── config.py                    # ✅ Đã có - Unified config
├── data_collector.py            # ✅ Đã có - Multi-source
├── volume_profile.py            # ✅ Đã có - VP calculator
│
├── data_context.py              # 🆕 MODULE 0 - Vector hóa
│   ├── calc_trend_slope()
│   ├── calc_percentile_rank()
│   ├── calc_rsi_regime()
│   ├── calc_macd_impulse()
│   ├── count_distribution_days()
│   └── detect_follow_through_day()
│
├── module1_market_timing_v3.py  # 🔄 Nâng cấp
├── module2_sector_rotation_v3.py # 🔄 Nâng cấp
├── module3_canslim_fundamental.py # 🆕
├── module4_sepa_vcp.py          # 🆕
├── module5_smart_money.py       # 🆕
├── module6_entry_trigger.py     # 🆕
├── module7_risk_management.py   # 🆕
│
├── main.py                      # ✅ Đã có - Runner
└── outputs/
    ├── report_YYYYMMDD.md       # Markdown cho người đọc
    ├── report_YYYYMMDD.json     # JSON cho AI
    └── watchlist_YYYYMMDD.csv   # CSV cho Excel
```

---

## 🚀 BẮT ĐẦU: MODULE 0 - DATA CONTEXT LAYER

### Mục tiêu:
1. Vector hóa dữ liệu (Rolling Window)
2. Tính các chỉ báo có "bộ nhớ" (context)
3. Output JSON cho AI

### Các hàm cần implement:

```python
class DataContext:
    """
    Chuyển từ phân tích điểm (scalar) sang phân tích dòng chảy (time-series)
    """
    
    # ═══════════════════════════════════════════════════════════════
    # 1. TREND CONTEXT
    # ═══════════════════════════════════════════════════════════════
    
    def calc_trend_slope(self, ma_series: pd.Series, window: int = 20) -> float:
        """
        Tính độ dốc của MA bằng Linear Regression
        
        Returns:
            slope > 0.5: Uptrend mạnh
            slope ≈ 0: Sideway
            slope < -0.5: Downtrend mạnh
        """
        
    def calc_ma_slope_status(self, slope: float) -> str:
        """
        Phân loại độ dốc thành trạng thái
        
        Returns: "STRONG_UP" | "UP" | "FLAT" | "DOWN" | "STRONG_DOWN"
        """
    
    # ═══════════════════════════════════════════════════════════════
    # 2. PRICE CONTEXT
    # ═══════════════════════════════════════════════════════════════
    
    def calc_percentile_rank(self, price: float, prices: pd.Series) -> float:
        """
        Vị thế của giá hiện tại trong phân phối N ngày
        
        Returns: 0-100 (%)
            > 90: Vùng rất đắt
            70-90: Vùng đắt
            30-70: Vùng trung tính
            < 30: Vùng rẻ
        """
    
    # ═══════════════════════════════════════════════════════════════
    # 3. RSI CONTEXT
    # ═══════════════════════════════════════════════════════════════
    
    def calc_rsi_regime(self, rsi_series: pd.Series, window: int = 50) -> dict:
        """
        RSI Regime dựa trên Rolling Min/Max
        
        Returns: {
            'rsi_min': float,
            'rsi_max': float,
            'regime': "BULLISH" | "BEARISH" | "NEUTRAL",
            'note': str
        }
        
        Logic:
            RSI_Min > 40 → BULLISH (đáy RSI không thủng 40)
            RSI_Max < 60 → BEARISH (đỉnh RSI không vượt 60)
            Còn lại → NEUTRAL
        """
    
    # ═══════════════════════════════════════════════════════════════
    # 4. MACD CONTEXT
    # ═══════════════════════════════════════════════════════════════
    
    def calc_macd_impulse(self, macd_hist: pd.Series) -> dict:
        """
        MACD Impulse System
        
        Returns: {
            'direction': "INCREASING" | "DECREASING" | "FLAT",
            'bars_in_direction': int,
            'signal': str
        }
        
        Logic:
            Histogram tăng → "Không được Short"
            Histogram giảm → "Không được Long mới"
        """
    
    # ═══════════════════════════════════════════════════════════════
    # 5. DISTRIBUTION DAYS (Market Timing)
    # ═══════════════════════════════════════════════════════════════
    
    def count_distribution_days(self, df: pd.DataFrame, window: int = 25) -> dict:
        """
        Đếm số ngày phân phối trong N phiên gần nhất
        
        Distribution Day = Giá giảm > 0.2% VÀ Volume > hôm trước
        
        Returns: {
            'count': int,
            'dates': List[str],
            'status': "SAFE" | "WARNING" | "DANGER",
            'note': str
        }
        
        Logic:
            < 3: SAFE (Thị trường khỏe)
            4-5: WARNING (Áp lực phân phối)
            > 6: DANGER (Phân phối nặng)
        """
    
    def is_distribution_day(self, row: pd.Series, prev_row: pd.Series) -> bool:
        """
        Kiểm tra 1 ngày có phải Distribution Day không
        """
    
    # ═══════════════════════════════════════════════════════════════
    # 6. FOLLOW-THROUGH DAY (Market Timing)
    # ═══════════════════════════════════════════════════════════════
    
    def find_recent_low(self, df: pd.DataFrame, lookback: int = 20) -> dict:
        """
        Tìm đáy gần nhất
        
        Returns: {
            'date': str,
            'price': float,
            'days_ago': int
        }
        """
    
    def detect_follow_through_day(self, df: pd.DataFrame) -> dict:
        """
        Phát hiện Follow-Through Day
        
        FTD = Ngày 4-10 từ đáy + Tăng > 1.25% + Volume > hôm trước
        
        Returns: {
            'has_ftd': bool,
            'ftd_date': str or None,
            'ftd_gain': float,
            'days_from_low': int,
            'note': str
        }
        """
    
    # ═══════════════════════════════════════════════════════════════
    # 7. MARKET REGIME
    # ═══════════════════════════════════════════════════════════════
    
    def classify_market_regime(self, 
                               price: float,
                               ma50: float,
                               ma200: float,
                               dist_days: int,
                               has_ftd: bool) -> dict:
        """
        Phân loại chế độ thị trường
        
        Returns: {
            'regime': "ACCUMULATION" | "MARKUP" | "DISTRIBUTION" | "MARKDOWN",
            'confidence': float,
            'signals': List[str]
        }
        """
    
    # ═══════════════════════════════════════════════════════════════
    # 8. AGGREGATE CONTEXT
    # ═══════════════════════════════════════════════════════════════
    
    def get_full_context(self, df: pd.DataFrame) -> dict:
        """
        Tổng hợp tất cả context thành 1 dict
        
        Returns: {
            'trend': {...},
            'price_position': {...},
            'rsi_regime': {...},
            'macd_impulse': {...},
            'distribution': {...},
            'ftd': {...},
            'regime': {...}
        }
        """
    
    def to_json(self, context: dict) -> str:
        """
        Export context thành JSON cho AI
        """
```

---

## 📤 OUTPUT FORMAT

### 1. JSON cho AI

```json
{
  "timestamp": "2025-11-27T21:18:00",
  "vnindex": {
    "price": 1684,
    "change_1d": 0.24,
    "change_1m": -0.09
  },
  "context": {
    "trend": {
      "ma50_slope": 0.82,
      "ma50_slope_status": "STRONG_UP",
      "ma_alignment": "BULLISH"
    },
    "price_position": {
      "percentile_50d": 92,
      "status": "EXPENSIVE"
    },
    "rsi_regime": {
      "rsi_current": 76.2,
      "rsi_min_50d": 52,
      "rsi_max_50d": 78,
      "regime": "BULLISH"
    },
    "macd_impulse": {
      "direction": "DECREASING",
      "bars": 2,
      "signal": "CAUTION_LONG"
    },
    "distribution": {
      "count": 2,
      "status": "SAFE"
    },
    "ftd": {
      "has_ftd": true,
      "date": "2025-11-18"
    },
    "regime": "MARKUP"
  },
  "traffic_light": "GREEN",
  "market_score": 72
}
```

### 2. Markdown cho người đọc

```markdown
## 📊 DATA CONTEXT

### Trend Analysis
| Metric | Value | Status |
|--------|-------|--------|
| MA50 Slope | +0.82 | 🟢 STRONG_UP |
| MA Alignment | MA20 > MA50 > MA200 | ✅ BULLISH |

### Price Position
| Metric | Value | Interpretation |
|--------|-------|----------------|
| Percentile 50D | 92% | ⚠️ Vùng đắt |

### Distribution Days (25 phiên)
| Count | Status | Note |
|-------|--------|------|
| 2 | 🟢 SAFE | Thị trường khỏe |

### Follow-Through Day
| Has FTD | Date | Gain |
|---------|------|------|
| ✅ Yes | 18/11 | +1.8% |

### Market Regime: 📈 MARKUP
```

---

## ❓ XÁC NHẬN TRƯỚC KHI CODE

1. **Cấu trúc này OK chưa?**
2. **JSON format như trên có phù hợp để gửi cho AI không?**
3. **Có cần thêm metric nào trong Data Context không?**

Nếu OK, tôi sẽ bắt đầu code `data_context.py` ngay!
