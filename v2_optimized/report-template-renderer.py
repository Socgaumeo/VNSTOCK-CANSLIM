#!/usr/bin/env python3
"""
Jinja2-based report renderer with deterministic fallback.

When AI analysis is None (AI failed), generates rule-based commentary
from market/sector/stock data. Renders Markdown via Jinja2 templates.
"""

import os
from datetime import datetime
from typing import Optional, Dict, List, Any

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


# ── Rule-based commentary helpers ────────────────────────────────────────────

def _rule_based_market_commentary(score: int, color: str, trend: str, signals: List[str]) -> str:
    """Generate deterministic market commentary from numeric data."""
    if score >= 70:
        stance = "TANG TOC - Thi truong xanh manh, co the tich cuc mo rong vi the."
        action = "Mo rong danh muc, uu tien co phieu breakout voi khoi luong lon."
    elif score >= 40:
        stance = "CHON LOC - Thi truong trung tinh/vang, can phan biet co phieu manh/yeu."
        action = "Giu nguyen vi the hien tai, mua them chi khi co tin hieu ro rang."
    else:
        stance = "PHONG THU - Thi truong do, rui ro cao, uu tien bao ve von."
        action = "Giam vi the, cat lo neu can, tranh mo them lenh moi."

    signal_summary = ""
    if signals:
        signal_summary = "\n**Tin hieu quan trong:**\n" + "\n".join(f"- {s}" for s in signals[:5])

    return (
        f"**Nhan dinh (Rule-Based):** {stance}\n\n"
        f"**Khuyến nghi hanh dong:** {action}"
        f"{signal_summary}"
    )


def _rule_based_sector_commentary(sectors: List[Dict]) -> str:
    """Generate deterministic sector commentary from phase/RS data."""
    leading = [s for s in sectors if s.get('phase', '').upper() in ('LEADING', 'IMPROVING')]
    lagging = [s for s in sectors if s.get('phase', '').upper() in ('LAGGING', 'WEAKENING')]

    focus_names = ", ".join(s.get('name', s.get('code', '')) for s in leading[:3]) or "Chua xac dinh"
    avoid_names = ", ".join(s.get('name', s.get('code', '')) for s in lagging[:3]) or "Khong co"

    return (
        f"**Tap trung:** {focus_names}\n\n"
        f"**Tranh:** {avoid_names}\n\n"
        f"*Phan tich dua tren RS Rating va Phase hien tai. "
        f"Nganh LEADING/IMPROVING la uu tien mua; LAGGING/WEAKENING nen tranh.*"
    )


def _rule_based_stock_commentary(candidate: Dict) -> str:
    """Generate deterministic stock commentary from score breakdown and pattern."""
    score = candidate.get('score_total', 0)
    pattern = candidate.get('pattern_type', 'N/A')
    rs = candidate.get('rs_rating', 0)
    eps_yoy = candidate.get('eps_yoy', 0)
    breakout_ready = candidate.get('breakout_ready', False)

    if score >= 80:
        conviction = "MANH - Diem so toan dien, day du dieu kien CANSLIM."
    elif score >= 60:
        conviction = "TRUNG BINH - Tieu du duoc, nhung can theo doi them."
    else:
        conviction = "YEU - Chi xem xet neu toan thi truong rat manh."

    pattern_note = f"Pattern '{pattern}' "
    if breakout_ready:
        pattern_note += "da san sang breakout - xem xet mua khi volume xac nhan."
    else:
        pattern_note += "dang hinh thanh - cho doi xac nhan them."

    return (
        f"**Muc do tin tuong:** {conviction}\n\n"
        f"**Pattern:** {pattern_note}\n\n"
        f"**RS {rs}** - {'Manh hon 70% thi truong.' if rs >= 70 else 'Can cai thien.'} "
        f"**EPS Y/Y {eps_yoy:+.1f}%** - {'Tang truong tot.' if eps_yoy >= 25 else 'Chua dat nguong CANSLIM.'}"
    )


# ── Renderer class ─────────────────────────────────────────────────────────────

