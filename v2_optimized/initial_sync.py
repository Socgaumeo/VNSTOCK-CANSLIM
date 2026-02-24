#!/usr/bin/env python3
"""
Initial sync script to populate SQLite database with historical data.

Usage:
    python initial_sync.py              # Sync all CANSLIM stocks, 5 years
    python initial_sync.py --days 365   # Sync 1 year
    python initial_sync.py --symbols VCB FPT TCB  # Sync specific stocks
    python initial_sync.py --quick      # Quick sync (120 days, top stocks only)
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta

# Ensure we can import from v2_optimized
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db, PriceStore, FundamentalStore
from config import get_config, APIKeys

# All CANSLIM universe stocks (from module3_stock_screener_v1.py)
SECTOR_STOCKS = {
    'VNFIN': ['VCB', 'BID', 'CTG', 'TCB', 'MBB', 'VPB', 'STB', 'HDB', 'ACB', 'TPB',
              'SSI', 'VND', 'HCM', 'VCI', 'SHS', 'BVH', 'PNJ'],
    'VNREAL': ['VHM', 'VIC', 'NVL', 'KDH', 'DXG', 'NLG', 'HDG', 'DIG', 'PDR', 'CEO',
               'KBC', 'IJC', 'SCR'],
    'VNMAT': ['HPG', 'HSG', 'NKG', 'TLH', 'POM', 'VGC', 'DHA', 'PHR', 'GVR', 'DPM',
              'DCM', 'CSV'],
    'VNIT': ['FPT', 'CMG', 'VGI', 'FOX', 'SAM', 'ELC', 'ITD'],
    'VNHEAL': ['DHG', 'DMC', 'IMP', 'TRA', 'DBD', 'PME', 'OPC'],
    'VNCOND': ['MWG', 'PNJ', 'DGW', 'HAX', 'VEA', 'SCS', 'AST'],
    'VNCONS': ['VNM', 'SAB', 'MSN', 'QNS', 'KDC', 'MCH', 'ANV'],
}

TOP_STOCKS = ['VCB', 'FPT', 'HPG', 'MWG', 'VNM', 'VHM', 'TCB', 'MBB',
              'ACB', 'STB', 'VPB', 'BID', 'CTG', 'HDB', 'SSI',
              'NVL', 'KDH', 'DGW', 'DHG', 'SAB', 'MSN', 'GVR']


def get_all_symbols() -> list:
    """Get all unique symbols from sector mapping."""
    symbols = set()
    for stocks in SECTOR_STOCKS.values():
        symbols.update(stocks)
    return sorted(symbols)


def sync_prices(symbols: list, days: int, api_delay: float = 1.5):
    """Sync OHLCV price data for all symbols."""
    db = get_db()
    price_store = PriceStore(db)

    # Set up vnstock
    api_key = APIKeys.VNSTOCK
    if api_key:
        os.environ['VNSTOCK_API_KEY'] = api_key

    try:
        from vnstock import Vnstock
    except ImportError:
        print("vnstock not installed. Run: pip install -U vnstock")
        return

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

    total = len(symbols)
    success = 0
    failed = []

    print(f"\n{'='*60}")
    print(f"SYNCING PRICES: {total} symbols, {days} days ({start_date} -> {end_date})")
    print(f"{'='*60}\n")

    for i, symbol in enumerate(symbols):
        # Check what we already have
        existing = price_store.get_data_range(symbol)
        fetch_start = start_date

        if existing['latest']:
            # Incremental: only fetch from last date
            days_old = (datetime.now() - datetime.strptime(existing['latest'], '%Y-%m-%d')).days
            if days_old <= 1 and existing['count'] >= days * 0.6:
                print(f"  [{i+1}/{total}] {symbol}: cached ({existing['count']} rows, latest {existing['latest']})")
                success += 1
                continue
            if existing['count'] > 20:
                fetch_start = existing['latest']

        try:
            stock = Vnstock().stock(symbol=symbol, source='VCI')
            df = stock.quote.history(start=fetch_start, end=end_date)

            if not df.empty:
                saved = price_store.save_prices(symbol, df)
                total_rows = price_store.get_data_range(symbol)['count']
                print(f"  [{i+1}/{total}] {symbol}: +{saved} rows (total: {total_rows})")
                success += 1
            else:
                print(f"  [{i+1}/{total}] {symbol}: empty response")
                failed.append(symbol)

        except Exception as e:
            error_msg = str(e)[:60]
            print(f"  [{i+1}/{total}] {symbol}: ERROR - {error_msg}")
            failed.append(symbol)

            if '429' in str(e) or 'rate' in str(e).lower():
                print(f"  Rate limited. Waiting 15s...")
                time.sleep(15)

        # Rate limiting
        time.sleep(api_delay)
        if (i + 1) % 20 == 0:
            print(f"\n  Batch pause ({i+1}/{total})...\n")
            time.sleep(3)

    print(f"\n{'='*60}")
    print(f"SYNC COMPLETE: {success}/{total} success, {len(failed)} failed")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    print(f"{'='*60}")


def sync_fundamentals(symbols: list, api_delay: float = 1.5):
    """Sync fundamental data for all symbols."""
    db = get_db()
    fund_store = FundamentalStore(db)

    api_key = APIKeys.VNSTOCK
    if api_key:
        os.environ['VNSTOCK_API_KEY'] = api_key

    try:
        from vnstock import Vnstock
    except ImportError:
        print("vnstock not installed.")
        return

    total = len(symbols)
    success = 0

    print(f"\n{'='*60}")
    print(f"SYNCING FUNDAMENTALS: {total} symbols")
    print(f"{'='*60}\n")

    for i, symbol in enumerate(symbols):
        # Skip if fresh
        if fund_store.is_fresh(symbol, max_days=7):
            print(f"  [{i+1}/{total}] {symbol}: cached (fresh)")
            success += 1
            continue

        try:
            stock = Vnstock().stock(symbol=symbol, source='VCI')

            # Income statement
            df_income = stock.finance.income_statement(period='quarter', lang='vi')
            if not df_income.empty:
                col_rev = 'Doanh thu (đồng)'
                col_profit = 'Lợi nhuận sau thuế của Cổ đông công ty mẹ (đồng)'
                records = []
                for idx, row in df_income.head(12).iterrows():
                    records.append({
                        'period': str(idx),
                        'revenue': float(row.get(col_rev, 0) or 0),
                        'profit': float(row.get(col_profit, 0) or 0),
                    })
                if records:
                    fund_store.save_quarterly(symbol, records)

            time.sleep(api_delay * 0.5)

            # Ratios
            df_ratio = stock.finance.ratio(period='quarter', lang='vi')
            if not df_ratio.empty:
                records = []
                for idx, row in df_ratio.head(12).iterrows():
                    pe = float(row.get(('Chỉ tiêu định giá', 'P/E'), 0) or 0)
                    pb = float(row.get(('Chỉ tiêu định giá', 'P/B'), 0) or 0)
                    roe = float(row.get(('Chỉ tiêu khả năng sinh lợi', 'ROE (%)'), 0) or 0) * 100
                    roa = float(row.get(('Chỉ tiêu khả năng sinh lợi', 'ROA (%)'), 0) or 0) * 100
                    records.append({
                        'period': str(idx),
                        'pe': pe, 'pb': pb, 'roe': roe, 'roa': roa,
                    })
                if records:
                    fund_store.save_quarterly(symbol, records)

            print(f"  [{i+1}/{total}] {symbol}: OK")
            success += 1

        except Exception as e:
            error_msg = str(e)[:60]
            print(f"  [{i+1}/{total}] {symbol}: ERROR - {error_msg}")
            if '429' in str(e):
                time.sleep(15)

        time.sleep(api_delay)
        if (i + 1) % 20 == 0:
            print(f"\n  Batch pause ({i+1}/{total})...\n")
            time.sleep(3)

    print(f"\nFundamentals sync: {success}/{total} success")


def print_db_stats():
    """Print database statistics."""
    db = get_db()
    stats = db.get_table_stats()
    price_store = PriceStore(db)

    print(f"\n{'='*60}")
    print(f"DATABASE STATISTICS")
    print(f"{'='*60}")
    print(f"  DB path: {db.db_path}")
    db_size = os.path.getsize(db.db_path) / (1024 * 1024) if os.path.exists(db.db_path) else 0
    print(f"  DB size: {db_size:.1f} MB")
    print(f"\n  Table rows:")
    for table, count in stats.items():
        print(f"    {table}: {count:,}")

    symbols = price_store.get_symbols_with_data()
    print(f"\n  Symbols with price data: {len(symbols)}")
    if symbols:
        print(f"    First 10: {', '.join(symbols[:10])}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Sync historical data to SQLite')
    parser.add_argument('--days', type=int, default=1825, help='Days of history (default: 1825 = 5 years)')
    parser.add_argument('--symbols', nargs='+', help='Specific symbols to sync')
    parser.add_argument('--quick', action='store_true', help='Quick sync (120 days, top stocks)')
    parser.add_argument('--fundamentals', action='store_true', help='Also sync fundamental data')
    parser.add_argument('--stats', action='store_true', help='Show database stats only')
    parser.add_argument('--delay', type=float, default=1.5, help='API delay in seconds')

    args = parser.parse_args()

    if args.stats:
        print_db_stats()
        return

    if args.quick:
        symbols = TOP_STOCKS
        days = 120
    elif args.symbols:
        symbols = args.symbols
        days = args.days
    else:
        symbols = get_all_symbols()
        days = args.days

    start_time = time.time()

    sync_prices(symbols, days, api_delay=args.delay)

    if args.fundamentals or not args.quick:
        sync_fundamentals(symbols, api_delay=args.delay)

    elapsed = time.time() - start_time
    print(f"\nTotal time: {elapsed/60:.1f} minutes")

    print_db_stats()


if __name__ == '__main__':
    main()
