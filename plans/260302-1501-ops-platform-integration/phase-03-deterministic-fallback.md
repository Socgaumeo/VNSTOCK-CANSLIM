# Phase 03: Deterministic Fallback

## Context Links
- Parent plan: [plan.md](./plan.md)
- Dependencies: [Phase 01 - Context Memo](./phase-01-context-memo-system.md)
- Research: [Multi-Agent Patterns Report](../../plans/reports/research-multi-agent-patterns-20260302.md)
- Current: [ai_providers.py](../../v2_optimized/ai_providers.py), [run_full_pipeline.py](../../v2_optimized/run_full_pipeline.py)

## Overview
- **Date**: 2026-03-02
- **Priority**: P1
- **Status**: complete
- **Effort**: 4h (actual: completed)
- **Description**: Create Jinja2 Markdown templates that generate complete reports when AI APIs fail. Structured data (scores, tables, metrics) always generated deterministically; AI narrative is optional enhancement. After 3 retries, AI returns None and templates fill the gaps.

## Key Insights
- Current AI providers return error strings like `"_____ L___i Gemini: ..."` -- downstream code cannot distinguish error from real analysis
- `_fallback_scoring()` in module1 (line 715) already handles AI-less scoring -- extend pattern to full report
- Report is pure Markdown (.md) -- use Jinja2 with `.md.j2` templates (not HTML)
- AI narrative sections: market timing analysis, sector commentary, stock pick rationale
- Deterministic sections: all tables, scores, trading plans, financial health, sector rankings
- Research recommends: "Separate deterministic (code) from stochastic (AI). Template guarantees output."

## Requirements

### Functional
- FR1: Jinja2 Markdown templates for: market summary, sector rotation, stock picks, trading plan
- FR2: `ReportTemplateRenderer` class: `render(context_memo, ai_narratives=None) -> str`
- FR3: AI providers return `None` on failure (not error string) after 3 retries
- FR4: Pipeline detects `None` AI response and uses template-only mode
- FR5: Template-only report includes all numeric data, tables, and rule-based commentary
- FR6: Rule-based commentary: market color interpretation, signal summary, threshold-based recommendations

### Non-Functional
- NFR1: New dependency: `jinja2` (lightweight, widely used)
- NFR2: Template rendering < 100ms (no API calls)
- NFR3: Template-only report visually similar to AI-enhanced report
- NFR4: Templates stored in `v2_optimized/templates/` directory

## Architecture

```
run_full_pipeline.py
  |
  +-- Module1.run() -> market_report (with or without AI)
  +-- Module2.run() -> sector_report
  +-- Module3.run() -> screener_report
  |
  +-- _generate_combined_report()
        |
        +-- ReportTemplateRenderer(templates_dir)
        |     +-- render_market_section(market_report, ai_narrative)
        |     +-- render_sector_section(sector_report, ai_narrative)
        |     +-- render_screener_section(screener_report, ai_narrative)
        |     +-- render_full_report(all_data, ai_narratives)
        |
        +-- If ai_narrative is None:
              +-- Template inserts rule-based fallback text
              +-- "[AI Analysis unavailable - Rule-based summary below]"
```

### Template Structure

```
v2_optimized/templates/
  +-- base-report.md.j2          # Full report wrapper
  +-- market-timing-section.md.j2    # Module 1 section
  +-- sector-rotation-section.md.j2  # Module 2 section
  +-- stock-picks-section.md.j2      # Module 3 section
  +-- trading-plan-section.md.j2     # Per-stock trading plan
```

### AI Provider Change

```python
# BEFORE (ai_providers.py):
except Exception as e:
    return f"_____ L___i Gemini: {str(e)}"

# AFTER:
except Exception as e:
    print(f"[WARN] AI API failed after retries: {e}")
    return None  # Caller checks for None
```

## Related Code Files

### Create
| File | Lines | Purpose |
|------|-------|---------|
| `v2_optimized/report-template-renderer.py` | ~150 | Jinja2 renderer + rule-based commentary |
| `v2_optimized/templates/base-report.md.j2` | ~60 | Report header/footer template |
| `v2_optimized/templates/market-timing-section.md.j2` | ~50 | Market timing Markdown template |
| `v2_optimized/templates/sector-rotation-section.md.j2` | ~40 | Sector table template |
| `v2_optimized/templates/stock-picks-section.md.j2` | ~80 | Stock picks + trading plan template |

### Modify
| File | Changes |
|------|---------|
| `v2_optimized/ai_providers.py` | All provider `chat()` methods return `None` on final failure (not error string) |
| `v2_optimized/run_full_pipeline.py` | Refactor `_generate_combined_report()` to use ReportTemplateRenderer |
| `v2_optimized/module1_market_timing_v2.py` | Check `ai_analysis is not None` before using |

### Delete
None.

## Implementation Steps

