"""Performance tracking for CANSLIM signals."""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

@dataclass
class PerformanceMetrics:
    total_signals: int = 0
    win_rate_5d: float = 0.0
    win_rate_20d: float = 0.0
    win_rate_60d: float = 0.0
    avg_return_5d: float = 0.0
    avg_return_20d: float = 0.0
    avg_return_60d: float = 0.0
    avg_winner: float = 0.0
    avg_loser: float = 0.0
    profit_factor: float = 0.0
    best_pick: str = ""
    worst_pick: str = ""
    best_return: float = 0.0
    worst_return: float = 0.0

class PerformanceTracker:
    def __init__(self):
        try:
            from database import SignalStore, PriceStore
            self.signal_store = SignalStore()
            self.price_store = PriceStore()
        except ImportError:
            self.signal_store = None
            self.price_store = None

    def record_signal(self, symbol: str, signal: str, score_total: float,
                      score_fundamental: float = 0, score_technical: float = 0,
                      score_pattern: float = 0, rs_rating: float = 0,
                      pattern_type: str = "", buy_point: float = 0,
                      stop_loss: float = 0, target: float = 0) -> Optional[int]:
        if not self.signal_store:
            return None
        return self.signal_store.record_signal(
            symbol=symbol, signal=signal, score_total=score_total,
            score_fundamental=score_fundamental, score_technical=score_technical,
            score_pattern=score_pattern, rs_rating=rs_rating,
            pattern_type=pattern_type, buy_point=buy_point,
            stop_loss=stop_loss, target=target
        )

    def update_returns(self) -> int:
        if not self.signal_store or not self.price_store:
            return 0
        db = self.signal_store.db
        rows = db.fetchall("""
            SELECT id, date, symbol, buy_point,
                   actual_return_5d, actual_return_20d, actual_return_60d
            FROM signals_history
            WHERE actual_return_5d IS NULL OR actual_return_20d IS NULL OR actual_return_60d IS NULL
            ORDER BY date DESC LIMIT 500
        """)
        updated, today = 0, datetime.now()
        for sig_id, sig_date, symbol, buy_point, r5d, r20d, r60d in rows:
            if not buy_point or buy_point <= 0:
                continue
            try:
                sig_dt = datetime.strptime(sig_date, '%Y-%m-%d') if isinstance(sig_date, str) else sig_date
            except (ValueError, TypeError):
                continue
            days_elapsed = (today - sig_dt).days
            prices_df = self.price_store.get_prices(symbol, limit=250)
            if prices_df is None or prices_df.empty:
                continue
            future = prices_df.sort_index()[prices_df.index >= sig_dt.strftime('%Y-%m-%d')]
            if future.empty:
                continue
            if r5d is None and days_elapsed >= 8 and len(future) >= 6:
                r5d = (float(future.iloc[min(5, len(future) - 1)]['close']) - buy_point) / buy_point * 100
            if r20d is None and days_elapsed >= 30 and len(future) >= 21:
                r20d = (float(future.iloc[min(20, len(future) - 1)]['close']) - buy_point) / buy_point * 100
            if r60d is None and days_elapsed >= 90 and len(future) >= 61:
                r60d = (float(future.iloc[min(60, len(future) - 1)]['close']) - buy_point) / buy_point * 100
            if any(x is not None for x in [r5d, r20d, r60d]):
                self.signal_store.update_returns(sig_id, r5d, r20d, r60d)
                updated += 1
        return updated

    def calc_metrics(self, days=90, signal_filter=None, pattern_filter=None):
        if not self.signal_store:
            return PerformanceMetrics()
        db = self.signal_store.db
        conditions, params = ["date >= date('now', ?)"], [f'-{days} days']
        if signal_filter:
            conditions.append("signal = ?")
            params.append(signal_filter)
        if pattern_filter:
            conditions.append("pattern_type = ?")
            params.append(pattern_filter)
        rows = db.fetchall(f"""
            SELECT symbol, signal, score_total, pattern_type,
                   actual_return_5d, actual_return_20d, actual_return_60d
            FROM signals_history WHERE {" AND ".join(conditions)} ORDER BY date DESC
        """, params)
        if not rows:
            return PerformanceMetrics()
        metrics = PerformanceMetrics(total_signals=len(rows))
        returns_5d = [r[4] for r in rows if r[4] is not None]
        returns_20d = [r[5] for r in rows if r[5] is not None]
        returns_60d = [r[6] for r in rows if r[6] is not None]
        if returns_5d:
            metrics.win_rate_5d = len([r for r in returns_5d if r > 0]) / len(returns_5d) * 100
            metrics.avg_return_5d = sum(returns_5d) / len(returns_5d)
        if returns_20d:
            winners = [r for r in returns_20d if r > 0]
            losers = [r for r in returns_20d if r <= 0]
            metrics.win_rate_20d = len(winners) / len(returns_20d) * 100
            metrics.avg_return_20d = sum(returns_20d) / len(returns_20d)
            metrics.avg_winner = sum(winners) / len(winners) if winners else 0
            metrics.avg_loser = sum(losers) / len(losers) if losers else 0
            total_wins, total_losses = sum(winners) if winners else 0, abs(sum(losers)) if losers else 0
            metrics.profit_factor = total_wins / total_losses if total_losses > 0 else (float('inf') if total_wins > 0 else 0)
            best_row = max(rows, key=lambda r: r[5] if r[5] is not None else -999)
            worst_row = min(rows, key=lambda r: r[5] if r[5] is not None else 999)
            if best_row[5] is not None:
                metrics.best_pick, metrics.best_return = best_row[0], best_row[5]
            if worst_row[5] is not None:
                metrics.worst_pick, metrics.worst_return = worst_row[0], worst_row[5]
        if returns_60d:
            metrics.win_rate_60d = len([r for r in returns_60d if r > 0]) / len(returns_60d) * 100
            metrics.avg_return_60d = sum(returns_60d) / len(returns_60d)
        return metrics

    def generate_report(self, days=90):
        overall = self.calc_metrics(days)
        lines = [
            f"# 📈 PERFORMANCE TRACKING (Last {days} days)", "",
            "| Metric | Value |", "|--------|-------|",
            f"| Signals issued | {overall.total_signals} |",
            f"| Win rate (5d) | {overall.win_rate_5d:.1f}% |",
            f"| Win rate (20d) | {overall.win_rate_20d:.1f}% |",
            f"| Win rate (60d) | {overall.win_rate_60d:.1f}% |",
            f"| Avg return (20d) | {overall.avg_return_20d:+.1f}% |",
            f"| Avg winner | {overall.avg_winner:+.1f}% |",
            f"| Avg loser | {overall.avg_loser:+.1f}% |",
            f"| Profit factor | {overall.profit_factor:.2f} |",
            f"| Best pick | {overall.best_pick} ({overall.best_return:+.1f}%) |",
            f"| Worst pick | {overall.worst_pick} ({overall.worst_return:+.1f}%) |",
            "\n## By Signal Type",
            "| Type | Count | Win Rate (20d) | Avg Return |",
            "|------|-------|----------------|------------|"
        ]
        for sig_type in ['STRONG_BUY', 'BUY', 'WATCH']:
            m = self.calc_metrics(days, signal_filter=sig_type)
            if m.total_signals > 0:
                lines.append(f"| {sig_type} | {m.total_signals} | {m.win_rate_20d:.1f}% | {m.avg_return_20d:+.1f}% |")
        lines.extend(["\n## By Pattern Type",
                      "| Pattern | Count | Win Rate (20d) | Avg Return |",
                      "|---------|-------|----------------|------------|"])
        if self.signal_store:
            patterns = self.signal_store.db.fetchall("""
                SELECT DISTINCT pattern_type FROM signals_history
                WHERE pattern_type IS NOT NULL AND pattern_type != ''
                AND date >= date('now', ?)
            """, [f'-{days} days'])
            for (pat,) in (patterns or []):
                m = self.calc_metrics(days, pattern_filter=pat)
                if m.total_signals > 0:
                    lines.append(f"| {pat} | {m.total_signals} | {m.win_rate_20d:.1f}% | {m.avg_return_20d:+.1f}% |")
        return "\n".join(lines)
