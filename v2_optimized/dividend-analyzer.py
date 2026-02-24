"""
Dividend Analysis: yield, consistency, CAGR, payout ratio
"""
from typing import Optional


def calculate_dividend_metrics(div_history: list, current_price_vnd: float) -> dict:
    """Calculate yield, consistency, CAGR from div_history [{'year', 'amount'}] and price."""
    if not div_history:
        return {
            'yield': 0.0,
            'yield_pct': 0.0,
            'yield_rating': 'none',
            'consistency': {'years_paid': 0, 'total_years': 0, 'score': 0.0, 'rating': 'none'},
            'cagr': 0.0,
            'latest_dividend': 0.0,
            'history_years': 0,
        }

    # Sort by year to ensure correct order
    sorted_history = sorted(div_history, key=lambda x: x['year'])
    latest = sorted_history[-1]['amount']
    oldest = sorted_history[0]['amount']
    years_count = len(sorted_history)

    # Yield
    div_yield = latest / current_price_vnd if current_price_vnd > 0 else 0.0
    yield_pct = div_yield * 100
    yield_rating = get_dividend_rating(yield_pct)

    # Consistency
    years_paid = sum(1 for d in sorted_history if d['amount'] > 0)
    consistency_score = years_paid / years_count if years_count > 0 else 0.0
    consistency_rating = 'excellent' if consistency_score >= 0.9 else 'good' if consistency_score >= 0.7 else 'average' if consistency_score >= 0.5 else 'poor'

    # CAGR
    cagr = (latest / oldest) ** (1 / (years_count - 1)) - 1 if years_count > 1 and oldest > 0 and latest > 0 else 0.0

    return {
        'yield': div_yield,
        'yield_pct': yield_pct,
        'yield_rating': yield_rating,
        'consistency': {
            'years_paid': years_paid,
            'total_years': years_count,
            'score': consistency_score,
            'rating': consistency_rating,
        },
        'cagr': cagr,
        'latest_dividend': latest,
        'history_years': years_count,
    }


def get_dividend_rating(yield_pct: float) -> str:
    """Rate dividend yield."""
    if yield_pct is None or yield_pct <= 0: return 'none'
    if yield_pct >= 8: return 'excellent'
    if yield_pct >= 6: return 'high'
    if yield_pct >= 4: return 'good'
    if yield_pct >= 2: return 'average'
    return 'low'


def calculate_payout_ratio(dividend_per_share: float, eps: float) -> Optional[float]:
    """Calculate payout ratio (dividend / EPS)."""
    return dividend_per_share / eps if eps and eps > 0 else None


if __name__ == '__main__':
    print("=== Dividend Analysis Tests ===\n")
    # Test 1: 3-year history
    div_hist = [{'year': 2023, 'amount': 1000}, {'year': 2024, 'amount': 1200}, {'year': 2025, 'amount': 1500}]
    r = calculate_dividend_metrics(div_hist, 45000.0)
    print(f"Test 1: Yield {r['yield_pct']:.2f}% ({r['yield_rating']}), Consistency {r['consistency']['score']:.2f}, CAGR {r['cagr']*100:.2f}%\n")
    # Test 2: Single year
    r2 = calculate_dividend_metrics([{'year': 2025, 'amount': 2000}], 50000.0)
    print(f"Test 2: Yield {r2['yield_pct']:.2f}% ({r2['yield_rating']}), CAGR {r2['cagr']*100:.2f}%\n")
    # Test 3: Empty
    r3 = calculate_dividend_metrics([], 50000.0)
    print(f"Test 3: Empty - Yield {r3['yield_pct']:.2f}% ({r3['yield_rating']})\n")
    # Test 4: Ratings
    print("Test 4: Ratings:", {pct: get_dividend_rating(pct) for pct in [0, 1.5, 3, 5, 7, 9]})
    # Test 5: Payout
    payout = calculate_payout_ratio(1500, 5000)
    print(f"\nTest 5: Payout {payout:.2%}" if payout else "N/A")