class ReportTemplateRenderer:
    """
    Renders CANSLIM reports via Jinja2 templates.
    Falls back to rule-based commentary when ai_narratives values are None.
    """

    def __init__(self, templates_dir: Optional[str] = None):
        if not HAS_JINJA2:
            raise ImportError("jinja2 not installed. Run: pip install jinja2")

        if templates_dir is None:
            templates_dir = os.path.join(os.path.dirname(__file__), "templates")

        self.templates_dir = templates_dir
        self.env = Environment(
            loader=FileSystemLoader(templates_dir),
            autoescape=select_autoescape([]),  # Markdown, no HTML escaping
            trim_blocks=True,
            lstrip_blocks=True,
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def render(self, data: Dict[str, Any], ai_narratives: Optional[Dict[str, Any]] = None) -> str:
        """
        Render full report from structured data.

        Args:
            data: Pipeline output dict with keys: market, sectors, screener
            ai_narratives: Dict with optional 'market', 'sector', 'screener' AI text (None = use fallback)

        Returns:
            Rendered Markdown string
        """
        if ai_narratives is None:
            ai_narratives = {}

        has_ai = any(v for v in ai_narratives.values() if v)

        market_section = self._render_market_section(data.get('market', {}), ai_narratives)
        sector_section = self._render_sector_section(data.get('sectors', []), ai_narratives)
        screener_section = self._render_screener_section(data.get('screener', {}), ai_narratives)

        tmpl = self.env.get_template("base-report.md.j2")
        return tmpl.render(
            timestamp=data.get('timestamp', datetime.now().strftime('%d/%m/%Y %H:%M')),
            market_section=market_section,
            sector_section=sector_section,
            screener_section=screener_section,
            has_ai=has_ai,
        )

    # ── Section renderers ───────────────────────────────────────────────────

    def _render_market_section(self, market: Dict, ai_narratives: Dict) -> str:
        ai_text = ai_narratives.get('market')
        if not ai_text:
            ai_text = None
            rule_text = _rule_based_market_commentary(
                score=market.get('score', 50),
                color=market.get('color', 'N/A'),
                trend=market.get('trend', ''),
                signals=market.get('key_signals', []),
            )
        else:
            rule_text = ""

        tmpl = self.env.get_template("market-timing-section.md.j2")
        return tmpl.render(
            market=market,
            ai_narrative=ai_text,
            rule_based_commentary=rule_text,
        )

    def _render_sector_section(self, sectors: List[Dict], ai_narratives: Dict) -> str:
        ai_text = ai_narratives.get('sector')
        if not ai_text:
            ai_text = None
            rule_text = _rule_based_sector_commentary(sectors)
        else:
            rule_text = ""

        tmpl = self.env.get_template("sector-rotation-section.md.j2")
        return tmpl.render(
            sectors=sectors,
            ai_narrative=ai_text,
            rule_based_commentary=rule_text,
        )

    def _render_screener_section(self, screener: Dict, ai_narratives: Dict) -> str:
        top_picks = screener.get('top_picks', [])
        top_picks_detail = screener.get('top_picks_detail', [])

        # Add per-stock rule-based commentary where AI is missing
        for c in top_picks_detail:
            if not c.get('ai_analysis'):
                c['rule_based_commentary'] = _rule_based_stock_commentary(c)
            else:
                c['rule_based_commentary'] = ""

        screener_ai = ai_narratives.get('screener')

        tmpl = self.env.get_template("stock-picks-section.md.j2")
        return tmpl.render(
            stats=screener.get('stats', {}),
            top_picks=top_picks,
            top_picks_detail=top_picks_detail,
            screener_ai_summary=screener_ai,
        )


# ── Availability check ────────────────────────────────────────────────────────

def is_available() -> bool:
    """Return True if jinja2 is installed and templates exist."""
    if not HAS_JINJA2:
        return False
    templates_dir = os.path.join(os.path.dirname(__file__), "templates")
    return os.path.isdir(templates_dir)
