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
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field


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
        """Tạo context chi tiết hơn cho AI"""
        history = self.scan_reports(limit)
        if not history:
            return "No historical data available."
            
        context = "### 📊 HISTORICAL CONTEXT (Enhanced Analysis)\n\n"
        
        for i, item in enumerate(history):
            context += f"---\n#### 📅 Report: {item.date}\n"
            
            # Market Overview
            context += f"\n**🚦 Market:**\n"
            context += f"- Color: {item.market_color}\n"
            context += f"- Score: {item.market_score}/100\n"
            context += f"- VN-Index: {item.vn_index:,.0f} ({item.vn_index_change:+.2f}%)\n"
            context += f"- RSI: {item.rsi:.1f}\n"
            
            # Allocation
            if item.allocation_stocks > 0:
                context += f"- Tỷ trọng: {item.allocation_stocks}% CP / {item.allocation_cash}% Cash\n"
            
            # What-If Scenarios
            if item.what_if_scenarios:
                context += f"\n**🔮 What-If Scenarios:**\n"
                for sc in item.what_if_scenarios[:3]:
                    context += f"- {sc.name}: {sc.probability}%\n"
                    
            # Sector RS Rankings
            if item.sectors:
                context += f"\n**🏭 Sector RS Rankings:**\n"
                for s in item.sectors[:5]:
                    trend_icon = "📈" if s.rs_trend == "IMPROVING" else "📉" if s.rs_trend == "DECLINING" else "➡️"
                    context += f"- {s.name}: RS={s.rs_score} | {s.change_1d:+.2f}% | {trend_icon} {s.rs_trend}\n"
                    
            # Top Recommendations
            if item.recommendations:
                context += f"\n**🏆 Top Recommendations:**\n"
                for r in item.recommendations[:5]:
                    signal_short = "BUY" if "BUY" in r.signal else "WATCH" if "WATCH" in r.signal else "NEUTRAL"
                    context += f"- {r.symbol}: Score={r.score} | RS={r.rs} | {r.pattern} | {signal_short}\n"
                    
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


# Backward compatibility
class HistoryManager(HistoryManagerV2):
    """Alias for backward compatibility"""
    pass


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
