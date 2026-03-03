"""
Research Lab - Bond-stock correlation and Granger causality analysis.
Analyzes the relationship between Vietnam 10Y bond yield changes and equity returns.
Requires 60+ daily observations accumulated in BondStore to run meaningful tests.
"""

import os
import sys
from typing import Dict, Optional


class ResearchLab:
    """
    Analyzes bond yield -> stock return relationship.

    Uses bond yield history accumulated via BondLab in SQLite.
    Requires statsmodels for Granger causality testing.
    Results become meaningful only after 60+ daily data points are collected.

    Usage:
        lab = ResearchLab()
        result = lab.lead_lag_analysis()
        print(result["summary"])
    """

    def __init__(self):
        self._bond_store = None
        self._statsmodels_ok = False
        self._init_deps()

    def _init_deps(self):
        """Initialize dependencies, fail silently if unavailable."""
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from database.bond_store import BondStore
            self._bond_store = BondStore()
        except Exception as e:
            print(f"[ResearchLab] BondStore init failed: {e}")

        try:
            import statsmodels  # noqa: F401
            self._statsmodels_ok = True
        except ImportError:
            print("[ResearchLab] statsmodels not installed. Run: pip3 install statsmodels")

    def granger_test(self, max_lag: int = 10) -> Dict:
        """
        Test if bond yield changes Granger-cause VNINDEX returns.

        Requires 60+ daily observations in bond_store.
        Returns status dict with test results when enough data is available.
        """
        if not self._statsmodels_ok or not self._bond_store:
            return {
                "status": "unavailable",
                "reason": "statsmodels or BondStore not available",
            }

        try:
            import pandas as pd
            from statsmodels.tsa.stattools import grangercausalitytests  # noqa: F401

            # Get bond yield history from our store
            bond_data = self._bond_store.get_recent(days=365)
            if len(bond_data) < 60:
                return {
                    "status": "insufficient_data",
                    "data_points": len(bond_data),
                    "required": 60,
                    "message": (
                        f"Need 60+ data points, have {len(bond_data)}. "
                        "Run pipeline daily to accumulate."
                    ),
                }

            # Build yield change series
            df = pd.DataFrame(bond_data)
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
            df["yield_change"] = df["yield_pct"].diff()
            df = df.dropna(subset=["yield_change"])

            if len(df) < 60:
                return {
                    "status": "insufficient_data",
                    "data_points": len(df),
                    "required": 60,
                }

            # VNINDEX return series needed for actual Granger test
            # TODO: integrate with PriceStore when VNINDEX daily close is stored
            return {
                "status": "ready",
                "data_points": len(df),
                "message": (
                    "Granger test infrastructure ready. "
                    "Needs VNINDEX daily return series integration via PriceStore."
                ),
            }

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def rolling_correlation(self, window: int = 30) -> Dict:
        """
        Rolling correlation between bond yield changes and stock returns.

        Requires window + 10 data points to compute meaningful correlations.
        """
        if not self._bond_store:
            return {"status": "unavailable", "reason": "BondStore not available"}

        bond_data = self._bond_store.get_recent(days=365)
        if len(bond_data) < window + 10:
            return {
                "status": "insufficient_data",
                "data_points": len(bond_data),
                "required": window + 10,
                "message": (
                    f"Need {window + 10}+ data points, have {len(bond_data)}. "
                    "Run pipeline daily to accumulate."
                ),
            }

        return {
            "status": "ready",
            "data_points": len(bond_data),
            "message": (
                "Rolling correlation infrastructure ready. "
                "Needs VNINDEX daily return series integration via PriceStore."
            ),
        }

    def lead_lag_analysis(self) -> Dict:
        """
        Full bond-stock lead/lag analysis combining Granger test and rolling correlation.

        Returns dict with granger, correlation, and human-readable summary.
        """
        granger = self.granger_test()
        correlation = self.rolling_correlation()

        return {
            "granger": granger,
            "correlation": correlation,
            "summary": self._interpret(granger, correlation),
        }

    def _interpret(self, granger: Dict, correlation: Dict) -> str:
        """Generate human-readable interpretation from analysis results."""
        g_status = granger.get("status", "unavailable")
        c_status = correlation.get("status", "unavailable")

        if g_status == "insufficient_data":
            pts = granger.get("data_points", 0)
            return f"Accumulating data ({pts}/60 days). Run pipeline daily to build history."

        if g_status == "unavailable":
            reason = granger.get("reason", "unknown")
            return f"Analysis unavailable: {reason}"

        if g_status == "error":
            return f"Analysis error: {granger.get('message', 'unknown')}"

        if g_status == "ready" and c_status == "ready":
            return (
                "Bond-stock analysis infrastructure ready. "
                "Pending VNINDEX integration for full correlation results."
            )

        return "Analysis pending further data accumulation."


if __name__ == "__main__":
    # Quick smoke test
    lab = ResearchLab()
    print("Running lead-lag analysis...")
    result = lab.lead_lag_analysis()
    print(f"Summary: {result['summary']}")
    print(f"Granger status: {result['granger'].get('status')}")
    print(f"Correlation status: {result['correlation'].get('status')}")
