from vnstock import Vnstock
import pandas as pd

def debug_cf(symbol):
    try:
        print(f"\n--- DEBUG {symbol} ---")
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        cf_df = stock.finance.cash_flow(period='quarter', lang='vi')
        if cf_df.empty:
            print("Empty CF DataFrame")
            return
        
        print(f"Columns: {cf_df.columns.tolist()}")
        # Check if first row has OCF
        for col in cf_df.columns:
            val = cf_df.iloc[0][col]
            print(f"[{col}]: {val} (type: {type(val)})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_cf('FPT')
    debug_cf('VCB')
