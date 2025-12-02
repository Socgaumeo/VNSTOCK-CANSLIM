#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║         RUN MARKET TIMING v3 - QUICK START                   ║
║         Module 1 v3 với DataContext + Traffic Light IBD      ║
╚══════════════════════════════════════════════════════════════╝

Cách sử dụng:
1. Điền API keys vào file config.py
2. Chạy: python run_market_timing_v3.py
"""

from module1_market_timing_v3 import MarketTimingModule, create_config_from_unified

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║         🚀 MARKET TIMING v3 - QUICK START 🚀                  ║
║         DataContext + Traffic Light (IBD) + FTD              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Tạo config từ file config.py thống nhất
    config = create_config_from_unified()
    
    # In thông tin config
    print(f"📡 Data Source: {config.DATA_SOURCE}")
    print(f"🤖 AI Provider: {config.AI_PROVIDER.upper() if config.AI_PROVIDER else 'Chưa cấu hình'}")
    print(f"📊 Volume Profile: {'BẬT' if config.ENABLE_VOLUME_PROFILE else 'TẮT'}")
    print(f"📁 Output: {config.OUTPUT_DIR}")
    print(f"📅 Distribution Window: {config.DISTRIBUTION_WINDOW} phiên")
    print(f"✨ FTD Window: Day {config.FTD_MIN_DAY}-{config.FTD_MAX_DAY}")
    
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
    
    # Return report và JSON
    return report, module.get_json()


if __name__ == "__main__":
    report, json_output = main()
