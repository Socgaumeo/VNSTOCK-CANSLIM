"""Quick test script for portfolio module functionality."""
import sys
from portfolio import (
    PositionSizer, TrailingStopManager, PortfolioManager, WatchlistManager
)

def test_position_sizer():
    """Test position sizing calculations."""
    print("\n=== Testing PositionSizer ===")
    sizer = PositionSizer()

    # Test scenario: 10B NAV, entry 50k, stop 46.5k (-7%), GREEN market, STRONG_BUY
    nav = 10_000_000_000
    entry = 50_000
    stop = 46_500
    target = 60_000

    pos = sizer.calc_position(
        nav=nav,
        entry_price=entry,
        stop_loss=stop,
        target_price=target,
        market_color='GREEN',
        conviction='STRONG_BUY'
    )

    print(f"Entry: {entry:,} | Stop: {stop:,} | Target: {target:,}")
    print(f"Shares: {pos.shares:,} (lot adjusted: {pos.lot_adjusted})")
    print(f"Amount: {pos.amount:,.0f} VND ({pos.amount/nav*100:.1f}% NAV)")
    print(f"Risk: {pos.risk_amount:,.0f} VND ({pos.risk_pct*100:.2f}% NAV)")
    print(f"R:R: {pos.risk_reward:.2f}")

    # Test pyramid sizing
    pyramid = sizer.calc_pyramid_sizes(pos.shares)
    print(f"Pyramid: Pilot={pyramid['pilot']} | Add={pyramid['add']} | Full={pyramid['full']}")
    print("✓ PositionSizer OK")

def test_trailing_stop():
    """Test trailing stop logic."""
    print("\n=== Testing TrailingStopManager ===")
    tsm = TrailingStopManager()

    entry = 50_000
    scenarios = [
        (50_000, 50_000, "Initial (0%)"),
        (52_500, 52_500, "Breakeven trigger (+5%)"),
        (55_000, 55_000, "MA10 trigger (+10%)"),
        (60_000, 60_000, "MA20 trigger (+20%)"),
    ]

    for current, highest, label in scenarios:
        stop = tsm.calc_stop(entry, current, highest)
        pct_gain = (current - entry) / entry * 100
        print(f"{label}: Current={current:,} | Stop={stop.stop_price:,.0f} ({stop.stop_type}) | Gain={pct_gain:+.1f}%")

    print("✓ TrailingStopManager OK")

def test_portfolio_manager():
    """Test portfolio management."""
    print("\n=== Testing PortfolioManager ===")
    pm = PortfolioManager(nav=10_000_000_000)

    # Add positions
    success, msg = pm.add_position('VNM', 85_000, 1000, 79_000, 95_000, 'Food & Beverage', 85.5, 1)
    print(f"Add VNM: {msg}")

    success, msg = pm.add_position('HPG', 25_000, 2000, 23_000, 30_000, 'Steel', 78.2, 1)
    print(f"Add HPG: {msg}")

    # Update prices
    pm.update_prices({'VNM': 87_000, 'HPG': 26_000})
    print(f"Updated prices")

    # Generate report
    print("\n" + pm.generate_report())

    # Test serialization
    state = pm.to_dict()
    pm2 = PortfolioManager.from_dict(state)
    print(f"\n✓ Serialization: {len(pm2.portfolio.positions)} positions restored")
    print("✓ PortfolioManager OK")

def test_watchlist_manager():
    """Test watchlist management."""
    print("\n=== Testing WatchlistManager ===")
    wm = WatchlistManager()

    # Add items
    wm.add('FPT', 95_000, 98_000, 92_000, 110_000, 'Breakout setup', 'IT', 88.5)
    wm.add('VIC', 42_000, 44_000, 40_000, 50_000, 'Cup base', 'Real Estate', 82.0)

    # Check alerts
    prices = {'FPT': 96_500, 'VIC': 45_000}
    alerts = wm.check_alerts(prices)
    print("Alerts:")
    for alert in alerts:
        print(f"  {alert}")

    # Generate report
    print("\n" + wm.generate_report())

    # Test serialization
    data = wm.to_list()
    wm2 = WatchlistManager.from_list(data)
    print(f"\n✓ Serialization: {len(wm2.items)} items restored")
    print("✓ WatchlistManager OK")

if __name__ == '__main__':
    try:
        test_position_sizer()
        test_trailing_stop()
        test_portfolio_manager()
        test_watchlist_manager()
        print("\n" + "="*50)
        print("ALL TESTS PASSED ✓")
        print("="*50)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
