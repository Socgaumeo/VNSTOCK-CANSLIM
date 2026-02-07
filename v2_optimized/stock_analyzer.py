#!/usr/bin/env python3
"""
Stock Analyzer - API phân tích single stock cho Telegram Bot

Tính năng:
- Phân tích kỹ thuật (Technical)
- Phân tích cơ bản (Fundamental)
- Nhận diện pattern
- Tính CANSLIM score
- Tạo trading plan
"""

import os
import sys
import warnings
from datetime import datetime
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict

warnings.filterwarnings('ignore')

# Add path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import get_config
from data_collector import get_data_collector, EnhancedStockData


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class TechnicalResult:
    """Kết quả phân tích kỹ thuật"""
    price: float = 0.0
    change_1d: float = 0.0
    change_1d_pct: float = 0.0

    # Moving Averages
    ma20: float = 0.0
    ma50: float = 0.0
    ma200: float = 0.0
    above_ma20: bool = False
    above_ma50: bool = False
    above_ma200: bool = False

    # RSI
    rsi: float = 0.0
    rsi_signal: str = "Neutral"

    # Volume
    volume: int = 0
    volume_avg_20: int = 0
    volume_ratio: float = 0.0
    volume_signal: str = ""

    # RS Rating
    rs_rating: int = 50

    # 52 week
    high_52w: float = 0.0
    low_52w: float = 0.0
    distance_from_high: float = 0.0

    # Volume Profile
    poc: float = 0.0
    vah: float = 0.0
    val: float = 0.0

    # Score
    score: float = 0.0


@dataclass
class FundamentalResult:
    """Kết quả phân tích cơ bản"""
    # EPS
    eps_ttm: float = 0.0
    eps_growth_qoq: float = 0.0
    eps_growth_yoy: float = 0.0

    # Revenue
    revenue_growth_qoq: float = 0.0
    revenue_growth_yoy: float = 0.0

    # Ratios
    roe: float = 0.0
    roa: float = 0.0
    pe: float = 0.0
    pb: float = 0.0

    # Cash Flow
    ocf_to_profit: float = 0.0
    cf_quality: str = ""

    # Score
    c_score: float = 0.0  # Current earnings
    a_score: float = 0.0  # Annual earnings
    score: float = 0.0


@dataclass
class PatternResult:
    """Kết quả nhận diện pattern"""
    pattern_type: str = "No Pattern"
    pattern_quality: float = 0.0
    buy_point: float = 0.0
    breakout_ready: bool = False
    has_shakeout: bool = False
    has_dryup: bool = False
    volume_confirmed: bool = False
    description: str = ""
    score: float = 0.0


@dataclass
class TradingPlan:
    """Kế hoạch giao dịch"""
    entry_low: float = 0.0
    entry_high: float = 0.0
    stop_loss: float = 0.0
    stop_loss_pct: float = 0.0
    target1: float = 0.0
    target1_pct: float = 0.0
    target2: float = 0.0
    target2_pct: float = 0.0
    risk_reward: float = 0.0


@dataclass
class StockAnalysis:
    """Kết quả phân tích tổng hợp"""
    symbol: str
    name: str = ""
    sector: str = ""
    exchange: str = ""
    timestamp: str = ""

    # Sub-results
    technical: TechnicalResult = None
    fundamental: FundamentalResult = None
    pattern: PatternResult = None
    trading_plan: TradingPlan = None

    # Scores
    score_technical: float = 0.0
    score_fundamental: float = 0.0
    score_pattern: float = 0.0
    score_total: float = 0.0

    # Signal
    signal: str = "NEUTRAL"
    signal_emoji: str = "➖"

    # AI Analysis
    ai_analysis: str = ""

    # Errors
    error: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# STOCK ANALYZER
# ══════════════════════════════════════════════════════════════════════════════

