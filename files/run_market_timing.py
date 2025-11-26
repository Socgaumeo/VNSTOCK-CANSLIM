#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║         MARKET TIMING - QUICK START                          ║
║         Chạy nhanh Module 1 với AI Analysis                  ║
╚══════════════════════════════════════════════════════════════╝

Cách sử dụng:
1. Điền API keys vào phần CONFIG bên dưới
2. Chạy: python run_market_timing.py
"""

from module1_market_timing import MarketTimingModule, MarketTimingConfig

# ══════════════════════════════════════════════════════════════════════════════
# ⚠️ CONFIG - ĐIỀN API KEYS CỦA BẠN VÀO ĐÂY
# ══════════════════════════════════════════════════════════════════════════════

# VNSTOCK
VNSTOCK_API_KEY = ""        # API key vnstock premium

# AI PROVIDER - Chọn 1 và điền API key tương ứng
AI_PROVIDER = "deepseek"    # deepseek | gemini | claude | openai | groq

# API Keys cho từng provider (chỉ cần điền 1 cái tương ứng với AI_PROVIDER)
DEEPSEEK_API_KEY = ""       # https://platform.deepseek.com/
GEMINI_API_KEY = ""         # https://makersuite.google.com/app/apikey  
CLAUDE_API_KEY = ""         # https://console.anthropic.com/
OPENAI_API_KEY = ""         # https://platform.openai.com/
GROQ_API_KEY = ""           # https://console.groq.com/

# ══════════════════════════════════════════════════════════════════════════════
# KHÔNG CẦN SỬA GÌ BÊN DƯỚI
# ══════════════════════════════════════════════════════════════════════════════

def get_ai_key():
    """Lấy API key dựa trên provider đã chọn"""
    keys = {
        "deepseek": DEEPSEEK_API_KEY,
        "gemini": GEMINI_API_KEY,
        "claude": CLAUDE_API_KEY,
        "openai": OPENAI_API_KEY,
        "groq": GROQ_API_KEY,
    }
    return keys.get(AI_PROVIDER, "")


def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║         🚀 MARKET TIMING - QUICK START 🚀                    ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Tạo config
    config = MarketTimingConfig()
    config.VNSTOCK_API_KEY = VNSTOCK_API_KEY
    config.AI_PROVIDER = AI_PROVIDER
    config.AI_API_KEY = get_ai_key()
    
    # Kiểm tra
    if not config.AI_API_KEY:
        print(f"⚠️ Chưa có API key cho {AI_PROVIDER.upper()}")
        print("   Sẽ chỉ xuất dữ liệu thô, không có phân tích AI")
    
    # Chạy
    module = MarketTimingModule(config)
    report = module.run()
    
    print("\n" + "="*60)
    print("✅ HOÀN THÀNH!")
    print("="*60)
    
    return report


if __name__ == "__main__":
    report = main()
