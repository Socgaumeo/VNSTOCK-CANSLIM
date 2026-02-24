#!/usr/bin/env python3
"""
Industry-Specific Analysis Module
Analyzes financial metrics specific to Banking, Real Estate, and Retail sectors.
"""

INDUSTRY_MAP = {
    'Ngân hàng': 'banking',
    'Bất động sản': 'real_estate',
    'Bán lẻ': 'retail',
    'Banks': 'banking',
    'Real Estate': 'real_estate',
    'Retail': 'retail',
}

# Rating thresholds
# Metric thresholds
NIM_T = [(3.5, 'excellent'), (2.5, 'good'), (1.5, 'average'), (0, 'weak')]
INV_RATIO_T = [(70, 'concentrated'), (40, 'normal'), (0, 'light')]
DE_T = [(0, 'conservative'), (1.5, 'acceptable'), (3.0, 'high_risk')]
CASH_T = [(1.5, 'strong'), (1.0, 'safe'), (0.5, 'tight'), (0, 'weak')]
GM_T = [(35, 'excellent'), (25, 'good'), (15, 'average'), (0, 'weak')]
IT_T = [(8, 'excellent'), (5, 'good'), (3, 'average'), (0, 'slow')]

RATING_POINTS = {
    'excellent': 100, 'strong': 100, 'optimal': 100, 'conservative': 100,
    'efficient': 100, 'light': 100,
    'good': 75, 'safe': 75, 'acceptable': 75, 'normal': 75,
    'average': 50,
    'weak': 25, 'slow': 25, 'high': 25, 'tight': 25, 'poor': 25,
    'concentrated': 50, 'high_risk': 25,
}


def _safe_div(a, b):
    return None if (a is None or b is None or b == 0) else a / b

def _rate(val, thresholds):
    if val is None:
        return 'unknown'
    for t, label in thresholds:
        if val >= t:
            return label
    return thresholds[-1][1] if thresholds else 'unknown'

def _rate_ci(v):
    return 'unknown' if v is None else ('excellent' if v < 40 else 'good' if v < 50 else 'average' if v < 60 else 'weak')

def _rate_ldr(v):
    return 'unknown' if v is None else ('optimal' if 80 <= v <= 90 else 'acceptable' if (70 <= v < 80 or 90 < v <= 100) else 'poor')

def _rate_dsi(v):
    return 'unknown' if v is None else ('excellent' if v < 45 else 'good' if v < 60 else 'average' if v < 90 else 'slow')


def analyze_banking(income, balance, ratios=None):
    nim = ratios.get('nim') if ratios and 'nim' in ratios else _safe_div(income.get('net_interest_income'), balance.get('total_assets'))
    nim = nim * 100 if nim else None
    ci = _safe_div(income.get('operating_expense'), income.get('operating_income'))
    ci = ci * 100 if ci else None
    ldr = _safe_div(balance.get('total_loans'), balance.get('total_deposits'))
    ldr = ldr * 100 if ldr else None
    metrics = {
        'nim': {'value': round(nim, 2) if nim else None, 'rating': _rate(nim, NIM_T)},
        'cost_to_income': {'value': round(ci, 2) if ci else None, 'rating': _rate_ci(ci)},
        'ldr': {'value': round(ldr, 2) if ldr else None, 'rating': _rate_ldr(ldr)},
    }
    points = [RATING_POINTS.get(m['rating'], 0) for m in metrics.values() if m['rating'] != 'unknown']
    return {'industry': 'banking', 'metrics': metrics, 'health_score': round(sum(points) / len(points)) if points else 0}


def analyze_real_estate(income, balance):
    inv_ratio = _safe_div(balance.get('inventory'), balance.get('total_assets'))
    inv_ratio = inv_ratio * 100 if inv_ratio else None
    de = _safe_div(balance.get('total_liabilities'), balance.get('total_equity'))
    cash_r = _safe_div((balance.get('cash', 0) + balance.get('cash_equivalents', 0)), balance.get('current_liabilities'))
    gm = _safe_div(income.get('gross_profit'), abs(income.get('revenue', 1)))
    gm = gm * 100 if gm else None
    metrics = {
        'inventory_to_assets': {'value': round(inv_ratio, 2) if inv_ratio else None, 'rating': _rate(inv_ratio, INV_RATIO_T)},
        'debt_to_equity': {'value': round(de, 2) if de else None, 'rating': _rate(de, DE_T)},
        'cash_ratio': {'value': round(cash_r, 2) if cash_r else None, 'rating': _rate(cash_r, CASH_T)},
        'gross_margin': {'value': round(gm, 2) if gm else None, 'rating': _rate(gm, GM_T)},
    }
    points = [RATING_POINTS.get(m['rating'], 0) for m in metrics.values() if m['rating'] != 'unknown']
    return {'industry': 'real_estate', 'metrics': metrics, 'health_score': round(sum(points) / len(points)) if points else 0}


def analyze_retail(income, balance):
    it = _safe_div(abs(income.get('cost_of_goods_sold', 0)), balance.get('inventory'))
    dsi = _safe_div(365, it) if it else None
    sga = _safe_div(income.get('sga_expense'), abs(income.get('revenue', 1)))
    sga = sga * 100 if sga else None
    sga_t = [(0, 'efficient'), (15, 'average'), (25, 'high')]
    metrics = {
        'inventory_turnover': {'value': round(it, 2) if it else None, 'rating': _rate(it, IT_T)},
        'dsi': {'value': round(dsi, 2) if dsi else None, 'rating': _rate_dsi(dsi)},
        'sga_percent': {'value': round(sga, 2) if sga else None, 'rating': _rate(sga, sga_t)},
    }
    points = [RATING_POINTS.get(m['rating'], 0) for m in metrics.values() if m['rating'] != 'unknown']
    return {'industry': 'retail', 'metrics': metrics, 'health_score': round(sum(points) / len(points)) if points else 0}


def get_industry_type(icb_name):
    return INDUSTRY_MAP.get(icb_name, 'general')

def analyze_industry(industry_code, income, balance, cash_flow=None, ratios=None):
    analyzers = {'banking': lambda: analyze_banking(income, balance, ratios),
                 'real_estate': lambda: analyze_real_estate(income, balance),
                 'retail': lambda: analyze_retail(income, balance)}
    return analyzers[industry_code]() if industry_code in analyzers else None


if __name__ == '__main__':
    print("=== Industry Analyzer CLI Test ===\n")

    # Test Banking
    banking_income = {'net_interest_income': 3800, 'operating_expense': 1500, 'operating_income': 3900}
    banking_balance = {'total_assets': 100000, 'total_loans': 68000, 'total_deposits': 80000}
    result = analyze_banking(banking_income, banking_balance)
    print(f"Banking: {result}\n")

    # Test Real Estate
    re_income = {'gross_profit': 3500, 'revenue': 10000}
    re_balance = {'total_assets': 50000, 'total_equity': 20000, 'total_liabilities': 30000,
                  'inventory': 25000, 'cash': 8000, 'cash_equivalents': 2000, 'current_liabilities': 8000}
    result = analyze_real_estate(re_income, re_balance)
    print(f"Real Estate: {result}\n")

    # Test Retail
    retail_income = {'cost_of_goods_sold': 40000, 'revenue': 60000, 'sga_expense': 8000}
    retail_balance = {'inventory': 5000}
    result = analyze_retail(retail_income, retail_balance)
    print(f"Retail: {result}\n")

    # Test Unknown Industry
    result = analyze_industry('general', {}, {})
    print(f"Unknown industry: {result}\n")

    print("All tests completed!")
