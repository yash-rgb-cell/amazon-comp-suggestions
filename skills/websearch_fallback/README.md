---
name: websearch_fallback
description: Degraded-mode workflow Claude follows when TMDb is unreachable (network outage, bad key, sandbox proxy block). Replaces TMDb calls with Claude's WebSearch tool. Lower fidelity but keeps the skill working end-to-end.
---

# Skill: websearch_fallback

## Purpose

The primary skill flow depends on TMDb for nearly every data lookup (search, credits, providers, keywords, discover). When TMDb is unreachable, the skill would otherwise fail at State 2. This sub-skill is the documented workaround — same 8-state pipeline, same output template, same feedback log, just with Claude's `WebSearch` tool standing in for TMDb endpoints.

## When to activate

At the start of every session, the orchestrator runs:

```bash
python -m scripts.health_check --quiet
```

Exit codes:
- `0` → TMDb reachable, run the normal flow
- `1` → TMDb unreachable but Claude's WebSearch is available → **activate this sub-skill**
- `2` → neither available → State 6 (fatal failure)

Common reasons exit code 1 fires:
- TMDb domain blocked by the user's corporate network / Cowork sandbox allowlist
- `TMDB_API_KEY` missing or invalid
- TMDb is experiencing an outage (rare)
- Per-user rate limit hit (very rare at LF's volume)

When activated, tell the analyst once at the top:

> Heads up — TMDb isn't reachable right now, so I'm using web search as a fallback. Results may be less comprehensive than usual. I'll flag anything I can't verify.

## What changes vs the normal flow

| Stage | Normal (TMDb) | Fallback (WebSearch) |
|---|---|---|
| 1. Intake | Disambiguate via `/search/multi` | Disambiguate via WebSearch: `"<title> film OR series wikipedia"` — present hits ≥2 to analyst |
| 2. Candidate generation | P1/P2/P3 via TMDb credits + discover | Build narrower pools — see "Pool building in fallback" below |
| 3. Rule filtering | Apply all 9 rules deterministically | Apply rules best-effort; flag any data point that's unverified |
| 4. Ranking + draft | Sort by tier+recency, pick 4-7 | Same logic; outputs may have more `BO unverified` and `platform unverified` flags |
| 5. Refinement loop | Same six intents | Same six intents; "correction" intent re-runs WebSearch instead of BOM |
| 6. Failure | Triggered if <4 candidates survive rules | Same trigger; relaxation options identical |
| 7. Finalize + log | Write log with `mode: "tmdb"` | Write log with `mode: "websearch_fallback"` (schema v2) |
| 8. Post-delivery | Find by title, append amazon_feedback | Unchanged |

## Pool building in fallback

Three short WebSearch queries replace the TMDb candidate generator. Run them in this order, dedupe by title:

### P1 — director / creator (one search)

For movies:
```
WebSearch: "<director name> directed films <genre> 2021..2026"
```

For TV:
```
WebSearch: "<creator name> created TV series <genre> 2021..2026"
```

Parse the top 10 results. Pull title + year out of snippets. Skip the input title itself.

### P2 — top-billed cast (one search per cast member, max 3)

```
WebSearch: "<actor name> films <genre> 2021..2026 -<input title>"
WebSearch: "<actor name 2> films <genre> 2021..2026 -<input title>"
WebSearch: "<actor name 3> films <genre> 2021..2026 -<input title>"
```

Cast comes from Claude's training knowledge if the input title is well-known, OR from a prior WebSearch on the input title's Wikipedia page if not.

### P3 — genre / discover proxy (one search)

For theatrical:
```
WebSearch: "<genre> films 2024 2025 opening weekend box office $<min>M to $<max>M"
```

For streaming:
```
WebSearch: "<genre> <platform list> series 2023 2024 2025"
```

Parse top 15 results. Many will already overlap with P1/P2.

## Rule application in fallback

Same rule order as `references/rules.md`. Per-rule notes:

| Rule | In fallback |
|---|---|
| 1. Wrong release type | OK — analyst's intake says theatrical or streaming, Claude knows from training/WebSearch |
| 2. Wrong streaming subtype | OK — same as above |
| 3. Wrong franchise installment | Best-effort. Claude searches `"<candidate> sequel installment"`. If unsure → tag `installment unverified` and keep |
| 4. Wrong series season | Best-effort. WebSearch `"<series> number of seasons"`. If unsure → keep with tag |
| 5. Theatrical OW in range | WebSearch `"<title> 2024 opening weekend box office"` per candidate. Source must be Box Office Mojo, Variety, Deadline, or The Numbers. If <2 sources agree → tag `BO unverified` |
| 6. Streaming approved platform | WebSearch `"<title> where to stream US"`. If platform isn't on the approved list → drop. If unsure → tag `platform unverified` |
| 7. Linear TV flagged outlier | Same as normal — linear networks recognized by name |
| 8. Time window | OK — release year is in the WebSearch snippet, no extra lookup needed |
| 13. IP status | Best-effort. Claude knows most IP-based titles from training. If unsure → tag `IP status unverified` |

Any candidate with 2+ "unverified" tags should be deprioritized in the ranker.

## Output formatting in fallback

Unchanged — same `output_formatter.py` template. The flag/footnote system already accommodates "BO unverified" and similar tags, so degraded data surfaces naturally to the analyst.

The opening line may include an additional note when the entire session ran in fallback:

> Sure thing — ideas below! Put together an initial list based on what's publicly available about the title as of now, but let us know if you've seen any of the material and it plays differently than it currently sounds. *(Note: ran in degraded mode this session — some metadata is from web search rather than our usual data source. Worth a quick spot-check.)*

Only add the parenthetical when ≥2 final-list titles carry "unverified" tags. Otherwise omit it — single unverified tags surface in the footnote already.

## Feedback log in fallback

The log schema (v2+) has a `mode` field at the top level:

```json
{
  "schema_version": 2,
  "mode": "websearch_fallback",
  "health_check": {
    "tmdb": {"reachable": false, "reason": "proxy blocked: 403", "key_present": true},
    "bom":  {"reachable": false, "reason": "proxy blocked: 403"}
  },
  ...
}
```

This makes degraded sessions auditable — when LF later queries the feedback dataset, they can filter to `mode=tmdb` for the clean accuracy benchmark and exclude fallback sessions where data quality is mixed.

## What this sub-skill does NOT change

- The 7-question intake — analyst still answers the same questions
- The output template — same Slack-style format
- The refinement loop — same 6 intents
- The State-7 finalize behavior
- The State-8 post-delivery feedback flow
- The hard rule that disambiguation never auto-picks

## Hard rules in fallback mode

- **Always tell the analyst upfront** that this is a degraded session.
- **Never silently skip a rule** because data is unavailable. Tag the candidate as "X unverified" and keep it visible.
- **Always log `mode: "websearch_fallback"`** so the session is auditable.
- **Always run the health check at session start** — don't trust state from a prior session.

## Verifying the fallback is live

```bash
# Quick CLI check
python -m scripts.health_check
# Look at the "mode" field in the JSON output
```

If `mode == "tmdb"`, the normal flow runs. If `mode == "websearch_fallback"`, this sub-skill is activated.
