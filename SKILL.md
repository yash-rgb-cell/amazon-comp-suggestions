---
name: amazon-comp-suggestions
description: Drafts the short Slack-style "comp titles" message that an LF analyst sends to Amazon before a launch. Activate when the user mentions Amazon asking for comps, says "build a comp list", "draft a comp message", "suggest comps for [title]", "Amazon wants comps for [title]", uploads or names a film/series and asks for comparable titles by opening weekend / streaming audience, or wants to log Amazon's feedback on a prior comp set. Use also for phrases like "comp titles", "ranked by opening weekend", "give me comps", "what should I send Amazon for X". Internal LF-only — output is always reviewed by the analyst before it leaves.
license: Proprietary
---

# Amazon Comp Suggestions

End-to-end conversational pipeline that turns a single launch-title prompt from an LF analyst into a polished, rule-checked, copy-paste-ready Slack message of 4-7 comp titles to send to Amazon. Every interaction is logged so we can build a feedback dataset and tighten the rules over time.

## When to use this skill

Activate whenever any of these apply:

- The analyst says: "comps for [title]", "draft a comp message", "Amazon wants comps", "build a comp list", "suggest comparable titles", "what should I send Amazon".
- The analyst names a film/series and asks for ranked comparable titles by opening weekend or streaming distribution.
- The analyst returns later with "log Amazon's feedback for [title]" → re-enter State 8.

This is internal LF tooling. Amazon never talks to the bot directly. The analyst always reviews and sends the message themselves.

## The state machine — read this first

The skill is a strict 8-state pipeline. Each state has clear inputs, outputs, transitions, and a dedicated sub-skill that owns it. **Do not skip states. Do not improvise transitions.**

| State | Name | Owner | What it does |
|---|---|---|---|
| 1 | Intake | `skills/intake/README.md` | 7-question conversational tree, validated, with branching |
| 2 | Candidate Generation | `skills/candidate_generation/README.md` | Build P1/P2/P3 TMDb pools in parallel |
| 3 | Rule Filtering | `skills/rule_filtering/README.md` | Apply 6 hard drops + 3 soft tags in order |
| 4 | Ranking + Draft | `skills/ranking/README.md` + `skills/output_formatter/README.md` | Sort, pick top 4-7 with LLM judgment, render message |
| 5 | Refinement Loop | `skills/refinement_loop/README.md` | Multi-turn edits — correction / add / remove / replace / reorder / finalize |
| 6 | Failure | `skills/refinement_loop/README.md` (failure mode) | Honest report + concrete relaxation options |
| 7 | Finalize + Log | `skills/feedback_log/README.md` | Show clean output, write JSON log |
| 8 | Post-Delivery Feedback | `skills/feedback_log/README.md` | Re-entry: append Amazon's response to existing log entry |
| 0 | Health check + (optional) fallback | `skills/websearch_fallback/README.md` | Runs *before* Stage 1. Probes TMDb + BOM; activates degraded WebSearch mode if TMDb is unreachable |

Read the sub-skill README.md whose state you are entering. Each one contains the exact prompts, validation, and transition rules.

## Hard rules (enforced everywhere)

The authoritative rules doc is `references/rules.md`. The summary:

1. Theatrical and streaming titles never mix in the same list.
2. Streaming films and streaming series never mix.
3. Franchise titles must match installment number.
4. Series titles must match season number.
5. Theatrical opening weekend must fall within the analyst-provided range.
6. Streaming candidates must be on the approved platform list (Prime, Netflix, HBO Max, Hulu, Disney+, Peacock, Paramount+).
7. Linear TV is allowed only as an explicitly flagged outlier.
8. Time window: ≤3y no flag, 3-5y flag, >5y drop unless P1 (director/creator match).
9. Prefer ≤1 flagged title per final list.
10. Final list must contain 4-7 titles. No more, no less.
11. Never guess when disambiguating. Always ask.
12. Never silently break a rule. Always surface the override option.

## Setup — required environment

The skill calls TMDb's free API. Set the API key once:

```bash
export TMDB_API_KEY="<your-key-here>"
```

Get a key at https://www.themoviedb.org/settings/api (free, ~15 minute approval). If `TMDB_API_KEY` is missing, the skill fails fast at State 2 with a pointer to that URL.

