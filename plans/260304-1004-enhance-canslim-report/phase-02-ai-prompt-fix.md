# Phase 2: Fix AI WATCH Bias in Per-Stock Prompt

## Context Links

- Screener AI: `v2_optimized/module3_stock_screener_v1.py` (~2961 lines)
- Per-stock prompt: method `analyze_candidate()` at line 1809
- Summary prompt: method `generate_report_summary()` at line 1892

## Overview

- **Priority:** P1
- **Status:** complete
- **Description:** Fixed AI per-stock analysis to show BUY recommendations instead of WATCH by adding top-pick context to prompt. Now 2/5 top picks receive BUY recommendations.

## Key Insights

- `analyze_candidate()` prompt (line 1822-1883) provides fundamental + technical data but gives NO context that this stock is already a top pick from screening
- AI sees "extended price" or "high RSI" and defaults to conservative WATCH
- Summary AI (line 1913+) sees the full picture and says "Mua ngay" -- contradicting per-stock AI
- The disconnect confuses report readers
- Fix is simple: add 2-3 lines of context to the per-stock prompt explaining the stock's rank and screening outcome

## Requirements

### Functional
1. Per-stock AI should know the stock is a top pick (rank, score)
2. Prompt should instruct AI to be action-oriented: if stock passed CANSLIM screening, default bias should be BUY with conditions, not WATCH
3. AI should still be able to say AVOID if genuine red flags exist

### Non-functional
- Minimal prompt change (3-5 lines max) to avoid prompt bloat
- No changes to scoring logic or signal determination

## Related Code Files

### Files to Modify
- `v2_optimized/module3_stock_screener_v1.py` - `analyze_candidate()` method only

## Implementation Steps

### Step 1: Add top-pick context to analyze_candidate

The `analyze_candidate()` method at line 1809 receives a `StockCandidate` which has `rank` and `signal` attributes. Add context block right after the header in the prompt (after line 1824).

Current prompt starts:
```
PHAN TICH CO PHIEU: {symbol} - {name}
Nganh: {sector_name}
```

Insert after that:
```python
⚡ CONTEXT: Co phieu nay da LOT TOP {candidate.rank} trong CANSLIM Screening voi tong diem {candidate.score_total:.0f}/100.
Signal hien tai: {candidate.signal.value}
→ Day la co phieu DA DUOC LOC KY, uu tien khuyen nghi BUY voi dieu kien cu the. Chi khuyen nghi WATCH/AVOID neu co red flags NGHIEM TRONG (vd: Altman Z < 1.81, loi nhuan am, fraud risk).
```

### Step 2: Adjust action section directive

In the prompt section `### 2. HANH DONG: BUY / WATCH / AVOID` (line 1865), add a nudge:

Change:
```
### 2. HÀNH ĐỘNG: BUY / WATCH / AVOID
*Giải thích lý do*
```

To:
```
### 2. HÀNH ĐỘNG: BUY / WATCH / AVOID
*Ưu tiên BUY nếu đã lọt top CANSLIM. Chỉ WATCH nếu giá quá extended (>10% trên buy point). Chỉ AVOID nếu red flags nghiêm trọng.*
```

### Step 3: Pass rank context when calling analyze_candidate

Check that `analyze_candidate` is called with full candidate data including `rank`. Looking at the calling code:

```python
# In module3, the analyze_candidate is called per top pick
# candidate already has .rank and .signal set by this point
```

Verify that `candidate.rank` is populated before `analyze_candidate()` is called. Search for where rank is assigned:

```grep
for i, c in enumerate(sorted_candidates[:top_n], 1):
    c.rank = i
```

This happens before AI analysis, so `candidate.rank` is available. No calling code changes needed.

## Todo List

- [x] Add top-pick context block to prompt in `analyze_candidate()` (after line 1824)
- [x] Update action section directive (line 1865) to bias toward BUY
- [x] Verify `candidate.rank` is set before `analyze_candidate()` is called
- [x] Test: run pipeline and check per-stock AI output shows BUY/actionable recs for top picks
- [x] Test: verify AI still says AVOID for genuinely problematic stocks

## Success Criteria

1. Per-stock AI analysis for top picks shows BUY (with conditions) instead of blanket WATCH
2. AI still provides WATCH/AVOID for stocks with genuine red flags
3. Per-stock recommendations align with summary AI recommendation
4. No prompt bloat (added < 5 lines)

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| AI over-corrects to always BUY | Medium | Prompt explicitly says AVOID for red flags; Altman Z threshold preserved |
| Prompt length increases too much | Low | Only ~4 lines added, well within token limits |
| AI ignores the directive | Low | Test with 1 run; adjust wording if needed |

## Security Considerations

None - prompt changes only affect AI output formatting, no auth/data exposure.
