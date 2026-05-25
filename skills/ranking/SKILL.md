---
name: ranking
description: Sorts surviving candidates by priority tier (P1 > P2 > P3) then recency, then applies Claude's judgment to pick the final 4-7 with tonal fit, distribution diversity, and ≤1 flag. Owns the LLM-judgment portion of State 4.
---

# Skill: ranking

## Purpose

Reduce the rule-engine's kept list (typically 8-30 titles) to the final 4-7 that get rendered into the message.

## When to invoke

Right after `rule_filtering` returns. Transition State 3 → State 4.

## The algorithm — two passes

### Pass 1: Deterministic sort

Sort the kept list by:
1. Priority tier ascending (P1 first, P2, P3 last)
2. Within each tier, recency descending (newest year first)
3. Tiebreak: title ascending alphabetically (stability for tests)

This is implemented inline by Claude (a single Python sorted() call) — no script needed.

```python
def sort_key(c):
    tier_rank = {"P1": 0, "P2": 1, "P3": 2}.get(c["priority_tier"], 3)
    return (tier_rank, -(c.get("year") or 0), c["title"])

ranked = sorted(kept, key=sort_key)
```

### Pass 2: LLM judgment (Claude — that's you)

From the top N of the deterministic ranking, pick the final 4-7. Optimize for:

1. **Audience similarity / tonal fit.** Use the candidate's `overview` field as the main signal. A heist comedy and an action thriller might share a genre code but appeal to different audiences — prefer tonal twins.
2. **Distribution diversity.** Don't pick four Universal releases or four Netflix originals. Spread across studios/platforms when possible.
3. **≤1 flag preferred.** A flagged title costs the caveat sentence. Take at most one.
4. **Year spread.** All-2024 picks look lazy. Spread across the window when possible.

If the kept list has fewer than 4 candidates after rules, **don't pad**. Transition to State 6.

If the kept list has 4-7 candidates, you may keep them all — no judgment needed beyond ordering.

## Output

A `final_list` of 4-7 candidate dicts, in the order they should appear in the message. The ranker is also responsible for the order: ranked by OW for theatrical (highest to lowest), by recency for streaming.

```python
final_list = sorted(picked, key=...)   # by OW desc for theatrical, by year desc for streaming
```

## Hand-off

`final_list` goes to `output_formatter.render_message(final_list, intake)`.

## Hard rules

- **Never pick fewer than 4 or more than 7.** Final list must be 4-7 inclusive.
- **Never reorder by tier in the final output.** The output shows OW-sorted (theatrical) or recency-sorted (streaming) — tier is internal-only.
- **Don't pad with low-relevance fillers.** Honest "not enough comps" is better than a weak suggestion. State 6 exists for this.
