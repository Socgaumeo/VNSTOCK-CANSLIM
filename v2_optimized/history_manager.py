#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    HISTORY MANAGER V2 - ENHANCED                              ║
║         So sánh sâu: What-If, RS Trends, Stock Progress Tracking             ║
╚══════════════════════════════════════════════════════════════════════════════╝

Features:
- What-If scenarios comparison
- RS Score & RS Trend per sector
- Stock recommendation tracking over time
- Progress summary
"""

import os
import re
import glob
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from enum import Enum


@dataclass
class SectorData:
    """Dữ liệu ngành"""
    name: str = ""
    change_1d: float = 0.0
    rs_score: int = 0
    rs_trend: str = ""  # IMPROVING, DECLINING, FLAT
    phase: str = ""     # LEADING, LAGGING, IMPROVING


@dataclass
class StockRecommendation:
    """Khuyến nghị cổ phiếu"""
    symbol: str = ""
    sector: str = ""
    score: int = 0
    rs: int = 0
    pattern: str = ""
    signal: str = ""      # STRONG BUY, BUY, WATCH, NEUTRAL
    buy_point: float = 0.0
    stop_loss: float = 0.0
    target: float = 0.0


@dataclass
class WhatIfScenario:
    """Kịch bản What-If"""
    name: str = ""
    probability: int = 0
    trigger: str = ""
    action: str = ""


@dataclass
class ReportData:
    """Dữ liệu báo cáo đã parse"""
    date: str = ""
    filename: str = ""
    
    # Market
    market_color: str = ""
    market_score: int = 0
    vn_index: float = 0.0
    vn_index_change: float = 0.0
    rsi: float = 0.0
    
    # Volume Profile
    poc: float = 0.0
    value_area_low: float = 0.0
    value_area_high: float = 0.0
    
    # What-If Scenarios
    what_if_scenarios: List[WhatIfScenario] = field(default_factory=list)
    
    # Sector Rotation
    sectors: List[SectorData] = field(default_factory=list)
    rotation_clock: str = ""  # EARLY CYCLE, LATE CYCLE, etc.
    
    # Stock Recommendations
    recommendations: List[StockRecommendation] = field(default_factory=list)
    
    # Portfolio Allocation
    allocation_stocks: int = 0
    allocation_cash: int = 0


class HistoryManagerV2:
    """Enhanced History Manager với so sánh sâu"""
    
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        
    def scan_reports(self, limit: int = 10) -> List[ReportData]:
        """Đọc N báo cáo gần nhất với parsing chi tiết"""
        if not self.output_dir.exists():
            return []
            
        files = sorted(glob.glob(str(self.output_dir / "canslim_report_*.md")), reverse=True)
        
        history = []
        for file_path in files[:limit]:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                parsed = self._parse_report_v2(content, file_path)
                if parsed:
                    history.append(parsed)
            except Exception as e:
                print(f"⚠️ Error reading report {file_path}: {e}")
                
        return history

    def _parse_report_v2(self, content: str, file_path: str) -> ReportData:
        """Phân tích chi tiết báo cáo"""
        data = ReportData()
        data.filename = os.path.basename(file_path)
        
        # 1. Date
        date_match = re.search(r"\*\*Ngày:\*\*\s*(.*?)\n", content)
        if date_match:
            data.date = date_match.group(1).strip()
            
        # 2. Market Timing
        market_color_match = re.search(r"\|\s*\*\*Market Color\*\*\s*\|\s*(.*?)\s*\|", content)
        market_score_match = re.search(r"\|\s*\*\*Score\*\*\s*\|\s*(\d+)/100\s*\|", content)
        vn_index_match = re.search(r"\|\s*\*\*VN-Index\*\*\s*\|\s*([\d,]+)\s*\(([\+\-]?[\d.]+)%\)", content)
        rsi_match = re.search(r"\|\s*\*\*RSI\(14\)\*\*\s*\|\s*([\d.]+)\s*\|", content)
        
        if market_color_match:
            data.market_color = market_color_match.group(1).strip()
        if market_score_match:
            data.market_score = int(market_score_match.group(1))
        if vn_index_match:
            data.vn_index = float(vn_index_match.group(1).replace(',', ''))
            data.vn_index_change = float(vn_index_match.group(2))
        if rsi_match:
            data.rsi = float(rsi_match.group(1))
            
        # 3. Volume Profile
        poc_match = re.search(r"\|\s*\*\*POC\*\*\s*\|\s*([\d,]+)\s*\|", content)
        va_match = re.search(r"\|\s*\*\*Value Area\*\*\s*\|\s*([\d,]+)\s*-\s*([\d,]+)\s*\|", content)
        
        if poc_match:
            data.poc = float(poc_match.group(1).replace(',', ''))
        if va_match:
            data.value_area_low = float(va_match.group(1).replace(',', ''))
            data.value_area_high = float(va_match.group(2).replace(',', ''))
            
        # 4. What-If Scenarios
        # Pattern: **Kịch bản 1: Tiếp tục tăng (Xác suất: 30%)**
        # Or: | **KB1: Điều chỉnh (Xác suất: 55%)** |
        whatif_patterns = [
            r"\*\*Kịch bản (\d+):\s*(.*?)\s*\(Xác suất:\s*(\d+)%\)\*\*",
            r"\|\s*\*\*KB(\d+):\s*(.*?)\s*\*\*\s*\|\s*\*\*(\d+)%\*\*",
            r"Kịch bản (\d+).*?\(Xác suất:\s*(\d+)%\).*?[–-]\s*(.*?)(?:\n|$)",
        ]
        
        for pattern in whatif_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                for match in matches:
                    scenario = WhatIfScenario()
                    if len(match) >= 3:
                        scenario.name = match[1] if len(match[1]) > 5 else match[2] if len(match) > 2 else ""
                        scenario.probability = int(match[2]) if match[2].isdigit() else int(match[1]) if match[1].isdigit() else 0
                    if scenario.name and scenario.probability > 0:
                        data.what_if_scenarios.append(scenario)
                break
                
        # 5. Sector Rotation - Bảng xếp hạng
        # | 1 | Tiêu dùng không thiết yếu | -0.23% | 82 |
        sector_pattern = r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([\+\-]?[\d.]+)%\s*\|\s*(\d+)\s*\|"
        sector_matches = re.findall(sector_pattern, content)
        
        for rank, name, change, rs in sector_matches[:7]:  # Top 7 sectors
            sector = SectorData()
            sector.name = name.strip()
            sector.change_1d = float(change)
            sector.rs_score = int(rs)
            
            # Try to find RS Trend from text (IMPROVING, DECLINING, FLAT)
            trend_pattern = rf"{re.escape(sector.name)}.*?RS.*?(IMPROVING|DECLINING|FLAT|📈|📉|➡️)"
            trend_match = re.search(trend_pattern, content, re.IGNORECASE)
            if trend_match:
                trend = trend_match.group(1)
                if "IMPROVING" in trend or "📈" in trend:
                    sector.rs_trend = "IMPROVING"
                elif "DECLINING" in trend or "📉" in trend:
                    sector.rs_trend = "DECLINING"
                else:
                    sector.rs_trend = "FLAT"
                    
            data.sectors.append(sector)
            
        # Rotation Clock
        clock_match = re.search(r"(EARLY CYCLE|LATE CYCLE|MID CYCLE|RECESSION)", content, re.IGNORECASE)
        if clock_match:
            data.rotation_clock = clock_match.group(1).upper()
            
        # 6. Stock Recommendations from Top Picks table
        # | 1 | FRT | Tiêu dùng không thiết yếu | 81 | 94 | Cup & Handle | ⭐⭐⭐ STRONG BUY |
        stock_pattern = r"\|\s*(\d+)\s*\|\s*([A-Z]{3})\s*\|\s*([^|]+?)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"
        stock_matches = re.findall(stock_pattern, content)
        
        for rank, symbol, sector, score, rs, pattern, signal in stock_matches[:10]:
            rec = StockRecommendation()
            rec.symbol = symbol.strip()
            rec.sector = sector.strip()
            rec.score = int(score)
            rec.rs = int(rs)
            rec.pattern = pattern.strip()
            rec.signal = signal.strip()
            
            # Try to find Buy Point from Trading Plan
            bp_pattern = rf"{symbol}.*?Buy Point\*\*\s*\|\s*([\d,]+)"
            bp_match = re.search(bp_pattern, content)
            if bp_match:
                rec.buy_point = float(bp_match.group(1).replace(',', ''))
                
            data.recommendations.append(rec)
            
        # 7. Portfolio Allocation
        alloc_match = re.search(r"(\d+)%\s*(?:Cổ phiếu|CP).*?(\d+)%\s*(?:Tiền mặt|Cash)", content, re.IGNORECASE)
        if alloc_match:
            data.allocation_stocks = int(alloc_match.group(1))
            data.allocation_cash = int(alloc_match.group(2))
            
        return data

    def get_ai_context_v2(self, limit: int = 5) -> str:
        """Tạo context chi tiết hơn cho AI, ưu tiên phiên gần nhất"""
        history = self.scan_reports(limit)
        if not history:
            return "No historical data available."
            
        context = "### 📊 HISTORICAL CONTEXT & PERFORMANCE TRACKING\n\n"
        
        # 1. Highlight the MOST RECENT session
        latest = history[0]
        context += f"#### 🔴 PHIÊN GẦN NHẤT (LATEST): {latest.date}\n"
        context += f"- Market: {latest.market_color} (Score: {latest.market_score}/100)\n"
        context += f"- VN-Index: {latest.vn_index:,.0f} ({latest.vn_index_change:+.2f}%)\n"
        
        if latest.recommendations:
            context += f"- Top Picks: {', '.join([r.symbol for r in latest.recommendations[:5]])}\n"
            context += "  Mã cụ thể:\n"
            for r in latest.recommendations[:5]:
                context += f"  * {r.symbol}: Score={r.score} | RS={r.rs} | {r.pattern} | {r.signal}\n"
        context += "\n"
        
        # 2. Progress Summary
        context += self.generate_progress_summary(limit)
        
        # 3. Older Sessions (Brief)
        if len(history) > 1:
            context += "#### 🕒 CÁC PHIÊN TRƯỚC ĐÓ (OLDER SESSIONS):\n"
            for item in history[1:]:
                context += f"- {item.date}: {item.market_color} | Score: {item.market_score} | VNIndex: {item.vn_index:,.0f}\n"
            context += "\n"
            
        return context

    def track_stock_progress(self, symbol: str, limit: int = 10) -> str:
        """Theo dõi tiến triển của một mã qua nhiều báo cáo"""
        history = self.scan_reports(limit)
        if not history:
            return f"No historical data for {symbol}."
            
        context = f"### 📈 Stock Progress: {symbol}\n\n"
        
        found_count = 0
        for item in history:
            for rec in item.recommendations:
                if rec.symbol == symbol:
                    found_count += 1
                    context += f"**{item.date}:**\n"
                    context += f"- Score: {rec.score} | RS: {rec.rs}\n"
                    context += f"- Pattern: {rec.pattern}\n"
                    context += f"- Signal: {rec.signal}\n"
                    if rec.buy_point > 0:
                        context += f"- Buy Point: {rec.buy_point:,.0f}\n"
                    context += "\n"
                    break
                    
        if found_count == 0:
            context += f"⚠️ {symbol} was not found in recent reports.\n"
        else:
            context += f"📊 {symbol} appeared in {found_count}/{len(history)} reports.\n"
            
        return context

    def compare_sector_rotation(self, limit: int = 5) -> str:
        """So sánh thay đổi RS ngành qua thời gian"""
        history = self.scan_reports(limit)
        if len(history) < 2:
            return "Not enough data for sector comparison."
            
        context = "### 🔄 Sector Rotation Progress\n\n"
        
        # Collect all sectors
        sector_history = {}
        for item in history:
            for s in item.sectors:
                if s.name not in sector_history:
                    sector_history[s.name] = []
                sector_history[s.name].append({
                    'date': item.date,
                    'rs': s.rs_score,
                    'trend': s.rs_trend,
                    'change': s.change_1d
                })
                
        # Build comparison
        context += "| Ngành | RS Latest | RS Change | Trend History |\n"
        context += "|-------|-----------|-----------|---------------|\n"
        
        for name, data in sector_history.items():
            if len(data) >= 2:
                latest_rs = data[0]['rs']
                oldest_rs = data[-1]['rs']
                rs_change = latest_rs - oldest_rs
                trend_icons = " → ".join([d['trend'][:3] if d['trend'] else "?" for d in data[:3]])
                
                change_str = f"+{rs_change}" if rs_change > 0 else str(rs_change)
                context += f"| {name} | {latest_rs} | {change_str} | {trend_icons} |\n"
                
        return context

    def generate_progress_summary(self, limit: int = 5) -> str:
        """Tạo tóm tắt tiến triển tổng thể"""
        history = self.scan_reports(limit)
        if not history:
            return "No data for progress summary."
            
        context = "### 📋 PROGRESS SUMMARY\n\n"
        
        # 1. Market Score Trend
        scores = [(h.date, h.market_score) for h in history if h.market_score > 0]
        if len(scores) >= 2:
            latest, oldest = scores[0][1], scores[-1][1]
            trend = "📈 Improving" if latest > oldest else "📉 Declining" if latest < oldest else "➡️ Stable"
            context += f"**Market Score Trend:** {oldest} → {latest} ({trend})\n\n"
            
        # 2. Top Persistent Stocks (appear multiple times)
        stock_count = {}
        for item in history:
            for rec in item.recommendations[:10]:
                if rec.symbol not in stock_count:
                    stock_count[rec.symbol] = {'count': 0, 'signals': [], 'scores': []}
                stock_count[rec.symbol]['count'] += 1
                stock_count[rec.symbol]['signals'].append(rec.signal)
                stock_count[rec.symbol]['scores'].append(rec.score)
                
        persistent = [(sym, data) for sym, data in stock_count.items() if data['count'] >= 2]
        persistent.sort(key=lambda x: x[1]['count'], reverse=True)
        
        if persistent:
            context += "**🎯 Persistent Top Picks (appeared ≥2 times):**\n"
            for sym, data in persistent[:5]:
                avg_score = sum(data['scores']) / len(data['scores'])
                latest_signal = data['signals'][0]
                context += f"- {sym}: {data['count']}x appearances | Avg Score: {avg_score:.0f} | Latest: {latest_signal}\n"
            context += "\n"
            
        # 3. What-If Scenario Accuracy (nếu có thể so sánh)
        if len(history) >= 2:
            context += "**🔮 What-If Scenario Review:**\n"
            if history[1].what_if_scenarios:
                for sc in history[1].what_if_scenarios[:3]:
                    context += f"- Previous: {sc.name} ({sc.probability}%) → Check actual result\n"
            context += "\n"
            
        # 4. Rotation Clock History
        clocks = [(h.date, h.rotation_clock) for h in history if h.rotation_clock]
        if clocks:
            context += f"**🕐 Rotation Clock History:** {' → '.join([c[1] for c in clocks[:3]])}\n\n"
            
        return context
    
    def get_mid_session_data(self, date: str = None) -> Optional[dict]:
        """
        Đọc dữ liệu giữa phiên từ JSON file
        
        Args:
            date: Date string in YYYYMMDD format. If None, uses today.
            
        Returns:
            dict with mid-session data or None if not found
        """
        import json
        
        if date is None:
            date = datetime.now().strftime('%Y%m%d')
        
        json_file = self.output_dir / f"mid_session_data_{date}.json"
        
        if not json_file.exists():
            return None
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading mid-session data: {e}")
            return None
    
    def get_mid_session_context(self, date: str = None) -> str:
        """
        Tạo context từ dữ liệu giữa phiên để so sánh với cuối ngày
        
        Returns:
            str: Formatted context for AI comparison
        """
        data = self.get_mid_session_data(date)
        
        if not data:
            return ""
        
        context = f"""
