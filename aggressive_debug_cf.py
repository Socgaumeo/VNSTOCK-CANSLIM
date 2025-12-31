from vnstock import Vnstock
import pandas as pd
import numpy as np

def aggressive_debug(symbol):
    print(f"\n{'='*20} DEBUG: {symbol} {'='*20}")
    try:
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        cf_df = stock.finance.cash_flow(period='quarter', lang='vi')
        
        if cf_df.empty:
            print("❌ DataFrame is EMPTY")
            return
            
        print(f"✅ DataFrame shape: {cf_df.shape}")
        print("\n--- ALL COLUMNS ---")
        for i, col in enumerate(cf_df.columns):
            print(f"{i}. [{col}]")
            
        print("\n--- FIRST 2 ROWS DATA (Values) ---")
        for i in range(min(2, len(cf_df))):
            row = cf_df.iloc[i]
            print(f"\nRow {i} ({row.get('Kỳ', 'N/A')}/{row.get('Năm', 'N/A')}):")
            for col in cf_df.columns:
                val = row[col]
                if pd.notna(val) and val != 0:
                    print(f"   - {col}: {val}")
                    
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    aggressive_debug('FPT')
    aggressive_debug('VCB')
    aggressive_debug('MWG')
