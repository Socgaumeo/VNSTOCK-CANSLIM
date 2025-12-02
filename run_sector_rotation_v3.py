#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║         RUN SECTOR ROTATION v3 - QUICK START                 ║
║         RS Rating (IBD) + Rotation Clock + JSON Output       ║
╚══════════════════════════════════════════════════════════════╝

Cách sử dụng:
1. Điền API keys vào file config.py
2. Chạy: python run_sector_rotation_v3.py

Tích hợp với Module 1:
    Truyền market_context từ Module 1 để có phân tích đầy đủ hơn
"""

from module2_sector_rotation_v3 import SectorRotationModule, create_config_from_unified

def main():
    print("""
╔══════════════════════════════════════════════════════════════╗
║         🚀 SECTOR ROTATION v3 - QUICK START 🚀                ║
║         RS Rating (IBD) + Rotation Clock Analysis            ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Tạo config từ file config.py thống nhất
    config = create_config_from_unified()
    
    # In thông tin config
    print(f"📡 Data Source: {config.DATA_SOURCE}")
    print(f"🤖 AI Provider: {config.AI_PROVIDER.upper() if config.AI_PROVIDER else 'Chưa cấu hình'}")
    print(f"📊 Volume Profile: {'BẬT' if config.ENABLE_VOLUME_PROFILE else 'TẮT'}")
    print(f"📁 Output: {config.OUTPUT_DIR}")
    
    # RS Rating weights
    print(f"\n📈 RS Rating Weights (IBD-style):")
    print(f"   Q1 (3 tháng): {config.RS_WEIGHT_Q1*100:.0f}%")
    print(f"   Q2 (6 tháng): {config.RS_WEIGHT_Q2*100:.0f}%")
    print(f"   Q3 (9 tháng): {config.RS_WEIGHT_Q3*100:.0f}%")
    print(f"   Q4 (12 tháng): {config.RS_WEIGHT_Q4*100:.0f}%")
    
    # Sector indices
    print(f"\n📊 Sector Indices (7 indices hợp lệ):")
    for code, name in config.SECTOR_INDICES.items():
        print(f"   - {code}: {name}")
    
    # Market context (có thể lấy từ Module 1 nếu đã chạy)
    # Ví dụ hardcode từ kết quả Module 1 hôm nay:
    market_context = {
        'traffic_light': '🟡 VÀNG - THẬN TRỌNG',
        'distribution_days': 6,
        'market_regime': 'DISTRIBUTION'
    }
    
    print(f"\n📋 Market Context (từ Module 1):")
    print(f"   Traffic Light: {market_context['traffic_light']}")
    print(f"   Distribution Days: {market_context['distribution_days']}")
    print(f"   Market Regime: {market_context['market_regime']}")
    
    # Chạy module
    module = SectorRotationModule(config)
    report = module.run(market_context)
    
    print("\n" + "="*60)
    print("✅ HOÀN THÀNH!")
    print("="*60)
    
    return report, module.get_json()


if __name__ == "__main__":
    report, json_output = main()