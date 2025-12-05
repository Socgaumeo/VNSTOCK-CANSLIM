from module3_stock_screener_v1 import StockScreener, ScreenerConfig

print("Initializing Screener...")
config = ScreenerConfig()
screener = StockScreener(config)

symbol = 'VCB'
print(f"\nAnalyzing {symbol}...")
data = screener.fundamental_analyzer.analyze(symbol)

print("\n--- RESULT ---")
print(f"ROE: {data.roe}%")
print(f"PE: {data.pe_ratio}")
print(f"EPS Growth YoY: {data.eps_growth_yoy}%")
print(f"EPS Growth QoQ: {data.eps_growth_qoq}%")
print(f"Revenue Growth YoY: {data.revenue_growth_yoy}%")
print(f"C Score: {data.c_score}")
print(f"A Score: {data.a_score}")
