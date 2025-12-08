#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║     MODULE 4: SPECIAL SCANS - LỌC CỔ PHIẾU ĐẶC BIỆT                          ║
║     1. MA200 Support Scan                                                    ║
║     2. Valuation Scan (P/E, P/B < Industry & Historical Avg)                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import pandas as pd
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime

from config import get_config
from data_collector import get_data_collector, EnhancedStockData
from module3_stock_screener_v1 import SECTOR_STOCKS, SECTOR_NAMES

@dataclass
class ScanResult:
    symbol: str
    sector: str
    price: float
    ma200: float = 0.0
    pe: float = 0.0
    pb: float = 0.0
    
    # Valuation metrics
    industry_pe: float = 0.0
    hist_pe_avg: float = 0.0
    industry_pb: float = 0.0
    hist_pb_avg: float = 0.0
    
    note: str = ""

import time

class SpecialScanner:
    """Scanner cho các tiêu chí đặc biệt"""
    
    def __init__(self):
        self.config = get_config()
        self.collector = get_data_collector(enable_volume_profile=False)
        # Delay mặc định từ config (0.3s) hoặc nhẹ nhàng hơn chút
        self.collector.api_delay = 0.5
        
    def scan_ma200(self, tolerance_pct: float = 5.0, limit: int = 0) -> List[ScanResult]:
        """
        Lọc cổ phiếu có giá nằm quanh MA200
        Args:
            tolerance_pct: Biên độ chấp nhận (%)
            limit: Giới hạn số lượng cổ phiếu scan (0 = all)
        """
        print(f"\n🔍 SCANNING MA200 (Tolerance: ±{tolerance_pct}%)")
        results = []
        
        # Lấy tất cả mã từ các ngành hợp lệ
        all_symbols = []
        for sector, symbols in SECTOR_STOCKS.items():
            all_symbols.extend(symbols)
            
        # Remove duplicates
        all_symbols = list(set(all_symbols))
        
        # Apply limit if needed
        if limit > 0:
            all_symbols = all_symbols[:limit]
            print(f"   ⚠️ Limiting scan to first {limit} stocks")
            
        print(f"   Total symbols to scan: {len(all_symbols)}")
        
        for i, symbol in enumerate(all_symbols):
            if i % 10 == 0:
                print(f"   Processing {i}/{len(all_symbols)}...", end='\r')
                
            try:
                # Lấy data (cần đủ dài để tính MA200)
                stock = self.collector.get_stock_data(symbol, lookback_days=300, include_vp=False)
                
                if stock.price > 0 and stock.ma200 > 0:
                    # Tính khoảng cách % so với MA200
                    diff_pct = abs(stock.price - stock.ma200) / stock.ma200 * 100
                    
                    if diff_pct <= tolerance_pct:
                        # Tìm sector
                        sector_name = "Unknown"
                        for s_code, s_symbols in SECTOR_STOCKS.items():
                            if symbol in s_symbols:
                                sector_name = SECTOR_NAMES.get(s_code, s_code)
                                break
                        
                        # Check trend: Giá > MA200 là tích cực, < MA200 là tiêu cực
                        status = "Above" if stock.price >= stock.ma200 else "Below"
                        
                        results.append(ScanResult(
                            symbol=symbol,
                            sector=sector_name,
                            price=stock.price,
                            ma200=stock.ma200,
                            note=f"{status} MA200 ({diff_pct:.1f}%)"
                        ))
            except Exception as e:
                print(f"   ⚠️ Error {symbol}: {e}")
                
        print(f"   ✅ Found {len(results)} stocks around MA200")
        return sorted(results, key=lambda x: abs(x.price - x.ma200) / x.ma200)

    def scan_valuation(self, metric: str = 'PB', period_years: int = 3, limit: int = 0) -> List[ScanResult]:
        """
        Lọc cổ phiếu định giá rẻ
        Criteria:
        1. Valuation < 1 (cho PB)
        2. Valuation < Industry Average
        3. Valuation < Historical Average (của chính nó)
        
        Args:
            metric: 'PB' hoặc 'PE'
            period_years: Số năm để tính trung bình lịch sử (2 hoặc 3)
            limit: Giới hạn số lượng cổ phiếu scan (0 = all)
        """
        metric = metric.upper()
        print(f"\n🔍 SCANNING VALUATION: {metric} (Cheap vs Industry & History)")
        
        results = []
        periods_count = period_years * 4  # Số quý
        
        # 1. Tính Industry Average trước
        print("   📊 Calculating Industry Averages...")
        industry_metrics = {} # {sector_code: median_metric}
        
        sector_data = {} # {sector_code: [val1, val2, ...]}
        
        # Lấy metric hiện tại cho tất cả mã
        all_symbols = []
        for s_code, symbols in SECTOR_STOCKS.items():
            for sym in symbols:
                all_symbols.append((s_code, sym))
        
        # Apply limit if needed
        if limit > 0:
            all_symbols = all_symbols[:limit]
            print(f"   ⚠️ Limiting scan to first {limit} stocks")
        
        print(f"   Fetching current metrics for {len(all_symbols)} stocks...")
        
        current_metrics = {} # {symbol: val}
        
        for i, (s_code, sym) in enumerate(all_symbols):
            if i % 20 == 0:
                print(f"   Fetching {i}/{len(all_symbols)}...", end='\r')
            
            try:
                ratios = self.collector.get_financial_ratios(sym)
                val = ratios.get(metric.lower(), 0)
                
                if val > 0:
                    current_metrics[sym] = val
                    if s_code not in sector_data:
                        sector_data[s_code] = []
                    sector_data[s_code].append(val)
            except Exception as e:
                print(f"   ⚠️ Error {sym}: {e}")
        
        # Tính median cho từng ngành
        for s_code, values in sector_data.items():
            if values:
                industry_metrics[s_code] = np.median(values)
                print(f"   - {SECTOR_NAMES.get(s_code, s_code)}: Median {metric}={industry_metrics[s_code]:.2f}")
        
        # 2. Scan từng mã
        print("\n   🕵️ Filtering stocks...")
        
        for i, (s_code, sym) in enumerate(all_symbols):
            if sym not in current_metrics:
                continue
                
            current_val = current_metrics[sym]
            industry_avg = industry_metrics.get(s_code, 0)
            
            # Condition 1: PB < 1 (chỉ áp dụng cho PB)
            if metric == 'PB' and current_val >= 1.0:
                continue
                
            # Condition 2: Lower than Industry Avg
            if current_val >= industry_avg:
                continue
            
            # Condition 3: Lower than Historical Avg
            try:
                # Lấy lịch sử
                hist_df = self.collector.get_historical_ratios(sym, periods=periods_count)
                if hist_df.empty:
                    continue
                    
                col_name = metric.lower()
                if col_name not in hist_df.columns:
                    continue
                    
                # Tính trung bình lịch sử (loại bỏ 0 hoặc NaN)
                hist_vals = hist_df[col_name].replace(0, np.nan).dropna()
                if len(hist_vals) < periods_count * 0.5: # Cần ít nhất 50% data
                    continue
                    
                hist_avg = hist_vals.mean()
                
                if current_val < hist_avg:
                    # Passed all criteria
                    res = ScanResult(
                        symbol=sym,
                        sector=SECTOR_NAMES.get(s_code, s_code),
                        price=0, # Sẽ update nếu cần
                        note=f"{metric}={current_val:.2f} < Ind({industry_avg:.2f}) & Hist({hist_avg:.2f})"
                    )
                    
                    if metric == 'PE':
                        res.pe = current_val
                        res.industry_pe = industry_avg
                        res.hist_pe_avg = hist_avg
                    else:
                        res.pb = current_val
                        res.industry_pb = industry_avg
                        res.hist_pb_avg = hist_avg
                    
                    # Lấy giá hiện tại để hiển thị
                    stock = self.collector.get_stock_data(sym, lookback_days=5, include_vp=False)
                    res.price = stock.price
                    
                    results.append(res)
                    print(f"   ✓ {sym}: {metric}={current_val:.2f} (Ind: {industry_avg:.2f}, Hist: {hist_avg:.2f})")
            except Exception as e:
                print(f"   ⚠️ Error processing {sym}: {e}")
        
        return sorted(results, key=lambda x: x.pe if metric == 'PE' else x.pb)

    def generate_report(self, results: List[ScanResult], title: str) -> str:
        """Tạo báo cáo markdown"""
        content = f"# 📊 {title}\n"
        content += f"**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        
        if not results:
            content += "Không tìm thấy cổ phiếu nào thỏa mãn tiêu chí.\n"
            return content
            
        content += f"Found {len(results)} stocks.\n\n"
        
        content += "| Symbol | Sector | Price | Metric | Industry Avg | Hist Avg | Note |\n"
        content += "|--------|--------|-------|--------|--------------|----------|------|\n"
        
        for r in results:
            if r.pe > 0:
                metric_val = f"P/E={r.pe:.2f}"
                ind_val = f"{r.industry_pe:.2f}"
                hist_val = f"{r.hist_pe_avg:.2f}"
            else:
                metric_val = f"P/B={r.pb:.2f}"
                ind_val = f"{r.industry_pb:.2f}"
                hist_val = f"{r.hist_pb_avg:.2f}"
                
            content += f"| **{r.symbol}** | {r.sector} | {r.price:,.0f} | {metric_val} | {ind_val} | {hist_val} | {r.note} |\n"
            
        return content

if __name__ == "__main__":
    scanner = SpecialScanner()
    
    # Test MA200
    # res = scanner.scan_ma200()
    # print(scanner.generate_report(res, "MA200 Scan"))
    
    # Test Valuation
    res = scanner.scan_valuation('PB')
    print(scanner.generate_report(res, "Undervalued P/B Scan"))
