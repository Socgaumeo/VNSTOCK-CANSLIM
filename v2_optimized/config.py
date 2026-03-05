#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CANSLIM SCANNER - UNIFIED CONFIG                          ║
║              File cấu hình chung cho tất cả các Modules                      ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Chỉ cần điền API keys 1 LẦN DUY NHẤT tại đây                                ║
║  Tất cả modules sẽ tự động đọc từ file này                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


# ══════════════════════════════════════════════════════════════════════════════
# ⚠️ ĐIỀN API KEYS CỦA BẠN VÀO ĐÂY (CHỈ 1 LẦN)
# ══════════════════════════════════════════════════════════════════════════════

class APIKeys:
    """Tất cả API keys tập trung tại đây"""
    
    # ─────────────────────────────────────────────────────────────
    # VNSTOCK PREMIUM
    # ─────────────────────────────────────────────────────────────
    # Đăng ký: https://vnstocks.com
    VNSTOCK = "vnstock_0acf8671851dba60b26830c7816c756f"
    
    # ─────────────────────────────────────────────────────────────
    # AI PROVIDERS (Điền ít nhất 1 cái)
    # ─────────────────────────────────────────────────────────────
    
    # DeepSeek - Rẻ nhất ($0.14/1M tokens)
    # Đăng ký: https://platform.deepseek.com/
    DEEPSEEK = "sk-2ccd0aea542e4da8b7af147b435be35d"
    
    # Google Gemini - Free tier rộng rãi (60 req/phút)
    # Đăng ký: https://makersuite.google.com/app/apikey
    GEMINI = "AIzaSyBf8r3SWc9NkuGcLbS4M_nKVIYo5lKr1VI"
    
    # Groq - Nhanh nhất (Free tier generous)
    # Đăng ký: https://console.groq.com/
    GROQ = ""
    
    # Anthropic Claude - Chất lượng cao nhất
    # Đăng ký: https://console.anthropic.com/
    CLAUDE = "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"
    
    # OpenAI - Phổ biến
    # Đăng ký: https://platform.openai.com/
    OPENAI = ""


# ══════════════════════════════════════════════════════════════════════════════
# DATA SOURCE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

class DataSource(Enum):
    """Nguồn dữ liệu được hỗ trợ"""
    KBS = "KBS"           # Mặc định từ vnstock 3.4.2 (thay VCI)
    VCI = "VCI"           # Legacy - API bị block từ 03/2026
    TCBS = "TCBS"         # Deprecated từ vnstock 3.4.0
    CAFEF = "CAFEF"       # Fallback cho dữ liệu cơ bản
    SSI = "SSI"           # Thêm option


@dataclass
class DataSourceConfig:
    """Cấu hình nguồn dữ liệu với fallback"""

    # Thứ tự ưu tiên nguồn dữ liệu
    PRIORITY: List[str] = field(default_factory=lambda: ["KBS", "VCI", "TCBS"])

    # Nguồn mặc định
    DEFAULT: str = "KBS"
    
    # Tự động fallback khi lỗi
    AUTO_FALLBACK: bool = True
    
    # Timeout cho mỗi request (giây)
    TIMEOUT: int = 30
    
    # Số lần retry trước khi chuyển nguồn
    MAX_RETRIES: int = 2


# ══════════════════════════════════════════════════════════════════════════════
# AI PROVIDER CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AIProviderConfig:
    """Cấu hình AI Provider với auto-detection"""
    
    # Thứ tự ưu tiên (Rẻ → Free → Nhanh → Chất lượng)
    PRIORITY: List[str] = field(default_factory=lambda: [
        "claude",    # Chất lượng cao - dùng Opus 4.5 - RUNNING CLAUDE
        "gemini",    # Free tier
        "deepseek",  # Rẻ nhất
        "groq",      # Nhanh nhất
        "openai"     # Phổ biến
    ])
    
    # Default models cho từng provider
    DEFAULT_MODELS: Dict[str, str] = field(default_factory=lambda: {
        "deepseek": "deepseek-chat",
        "gemini": "gemini-3-pro-preview",  # Gemini 3.0 Pro Preview - mới nhất
        "groq": "llama-3.1-70b-versatile",
        "claude": "claude-opus-4-5-20251101",  # Claude Opus 4.5 - mới nhất (Nov 2025)
        "openai": "gpt-4o-mini"
    })
    
    # Generation settings
    MAX_TOKENS: int = 4096
    TEMPERATURE: float = 0.7
    
    @staticmethod
    def get_available_provider() -> tuple:
        """Tự động tìm provider có API key"""
        providers_keys = {
            "deepseek": APIKeys.DEEPSEEK,
            "gemini": APIKeys.GEMINI,
            "groq": APIKeys.GROQ,
            "claude": APIKeys.CLAUDE,
            "openai": APIKeys.OPENAI,
        }
        
        priority = ["claude", "gemini", "deepseek", "groq", "openai"]  # Claude first
        
        for provider in priority:
            key = providers_keys.get(provider, "")
            if key:
                return provider, key
        
        return "", ""


