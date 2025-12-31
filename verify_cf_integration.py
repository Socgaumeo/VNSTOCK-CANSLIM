import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from v3_enhanced.fundamental_enhanced_v3 import analyze_fundamental

def verify_cf_integration(symbol):
    print(f"\n🔍 Verifying Cash Flow for {symbol}...")
    result = analyze_fundamental(symbol)
    
    # Check for CF fields in data
    data = result.get('data', {})
    print(f"   OCF/Profit Ratio: {data.get('ocf_to_profit_ratio'):.2f}")
    print(f"   CF Quality Score: {data.get('cash_flow_quality_score')}")
    print(f"   CF Warning: {data.get('cash_flow_warning') or 'None'}")
    
    # Check breakdown
    breakdown = result.get('breakdown', {}).get('details', {})
    print(f"   Breakdown CF Quality: {breakdown.get('cf_quality')}")
    print(f"   Breakdown OCF/Profit: {breakdown.get('ocf_profit_ratio')}")

if __name__ == "__main__":
    # Test with a mix of sectors
    symbols = ['FPT', 'VCB', 'MWG', 'SSI']
    for s in symbols:
        try:
            verify_cf_integration(s)
        except Exception as e:
            print(f"❌ Error verifying {s}: {e}")
