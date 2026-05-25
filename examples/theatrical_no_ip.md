# Example: theatrical, no IP — "How to Rob a Bank"

A fully-worked walkthrough based on a real LF request. The analyst asked for comps for the theatrical comedy-crime film *How to Rob a Bank* in the $7M–$40M opening-weekend band.

## Intake transcript

**Analyst:** "Amazon wants comps for How to Rob a Bank"

**Bot:** *[activates intake; runs disambiguator.disambiguate(tmdb, "How to Rob a Bank")]*

> Found two titles matching "How to Rob a Bank":
> 1. How to Rob a Bank (2024, theatrical, dir. Stephen Robert Morse) — documentary about Cody Castagna ~ $0.2M OW
> 2. How to Rob a Bank (2007, theatrical, dir. Andrews Jenkins) — comedy-crime, Nick Stahl
>
> Which one did you mean?

**Analyst:** *(picks option 1)*

**Bot:** Is *How to Rob a Bank* based on pre-existing IP?
> [Yes] [No]

**Analyst:** No

**Bot:** Theatrical or streaming?
> [Theatrical] [Streaming]

**Analyst:** Theatrical

**Bot:** Is this part of a franchise?
> [Yes — franchise/sequel] [No — standalone]

**Analyst:** No

**Bot:** What US opening-weekend range are we targeting, in $M? (give a min and a max, e.g. '7-40')

**Analyst:** 7-40

**Bot:**
> Got it — here's what I'm working with:
>   • Title: How to Rob a Bank (2024)
>   • IP-based? No
>   • Release type: Theatrical
>   • Franchise? No
>   • Opening weekend target: $7M – $40M
>
> Ready to generate candidates?  [Yes — generate] [Let me fix something]

**Analyst:** Yes

## Candidate generation

The bot runs:
```python
input_meta = resolve_input(tmdb, "How to Rob a Bank", media_type="movie", tmdb_id=1071215)
# input_meta = {tmdb_id: 1071215, primary_genre_id: 99 (Documentary), director_ids: [...], cast_ids: [...]}
cg = CandidateGenerator(tmdb, time_window_years=5)
result = cg.build_pools(input_meta, intake)
```

Result (illustrative counts):
```
P1: 3   (Stephen Robert Morse's other docs in 5y window)
P2: 11  (top-3 cast credits in same genre, 5y)
P3: 47  (TMDb /discover, documentary, 2021-05 → 2026-05)
merged: 58 after dedupe
```

The bot writes the full pool to `outputs/candidates_<request_id>.json` and tells the analyst:

> 58 candidates pooled. Running rules…

## Rule filtering

```python
eng = RuleEngine(tmdb, bom)
kept, dropped, audit = eng.apply(result["merged"], intake)
```

Illustrative outcome:
- Rule 1 (release type): drop 0 (all movies)
- Rule 5 (OW range $7-40M): drops 41, keeps 17 (and 6 are "BO unverified")
- Rule 7 (time window): drops 3 outside 5y; tags 4 as 3-5y
- Priority tier: P1=2, P2=4, P3=11

17 candidates remain.

## Ranker

Deterministic sort:
```
P1: A Photographic Memory (2024)
P1: Free For All (2022)
P2: Argylle (2024)
P2: The Fall Guy (2024)
P2: The Gentlemen (2020)
P2: Bullet Train (2022)
...
```

Claude picks 5 (4-7 is the spec, leaning toward 5 here for breadth):

| # | Title | Year | Distributor | OW | Tier | Flags |
|---|---|---|---|---|---|---|
| 1 | The Fall Guy | 2024 | Universal | $27.7M | P2 | — |
| 2 | Bullet Train | 2022 | Sony | $30.1M | P2 | — |
| 3 | Argylle | 2024 | Universal/Apple | $17.3M | P2 | — |
| 4 | The Gentlemen | 2020 | STX | $11.1M | P2 | — |
| 5 | A Photographic Memory | 2024 | (indie) | $0.4M | P1 | — |

Wait — P1 #5 is below the OW band. Rule 5 should have dropped it. Let me re-check: P1's *A Photographic Memory* has OW $0.4M, which is outside [$7M, $40M] → drops at Rule 5. So actual final picks (after rules):

Final 4, ranked by OW desc:

| # | Title | Year | Distributor | OW |
|---|---|---|---|---|
| 1 | Bullet Train | 2022 | Sony | $30.1M |
| 2 | The Fall Guy | 2024 | Universal | $27.7M |
| 3 | Argylle | 2024 | Universal/Apple | $17.3M |
| 4 | The Gentlemen | 2020 | STX | $11.1M |

No flags. Distribution spread (Sony / Universal / Apple / STX). Year spread (2020-2024). ✓

## Rendered draft

```
Sure thing — ideas below! Put together an initial list based on what's publicly available about the title as of now, but let us know if you've seen any of the material and it plays differently than it currently sounds.

Ideas ranked by opening weekend:
- Bullet Train (2022, Sony) — ~$30.1M OW
- The Fall Guy (2024, Universal) — ~$27.7M OW
- Argylle (2024, Universal) — ~$17.3M OW
- The Gentlemen (2020, STX) — ~$11.1M OW
```

## Refinement (analyst is happy first time)

**Analyst:** "looks good, send it"

**Bot:** *(transitions to State 7)*

```
Final message — ready to copy and send to Amazon:
═══════════════════════════════════════════════════
[full message above]
═══════════════════════════════════════════════════

Summary of this session:
  • 58 initial candidates
  • 0 edits during refinement
  • 4 titles in final list
  • Logged to: feedback_log/2026-05/request_b27fdee2-….json
```

## What this example demonstrates

- Multi-match disambiguation at intake (2 different "How to Rob a Bank" films).
- All three pools producing useful candidates.
- Rule 5 doing its job (drops a P1 because OW is too low — priority tier does NOT override hard rules, only soft drops).
- Distribution diversity in the final pick.
- Happy-path one-turn finalization.
