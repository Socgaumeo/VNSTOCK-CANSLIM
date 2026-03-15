"""
Centralized vnstock_data wrapper with same-day JSON caching.

Provides commodity prices (VN gold, oil, steel), market PE/PB valuation,
top foreign flow, and macro indicators (USD/VND, CPI).
All consumers import from this module instead of vnstock_data directly.
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional

# Optional dependency — graceful degradation
try:
    from vnstock_data import CommodityPrice, Market, TopStock, Macro
    HAS_VNSTOCK_DATA = True
except ImportError:
    HAS_VNSTOCK_DATA = False


def _ohlcv_extract(df, price_col: str = "close") -> dict:
    """Extract price + change % from OHLCV DataFrame."""
    if df is None or df.empty:
        return {}
    latest = df.iloc[-1]
    price = float(latest[price_col])
    daily_chg, weekly_chg = 0.0, 0.0
    if len(df) >= 2:
        prev = float(df.iloc[-2][price_col])
        if prev > 0:
            daily_chg = round(((price / prev) - 1) * 100, 2)
    if len(df) >= 6:
        prev_w = float(df.iloc[-6][price_col])
        if prev_w > 0:
            weekly_chg = round(((price / prev_w) - 1) * 100, 2)
    return {
        "price": round(price, 2),
        "daily_change_pct": daily_chg,
        "weekly_change_pct": weekly_chg,
        "direction": "up" if weekly_chg >= 0 else "down",
    }


class VnstockDataProvider:
    """Centralized vnstock_data access with same-day caching."""

    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), "cache", "vnstock_data")
        self._cache_dir = cache_dir
        os.makedirs(self._cache_dir, exist_ok=True)
        self._purge_old(days=7)

    def _cache_path(self, endpoint: str) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self._cache_dir, f"{endpoint}_{today}.json")

    def _read_cache(self, endpoint: str) -> Optional[Dict]:
        path = self._cache_path(endpoint)
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return None

    def _write_cache(self, endpoint: str, data: Dict):
        try:
            with open(self._cache_path(endpoint), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, default=str)
        except IOError as e:
            print(f"[VnstockData] Cache write error: {e}")

    def _purge_old(self, days: int = 7):
        try:
            import time
            cutoff = time.time() - days * 86400
            for fname in os.listdir(self._cache_dir):
                fpath = os.path.join(self._cache_dir, fname)
                if os.path.isfile(fpath) and os.path.getmtime(fpath) < cutoff:
                    os.remove(fpath)
        except OSError:
            pass

    # ── Commodity Prices ─────────────────────────────────────────────

    def get_commodity_prices(self) -> Optional[Dict]:
        """Fetch VN gold (SJC), Brent oil, steel HRC prices."""
        if not HAS_VNSTOCK_DATA:
            return None
        cached = self._read_cache("commodity_prices")
        if cached:
            return cached

        result = {}
        cp = CommodityPrice()

        # Gold VN (SJC) — columns: buy, sell
        try:
            df = cp.gold_vn()
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                buy_price = float(latest["buy"])
                daily_chg, weekly_chg = 0.0, 0.0
                if len(df) >= 2:
                    prev = float(df.iloc[-2]["buy"])
                    if prev > 0:
                        daily_chg = round(((buy_price / prev) - 1) * 100, 2)
                if len(df) >= 6:
                    prev_w = float(df.iloc[-6]["buy"])
                    if prev_w > 0:
                        weekly_chg = round(((buy_price / prev_w) - 1) * 100, 2)
                result["gold_vn"] = {
                    "price": buy_price,
                    "sell_price": float(latest["sell"]),
                    "daily_change_pct": daily_chg,
                    "weekly_change_pct": weekly_chg,
                    "direction": "up" if weekly_chg >= 0 else "down",
                }
        except Exception as e:
            print(f"[VnstockData] gold_vn error: {e}")

        # Oil Brent — columns: open, high, low, close, volume
        try:
            data = _ohlcv_extract(cp.oil_crude(), "close")
            if data:
                result["oil_brent"] = data
        except Exception as e:
            print(f"[VnstockData] oil_crude error: {e}")

        # Steel HRC — columns: open, high, low, close, volume
        try:
            data = _ohlcv_extract(cp.steel_hrc(), "close")
            if data:
                result["steel_hrc"] = data
        except Exception as e:
            print(f"[VnstockData] steel_hrc error: {e}")

        if result:
            self._write_cache("commodity_prices", result)
        return result or None

    # ── Market PE/PB ─────────────────────────────────────────────────

    def get_market_pe(self, period: str = "1Y") -> Optional[Dict]:
        """VN-Index PE/PB with 1Y stats (latest, min, max, avg)."""
        if not HAS_VNSTOCK_DATA:
            return None
        cached = self._read_cache(f"market_pe_{period}")
        if cached:
            return cached
        try:
            df = Market().pe(period=period)
            if df is None or df.empty:
                return None
            pe_col = "pe" if "pe" in df.columns else df.columns[1]
            latest = df.iloc[-1]
            pe_vals = df[pe_col].dropna()
            result = {
                "pe_current": round(float(latest[pe_col]), 2),
                "pe_1y_avg": round(float(pe_vals.mean()), 2),
                "pe_1y_min": round(float(pe_vals.min()), 2),
                "pe_1y_max": round(float(pe_vals.max()), 2),
            }
            if "pb" in df.columns:
                pb_vals = df["pb"].dropna()
                result["pb_current"] = round(float(latest["pb"]), 2)
                result["pb_1y_avg"] = round(float(pb_vals.mean()), 2)
            if "marketCap" in df.columns:
                result["market_cap"] = float(latest["marketCap"])
            self._write_cache(f"market_pe_{period}", result)
            return result
        except Exception as e:
            print(f"[VnstockData] market_pe error: {e}")
            return None

    # ── Top Foreign Flow ─────────────────────────────────────────────

    def get_top_foreign(self, exchange: str = "HOSE", limit: int = 5) -> Optional[Dict]:
        """Top foreign net buy/sell by stock (via TopStock.gainer/loser fallback)."""
        if not HAS_VNSTOCK_DATA:
            return None
        cached = self._read_cache(f"top_foreign_{exchange}")
        if cached:
            return cached
        try:
            ts = TopStock()
            result = {"top_buy": [], "top_sell": []}

            # Try foreign_buy/sell first
            buy_df = ts.foreign_buy(exchange=exchange)
            if buy_df is not None and not buy_df.empty:
                for _, row in buy_df.head(limit).iterrows():
                    sym = str(row.get("symbol", row.get("ticker", "")))
                    val = float(row.get("netValue", row.get("accumulated_value", 0)))
                    result["top_buy"].append({"symbol": sym, "net_value": val})

            sell_df = ts.foreign_sell(exchange=exchange)
            if sell_df is not None and not sell_df.empty:
                for _, row in sell_df.head(limit).iterrows():
                    sym = str(row.get("symbol", row.get("ticker", "")))
                    val = float(row.get("netValue", row.get("accumulated_value", 0)))
                    result["top_sell"].append({"symbol": sym, "net_value": val})

            # Fallback: use gainer/loser if foreign data unavailable
            if not result["top_buy"] and not result["top_sell"]:
                gainer_df = ts.gainer()
                if gainer_df is not None and not gainer_df.empty:
                    for _, row in gainer_df.head(limit).iterrows():
                        result["top_buy"].append({
                            "symbol": str(row.get("symbol", "")),
                            "net_value": float(row.get("accumulated_value", 0)),
                            "change_pct": float(row.get("price_change_pct_1d", 0)),
                            "source": "top_gainer",
                        })
                loser_df = ts.loser()
                if loser_df is not None and not loser_df.empty:
                    for _, row in loser_df.head(limit).iterrows():
                        result["top_sell"].append({
                            "symbol": str(row.get("symbol", "")),
                            "net_value": float(row.get("accumulated_value", 0)),
                            "change_pct": float(row.get("price_change_pct_1d", 0)),
                            "source": "top_loser",
                        })

            if result["top_buy"] or result["top_sell"]:
                self._write_cache(f"top_foreign_{exchange}", result)
                return result
        except Exception as e:
            print(f"[VnstockData] top_foreign error: {e}")
        return None

    # ── Macro Indicators ─────────────────────────────────────────────

    def get_macro_indicators(self) -> Optional[Dict]:
        """USD/VND exchange rate + CPI (latest values)."""
        if not HAS_VNSTOCK_DATA:
            return None
        cached = self._read_cache("macro_indicators")
        if cached:
            return cached

        result = {}
        macro = Macro()

        # USD/VND — filter for 'trung tâm' (central rate), use 'value' column
        try:
            df = macro.exchange_rate()
            if df is not None and not df.empty:
                central = df[df["name"].str.contains("trung tâm", na=False)]
                if not central.empty:
                    latest = central.dropna(subset=["value"]).iloc[-1]
                    result["usd_vnd"] = {
                        "rate": float(latest["value"]),
                        "change_pct": 0,
                    }
        except Exception as e:
            print(f"[VnstockData] exchange_rate error: {e}")

        # CPI — filter for "Chỉ số giá tiêu dùng", use 'value' column
        try:
            df = macro.cpi()
            if df is not None and not df.empty:
                cpi_rows = df[df["name"].str.contains("tiêu dùng", na=False)]
                if not cpi_rows.empty:
                    latest = cpi_rows.iloc[-1]
                    period = str(latest.name) if hasattr(latest, "name") else ""
                    result["cpi"] = {
                        "value": float(latest["value"]),
                        "period": period,
                        "unit": str(latest.get("unit", "%")),
                    }
        except Exception as e:
            print(f"[VnstockData] cpi error: {e}")

        if result:
            self._write_cache("macro_indicators", result)
        return result or None


# ── CLI test ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    provider = VnstockDataProvider()

    print("=== Commodity Prices ===")
    c = provider.get_commodity_prices()
    if c:
        for name, d in c.items():
            print(f"  {name}: {d.get('price', 'N/A')} | day:{d.get('daily_change_pct', 0):+.2f}% wk:{d.get('weekly_change_pct', 0):+.2f}%")

    print("\n=== Market PE/PB ===")
    pe = provider.get_market_pe()
    if pe:
        print(f"  PE={pe['pe_current']} (1Y: {pe['pe_1y_min']}-{pe['pe_1y_max']}, avg={pe['pe_1y_avg']})")
        if "pb_current" in pe:
            print(f"  PB={pe['pb_current']} (1Y avg={pe['pb_1y_avg']})")

    print("\n=== Top Stocks ===")
    top = provider.get_top_foreign()
    if top:
        for s in top.get("top_buy", []):
            print(f"  BUY: {s['symbol']} | {s['net_value']:,.0f}")
        for s in top.get("top_sell", []):
            print(f"  SELL: {s['symbol']} | {s['net_value']:,.0f}")

    print("\n=== Macro ===")
    m = provider.get_macro_indicators()
    if m:
        usd = m.get("usd_vnd", {})
        cpi = m.get("cpi", {})
        print(f"  USD/VND: {usd.get('rate', 'N/A'):,.0f}" if usd else "  USD/VND: N/A")
        print(f"  CPI: {cpi.get('value', 'N/A')}% ({cpi.get('period', '')})" if cpi else "  CPI: N/A")
