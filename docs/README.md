# VNSTOCK-CANSLIM Documentation

**Last Updated:** 2026-02-23
**Project Status:** MVP Complete - All 7 phases delivered

## Quick Navigation

### Getting Started
- **README.md** (in project root) - Quick start, setup, running modules
- **codebase-summary.md** (this folder) - Module listing, file organization, statistics

### Architecture & Design
- **system-architecture.md** - High-level architecture, component interactions, data flow
- **code-standards.md** - Coding guidelines, patterns, VN market conventions, security

### Project Management
- **project-roadmap.md** - Phase status, completed features, future milestones
- **project-changelog.md** - Version history, feature additions, breaking changes

---

## Documentation Structure

```
docs/
├── README.md                    ← You are here
├── codebase-summary.md          # Module listing & architecture overview
├── system-architecture.md       # Detailed component architecture
├── code-standards.md            # Coding guidelines & best practices
├── project-roadmap.md           # Phase progress & future roadmap
└── project-changelog.md         # Version history & changes
```

---

## What's New (v2.7.0)

### Financial Analysis Integration Complete
Seven new modules (862 lines total) integrated into screening pipeline:

1. **financial_health_scorer.py** (112 LOC)
   - Piotroski F-Score (0-9) - accounting quality assessment
   - Altman Z-Score - distress detection + hard reject gate
   - Vietnam-adjusted CFO/NI threshold (0.8x)

2. **valuation-scorer.py** (143 LOC)
   - PEG ratio calculation (PE / earnings growth)
   - Valuation classification (cheap/fair/expensive)

3. **risk-metrics-calculator.py** (154 LOC)
   - Beta vs VNINDEX
   - Annualized volatility, VaR, Sharpe/Sortino ratios
   - Maximum drawdown

4. **data-reconciliation-checker.py** (122 LOC)
   - Validates computed ratios vs provider data
   - PE, PB, ROE, ROA validation
   - Divergence reporting (>5% variance flagged)

5. **industry_analyzer.py** (140 LOC)
   - Banking: NIM, LDR analysis
   - Real Estate: D/E ratio, land bank years
   - Retail: DSI, CCC (cash conversion cycle)

6. **dupont-analyzer.py** (125 LOC)
   - ROE decomposition: NPM × ATO × EM
   - Component trend analysis

7. **dividend-analyzer.py** (86 LOC)
   - Dividend yield, payout ratio, consistency
   - 3-year dividend CAGR

### Scoring System Integration
- Piotroski: +5 if ≥7, -10 if ≤3
- Altman: -5 if grey zone (1.81-2.99), REJECT if Z < 1.81 (distress)
- PEG: +5 if <1, -5 if >3
- Dividend: +3 if ≥4%
- Industry: +3 if ≥80, -5 if <40

---

## Project Statistics

| Metric | Value |
|--------|-------|
| Total Modules | 33 files |
| Total LOC | ~5,500 (excl. tests) |
| Phase Status | 7/7 Complete ✅ |
| Modularization | 32/33 <200 lines |
| Test Coverage | Manual (comprehensive) |
| CI/CD Status | All checks passing |

---

## Key Features

### Analysis Dimensions (9 total)
1. **Technical** - RS, MA, Volume, RSI, Money Flow, patterns
2. **Fundamental** - C/A/L/P scoring (CANSLIM core)
3. **Financial Health** - Piotroski, Altman
4. **Valuation** - PEG ratio, fair value
5. **Income** - Dividend yield, consistency
6. **Risk** - Beta, volatility, Sharpe, max drawdown
7. **Industry** - Sector-specific metrics
8. **Quality** - DuPont ROE decomposition
9. **Validation** - Ratio reconciliation

### Risk Management
- Altman distress hard reject (Z < 1.81)
- Volatility gate (>60% → size reduction)
- Beta gate (>1.5 → size reduction)
- ATR-based stop-loss placement
- Dynamic trailing stops (Initial → Breakeven → MA10 → MA20)

### Data Management
- SQLite with WAL mode (thread-safe)
- 20 quarters fundamental caching
- 87 VNINDEX historical rows
- Foreign flow tracking
- Signal persistence

---

## For Developers

### Starting Development
1. Read **codebase-summary.md** for module organization
2. Read **code-standards.md** for coding guidelines & VN market patterns
3. Reference **system-architecture.md** for data flow & component interaction

