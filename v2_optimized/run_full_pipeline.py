#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                 CANSLIM FULL PIPELINE - TẤT CẢ 3 MODULES                      ║
║            Gộp Market Timing + Sector Rotation + Stock Screener               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  OUTPUT: 1 file Markdown duy nhất với đầy đủ thông tin                        ║
║  - Module 1: Market Timing (Traffic Light, Volume Profile)                   ║
║  - Module 2: Sector Rotation (Top ngành, RS Ranking)                         ║
║  - Module 3: Stock Screener (CANSLIM, Pattern, News, AI Analysis)            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Cách sử dụng:
    python run_full_pipeline.py
"""

import os
import sys
import time
import importlib.util
from datetime import datetime
from typing import Dict, List, Optional

# ── Patch vnai rate limit: prevent process kill on rate limit ──
def _patch_vnai_rate_limit():
    """
    vnai's CleanErrorContext calls sys.exit() on RateLimitExceeded,
    killing the entire process. Patch it to sleep + retry instead.
    """
    try:
        from vnai.beam import quota
        import time as _time

        # 1. Patch CleanErrorContext.__exit__ — the actual killer
        #    Original: catches RateLimitExceeded → sys.exit() (kills process)
        #    Patched:  catches RateLimitExceeded → sleep 60s → suppress exception
        def _safe_exit(self, exc_type, exc_val, exc_tb):
            if exc_type is quota.RateLimitExceeded:
                msg = str(exc_val)
                # Extract wait time from error message (e.g., "thử lại sau 48 giây")
                wait = 60
                import re
                m = re.search(r'(\d+)\s*giây', msg)
                if m:
                    wait = int(m.group(1)) + 5  # Add 5s buffer
                print(f"\n   ⏳ VCI rate limited, waiting {wait}s... ({msg})", flush=True)
                _time.sleep(wait)
                return True  # Suppress the exception (don't kill process)
            return False

        quota.CleanErrorContext.__exit__ = _safe_exit

        # 2. Increase guardian tier limits to reduce false triggers
        guardian = quota.guardian
        guardian._tier_limits = {
            "free": {"min": 600, "hour": 36000},
            "golden": {"min": 6000, "hour": 360000},
            "diamond": {"min": 60000, "hour": 3600000},
        }
        try:
            _orig_get_limits = guardian._get_tier_limits
            def _patched_get_limits():
                tier = guardian._get_current_tier()
                return guardian._tier_limits.get(tier, {"min": 6000, "hour": 360000})
            guardian._get_tier_limits = _patched_get_limits
        except AttributeError:
            pass  # _get_tier_limits doesn't exist in this version

        print("✓ vnai rate limit patch: sleep+retry instead of process kill")
    except Exception as e:
        print(f"⚠️ vnai patch skipped: {e}")

_patch_vnai_rate_limit()

# Import config
from config import get_config

# Import modules
from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified as create_m1_config
from module2_sector_rotation_v3 import SectorRotationModule, create_config_from_unified as create_m2_config
from module3_stock_screener_v1 import StockScreenerModule, create_config_from_unified as create_m3_config
from email_notifier import EmailNotifier
from history_manager import HistoryManager
from database.signal_store import SignalStore


# Load kebab-case modules dynamically
def _load_kebab_module(module_path: str, module_name: str):
    """Helper to import kebab-case module files."""
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    except Exception as e:
        print(f"⚠️ Could not load {module_name}: {e}")
    return None


# Load context memo module
_memo_module = _load_kebab_module(
    os.path.join(os.path.dirname(__file__), "context-memo.py"),
    "context_memo"
)

# Load template renderer (optional - requires jinja2)
_template_renderer_module = _load_kebab_module(
    os.path.join(os.path.dirname(__file__), "report-template-renderer.py"),
    "report_template_renderer"
)

# Try loading new modules
_dupont_module = _load_kebab_module(
    os.path.join(os.path.dirname(__file__), "dupont-analyzer.py"),
    "dupont_analyzer"
)
_risk_module = _load_kebab_module(
    os.path.join(os.path.dirname(__file__), "risk-metrics-calculator.py"),
    "risk_metrics_calculator"
)
_news_hub_module = _load_kebab_module(
    os.path.join(os.path.dirname(__file__), "news-hub.py"),
    "news_hub"
)
_asset_tracker_module = _load_kebab_module(
    os.path.join(os.path.dirname(__file__), "asset-tracker.py"),
    "asset_tracker"
)
_bond_lab_module = _load_kebab_module(
    os.path.join(os.path.dirname(__file__), "bond-lab.py"),
    "bond_lab"
)


def calculate_dynamic_sl_tp(candidate, market_score: int) -> dict:
    """
    Tính SL/TP động dựa trên điều kiện thị trường và cổ phiếu
    
    Args:
        candidate: Stock candidate với technical, pattern data
        market_score: 0-100 market score
        
    Returns:
        Dict với stop_loss, target_1, target_2, risk_reward
    """
    price = candidate.technical.price
    buy_point = candidate.pattern.buy_point if candidate.pattern.buy_point > 0 else price * 1.02
    
    # ATR-based calculation (default 3% nếu chưa có)
    atr_pct = getattr(candidate.technical, 'atr_pct', 3.0) / 100  # Convert to decimal
    if atr_pct <= 0:
        atr_pct = 0.03  # Default 3%
    
    # === MARKET SCORE ADJUSTMENT ===
    if market_score >= 60:     # XANH - Tấn công
        sl_mult = 2.0          # SL = 2x ATR (rộng hơn)
        tp_mult = 3.5          # TP = 3.5x ATR
        mode = "Xanh-Tấn công"
    elif market_score >= 40:   # VÀNG - Phòng thủ
        sl_mult = 1.5          # SL = 1.5x ATR
        tp_mult = 2.5          # TP = 2.5x ATR
        mode = "Vàng-Phòng thủ"
    else:                       # ĐỎ - Thận trọng
        sl_mult = 1.0          # SL = 1x ATR (chặt)
        tp_mult = 2.0          # TP = 2x ATR
        mode = "Đỏ-Thận trọng"
    
    # === PATTERN QUALITY BONUS ===
    pattern_quality = candidate.pattern.pattern_quality
    if pattern_quality >= 80:
        tp_mult += 0.5    # Pattern đẹp → TP xa hơn
    
    # === VOLUME CONFIRMATION BONUS ===
    if getattr(candidate.pattern, 'breakout_ready', False):
        tp_mult += 0.5    # Breakout Ready → TP xa hơn
        sl_mult += 0.3    # Cho room chạy
    elif getattr(candidate.pattern, 'has_shakeout', False) or getattr(candidate.pattern, 'has_dryup', False):
        tp_mult += 0.25
    
    # === CALCULATE FINAL VALUES ===
    sl_pct = atr_pct * sl_mult
    tp_pct = atr_pct * tp_mult
    
    # Clamp values
    sl_pct = max(0.03, min(0.10, sl_pct))   # 3% - 10%
    tp_pct = max(0.10, min(0.35, tp_pct))   # 10% - 35%
    
    stop_loss = buy_point * (1 - sl_pct)
    target_1 = buy_point * (1 + tp_pct)
    target_2 = buy_point * (1 + tp_pct * 1.3)  # +30% thêm
    
    risk_reward = tp_pct / sl_pct if sl_pct > 0 else 2.0
    
    return {
        'stop_loss': stop_loss,
        'stop_loss_pct': sl_pct * 100,
        'target_1': target_1,
        'target_1_pct': tp_pct * 100,
        'target_2': target_2,
        'target_2_pct': tp_pct * 1.3 * 100,
        'risk_reward': risk_reward,
        'atr_pct': atr_pct * 100,
        'sl_mult': sl_mult,
        'tp_mult': tp_mult,
        'mode': mode,
        'rationale': f"ATR={atr_pct*100:.1f}% | {mode} | SL {sl_mult}x | TP {tp_mult}x"
    }


class FullPipelineRunner:
    """Chạy toàn bộ pipeline và gộp output"""
    
    def __init__(self):
        self.config = get_config()
        self.output_dir = self.config.output.OUTPUT_DIR
        self.timestamp = datetime.now()
        
        # Results
        self.market_report = None
        self.sector_report = None
        self.screener_report = None
        self.mid_session_data = None  # Mid-session data for comparison
        self.memo = None  # ContextMemo reference for OPS data in reports
    
    def run(self, target_sectors: List[str] = None) -> str:
        """
        Chạy toàn bộ pipeline
        
        Args:
            target_sectors: Danh sách ngành để scan (optional, sẽ lấy từ Module 2)
        """
        print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🚀 CANSLIM FULL PIPELINE 🚀                               ║
║              Market Timing → Sector Rotation → Stock Screener                ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """)
        
        # ══════════════════════════════════════════════════════════════════════
        # INIT CONTEXT MEMO
        # ══════════════════════════════════════════════════════════════════════
        memo = None
        if _memo_module:
            memo = _memo_module.ContextMemo()
            memo.clear()
            self.memo = memo
            print("✓ Context memo initialized")

        # ══════════════════════════════════════════════════════════════════════
        # PREPARE HISTORY CONTEXT
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("📜 FETCHING HISTORY CONTEXT")
        print("="*80)
        
        history_manager = HistoryManager(self.output_dir)
        history_context = history_manager.get_ai_context_v2()  # V2 with What-If, RS trends
        print("✓ History context loaded (V2 Enhanced).")
        
        # Load mid-session data if available
        self.mid_session_data = history_manager.get_mid_session_data()
        mid_session_context = ""
        if self.mid_session_data:
            mid_session_context = history_manager.get_mid_session_context()
            print(f"✓ Mid-session data found: {self.mid_session_data.get('timestamp', 'N/A')}")
        else:
            print("ℹ️ No mid-session data available for today.")
        
        # Combine contexts for AI
        combined_context = f"{mid_session_context}\n{history_context}"

        # ══════════════════════════════════════════════════════════════════════
        # BOND LAB: Fetch VN10Y yield and compute bond health score
        # ══════════════════════════════════════════════════════════════════════
        if _bond_lab_module:
            try:
                lab = _bond_lab_module.BondLab()
                new_yields = lab.fetch_and_store()
                bond_health = lab.get_bond_health_score()
                if memo:
                    memo.save("bonds", {
                        "bond_health": bond_health,
                        "yield_curve": lab.get_yield_curve(),
                    })
                print(
                    f"\n✓ Bond Lab: VN10Y={bond_health.get('vn10y_yield', 'N/A')}%, "
                    f"health={bond_health.get('score', 0)} "
                    f"({bond_health.get('interpretation', '')})"
                )
            except Exception as e:
                print(f"  Bond Lab error (skipping): {e}")

        # ══════════════════════════════════════════════════════════════════════
        # MODULE 1: MARKET TIMING
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("📊 MODULE 1: MARKET TIMING")
        print("="*80)
        
        m1_config = create_m1_config()
        m1_config.SAVE_REPORT = False  # Không save riêng
        
        m1_module = MarketTimingModule(m1_config)
        self.market_report = m1_module.run(combined_context, memo=memo)
        
        # ══════════════════════════════════════════════════════════════════════
        # MODULE 2: SECTOR ROTATION
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("🏭 MODULE 2: SECTOR ROTATION")
        print("="*80)
        
        m2_config = create_m2_config()
        m2_config.SAVE_REPORT = False  # Không save riêng
        
        m2_module = SectorRotationModule(m2_config)
        self.sector_report = m2_module.run(memo=memo)
        
        # Xác định target sectors từ Module 2
        # LOGIC MỚI: Scan TẤT CẢ các ngành mạnh hoặc đang improving
        if not target_sectors and self.sector_report:
            target_sectors = []
            
            print("\n📊 PHÂN TÍCH NGÀNH ĐỂ SCAN:")
            if hasattr(self.sector_report, 'sectors') and self.sector_report.sectors:
                for sector in self.sector_report.sectors:
                    if hasattr(sector, 'code'):
                        sector_code = sector.code
                        rs_rating = getattr(sector, 'rs_rating', 0)
                        phase = getattr(sector, 'phase', None)
                        rs_trend = getattr(sector, 'rs_trend', '')
                        
                        # Lấy phase name (xử lý cả Enum lẫn string)
                        if hasattr(phase, 'name'):
                            phase_name = phase.name  # Enum -> 'LEADING', 'IMPROVING', etc
                        else:
                            phase_name = str(phase) if phase else ''
                        
                        # Scan ngành nếu:
                        # 1. Đang LEADING hoặc IMPROVING
                        # 2. Hoặc có RS >= 50 (top half)
                        # 3. Hoặc RS trend đang IMPROVING (có thể sắp bứt phá)
                        should_scan = (
                            phase_name in ['LEADING', 'IMPROVING'] or
                            rs_rating >= 50 or
                            'IMPROVING' in rs_trend.upper()
                        )
                        
                        if should_scan:
                            target_sectors.append(sector_code)
                            print(f"   ✓ {sector_code}: RS={rs_rating}, Phase={phase_name}, Trend={rs_trend}")
                        else:
                            print(f"   ✗ {sector_code}: RS={rs_rating}, Phase={phase_name} - SKIP (yếu)")
            
            # Fallback nếu không có ngành nào
            if not target_sectors:
                target_sectors = ['VNFIN', 'VNREAL', 'VNCOND', 'VNCONS', 'VNMAT', 'VNIT', 'VNHEAL']
                print("   ⚠️ Fallback: Scan tất cả ngành")
            
            print(f"\n📋 TARGET SECTORS ({len(target_sectors)}): {', '.join(target_sectors)}")
        
        # ══════════════════════════════════════════════════════════════════════
        # NEWS HUB: Crawl & refresh market news sentiment
        # ══════════════════════════════════════════════════════════════════════
        news_hub = None
        if _news_hub_module:
            try:
                hub = _news_hub_module.NewsHub()
                new_count = hub.refresh()
                print(f"\n✓ News Hub: {new_count} new articles fetched")
                if memo:
                    memo.save("news", hub.get_market_sentiment())
                news_hub = hub
            except Exception as e:
                print(f"⚠️ News Hub failed: {e}")

        # ══════════════════════════════════════════════════════════════════════
        # ASSET TRACKER: Fetch commodity prices and derive macro signal
        # ══════════════════════════════════════════════════════════════════════
        if _asset_tracker_module:
            try:
                tracker = _asset_tracker_module.AssetTracker()
                new_assets = tracker.fetch_and_store()
                macro_signal = tracker.get_macro_signal()
                if memo:
                    memo.save("assets", {"macro_signal": macro_signal, "summary": tracker.get_asset_summary()})
                print(f"  Asset Tracker: {new_assets} assets updated, signal={macro_signal.get('signal', 'N/A')}")
            except Exception as e:
                print(f"  Asset Tracker error (skipping): {e}")

        # ══════════════════════════════════════════════════════════════════════
        # MODULE 3: STOCK SCREENER
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("📈 MODULE 3: STOCK SCREENER")
        print("="*80)

        # Build market context từ Module 1 & 2
        market_context = self._build_market_context()

        m3_config = create_m3_config()
        m3_config.SAVE_REPORT = False  # Không save riêng

        m3_module = StockScreenerModule(m3_config)
        self.screener_report = m3_module.run(
            target_sectors=target_sectors,
            market_context=market_context,
            history_context=history_context,
            memo=memo,
            news_hub=news_hub
        )
        
        # ══════════════════════════════════════════════════════════════════════
        # SAVE SIGNALS TO DATABASE
        # ══════════════════════════════════════════════════════════════════════
        self._save_signals_to_db()

        # ══════════════════════════════════════════════════════════════════════
        # GENERATE COMBINED OUTPUT
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("📝 GENERATING COMBINED REPORT")
        print("="*80)
        
        # Use combined report (richer: includes Financial Health, DuPont, OPS sections)
        combined_report = self._generate_combined_report()
        output_file = self._save_report(combined_report)
        
        print(f"\n✅ HOÀN THÀNH!")
        print(f"📄 Output file: {output_file}")
        
        # Send Email
        try:
            notifier = EmailNotifier()
            if notifier.config.ENABLED:
                notifier.send_report(combined_report, output_file)
        except Exception as e:
            print(f"⚠️ Email Error: {e}")
        
        return output_file
    
    def _save_signals_to_db(self):
        """Persist screener signals to signals_history for backtesting."""
        if not self.screener_report or not self.screener_report.top_picks:
            print("⚠️ No signals to save")
            return

        try:
            store = SignalStore()
            market_score = self.market_report.market_score if self.market_report else 50
            today = self.timestamp.strftime('%Y-%m-%d')
            signals = []
            for c in self.screener_report.top_picks:
                price = c.technical.price
                buy_point = c.pattern.buy_point if c.pattern.buy_point > 0 else price * 1.02
                sl_tp = calculate_dynamic_sl_tp(c, market_score)
                signals.append({
                    'date': today,
                    'symbol': c.symbol,
                    'signal': c.signal.value,
                    'score_total': c.score_total,
                    'score_fundamental': c.score_fundamental,
                    'score_technical': c.score_technical,
                    'score_pattern': c.score_pattern,
                    'rs_rating': c.technical.rs_rating,
                    'pattern_type': c.pattern.pattern_type.value,
                    'buy_point': buy_point,
                    'stop_loss': sl_tp['stop_loss'],
                    'target': sl_tp['target_1'],
                })
            saved = store.record_signals_batch(signals)
            print(f"\n💾 Saved {saved} signals to database")

            # Save market snapshot
            if self.market_report:
                store.save_market_snapshot(
                    date=today,
                    market_score=self.market_report.market_score,
                    market_color=self.market_report.traffic_light if hasattr(self.market_report, 'traffic_light') else '',
                    distribution_days=getattr(self.market_report, 'distribution_days', 0),
                )
                print(f"💾 Saved market snapshot (score={self.market_report.market_score})")
        except Exception as e:
            print(f"⚠️ Error saving signals to DB: {e}")

    def _build_market_context(self) -> Dict:
        """Xây dựng market context từ Module 1 & 2"""
        context = {
            'traffic_light': 'N/A',
            'market_score': 50,
            'distribution_days': 0,
            'leading_sectors': [],
        }
        
        if self.market_report:
            context['traffic_light'] = f"{self.market_report.market_color} ({self.market_report.market_score}/100)"
            context['market_score'] = self.market_report.market_score
            
            # Distribution days từ key_signals
            for sig in self.market_report.key_signals:
                if 'Distribution' in sig or 'distribution' in sig:
                    context['distribution_days'] = 1  # Placeholder
        
        if self.sector_report and hasattr(self.sector_report, 'sectors'):
            top_sectors = [s.code for s in self.sector_report.sectors[:3] if hasattr(s, 'code')]
            context['leading_sectors'] = top_sectors
        
        return context

    def _generate_breadth_section(self) -> str:
        """Generate market breadth section for combined report (Phase 02)."""
        if not self.market_report:
            return ""
        try:
            breadth_mod = _load_kebab_module(
                os.path.join(os.path.dirname(__file__), "market-breadth-analyzer.py"),
                "market_breadth_analyzer"
            )
            if not breadth_mod:
                return ""

            analyzer = breadth_mod.MarketBreadthAnalyzer()
            b = self.market_report.breadth
            metrics = analyzer.calculate_breadth_metrics(
                advances=b.advances, declines=b.declines,
                unchanged=b.unchanged, ceiling=b.ceiling, floor=b.floor,
            )
            section = analyzer.format_breadth_report_section(metrics) + "\n\n"

            # Add VNMID/VNSML comparison table if available
            indices = []
            for name, data in [("VNMID", self.market_report.vnmid), ("VNSML", self.market_report.vnsml)]:
                if data and data.price > 0:
                    indices.append(f"| **{name}** | {data.price:,.0f} | {data.change_1d:+.2f}% |")
            if indices:
                section += "### Mid/Small Cap\n| Index | Price | 1D Change |\n|-------|-------|----------|\n"
                section += "\n".join(indices) + "\n\n"

            # Sector heatmap
            if self.sector_report and hasattr(self.sector_report, 'sectors'):
                heatmap_data = []
                for s in self.sector_report.sectors:
                    code = getattr(s, 'code', '')
                    name = getattr(s, 'name', code)
                    change = getattr(s, 'change_1d', 0)
                    phase = getattr(s, 'phase', '')
                    if hasattr(phase, 'name'):
                        phase = phase.name
                    heatmap_data.append({"code": code, "name": name, "change_1d": change, "phase": str(phase)})
                if heatmap_data:
                    section += analyzer.generate_sector_heatmap(heatmap_data) + "\n\n"

            return section
        except Exception as e:
            print(f"[WARN] Breadth section generation failed: {e}")
            return ""

    def _generate_financial_health_report(self) -> str:
        """Generate financial health summary table from screener results."""
        if not self.screener_report or not self.screener_report.top_picks:
            return ""

        content = """## 📊 Financial Health Summary

| Stock | Piotroski | Rating | Altman Z | Zone | PEG | Rating |
|-------|-----------|--------|----------|------|-----|--------|
"""

        for c in self.screener_report.top_picks[:10]:
            try:
                # Extract attributes (with backward compatibility)
                piotroski = getattr(c.fundamental, 'piotroski_score', None)
                altman_z = getattr(c.fundamental, 'altman_z_score', None)
                altman_zone = getattr(c.fundamental, 'altman_zone', None)
                peg = getattr(c.fundamental, 'peg_ratio', None)
                peg_rating = getattr(c.fundamental, 'peg_rating', None)

                # Format values
                piotroski_str = f"{piotroski}/9" if piotroski is not None and piotroski > 0 else "N/A"
                piotroski_rating = ("Very Strong" if piotroski is not None and piotroski >= 7 else
                                   "Strong" if piotroski is not None and piotroski >= 5 else
                                   "Weak" if piotroski is not None and piotroski > 0 else "N/A")

                altman_str = f"{altman_z:.2f}" if altman_z is not None and altman_z > 0 else "N/A"
                zone_str = altman_zone if altman_zone else "N/A"

                peg_str = f"{peg:.2f}" if peg is not None and peg > 0 else "N/A"
                peg_rating_str = peg_rating if peg_rating else "N/A"

                content += f"| {c.symbol} | {piotroski_str} | {piotroski_rating} | {altman_str} | {zone_str} | {peg_str} | {peg_rating_str} |\n"
            except Exception as e:
                # Gracefully skip if attributes don't exist
                content += f"| {c.symbol} | N/A | N/A | N/A | N/A | N/A | N/A |\n"

        content += "\n"
        return content

    def _generate_dupont_analysis_report(self) -> str:
        """Generate DuPont ROE decomposition for top 5 picks."""
        if not self.screener_report or not self.screener_report.top_picks:
            return ""

        if not _dupont_module:
            return ""  # Module not available

        content = """## 🔍 DuPont ROE Analysis (Top 5)

"""

        for c in self.screener_report.top_picks[:5]:
            try:
                # Build input dicts from fundamental data
                income_data = {
                    'net_income': getattr(c.fundamental, 'net_income', None),
                    'profit_before_tax': getattr(c.fundamental, 'profit_before_tax', None),
                    'operating_profit': getattr(c.fundamental, 'operating_profit', None),
                    'revenue': getattr(c.fundamental, 'revenue', None),
                }
                balance_data = {
                    'total_assets': getattr(c.fundamental, 'total_assets', None),
                    'total_equity': getattr(c.fundamental, 'total_equity', None),
                }

                # Check if we have enough data
                if not all([income_data.get('net_income'), income_data.get('revenue'),
                           balance_data.get('total_assets'), balance_data.get('total_equity')]):
                    # Skip if critical fields missing
                    continue

                # Calculate DuPont
                dupont_result = _dupont_module.calculate_dupont(income_data, balance_data)

                roe = dupont_result.get('roe')
                components = dupont_result.get('components', {})
                driver = dupont_result.get('driver')
                weakness = dupont_result.get('weakness')

                if roe is None:
                    continue

                # Extract component values
                tax_burden = components.get('tax_burden', {}).get('value')
                interest = components.get('interest_burden', {}).get('value')
                margin = components.get('operating_margin', {}).get('value')
                turnover = components.get('asset_turnover', {}).get('value')
                leverage = components.get('financial_leverage', {}).get('value')

                # Format component display
                def fmt(val):
                    return f"{val:.2f}" if val is not None else "N/A"

                content += f"""**{c.symbol}** (ROE: {roe*100:.1f}%)
- Tax Burden: {fmt(tax_burden)} | Interest: {fmt(interest)} | Margin: {fmt(margin)} | Turnover: {fmt(turnover)} | Leverage: {fmt(leverage)}
- Driver: {driver.replace('_', ' ').title() if driver else 'N/A'} | Weakness: {weakness.replace('_', ' ').title() if weakness else 'N/A'}

"""
            except Exception as e:
                # Skip on error
                continue

        if content.count("**") == 0:  # No stocks analyzed
            return ""

        return content

    def _generate_mid_session_comparison(self) -> str:
        """Tạo section so sánh giữa phiên và cuối ngày"""
        if not self.mid_session_data or not self.market_report:
            return ""
        
        mid = self.mid_session_data
        mid_market = mid.get('market', {})
        mid_vnindex = mid_market.get('vnindex', {})
        
        # Current end-of-day data
        eod_score = self.market_report.market_score
        eod_color = self.market_report.market_color
        eod_price = self.market_report.vnindex.price
        eod_change = self.market_report.vnindex.change_1d
        
        # Mid-session data
        mid_score = mid_market.get('score', 0)
        mid_color = mid_market.get('color', 'N/A')
        mid_price = mid_vnindex.get('price', 0)
        mid_change = mid_vnindex.get('change_1d', 0)
        
        # Calculate changes
        score_change = eod_score - mid_score
        price_change = eod_price - mid_price
        
        # Score change indicator
        if score_change > 5:
            score_indicator = "📈 Tăng"
        elif score_change < -5:
            score_indicator = "📉 Giảm"
        else:
            score_indicator = "➡️ Ổn định"
        
        content = f"""# 📊 SO SÁNH GIỮA PHIÊN VS CUỐI NGÀY

**Thời điểm giữa phiên:** {mid.get('timestamp', 'N/A')}

## Tổng quan thay đổi

| Chỉ số | Giữa phiên | Cuối ngày | Thay đổi |
|--------|------------|-----------|----------|
| **Score** | {mid_score}/100 | {eod_score}/100 | {score_change:+d} ({score_indicator}) |
| **Color** | {mid_color} | {eod_color} | - |
| **VNIndex** | {mid_price:,.0f} ({mid_change:+.2f}%) | {eod_price:,.0f} ({eod_change:+.2f}%) | {price_change:+,.0f} |
| **RSI** | {mid_vnindex.get('rsi_14', 0):.1f} | {self.market_report.vnindex.rsi_14:.1f} | - |
| **A/D Ratio** | {mid_market.get('breadth', {}).get('ad_ratio', 0):.2f} | {self.market_report.breadth.ad_ratio:.2f} | - |

"""
        
        # Sector comparison
        mid_sectors = mid.get('sectors', [])
        if mid_sectors and self.sector_report and hasattr(self.sector_report, 'sectors'):
            content += """## Thay đổi xếp hạng ngành

| Ngành | RS Giữa phiên | RS Cuối ngày | Trend |
|-------|---------------|--------------|-------|
"""
            # Build lookup for mid-session sectors
            mid_sector_map = {s.get('code', ''): s for s in mid_sectors}
            
            for sector in self.sector_report.sectors[:5]:
                code = getattr(sector, 'code', '')
                eod_rs = getattr(sector, 'rs_rating', 0)
                mid_sector = mid_sector_map.get(code, {})
                mid_rs = mid_sector.get('rs_rating', 0)
                
                rs_change = eod_rs - mid_rs
                if rs_change > 2:
                    trend = "📈"
                elif rs_change < -2:
                    trend = "📉"
                else:
                    trend = "➡️"
                
                content += f"| {getattr(sector, 'name', code)} | {mid_rs:.0f} | {eod_rs:.0f} | {trend} ({rs_change:+.0f}) |\n"
        
        content += "\n---\n\n"
        
        return content
    
    def _generate_ops_sections(self) -> str:
        """Generate BondLab + AssetTracker + NewsHub report sections from ContextMemo."""
        if not self.memo:
            return ""

        content = ""

        # ── Bond Lab ──
        bonds = self.memo.read("bonds")
        if bonds:
            health = bonds.get("bond_health", {})
            curve = bonds.get("yield_curve", {})
            vn10y = health.get("vn10y_yield") or curve.get("VN10Y") or "N/A"
            score = health.get("score", 0)
            interp = health.get("interpretation", "N/A")
            weekly_bps = health.get("weekly_change_bps", 0)
            monthly_bps = health.get("monthly_change_bps", 0)
            score_emoji = "🟢" if score >= 3 else "🔴" if score <= -3 else "🟡"

            content += f"""## 🏦 Bond Lab - Lãi suất trái phiếu

| Chỉ số | Giá trị |
|--------|---------|
| **VN10Y Yield** | {vn10y}% |
| **Thay đổi tuần** | {weekly_bps:+.1f} bps |
| **Thay đổi tháng** | {monthly_bps:+.1f} bps |
| **Health Score** | {score_emoji} {score:+.1f}/10 |
| **Nhận định** | {interp} |

"""

        # ── Asset Tracker ──
        assets_data = self.memo.read("assets")
        if assets_data:
            macro = assets_data.get("macro_signal", {})
            summary = assets_data.get("summary", {})
            assets_list = summary.get("assets", {})
            signal = macro.get("signal", "neutral")
            macro_score = macro.get("score", 0)
            signal_emoji = "🟢" if signal == "risk-on" else "🔴" if signal == "risk-off" else "🟡"

            content += """## 🌍 Asset Tracker - Tín hiệu vĩ mô

| Asset | Giá | Ngày | Tuần | Xu hướng |
|-------|-----|------|------|----------|
"""
            for ticker, info in assets_list.items():
                price = info.get("price", "N/A")
                unit = info.get("unit", "")
                daily = info.get("daily_change_pct", 0)
                weekly = info.get("weekly_change_pct", 0)
                direction = "📈" if info.get("direction") == "up" else "📉"
                content += f"| **{ticker}** | {price} {unit} | {daily:+.1f}% | {weekly:+.1f}% | {direction} |\n"

            content += f"""
**Macro Signal:** {signal_emoji} **{signal.upper()}** (score: {macro_score:+.1f})

"""

        # ── News Hub ──
        news = self.memo.read("news")
        if news:
            avg_sent = news.get("avg_sentiment", 0)
            total = news.get("total_articles", 0)
            positive = news.get("positive", 0)
            negative = news.get("negative", 0)
            sent_emoji = "🟢" if avg_sent > 0.1 else "🔴" if avg_sent < -0.1 else "🟡"

            content += f"""## 📰 News Hub - Sentiment thị trường

| Metric | Value |
|--------|-------|
| **Sentiment TB** | {sent_emoji} {avg_sent:+.3f} |
| **Tổng bài (7 ngày)** | {total} |
| **Tích cực** | {positive} |
| **Tiêu cực** | {negative} |

"""

        return content

    def _generate_report_via_templates(self) -> Optional[str]:
        """
        Render report using Jinja2 templates with deterministic fallback.
        Returns None if template renderer unavailable (caller falls back to _generate_combined_report).
        """
        if not _template_renderer_module:
            return None
        if not _template_renderer_module.is_available():
            return None

        try:
            renderer = _template_renderer_module.ReportTemplateRenderer()

            # Build market data dict
            market_data: dict = {}
            if self.market_report:
                vni = self.market_report.vnindex
                breadth = self.market_report.breadth
                market_data = {
                    'color': self.market_report.market_color,
                    'score': self.market_report.market_score,
                    'vnindex_price': vni.price,
                    'vnindex_change': vni.change_1d,
                    'rsi': vni.rsi_14,
                    'macd_hist': vni.macd_hist,
                    'poc': vni.poc,
                    'val': vni.val,
                    'vah': vni.vah,
                    'price_vs_va': vni.price_vs_va,
                    'key_signals': self.market_report.key_signals,
                    'trend': getattr(self.market_report, 'trend_status', ''),
                    'breadth': {
                        'advances': breadth.advances,
                        'declines': breadth.declines,
                        'unchanged': breadth.unchanged,
                        'ad_ratio': breadth.ad_ratio,
                        'ceiling': getattr(breadth, 'ceiling', 0),
                        'floor': getattr(breadth, 'floor', 0),
                    } if breadth else None,
                }

            # Build sectors list
            sectors_data: list = []
            if self.sector_report and hasattr(self.sector_report, 'sectors'):
                for s in self.sector_report.sectors:
                    phase = getattr(s, 'phase', '')
                    phase_str = phase.name if hasattr(phase, 'name') else str(phase)
                    sectors_data.append({
                        'code': getattr(s, 'code', ''),
                        'name': getattr(s, 'name', getattr(s, 'code', '')),
                        'change_1d': getattr(s, 'change_1d', 0),
                        'rs_rating': getattr(s, 'rs_rating', 50),
                        'phase': phase_str,
                    })

            # Build screener data
            market_score = self.market_report.market_score if self.market_report else 50
            top_picks_rows: list = []
            top_picks_detail: list = []

            if self.screener_report:
                for c in self.screener_report.top_picks[:10]:
                    top_picks_rows.append({
                        'rank': c.rank,
                        'symbol': c.symbol,
                        'sector_name': c.sector_name,
                        'score_total': c.score_total,
                        'rs_rating': c.technical.rs_rating,
                        'pattern_type': c.pattern.pattern_type.value,
                        'signal': c.signal.value,
                    })

                for c in self.screener_report.top_picks[:5]:
                    sl_tp = calculate_dynamic_sl_tp(c, market_score)
                    price = c.technical.price
                    buy_point = c.pattern.buy_point if c.pattern.buy_point > 0 else price * 1.02
                    top_picks_detail.append({
                        'rank': c.rank,
                        'symbol': c.symbol,
                        'sector_name': c.sector_name,
                        'score_total': c.score_total,
                        'score_fundamental': c.score_fundamental,
                        'score_technical': c.score_technical,
                        'score_pattern': c.score_pattern,
                        'roe': c.fundamental.roe,
                        'roa': c.fundamental.roa,
                        'eps_qoq': c.fundamental.eps_growth_qoq,
                        'eps_yoy': c.fundamental.eps_growth_yoy,
                        'price': price,
                        'rs_rating': c.technical.rs_rating,
                        'rsi': c.technical.rsi_14,
                        'volume_ratio': c.technical.volume_ratio,
                        'pattern_type': c.pattern.pattern_type.value,
                        'pattern_quality': c.pattern.pattern_quality,
                        'breakout_ready': getattr(c.pattern, 'breakout_ready', False),
                        'buy_point': buy_point,
                        'stop_loss': sl_tp['stop_loss'],
                        'stop_loss_pct': sl_tp['stop_loss_pct'],
                        'target_1': sl_tp['target_1'],
                        'target_1_pct': sl_tp['target_1_pct'],
                        'target_2': sl_tp['target_2'],
                        'target_2_pct': sl_tp['target_2_pct'],
                        'ai_analysis': c.ai_analysis or None,
                        'rule_based_commentary': '',
                    })

            screener_data = {
                'stats': {
                    'total_scanned': self.screener_report.total_scanned if self.screener_report else 0,
                    'passed_technical': self.screener_report.passed_technical if self.screener_report else 0,
                    'final_candidates': len(self.screener_report.candidates) if self.screener_report else 0,
                },
                'top_picks': top_picks_rows,
                'top_picks_detail': top_picks_detail,
            }

            data = {
                'timestamp': self.timestamp.strftime('%d/%m/%Y %H:%M'),
                'market': market_data,
                'sectors': sectors_data,
                'screener': screener_data,
            }

            ai_narratives = {
                'market': getattr(self.market_report, 'ai_analysis', None) if self.market_report else None,
                'sector': getattr(self.sector_report, 'ai_analysis', None) if self.sector_report else None,
                'screener': getattr(self.screener_report, 'ai_analysis', None) if self.screener_report else None,
            }

            print("Using Jinja2 template renderer...")
            return renderer.render(data, ai_narratives)

        except Exception as e:
            print(f"⚠️ Template renderer failed: {e} - falling back to combined report")
            return None

    def _generate_combined_report(self) -> str:
        """Tạo báo cáo gộp từ 3 modules"""
        
        # Header
        content = f"""# 📊 CANSLIM DAILY REPORT
**Ngày:** {self.timestamp.strftime('%d/%m/%Y %H:%M')}

---

"""
        
        # Mid-Session Comparison Section (if available)
        if self.mid_session_data:
            content += self._generate_mid_session_comparison()
        
        content += """# 🎯 PHẦN 1: MARKET TIMING (Module 1)

"""
        
        # Module 1: Market Timing
        if self.market_report:
            vni = self.market_report.vnindex
            content += f"""## Tổng quan thị trường

| Chỉ số | Giá trị |
|--------|---------|
| **Market Color** | {self.market_report.market_color} |
| **Score** | {self.market_report.market_score}/100 |
| **VN-Index** | {vni.price:,.0f} ({vni.change_1d:+.2f}%) |
| **RSI(14)** | {vni.rsi_14:.1f} |
| **MACD Hist** | {vni.macd_hist:+.2f} |

## Volume Profile
| Level | Giá |
|-------|-----|
| **POC** | {vni.poc:,.0f} |
| **Value Area** | {vni.val:,.0f} - {vni.vah:,.0f} |
| **Price vs VA** | {vni.price_vs_va} |

"""
            # Market Breadth section (Phase 02)
            content += self._generate_breadth_section()

            content += """## Tín hiệu chính
"""
            for sig in self.market_report.key_signals:
                content += f"- {sig}\n"
            
            if self.market_report.ai_analysis:
                content += f"""
## 🤖 AI Analysis - Market Timing
{self.market_report.ai_analysis}
"""
        
        content += "\n---\n\n"

        # OPS Platform sections (Bond Lab, Asset Tracker, News Hub)
        ops_sections = self._generate_ops_sections()
        if ops_sections:
            content += "# 🔬 OPS PLATFORM DATA\n\n"
            content += ops_sections
            content += "\n---\n\n"

        # Module 2: Sector Rotation
        content += """# 🏭 PHẦN 2: SECTOR ROTATION (Module 2)

"""
        if self.sector_report and hasattr(self.sector_report, 'sectors'):
            content += """## Bảng xếp hạng ngành

| Rank | Ngành | Change 1D | RS Score |
|------|-------|-----------|----------|
"""
            for i, sector in enumerate(self.sector_report.sectors, 1):
                name = getattr(sector, 'name', sector.code if hasattr(sector, 'code') else 'N/A')
                change = getattr(sector, 'change_1d', 0)
                rs = getattr(sector, 'rs_rating', 50)
                content += f"| {i} | {name} | {change:+.2f}% | {rs:.0f} |\n"
            
            if hasattr(self.sector_report, 'ai_analysis') and self.sector_report.ai_analysis:
                content += f"""
## 🤖 AI Analysis - Sector Rotation
{self.sector_report.ai_analysis}
"""
        
        content += "\n---\n\n"
        
        # Module 3: Stock Screener
        content += """# 📈 PHẦN 3: STOCK SCREENER (Module 3)

"""
        if self.screener_report:
            content += f"""## Screening Stats

| Metric | Value |
|--------|-------|
| **Target Sectors** | {', '.join(self.screener_report.target_sectors)} |
| **Total Scanned** | {self.screener_report.total_scanned} |
| **Passed Technical** | {self.screener_report.passed_technical} |
| **Final Candidates** | {len(self.screener_report.candidates)} |

## 🏆 Top Picks

| Rank | Symbol | Sector | Score | RS | Pattern | Vol✓ | Signal |
|------|--------|--------|-------|----| --------|------|--------|
"""
            for c in self.screener_report.top_picks[:10]:
                vol_status = "🚀" if getattr(c.pattern, 'breakout_ready', False) else ("✓" if getattr(c.pattern, 'has_shakeout', False) or getattr(c.pattern, 'has_dryup', False) else "⭕")
                content += f"| {c.rank} | {c.symbol} | {c.sector_name} | {c.score_total:.0f} | {c.technical.rs_rating} | {c.pattern.pattern_type.value} | {vol_status} | {c.signal.value} |\n"

            # Financial Health Summary right after Top Picks table
            financial_health = self._generate_financial_health_report()
            if financial_health:
                content += "\n" + financial_health + "\n"

            # Top 5 detail với Trading Plan
            content += "\n## 📝 Chi tiết Top 5 Candidates\n"
            
            for c in self.screener_report.top_picks[:5]:
                price = c.technical.price
                buy_point = c.pattern.buy_point if c.pattern.buy_point > 0 else price * 1.02
                buy_zone_max = buy_point * 1.05
                
                # Dynamic SL/TP based on market conditions
                market_score = self.market_report.market_score if self.market_report else 50
                sl_tp = calculate_dynamic_sl_tp(c, market_score)
                
                # Calculate price vs MA percentages
                pct_vs_ma20 = ((price - c.technical.ma20) / c.technical.ma20 * 100) if c.technical.ma20 > 0 else 0
                pct_vs_ma50 = ((price - c.technical.ma50) / c.technical.ma50 * 100) if c.technical.ma50 > 0 else 0
                pct_vs_ma200 = ((price - c.technical.ma200) / c.technical.ma200 * 100) if c.technical.ma200 > 0 else 0
                
                content += f"""
### {c.rank}. {c.symbol} - {c.sector_name}

**Scores:** Fundamental {c.score_fundamental:.0f} | Technical {c.score_technical:.0f} | Pattern {c.score_pattern:.0f} | News {c.score_news:.0f} | **Total: {c.score_total:.0f}**

**📊 Fundamental (V3 Enhanced):**
- ROE: {c.fundamental.roe:.1f}% | ROA: {c.fundamental.roa:.1f}%
- EPS Q/Q: {c.fundamental.eps_growth_qoq:+.1f}% | EPS Y/Y: {c.fundamental.eps_growth_yoy:+.1f}%
- EPS 3Y CAGR: {getattr(c.fundamental, 'eps_growth_3y_cagr', c.fundamental.eps_growth_3y):+.1f}%
- C Score: {c.fundamental.c_score:.0f} | A Score: {c.fundamental.a_score:.0f}
- Confidence: {getattr(c.fundamental, 'confidence_score', 50):.0f}%

**📈 Technical:**
- Giá: {price:,.0f} | RS: {c.technical.rs_rating} | RSI: {c.technical.rsi_14:.0f}
- Volume Ratio: {c.technical.volume_ratio:.2f}x | ATR(14): {getattr(c.technical, 'atr_pct', 0):.1f}%

**📍 Cấu trúc giá (MA Positions):**
| MA | Giá | Vị thế | % vs Giá |
|----|-----|--------|----------|
| MA20 | {c.technical.ma20:,.0f} | {'✅ TRÊN' if c.technical.above_ma20 else '❌ DƯỚI'} | {pct_vs_ma20:+.1f}% |
| MA50 | {c.technical.ma50:,.0f} | {'✅ TRÊN' if c.technical.above_ma50 else '❌ DƯỚI'} | {pct_vs_ma50:+.1f}% |
| MA200 | {c.technical.ma200:,.0f} | {'✅ TRÊN' if c.technical.above_ma200 else '❌ DƯỚI'} | {pct_vs_ma200:+.1f}% |

**📊 Volume Profile:**
| Level | Giá | Ý nghĩa |
|-------|-----|---------|
| POC | {c.technical.poc:,.0f} | Vùng giao dịch nhiều nhất |
| VAH | {c.technical.vah:,.0f} | Kháng cự Volume |
| VAL | {c.technical.val:,.0f} | Hỗ trợ Volume |
| **Vị thế** | **{c.technical.price_vs_va}** | {'📈 Bullish' if c.technical.price_vs_va == 'ABOVE_VA' else '📊 Neutral' if c.technical.price_vs_va == 'IN_VA' else '📉 Caution' if c.technical.price_vs_va else 'N/A'} |

**Pattern:** {c.pattern.pattern_type.value} (Quality: {c.pattern.pattern_quality:.0f})
- 📊 Volume Score: {getattr(c.pattern, 'volume_score', 0):.0f}/80
- {'✅ Shakeout detected' if getattr(c.pattern, 'has_shakeout', False) else '⭕ No shakeout'}
- {'✅ Dry-up confirmed' if getattr(c.pattern, 'has_dryup', False) else '⭕ No dry-up'}
- {'🚀 **BREAKOUT READY**' if getattr(c.pattern, 'breakout_ready', False) else '⏳ Waiting for confirmation'}

"""
                # Financial Health section for each stock
                pio = getattr(c.fundamental, 'piotroski_score', None)
                alt_z = getattr(c.fundamental, 'altman_z_score', None)
                alt_zone = getattr(c.fundamental, 'altman_zone', None)
                peg = getattr(c.fundamental, 'peg_ratio', None)
                peg_r = getattr(c.fundamental, 'peg_rating', None)
                div_y = getattr(c.fundamental, 'dividend_yield', None)

                if pio is not None or alt_z is not None or (peg is not None and peg > 0):
                    pio_rating = ("Very Strong" if pio is not None and pio >= 8 else
                                  "Strong" if pio is not None and pio >= 6 else
                                  "Average" if pio is not None and pio >= 4 else
                                  "Weak" if pio is not None and pio > 0 else "N/A")
                    pio_emoji = "🟢" if pio is not None and pio >= 7 else "🟡" if pio is not None and pio >= 4 else "🔴" if pio is not None and pio > 0 else "⚪"
                    alt_emoji = "🟢" if alt_zone == 'safe' else "🟡" if alt_zone == 'grey' else "🔴" if alt_zone == 'distress' else "⚪"
                    peg_emoji = "🟢" if peg and peg < 1 else "🟡" if peg and peg <= 2 else "🔴" if peg and peg > 2 else "⚪"

                    pio_val = f"{pio}/9" if pio is not None and pio > 0 else "N/A"
                    alt_val = f"{alt_z:.2f}" if alt_z is not None and alt_z > 0 else "N/A"
                    peg_val = f"{peg:.2f}" if peg is not None and peg > 0 else "N/A"
                    div_val = f"{div_y*100:.1f}%" if div_y and div_y > 0 else "N/A"

                    content += f"""**🏥 Financial Health:**
| Chỉ số | Giá trị | Đánh giá |
|--------|---------|----------|
| Piotroski F-Score | {pio_val} | {pio_emoji} {pio_rating} |
| Altman Z-Score | {alt_val} | {alt_emoji} {alt_zone if alt_zone else 'N/A'} |
| PEG Ratio | {peg_val} | {peg_emoji} {peg_r if peg_r else 'N/A'} |
| Dividend Yield | {div_val} | {'🟢' if div_y and div_y >= 0.04 else '🟡' if div_y and div_y >= 0.02 else '⚪'} |

"""
                # News section
                if c.news and c.news.articles:
                    content += f"**📰 News ({len(c.news.articles)} bài):**\n"
                    for a in c.news.articles[:3]:
                        title = a.get('title', '')[:80]
                        source = a.get('source', '')
                        url = a.get('url', '#')
                        content += f"- [{title}...]({url}) ({source})\n"
                    sentiment_emoji = "🟢" if c.news.sentiment == "positive" else "🔴" if c.news.sentiment == "negative" else "🟡"
                    content += f"- Sentiment: {sentiment_emoji} {c.news.sentiment.upper()} ({c.news.sentiment_score:+.2f})\n"
                    if c.news.key_topics:
                        content += f"- Topics: {', '.join(c.news.key_topics)}\n"
                else:
                    content += "**📰 News:** Không có tin tức đáng chú ý\n"
                
                content += f"""
**📈 TRADING PLAN (Dynamic):**
| Level | Giá | % | Lý do |
|-------|-----|---|-------|
| 🎯 **Buy Point** | {buy_point:,.0f} | - | Breakout từ pattern |
| 🛒 **Buy Zone** | {buy_point:,.0f} - {buy_zone_max:,.0f} | +5% | Mua trong vùng này |
| 🛑 **Stop Loss** | {sl_tp['stop_loss']:,.0f} | -{sl_tp['stop_loss_pct']:.1f}% | {sl_tp['rationale']} |
| 💰 **Target 1** | {sl_tp['target_1']:,.0f} | +{sl_tp['target_1_pct']:.0f}% | R:R = 1:{sl_tp['risk_reward']:.1f} |
| 💰 **Target 2** | {sl_tp['target_2']:,.0f} | +{sl_tp['target_2_pct']:.0f}% | Trailing stop sau T1 |

> 📊 **SL/TP Logic:** Market {sl_tp['mode']} | ATR={sl_tp['atr_pct']:.1f}% | Pattern={c.pattern.pattern_quality:.0f} | Vol={'🚀' if getattr(c.pattern, 'breakout_ready', False) else '✓' if getattr(c.pattern, 'has_shakeout', False) else '⭕'}

**Signal:** {c.signal.value}

"""
                if c.ai_analysis:
                    content += f"**🤖 AI Analysis:**\n{c.ai_analysis}\n\n"
                
                content += "---\n"
            
            # AI Summary
            if self.screener_report.ai_analysis:
                content += f"""
## 🤖 AI Summary - Stock Screening
{self.screener_report.ai_analysis}
"""

        # ══════════════════════════════════════════════════════════════════════
        # NEW SECTIONS: DuPont Analysis
        # ══════════════════════════════════════════════════════════════════════
        content += "\n---\n\n"

        # DuPont ROE Decomposition
        dupont_analysis = self._generate_dupont_analysis_report()
        if dupont_analysis:
            content += dupont_analysis

        # Footer
        content += f"""
---

# ⚠️ DISCLAIMER

*Báo cáo này được tạo tự động bởi hệ thống CANSLIM Scanner.*
*Thông tin chỉ mang tính chất tham khảo, không phải khuyến nghị đầu tư.*
*Nhà đầu tư tự chịu trách nhiệm với quyết định giao dịch của mình.*

---
**Generated:** {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        return content
    
    def _save_report(self, content: str) -> str:
        """Lưu báo cáo"""
        os.makedirs(self.output_dir, exist_ok=True)
        
        filename = os.path.join(
            self.output_dir,
            f"canslim_report_{self.timestamp.strftime('%Y%m%d_%H%M')}.md"
        )
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return filename


def main():
    """Main entry point"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🚀 CANSLIM FULL PIPELINE 🚀                               ║
║              3-in-1: Market + Sector + Stock Screening                       ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Check config
    config = get_config()
    ai_provider, ai_key = config.get_ai_provider()
    
    print(f"📡 Data Source: {config.get_data_source()}")
    print(f"🤖 AI Provider: {ai_provider.upper() if ai_provider else 'Chưa cấu hình'}")
    print(f"📁 Output: {config.output.OUTPUT_DIR}")
    
    if not ai_key:
        print("\n⚠️ Không có AI key - báo cáo sẽ không có phân tích AI")
        print("   Điền API key vào config.py để có đầy đủ tính năng")
    
    # Run pipeline
    runner = FullPipelineRunner()
    
    # Có thể chỉ định sectors cụ thể hoặc để auto detect từ Module 2
    output_file = runner.run(target_sectors=None)  # Auto detect
    
    print("\n" + "="*80)
    print("🎉 HOÀN THÀNH PIPELINE!")
    print("="*80)
    print(f"\n📄 File output: {output_file}")
    print("\nMở file để xem báo cáo đầy đủ.")
    
    return output_file


if __name__ == "__main__":
    main()