### 📊 DỮ LIỆU GIỮA PHIÊN (Mid-Session Snapshot)
**Thời gian:** {data.get('timestamp', 'N/A')}

**🚦 Market Timing (Giữa phiên):**
- Score: {data.get('market', {}).get('score', 'N/A')}/100
- Color: {data.get('market', {}).get('color', 'N/A')}
- Trend: {data.get('market', {}).get('trend', 'N/A')}
"""
        
        vnindex = data.get('market', {}).get('vnindex', {})
        if vnindex:
            context += f"""
**📈 VNIndex (Giữa phiên):**
- Giá: {vnindex.get('price', 0):,.0f} ({vnindex.get('change_1d', 0):+.2f}%)
- RSI: {vnindex.get('rsi_14', 0):.1f}
- A/D Ratio: {data.get('market', {}).get('breadth', {}).get('ad_ratio', 0):.2f}
- Khối ngoại: {data.get('market', {}).get('money_flow', {}).get('foreign_net', 0):+.1f} tỷ
"""
        
        sectors = data.get('sectors', [])
        if sectors:
            context += "\n**🏭 Sector Rankings (Giữa phiên):**\n"
            for s in sectors[:5]:
                context += f"- {s.get('name', 'N/A')}: RS={s.get('rs_rating', 0)} | {s.get('change_1d', 0):+.2f}%\n"
        
        context += "\n---\n"
        
        return context


# Backward compatibility
class HistoryManager(HistoryManagerV2):
    """Alias for backward compatibility"""
    pass


# ══════════════════════════════════════════════════════════════════════════════
# RECOMMENDATION HISTORY TRACKER
# ══════════════════════════════════════════════════════════════════════════════

class TradeStatus(Enum):
    """Trạng thái giao dịch"""
    PENDING = "PENDING"           # Chờ trigger buy point
    TRIGGERED = "TRIGGERED"       # Đã trigger, đang hold
    STOPPED = "STOPPED"           # Hit stop loss
    TARGET_HIT = "TARGET_HIT"     # Đạt target
    EXPIRED = "EXPIRED"           # Quá thời gian theo dõi


@dataclass
class TrackedRecommendation:
    """Khuyến nghị đang được theo dõi"""

    # Basic info
    date: str = ""                          # Ngày khuyến nghị (YYYY-MM-DD)
    symbol: str = ""
    sector: str = ""
    signal: str = ""                        # STRONG BUY, BUY, WATCH
    pattern: str = ""
    score: int = 0
    rs_rating: int = 0

    # Price levels
    price_at_recommendation: float = 0.0    # Giá lúc khuyến nghị
    buy_point: float = 0.0                  # Điểm mua
    stop_loss: float = 0.0                  # Cắt lỗ
    target_price: float = 0.0               # Mục tiêu

    # Tracking (updated daily)
    status: str = "PENDING"                 # PENDING, TRIGGERED, STOPPED, TARGET_HIT, EXPIRED
    buy_point_hit: bool = False
    buy_point_hit_date: str = ""
    triggered_price: float = 0.0            # Giá trigger thực tế
    highest_price_after: float = 0.0        # Giá cao nhất sau trigger
    lowest_price_after: float = 0.0         # Giá thấp nhất sau trigger
    current_price: float = 0.0              # Giá hiện tại
    last_updated: str = ""

    # Performance
    profit_loss_pct: float = 0.0            # % lời/lỗ
    max_profit_pct: float = 0.0             # % lời cao nhất (MAE)
    max_drawdown_pct: float = 0.0           # % drawdown max (MFE)
    holding_days: int = 0                   # Số ngày hold

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'TrackedRecommendation':
        # Handle missing fields with defaults
        valid_fields = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid_fields)


class RecommendationHistoryTracker:
    """
    Theo dõi hiệu suất khuyến nghị qua thời gian

    Usage:
        tracker = RecommendationHistoryTracker()

        # Save daily recommendations
        tracker.save_daily_recommendations(date, picks)

        # Update with current prices
        tracker.update_tracking(current_prices)

        # Get win rates
        rates = tracker.calculate_win_rates()
        print(f"Win Rate: {rates['overall_win_rate']*100:.0f}%")
    """

    def __init__(self, cache_dir: str = "./cache/historical/recommendations"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.master_file = self.cache_dir / "tracking_master.json"
        self.max_tracking_days = 30         # Theo dõi tối đa 30 ngày
        self.history_days = 90              # Giữ lịch sử 90 ngày

    def _load_master(self) -> List[TrackedRecommendation]:
        """Load master tracking file"""
        if not self.master_file.exists():
            return []

        try:
            with open(self.master_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                recs = data.get('recommendations', [])
                return [TrackedRecommendation.from_dict(r) for r in recs]
        except Exception as e:
            print(f"   Warning: Could not load tracking master: {e}")
            return []

    def _save_master(self, recommendations: List[TrackedRecommendation]) -> bool:
        """Save master tracking file"""
        try:
            data = {
                'last_updated': datetime.now().isoformat(),
                'total_count': len(recommendations),
                'recommendations': [r.to_dict() for r in recommendations]
            }

            with open(self.master_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            print(f"   Error saving tracking master: {e}")
            return False

    def save_daily_recommendations(self, date: str,
                                   picks: List[Any],
                                   current_prices: Dict[str, float] = None) -> int:
        """
        Lưu khuyến nghị hàng ngày

        Args:
            date: Date string (YYYY-MM-DD)
            picks: List of StockCandidate or similar objects
            current_prices: Dict of symbol -> current price

        Returns:
            Number of recommendations saved
        """
        if not picks:
            return 0

        # Save daily file
        daily_file = self.cache_dir / f"recommendations_{date.replace('-', '')}.json"

        daily_data = {
            'date': date,
            'count': len(picks),
            'picks': []
        }

        # Load existing master
        master = self._load_master()
        existing_keys = {f"{r.date}_{r.symbol}" for r in master}

        new_recs = []
        for pick in picks:
            # Extract data from pick object
            symbol = getattr(pick, 'symbol', '') or getattr(pick, 'code', '')
            if not symbol:
                continue

            price = current_prices.get(symbol, 0) if current_prices else 0
            if price == 0:
                price = getattr(pick, 'price', 0) or getattr(pick, 'close', 0) or 0

            rec = TrackedRecommendation(
                date=date,
                symbol=symbol,
                sector=getattr(pick, 'sector', '') or getattr(pick, 'industry', ''),
                signal=getattr(pick, 'signal', '') or getattr(pick, 'action', 'WATCH'),
                pattern=getattr(pick, 'pattern', '') or getattr(pick, 'chart_pattern', ''),
                score=int(getattr(pick, 'score', 0) or getattr(pick, 'canslim_score', 0) or 0),
                rs_rating=int(getattr(pick, 'rs_rating', 0) or getattr(pick, 'rs', 0) or 0),
                price_at_recommendation=price,
                buy_point=float(getattr(pick, 'buy_point', 0) or price * 1.02),
                stop_loss=float(getattr(pick, 'stop_loss', 0) or price * 0.92),
                target_price=float(getattr(pick, 'target_price', 0) or getattr(pick, 'target', 0) or price * 1.15),
                status=TradeStatus.PENDING.value,
                current_price=price,
                last_updated=datetime.now().isoformat()
            )

            # Add to daily file
            daily_data['picks'].append(rec.to_dict())

            # Add to master if new
            key = f"{date}_{symbol}"
            if key not in existing_keys:
                new_recs.append(rec)

        # Save daily file
        try:
            with open(daily_file, 'w', encoding='utf-8') as f:
                json.dump(daily_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"   Error saving daily recommendations: {e}")

        # Add new to master and save
        if new_recs:
            master.extend(new_recs)
            self._save_master(master)

        return len(new_recs)

    def update_tracking(self, current_prices: Dict[str, float]) -> Dict[str, int]:
        """
        Cập nhật tracking với giá hiện tại

        Args:
            current_prices: Dict of symbol -> current price

        Returns:
            Dict with update statistics
        """
        master = self._load_master()
        if not master:
            return {'updated': 0, 'triggered': 0, 'stopped': 0, 'target_hit': 0}

        stats = {'updated': 0, 'triggered': 0, 'stopped': 0, 'target_hit': 0}
        today = datetime.now().strftime('%Y-%m-%d')
        cutoff_date = (datetime.now() - timedelta(days=self.max_tracking_days)).strftime('%Y-%m-%d')

        for rec in master:
            # Skip if already closed or expired
            if rec.status in [TradeStatus.STOPPED.value, TradeStatus.TARGET_HIT.value, TradeStatus.EXPIRED.value]:
                continue

            # Check expiration
            if rec.date < cutoff_date:
                rec.status = TradeStatus.EXPIRED.value
                continue

            symbol = rec.symbol
            if symbol not in current_prices:
                continue

            price = current_prices[symbol]
            rec.current_price = price
            rec.last_updated = datetime.now().isoformat()
            stats['updated'] += 1

            # Check buy point trigger
            if rec.status == TradeStatus.PENDING.value:
                if price >= rec.buy_point:
                    rec.buy_point_hit = True
                    rec.buy_point_hit_date = today
                    rec.triggered_price = price
                    rec.status = TradeStatus.TRIGGERED.value
                    rec.highest_price_after = price
                    rec.lowest_price_after = price
                    stats['triggered'] += 1

            # If triggered, track performance
            if rec.status == TradeStatus.TRIGGERED.value:
                rec.highest_price_after = max(rec.highest_price_after, price)
                rec.lowest_price_after = min(rec.lowest_price_after, price) if rec.lowest_price_after > 0 else price

                # Calculate holding days
                try:
                    trigger_date = datetime.strptime(rec.buy_point_hit_date, '%Y-%m-%d')
                    rec.holding_days = (datetime.now() - trigger_date).days
                except:
                    pass

                # Calculate P/L
                if rec.triggered_price > 0:
                    rec.profit_loss_pct = ((price / rec.triggered_price) - 1) * 100
                    rec.max_profit_pct = ((rec.highest_price_after / rec.triggered_price) - 1) * 100
                    rec.max_drawdown_pct = ((rec.lowest_price_after / rec.triggered_price) - 1) * 100

                # Check stop loss
                if price <= rec.stop_loss:
                    rec.status = TradeStatus.STOPPED.value
                    stats['stopped'] += 1

                # Check target
                if price >= rec.target_price:
                    rec.status = TradeStatus.TARGET_HIT.value
                    stats['target_hit'] += 1

        # Save updated master
        self._save_master(master)

        return stats

    def calculate_win_rates(self, days: int = 90) -> Dict:
        """
        Tính win rates và metrics

        Args:
            days: Số ngày để tính (mặc định 90)

        Returns:
            Dict with win rate metrics
        """
        master = self._load_master()
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')

        # Filter by date
        recs = [r for r in master if r.date >= cutoff]

        if not recs:
            return {
                'total_recommendations': 0,
                'overall_win_rate': 0,
                'by_signal': {},
                'by_pattern': {},
            }

        # Count by status
        total = len(recs)
        triggered = [r for r in recs if r.buy_point_hit]
        stopped = [r for r in recs if r.status == TradeStatus.STOPPED.value]
        target_hit = [r for r in recs if r.status == TradeStatus.TARGET_HIT.value]
        pending = [r for r in recs if r.status == TradeStatus.PENDING.value]

        # Win rate (target hit / (stopped + target hit))
        closed_trades = len(stopped) + len(target_hit)
        win_rate = len(target_hit) / closed_trades if closed_trades > 0 else 0

        # Trigger rate
        trigger_rate = len(triggered) / total if total > 0 else 0

        # Average P/L for triggered trades
        triggered_pnl = [r.profit_loss_pct for r in triggered if r.profit_loss_pct != 0]
        avg_pnl = sum(triggered_pnl) / len(triggered_pnl) if triggered_pnl else 0

        # Win rate by signal
        by_signal = {}
        for signal in ['STRONG BUY', 'BUY', 'WATCH']:
            signal_recs = [r for r in recs if signal in r.signal]
            signal_wins = [r for r in signal_recs if r.status == TradeStatus.TARGET_HIT.value]
            signal_losses = [r for r in signal_recs if r.status == TradeStatus.STOPPED.value]
            signal_closed = len(signal_wins) + len(signal_losses)

            by_signal[signal] = {
                'count': len(signal_recs),
                'triggered': len([r for r in signal_recs if r.buy_point_hit]),
                'wins': len(signal_wins),
                'losses': len(signal_losses),
                'win_rate': len(signal_wins) / signal_closed if signal_closed > 0 else 0,
            }

        # Win rate by pattern
        by_pattern = {}
        patterns = set(r.pattern for r in recs if r.pattern)
        for pattern in patterns:
            pat_recs = [r for r in recs if r.pattern == pattern]
            pat_wins = [r for r in pat_recs if r.status == TradeStatus.TARGET_HIT.value]
            pat_losses = [r for r in pat_recs if r.status == TradeStatus.STOPPED.value]
            pat_closed = len(pat_wins) + len(pat_losses)

            if len(pat_recs) >= 3:  # Only include patterns with enough data
                by_pattern[pattern] = {
                    'count': len(pat_recs),
                    'wins': len(pat_wins),
                    'losses': len(pat_losses),
                    'win_rate': len(pat_wins) / pat_closed if pat_closed > 0 else 0,
                }

        return {
            'period_days': days,
            'total_recommendations': total,
            'triggered_count': len(triggered),
            'trigger_rate': trigger_rate,
            'pending_count': len(pending),
            'closed_trades': closed_trades,
            'wins': len(target_hit),
            'losses': len(stopped),
            'overall_win_rate': win_rate,
            'avg_pnl_pct': avg_pnl,
            'by_signal': by_signal,
            'by_pattern': by_pattern,
        }

    def get_active_trades(self) -> List[TrackedRecommendation]:
        """Get all active (triggered but not closed) trades"""
        master = self._load_master()
        return [r for r in master if r.status == TradeStatus.TRIGGERED.value]

    def get_pending_recommendations(self) -> List[TrackedRecommendation]:
        """Get all pending (not yet triggered) recommendations"""
        master = self._load_master()
        cutoff = (datetime.now() - timedelta(days=self.max_tracking_days)).strftime('%Y-%m-%d')
        return [r for r in master if r.status == TradeStatus.PENDING.value and r.date >= cutoff]

    def get_recent_closed(self, days: int = 7) -> List[TrackedRecommendation]:
        """Get recently closed trades"""
        master = self._load_master()
        cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        closed_statuses = [TradeStatus.STOPPED.value, TradeStatus.TARGET_HIT.value]
        return [r for r in master if r.status in closed_statuses and r.date >= cutoff]

    def generate_backtest_report(self, days: int = 90) -> str:
        """
        Tạo báo cáo backtest

        Returns:
            Markdown formatted report
        """
        rates = self.calculate_win_rates(days)
        active = self.get_active_trades()
        pending = self.get_pending_recommendations()

        report = f"""
