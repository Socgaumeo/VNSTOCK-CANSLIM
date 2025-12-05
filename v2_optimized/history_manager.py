#!/usr/bin/env python3
"""
Module quản lý lịch sử phân tích (History Manager)
Giúp AI "học" từ các báo cáo cũ để đưa ra nhận định tốt hơn.
"""

import os
import re
import glob
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

class HistoryManager:
    def __init__(self, output_dir: str = "./output"):
        self.output_dir = Path(output_dir)
        
    def scan_reports(self, limit: int = 10) -> List[Dict]:
        """
        Đọc N báo cáo gần nhất
        Returns: List các dict chứa thông tin tóm tắt
        """
        if not self.output_dir.exists():
            return []
            
        # Lấy danh sách file .md, sắp xếp theo thời gian (mới nhất trước)
        files = sorted(glob.glob(str(self.output_dir / "canslim_report_*.md")), reverse=True)
        
        history = []
        for file_path in files[:limit]:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                parsed = self._parse_report(content, file_path)
                if parsed:
                    history.append(parsed)
            except Exception as e:
                print(f"⚠️ Error reading report {file_path}: {e}")
                
        return history

    def _parse_report(self, content: str, file_path: str) -> Dict:
        """Phân tích nội dung báo cáo để lấy thông tin quan trọng"""
        data = {
            'date': self._extract_date(content) or os.path.basename(file_path),
            'market': {},
            'sectors': [],
            'picks': []
        }
        
        # 1. Market Timing
        # Tìm dòng: | **Market Color** | 🟢 XANH - TẤN CÔNG |
        market_color_match = re.search(r"\|\s*\*\*Market Color\*\*\s*\|\s*(.*?)\s*\|", content)
        market_score_match = re.search(r"\|\s*\*\*Score\*\*\s*\|\s*(\d+)/100\s*\|", content)
        
        if market_color_match:
            data['market']['color'] = market_color_match.group(1).strip()
        if market_score_match:
            data['market']['score'] = int(market_score_match.group(1))
            
        # 2. Sector Rotation
        # Tìm bảng xếp hạng ngành (Top 3)
        # | 1 | Bất động sản | ...
        sector_matches = re.findall(r"\|\s*([1-3])\s*\|\s*([^|]+)\s*\|", content)
        for rank, name in sector_matches:
            data['sectors'].append(f"#{rank} {name.strip()}")
            
        # 3. Top Picks
        # | 1 | FRT | Tiêu dùng... | ⭐⭐ BUY |
        # Regex tìm các dòng trong bảng Top Picks
        pick_matches = re.findall(r"\|\s*\d+\s*\|\s*([A-Z]{3})\s*\|.*?\|\s*(.*?)\s*\|", content)
        for symbol, signal in pick_matches:
            # Chỉ lấy mã có signal BUY hoặc WATCH
            if "BUY" in signal or "WATCH" in signal:
                clean_signal = "BUY" if "BUY" in signal else "WATCH"
                data['picks'].append(f"{symbol}({clean_signal})")
                
        return data

    def _extract_date(self, content: str) -> Optional[str]:
        """Lấy ngày báo cáo"""
        match = re.search(r"\*\*Ngày:\*\*\s*(.*?)\n", content)
        if match:
            return match.group(1).strip()
        return None

    def get_ai_context(self, limit: int = 5) -> str:
        """
        Tạo chuỗi context để feed cho AI
        """
        history = self.scan_reports(limit)
        if not history:
            return "No historical data available."
            
        context = "### HISTORICAL CONTEXT (Last 5 reports):\n"
        
        for item in history:
            date = item['date']
            market = item.get('market', {})
            sectors = ", ".join(item.get('sectors', []))
            picks = ", ".join(item.get('picks', [])[:5]) # Lấy top 5 picks
            
            context += f"- **{date}**:\n"
            context += f"  • Market: {market.get('color', 'N/A')} (Score: {market.get('score', 'N/A')})\n"
            context += f"  • Top Sectors: {sectors}\n"
            context += f"  • Top Picks: {picks}\n"
            
        return context

if __name__ == "__main__":
    # Test
    hm = HistoryManager()
    print(hm.get_ai_context())
