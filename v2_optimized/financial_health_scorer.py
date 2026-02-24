"""Financial Health Scoring: Piotroski F-Score & Altman Z-Score for Vietnam market"""
from typing import Dict, Optional, Any

def _safe_get(data: Dict[str, Any], key: str, default: Optional[float] = None) -> Optional[float]:
    if data is None:
        return default
    val = data.get(key, default)
    return val if val is not None else default

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
        details['cfo_gt_net_income'] = int(cfo >= 0.8 * net_income)
        score += details['roa_improved'] + details['cfo_gt_net_income']

        curr_debt = _safe_get(current, 'long_term_debt') or _safe_get(current, 'total_liabilities', 0)
        prev_debt = _safe_get(previous, 'long_term_debt') or _safe_get(previous, 'total_liabilities', 0)
        curr_ratio = curr_debt / _safe_get(current, 'total_assets', 1)
        prev_ratio = prev_debt / _safe_get(previous, 'total_assets', 1)
        details['leverage_improved'] = int(curr_ratio < prev_ratio)
        score += details['leverage_improved']

        curr_cr = _safe_get(current, 'current_assets', 0) / _safe_get(current, 'current_liabilities', 1)
        prev_cr = _safe_get(previous, 'current_assets', 0) / _safe_get(previous, 'current_liabilities', 1)
        details['current_ratio_improved'] = int(curr_cr > prev_cr)
        score += details['current_ratio_improved']

        curr_shares = _safe_get(current, 'shares_outstanding', 0)
        prev_shares = _safe_get(previous, 'shares_outstanding', 0)
        details['no_dilution'] = int(curr_shares <= prev_shares and prev_shares > 0)
        score += details['no_dilution']

        curr_gm = _safe_get(current, 'gross_profit', 0) / _safe_get(current, 'revenue', 1)
        prev_gm = _safe_get(previous, 'gross_profit', 0) / _safe_get(previous, 'revenue', 1)
        details['gross_margin_improved'] = int(curr_gm > prev_gm)
        score += details['gross_margin_improved']

        curr_turnover = _safe_get(current, 'revenue', 0) / _safe_get(current, 'total_assets', 1)
        prev_turnover = _safe_get(previous, 'revenue', 0) / _safe_get(previous, 'total_assets', 1)
        details['asset_turnover_improved'] = int(curr_turnover > prev_turnover)
        score += details['asset_turnover_improved']
    else:
        for k in ['roa_improved', 'cfo_gt_net_income', 'leverage_improved',
                  'current_ratio_improved', 'no_dilution', 'gross_margin_improved', 'asset_turnover_improved']:
            details[k] = 0

    rating = 'Very Strong' if score >= 8 else 'Strong' if score >= 6 else 'Average' if score >= 4 else 'Weak'
    return {'score': score, 'rating': rating, 'details': details}


def calculate_altman_z_score(data: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate Altman Z-Score: Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5"""
    if data is None:
        return {'z_score': 0.0, 'zone': 'distress', 'components': {}}

    ta = max(_safe_get(data, 'total_assets', 1), 1)
    tl = max(_safe_get(data, 'total_liabilities', 1), 1)
    x1 = (_safe_get(data, 'current_assets', 0) - _safe_get(data, 'current_liabilities', 0)) / ta
    x2 = _safe_get(data, 'retained_earnings', 0) / ta
    x3 = (_safe_get(data, 'ebit') or _safe_get(data, 'operating_profit', 0)) / ta
    mc = _safe_get(data, 'market_cap')
    x4 = (mc / tl) if mc else (_safe_get(data, 'total_equity', 0) / tl)
    x5 = _safe_get(data, 'revenue', 0) / ta
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
