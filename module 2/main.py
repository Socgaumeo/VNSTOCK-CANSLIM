#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    CANSLIM SCANNER - MAIN RUNNER                             ║
║              Chạy tất cả Modules từ một file duy nhất                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Workflow:                                                                   ║
║  1. Module 1: Market Timing → Xác định màu thị trường                       ║
║  2. Module 2: Sector Rotation → Tìm ngành dẫn dắt                           ║
║  3. Module 3: Stock Selection → Chọn cổ phiếu trong ngành (Coming)          ║
║  4. Module 4: Entry Point → Xác định điểm mua (Coming)                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Cách sử dụng:
    python main.py                  # Chạy full workflow
    python main.py --module 1       # Chỉ chạy Module 1
    python main.py --module 2       # Chỉ chạy Module 2
    python main.py --status         # Kiểm tra config
"""

import sys
import argparse
from datetime import datetime

# Import config
from config import get_config, reload_config


# ══════════════════════════════════════════════════════════════════════════════
# MODULE RUNNERS
# ══════════════════════════════════════════════════════════════════════════════

def run_module_1():
    """Chạy Module 1: Market Timing"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║           MODULE 1: MARKET TIMING                            ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified
        
        config = create_config_from_unified()
        module = MarketTimingModule(config)
        report = module.run()
        
        return report
        
    except ImportError as e:
        print(f"❌ Lỗi import Module 1: {e}")
        print("   Đang thử với phiên bản cũ...")
        
        try:
            from module1_market_timing import MarketTimingModule, MarketTimingConfig
            
            unified = get_config()
            
            config = MarketTimingConfig()
            config.VNSTOCK_API_KEY = unified.get_vnstock_key()
            
            ai_provider, ai_key = unified.get_ai_provider()
            config.AI_PROVIDER = ai_provider
            config.AI_API_KEY = ai_key
            
            module = MarketTimingModule(config)
            return module.run()
            
        except Exception as e2:
            print(f"❌ Lỗi: {e2}")
            return None


def run_module_2():
    """Chạy Module 2: Sector Rotation"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║           MODULE 2: SECTOR ROTATION                          ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    try:
        from module2_sector_rotation_v2 import SectorRotationModule, create_config_from_unified
        
        config = create_config_from_unified()
        module = SectorRotationModule(config)
        report = module.run()
        
        return report
        
    except ImportError as e:
        print(f"❌ Lỗi import Module 2: {e}")
        print("   Đang thử với phiên bản cũ...")
        
        try:
            from module2_sector_rotation import SectorRotationModule, SectorRotationConfig
            
            unified = get_config()
            
            config = SectorRotationConfig()
            config.VNSTOCK_API_KEY = unified.get_vnstock_key()
            
            ai_provider, ai_key = unified.get_ai_provider()
            config.AI_PROVIDER = ai_provider
            config.AI_API_KEY = ai_key
            
            module = SectorRotationModule(config)
            return module.run()
            
        except Exception as e2:
            print(f"❌ Lỗi: {e2}")
            return None


def run_module_3():
    """Chạy Module 3: Stock Selection (Coming Soon)"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║           MODULE 3: STOCK SELECTION                          ║
║                   🚧 COMING SOON 🚧                          ║
╚══════════════════════════════════════════════════════════════╝
    """)
    return None


def run_module_4():
    """Chạy Module 4: Entry Point (Coming Soon)"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║           MODULE 4: ENTRY POINT DETECTION                    ║
║                   🚧 COMING SOON 🚧                          ║
╚══════════════════════════════════════════════════════════════╝
    """)
    return None


# ══════════════════════════════════════════════════════════════════════════════
# FULL WORKFLOW
# ══════════════════════════════════════════════════════════════════════════════

def run_full_workflow():
    """Chạy full workflow dựa trên Market Color"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🚀 CANSLIM SCANNER - FULL WORKFLOW 🚀                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    results = {}
    
    # 1. Market Timing
    print("\n" + "="*70)
    print("STEP 1/4: MARKET TIMING")
    print("="*70)
    
    m1_report = run_module_1()
    results['module1'] = m1_report
    
    if m1_report is None:
        print("\n❌ Module 1 thất bại, không thể tiếp tục")
        return results
    
    # Kiểm tra Market Color
    market_color = getattr(m1_report, 'market_color', '🟡 VÀNG')
    market_score = getattr(m1_report, 'market_score', 50)
    
    print(f"\n📊 Kết quả Module 1:")
    print(f"   Market Color: {market_color}")
    print(f"   Market Score: {market_score}/100")
    
    # 2. Sector Rotation (chỉ chạy nếu không phải ĐỎ)
    if "ĐỎ" not in market_color:
        print("\n" + "="*70)
        print("STEP 2/4: SECTOR ROTATION")
        print("="*70)
        
        m2_report = run_module_2()
        results['module2'] = m2_report
        
        if m2_report:
            leading = getattr(m2_report, 'leading_sectors', [])
            if leading:
                print(f"\n🚀 Ngành dẫn dắt: {', '.join([s.name for s in leading])}")
    else:
        print("\n⚠️ Market Color = ĐỎ → Bỏ qua Sector Rotation")
        print("   💡 Khuyến nghị: Giữ tiền mặt, không tham gia thị trường")
    
    # 3 & 4: Coming soon
    print("\n" + "="*70)
    print("STEP 3-4: COMING SOON")
    print("="*70)
    print("   Module 3: Stock Selection")
    print("   Module 4: Entry Point Detection")
    
    # Summary
    print("\n" + "="*70)
    print("📋 TỔNG KẾT")
    print("="*70)
    
    print(f"""
📅 Thời gian: {datetime.now().strftime('%d/%m/%Y %H:%M')}
🎯 Market Color: {market_color}
📊 Market Score: {market_score}/100
    """)
    
    if "XANH" in market_color:
        print("💡 Khuyến nghị: TẤN CÔNG - Tăng tỷ trọng cổ phiếu trong ngành dẫn dắt")
    elif "VÀNG" in market_color:
        print("💡 Khuyến nghị: PHÒNG THỦ - Giữ nguyên, chỉ mua cổ phiếu dẫn dắt nếu breakout")
    else:
        print("💡 Khuyến nghị: RÚT LUI - Giữ tiền mặt >= 50%")
    
    return results