No other secrets required. Box Office Mojo is scraped (no API), with a 2-second polite delay and aggressive caching for old releases (their numbers don't change).

## Layout — sub-skills and their roles

The skill is composed of single-responsibility sub-skills under `skills/`. Each has its own `README.md` with the deeper spec; read whichever ones are relevant for the state you're entering.

| Sub-skill folder | Role |
|---|---|
| `skills/intake/README.md` | **Entry-point conversational flow.** 7 questions, branching by release type. |
| `skills/tmdb_client/README.md` | TMDb API wrapper — search, person credits, discover, watch providers, keywords. SQLite cache. |
| `skills/box_office_scraper/README.md` | Box Office Mojo opening-weekend scraper. Polite, cached, fragile-by-design. |
| `skills/candidate_generation/README.md` | Builds P1 (director), P2 (top-3 cast), P3 (genre /discover) pools. Dedupes, attaches metadata. |
| `skills/rule_filtering/README.md` | Applies the 6 hard drops + 3 soft tags in fixed order. |
| `skills/ranking/README.md` | Sorts surviving candidates by P1>P2>P3 then recency; picks 4-7 with LLM judgment. |
| `skills/output_formatter/README.md` | Renders the standard Slack-style message (theatrical OR streaming-film OR streaming-series variants). |
| `skills/refinement_loop/README.md` | The multi-turn edit loop. Intent classification (6 classes) and per-intent handlers. |
| `skills/disambiguation/README.md` | When a TMDb search returns >1 match, asks the analyst — never guesses. |
| `skills/feedback_log/README.md` | JSON log writer (State 7) and updater (State 8). One file per request, monthly folders. |
| `skills/websearch_fallback/README.md` | Degraded-mode workflow Claude follows when TMDb is unreachable. Same pipeline, same template, WebSearch instead of TMDb. |

## Scripts — what does the deterministic work

Each script under `scripts/` is callable from the command line for isolated testing AND importable as a module from the orchestrator. The orchestrator (Claude) handles conversation flow + LLM judgment; scripts handle deterministic work (API calls, rule application, formatting, logging).

| Script | Purpose | CLI test |
|---|---|---|
| `scripts/tmdb_client.py` | TMDb endpoints + SQLite cache | `python -m scripts.tmdb_client search-movie "How to Rob a Bank"` |
| `scripts/box_office_scraper.py` | BOM opening-weekend scrape | `python -m scripts.box_office_scraper tt1234567` |
| `scripts/candidate_generator.py` | Runs the 3 pools | `python -m scripts.candidate_generator --title "How to Rob a Bank" --type theatrical` |
| `scripts/rule_engine.py` | Apply hard rules + soft tags | `python -m scripts.rule_engine --in pool.json --intake intake.json` |
| `scripts/disambiguator.py` | TMDb search + multi-match handler | `python -m scripts.disambiguator "the grey"` |
| `scripts/output_formatter.py` | Render the final message | `python -m scripts.output_formatter --in final.json` |
| `scripts/feedback_logger.py` | Write/update the JSON log | `python -m scripts.feedback_logger init …` |
| `scripts/health_check.py` | Probe TMDb + BOM reachability at session start | `python -m scripts.health_check` |

## Canonical execution order

**Stage 0** — at the very start of every session, run `python -m scripts.health_check --quiet`. Exit code 0 → normal flow; exit code 1 → activate `skills/websearch_fallback/README.md` and tell the analyst this is a degraded session; exit code 2 → State 6 (no data source available).

After the analyst has answered the 7 intake questions:

1. **State 2** — `scripts/candidate_generator.py` builds P1/P2/P3 pools (use `disambiguator.py` to resolve the input title if there are multiple TMDb matches).
2. **State 3** — `scripts/rule_engine.py` applies hard rules + soft tags. If <4 candidates survive → State 6.
3. **State 4** — Claude sorts by priority tier then recency, picks 4-7 with judgment for tonal fit + distribution diversity + ≤1 flag. `scripts/output_formatter.py` renders the draft.
4. **State 5** — Show draft, classify each analyst instruction into one of 6 intents, mutate the current list, re-render. Stay until "looks good"/"done"/"send it".
5. **State 7** — Render clean copy-paste output, `scripts/feedback_logger.py init` writes the JSON log.
6. **State 8** (later, optional) — `scripts/feedback_logger.py update` appends Amazon's response.

## Token hygiene

- Do not echo full candidate pools to chat. Save to a scratch file (e.g. `outputs/candidates_<request_id>.json`) and reference counts only.
- Per-turn responses in State 5 should be the regenerated draft + a one-line summary of what changed.
- Never dump the feedback log JSON to chat — it's for the disk, not the conversation.

## When data is missing or off

- TMDb key missing → fail fast at State 2 with the signup URL.
- TMDb can't find the input title → State 6, ask for spelling confirmation or TMDb ID.
- One of P1/P2/P3 pools returns zero → keep going with the others, log the gap.
- All three pools empty OR final filtered <4 → State 6, offer concrete relaxation (extend time window, widen box office band, drop IP-preference).
- Box Office Mojo scrape fails for a candidate → mark `BO unverified`, do NOT drop.
- Box Office Mojo selector breaks (their site redesigned) → see `references/data_sources.md` "Maintenance" section.

## Known fragility points

- **Box Office Mojo HTML selector** — they redesign every ~2 years. Maintenance plan documented in `scripts/box_office_scraper.py` and `references/data_sources.md`.
- **Watch providers cache TTL is 1h** — a candidate that just got pulled from Hulu won't be reflected for up to an hour. Acceptable trade-off for hit rate.
- **TMDb keyword IDs for IP detection** — TMDb occasionally renumbers keywords. `references/ip_keywords.md` lists the IDs we depend on; verify quarterly.