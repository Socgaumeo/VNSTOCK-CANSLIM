"""
DuPont Extended Analysis (5-component ROE decomposition)
ROE = Tax Burden × Interest Burden × Operating Margin × Asset Turnover × Financial Leverage
"""
from typing import Optional


def _safe_div(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """Safe division returning None if division invalid."""
    if a is None or b is None or b == 0:
        return None
    return a / b


def calculate_dupont(income: dict, balance: dict, ratios: dict = None) -> dict:
    """
    Compute 5-component DuPont decomposition of ROE.

    Args:
        income: {'net_income', 'profit_before_tax', 'operating_profit', 'revenue'}
        balance: {'total_assets', 'total_equity'}
        ratios: optional pre-computed ratios (unused, for future extension)

    Returns:
        {
            'roe': actual ROE,
            'dupont_roe': reconstructed from components,
            'components': {name: {'value': float, 'label': str}},
            'driver': strongest component name,
            'weakness': weakest component name
        }
    """
    ni = income.get('net_income')
    ebt = income.get('profit_before_tax')
    ebit = income.get('operating_profit')  # fallback to operating_profit
    rev = income.get('revenue')
    assets = balance.get('total_assets')
    equity = balance.get('total_equity')

    # Actual ROE
    roe = _safe_div(ni, equity)

    # 5 components
    tax_burden = _safe_div(ni, ebt)
    interest_burden = _safe_div(ebt, ebit)
    operating_margin = _safe_div(ebit, abs(rev) if rev else None)
    asset_turnover = _safe_div(abs(rev) if rev else None, assets)
    financial_leverage = _safe_div(assets, equity)

    components = {
        'tax_burden': {'value': tax_burden, 'label': 'NI/EBT'},
        'interest_burden': {'value': interest_burden, 'label': 'EBT/EBIT'},
        'operating_margin': {'value': operating_margin, 'label': 'EBIT/Revenue'},
        'asset_turnover': {'value': asset_turnover, 'label': 'Revenue/Assets'},
        'financial_leverage': {'value': financial_leverage, 'label': 'Assets/Equity'},
    }

    # Reconstruct ROE from product
    dupont_roe = None
    vals = [c['value'] for c in components.values()]
    if all(v is not None for v in vals):
        dupont_roe = vals[0] * vals[1] * vals[2] * vals[3] * vals[4]

    # Identify driver and weakness
    benchmarks = {
        'tax_burden': 0.80,
        'interest_burden': 0.85,
        'operating_margin': 0.10,
        'asset_turnover': 0.80,
        'financial_leverage': 2.0,
    }

    driver, weakness = None, None
    max_ratio, min_ratio = -float('inf'), float('inf')

    for name, comp in components.items():
        val = comp['value']
        bench = benchmarks[name]
        if val is not None and bench > 0:
            ratio = val / bench
            if ratio > max_ratio:
                max_ratio = ratio
                driver = name
            if ratio < min_ratio:
                min_ratio = ratio
                weakness = name

    return {
        'roe': roe,
        'dupont_roe': dupont_roe,
        'components': components,
        'driver': driver,
        'weakness': weakness,
    }


if __name__ == '__main__':
    # CLI test
    test_income = {
        'net_income': 1850,
        'profit_before_tax': 2256,
        'operating_profit': 2480,
        'revenue': 16500,
    }
    test_balance = {
        'total_assets': 13750,
        'total_equity': 10000,
    }

    result = calculate_dupont(test_income, test_balance)
    print("=== DuPont Extended Analysis ===")
    print(f"Actual ROE: {result['roe']:.4f}" if result['roe'] else "Actual ROE: N/A")
    print(f"DuPont ROE: {result['dupont_roe']:.4f}" if result['dupont_roe'] else "DuPont ROE: N/A")
    print("\nComponents:")
    for name, comp in result['components'].items():
        val_str = f"{comp['value']:.4f}" if comp['value'] is not None else "N/A"
        print(f"  {comp['label']:20s}: {val_str}")
    print(f"\nDriver: {result['driver']}")
    print(f"Weakness: {result['weakness']}")

    # Verify product
    if result['dupont_roe'] and result['roe']:
        diff_pct = abs(result['dupont_roe'] - result['roe']) / result['roe'] * 100
        print(f"\nDifference: {diff_pct:.2f}% (should be <5%)")
        print("✅ PASS" if diff_pct < 5 else "❌ FAIL")