class StockAnalyzer:
    """
    Phân tích single stock

    Usage:
        analyzer = StockAnalyzer()
        result = analyzer.analyze("VCB")
        print(result.score_total, result.signal)
    """

    def __init__(self, use_ai: bool = True):
        self.config = get_config()
        self.collector = get_data_collector()
        self.use_ai = use_ai

        # Import analyzers từ module3
        try:
            from module3_stock_screener_v1 import (
                TechnicalAnalyzer, FundamentalAnalyzer, PatternDetector,
                create_config_from_unified as create_m3_config
            )
            m3_config = create_m3_config()
            self.tech_analyzer = TechnicalAnalyzer(m3_config)
            self.fund_analyzer = FundamentalAnalyzer(m3_config)
            self.pattern_detector = PatternDetector(m3_config)
            self._has_analyzers = True
        except ImportError as e:
            print(f"⚠️ Could not import analyzers: {e}")
            self._has_analyzers = False

        # Initialize AI Provider (Claude)
        self.ai_provider = None
        if use_ai:
            try:
                from ai_providers import AIProvider, AIConfig
                from config import APIKeys

                ai_config = AIConfig(
                    provider="claude",
                    api_key=APIKeys.CLAUDE,
                    model="claude-sonnet-4-20250514",  # Claude Sonnet 4 - Nhanh và thông minh
                    max_tokens=4096,
                    temperature=0.7,
                    system_prompt="""Bạn là chuyên gia phân tích chứng khoán Việt Nam theo trường phái CANSLIM và VSA (Volume Spread Analysis).
Hãy phân tích cổ phiếu dựa trên dữ liệu được cung cấp và đưa ra:
1. Đánh giá tổng quan (bullish/bearish/neutral)
2. Điểm mạnh và điểm yếu chính
3. Khuyến nghị hành động cụ thể (MUA/BÁN/CHỜ)
4. Mức giá entry, stop loss, target
Trả lời ngắn gọn, súc tích trong khoảng 200-300 chữ."""
                )
                self.ai_provider = AIProvider(ai_config)
                print("✓ AI Provider (Claude Sonnet 4) initialized")
            except Exception as e:
                print(f"⚠️ Could not initialize AI: {e}")
                self.ai_provider = None

    def analyze(self, symbol: str) -> StockAnalysis:
        """
        Phân tích đầy đủ một mã cổ phiếu

        Args:
            symbol: Mã cổ phiếu (VD: VCB, FPT)

        Returns:
            StockAnalysis object với tất cả thông tin
        """
        symbol = symbol.upper().strip()
        result = StockAnalysis(
            symbol=symbol,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        try:
            # Get basic stock data
            stock_data = self.collector.get_stock_data(symbol, lookback_days=120)
            if stock_data is None:
                result.error = f"Không tìm thấy dữ liệu cho {symbol}"
                return result

            result.name = getattr(stock_data, 'name', symbol)

            # Technical Analysis
            result.technical = self._analyze_technical(symbol, stock_data)
            result.score_technical = result.technical.score

            # Fundamental Analysis
            result.fundamental = self._analyze_fundamental(symbol)
            result.score_fundamental = result.fundamental.score

            # Pattern Detection
            result.pattern = self._detect_pattern(symbol)
            result.score_pattern = result.pattern.score

            # Calculate total score
            result.score_total = (
                result.score_technical * 0.40 +
                result.score_fundamental * 0.40 +
                result.score_pattern * 0.20
            )

            # Generate signal
            result.signal, result.signal_emoji = self._get_signal(result.score_total)

            # Generate trading plan
            result.trading_plan = self._create_trading_plan(
                result.technical.price,
                result.pattern.buy_point,
                result.technical.poc
            )

            # AI Analysis (Claude)
            if self.use_ai and self.ai_provider:
                result.ai_analysis = self._get_ai_analysis(result)

        except Exception as e:
            result.error = str(e)

        return result

    def _get_ai_analysis(self, result: StockAnalysis) -> str:
        """Gọi AI để phân tích dựa trên dữ liệu đã thu thập"""
        if not self.ai_provider:
            return ""

        try:
            tech = result.technical
            fund = result.fundamental
            pattern = result.pattern
            plan = result.trading_plan

            # Tạo prompt với dữ liệu chi tiết
            prompt = f"""Phân tích cổ phiếu {result.symbol}:

📊 DỮ LIỆU KỸ THUẬT:
- Giá hiện tại: {tech.price:,.0f} VND ({tech.change_1d_pct:+.1f}% hôm nay)
- RSI(14): {tech.rsi:.0f}
- MA20: {tech.ma20:,.0f} ({'trên' if tech.above_ma20 else 'dưới'} giá)
- MA50: {tech.ma50:,.0f} ({'trên' if tech.above_ma50 else 'dưới'} giá)
- MA200: {tech.ma200:,.0f} ({'trên' if tech.above_ma200 else 'dưới'} giá)
- RS Rating: {tech.rs_rating}/100
- Volume ratio: {tech.volume_ratio:.1f}x so với trung bình
- Khoảng cách từ đỉnh 52 tuần: {tech.distance_from_high:.1f}%
- Volume Profile POC: {tech.poc:,.0f}

💼 DỮ LIỆU CƠ BẢN:
- EPS tăng trưởng Q/Q: {fund.eps_growth_qoq:+.1f}%
- EPS tăng trưởng Y/Y: {fund.eps_growth_yoy:+.1f}%
- ROE: {fund.roe:.1f}%
- ROA: {fund.roa:.1f}%
- P/E: {fund.pe:.1f}
- P/B: {fund.pb:.1f}
- Chất lượng dòng tiền: {fund.cf_quality}

📐 PATTERN:
- Loại: {pattern.pattern_type}
- Chất lượng: {pattern.pattern_quality:.0f}%
- Buy point: {pattern.buy_point:,.0f}
- Breakout ready: {'Có' if pattern.breakout_ready else 'Chưa'}
- Volume xác nhận: {'Có' if pattern.volume_confirmed else 'Chưa'}

📈 ĐIỂM SỐ CANSLIM:
- Technical: {result.score_technical:.0f}/100
- Fundamental: {result.score_fundamental:.0f}/100
- Pattern: {result.score_pattern:.0f}/100
- TỔNG: {result.score_total:.0f}/100

Hãy đưa ra phân tích chi tiết và khuyến nghị cụ thể."""

            # Gọi AI
            response = self.ai_provider.chat(prompt)
            return response.strip() if response else ""

        except Exception as e:
            print(f"⚠️ AI analysis error: {e}")
            return f"(Lỗi AI: {str(e)[:50]})"

    def _analyze_technical(self, symbol: str, stock_data: EnhancedStockData) -> TechnicalResult:
        """Phân tích kỹ thuật"""
        tech = TechnicalResult()

        try:
            if self._has_analyzers:
                raw_data = self.tech_analyzer.analyze(symbol)
                tech.price = raw_data.price
                tech.change_1d = raw_data.change_1d
                tech.change_1d_pct = (raw_data.change_1d / (raw_data.price - raw_data.change_1d) * 100) if raw_data.price != raw_data.change_1d else 0
                tech.ma20 = raw_data.ma20
                tech.ma50 = raw_data.ma50
                tech.ma200 = raw_data.ma200
                tech.above_ma20 = raw_data.above_ma20
                tech.above_ma50 = raw_data.above_ma50
                tech.above_ma200 = raw_data.above_ma200
                tech.rsi = raw_data.rsi_14
                tech.volume_avg_20 = int(raw_data.volume_avg_20)
                tech.volume_ratio = raw_data.volume_ratio
                tech.rs_rating = raw_data.rs_rating
                tech.high_52w = raw_data.high_52w
                tech.low_52w = raw_data.low_52w
                tech.distance_from_high = raw_data.distance_from_high
                tech.poc = raw_data.poc
                tech.vah = raw_data.vah
                tech.val = raw_data.val
                tech.score = self.tech_analyzer.score(raw_data)
            else:
                # Fallback to basic analysis
                if stock_data.df is not None and len(stock_data.df) > 0:
                    df = stock_data.df
                    tech.price = float(df['close'].iloc[-1])
                    tech.ma20 = float(df['close'].tail(20).mean())
                    tech.ma50 = float(df['close'].tail(50).mean()) if len(df) >= 50 else tech.ma20
                    tech.above_ma20 = tech.price > tech.ma20
                    tech.above_ma50 = tech.price > tech.ma50
                    tech.score = 50  # Default

            # RSI Signal
            if tech.rsi > 70:
                tech.rsi_signal = "Overbought"
            elif tech.rsi < 30:
                tech.rsi_signal = "Oversold"
            else:
                tech.rsi_signal = "Neutral"

            # Volume Signal
            if tech.volume_ratio >= 1.5:
                tech.volume_signal = "Strong"
            elif tech.volume_ratio >= 1.0:
                tech.volume_signal = "Normal"
            else:
                tech.volume_signal = "Weak"

        except Exception as e:
            print(f"⚠️ Technical analysis error for {symbol}: {e}")
            tech.score = 0

        return tech

    def _analyze_fundamental(self, symbol: str) -> FundamentalResult:
        """Phân tích cơ bản"""
        fund = FundamentalResult()

        try:
            if self._has_analyzers:
                raw_data = self.fund_analyzer.analyze(symbol)
                fund.eps_ttm = raw_data.eps_ttm
                fund.eps_growth_qoq = raw_data.eps_growth_qoq
                fund.eps_growth_yoy = raw_data.eps_growth_yoy
                fund.revenue_growth_qoq = raw_data.revenue_growth_qoq
                fund.revenue_growth_yoy = raw_data.revenue_growth_yoy
                fund.roe = raw_data.roe
                fund.roa = raw_data.roa
                fund.pe = raw_data.pe
                fund.pb = raw_data.pb
                fund.ocf_to_profit = getattr(raw_data, 'ocf_to_profit_ratio', 0)
                fund.c_score = raw_data.c_score
                fund.a_score = raw_data.a_score
                fund.score = self.fund_analyzer.score(raw_data)

                # Cash flow quality
                if fund.ocf_to_profit >= 1.0:
                    fund.cf_quality = "Excellent"
                elif fund.ocf_to_profit >= 0.7:
                    fund.cf_quality = "Good"
                elif fund.ocf_to_profit >= 0.5:
                    fund.cf_quality = "Fair"
                else:
                    fund.cf_quality = "Weak"
            else:
                # Get basic ratios from collector
                ratios = self.collector.get_financial_ratios(symbol)
                fund.pe = ratios.get('pe', 0)
                fund.pb = ratios.get('pb', 0)
                fund.roe = ratios.get('roe', 0)
                fund.roa = ratios.get('roa', 0)
                fund.score = 50  # Default

        except Exception as e:
            print(f"⚠️ Fundamental analysis error for {symbol}: {e}")
            fund.score = 0

        return fund

    def _detect_pattern(self, symbol: str) -> PatternResult:
        """Nhận diện pattern"""
        pattern = PatternResult()

        try:
            if self._has_analyzers:
                raw_data = self.pattern_detector.detect(symbol)
                pattern.pattern_type = raw_data.pattern_type.value if hasattr(raw_data.pattern_type, 'value') else str(raw_data.pattern_type)
                pattern.pattern_quality = raw_data.pattern_quality
                pattern.buy_point = raw_data.buy_point
                pattern.breakout_ready = raw_data.breakout_ready
                pattern.has_shakeout = raw_data.has_shakeout
                pattern.has_dryup = raw_data.has_dryup
                pattern.volume_confirmed = raw_data.volume_confirmed
                pattern.description = raw_data.description
                pattern.score = self.pattern_detector.score(raw_data)
            else:
                pattern.score = 50  # Default

        except Exception as e:
            print(f"⚠️ Pattern detection error for {symbol}: {e}")
            pattern.score = 0

        return pattern

    def _get_signal(self, score: float) -> tuple:
        """Xác định signal dựa trên score"""
        if score >= 80:
            return "STRONG BUY", "⭐⭐⭐"
        elif score >= 65:
            return "BUY", "⭐⭐"
        elif score >= 50:
            return "WATCH", "👀"
        elif score >= 35:
            return "NEUTRAL", "➖"
        else:
            return "AVOID", "⛔"

    def _create_trading_plan(self, price: float, buy_point: float, poc: float) -> TradingPlan:
        """Tạo trading plan"""
        plan = TradingPlan()

        if price <= 0:
            return plan

        # Entry zone
        base_price = buy_point if buy_point > 0 else price
        plan.entry_low = round(base_price * 0.98, 0)  # -2%
        plan.entry_high = round(base_price * 1.02, 0)  # +2%

        # Stop loss (-7%)
        plan.stop_loss = round(base_price * 0.93, 0)
        plan.stop_loss_pct = -7.0

        # Targets
        plan.target1 = round(base_price * 1.10, 0)  # +10%
        plan.target1_pct = 10.0
        plan.target2 = round(base_price * 1.20, 0)  # +20%
        plan.target2_pct = 20.0

        # Risk/Reward
        risk = base_price - plan.stop_loss
        reward = plan.target1 - base_price
        plan.risk_reward = round(reward / risk, 1) if risk > 0 else 0

        return plan

    def get_quick_summary(self, symbol: str) -> str:
        """Lấy tóm tắt nhanh dạng text"""
        result = self.analyze(symbol)

        if result.error:
            return f"❌ Lỗi: {result.error}"

        tech = result.technical
        fund = result.fundamental
        pattern = result.pattern
        plan = result.trading_plan

        # Build summary text
        lines = [
            f"📊 PHÂN TÍCH: {result.symbol}",
            f"━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"💰 GIÁ: {tech.price:,.0f} VND ({tech.change_1d_pct:+.1f}%)",
            f"📈 CANSLIM Score: {result.score_total:.0f}/100 {result.signal_emoji} {result.signal}",
            "",
            f"📉 TECHNICAL (Score: {result.score_technical:.0f})",
            f"• RSI(14): {tech.rsi:.0f} ({tech.rsi_signal})",
            f"• MA: {'✅' if tech.above_ma20 else '❌'} MA20 | {'✅' if tech.above_ma50 else '❌'} MA50 | {'✅' if tech.above_ma200 else '❌'} MA200",
            f"• RS Rating: {tech.rs_rating}",
            f"• Volume: {tech.volume_ratio:.1f}x avg ({tech.volume_signal})",
            "",
            f"💼 FUNDAMENTAL (Score: {result.score_fundamental:.0f})",
            f"• EPS Growth Q/Q: {fund.eps_growth_qoq:+.1f}%",
            f"• EPS Growth Y/Y: {fund.eps_growth_yoy:+.1f}%",
            f"• ROE: {fund.roe:.1f}% | ROA: {fund.roa:.1f}%",
            f"• PE: {fund.pe:.1f} | PB: {fund.pb:.1f}",
            "",
            f"📐 PATTERN: {pattern.pattern_type}",
            f"• Quality: {pattern.pattern_quality:.0f}%",
            f"• Buy Point: {pattern.buy_point:,.0f}" if pattern.buy_point > 0 else "• Buy Point: N/A",
            f"• Breakout Ready: {'✅' if pattern.breakout_ready else '❌'}",
            "",
            f"🎯 TRADING PLAN:",
            f"• Entry Zone: {plan.entry_low:,.0f} - {plan.entry_high:,.0f}",
            f"• Stop Loss: {plan.stop_loss:,.0f} ({plan.stop_loss_pct:.0f}%)",
            f"• Target 1: {plan.target1:,.0f} (+{plan.target1_pct:.0f}%)",
            f"• Target 2: {plan.target2:,.0f} (+{plan.target2_pct:.0f}%)",
            f"• R:R = 1:{plan.risk_reward}",
        ]

        # Add AI Analysis if available
        if result.ai_analysis:
            lines.extend([
                "",
                "🤖 PHÂN TÍCH AI (Claude):",
                "━━━━━━━━━━━━━━━━━━━━━━",
                result.ai_analysis,
            ])

        return "\n".join(lines)

    def to_dict(self, result: StockAnalysis) -> dict:
        """Convert StockAnalysis to dict"""
        return {
            'symbol': result.symbol,
            'name': result.name,
            'timestamp': result.timestamp,
            'scores': {
                'technical': result.score_technical,
                'fundamental': result.score_fundamental,
                'pattern': result.score_pattern,
                'total': result.score_total,
            },
            'signal': result.signal,
            'signal_emoji': result.signal_emoji,
            'technical': asdict(result.technical) if result.technical else {},
            'fundamental': asdict(result.fundamental) if result.fundamental else {},
            'pattern': asdict(result.pattern) if result.pattern else {},
            'trading_plan': asdict(result.trading_plan) if result.trading_plan else {},
            'error': result.error,
        }


# ══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

_analyzer_instance: Optional[StockAnalyzer] = None

def get_stock_analyzer() -> StockAnalyzer:
    """Lấy singleton instance"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = StockAnalyzer()
    return _analyzer_instance


# ══════════════════════════════════════════════════════════════════════════════
# CLI TEST
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    symbol = sys.argv[1] if len(sys.argv) > 1 else "VCB"

    print(f"\n{'='*60}")
    print(f"STOCK ANALYZER - Testing {symbol}")
    print(f"{'='*60}\n")

    analyzer = StockAnalyzer()
    summary = analyzer.get_quick_summary(symbol)
    print(summary)

    print(f"\n{'='*60}")
    print("TEST COMPLETE")
    print(f"{'='*60}")
