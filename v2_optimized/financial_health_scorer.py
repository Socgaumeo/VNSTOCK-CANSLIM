"""Financial Health Scoring: Piotroski F-Score & Altman Z-Score for Vietnam market"""
from typing import Dict, Optional, Any

def _safe_get(data: Dict[str, Any], key: str, default: Optional[float] = None) -> Optional[float]:
    if data is None:
        return default
    val = data.get(key, default)
    return val if val is not None else default


def _safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safe division to avoid ZeroDivisionError."""
    if denominator is None or denominator == 0:
        return default
    return numerator / denominator

def calculate_piotroski_f_score(current: Dict[str, Any], previous: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Calculate Piotroski F-Score (0-9) with Vietnam market adjustments"""
    if current is None:
        return {'score': 0, 'rating': 'Weak', 'details': {}}

    details, score = {}, 0
    roa = _safe_get(current, 'roa', 0)
    cfo = _safe_get(current, 'cfo', 0)
    details['roa_positive'] = int(roa > 0)
    details['cfo_positive'] = int(cfo > 0)
    score += details['roa_positive'] + details['cfo_positive']

    if previous:
        details['roa_improved'] = int(roa > _safe_get(previous, 'roa', 0))
        net_income = _safe_get(current, 'net_income', 0)
        details['cfo_gt_net_income'] = int(cfo >= 0.8 * net_income if net_income else cfo > 0)
        score += details['roa_improved'] + details['cfo_gt_net_income']

        curr_debt = _safe_get(current, 'long_term_debt') or _safe_get(current, 'total_liabilities', 0)
        prev_debt = _safe_get(previous, 'long_term_debt') or _safe_get(previous, 'total_liabilities', 0)
        curr_ratio = _safe_divide(curr_debt, _safe_get(current, 'total_assets', 1), 1.0)
        prev_ratio = _safe_divide(prev_debt, _safe_get(previous, 'total_assets', 1), 1.0)
        details['leverage_improved'] = int(curr_ratio < prev_ratio)
        score += details['leverage_improved']

        curr_cr = _safe_divide(_safe_get(current, 'current_assets', 0), _safe_get(current, 'current_liabilities', 1), 1.0)
        prev_cr = _safe_divide(_safe_get(previous, 'current_assets', 0), _safe_get(previous, 'current_liabilities', 1), 1.0)
        details['current_ratio_improved'] = int(curr_cr > prev_cr)
        score += details['current_ratio_improved']

        curr_shares = _safe_get(current, 'shares_outstanding', 0)
        prev_shares = _safe_get(previous, 'shares_outstanding', 0)
        details['no_dilution'] = int(curr_shares <= prev_shares and prev_shares > 0)
        score += details['no_dilution']

        # Gross margin - skip if revenue is 0 (banks use interest income, not traditional revenue)
        curr_revenue = _safe_get(current, 'revenue', 0)
        prev_revenue = _safe_get(previous, 'revenue', 0)
        if curr_revenue > 0 and prev_revenue > 0:
            curr_gm = _safe_divide(_safe_get(current, 'gross_profit', 0), curr_revenue, 0.0)
            prev_gm = _safe_divide(_safe_get(previous, 'gross_profit', 0), prev_revenue, 0.0)
            details['gross_margin_improved'] = int(curr_gm > prev_gm)
        else:
            # For banks: use net interest margin improvement via ROA improvement (already counted)
            details['gross_margin_improved'] = details.get('roa_improved', 0)
        score += details['gross_margin_improved']

        # Asset turnover - skip if revenue is 0 (banks)
        if curr_revenue > 0 and prev_revenue > 0:
            curr_turnover = _safe_divide(curr_revenue, _safe_get(current, 'total_assets', 1), 0.0)
            prev_turnover = _safe_divide(prev_revenue, _safe_get(previous, 'total_assets', 1), 0.0)
            details['asset_turnover_improved'] = int(curr_turnover > prev_turnover)
        else:
            # For banks: use ROA as proxy for efficiency improvement
            details['asset_turnover_improved'] = details.get('roa_improved', 0)
        score += details['asset_turnover_improved']
    else:
        for k in ['roa_improved', 'cfo_gt_net_income', 'leverage_improved',
                  'current_ratio_improved', 'no_dilution', 'gross_margin_improved', 'asset_turnover_improved']:
            details[k] = 0

    rating = 'Very Strong' if score >= 8 else 'Strong' if score >= 6 else 'Average' if score >= 4 else 'Weak'
    return {'score': score, 'rating': rating, 'details': details}


def _is_financial_institution(data: Dict[str, Any]) -> bool:
    """Detect if company is a bank/financial institution based on balance sheet structure."""
    if data is None:
        return False
    ta = _safe_get(data, 'total_assets', 0)
    tl = _safe_get(data, 'total_liabilities', 0)
    revenue = _safe_get(data, 'revenue', 0)
    # Banks typically have: very high leverage (liabilities > 85% assets) AND low/zero traditional revenue
    if ta > 0 and tl > 0:
        leverage_ratio = tl / ta
        revenue_to_assets = revenue / ta if revenue else 0
        # Banks: very high leverage + low revenue-to-assets ratio
        if leverage_ratio > 0.85 and revenue_to_assets < 0.1:
            return True
    return False


