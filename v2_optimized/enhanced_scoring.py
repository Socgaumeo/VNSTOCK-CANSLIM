"""Bridge module: integrates financial_health_scorer + valuation-scorer into Module 3.

Provides EnhancedScorer with quick_health_check() that Module 3 calls
to populate Piotroski, Altman Z, PEG fields on each StockCandidate.
"""

import importlib.util
import os
from typing import Dict, Optional, Any

from financial_health_scorer import calculate_piotroski_f_score, calculate_altman_z_score

# Load kebab-case valuation module
_valuation_module = None
_val_path = os.path.join(os.path.dirname(__file__), "valuation-scorer.py")
if os.path.isfile(_val_path):
    spec = importlib.util.spec_from_file_location("valuation_scorer", _val_path)
    _valuation_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_valuation_module)


class EnhancedScorer:
    """Wraps Piotroski F-Score, Altman Z-Score, and PEG Ratio calculations."""

    def quick_health_check(
        self,
        current: Dict[str, Any],
        previous: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run Piotroski + Altman + PEG and return combined result dict.

        Args:
            current: Dict with keys like roa, cfo, net_income, total_assets,
                     total_liabilities, total_equity, pe, market_cap, etc.
            previous: Optional prior-period dict for YoY Piotroski comparison.

        Returns:
            Dict with piotroski_score, piotroski_rating, altman_z_score,
            altman_zone, peg_ratio, peg_rating.
        """
        result: Dict[str, Any] = {
            "piotroski_score": 0,
            "piotroski_rating": "N/A",
            "altman_z_score": 0.0,
            "altman_zone": "",
            "peg_ratio": None,
            "peg_rating": None,
        }

        # ── Piotroski F-Score ──
        try:
            pio = calculate_piotroski_f_score(current, previous)
            result["piotroski_score"] = pio.get("score", 0)
            result["piotroski_rating"] = pio.get("rating", "N/A")
        except Exception:
            pass

        # ── Altman Z-Score ──
        try:
            alt = calculate_altman_z_score(current)
            result["altman_z_score"] = alt.get("z_score", 0.0)
            result["altman_zone"] = alt.get("zone", "")
        except Exception:
            pass

        # ── PEG Ratio ──
        try:
            if _valuation_module and current.get("pe"):
                eps_values = current.get("eps_values", [])
                if not eps_values:
                    # Approximate from EPS growth YoY if available
                    eps_growth = current.get("eps_growth_yoy", 0)
                    if eps_growth and eps_growth > 0:
                        pe = current["pe"]
                        peg = pe / eps_growth if eps_growth != 0 else None
                        if peg is not None:
                            result["peg_ratio"] = round(peg, 2)
                            result["peg_rating"] = _valuation_module.get_peg_rating(peg)
                else:
                    peg_result = _valuation_module.calculate_peg_ratio(
                        current["pe"], eps_values, len(eps_values)
                    )
                    if peg_result.get("peg_ratio") is not None:
                        result["peg_ratio"] = round(peg_result["peg_ratio"], 2)
                        result["peg_rating"] = peg_result.get("rating", "N/A")
        except Exception:
            pass

        return result


def get_enhanced_scorer() -> EnhancedScorer:
    """Factory function expected by module3_stock_screener_v1.py."""
    return EnhancedScorer()