# ══════════════════════════════════════════════════════════════════════════════
# RATE LIMITING CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RateLimitConfig:
    """Cấu hình rate limiting"""
    
    # Delay giữa các request (giây)
    API_DELAY: float = 1.5  # Tăng từ 0.3 để tránh TCBS rate limit
    
    # Số request trước khi nghỉ dài
    BATCH_SIZE: int = 20
    
    # Thời gian nghỉ giữa các batch (giây)
    BATCH_DELAY: float = 2.0
    
    # Delay khi gặp rate limit error
    RATE_LIMIT_DELAY: float = 15.0


# ══════════════════════════════════════════════════════════════════════════════
# CACHE CONFIGURATION (Smart Cache)
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class CacheConfig:
    """Cấu hình Smart Cache với TTL khác nhau theo loại dữ liệu"""

    # Thư mục cache
    CACHE_DIR: str = "./cache"

    # TTL cho từng loại dữ liệu (ngày)
    TTL_STOCK_LIST: int = 7              # Danh sách cổ phiếu
    TTL_QUARTERLY_FINANCIALS: int = 30   # EPS, Revenue, Profit (theo BCTC quý)
    TTL_CASH_FLOW: int = 30              # Cash flow statement
    TTL_FINANCIAL_RATIOS: int = 30       # ROE, ROA, PE, PB
    TTL_SECTOR_MAPPING: int = 30         # ICB → Sector mapping
    TTL_VOLUME_AVERAGE: int = 1          # Volume TB (cập nhật hàng ngày)

    # Auto-refresh theo mùa BCTC
    ENABLE_EARNINGS_REFRESH: bool = True

    # Các mốc công bố BCTC (tháng, ngày)
    EARNINGS_DATES: List[tuple] = field(default_factory=lambda: [
        (1, 25),   # Q4 năm trước
        (4, 25),   # Q1
        (7, 25),   # Q2
        (10, 25),  # Q3
    ])


# ══════════════════════════════════════════════════════════════════════════════
# HISTORICAL DATA CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class HistoricalDataConfig:
    """Cấu hình theo dõi dữ liệu lịch sử"""

    # Thư mục lưu historical cache
    HISTORICAL_CACHE_DIR: str = "./cache/historical"

    # Số ngày lưu trữ cho từng loại dữ liệu
    PRICE_HISTORY_DAYS: int = 30           # Lịch sử giá (OHLCV + indicators)
    FOREIGN_HISTORY_DAYS: int = 30         # Lịch sử giao dịch khối ngoại
    RECOMMENDATION_HISTORY_DAYS: int = 90  # Lịch sử khuyến nghị

    # Rolling window cho tính toán
    FOREIGN_ROLLING_WINDOW: int = 20       # 20-day rolling average khối ngoại

    # Ngưỡng phát hiện pattern
    ACCUMULATION_MIN_BUY_DAYS: int = 12    # Tối thiểu 12/20 ngày mua ròng
    DISTRIBUTION_MIN_SELL_DAYS: int = 12   # Tối thiểu 12/20 ngày bán ròng

    # Auto cleanup
    AUTO_CLEANUP_ENABLED: bool = True
    CLEANUP_OLDER_THAN_DAYS: int = 90


