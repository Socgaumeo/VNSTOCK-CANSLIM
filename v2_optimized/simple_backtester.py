"""Simple backtester for CANSLIM signal validation."""
from dataclasses import dataclass, field
from typing import List
import sys, os, math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

@dataclass
class TradeResult:
    symbol: str
    signal: str
    pattern_type: str
    entry_date: str
    entry_price: float
    exit_date: str = ""
    exit_price: float = 0.0
    exit_reason: str = ""
    return_pct: float = 0.0
    hold_days: int = 0
    max_gain: float = 0.0
    max_drawdown: float = 0.0
    score_total: float = 0.0

@dataclass
class BacktestResult:
    strategy_name: str = ""
    period: str = ""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_return: float = 0.0
    avg_winner: float = 0.0
    avg_loser: float = 0.0
    total_return: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    trades: List[TradeResult] = field(default_factory=list)

class SimpleBacktester:
    def __init__(self):
        try:
            from database import SignalStore, PriceStore
            self.signal_store = SignalStore()
            self.price_store = PriceStore()
        except ImportError:
            self.signal_store = None
            self.price_store = None

    def _get_signals(self, days_back, signal_filter):
        conditions = [f"date >= date('now', '-{days_back} days')"]
        params = []
        if signal_filter:
            conditions.append("signal = ?")
            params.append(signal_filter)
        return self.signal_store.db.fetchall(f"""
            SELECT date, symbol, signal, score_total, pattern_type, buy_point, stop_loss, target
            FROM signals_history WHERE {" AND ".join(conditions)} ORDER BY date
        """, params)

    def backtest_signals(self, days_back=180, signal_filter=None, hold_days=20):
        if not self.signal_store or not self.price_store:
            return BacktestResult(strategy_name="No DB")

        rows = self._get_signals(days_back, signal_filter)
        strategy_name = f"Hold {hold_days}d" + (f" ({signal_filter})" if signal_filter else "")
        if not rows:
            return BacktestResult(strategy_name=strategy_name, period=f"Last {days_back} days")

        trades = []
        for sig_date, symbol, signal, score, pattern, buy_point, _, _ in rows:
            if not buy_point or buy_point <= 0:
                continue
            prices_df = self.price_store.get_prices(symbol, limit=500)
            if prices_df is None or prices_df.empty:
                continue
            try:
                sig_date_str = sig_date if isinstance(sig_date, str) else sig_date.strftime('%Y-%m-%d')
            except:
                continue
            future = prices_df.sort_index()[prices_df.index >= sig_date_str]
            if len(future) < 2:
                continue

            max_gain, max_dd, exit_price, exit_date = 0.0, 0.0, buy_point, sig_date_str
            for i in range(1, min(hold_days + 1, len(future))):
                price = float(future.iloc[i]['close'])
                ret = (price - buy_point) / buy_point * 100
                max_gain, max_dd = max(max_gain, ret), min(max_dd, ret)
                exit_price, exit_date = price, str(future.index[i])[:10]

            trades.append(TradeResult(
                symbol=symbol, signal=signal, pattern_type=pattern or "", entry_date=sig_date_str,
                entry_price=buy_point, exit_date=exit_date, exit_price=exit_price, exit_reason="HOLD_EXPIRED",
                return_pct=(exit_price - buy_point) / buy_point * 100, hold_days=hold_days,
                max_gain=max_gain, max_drawdown=max_dd, score_total=score or 0
            ))
        return self._aggregate(trades, strategy_name, f"Last {days_back} days")

    def backtest_with_stops(self, days_back=180, signal_filter=None, stop_pct=0.07, target_pct=0.20, max_hold=60):
        if not self.signal_store or not self.price_store:
            return BacktestResult(strategy_name="No DB")

        rows = self._get_signals(days_back, signal_filter)
        strategy_name = f"Stop {stop_pct*100:.0f}%/Target {target_pct*100:.0f}%"
        if not rows:
            return BacktestResult(strategy_name=strategy_name, period=f"Last {days_back} days")

        trades = []
        for sig_date, symbol, signal, score, pattern, buy_point, stop_db, target_db in rows:
            if not buy_point or buy_point <= 0:
                continue
            prices_df = self.price_store.get_prices(symbol, limit=500)
            if prices_df is None or prices_df.empty:
                continue
            try:
                sig_date_str = sig_date if isinstance(sig_date, str) else sig_date.strftime('%Y-%m-%d')
            except:
                continue
            future = prices_df.sort_index()[prices_df.index >= sig_date_str]
            if len(future) < 2:
                continue

            stop_price = stop_db if stop_db and stop_db > 0 else buy_point * (1 - stop_pct)
            target_price = target_db if target_db and target_db > 0 else buy_point * (1 + target_pct)
            max_gain, max_dd = 0.0, 0.0
            exit_price, exit_date, exit_reason, actual_hold = buy_point, sig_date_str, "HOLD_EXPIRED", 0

            for i in range(1, min(max_hold + 1, len(future))):
                close = float(future.iloc[i]['close'])
                low = float(future.iloc[i].get('low', close))
                high = float(future.iloc[i].get('high', close))
                max_gain = max(max_gain, (close - buy_point) / buy_point * 100)
                max_dd = min(max_dd, (low - buy_point) / buy_point * 100)
                actual_hold, exit_date = i, str(future.index[i])[:10]
                if low <= stop_price:
                    exit_price, exit_reason = stop_price, "STOP_LOSS"
                    break
                if high >= target_price:
                    exit_price, exit_reason = target_price, "TARGET"
                    break
                exit_price = close

            trades.append(TradeResult(
                symbol=symbol, signal=signal, pattern_type=pattern or "", entry_date=sig_date_str,
                entry_price=buy_point, exit_date=exit_date, exit_price=exit_price, exit_reason=exit_reason,
                return_pct=(exit_price - buy_point) / buy_point * 100, hold_days=actual_hold,
                max_gain=max_gain, max_drawdown=max_dd, score_total=score or 0
            ))
        return self._aggregate(trades, strategy_name, f"Last {days_back} days")

    def compare_strategies(self, days_back=180):
        results = [
            self.backtest_signals(days_back, hold_days=20),
            self.backtest_signals(days_back, signal_filter='STRONG_BUY', hold_days=20),
            self.backtest_signals(days_back, signal_filter='BUY', hold_days=20),
            self.backtest_with_stops(days_back, stop_pct=0.07, target_pct=0.20),
            self.backtest_with_stops(days_back, signal_filter='STRONG_BUY', stop_pct=0.07, target_pct=0.20),
        ]
        lines = [f"# 🔬 BACKTEST COMPARISON ({days_back} days)", "",
                 "| Strategy | Trades | Win Rate | Avg Return | Avg Win | Avg Loss | PF | Max DD |",
                 "|----------|--------|----------|------------|---------|----------|-----|--------|"]
        for r in results:
            if r.total_trades > 0:
                lines.append(f"| {r.strategy_name} | {r.total_trades} | {r.win_rate:.1f}% | "
                             f"{r.avg_return:+.1f}% | {r.avg_winner:+.1f}% | {r.avg_loser:+.1f}% | "
                             f"{r.profit_factor:.2f} | {r.max_drawdown:.1f}% |")

        all_trades = []
        for r in results:
            all_trades.extend(r.trades)
        if all_trades:
            seen, unique_trades = set(), []
            for t in all_trades:
                key = f"{t.symbol}_{t.entry_date}"
                if key not in seen:
                    seen.add(key)
                    unique_trades.append(t)
            best = sorted(unique_trades, key=lambda t: t.return_pct, reverse=True)[:5]
            worst = sorted(unique_trades, key=lambda t: t.return_pct)[:5]
            lines.extend(["\n## 🏆 Top 5 Winners",
                          "| Symbol | Signal | Entry Date | Return | Max Gain | Pattern |",
                          "|--------|--------|------------|--------|----------|---------|"])
            for t in best:
                lines.append(f"| {t.symbol} | {t.signal} | {t.entry_date} | {t.return_pct:+.1f}% | {t.max_gain:+.1f}% | {t.pattern_type} |")
            lines.extend(["\n## 💀 Top 5 Losers",
                          "| Symbol | Signal | Entry Date | Return | Max DD | Pattern |",
                          "|--------|--------|------------|--------|--------|---------|"])
            for t in worst:
                lines.append(f"| {t.symbol} | {t.signal} | {t.entry_date} | {t.return_pct:+.1f}% | {t.max_drawdown:+.1f}% | {t.pattern_type} |")
        return "\n".join(lines)

    def _aggregate(self, trades, strategy_name, period):
        result = BacktestResult(strategy_name=strategy_name, period=period, total_trades=len(trades), trades=trades)
        if not trades:
            return result
        returns = [t.return_pct for t in trades]
        winners = [r for r in returns if r > 0]
        losers = [r for r in returns if r <= 0]
        result.winning_trades, result.losing_trades = len(winners), len(losers)
        result.win_rate = len(winners) / len(returns) * 100
        result.avg_return, result.total_return = sum(returns) / len(returns), sum(returns)
        result.avg_winner = sum(winners) / len(winners) if winners else 0
        result.avg_loser = sum(losers) / len(losers) if losers else 0
        total_wins, total_losses = sum(winners) if winners else 0, abs(sum(losers)) if losers else 0
        result.profit_factor = total_wins / total_losses if total_losses > 0 else (float('inf') if total_wins > 0 else 0)
        cumulative, peak, max_dd = 0, 0, 0
        for r in returns:
            cumulative += r
            peak = max(peak, cumulative)
            max_dd = min(max_dd, cumulative - peak)
        result.max_drawdown = max_dd
        if len(returns) > 1:
            avg = sum(returns) / len(returns)
            variance = sum((r - avg) ** 2 for r in returns) / (len(returns) - 1)
            std = math.sqrt(variance) if variance > 0 else 0
            if std > 0:
                result.sharpe_ratio = (avg / std) * math.sqrt(250 / 20)
        return result
