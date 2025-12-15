#!/usr/bin/env python3
"""
Run Special Scans (MA200, Valuation)
Usage:
    python run_special_scans.py --scan ma200
    python run_special_scans.py --scan valuation --type PB
    python run_special_scans.py --scan valuation --type PE
"""

import argparse
import os
from datetime import datetime
from module4_special_scans import SpecialScanner

def main():
    parser = argparse.ArgumentParser(description='CANSLIM Special Scans')
    parser.add_argument('--scan', type=str, required=True, choices=['ma200', 'valuation'], help='Scan type')
    parser.add_argument('--type', type=str, choices=['PE', 'PB'], default='PB', help='Valuation metric (PE or PB)')
    parser.add_argument('--tolerance', type=float, default=5.0, help='MA200 tolerance %')
    parser.add_argument('--period', type=int, default=3, help='Historical period in years')
    parser.add_argument('--limit', type=int, default=0, help='Limit number of stocks to scan (0=all)')
    
    args = parser.parse_args()
    
    scanner = SpecialScanner()
    output_dir = "./output"
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    
    if args.scan == 'ma200':
        print(f"🚀 Running MA200 Scan (Tolerance: {args.tolerance}%)")
        results = scanner.scan_ma200(tolerance_pct=args.tolerance, limit=args.limit)
        report = scanner.generate_report(results, f"MA200 Support Scan (±{args.tolerance}%)")
        filename = f"{output_dir}/scan_ma200_{timestamp}.md"
        
    elif args.scan == 'valuation':
        print(f"🚀 Running Valuation Scan ({args.type})")
        results = scanner.scan_valuation(metric=args.type, period_years=args.period, limit=args.limit)
        report = scanner.generate_report(results, f"Undervalued {args.type} Scan")
        filename = f"{output_dir}/scan_valuation_{args.type}_{timestamp}.md"
    
    # Save report
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
        
    print(f"\n✅ Scan completed!")
    print(f"📄 Report saved to: {filename}")
    print("\nContent preview:")
    print("-" * 50)
    print(report[:1000] + "..." if len(report) > 1000 else report)
    print("-" * 50)

if __name__ == "__main__":
    main()
