"""
Asset Tracker - Commodity price tracking via vnstock_data.

Fetches VN gold (SJC), oil (Brent), steel (HRC) prices and stores
in SQLite via AssetStore. Derives macro signals for portfolio context.
"""

import os
import sys
import importlib.util
from datetime import datetime
from typing import Dict, Optional

# Load vnstock-data-provider (kebab-case module)
_provider_module = None
try:
    _spec = importlib.util.spec_from_file_location(
        "vnstock_data_provider",
        os.path.join(os.path.dirname(__file__), "vnstock-data-provider.py"),
    )
    if _spec and _spec.loader:
        _provider_module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_provider_module)
except Exception as e:
    print(f"[AssetTracker] vnstock-data-provider load failed: {e}")

# Asset config: maps ticker to provider key + display unit
TRACKED_ASSETS = {
    "GOLD_VN": {"key": "gold_vn", "unit": "VND/luong"},
    "OIL_BRENT": {"key": "oil_brent", "unit": "USD/bbl"},
    "STEEL_HRC": {"key": "steel_hrc", "unit": "USD/ton"},
}


class AssetTracker:
    """
    Fetches commodity prices via VnstockDataProvider,
    stores in SQLite, and derives macro signals.

    Usage:
        tracker = AssetTracker()
        new_count = tracker.fetch_and_store()
        summary = tracker.get_asset_summary()
        signal = tracker.get_macro_signal()
    """

    def __init__(self):
        self._store = None
        self._cached_assets: Optional[Dict] = None
        self._init_store()

    def _init_store(self):
        try:
            sys.path.insert(0, os.path.dirname(__file__))
            from database.asset_store import AssetStore
            self._store = AssetStore()
        except Exception as e:
            print(f"[AssetTracker] Store init failed: {e}")

    def fetch_and_store(self) -> int:
        """Fetch commodity prices and store in DB. Returns new entry count."""
        try:
            if self._store and not self._store.is_stale("GOLD_VN"):
                print("[AssetTracker] Data fresh, skipping fetch")
                return 0

            assets = self._fetch_all_assets()
            if not assets:
                return 0

            today = datetime.now().strftime("%Y-%m-%d")
            count = 0
            for ticker, data in assets.items():
                record = {
                    "date": today,
                    "ticker": ticker,
                    "price": data.get("price", 0),
                    "daily_change_pct": data.get("daily_change_pct", 0),
                    "weekly_change_pct": data.get("weekly_change_pct", 0),
                    "source": "vnstock_data",
                }
                if self._store:
                    if self._store.insert_price(record):
                        count += 1
                else:
                    count += 1

            if self._store:
                self._store.purge_old(days=365)
            return count
        except Exception as e:
            print(f"[AssetTracker] fetch_and_store error: {e}")
            return 0

    def _fetch_all_assets(self) -> Dict:
        """Fetch all tracked assets via VnstockDataProvider. Cached per session."""
        if self._cached_assets is not None:
            return self._cached_assets

        if not _provider_module:
            return {}

        provider = _provider_module.VnstockDataProvider()
        commodities = provider.get_commodity_prices()
        if not commodities:
            return {}

        assets = {}
        for name, config in TRACKED_ASSETS.items():
            data = commodities.get(config["key"])
            if data:
                assets[name] = {**data, "unit": config["unit"]}

        if assets:
            self._cached_assets = assets
        return assets

    def get_asset_summary(self) -> Dict:
        """Get current prices. Returns: {"status": "ok"|"unavailable", "assets": {...}}"""
        try:
            assets = self._fetch_all_assets()
            if not assets:
                return {"status": "unavailable", "assets": {}}
            return {"status": "ok", "assets": assets}
        except Exception as e:
            print(f"[AssetTracker] get_asset_summary error: {e}")
            return {"status": "unavailable", "assets": {}}

    def get_macro_signal(self) -> Dict:
        """
        Derive macro signal from commodity movements.

        - Gold VN rising >2%/wk = risk-off (negative for equities)
        - Oil moderate rise 0-3% = growth, spike >5% = inflationary
        - Steel rising >3% = industrial demand (positive for VNMAT)
        """
        try:
            summary = self.get_asset_summary()
            if summary.get("status") != "ok":
                return {"signal": "neutral", "score": 0.0, "details": {}}

            assets = summary["assets"]
            gold = assets.get("GOLD_VN", {})
            oil = assets.get("OIL_BRENT", {})
            steel = assets.get("STEEL_HRC", {})

            gold_wk = gold.get("weekly_change_pct", 0)
            oil_wk = oil.get("weekly_change_pct", 0)
            steel_wk = steel.get("weekly_change_pct", 0)

            score = 0.0

            # Gold: rising = risk-off (bad for stocks)
            if gold_wk > 2:
                score -= 2.0
            elif gold_wk > 1:
                score -= 1.0
            elif gold_wk < -1:
                score += 1.0

            # Oil: moderate rise = growth; spike or crash = headwind
            if 0 < oil_wk <= 3:
                score += 1.0
            elif oil_wk > 5:
                score -= 1.5
            elif oil_wk < -3:
                score -= 1.0

            # Steel: rising = industrial demand
            if steel_wk > 3:
                score += 0.5
            elif steel_wk < -3:
                score -= 0.5

            score = max(-5.0, min(5.0, score))

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
                    "gold_weekly_pct": gold_wk,
                    "oil_weekly_pct": oil_wk,
                    "steel_weekly_pct": steel_wk,
                    "gold_price": gold.get("price"),
                    "oil_price": oil.get("price"),
                    "steel_price": steel.get("price"),
                },
            }
        except Exception as e:
            print(f"[AssetTracker] get_macro_signal error: {e}")
            return {"signal": "neutral", "score": 0.0, "details": {}}


# ── CLI entry point ──────────────────────────────────────────────────
if __name__ == "__main__":
    tracker = AssetTracker()
    print("Fetching commodity prices (vnstock_data)...")
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
    for k, v in signal["details"].items():
        print(f"  {k}: {v}")
