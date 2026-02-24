#!/usr/bin/env python3
"""
Earnings Calculator for CANSLIM Analysis
Calculates EPS growth, revenue growth, earnings acceleration, cash flow quality.
Fixes critical C&A scoring bug where MultiIndex column parsing fails.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Tuple

import pandas as pd
import numpy as np

try:
    from vnstock import Vnstock
except ImportError:
    Vnstock = None

from database import get_db, FundamentalStore
from config import get_config


@dataclass
class EarningsResult:
    """Complete earnings metrics for a stock."""
    symbol: str
    # Current Quarter
    eps_current_q: float = 0.0
    eps_growth_qoq: float = 0.0       # vs previous quarter (%)
    eps_growth_yoy: float = 0.0       # vs same quarter last year (%)
    revenue_current_q: float = 0.0
    revenue_growth_qoq: float = 0.0
    revenue_growth_yoy: float = 0.0

    # Annual (CAGR)
    eps_3y_cagr: float = 0.0
    eps_5y_cagr: float = 0.0

    # Acceleration
    eps_acceleration: float = 0.0     # rate of growth change

    # Quality
    consecutive_growth_q: int = 0     # consecutive quarters EPS grew
    earnings_stability: float = 0.0   # 0-100

    # Cash Flow
    ocf_to_profit_ratio: float = 0.0  # average 4Q OCF / average 4Q profit
    cash_flow_quality: float = 0.0    # 0-100 score

    # Margins
    roe: float = 0.0
    roa: float = 0.0
    gross_margin: float = 0.0
    gross_margin_expansion: float = 0.0  # current - avg(previous 4Q)

    # Metadata
    quarters_available: int = 0
    confidence: float = 0.0           # 0-100
    data_source: str = ""


class EarningsCalculator:
    """
    Calculate earnings metrics from vnstock APIs.
    Uses SQLite cache with 7-day TTL.
    """

    def __init__(self):
        self._store = FundamentalStore()
        self._vnstock = None
        self._config = get_config()

    def calculate(self, symbol: str) -> EarningsResult:
        """Main entry: check cache, fetch if stale, calculate all metrics."""
        try:
            # Check cache freshness
            if self._store.is_fresh(symbol, max_days=7):
                quarters = self._load_from_db(symbol)
                if quarters:
                    return self._calculate_metrics(symbol, quarters, source="cache")

            # Fetch from API
            quarters = self._fetch_from_api(symbol)
            if not quarters:
                return EarningsResult(symbol=symbol, data_source="failed")

            # Save to DB
            self._save_to_db(symbol, quarters)

            # Calculate metrics
            return self._calculate_metrics(symbol, quarters, source="api")

        except Exception as e:
            print(f"   ⚠️ EarningsCalculator error for {symbol}: {e}")
            return EarningsResult(symbol=symbol, data_source="error")

    def _load_from_db(self, symbol: str) -> List[Dict]:
        """Load quarterly data from SQLite cache."""
        try:
            df = self._store.get_quarterly(symbol, periods=20)
            if df.empty:
                return []

            quarters = []
            for _, row in df.iterrows():
                quarters.append({
                    'period': row['period'],
                    'year': row['year'],
                    'quarter': row['quarter'],
                    'revenue': row['revenue'],
                    'profit': row['profit'],
                    'eps': row['eps'],
                    'roe': row['roe'],
                    'roa': row['roa'],
                    'pe': row['pe'],
                    'pb': row['pb'],
                    'gross_margin': row['gross_margin'],
                    'net_margin': row['net_margin'],
                    'ocf': row['ocf'],
                    'icf': row['icf'],
                    'fcf': row['fcf'],
                })
            return quarters

        except Exception as e:
            print(f"   ⚠️ Load from DB failed for {symbol}: {e}")
            return []

    def _fetch_from_api(self, symbol: str) -> List[Dict]:
        """Fetch income_statement + ratio + cash_flow from vnstock API."""
        try:
            if not self._vnstock:
                self._vnstock = Vnstock()

            stock = self._vnstock.stock(symbol, source='VCI')

            # Fetch 3 endpoints
            df_income = self._safe_fetch(stock.finance.income_statement, period='quarter', lang='vi')
            time.sleep(1)  # Rate limiting
            df_ratio = self._safe_fetch(stock.finance.ratio, period='quarter', lang='vi')
            time.sleep(1)
            df_cash = self._safe_fetch(stock.finance.cash_flow, period='quarter', lang='vi')

            if df_income is None or df_income.empty:
                return []

            # Parse quarterly data
            quarters = self._parse_quarterly_data(df_income, df_ratio, df_cash)
            return quarters

        except Exception as e:
            print(f"   ⚠️ API fetch failed for {symbol}: {e}")
            return []

    def _safe_fetch(self, method, **kwargs) -> Optional[pd.DataFrame]:
        """Safe API call with error handling."""
        try:
            return method(**kwargs)
        except Exception:
            return None

    def _parse_quarterly_data(
        self,
        df_income: pd.DataFrame,
        df_ratio: Optional[pd.DataFrame],
        df_cash: Optional[pd.DataFrame]
    ) -> List[Dict]:
        """Parse DataFrames into unified quarterly records."""
        quarters = []

        # Find columns using flexible matching
        col_revenue = self._find_column(df_income, 'doanh thu', 'đồng')
        col_profit = self._find_column(df_income, 'lợi nhuận sau thuế', 'cổ đông công ty mẹ')

        # Ratio columns (MultiIndex)
        col_roe = self._find_column(df_ratio, 'roe') if df_ratio is not None else None
        col_roa = self._find_column(df_ratio, 'roa') if df_ratio is not None else None
        col_pe = self._find_column(df_ratio, 'p/e') if df_ratio is not None else None
        col_pb = self._find_column(df_ratio, 'p/b') if df_ratio is not None else None
        col_gross = self._find_column(df_ratio, 'biên lợi nhuận gộp') if df_ratio is not None else None
        col_net = self._find_column(df_ratio, 'biên lợi nhuận ròng') if df_ratio is not None else None

        # Cash flow columns (MultiIndex)
        col_ocf = self._find_column(df_cash, 'lưu chuyển', 'kinh doanh') if df_cash is not None else None
        col_icf = self._find_column(df_cash, 'lưu chuyển', 'đầu tư') if df_cash is not None else None
        col_fcf = self._find_column(df_cash, 'lưu chuyển', 'tài chính') if df_cash is not None else None

        # Parse up to 20 quarters
        for idx, row in df_income.head(20).iterrows():
            period = str(idx) if isinstance(idx, str) else f"Q{idx}"

            # Extract values safely
            revenue = self._safe_float(row.get(col_revenue) if col_revenue else 0)
            profit = self._safe_float(row.get(col_profit) if col_profit else 0)

            # Calculate EPS (profit / 1B shares assumed, actual shares unknown)
            eps = profit / 1e9 if profit else 0

            # Get ratio values
            roe = 0.0
            roa = 0.0
            pe = 0.0
            pb = 0.0
            gross_margin = 0.0
            net_margin = 0.0

            if df_ratio is not None and not df_ratio.empty and idx in df_ratio.index:
                ratio_row = df_ratio.loc[idx]
                roe = self._safe_float(ratio_row.get(col_roe) if col_roe else 0)
                roa = self._safe_float(ratio_row.get(col_roa) if col_roa else 0)
                pe = self._safe_float(ratio_row.get(col_pe) if col_pe else 0)
                pb = self._safe_float(ratio_row.get(col_pb) if col_pb else 0)
                gross_margin = self._safe_float(ratio_row.get(col_gross) if col_gross else 0)
                net_margin = self._safe_float(ratio_row.get(col_net) if col_net else 0)

            # Get cash flow values
            ocf = 0.0
            icf = 0.0
            fcf = 0.0

            if df_cash is not None and not df_cash.empty and idx in df_cash.index:
                cash_row = df_cash.loc[idx]
                ocf = self._safe_float(cash_row.get(col_ocf) if col_ocf else 0)
                icf = self._safe_float(cash_row.get(col_icf) if col_icf else 0)
                fcf = self._safe_float(cash_row.get(col_fcf) if col_fcf else 0)

            # Parse year/quarter
            year, quarter = self._parse_period(period)

            quarters.append({
                'period': period,
                'year': year,
                'quarter': quarter,
                'revenue': revenue,
                'profit': profit,
                'eps': eps,
                'roe': roe,
                'roa': roa,
                'pe': pe,
                'pb': pb,
                'gross_margin': gross_margin,
                'net_margin': net_margin,
                'ocf': ocf,
                'icf': icf,
                'fcf': fcf,
            })

        return quarters

    def _find_column(self, df: Optional[pd.DataFrame], *keywords) -> Optional[str]:
        """Find column in MultiIndex or single-level by keyword matching."""
        if df is None or df.empty:
            return None

        for col in df.columns:
            col_str = str(col).lower()
            # Exclude growth columns (tăng trưởng)
            if 'tăng trưởng' in col_str:
                continue
            # Match all keywords
            if all(kw.lower() in col_str for kw in keywords):
                return col
        return None

    def _safe_float(self, value) -> float:
        """Safely convert to float, handle NaN."""
        try:
            if pd.isna(value):
                return 0.0
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    def _parse_period(self, period: str) -> Tuple[int, int]:
        """Parse period string like 'Q1/2024' into (year, quarter)."""
        try:
            parts = period.replace('-', '/').split('/')
            if len(parts) == 2:
                q_part = parts[0].upper().replace('Q', '')
                return int(parts[1]), int(q_part)
        except (ValueError, IndexError):
            pass
        return 0, 0

    def _save_to_db(self, symbol: str, quarters: List[Dict]):
        """Save quarterly data to SQLite."""
        try:
            self._store.save_quarterly(symbol, quarters)
        except Exception as e:
            print(f"   ⚠️ Save to DB failed for {symbol}: {e}")

    def _calculate_metrics(
        self,
        symbol: str,
        quarters: List[Dict],
        source: str = "api"
    ) -> EarningsResult:
        """Calculate all growth metrics from quarterly data."""
        result = EarningsResult(symbol=symbol, data_source=source)

        if not quarters:
            return result

        result.quarters_available = len(quarters)
        result.confidence = min(100, len(quarters) * 5)  # 20 quarters = 100%

        # Current quarter metrics
        current = quarters[0]
        result.eps_current_q = current['eps']
        result.revenue_current_q = current['revenue']
        result.roe = current['roe']
        result.roa = current['roa']
        result.gross_margin = current['gross_margin']

        # QoQ growth
        if len(quarters) >= 2:
            prev = quarters[1]
            result.eps_growth_qoq = self._calc_growth(current['profit'], prev['profit'])
            result.revenue_growth_qoq = self._calc_growth(current['revenue'], prev['revenue'])

        # YoY growth (same quarter last year = 4 quarters ago)
        if len(quarters) >= 5:
            yoy = quarters[4]
            result.eps_growth_yoy = self._calc_growth(current['profit'], yoy['profit'])
            result.revenue_growth_yoy = self._calc_growth(current['revenue'], yoy['revenue'])

        # CAGR
        result.eps_3y_cagr = self._calc_cagr(quarters, 3)
        result.eps_5y_cagr = self._calc_cagr(quarters, 5)

        # Acceleration
        result.eps_acceleration = self._calc_acceleration(quarters)

        # Consecutive growth
        result.consecutive_growth_q = self._calc_consecutive_growth(quarters)

        # Stability
        result.earnings_stability = self._calc_earnings_stability(quarters)

        # Cash flow quality
        result.ocf_to_profit_ratio, result.cash_flow_quality = self._calc_cash_flow_quality(quarters)

        # Gross margin expansion
        result.gross_margin_expansion = self._calc_gross_margin_expansion(quarters)

        return result

    def _calc_growth(self, current: float, previous: float) -> float:
        """Calculate growth percentage."""
        if previous == 0 or pd.isna(previous) or pd.isna(current):
            return 0.0
        return ((current - previous) / abs(previous)) * 100

    def _calc_cagr(self, quarters: List[Dict], years: int) -> float:
        """CAGR from quarterly profit data. Requires both values positive."""
        required_quarters = years * 4
        if len(quarters) < required_quarters + 1:
            return 0.0

        current = quarters[0]['profit']
        past = quarters[required_quarters]['profit']

        if pd.isna(current) or pd.isna(past):
            return 0.0
        # CAGR only meaningful when both periods are profitable
        if current <= 0 or past <= 0:
            return 0.0

        try:
            cagr = (pow(current / past, 1 / years) - 1) * 100
            return cagr
        except (ValueError, ZeroDivisionError):
            return 0.0

    def _calc_acceleration(self, quarters: List[Dict]) -> float:
        """EPS acceleration: rate of growth change."""
        if len(quarters) < 6:
            return 0.0

        # Compare recent 2Q growth vs previous 2Q growth
        recent_growth = self._calc_growth(quarters[0]['profit'], quarters[1]['profit'])
        prev_growth = self._calc_growth(quarters[2]['profit'], quarters[3]['profit'])

        if prev_growth == 0:
            return 0.0

        acceleration = recent_growth - prev_growth
        return acceleration

    def _calc_consecutive_growth(self, quarters: List[Dict]) -> int:
        """Count consecutive quarters with EPS growth."""
        count = 0
        for i in range(len(quarters) - 1):
            current = quarters[i]['profit']
            prev = quarters[i + 1]['profit']
            if current > prev and prev > 0:
                count += 1
            else:
                break
        return count

    def _calc_earnings_stability(self, quarters: List[Dict]) -> float:
        """Stability score based on EPS variance (0-100)."""
        if len(quarters) < 4:
            return 0.0

        profits = [q['profit'] for q in quarters[:8] if pd.notna(q['profit']) and q['profit'] > 0]
        if len(profits) < 4:
            return 0.0

        try:
            mean = np.mean(profits)
            std = np.std(profits)
            if mean == 0:
                return 0.0
            cv = std / mean  # coefficient of variation
            # Lower CV = higher stability
            stability = max(0, 100 - (cv * 100))
            return min(100, stability)
        except Exception:
            return 0.0

    def _calc_cash_flow_quality(self, quarters: List[Dict]) -> Tuple[float, float]:
        """Returns (ocf_to_profit_ratio, quality_score)."""
        if len(quarters) < 4:
            return 0.0, 0.0

        # Average last 4 quarters
        recent = quarters[:4]
        avg_ocf = np.mean([q['ocf'] for q in recent if pd.notna(q['ocf'])])
        avg_profit = np.mean([q['profit'] for q in recent if pd.notna(q['profit']) and q['profit'] != 0])

        if avg_profit == 0:
            return 0.0, 0.0

        ratio = avg_ocf / avg_profit

        # Quality score: ratio > 1.0 = excellent, ratio > 0.8 = good
        if ratio >= 1.2:
            quality = 100
        elif ratio >= 1.0:
            quality = 80
        elif ratio >= 0.8:
            quality = 60
        elif ratio >= 0.5:
            quality = 40
        else:
            quality = 20

        return ratio, quality

    def _calc_gross_margin_expansion(self, quarters: List[Dict]) -> float:
        """Current gross margin vs average of previous quarters."""
        if len(quarters) < 5:
            return 0.0

        current_margin = quarters[0]['gross_margin']
        prev_margins = [q['gross_margin'] for q in quarters[1:5] if pd.notna(q['gross_margin'])]

        if not prev_margins or pd.isna(current_margin):
            return 0.0

        avg_prev = np.mean(prev_margins)
        expansion = current_margin - avg_prev
        return expansion


# ══════════════════════════════════════════════════════════════════════════════
# FACTORY FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def get_earnings_calculator() -> EarningsCalculator:
    """
    Factory function for EarningsCalculator.

    Usage:
        from earnings_calculator import get_earnings_calculator
        calc = get_earnings_calculator()
        result = calc.calculate("VCB")
        print(f"EPS YoY: {result.eps_growth_yoy:.1f}%")
    """
    return EarningsCalculator()


# ══════════════════════════════════════════════════════════════════════════════
# CLI TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "VCB"

    print(f"\n{'='*70}")
    print(f"EARNINGS CALCULATOR TEST - {symbol}")
    print('='*70)

    calc = get_earnings_calculator()
    result = calc.calculate(symbol)

    print(f"\n📊 CURRENT QUARTER")
    print(f"   EPS: {result.eps_current_q:,.2f}")
    print(f"   Revenue: {result.revenue_current_q:,.0f}")
    print(f"   EPS Growth QoQ: {result.eps_growth_qoq:+.1f}%")
    print(f"   EPS Growth YoY: {result.eps_growth_yoy:+.1f}%")
    print(f"   Revenue Growth QoQ: {result.revenue_growth_qoq:+.1f}%")
    print(f"   Revenue Growth YoY: {result.revenue_growth_yoy:+.1f}%")

    print(f"\n📈 GROWTH RATES")
    print(f"   3Y CAGR: {result.eps_3y_cagr:+.1f}%")
    print(f"   5Y CAGR: {result.eps_5y_cagr:+.1f}%")
    print(f"   Acceleration: {result.eps_acceleration:+.1f}%")
    print(f"   Consecutive Growth: {result.consecutive_growth_q} quarters")

    print(f"\n💰 QUALITY METRICS")
    print(f"   Stability: {result.earnings_stability:.1f}/100")
    print(f"   OCF/Profit Ratio: {result.ocf_to_profit_ratio:.2f}")
    print(f"   Cash Flow Quality: {result.cash_flow_quality:.1f}/100")

    print(f"\n📉 MARGINS")
    print(f"   ROE: {result.roe:.1f}%")
    print(f"   ROA: {result.roa:.1f}%")
    print(f"   Gross Margin: {result.gross_margin:.1f}%")
    print(f"   Margin Expansion: {result.gross_margin_expansion:+.1f}%")

    print(f"\n📋 METADATA")
    print(f"   Quarters Available: {result.quarters_available}")
    print(f"   Confidence: {result.confidence:.0f}%")
    print(f"   Data Source: {result.data_source}")

    print(f"\n{'='*70}\n")
