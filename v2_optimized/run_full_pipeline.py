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
from datetime import datetime
from typing import Dict, List, Optional

# Import config
from config import get_config

# Import modules
from module1_market_timing_v2 import MarketTimingModule, create_config_from_unified as create_m1_config
from module2_sector_rotation_v3 import SectorRotationModule, create_config_from_unified as create_m2_config
from module3_stock_screener_v1 import StockScreenerModule, create_config_from_unified as create_m3_config
from email_notifier import EmailNotifier
from history_manager import HistoryManager


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
        # MODULE 1: MARKET TIMING
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("📊 MODULE 1: MARKET TIMING")
        print("="*80)
        
        m1_config = create_m1_config()
        m1_config.SAVE_REPORT = False  # Không save riêng
        
        m1_module = MarketTimingModule(m1_config)
        self.market_report = m1_module.run(combined_context)
        
        # ══════════════════════════════════════════════════════════════════════
        # MODULE 2: SECTOR ROTATION
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("🏭 MODULE 2: SECTOR ROTATION")
        print("="*80)
        
        m2_config = create_m2_config()
        m2_config.SAVE_REPORT = False  # Không save riêng
        
        m2_module = SectorRotationModule(m2_config)
        self.sector_report = m2_module.run()
        
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
            history_context=history_context
        )
        
        # ══════════════════════════════════════════════════════════════════════
        # GENERATE COMBINED OUTPUT
        # ══════════════════════════════════════════════════════════════════════
        print("\n" + "="*80)
        print("📝 GENERATING COMBINED REPORT")
        print("="*80)
        
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

## Tín hiệu chính
"""
            for sig in self.market_report.key_signals:
                content += f"- {sig}\n"
            
            if self.market_report.ai_analysis:
                content += f"""
## 🤖 AI Analysis - Market Timing
{self.market_report.ai_analysis}
"""
        
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