# 📊 RECOMMENDATION BACKTEST REPORT

**Period:** Last {days} days
**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 📈 Overall Performance

| Metric | Value |
|--------|-------|
| Total Recommendations | {rates['total_recommendations']} |
| Trigger Rate | {rates['trigger_rate']*100:.1f}% |
| Closed Trades | {rates['closed_trades']} |
| **Win Rate** | **{rates['overall_win_rate']*100:.1f}%** |
| Avg P/L (Triggered) | {rates['avg_pnl_pct']:+.1f}% |

---

## 📊 By Signal Type

| Signal | Count | Triggered | Wins | Losses | Win Rate |
|--------|-------|-----------|------|--------|----------|
"""
        for signal, data in rates['by_signal'].items():
            if data['count'] > 0:
                report += f"| {signal} | {data['count']} | {data['triggered']} | {data['wins']} | {data['losses']} | {data['win_rate']*100:.0f}% |\n"

        if rates['by_pattern']:
            report += """
---

## 📐 By Pattern

| Pattern | Count | Wins | Losses | Win Rate |
|---------|-------|------|--------|----------|
"""
            for pattern, data in sorted(rates['by_pattern'].items(), key=lambda x: x[1]['win_rate'], reverse=True):
                report += f"| {pattern} | {data['count']} | {data['wins']} | {data['losses']} | {data['win_rate']*100:.0f}% |\n"

        if active:
            report += f"""
