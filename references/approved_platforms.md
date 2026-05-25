# Approved Platforms

The whitelist of streaming services that may appear in a streaming comp suggestion. Anything not on this list is either dropped (most streaming services) or kept with a flag (linear TV).

## Approved (always allowed for streaming comps)

| Platform | TMDb provider IDs (US) | Notes |
|---|---|---|
| Amazon Prime Video | 9, 119 | id 9 = Amazon, id 119 = Prime Video subscription. Either qualifies. |
| Netflix | 8 | |
| HBO Max | 384, 1899 | id 384 = legacy HBO Max, id 1899 = Max rebrand. Treat as same platform. Display as "HBO Max" in output. |
| Hulu | 15 | |
| Disney+ | 337 | |
| Peacock | 386, 387 | id 386 = Peacock Premium, id 387 = Peacock Premium Plus. Either qualifies. |
| Paramount+ | 531 | Includes Paramount+ with Showtime. |

## Approved with caveat — Apple TV+

| Platform | TMDb provider IDs (US) | Notes |
|---|---|---|
| Apple TV+ | 350 | Was not on the original approved list but the analyst team unofficially accepted it for high-quality prestige comps starting late 2024. Treated as approved; no flag needed. |

## Linear TV — flagged outlier only

The following linear networks are NOT dropped, but they only ever appear in the output with a flag and the caveat sentence. The ranker treats them as last-resort fillers (never pick a linear comp if 4+ streaming candidates exist).

ABC, NBC, CBS, Fox, The CW, FX, FXX, Showtime, Starz, AMC, BBC, BBC America, USA Network, TNT, TBS, ESPN, History, Discovery, Lifetime, Hallmark.

In the output, the platform string is the network name (e.g. `FX`, `AMC`). The footnote reads: `* flagged: linear/network distribution, included for tonal fit`.

## Dropped (never appear)

- Cable/satellite-only channels not in the linear list above.
- PVOD-only releases (iTunes, Vudu rental-only, etc.) — TMDb providers will include these, ignore them.
- YouTube TV, Sling, Fubo — those are aggregators, not original distributors.
- Discovery+, Peacock free tier, Tubi, Pluto TV — free/ad-tier-only originals are skipped unless the title also exists on an approved platform.

## How the filter actually decides

`rules.md` rule 6 + the rule engine logic:

1. Pull the TMDb watch providers for the candidate (US region).
2. Look at the `flatrate` array (subscription only — never `buy`, `rent`, `ads`).
3. If ANY provider in `flatrate` matches an approved ID → keep, unflagged.
4. Else if the candidate is on a linear network → keep, **flag as outlier**.
5. Else → drop.

This is in `scripts/rule_engine.py::filter_streaming_platform`.