# ══════════════════════════════════════════════════════════════════════════════
# STOCK UNIVERSE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class StockUniverseConfig:
    """Cấu hình Stock Universe - Phạm vi scan"""

    # Filter thanh khoản
    MIN_VOLUME: int = 100_000              # Volume TB tối thiểu (cp/ngày)
    MIN_MARKET_CAP: float = 0              # Vốn hóa tối thiểu (VND). 0 = không filter

    # Sàn giao dịch (HSX = HoSE, HNX)
    EXCHANGES: List[str] = field(default_factory=lambda: ['HSX', 'HNX'])

    # Loại trừ
    EXCLUDE_TYPES: List[str] = field(default_factory=lambda: ['FUND', 'ETF', 'CW', 'BOND'])

    # Dùng dynamic stock list từ API (True) hay hardcode (False)
    USE_DYNAMIC_LIST: bool = True

    # Scan tất cả 7 ngành hay chỉ top sectors theo RS
    SCAN_ALL_SECTORS: bool = True


# ══════════════════════════════════════════════════════════════════════════════
# VOLUME PROFILE CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class VolumeProfileConfig:
    """Cấu hình Volume Profile"""
    
    # Số bins (mức giá) để phân tích
    NUM_BINS: int = 50
    
    # Value Area percentage (thông thường 70%)
    VALUE_AREA_PCT: float = 0.70
    
    # Lookback period (ngày)
    LOOKBACK_DAYS: int = 20
    
    # High Volume Node threshold (% of total volume)
    HVN_THRESHOLD: float = 0.05  # 5%
    
    # Low Volume Node threshold
    LVN_THRESHOLD: float = 0.01  # 1%


# ══════════════════════════════════════════════════════════════════════════════
# ANALYSIS CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AnalysisConfig:
    """Cấu hình phân tích"""
    
    # Lookback periods
    LOOKBACK_DAYS: int = 120
    
    # MA periods
    MA_SHORT: int = 20
    MA_MEDIUM: int = 50
    MA_LONG: int = 200
    
    # RSI
    RSI_PERIOD: int = 14
    RSI_OVERBOUGHT: int = 70
    RSI_OVERSOLD: int = 30
    
    # MACD
    MACD_FAST: int = 12
    MACD_SLOW: int = 26
    MACD_SIGNAL: int = 9
    
    # ADX
    ADX_PERIOD: int = 14
    ADX_STRONG_TREND: int = 25
    
    # Volume
    VOLUME_MA_PERIOD: int = 20
    VOLUME_SURGE_THRESHOLD: float = 1.5  # 150% of MA


# ══════════════════════════════════════════════════════════════════════════════
# OUTPUT CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class OutputConfig:
    """Cấu hình output"""
    
    # Thư mục output
    OUTPUT_DIR: str = "./output"
    
    # Lưu báo cáo
    SAVE_REPORTS: bool = True
    
    # Format báo cáo
    REPORT_FORMAT: str = "markdown"  # markdown | html | json
    
    # Export Excel
    EXPORT_EXCEL: bool = True


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class EmailConfig:
    """Cấu hình gửi Email"""
    
    # Bật/Tắt tính năng gửi email
    ENABLED: bool = True
    
    # SMTP Settings (Mặc định cho Gmail)
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    
    # Credentials
    # Lưu ý: Với Gmail, cần dùng "App Password" (Mật khẩu ứng dụng)
    # Hướng dẫn: https://support.google.com/accounts/answer/185833
    SENDER_EMAIL: str = "khanhnn.112@gmail.com"
    SENDER_PASSWORD: str = "gdzy kbyw rceo qzwh"
    
    # Người nhận (có thể là list hoặc string phân cách bởi dấu phẩy)
    RECEIVER_EMAIL: str = "khanhnn.112@gmail.com"
    
    # Tiêu đề email
    SUBJECT_PREFIX: str = "[CANSLIM REPORT]"


# ══════════════════════════════════════════════════════════════════════════════
# TELEGRAM BOT CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TelegramConfig:
    """Cấu hình Telegram Bot"""

    # Bật/Tắt tính năng Telegram
    ENABLED: bool = True

    # Bot Token (lấy từ @BotFather)
    BOT_TOKEN: str = "7058792437:AAHcArFXfdP-UOlw3Mnk_E_syhX_iPORJ5o"

    # Admin User ID (để nhận thông báo lỗi)
    ADMIN_USER_ID: int = 348988385

    # Gửi alert hàng ngày lúc 16h
    DAILY_ALERT_ENABLED: bool = True
    DAILY_ALERT_HOUR: int = 16
    DAILY_ALERT_MINUTE: int = 0


