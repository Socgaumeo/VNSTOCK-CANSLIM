#!/usr/bin/env python3
"""Valuation Scorer - PEG Ratio & Metrics (pure functions, no deps)"""

def calculate_cagr(values: list, years: int) -> float | None:
    """CAGR = (end/start)^(1/years) - 1. Returns None if start/end ≤ 0."""
    if not values or len(values) < 2 or years <= 0:
        return None
    start_val, end_val = values[0], values[-1]
    if start_val is None or end_val is None or start_val <= 0 or end_val <= 0:
        return None
    return round((end_val / start_val) ** (1 / years) - 1, 4)


def get_peg_rating(peg: float) -> str:
    """<0:negative, 0-1:very_cheap, 1-2:cheap, 2-3:fair, >3:expensive"""
    if peg < 0: return 'negative'
    if peg <= 1: return 'very_cheap'
    if peg <= 2: return 'cheap'
    if peg <= 3: return 'fair'
    return 'expensive'


def calculate_peg_ratio(pe_ratio: float, eps_values: list, years: int) -> dict:
    """PEG = P/E / (EPS CAGR%). Returns {peg_ratio, rating, eps_cagr, pe_used}"""
    result = {'peg_ratio': None, 'rating': 'unknown', 'eps_cagr': None, 'pe_used': pe_ratio}
    if pe_ratio is None or pe_ratio <= 0:
        return result

    eps_cagr = calculate_cagr(eps_values, years)
    if eps_cagr is None:
        return result

    result['eps_cagr'] = round(eps_cagr * 100, 2)
    if eps_cagr <= 0:
        result['peg_ratio'] = -1.0
        result['rating'] = 'negative'
        return result

    peg = pe_ratio / (eps_cagr * 100)
    result['peg_ratio'] = round(peg, 2)
    result['rating'] = get_peg_rating(peg)
    return result


def compare_valuation(company_value: float, industry_value: float, lower_is_better: bool = True) -> dict:
    """Compare metric vs industry. Status: cheaper/similar/expensive (within 15% = similar)"""
    result = {'company': company_value, 'industry': industry_value, 'status': 'unknown', 'delta_pct': None}
    if company_value is None or industry_value is None or industry_value == 0:
        return result

    delta_pct = ((company_value - industry_value) / industry_value) * 100
    result['delta_pct'] = round(delta_pct, 2)

    if abs(delta_pct) <= 15:
        result['status'] = 'similar'
    elif lower_is_better:
        result['status'] = 'cheaper' if delta_pct < 0 else 'expensive'
    else:
        result['status'] = 'expensive' if delta_pct < 0 else 'cheaper'
    return result


def classify_valuation(pe: float, pb: float, industry_pe: float, industry_pb: float) -> dict:
    """Overall: undervalued (both cheaper), overvalued (both expensive), fair (mixed)"""
    pe_comp = compare_valuation(pe, industry_pe)
    pb_comp = compare_valuation(pb, industry_pb)
    pe_status, pb_status = pe_comp['status'], pb_comp['status']

    if pe_status == 'unknown' or pb_status == 'unknown':
        overall = 'unknown'
    elif pe_status == 'cheaper' and pb_status in ['cheaper', 'similar']:
        overall = 'undervalued'
    elif pb_status == 'cheaper' and pe_status in ['cheaper', 'similar']:
        overall = 'undervalued'
    elif pe_status == 'expensive' and pb_status in ['expensive', 'similar']:
        overall = 'overvalued'
    elif pb_status == 'expensive' and pe_status in ['expensive', 'similar']:
        overall = 'overvalued'
    else:
        overall = 'fair'

    return {'pe_vs_industry': pe_comp, 'pb_vs_industry': pb_comp, 'overall': overall}


def calculate_percentiles(values: list) -> dict:
    """Percentiles (p5/25/50/75/95) via type-7 linear interpolation"""
    empty_result = {'p5': None, 'p25': None, 'p50': None, 'p75': None, 'p95': None, 'count': 0}
    if not values:
        return empty_result

    clean = sorted([v for v in values if v is not None])
    if not clean:
        return empty_result

    n = len(clean)
    def interp(p):
        if n == 1: return clean[0]
        pos = (n - 1) * (p / 100.0)
        lo, hi = int(pos), min(int(pos) + 1, n - 1)
        frac = pos - lo
        return clean[lo] + frac * (clean[hi] - clean[lo])

    return {
        'p5': round(interp(5), 2), 'p25': round(interp(25), 2), 'p50': round(interp(50), 2),
        'p75': round(interp(75), 2), 'p95': round(interp(95), 2), 'count': n
    }


if __name__ == "__main__":
    print("=== Valuation Scorer Tests ===\n")

    # Test 1: PEG (P/E 20, EPS CAGR 15% -> PEG 1.33)
    peg = calculate_peg_ratio(20, [1000, 1150, 1322.5, 1520.9], 3)
    print(f"T1 PEG: {peg}")
    assert abs(peg['peg_ratio'] - 1.33) < 0.01 and peg['rating'] == 'cheap', "PEG fail"

    # Test 2: Negative growth
    peg_neg = calculate_peg_ratio(20, [1000, 950, 900, 850], 3)
    print(f"T2 Neg: {peg_neg}")
    assert peg_neg['rating'] == 'negative', "Neg fail"

    # Test 3: Percentiles
    pct = calculate_percentiles([10, 12, 14, 15, 18, 20, 22, 25, 28, 30])
    print(f"T3 Pct: {pct}")
    assert pct['p50'] == 19.0, "Pct fail"

    # Test 4: Valuation comparison
    comp = compare_valuation(15.2, 18.5)
    print(f"T4 Comp: {comp}")
    assert comp['status'] == 'cheaper', "Comp fail"

    # Test 5: Classification
    cls = classify_valuation(15.2, 2.1, 18.5, 2.3)
    print(f"T5 Class: {cls['overall']}")
    assert cls['overall'] == 'undervalued', "Class fail"

    # Test 6: Edge cases
    assert calculate_cagr([0, 100], 1) is None, "Zero start fail"
    assert calculate_cagr([-10, 100], 1) is None, "Neg start fail"
    assert calculate_percentiles([])['count'] == 0, "Empty fail"
    print("T6 Edge: OK")

    print("\n=== All Tests Passed ✓ ===")
