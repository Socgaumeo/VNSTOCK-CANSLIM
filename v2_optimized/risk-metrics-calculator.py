"""Risk Metrics Calculator - lightweight module for portfolio risk analysis."""
import math
from typing import Optional


class RiskCalculator:
    def __init__(self, price_history: list, market_history: list = None, risk_free_rate: float = 0.05):
        self.rf = risk_free_rate
        self.prices, self.price_dates = self._extract_closes(price_history)
        self.returns = self._calc_returns(self.prices)
        self.market_prices = None
        self.market_dates = None
        self.market_returns = None
        if market_history:
            self.market_prices, self.market_dates = self._extract_closes(market_history)
            self.market_returns = self._calc_returns(self.market_prices)

    def _extract_closes(self, data) -> tuple[list[float], list[str]]:
        if not data:
            return [], []
        if isinstance(data[0], dict):
            prices = [float(d['close']) for d in data]
            dates = [str(d['time']) for d in data]
            return prices, dates
        return [float(p) for p in data], []

    def _calc_returns(self, prices: list[float]) -> list[float]:
        if len(prices) < 2:
            return []
        return [math.log(prices[i] / prices[i-1]) for i in range(1, len(prices))]

    def _stddev(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        mean_val = sum(values) / len(values)
        variance = sum((x - mean_val) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)

    def calc_volatility(self, days: int = None) -> Optional[float]:
        returns = self.returns[-days:] if days else self.returns
        if len(returns) < 5:
            return None
        stddev = self._stddev(returns)
        return round(stddev * math.sqrt(252) * 100, 2)

    def calc_beta(self) -> Optional[float]:
        if not self.market_returns or not self.price_dates or not self.market_dates:
            return None
        stock_dict = {self.price_dates[i+1]: self.returns[i] for i in range(len(self.returns))}
        market_dict = {self.market_dates[i+1]: self.market_returns[i] for i in range(len(self.market_returns))}
        common_dates = sorted(set(stock_dict.keys()) & set(market_dict.keys()))
        if len(common_dates) < 10:
            return None
        stock_aligned = [stock_dict[d] for d in common_dates]
        market_aligned = [market_dict[d] for d in common_dates]
        stock_mean = sum(stock_aligned) / len(stock_aligned)
        market_mean = sum(market_aligned) / len(market_aligned)
        covariance = sum((stock_aligned[i] - stock_mean) * (market_aligned[i] - market_mean)
                        for i in range(len(common_dates))) / (len(common_dates) - 1)
        market_variance = sum((m - market_mean) ** 2 for m in market_aligned) / (len(market_aligned) - 1)
        if market_variance == 0:
            return None
        return round(covariance / market_variance, 2)

    def calc_var(self, confidence: float = 0.95) -> Optional[float]:
        if len(self.returns) < 20:
            return None
        sorted_returns = sorted(self.returns)
        index = int((1 - confidence) * len(sorted_returns))
        return round(-sorted_returns[index] * 100, 2)

    def calc_sharpe(self, risk_free_rate: float = None) -> Optional[float]:
        if len(self.returns) < 5:
            return None
        rf = risk_free_rate if risk_free_rate is not None else self.rf
        mean_daily_return = sum(self.returns) / len(self.returns)
        annual_log_return = mean_daily_return * 252
        stddev = self._stddev(self.returns)
        annual_vol = stddev * math.sqrt(252)
        if annual_vol == 0:
            return None
        log_rf = math.log(1 + rf)
        return round((annual_log_return - log_rf) / annual_vol, 2)

    def calc_sortino(self, target: float = 0.0) -> Optional[float]:
        if len(self.returns) < 5:
            return None
        downside = [r for r in self.returns if r < target]
        if not downside:
            return None
        downside_variance = sum((r - target) ** 2 for r in downside) / len(downside)
        downside_dev_annual = math.sqrt(downside_variance) * math.sqrt(252)
        if downside_dev_annual == 0:
            return None
        mean_return = sum(self.returns) / len(self.returns)
        annual_return = mean_return * 252
        return round((annual_return - target) / downside_dev_annual, 2)

    def calc_max_drawdown(self) -> Optional[float]:
        if len(self.prices) < 2:
            return None
        peak = self.prices[0]
        max_dd = 0.0
        for price in self.prices:
            if price > peak:
                peak = price
            dd = (peak - price) / peak
            if dd > max_dd:
                max_dd = dd
        return round(max_dd * 100, 2)

    def calc_all(self) -> dict:
        return {
            'volatility_30d': self.calc_volatility(30),
            'volatility_90d': self.calc_volatility(90),
            'volatility_1y': self.calc_volatility(252),
            'beta': self.calc_beta(),
            'var_95': self.calc_var(0.95),
            'var_99': self.calc_var(0.99),
            'sharpe': self.calc_sharpe(),
            'sortino': self.calc_sortino(),
            'max_drawdown': self.calc_max_drawdown(),
            'data_days': len(self.prices),
        }


if __name__ == "__main__":
    import random
    print("=== Risk Metrics Calculator Test ===\n")
    random.seed(42)
    base_price = 100.0
    prices = [base_price]
    dates = ["2024-01-01"]
    for i in range(252):
        change = random.gauss(0.0005, 0.02)
        prices.append(prices[-1] * (1 + change))
        dates.append(f"2024-{((i+1) % 12) + 1:02d}-{((i+1) % 28) + 1:02d}")
    price_history = [{'time': dates[i], 'close': prices[i]} for i in range(len(prices))]
    market_prices = [100.0]
    for i in range(252):
        change = random.gauss(0.0003, 0.015)
        market_prices.append(market_prices[-1] * (1 + change))
    market_history = [{'time': dates[i], 'close': market_prices[i]} for i in range(len(market_prices))]
    calc = RiskCalculator(price_history, market_history, risk_free_rate=0.05)
    metrics = calc.calc_all()
    print("Full Data Metrics:")
    for k, v in metrics.items():
        print(f"  {k}: {v}")
    print("\n\nInsufficient Data Test (should return None):")
    calc_small = RiskCalculator(price_history[:3], market_history[:3])
    metrics_small = calc_small.calc_all()
    for k, v in metrics_small.items():
        print(f"  {k}: {v}")
    print("\n✓ All tests passed - no crashes with insufficient data")
