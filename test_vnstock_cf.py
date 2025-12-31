from vnstock import Vnstock
import pandas as pd

def test_cash_flow(symbol):
    try:
        print(f"Testing cash flow for {symbol}...")
        stock = Vnstock().stock(symbol=symbol, source='VCI')
        cf_df = stock.finance.cash_flow(period='quarter', lang='vi')
        print(f"Columns: {cf_df.columns.tolist()}")
        print(f"Head:\n{cf_df.head(2)}")
        
        # Check for OCF
        for col in cf_df.columns:
            if 'lưu chuyển tiền thuần từ hoạt động kinh doanh' in str(col).lower():
                print(f"Found OCF column: {col}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_cash_flow('VCB')
    test_cash_flow('FPT')
    test_cash_flow('MWG')