1. **Create `templates/` directory and template files**
   - `base-report.md.j2`: Full report with header (date, disclaimer), sections via `{% include %}` or inline blocks, footer
   - `market-timing-section.md.j2`:
     - Market overview table (color, score, VNIndex, RSI, MACD)
     - Volume Profile table (POC, VA, price position)
     - Key signals list
     - AI narrative block with `{% if ai_narrative %}...{% else %}[Rule-based]{% endif %}`
   - `sector-rotation-section.md.j2`:
     - Sector ranking table (rank, name, change, RS)
     - AI commentary or fallback
   - `stock-picks-section.md.j2`:
     - Top picks table (rank, symbol, sector, score, RS, pattern, signal)
     - Per-stock detail blocks with trading plan
     - Financial health summary table
     - News section per stock

2. **Create `report-template-renderer.py`**
   - `ReportTemplateRenderer.__init__(templates_dir)`: init Jinja2 Environment with FileSystemLoader
   - `render(data: dict) -> str`: render full report from context memo + module reports
   - `_generate_rule_based_market_commentary(market_report) -> str`:
     - If score >= 70: "Market uptrend strong, favor aggressive positioning"
     - If score 40-69: "Market neutral, selective approach recommended"
     - If score < 40: "Market weak, defensive positioning, reduce exposure"
   - `_generate_rule_based_sector_commentary(sector_report) -> str`:
     - List LEADING sectors as "focus", LAGGING as "avoid"
   - `_generate_rule_based_stock_commentary(candidate) -> str`:
     - Pattern type interpretation, score breakdown explanation

3. **Update AI provider error handling (CLEAN BREAK — validated)**
   - In `GeminiProvider.chat()`: change `return f"_____ ..."` to `return None`
   - In `ClaudeProvider.chat()`: change final `return f"_____ ..."` to `return None`
   - In `DeepSeekProvider.chat()`: same change
   - In `OpenAIProvider.chat()`: same change
   - In `GroqProvider.chat()`: same change
   - All retry loops: `print(f"[WARN] ...")` then `return None`
   - **[CRITICAL] Audit ALL callers of AI providers** — find every check for error strings and update:
     - `module1_market_timing_v2.py` — ai_analysis usage
     - `module2_sector_rotation_v3.py` — sector AI commentary
     - `module3_stock_screener_v1.py` — stock AI analysis
     - `run_full_pipeline.py` — combined report generation
     - `run_simultaneous_debate.py` — debate orchestration
     - Any other file using `ai_providers.py` functions

4. **Update `run_full_pipeline.py`**
   - Import `ReportTemplateRenderer` via importlib.util
   - Refactor `_generate_combined_report()`:
     - Build data dict from market_report, sector_report, screener_report
     - Collect AI narratives: `{"market": report.ai_analysis, "sector": sector.ai_analysis, ...}`
     - Pass to renderer: `renderer.render(data=data, ai_narratives=narratives)`
   - Keep existing `_generate_financial_health_report()` and `_generate_dupont_analysis_report()` as data helpers

5. **Update module1 to handle None AI response**
   - In `MarketTimingModule.run()` (line 982):
     ```python
     ai_analysis = self.ai_generator.generate(self.report, history_context)
     self.report.ai_analysis = ai_analysis  # Can be None
     ```
   - Fallback scoring already handles AI unavailability

6. **Add `jinja2` to requirements**
   - `pip install jinja2` (or add to requirements.txt)

7. **Test AI failure scenario**
   - Temporarily set invalid API key
   - Run pipeline, verify report still generates with rule-based commentary
   - Compare template-only vs AI-enhanced report structure

## Todo List

- [x] Create `templates/` directory
- [x] Write `base-report.md.j2` template
- [x] Write `market-timing-section.md.j2` template
- [x] Write `sector-rotation-section.md.j2` template
- [x] Write `stock-picks-section.md.j2` template
- [x] Create `report-template-renderer.py` with ReportTemplateRenderer
- [x] Implement rule-based commentary generators
- [x] Update all AI providers to return None on failure
- [x] Refactor `_generate_combined_report()` to use templates
- [x] Add jinja2 to dependencies
- [x] Test with valid AI key (full report)
- [x] Test with invalid AI key (template-only report)
- [x] Verify report structure matches current output
- [x] Create comprehensive test suite (test_phase03.py)
- [x] Generate test report with 6/6 tests passing

## Success Criteria
- Pipeline completes and generates full Markdown report even when all AI APIs fail
- Template-only report includes all tables, scores, and trading plans
- Rule-based commentary provides actionable (if generic) recommendations
- AI-enhanced report includes narrative sections when APIs succeed
- No breaking changes to existing report consumers (email, Telegram)

## Risk Assessment
| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Template drift from code changes | M | H | Template mirrors report structure, update together |
| Jinja2 template syntax errors | L | L | Test templates on every pipeline change |
| Rule-based commentary too generic | L | M | Iterate on rules based on user feedback |
| Breaking downstream consumers | H | L | Keep same Markdown structure, templates match current format |

## Security Considerations
- Templates contain no sensitive data (API keys, passwords)
- Jinja2 autoescaping not needed (Markdown output, not HTML served to browser)
- Templates stored in codebase (version controlled)

## Next Steps
- Phase 4 news hub adds news section to templates
- Phase 5 bond lab adds macro health section to templates
