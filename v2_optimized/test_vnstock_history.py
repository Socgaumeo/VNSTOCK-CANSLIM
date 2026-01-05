
from vnstock import Vnstock
import pandas as pd

try:
    stock = Vnstock().stock(symbol='VCI', source='VCI')
    df = stock.quote.history(start='2025-12-01', end='2026-01-05')
    print("Columns:", df.columns.tolist())
    print("Head:\n", df.head())
    
    # Check for foreign data
    foreign_cols = [c for c in df.columns if 'foreign' in c.lower() or 'nn' in c.lower()]
    print("Foreign Columns:", foreign_cols)
except Exception as e:
    print(e)
