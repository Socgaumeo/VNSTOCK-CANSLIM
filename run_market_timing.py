#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║         MARKET TIMING - QUICK START v2                        ║
║         Chạy nhanh Module 1 với Config thống nhất            ║
╚══════════════════════════════════════════════════════════════╝

Cách sử dụng:
1. Điền API keys vào file config.py
2. Chạy: python run_market_timing.py
"""

# Import từ module v2 (sử dụng config.py thống nhất)
from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║         🚀 MARKET TIMING v2 - QUICK START 🚀                  ║
║            Config từ config.py + Volume Profile              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Tạo config từ file config.py thống nhất
    config = create_config_from_unified()
    
    # In thông tin config
    print(f"📡 Data Source: {config.DATA_SOURCE}")
    print(f"🤖 AI Provider: {config.AI_PROVIDER.upper() if config.AI_PROVIDER else 'Chưa cấu hình'}")
    print(f"📊 Volume Profile: {'BẬT' if config.ENABLE_VOLUME_PROFILE else 'TẮT'}")
    print(f"📁 Output: {config.OUTPUT_DIR}")
    
    # Kiểm tra AI
    if not config.AI_API_KEY:
        print("\n⚠️ Không tìm thấy API key cho bất kỳ AI provider nào")
        print("   Sẽ chỉ xuất dữ liệu thô, không có phân tích AI")
        print("   Hãy điền API key vào file config.py")
    
    # Chạy module
    module = MarketTimingModule(config)
    report = module.run()
    
    print("\n" + "="*60)
    print("✅ HOÀN THÀNH!")
    print("="*60)
    
    return report


if __name__ == "__main__":
    report = main()
