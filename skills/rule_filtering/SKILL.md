---
name: rule_filtering
description: Applies the 6 hard drops + 3 soft tags from rules.md in the exact spec order. Owns State 3. Deterministic — no LLM judgment in this stage.
---

# Skill: rule_filtering

## Purpose

Cut the candidate pool down to a rule-passing set, with every surviving candidate tagged with its priority tier and any soft flags. The ranker then picks the final 4-7 from this set.

## When to invoke

Immediately after `candidate_generation` (transition State 2 → State 3).

## The rule order — DO NOT REARRANGE

1. Wrong release type → drop
2. Wrong streaming sub-type (film vs series) → drop
3. Wrong franchise installment → drop (best-effort via TMDb collection)
4. Wrong series season → drop (proxy: candidate has ≥ N seasons)
5. Theatrical OW outside range → drop. **BOM scrape failure → tag "BO unverified", keep.**
6. Streaming not on approved platform → drop. Linear network → tag "linear/network outlier", keep.
7. Time window: >5y AND not P1 → drop; 3-5y → tag; ≤3y → no tag.
8. IP status (if intake.based_on_ip): tag candidates whose keyword IDs don't match the preferred set.
9. Priority tier: tag P1/P2/P3 (highest wins on multi-pool overlap).

The authoritative spec is `references/rules.md`. If the two ever disagree, the rules doc is right and the engine code is the bug.

## Public API

```python
from scripts.rule_engine import RuleEngine
from scripts.tmdb_client import TMDbClient
from scripts.box_office_scraper import BoxOfficeMojoScraper

tmdb = TMDbClient()
bom = BoxOfficeMojoScraper()
eng = RuleEngine(tmdb=tmdb, bom=bom)

kept, dropped, audit = eng.apply(candidates, intake)
# `kept` is the list to pass to the ranker
# `dropped` and `audit` are for the feedback log
```

## Output

Each `kept` item has the original generator fields PLUS:
- `priority_tier`: `"P1" | "P2" | "P3"`
- `flags`: optional list (`"exceeds ideal range (3-5y)"`, `"BO unverified"`, `"linear/network outlier"`, `"non-IP"`, etc.)
- `distributor`: studio (theatrical) or platform (streaming) string
- `opening_weekend_m`: float (theatrical) or `None`
- `ip_match`: `"exact" | "any" | "none"` (only set when intake.based_on_ip=True)
- `comp_season_number`: int (only set for streaming-series)

## Failure handling

- If `kept < 4` → return the kept list anyway. The orchestrator decides whether to transition to State 6 (failure) and surface relaxation options.

## CLI

```bash
python -m scripts.rule_engine \
  --in /tmp/pool.json \
  --intake /tmp/intake.json \
  --out /tmp/kept.json
```

## Hard rules

- **Apply rules in the exact order above.** Reordering can change which candidates survive and breaks audit reproducibility.
- **Never drop on BOM failure.** Tag and keep.
- **Linear TV is tagged, not dropped.** The output_formatter is responsible for the visible flag and footnote.
- **Audit every action.** Every drop, every tag — written to the feedback log.
