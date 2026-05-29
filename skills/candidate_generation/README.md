---
name: candidate_generation
description: Builds the P1 (director), P2 (top-3 cast), P3 (genre /discover) candidate pools from TMDb in parallel. Dedupes and attaches the metadata downstream stages need. Activates at State 2.
---

# Skill: candidate_generation

## Purpose

Turn the analyst's resolved input title into a pool of ~30-100 unique candidates, each tagged with which pool(s) they came from, ready for the rule engine.

## When to invoke

Once intake is complete and confirmed (transition from State 1 → State 2).

## The three pools

| Pool | Seed | Source | Rationale |
|---|---|---|---|
| P1 | Input title's director (movie) or creator (tv) | `/person/{id}/movie_credits` or `/tv_credits`, filter to same primary genre + last 5y | Strongest signal of tonal fit |
| P2 | Top-3 billed cast | Same as P1, repeated for each cast member | Strong audience-overlap signal |
| P3 | Primary genre | `/discover` with `with_genres` + date window | Catch-all for genre/audience match |

## Public API

```python
from scripts.candidate_generator import CandidateGenerator, resolve_input

# Resolve the analyst's title (assumes single match — disambiguator already ran)
input_meta = resolve_input(tmdb, "How to Rob a Bank", media_type="movie", tmdb_id=1071215)

cg = CandidateGenerator(tmdb=tmdb, time_window_years=5)
result = cg.build_pools(input_meta, intake)
# result["merged"] is the deduped candidate list to hand to the rule engine
```

## Window — why 5 years here vs 3 years in the rule engine

The candidate generator uses a wide 5-year window because the rule engine's recency rule (rule 8) will *tag* things 3-5 years old, not drop them. Catching the wider window here means the ranker has more options to work with.

## Dedupe

A candidate that appears in P1 and P3 (e.g. the director's other film also surfaces in /discover) is kept once, with `pools = {"P1", "P3"}`. The rule engine's priority-tier tagger picks the highest tier.

## Failure handling

- **resolve_input throws TMDbNotFound** → State 6. Ask the analyst to confirm spelling or supply a TMDb ID directly.
- **P1 empty** (no director found, or director has no other genre-matching films in window) → record `gap = {"pool":"P1","reason":"..."}` and continue.
- **P2 empty** → same.
- **P3 empty** → same.
- **All three empty** → State 6 with the full gap report and relaxation options.

## Output shape

```json
{
  "input": { "tmdb_id": 1071215, "media_type": "movie", "title": "...", "primary_genre_id": 35, "director_ids": [123], "cast_ids": [10, 11, 12] },
  "pools": { "P1": [...], "P2": [...], "P3": [...] },
  "merged": [
    { "tmdb_id": 12345, "media_type": "movie", "title": "Argylle", "year": 2024, "primary_genre_id": 35, "genre_ids": [35,28], "pools": ["P2"], "source_person_ids": [11] }
  ],
  "gaps": [{ "pool": "P2", "reason": "no genre-matching films in window for cast member 12" }],
  "window": { "gte": "2021-05-25", "lte": "2026-05-25" }
}
```

## CLI

```bash
python -m scripts.candidate_generator \
  --title "How to Rob a Bank" \
  --type theatrical \
  --tmdb-id 1071215 \
  --out /tmp/pool.json
```

## Hard rules

- **Always exclude the input title from its own pools.** Self-referencing comps are useless.
- **Always set `primary_genre_id`** on candidates that didn't already carry it (use input's primary genre as fallback).
- **Never call `resolve_input` without first running disambiguator** if the search returns >1 result. `resolve_input` raises if it sees ambiguity.