# ══════════════════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════════════════

def check_status():
    """Kiểm tra trạng thái config"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║              📋 KIỂM TRA CẤU HÌNH                            ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    config = get_config()
    config.print_status()
    
    # Kiểm tra modules
    print("\n📦 MODULES:")
    
    modules = [
        ('module1_market_timing', 'Module 1: Market Timing'),
        ('module2_sector_rotation', 'Module 2: Sector Rotation'),
        ('data_collector', 'Data Collector'),
        ('volume_profile', 'Volume Profile'),
        ('ai_providers', 'AI Providers'),
    ]
    
    for module_name, display_name in modules:
        try:
            __import__(module_name)
            print(f"   ✓ {display_name}")
        except ImportError:
            print(f"   ✗ {display_name}")
    
    # Kiểm tra vnstock
    print("\n🔌 VNSTOCK:")
    try:
        from vnstock import Vnstock
        print("   ✓ vnstock installed")
        
        # Test connection
        stock = Vnstock().stock(symbol="VNM", source="VCI")
        print("   ✓ VCI connection OK")
    except Exception as e:
        print(f"   ✗ Error: {e}")
    
    print("\n" + "="*60)


def print_help():
    """In hướng dẫn sử dụng"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                         HƯỚNG DẪN SỬ DỤNG                                   ║
╚══════════════════════════════════════════════════════════════════════════════╝

📌 CÁCH CHẠY:

    python main.py                  # Chạy full workflow (Module 1 → 2 → ...)
    python main.py --module 1       # Chỉ chạy Module 1 (Market Timing)
    python main.py --module 2       # Chỉ chạy Module 2 (Sector Rotation)
    python main.py --status         # Kiểm tra cấu hình
    python main.py --help           # Hiển thị hướng dẫn này

📌 CẤU HÌNH:

    Mở file config.py và điền API keys vào class APIKeys:
    
    class APIKeys:
        VNSTOCK = "your_vnstock_key"
        GEMINI = "your_gemini_key"
        # hoặc DEEPSEEK, CLAUDE, OPENAI, GROQ

📌 WORKFLOW ĐỀ XUẤT:

    1. Mỗi sáng trước phiên: Chạy full workflow
    2. Giữa phiên: Chạy Module 1 để update market timing
    3. Cuối tuần: Chạy Module 2 để review sector rotation

📌 FILES:

    config.py           - Cấu hình chung (API keys)
    main.py             - File chạy chính
    module1_*.py        - Market Timing
    module2_*.py        - Sector Rotation
    data_collector.py   - Thu thập dữ liệu (multi-source)
    volume_profile.py   - Phân tích Volume Profile
    ai_providers.py     - Tích hợp AI
    """)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='CANSLIM Scanner - Vietnam Stock Market',
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        '--module', '-m',
        type=int,
        choices=[1, 2, 3, 4],
        help='Chạy module cụ thể (1-4)'
    )
    
    parser.add_argument(
        '--status', '-s',
        action='store_true',
        help='Kiểm tra trạng thái cấu hình'
    )
    
    parser.add_argument(
        '--help-detail', '-hd',
        action='store_true',
        help='Hiển thị hướng dẫn chi tiết'
    )
    
    args = parser.parse_args()
    
    # Xử lý arguments
    if args.help_detail:
        print_help()
        return
    
    if args.status:
        check_status()
        return
    
    if args.module:
        if args.module == 1:
            run_module_1()
        elif args.module == 2:
            run_module_2()
        elif args.module == 3:
            run_module_3()
        elif args.module == 4:
            run_module_4()
        return
    
    # Mặc định: chạy full workflow
    run_full_workflow()


if __name__ == "__main__":
    main()