---

## 🔥 Active Trades ({len(active)})

| Symbol | Entry | Current | P/L | Days |
|--------|-------|---------|-----|------|
"""
            for r in sorted(active, key=lambda x: x.profit_loss_pct, reverse=True)[:10]:
                report += f"| {r.symbol} | {r.triggered_price:,.0f} | {r.current_price:,.0f} | {r.profit_loss_pct:+.1f}% | {r.holding_days} |\n"

        if pending:
            report += f"""
---

## ⏳ Pending ({len(pending)})

| Symbol | Rec Price | Buy Point | Gap |
|--------|-----------|-----------|-----|
"""
            for r in pending[:10]:
                gap = ((r.buy_point / r.price_at_recommendation) - 1) * 100 if r.price_at_recommendation > 0 else 0
                report += f"| {r.symbol} | {r.price_at_recommendation:,.0f} | {r.buy_point:,.0f} | {gap:+.1f}% |\n"

        return report

    def cleanup_old_data(self, older_than_days: int = 90):
        """Clean up old recommendation files"""
        cutoff = datetime.now() - timedelta(days=older_than_days)

        # Clean daily files
        for f in self.cache_dir.glob("recommendations_*.json"):
            try:
                date_str = f.stem.replace("recommendations_", "")
                file_date = datetime.strptime(date_str, '%Y%m%d')
                if file_date < cutoff:
                    f.unlink()
                    print(f"   Cleaned up: {f.name}")
            except:
                pass

        # Clean master file - remove old entries
        master = self._load_master()
        cutoff_str = cutoff.strftime('%Y-%m-%d')
        master = [r for r in master if r.date >= cutoff_str or
                  r.status in [TradeStatus.TRIGGERED.value, TradeStatus.PENDING.value]]
        self._save_master(master)

    def get_summary(self) -> Dict:
        """Get summary statistics"""
        master = self._load_master()

        status_counts = {}
        for status in TradeStatus:
            status_counts[status.value] = len([r for r in master if r.status == status.value])

        return {
            'total_tracked': len(master),
            'by_status': status_counts,
            'cache_dir': str(self.cache_dir),
        }


# Singleton
_rec_tracker_instance: Optional[RecommendationHistoryTracker] = None


def get_recommendation_tracker() -> RecommendationHistoryTracker:
    """Get singleton instance"""
    global _rec_tracker_instance
    if _rec_tracker_instance is None:
        _rec_tracker_instance = RecommendationHistoryTracker()
    return _rec_tracker_instance


if __name__ == "__main__":
    # Test
    hm = HistoryManagerV2()
    
    print("=" * 60)
    print("📊 TEST HISTORY MANAGER V2")
    print("=" * 60)
    
    print("\n--- AI CONTEXT V2 ---")
    print(hm.get_ai_context_v2(limit=3))
    
    print("\n--- SECTOR ROTATION COMPARISON ---")
    print(hm.compare_sector_rotation(limit=5))
    
    print("\n--- PROGRESS SUMMARY ---")
    print(hm.generate_progress_summary(limit=5))
