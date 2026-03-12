"""
Bond Lab - Vietnam government bond yield tracker with health scoring.
Uses TradingEconomics free guest API for VN10Y yield data.
Stores daily snapshots in SQLite to build historical yield history over time.
"""

import os
import sys
import requests
from datetime import datetime
from typing import Dict, Optional

# TradingEconomics free guest API for Vietnam bond yields
TE_BOND_URL = "https://api.tradingeconomics.com/markets/bond"
TE_PARAMS = {"c": "guest:guest", "country": "vietnam"}


class BondLab:
    """
    Vietnam government bond yield tracker.

    Fetches VN10Y yield from TradingEconomics free API and persists daily
    snapshots to SQLite. Computes bond health score for equity market context.

    Usage:
        lab = BondLab()
        lab.fetch_and_store()
        health = lab.get_bond_health_score()
        curve = lab.get_yield_curve()
    """

    def __init__(self):
        self._store = None
        self._cached_te_data = None  # Cache API response within session
        self._init_store()

    def _init_store(self):
        """Init BondStore, fail silently if DB unavailable."""
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from database.bond_store import BondStore
            self._store = BondStore()
        except Exception as e:
            print(f"[BondLab] Store init failed: {e}")

    def fetch_and_store(self) -> int:
        """
        Fetch current VN10Y yield from TradingEconomics, store in DB.
        Returns 1 if new entry inserted, 0 if already exists or error.
        """
        try:
            data = self._fetch_from_te()
            if not data:
                return 0
            today = datetime.now().strftime("%Y-%m-%d")
            record = {
                "date": today,
                "ticker": "VN10Y",
                "yield_pct": data["Last"],
                "daily_change_bps": round(
                    (data["Last"] - data.get("yesterday", data["Last"])) * 100, 1
                ),
                "weekly_change_bps": round(data.get("WeeklyChange", 0) * 100, 1),
                "monthly_change_bps": round(data.get("MonthlyChange", 0) * 100, 1),
            }
            if self._store:
                inserted = self._store.insert_yield(record)
                # Purge records older than 365 days
                if inserted:
                    self._store.purge_old(days=365)
                return 1 if inserted else 0
            return 1
        except Exception as e:
            print(f"[BondLab] fetch_and_store error: {e}")
            return 0

    def _fetch_from_te(self) -> Optional[Dict]:
        """Fetch Vietnam bond data from TradingEconomics guest API. Cached per session."""
        if self._cached_te_data is not None:
            return self._cached_te_data
        try:
            r = requests.get(
                TE_BOND_URL,
                params=TE_PARAMS,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    self._cached_te_data = data[0]
                    return self._cached_te_data
            return None
        except Exception as e:
            print(f"[BondLab] TradingEconomics API error: {e}")
            return None

    def get_yield_curve(self) -> Dict:
        """
        Current yield snapshot (only VN10Y available from free API).
        Returns latest data including multi-period comparisons.
        """
        data = self._fetch_from_te()
        if not data:
            return {"VN10Y": None}
        return {
            "VN10Y": data.get("Last"),
            "yesterday": data.get("yesterday"),
            "last_week": data.get("lastWeek"),
            "last_month": data.get("lastMonth"),
            "last_year": data.get("lastYear"),
        }

    def get_yield_change(self, days: int = 5) -> Dict:
        """
        Get yield changes across periods.
        Uses TradingEconomics data directly (weekly/monthly provided by API).
        """
        data = self._fetch_from_te()
        if not data:
            return {}
        current = data.get("Last", 0)
        yesterday = data.get("yesterday", current)
        weekly_change = data.get("WeeklyChange", 0)
        return {
            "VN10Y": {
                "current": current,
                "daily_change_bps": round((current - yesterday) * 100, 1),
                "weekly_change_bps": round(weekly_change * 100, 1),
                "monthly_change_bps": round(data.get("MonthlyChange", 0) * 100, 1),
                "direction": (
                    "up" if weekly_change > 0
                    else "down" if weekly_change < 0
                    else "flat"
                ),
            }
        }

    def get_bond_health_score(self) -> Dict:
        """
        Compute bond health score in range [-10, +10].

        Positive score = falling yields = supportive for equities.
        Negative score = rising yields = headwind for equities.

        Scoring:
          Weekly component (max +/-5):
            weekly_bps <= -20: +5 | <= -10: +3
            weekly_bps >= 20: -5 | >= 10: -3
          Monthly component (max +/-3):
            monthly_bps <= -50: +3 | <= -20: +1.5
            monthly_bps >= 50: -3 | >= 20: -1.5

        Returns: {score, interpretation, vn10y_yield, weekly_change_bps, monthly_change_bps}
        """
        data = self._fetch_from_te()
        if not data:
            return {"score": 0.0, "interpretation": "Bond data unavailable"}

        score = 0.0
        weekly_bps = round(data.get("WeeklyChange", 0) * 100, 1)
        monthly_bps = round(data.get("MonthlyChange", 0) * 100, 1)

        # Weekly component (max +/-5)
        if weekly_bps <= -20:
            score += 5.0
        elif weekly_bps <= -10:
            score += 3.0
        elif weekly_bps >= 20:
            score -= 5.0
        elif weekly_bps >= 10:
            score -= 3.0

        # Monthly component (max +/-3)
        if monthly_bps <= -50:
            score += 3.0
        elif monthly_bps <= -20:
            score += 1.5
        elif monthly_bps >= 50:
            score -= 3.0
        elif monthly_bps >= 20:
            score -= 1.5

        # Clamp to [-10, +10]
        score = max(-10.0, min(10.0, score))

        # Human-readable interpretation
        if score >= 3:
            interp = "Supportive: falling yields favor equities"
        elif score <= -3:
            interp = "Headwind: rising yields pressure equities"
        else:
            interp = "Neutral: yields stable"

        return {
            "score": round(score, 1),
            "interpretation": interp,
            "vn10y_yield": data.get("Last"),
            "weekly_change_bps": weekly_bps,
            "monthly_change_bps": monthly_bps,
        }


if __name__ == "__main__":
    # Quick smoke test
    lab = BondLab()
    print("Fetching VN10Y yield...")
    stored = lab.fetch_and_store()
    print(f"New record stored: {stored}")
    print("Yield curve:", lab.get_yield_curve())
    print("Yield changes:", lab.get_yield_change())
    print("Bond health:", lab.get_bond_health_score())
