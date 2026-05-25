---
name: disambiguation
description: When a TMDb title search returns more than one match, present the options to the analyst with enough context to choose instantly. Never guess. Used by intake (Q1) and the refinement loop (add/replace).
---

# Skill: disambiguation

## Purpose

The single most important behavioral rule of the skill: when there's any doubt, ask. This sub-skill formats and presents the question.

## When to invoke

- During intake Q1, after the analyst types the input title and the TMDb search returns >1 result.
- During State 5 refinement, when the analyst says "add [title]" or "swap A for B" and the search returns >1 result.

## Public API

```python
from scripts.disambiguator import disambiguate

options = disambiguate(tmdb, "the grey", max_options=8, enrich_box_office=True)
# returns list of dicts: tmdb_id, media_type, title, year, director, distributor,
# opening_weekend_m, overview, context_line
```

## Sort order

By **recency** (release_date / first_air_date descending). Not by popularity. The point is to give the analyst a clean snapshot of what's recent — popularity tends to surface remakes and franchise reboots that aren't what they meant.

## Presentation

Use `AskUserQuestion` (single-select) with up to 4 options visible at a time. If TMDb returns more than 4, present the 4 most-recent in `AskUserQuestion` and put the rest in the question body:

```
Found multiple titles matching "the grey":
  1. The Grey (2011, theatrical, dir. Joe Carnahan) — Liam Neeson survival thriller — ~$19.6M OW
  2. The Gray Man (2022, streaming, Netflix) — Russo brothers action film
  3. In the Grey (2025, theatrical, dir. Guy Ritchie) — not yet released
  4. The Gentlemen (2020, theatrical, STX, dir. Guy Ritchie) — ~$11M OW

(also: The Grey Zone (2001), Grey Gardens (2009) — let me know if you meant one of those)

Which one did you mean?
```

`AskUserQuestion` options would be:
- "The Grey (2011, theatrical)"
- "The Gray Man (2022, Netflix)"
- "In the Grey (2025, theatrical)"
- "The Gentlemen (2020, theatrical)"

Each option's description carries the rest of the context line.

The analyst can also pick "Other" (auto-injected) to free-text a different title or paste a TMDb URL.

## What to include in each context line

Goal: enough context that the analyst doesn't have to click through. Pack:
- Year (4-digit)
- Media type (theatrical / tv)
- Director (movies) or creator (tv) — first 1-2 names
- Distributor / Network (when known)
- Opening weekend for theatrical (when scraped successfully)
- Overview snippet only if there's still ambiguity (e.g. two films with the same title and year)

## Hard rules

- **Never pick automatically.** Even if one option is wildly more popular.
- **Never sort by popularity.** Sort by recency.
- **If TMDb returns zero results**, do NOT fall back to disambiguation — instead surface the empty result and ask the analyst to confirm spelling or paste a TMDb ID/URL.

## What "single-result" means

`disambiguate()` returning a list of length 1 is the disambiguated case — the orchestrator skips the question and uses the only result. The orchestrator should also collapse exact-title-year matches across media types if the intake answer constrains it (e.g. theatrical intake → only movie results matter).
