"""Money Flow Analyzer: foreign flow, vol-price divergence, distribution days, MFI, OBV.

Usage with database layer:
    from database import get_db, ForeignFlowStore
    from data_collector import DataCollector

    collector = DataCollector()
    stock_data = collector.get_stock_data("VNM", period="1Y")

    flow_store = ForeignFlowStore()
    foreign_df = flow_store.get_flow("VNM", days=20)

    analyzer = MoneyFlowAnalyzer()
    result = analyzer.analyze("VNM", stock_data.df, foreign_df)
    print(f"Money Flow Score: {result.money_flow_score}/100")
"""

from dataclasses import dataclass
import pandas as pd
import numpy as np
from typing import Optional


@dataclass
class MoneyFlowResult:
    symbol: str
    foreign_net_5d: float = 0.0
    foreign_net_20d: float = 0.0
    foreign_trend: str = "NEUTRAL"
    foreign_consecutive_buy: int = 0
    foreign_consecutive_sell: int = 0
    volume_price_divergence: str = "NONE"
    divergence_strength: float = 0.0
    distribution_days_25: int = 0
    accumulation_days_25: int = 0
    mfi_14: float = 50.0
    obv_trend: str = "FLAT"
    obv_divergence: str = "NONE"
    money_flow_score: float = 50.0