def calculate_altman_z_score(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate Altman Z-Score: Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5

    Note: Altman Z-Score is NOT designed for financial institutions (banks, insurance).
    For banks, returns a modified estimate based on available metrics.
    """
    if data is None:
        return {'z_score': 0.0, 'zone': 'distress', 'components': {}}

    ta = max(_safe_get(data, 'total_assets', 1), 1)
    tl = max(_safe_get(data, 'total_liabilities', 1), 1)
    te = _safe_get(data, 'total_equity', 0)

    # Check if this is a financial institution
    is_bank = _is_financial_institution(data)

    if is_bank:
        # For banks: use simplified solvency metrics
        # Capital adequacy proxy: equity / total_assets
        # This is a rough approximation since true CAR requires risk-weighted assets
        capital_ratio = _safe_divide(te, ta, 0.0)
        roa = _safe_get(data, 'roa', 0)
        if isinstance(roa, (int, float)) and roa > 1:  # Assume percentage
            roa = roa / 100

        # Simplified bank health score (0-5 range mapped to Z-Score equivalent)
        # Capital ratio > 10% is generally considered healthy for banks
        bank_score = 0.0
        if capital_ratio >= 0.12:  # CAR > 12%
            bank_score += 2.0
        elif capital_ratio >= 0.08:  # CAR 8-12%
            bank_score += 1.2

        # ROA > 1% is good for banks
        if roa >= 0.015:
            bank_score += 1.5
        elif roa >= 0.01:
            bank_score += 1.0
        elif roa > 0:
            bank_score += 0.5

        zone = 'safe' if bank_score >= 2.5 else 'grey' if bank_score >= 1.5 else 'distress'
        return {
            'z_score': round(bank_score, 2),
            'zone': zone,
            'is_bank': True,
            'components': {
                'capital_ratio': round(capital_ratio, 3),
                'roa': round(roa, 4) if roa else 0,
                'note': 'Modified score for financial institution'
            }
        }

    # Standard Altman Z-Score for non-financial companies
    x1 = _safe_divide(_safe_get(data, 'current_assets', 0) - _safe_get(data, 'current_liabilities', 0), ta, 0.0)
    x2 = _safe_divide(_safe_get(data, 'retained_earnings', 0), ta, 0.0)
    x3 = _safe_divide(_safe_get(data, 'ebit') or _safe_get(data, 'operating_profit', 0), ta, 0.0)
    mc = _safe_get(data, 'market_cap')
    x4 = _safe_divide(mc, tl, 0.0) if mc else _safe_divide(te, tl, 0.0)
    x5 = _safe_divide(_safe_get(data, 'revenue', 0), ta, 0.0)
    z_score = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
    zone = 'safe' if z_score > 2.99 else 'grey' if z_score >= 1.81 else 'distress'
    return {'z_score': round(z_score, 2), 'zone': zone,
            'components': {k: round(v, 3) for k, v in zip(['x1', 'x2', 'x3', 'x4', 'x5'], [x1, x2, x3, x4, x5])}}


def get_financial_health_summary(current: Dict[str, Any], previous: Optional[Dict[str, Any]] = None,
                                 market_cap: Optional[float] = None) -> Dict[str, Any]:
    """Convenience function combining Piotroski F-Score and Altman Z-Score"""
    piotroski = calculate_piotroski_f_score(current, previous)
    altman_input = current.copy() if current else {}
    if market_cap:
        altman_input['market_cap'] = market_cap
    altman = calculate_altman_z_score(altman_input)
    return {'piotroski': piotroski, 'altman': altman}


if __name__ == "__main__":
    print("=== Financial Health Scorer Test ===\n")
    curr = {'roa': 0.12, 'cfo': 150e9, 'net_income': 120e9, 'total_assets': 1000e9, 'long_term_debt': 300e9,
            'current_assets': 400e9, 'current_liabilities': 200e9, 'shares_outstanding': 100e6,
            'gross_profit': 200e9, 'revenue': 500e9, 'retained_earnings': 150e9, 'ebit': 130e9,
            'total_liabilities': 400e9, 'total_equity': 600e9}
    prev = {'roa': 0.10, 'total_assets': 950e9, 'long_term_debt': 320e9, 'current_assets': 380e9,
            'current_liabilities': 210e9, 'shares_outstanding': 100e6, 'gross_profit': 180e9, 'revenue': 480e9}

    pio = calculate_piotroski_f_score(curr, prev)
    print(f"1. Piotroski: {pio['score']}/9 ({pio['rating']})\n   Details: {pio['details']}\n")

    alt = calculate_altman_z_score(curr)
    print(f"2. Altman: {alt['z_score']} ({alt['zone']})\n   Components: {alt['components']}\n")

    summ = get_financial_health_summary(curr, prev, market_cap=1200e9)
    print(f"3. Combined: Piotroski={summ['piotroski']['score']}/9, Altman={summ['altman']['z_score']} ({summ['altman']['zone']})\n")

    print(f"4. None test: {calculate_piotroski_f_score(None)}, {calculate_altman_z_score(None)}\n")
    print("✅ All tests completed successfully")
