"""
Asset Tracker - Gold, Silver, Oil, and USD/VND price tracking.

Fetches commodity prices from TradingEconomics free API and stores
in SQLite via AssetStore. Derives macro signals for portfolio context.
"""

import os
import sys
import requests
from datetime import datetime
from typing import Dict, List, Optional

# TradingEconomics free API (public guest credentials)
TE_URL = "https://api.tradingeconomics.com/markets/commodities"
TE_PARAMS = {"c": "guest:guest"}

# Tracked assets and their TradingEconomics name prefixes
TRACKED_ASSETS = {
    "GOLD": {"te_name": "Gold", "unit": "USD/oz"},
    "SILVER": {"te_name": "Silver", "unit": "USD/oz"},
    "OIL": {"te_name": "Brent", "unit": "USD/bbl"},
}


class AssetTracker:
    """
    Fetches commodity prices (gold, silver, oil) from TradingEconomics,
    stores in SQLite, and derives macro signals for portfolio risk context.

    Usage:
        tracker = AssetTracker()
        new_count = tracker.fetch_and_store()
        summary = tracker.get_asset_summary()
        signal = tracker.get_macro_signal()
    """

    def __init__(self):
        self._store = None
        self._cached_commodities = None  # Cache API response within session
        self._init_store()

    def _init_store(self):
        """Initialize AssetStore with graceful failure."""
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from database.asset_store import AssetStore
            self._store = AssetStore()
        except Exception as e:
            print(f"[AssetTracker] Store init failed: {e}")

    def fetch_and_store(self) -> int:
        """
        Fetch current commodity prices and store in DB.
        Skips if data is fresh (same-day record already exists).
        Returns count of new entries inserted.
        """
        try:
            # Skip if data already fresh for first tracked asset
            if self._store and not self._store.is_stale("GOLD"):
                print("[AssetTracker] Data fresh, skipping fetch")
                return 0

            commodities = self._fetch_commodities()
            if not commodities:
                return 0

            today = datetime.now().strftime("%Y-%m-%d")
            count = 0

            for ticker, config in TRACKED_ASSETS.items():
                match = self._find_commodity(commodities, config["te_name"])
                if match:
                    record = {
                        "date": today,
                        "ticker": ticker,
                        "price": match.get("Last", 0),
                        "daily_change_pct": match.get("DailyPercentualChange", 0),
                        "weekly_change_pct": match.get("WeeklyPercentualChange", 0),
                        "source": "tradingeconomics",
                    }
                    if self._store:
                        if self._store.insert_price(record):
                            count += 1
                    else:
                        count += 1  # Count even without DB (API success)

            # Purge old data to keep DB lean
            if self._store:
                self._store.purge_old(days=365)

            return count
        except Exception as e:
            print(f"[AssetTracker] fetch_and_store error: {e}")
            return 0

    def _fetch_commodities(self) -> Optional[List[Dict]]:
        """Fetch commodity data from TradingEconomics API. Cached per session."""
        if self._cached_commodities is not None:
            return self._cached_commodities
        try:
            r = requests.get(
                TE_URL,
                params=TE_PARAMS,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            if r.status_code == 200:
                self._cached_commodities = r.json()
                return self._cached_commodities
            print(f"[AssetTracker] API returned status {r.status_code}")
            return None
        except Exception as e:
            print(f"[AssetTracker] API error: {e}")
            return None

    def _find_commodity(self, data: list, name: str) -> Optional[Dict]:
        """Find a commodity entry by name prefix (case-insensitive)."""
        for item in data:
            if item.get("Name", "").lower().startswith(name.lower()):
                return item
        return None

    def get_asset_summary(self) -> Dict:
        """
        Get current prices and change percentages for all tracked assets.
        Returns: {"status": "ok"|"unavailable", "assets": {ticker: {...}}}
        """
        try:
            commodities = self._fetch_commodities()
            if not commodities:
                return {"status": "unavailable", "assets": {}}

            assets = {}
            for ticker, config in TRACKED_ASSETS.items():
                match = self._find_commodity(commodities, config["te_name"])
                if match:
                    assets[ticker] = {
                        "price": match.get("Last"),
                        "unit": config["unit"],
                        "daily_change_pct": round(float(match.get("DailyPercentualChange", 0)), 2),
                        "weekly_change_pct": round(float(match.get("WeeklyPercentualChange", 0)), 2),
                        "monthly_change_pct": round(float(match.get("MonthlyPercentualChange", 0)), 2),
                        "direction": "up" if match.get("WeeklyPercentualChange", 0) > 0 else "down",
                    }

            return {"status": "ok", "assets": assets}
        except Exception as e:
            print(f"[AssetTracker] get_asset_summary error: {e}")
            return {"status": "unavailable", "assets": {}}

    def get_macro_signal(self) -> Dict:
        """
        Derive macro signal from commodity price movements.

        Signal logic:
        - Gold rising strongly (>2%/wk) = risk-off sentiment, negative for stocks
        - Gold falling (<-1%/wk) = risk-on, positive for stocks
        - Oil rising moderately (0-3%/wk) = growth signal, positive
        - Oil spiking (>5%/wk) = inflationary headwind, negative
        - Oil crashing (<-3%/wk) = demand concerns, negative

        Returns:
            {"signal": "risk-on"|"risk-off"|"neutral", "score": float [-5,5], "details": dict}
        """
        try:
            summary = self.get_asset_summary()
            if summary.get("status") != "ok":
                return {"signal": "neutral", "score": 0.0, "details": {}}

            assets = summary["assets"]
            gold = assets.get("GOLD", {})
            oil = assets.get("OIL", {})

            gold_weekly = gold.get("weekly_change_pct", 0)
            oil_weekly = oil.get("weekly_change_pct", 0)

            score = 0.0

            # Gold sentiment: rising gold = risk-off (bad for equities)
            if gold_weekly > 2:
                score -= 2.0
            elif gold_weekly > 1:
                score -= 1.0
            elif gold_weekly < -1:
                score += 1.0  # Falling gold = risk-on

            # Oil: moderate rise = growth; spike or crash = headwind
            if 0 < oil_weekly <= 3:
                score += 1.0
            elif oil_weekly > 5:
                score -= 1.5  # Oil spiking = inflationary headwind
            elif oil_weekly < -3:
                score -= 1.0  # Oil crashing = demand concerns

            # Clamp score to [-5, 5]
            score = max(-5.0, min(5.0, score))

            # Determine signal label
            if score >= 1.5:
                signal = "risk-on"
            elif score <= -1.5:
                signal = "risk-off"
            else:
                signal = "neutral"

            return {
                "signal": signal,
                "score": round(score, 1),
                "details": {
                    "gold_weekly_pct": gold_weekly,
                    "oil_weekly_pct": oil_weekly,
                    "gold_price": gold.get("price"),
                    "oil_price": oil.get("price"),
                },
            }
        except Exception as e:
            print(f"[AssetTracker] get_macro_signal error: {e}")
            return {"signal": "neutral", "score": 0.0, "details": {}}


# ── CLI entry point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    tracker = AssetTracker()
    print("Fetching commodity prices...")
    new_count = tracker.fetch_and_store()
    print(f"New entries stored: {new_count}")

    summary = tracker.get_asset_summary()
    if summary["status"] == "ok":
        print("\nAsset Summary:")
        for ticker, data in summary["assets"].items():
            print(
                f"  {ticker}: {data['price']} {data['unit']} | "
                f"Daily: {data['daily_change_pct']:+.2f}% | "
                f"Weekly: {data['weekly_change_pct']:+.2f}%"
            )

    signal = tracker.get_macro_signal()
    print(f"\nMacro Signal: {signal['signal']} (score={signal['score']})")
    print(f"  Gold weekly: {signal['details'].get('gold_weekly_pct', 'N/A')}%")
    print(f"  Oil weekly:  {signal['details'].get('oil_weekly_pct', 'N/A')}%")