class MoneyFlowAnalyzer:
    """Analyze volume and money flow patterns."""

    def analyze(self, symbol: str, df: pd.DataFrame,
                foreign_df: Optional[pd.DataFrame] = None) -> MoneyFlowResult:
        """Full money flow analysis from OHLCV and foreign flow data."""
        result = MoneyFlowResult(symbol=symbol)

        if df is None or len(df) < 20:
            return result

        df_clean = df.dropna(subset=['close', 'volume'])
        if len(df_clean) < 20:
            return result

        # Foreign flow
        if foreign_df is not None and len(foreign_df) > 0:
            fdata = self._calc_foreign_trend(foreign_df)
            result.foreign_net_5d = fdata['net_5d']
            result.foreign_net_20d = fdata['net_20d']
            result.foreign_trend = fdata['trend']
            result.foreign_consecutive_buy = fdata['consecutive_buy']
            result.foreign_consecutive_sell = fdata['consecutive_sell']

        # Volume-price divergence
        div = self._detect_volume_price_divergence(df_clean)
        result.volume_price_divergence = div['type']
        result.divergence_strength = div['strength']

        # Distribution/accumulation
        dist = self._count_distribution_days(df_clean)
        result.distribution_days_25 = dist['distribution']
        result.accumulation_days_25 = dist['accumulation']

        # Indicators
        result.mfi_14 = self._calc_mfi(df_clean)
        obv = self._calc_obv(df_clean)
        result.obv_trend = obv['trend']
        result.obv_divergence = obv['divergence']

        result.money_flow_score = self._calc_composite_score(result)
        return result

    def _calc_foreign_trend(self, foreign_df: pd.DataFrame) -> dict:
        r = {'net_5d': 0.0, 'net_20d': 0.0, 'trend': 'NEUTRAL',
             'consecutive_buy': 0, 'consecutive_sell': 0}
        if foreign_df is None or len(foreign_df) == 0 or 'net_value' not in foreign_df.columns:
            return r
        df = foreign_df.sort_index(ascending=False).copy()
        if len(df) >= 5:
            r['net_5d'] = df['net_value'].iloc[:5].sum()
        if len(df) >= 20:
            r['net_20d'] = df['net_value'].iloc[:20].sum()
        if r['net_5d'] > 0 and r['net_20d'] > 0:
            r['trend'] = 'ACCUMULATING'
        elif r['net_5d'] < 0 and r['net_20d'] < 0:
            r['trend'] = 'DISTRIBUTING'
        for net_val in df['net_value'].values:
            if net_val > 0:
                r['consecutive_buy'] += 1
            else:
                break
        for net_val in df['net_value'].values:
            if net_val < 0:
                r['consecutive_sell'] += 1
            else:
                break
        return r

    def _detect_volume_price_divergence(self, df: pd.DataFrame, lookback: int = 20) -> dict:
        r = {'type': 'NONE', 'strength': 0.0}
        if len(df) < lookback:
            return r
        recent = df.tail(lookback)
        x = np.arange(len(recent))
        try:
            ps = np.polyfit(x, recent['close'].values, 1)[0] if len(recent) >= 2 else 0
            vs = np.polyfit(x, recent['volume'].values, 1)[0] if len(recent) >= 2 else 0
        except:
            return r
        calc_str = lambda: min(100.0, abs(ps / (recent['close'].mean() + 1e-9)) *
                              abs(vs / (recent['volume'].mean() + 1e-9)) * 1000)
        if ps > 0 and vs < 0:
            r['type'], r['strength'] = 'BEARISH_DIV', calc_str()
        elif ps < 0 and vs < 0:
            r['type'], r['strength'] = 'BULLISH_DIV', calc_str()
        return r

    def _count_distribution_days(self, df: pd.DataFrame, lookback: int = 25) -> dict:
        """Count distribution and accumulation days (O'Neil method)."""
        if len(df) < 2:
            return {'distribution': 0, 'accumulation': 0}

        recent = df.tail(min(lookback + 1, len(df))).copy()
        recent['pct_change'] = recent['close'].pct_change() * 100
        recent['vol_inc'] = recent['volume'] > recent['volume'].shift(1)

        return {
            'distribution': ((recent['pct_change'] <= -0.2) & recent['vol_inc']).sum(),
            'accumulation': ((recent['pct_change'] >= 0.2) & recent['vol_inc']).sum()
        }

    def _calc_mfi(self, df: pd.DataFrame, period: int = 14) -> float:
        if len(df) < period + 1:
            return 50.0
        tp = (df['high'] + df['low'] + df['close']) / 3
        rmf = tp * df['volume']
        tc = tp.diff()
        pos = (rmf.where(tc > 0, 0)).rolling(window=period).sum()
        neg = (rmf.where(tc < 0, 0)).rolling(window=period).sum()
        mfi = 100 - (100 / (1 + (pos / (neg + 1e-9))))
        last = mfi.iloc[-1]
        return 50.0 if pd.isna(last) else float(np.clip(last, 0, 100))

    def _calc_obv(self, df: pd.DataFrame) -> dict:
        if len(df) < 20:
            return {'trend': 'FLAT', 'divergence': 'NONE'}
        obv = pd.Series(index=df.index, dtype=float)
        obv.iloc[0] = df['volume'].iloc[0]
        for i in range(1, len(df)):
            if df['close'].iloc[i] > df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] + df['volume'].iloc[i]
            elif df['close'].iloc[i] < df['close'].iloc[i-1]:
                obv.iloc[i] = obv.iloc[i-1] - df['volume'].iloc[i]
            else:
                obv.iloc[i] = obv.iloc[i-1]
        x = np.arange(20)
        try:
            os = np.polyfit(x, obv.tail(20).values, 1)[0]
            ps = np.polyfit(x, df['close'].tail(20).values, 1)[0]
        except:
            return {'trend': 'FLAT', 'divergence': 'NONE'}
        trend = 'RISING' if os > 0 else ('FALLING' if os < 0 else 'FLAT')
        div = 'BULLISH' if (ps < 0 and os > 0) else ('BEARISH' if (ps > 0 and os < 0) else 'NONE')
        return {'trend': trend, 'divergence': div}

    def _calc_composite_score(self, r: MoneyFlowResult) -> float:
        s = 0.0
        s += {'ACCUMULATING': 25, 'NEUTRAL': 12}.get(r.foreign_trend, 0)
        s += {'BULLISH_DIV': 15, 'NONE': 8}.get(r.volume_price_divergence, 0)
        if r.distribution_days_25 == 0:
            s += 20
        elif r.distribution_days_25 <= 2:
            s += 15
        elif r.distribution_days_25 <= 4:
            s += 10
        s += (r.mfi_14 / 100) * 20
        s += {'RISING': 20, 'FLAT': 10}.get(r.obv_trend, 0)
        return round(s, 2)
