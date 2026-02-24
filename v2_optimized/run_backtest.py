#!/usr/bin/env python3
"""
VNSTOCK-CANSLIM Backtest Runner
Runs backtests against historical signals and generates performance reports.
"""
import sys
import os
import importlib.util
from datetime import datetime

# Ensure correct import path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from performance_tracker import PerformanceTracker
from simple_backtester import SimpleBacktester
from vn_market_optimizer import VNMarketOptimizer, SECTOR_PE_RANGES


# Load risk-metrics-calculator module dynamically
def _load_risk_module():
    """Load risk-metrics-calculator module with kebab-case filename."""
    try:
        module_path = os.path.join(os.path.dirname(__file__), "risk-metrics-calculator.py")
        spec = importlib.util.spec_from_file_location("risk_metrics_calculator", module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    except Exception as e:
        print(f"⚠️ Could not load risk-metrics-calculator: {e}")
    return None


_risk_module = _load_risk_module()

def main():
    print("=" * 60)
    print("  VNSTOCK-CANSLIM BACKTEST RUNNER")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    # 1. Initialize
    tracker = PerformanceTracker()
    backtester = SimpleBacktester()
    optimizer = VNMarketOptimizer()

    # 2. Check DB status
    print("\n📊 Checking database status...")
    try:
        from database import get_db
        db = get_db()

        # Count records
        signals_count = db.fetchone("SELECT COUNT(*) FROM signals_history")[0]
        prices_count = db.fetchone("SELECT COUNT(DISTINCT symbol) FROM prices")[0]

        print(f"  Signals in DB: {signals_count}")
        print(f"  Symbols with price data: {prices_count}")

        if signals_count == 0:
            print("\n⚠️  No signals in database. Run the screener first to generate signals.")
            print("  Use: python run_full_pipeline.py")

            # Still show what data we have
            date_range = db.fetchone("SELECT MIN(date), MAX(date) FROM prices")
            if date_range and date_range[0]:
                print(f"\n  Price data available: {date_range[0]} → {date_range[1]}")
            return

        # Show signal distribution
        print("\n📋 Signal Distribution:")
        signal_dist = db.fetchall("""
            SELECT signal, COUNT(*) as cnt
            FROM signals_history
            GROUP BY signal
            ORDER BY cnt DESC
        """)
        for sig, cnt in signal_dist:
            print(f"  {sig}: {cnt}")

    except Exception as e:
        print(f"  ⚠️  Database check failed: {e}")

    # 3. Update returns for existing signals
    print("\n🔄 Updating signal returns...")
    updated = tracker.update_returns()
    print(f"  Updated returns for {updated} signals")

    # 4. Performance tracking report
    print("\n📈 Generating performance report...")
    perf_report = tracker.generate_report(days=180)
    print(perf_report)

    # 5. Run backtests
    print("\n" + "=" * 60)
    print("🔬 RUNNING BACKTESTS")
    print("=" * 60)

    comparison = backtester.compare_strategies(days_back=365)
    print(comparison)

    # 6. Detailed strategy results
    print("\n" + "=" * 60)
    print("📊 DETAILED STRATEGY RESULTS")
    print("=" * 60)

    strategies = [
        ("All Signals (Hold 5d)", lambda: backtester.backtest_signals(365, hold_days=5)),
        ("All Signals (Hold 20d)", lambda: backtester.backtest_signals(365, hold_days=20)),
        ("All Signals (Hold 60d)", lambda: backtester.backtest_signals(365, hold_days=60)),
        ("STRONG_BUY Only (Hold 20d)", lambda: backtester.backtest_signals(365, signal_filter='STRONG_BUY', hold_days=20)),
        ("BUY Only (Hold 20d)", lambda: backtester.backtest_signals(365, signal_filter='BUY', hold_days=20)),
        ("7% Stop / 20% Target", lambda: backtester.backtest_with_stops(365, stop_pct=0.07, target_pct=0.20)),
        ("5% Stop / 15% Target", lambda: backtester.backtest_with_stops(365, stop_pct=0.05, target_pct=0.15)),
        ("STRONG_BUY + Stops", lambda: backtester.backtest_with_stops(365, signal_filter='STRONG_BUY', stop_pct=0.07, target_pct=0.20)),
    ]

    results_data = []
    for name, strategy_fn in strategies:
        result = strategy_fn()
        results_data.append((name, result))
        if result.total_trades > 0:
            print(f"\n  {name}:")
            print(f"    Trades: {result.total_trades} | Win: {result.win_rate:.1f}% | "
                  f"Avg: {result.avg_return:+.1f}% | PF: {result.profit_factor:.2f} | "
                  f"MaxDD: {result.max_drawdown:.1f}%")

            # Show exit reason breakdown for stop strategies
            if any(t.exit_reason != 'HOLD_EXPIRED' for t in result.trades):
                stop_count = sum(1 for t in result.trades if t.exit_reason == 'STOP_LOSS')
                target_count = sum(1 for t in result.trades if t.exit_reason == 'TARGET')
                hold_count = sum(1 for t in result.trades if t.exit_reason == 'HOLD_EXPIRED')
                print(f"    Exit reasons: Stop={stop_count} | Target={target_count} | Hold={hold_count}")

    # 6.5 Calculate risk-adjusted metrics for equity curve (if module available)
    risk_adjusted_metrics = {}
    if _risk_module and results_data:
        # Use the best performing strategy for risk analysis
        best_result = max(results_data, key=lambda x: x[1].avg_return if x[1].total_trades > 0 else -999)
        if best_result[1].total_trades > 0:
            try:
                # Build equity curve from trades
                equity_curve = [10000.0]  # Start with 10k
                for trade in best_result[1].trades:
                    equity_curve.append(equity_curve[-1] * (1 + trade.return_pct / 100))

                # Convert to price history format
                price_history = [{'time': f'day_{i}', 'close': equity_curve[i]} for i in range(len(equity_curve))]

                # Calculate risk metrics
                calc = _risk_module.RiskCalculator(price_history, risk_free_rate=0.05)
                risk_adjusted_metrics = {
                    'sharpe': calc.calc_sharpe(),
                    'sortino': calc.calc_sortino(),
                    'max_drawdown': calc.calc_max_drawdown(),
                }

                print("\n" + "=" * 60)
                print("📊 RISK-ADJUSTED METRICS (Best Strategy Equity Curve)")
                print("=" * 60)
                print(f"  Strategy: {best_result[0]}")
                print(f"  Sharpe Ratio: {risk_adjusted_metrics.get('sharpe', 'N/A')}")
                print(f"  Sortino Ratio: {risk_adjusted_metrics.get('sortino', 'N/A')}")
                print(f"  Max Drawdown: {risk_adjusted_metrics.get('max_drawdown', 'N/A')}%")
            except Exception as e:
                print(f"\n⚠️ Could not calculate risk-adjusted metrics: {e}")

    # 7. VN Market Insights
    print("\n" + "=" * 60)
    print("🇻🇳 VN MARKET OPTIMIZATION INSIGHTS")
    print("=" * 60)
    print(f"\n  RSI zones (VN adjusted): Oversold < 35, Overbought > 65, Optimal 45-65")
    print(f"  Price limits: HOSE ±7%, HNX ±10%, UPCOM ±15%")
    print(f"\n  Sector PE Ranges:")
    for sector, (low, high) in sorted(SECTOR_PE_RANGES.items()):
        print(f"    {sector}: {low}-{high}")
    print(f"\n  Liquidity filter: Min 5B VND avg daily value")
    print(f"  Max participation rate: 5% of daily volume")
    print(f"  Settlement: T+2.5 (plan cash flow accordingly)")

    # 8. Save report to file
    report_lines = [
        f"# VNSTOCK-CANSLIM BACKTEST REPORT",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        perf_report,
        "",
        comparison,
        "",
        "## Strategy Details",
    ]

    for name, result in results_data:
        if result.total_trades > 0:
            report_lines.extend([
                f"\n### {name}",
                f"- Trades: {result.total_trades}",
                f"- Win Rate: {result.win_rate:.1f}%",
                f"- Avg Return: {result.avg_return:+.1f}%",
                f"- Avg Winner: {result.avg_winner:+.1f}%",
                f"- Avg Loser: {result.avg_loser:+.1f}%",
                f"- Profit Factor: {result.profit_factor:.2f}",
                f"- Max Drawdown: {result.max_drawdown:.1f}%",
                f"- Sharpe Ratio: {result.sharpe_ratio:.2f}",
            ])

    # Add risk-adjusted metrics section if available
    if risk_adjusted_metrics:
        report_lines.extend([
            "",
            "## Risk-Adjusted Performance",
            f"- Sharpe Ratio: {risk_adjusted_metrics.get('sharpe', 'N/A')}",
            f"- Sortino Ratio: {risk_adjusted_metrics.get('sortino', 'N/A')}",
            f"- Max Drawdown: {risk_adjusted_metrics.get('max_drawdown', 'N/A')}%",
        ])

    report_content = "\n".join(report_lines)

    os.makedirs("output", exist_ok=True)
    report_file = f"output/backtest_report_{datetime.now().strftime('%Y%m%d')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_content)

    print(f"\n📝 Report saved to: {report_file}")
    print("\n" + "=" * 60)
    print("  BACKTEST COMPLETE")
    print("=" * 60)


if __name__ == '__main__':
    main()