# ══════════════════════════════════════════════════════════════════════════════
# UNIFIED CONFIG CLASS
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class UnifiedConfig:
    """
    Config tổng hợp cho tất cả modules
    
    Usage:
        from config import get_config
        config = get_config()
        
        # Truy cập API keys
        vnstock_key = config.api_keys.VNSTOCK
        
        # Truy cập AI provider
        ai_provider, ai_key = config.ai.get_available_provider()
        
        # Truy cập data source
        data_source = config.data_source.DEFAULT
    """
    
    # API Keys
    api_keys: APIKeys = field(default_factory=APIKeys)
    
    # Sub-configs
    data_source: DataSourceConfig = field(default_factory=DataSourceConfig)
    ai: AIProviderConfig = field(default_factory=AIProviderConfig)
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    historical: HistoricalDataConfig = field(default_factory=HistoricalDataConfig)
    stock_universe: StockUniverseConfig = field(default_factory=StockUniverseConfig)
    volume_profile: VolumeProfileConfig = field(default_factory=VolumeProfileConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    email: EmailConfig = field(default_factory=EmailConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)

    def __post_init__(self):
        """Thiết lập environment variables"""
        if APIKeys.VNSTOCK:
            os.environ['VNSTOCK_API_KEY'] = APIKeys.VNSTOCK
    
    def get_vnstock_key(self) -> str:
        return APIKeys.VNSTOCK
    
    def get_ai_provider(self) -> tuple:
        """Lấy AI provider và key có sẵn"""
        return AIProviderConfig.get_available_provider()
    
    def get_data_source(self) -> str:
        """Lấy data source mặc định"""
        return self.data_source.DEFAULT
    
    def print_status(self):
        """In trạng thái cấu hình"""
        print("\n" + "="*60)
        print("📋 CẤU HÌNH HIỆN TẠI")
        print("="*60)
        
        # Vnstock
        vnstock_status = "✓" if APIKeys.VNSTOCK else "✗"
        print(f"\n🔗 VNSTOCK: {vnstock_status}")
        if APIKeys.VNSTOCK:
            print(f"   Key: {APIKeys.VNSTOCK[:20]}...")
        
        # Data source
        print(f"\n📊 DATA SOURCE: {self.data_source.DEFAULT}")
        print(f"   Fallback: {' → '.join(self.data_source.PRIORITY)}")
        
        # AI Provider
        provider, key = self.get_ai_provider()
        if provider:
            print(f"\n🤖 AI PROVIDER: {provider.upper()}")
            print(f"   Key: {key[:20]}...")
        else:
            print("\n🤖 AI PROVIDER: ✗ Không có")
            print("   Cần điền ít nhất 1 API key trong config.py")
        
        print("\n" + "="*60)


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON INSTANCE
# ══════════════════════════════════════════════════════════════════════════════

_config_instance: Optional[UnifiedConfig] = None


def get_config() -> UnifiedConfig:
    """
    Lấy instance của UnifiedConfig (singleton pattern)
    
    Usage:
        from config import get_config
        config = get_config()
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = UnifiedConfig()
    
    return _config_instance


def reload_config() -> UnifiedConfig:
    """Reload config (useful khi thay đổi API keys)"""
    global _config_instance
    _config_instance = UnifiedConfig()
    return _config_instance


# ══════════════════════════════════════════════════════════════════════════════
# QUICK ACCESS FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def get_vnstock_key() -> str:
    """Quick access: Lấy vnstock API key"""
    return APIKeys.VNSTOCK


def get_ai_provider() -> tuple:
    """Quick access: Lấy AI provider và key"""
    return AIProviderConfig.get_available_provider()


def get_data_source() -> str:
    """Quick access: Lấy default data source"""
    return get_config().data_source.DEFAULT


# ══════════════════════════════════════════════════════════════════════════════
# TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    config = get_config()
    config.print_status()
