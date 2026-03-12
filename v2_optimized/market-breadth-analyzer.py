#!/usr/bin/env python3
"""
Market Breadth Analyzer - A/D ratio, breadth thrust, sector heatmap, sparklines.

Used by Module1 to expand market breadth analysis beyond simple advance/decline counts.
"""

from typing import Dict, List, Optional


# Unicode block characters for sparklines (8 levels)
SPARK_CHARS = "▁▂▃▄▅▆▇█"


class MarketBreadthAnalyzer:
    """Compute advanced breadth metrics and generate visual indicators."""

    def calculate_breadth_metrics(
        self,
        advances: int,
        declines: int,
        unchanged: int,
        ceiling: int,
        floor: int,
    ) -> Dict:
        """Calculate advanced breadth metrics from raw counts.

        Returns dict with: ad_ratio, breadth_thrust, net_breadth_score,
        breadth_signal, new_highs_proxy, new_lows_proxy.
        """
        total = advances + declines + unchanged
        if total == 0:
            return self._empty_metrics()

        ad_ratio = advances / max(declines, 1)
        breadth_thrust = advances / max(advances + declines, 1)
        net_breadth_score = (advances - declines) / total * 100

        # Interpret signals
        if ad_ratio >= 2.0:
            breadth_signal = "VERY_STRONG"
        elif ad_ratio >= 1.5:
            breadth_signal = "STRONG"
        elif ad_ratio >= 1.0:
            breadth_signal = "NEUTRAL_POSITIVE"
        elif ad_ratio >= 0.7:
            breadth_signal = "WEAK"
        else:
            breadth_signal = "VERY_WEAK"

        return {
            "ad_ratio": round(ad_ratio, 2),
            "breadth_thrust": round(breadth_thrust, 3),
            "net_breadth_score": round(net_breadth_score, 1),
            "breadth_signal": breadth_signal,
            "is_thrust_bullish": breadth_thrust > 0.615,
            "new_highs_proxy": ceiling,
            "new_lows_proxy": floor,
            "total_stocks": total,
        }

    def generate_sector_heatmap(self, sectors: list) -> str:
        """Generate Markdown sector heatmap table.

        Args:
            sectors: List of dicts with keys: code, name, change_1d, phase (optional)
        """
        if not sectors:
            return ""

        lines = [
            "| Sector | Name | 1D Change | Signal |",
            "|--------|------|-----------|--------|",
        ]
        for s in sectors:
            code = s.get("code", "")
            name = s.get("name", code)
            change = s.get("change_1d", 0)
            phase = s.get("phase", "")

            indicator = self._change_indicator(change)
            lines.append(f"| {code} | {name} | {indicator} {change:+.2f}% | {phase} |")

        return "\n".join(lines)

    def generate_sparkline(self, values: List[float]) -> str:
        """Generate Unicode sparkline from numeric values.

        Args:
            values: List of numeric values (e.g., last 10 A/D ratios)
        Returns:
            Unicode sparkline string like "▁▂▃▅▇▆▄▃▂▁"
        """
        if not values:
            return ""
        if len(values) == 1:
            return SPARK_CHARS[4]

        vmin = min(values)
        vmax = max(values)
        spread = vmax - vmin
        if spread == 0:
            return SPARK_CHARS[4] * len(values)

        chars = []
        for v in values:
            idx = int((v - vmin) / spread * (len(SPARK_CHARS) - 1))
            idx = max(0, min(len(SPARK_CHARS) - 1, idx))
            chars.append(SPARK_CHARS[idx])
        return "".join(chars)

    def format_breadth_report_section(self, metrics: Dict) -> str:
        """Generate Markdown section for breadth analysis."""
        if not metrics:
            return ""

        signal = metrics.get("breadth_signal", "N/A")
        ad = metrics.get("ad_ratio", 0)
        thrust = metrics.get("breadth_thrust", 0)
        net = metrics.get("net_breadth_score", 0)
        highs = metrics.get("new_highs_proxy", 0)
        lows = metrics.get("new_lows_proxy", 0)
        total = metrics.get("total_stocks", 0)

        thrust_note = " 🚀 **Breadth Thrust!**" if metrics.get("is_thrust_bullish") else ""

        lines = [
            "### 📊 Market Breadth",
            f"- **A/D Ratio**: {ad:.2f} ({signal})",
            f"- **Breadth Thrust**: {thrust:.3f}{thrust_note}",
            f"- **Net Breadth Score**: {net:+.1f}%",
            f"- **Ceiling Hits**: {highs} | **Floor Hits**: {lows}",
            f"- **Total Stocks**: {total}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _change_indicator(change: float) -> str:
        if change >= 2.0:
            return "🟢🟢"
        elif change >= 0.5:
            return "🟢"
        elif change > -0.5:
            return "🟡"
        elif change > -2.0:
            return "🔴"
        else:
            return "🔴🔴"

    @staticmethod
    def _empty_metrics() -> Dict:
        return {
            "ad_ratio": 0,
            "breadth_thrust": 0,
            "net_breadth_score": 0,
            "breadth_signal": "N/A",
            "is_thrust_bullish": False,
            "new_highs_proxy": 0,
            "new_lows_proxy": 0,
            "total_stocks": 0,
        }
