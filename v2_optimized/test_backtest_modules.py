"""Test script for backtesting modules."""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from performance_tracker import PerformanceTracker
from simple_backtester import SimpleBacktester

def test_modules():
    print("=== Testing Performance Tracker ===")
    tracker = PerformanceTracker()

    # Test metrics calculation
    metrics = tracker.calc_metrics(days=90)
    print(f"Total signals (90d): {metrics.total_signals}")
    print(f"Win rate (20d): {metrics.win_rate_20d:.1f}%")
    print(f"Avg return (20d): {metrics.avg_return_20d:+.1f}%")

    # Test report generation
    report = tracker.generate_report(days=90)
    print(f"\nReport preview (first 500 chars):\n{report[:500]}...")

    print("\n=== Testing Simple Backtester ===")
    backtester = SimpleBacktester()

    # Test simple backtest
    result = backtester.backtest_signals(days_back=180, hold_days=20)
    print(f"Total trades: {result.total_trades}")
    print(f"Win rate: {result.win_rate:.1f}%")
    print(f"Avg return: {result.avg_return:+.1f}%")
    print(f"Profit factor: {result.profit_factor:.2f}")

    # Test backtest with stops
    result_stops = backtester.backtest_with_stops(days_back=180)
    print(f"\nWith stops - Total trades: {result_stops.total_trades}")
    print(f"Win rate: {result_stops.win_rate:.1f}%")
    print(f"Avg return: {result_stops.avg_return:+.1f}%")

    # Test comparison
    comparison = backtester.compare_strategies(days_back=180)
    print(f"\nComparison report preview (first 800 chars):\n{comparison[:800]}...")

    print("\n✅ All tests passed!")

if __name__ == "__main__":
    test_modules()