### Adding New Features
1. Check **project-roadmap.md** for planned phases
2. Follow **code-standards.md** checklist
3. Keep files under 200 LOC (split if needed)
4. Add type hints + docstrings
5. Test with real data (no mocks)
6. Update **project-changelog.md** when merging

### Debugging
- Check **system-architecture.md** data flow section
- Review **code-standards.md** "Common Gotchas" section
- VN market conventions: RSI 35/65, ±7% daily limit, ±0.8x Piotroski CFO/NI

### Performance Optimization
- Reference "Performance Guidelines" in **code-standards.md**
- Avoid N+1 queries (batch fetch first)
- Use caching for computed values
- Profile hot paths before optimizing

---

## Common Tasks

### Understanding the Screening Flow
See **system-architecture.md** → "Data Flow During Screening" section

### Adding a New Analysis Module
1. Create `v2_optimized/new-module.py` (keep <200 lines)
2. Write stateless functions (no DB reads inside)
3. Accept pre-fetched data as parameters
4. Return dict with results
5. Integrate in `module3_stock_screener_v1.py`
6. Add bonus/penalty scoring
7. Update docs (codebase-summary.md, changelog)

### Integrating with Portfolio Management
See **system-architecture.md** → "Position Sizing" section
1. Calculate score in screener
2. Pass to `portfolio/position_sizer.py`
3. Apply risk gates (Altman, volatility, beta)
4. Calculate ATR-based position size
5. Persist in signal_store

### Backtesting a Strategy
1. Run `python run_full_pipeline.py` to generate signals
2. Run `python run_backtest.py` to replay trades
3. Review `output/backtest_report_*.md` for P&L

---

## FAQ

**Q: Why no database for v2.0-2.1?**
A: Batch CLI initially (no persistence needed). Database added in v2.1 for caching + portfolio tracking.

**Q: Why 0.8x for Piotroski CFO/NI (not >1)?**
A: Vietnam market adjustment - strict >1.0 is too harsh due to different working capital management.

**Q: Why Altman < 1.81 is hard reject?**
A: Academic consensus - Z < 1.81 = 95% bankruptcy probability within 2 years.

**Q: Can I use this for live trading?**
A: With caution. Backtesting is on historical data; live execution needs bid-ask management + slippage modeling.

**Q: What about news sentiment?**
A: Planned for v3.0 (2026 Q4). Currently news_analyzer.py is stub.

**Q: How do I add more stocks?**
A: Edit `config.py` WATCHLIST; run `python run_full_pipeline.py`. Screener auto-scales.

---

## Version Info

- **Current**: v2.7.0 (MVP complete)
- **Python**: 3.10+
- **Key Libraries**: vnstock 3.3.0+, pandas 2.0+, numpy 1.24+
- **Database**: SQLite with WAL mode
- **Last Updated**: 2026-02-23

---

## Support & Contribution

### Issues & Questions
1. Check **codebase-summary.md** → "Lessons Learned" section
2. Check **code-standards.md** → "Common Gotchas & Fixes" section
3. Review relevant phase doc in **project-roadmap.md**

### Contributing
1. Create feature branch from `main`
2. Follow **code-standards.md** guidelines
3. Keep commits focused (one feature per commit)
4. Test before push (no failing tests)
5. Update docs (changelog, roadmap, relevant READMEs)
6. Create PR with clear description

### Security
- Never commit API keys (use `.env` + `config.py`)
- Use parameterized SQL queries
- Validate all external input
- Review **code-standards.md** "Security Guidelines" before deploying

---

## Document Maintenance

These docs are maintained together with code. When updating code:
1. Update **codebase-summary.md** if adding/removing modules
2. Update **system-architecture.md** if changing architecture
3. Update **code-standards.md** if changing patterns/conventions
4. Update **project-changelog.md** for every version bump
5. Update **project-roadmap.md** when completing phases

---

## Next Steps

**For Users**:
- Run `python run_full_pipeline.py` to screen stocks
- Review `output/canslim_report_*.md` for results
- Run `python run_backtest.py` to validate strategy

**For Developers**:
- Start with **codebase-summary.md** to understand structure
- Read **code-standards.md** before writing new code
- Reference **system-architecture.md** for complex flows
- Check **project-roadmap.md** for planned features

**For Contributors**:
- Open an issue describing the improvement
- Follow the checklist in **code-standards.md**
- Submit PR with docs updates
- Wait for code review + test results

---

Generated: 2026-02-23
Maintained by: Project Documentation System

