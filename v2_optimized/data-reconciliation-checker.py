#!/usr/bin/env python3
"""
Data Reconciliation Checker
Diagnostic tool for validating computed financial ratios against provided values.
Run occasionally to verify data quality, not integrated in main pipeline.
"""

from typing import Optional

# Metric formulas for reference
FORMULAS = {
    'roe': 'net_income / total_equity',
    'roa': 'net_income / total_assets',
    'net_profit_margin': 'net_income / abs(revenue)',
    'gross_margin': 'gross_profit / abs(revenue)',
    'current_ratio': 'current_assets / current_liabilities',
    'quick_ratio': '(current_assets - inventory) / current_liabilities',
    'debt_to_equity': 'total_liabilities / total_equity',
    'asset_turnover': 'abs(revenue) / total_assets',
}

# Tolerance thresholds by metric type
TOLERANCES = {
    'roe': 0.05, 'roa': 0.05, 'current_ratio': 0.05,
    'quick_ratio': 0.05, 'debt_to_equity': 0.05, 'asset_turnover': 0.05,
    'net_profit_margin': 0.03, 'gross_margin': 0.03,
}


def _safe_divide(a: float, b: float) -> Optional[float]:
    """Return a/b or None if b is 0/None."""
    if a is None or b is None or b == 0:
        return None
    return a / b


def compute_ratio(metric: str, income: dict, balance: dict, cash_flow: dict = None) -> Optional[float]:
    """Compute financial ratio from raw statement data."""
    if metric == 'roe':
        return _safe_divide(income.get('net_income'), balance.get('total_equity'))
    elif metric == 'roa':
        return _safe_divide(income.get('net_income'), balance.get('total_assets'))
    elif metric == 'net_profit_margin':
        revenue = income.get('revenue')
        return _safe_divide(income.get('net_income'), abs(revenue)) if revenue is not None else None
    elif metric == 'gross_margin':
        revenue = income.get('revenue')
        return _safe_divide(income.get('gross_profit'), abs(revenue)) if revenue is not None else None
    elif metric == 'current_ratio':
        return _safe_divide(balance.get('current_assets'), balance.get('current_liabilities'))
    elif metric == 'quick_ratio':
        current_assets = balance.get('current_assets')
        if current_assets is None:
            return None
        return _safe_divide(current_assets - balance.get('inventory', 0), balance.get('current_liabilities'))
    elif metric == 'debt_to_equity':
        return _safe_divide(balance.get('total_liabilities'), balance.get('total_equity'))
    elif metric == 'asset_turnover':
        revenue = income.get('revenue')
        return _safe_divide(abs(revenue), balance.get('total_assets')) if revenue is not None else None
    return None


def reconcile_metric(metric: str, computed: Optional[float], provided: Optional[float],
                     tolerance: float = 0.05) -> dict:
    """Compare computed vs provided values. Returns status: OK/WARN/FAIL/MISSING."""
    if computed is None or provided is None:
        return {'metric': metric, 'computed': computed, 'provided': provided,
                'delta_pct': None, 'status': 'MISSING', 'formula': FORMULAS.get(metric, 'unknown')}

    delta_pct = (100.0 if computed != 0 else 0.0) if provided == 0 else abs(computed - provided) / abs(provided) * 100
    status = 'OK' if delta_pct < tolerance * 100 else ('WARN' if delta_pct < tolerance * 200 else 'FAIL')

    return {'metric': metric, 'computed': round(computed, 4) if computed is not None else None,
            'provided': round(provided, 4) if provided is not None else None,
            'delta_pct': round(delta_pct, 2), 'status': status, 'formula': FORMULAS.get(metric, 'unknown')}


def reconcile_fundamentals(income: dict, balance: dict, cash_flow: dict, ratios: dict) -> dict:
    """Batch reconciliation of all supported metrics."""
    results = []
    summary = {'total': 0, 'ok': 0, 'warn': 0, 'fail': 0, 'missing': 0}

    for metric in FORMULAS.keys():
        computed = compute_ratio(metric, income, balance, cash_flow)
        provided = ratios.get(metric)
        tolerance = TOLERANCES.get(metric, 0.05)
        result = reconcile_metric(metric, computed, provided, tolerance)
        results.append(result)
        summary['total'] += 1
        status = result['status'].lower()
        if status in summary:
            summary[status] += 1

    return {'results': results, 'summary': summary}


if __name__ == "__main__":
    print("=" * 80)
    print("Data Reconciliation Checker - Test Run")
    print("=" * 80)

    income = {'revenue': 1000, 'net_income': 150, 'gross_profit': 350, 'cost_of_goods_sold': 650}
    balance = {'total_assets': 5000, 'total_equity': 2000, 'total_liabilities': 3000,
               'current_assets': 1500, 'current_liabilities': 1000, 'inventory': 300}
    ratios = {'roe': 0.075, 'roa': 0.032, 'net_profit_margin': 0.15, 'gross_margin': 0.35,
              'current_ratio': 1.5, 'quick_ratio': 1.2, 'debt_to_equity': 1.6, 'asset_turnover': None}

    result = reconcile_fundamentals(income, balance, {}, ratios)

    print(f"\n{'Metric':<20} {'Computed':<12} {'Provided':<12} {'Delta %':<10} {'Status':<8}")
    print("-" * 80)
    for r in result['results']:
        c = f"{r['computed']:.4f}" if r['computed'] is not None else "None"
        p = f"{r['provided']:.4f}" if r['provided'] is not None else "None"
        d = f"{r['delta_pct']:.2f}%" if r['delta_pct'] is not None else "N/A"
        print(f"{r['metric']:<20} {c:<12} {p:<12} {d:<10} {r['status']:<8}")

    s = result['summary']
    print("\n" + "=" * 80)
    print(f"Summary: Total={s['total']}, OK={s['ok']}, WARN={s['warn']}, FAIL={s['fail']}, MISSING={s['missing']}")
    print("=" * 80)
