"""
Asset Tracker - Gold, Silver, Oil price tracking via Yahoo Finance.

Fetches commodity prices from Yahoo Finance API and stores
in SQLite via AssetStore. Derives macro signals for portfolio context.
"""

import os
import sys
import requests
from datetime import datetime
from typing import Dict, List, Optional

# Yahoo Finance chart API for commodity futures
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0"}

# Tracked assets and their Yahoo Finance ticker symbols
TRACKED_ASSETS = {
    "GOLD": {"yahoo_ticker": "GC=F", "unit": "USD/oz"},
    "SILVER": {"yahoo_ticker": "SI=F", "unit": "USD/oz"},
    "OIL": {"yahoo_ticker": "BZ=F", "unit": "USD/bbl"},
}


class AssetTracker:
    """
    Fetches commodity prices (gold, silver, oil) from Yahoo Finance,
    stores in SQLite, and derives macro signals for portfolio risk context.

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
            if self._store and not self._store.is_stale("GOLD"):
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
                    "source": "yahoo_finance",
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

    def _fetch_yahoo_chart(self, ticker: str) -> Optional[Dict]:
        """Fetch price data from Yahoo Finance chart API."""
        try:
            url = YAHOO_CHART_URL.format(ticker=ticker)
            r = requests.get(
                url,
                params={"interval": "1d", "range": "1mo"},
                timeout=10,
                headers=YAHOO_HEADERS,
            )
            if r.status_code != 200:
                return None

            data = r.json()
            result = data.get("chart", {}).get("result", [{}])[0]
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            closes = [c for c in closes if c is not None]

            if len(closes) < 2:
                return None

            current = closes[-1]
            prev_day = closes[-2]
            prev_week = closes[-6] if len(closes) >= 6 else closes[0]
            prev_month = closes[0]

            return {
                "price": round(current, 2),
                "daily_change_pct": round(((current / prev_day) - 1) * 100, 2) if prev_day else 0,
                "weekly_change_pct": round(((current / prev_week) - 1) * 100, 2) if prev_week else 0,
                "monthly_change_pct": round(((current / prev_month) - 1) * 100, 2) if prev_month else 0,
            }
        except Exception as e:
            print(f"[AssetTracker] Yahoo chart error for {ticker}: {e}")
            return None

    def _fetch_all_assets(self) -> Dict:
        """Fetch all tracked assets. Cached per session."""
        if self._cached_assets is not None:
            return self._cached_assets

        assets = {}
        for name, config in TRACKED_ASSETS.items():
            result = self._fetch_yahoo_chart(config["yahoo_ticker"])
            if result:
                result["unit"] = config["unit"]
                result["direction"] = "up" if result.get("weekly_change_pct", 0) > 0 else "down"
                assets[name] = result

        if assets:
            self._cached_assets = assets
        return assets

    def get_asset_summary(self) -> Dict:
        """
        Get current prices and change percentages for all tracked assets.
        Returns: {"status": "ok"|"unavailable", "assets": {ticker: {...}}}
        """
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
                score += 1.0

            # Oil: moderate rise = growth; spike or crash = headwind
            if 0 < oil_weekly <= 3:
                score += 1.0
            elif oil_weekly > 5:
                score -= 1.5
            elif oil_weekly < -3:
                score -= 1.0

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
