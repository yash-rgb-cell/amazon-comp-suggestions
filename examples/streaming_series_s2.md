# Example: streaming series Season 2 — "Shrinking S2" (illustrative)

A walkthrough showing how the streaming-series flow and the season-number rule work. Real series with realistic comp picks.

## Intake transcript

**Analyst:** "Shrinking S2 — Amazon wants comps"

**Bot:** *(disambiguator returns a single match — clean)*

**Bot:** Is *Shrinking* based on pre-existing IP?
> [Yes] [No]

**Analyst:** No

**Bot:** Theatrical or streaming?

**Analyst:** Streaming

**Bot:** Streaming film or streaming series?
> [Film] [Series]

**Analyst:** Series

**Bot:** Which season are we comping?

**Analyst:** "2"

**Bot:** Summary:
> • Title: Shrinking
> • IP-based? No
> • Release type: Streaming, Series
> • Comping: Season 2
>
> [Yes — generate] [Let me fix something]

**Analyst:** Yes

## What's different for series

- **media_type = "tv"** throughout. Cast comes from `/tv/{id}/credits`. Director is replaced by `creators_of_tv(details)` (i.e. the `created_by` array on TV details).
- **Rule 4 (season match)** runs: for each TV candidate, the bot pulls `/tv/{id}` and counts real seasons (excluding season 0 specials). Only series with **≥ 2 seasons** qualify (proxy for "could be a Season 2 comp").
- **Rule 6 (streaming platform)** runs against the candidate's TMDb watch providers. If the series is on Hulu, Netflix, HBO Max, Disney+, Peacock, Paramount+, Prime Video, or Apple TV+ → keep. Linear (FX, BBC, etc.) → keep but flag.

## Candidate generation (illustrative)

Creators: Bill Lawrence, Brett Goldstein, Jason Segel → P1 modest set (Lawrence has Ted Lasso and Scrubs; Goldstein limited).

Top-3 cast: Jason Segel, Harrison Ford, Jessica Williams → P2 modest set.

P3 /discover: Comedy genre (TMDb code 35) for TV, 2021-05 to 2026-05.

After dedupe: ~45 merged.

## Rule filtering

- Rule 2 (streaming subtype = series): drops any movie candidates that slipped in.
- Rule 4 (≥ 2 seasons): drops candidates that only have 1 season → loses ~8 candidates (newer pilots).
- Rule 6 (streaming platform): drops cable-only / discovery+/AMC+ candidates → loses ~4. *Atlanta* (FX) is kept-with-flag.
- Rule 7 (time window): drops 1 candidate >5y old that isn't P1.

Survivors (illustrative): 12 candidates, including Atlanta (flagged).

## Final pick

| # | Title | Year | Platform | Tier | Flags |
|---|---|---|---|---|---|
| 1 | The Bear S2 | 2023 | Hulu | P3 | — |
| 2 | Severance S2 | 2025 | Apple TV+ | P3 | — |
| 3 | Shrinking S2 (input — excluded) | — | — | — | — |
| 4 | What We Do in the Shadows S2 | 2020 | Hulu | P3 | exceeds ideal range (3-5y) |
| 5 | Atlanta S2 | 2018 | FX | P3 | linear/network outlier |

Picks reduced to 4 unflagged where possible. *What We Do in the Shadows S2* is borderline (5y old, broad comedy match). *Atlanta S2* requires a linear caveat.

Realistic final pick (4 titles, 1 flagged):

| # | Title | Year | Platform | Flag |
|---|---|---|---|---|
| 1 | The Bear S2 | 2023 | Hulu | — |
| 2 | Severance S2 | 2025 | Apple TV+ | — |
| 3 | Slow Horses S2 | 2022 | Apple TV+ | — |
| 4 | What We Do in the Shadows S2 | 2020 | Hulu | exceeds ideal range |

## Rendered draft

```
Sure thing — ideas below! Put together an initial list based on what's publicly available about the title as of now, but let us know if you've seen any of the material and it plays differently than it currently sounds.

One note — including What We Do in the Shadows S2 here despite exceeding our preferred 3-year window; included for tonal/audience fit.

Ideas ranked by recency (Season 2 comps):
- Severance S2 (2025, Apple TV+)
- The Bear S2 (2023, Hulu)
- Slow Horses S2 (2022, Apple TV+)
- What We Do in the Shadows S2 (2020, Hulu) *

* flagged: outside the preferred 3-year recency window
```

## Refinement (analyst tweaks)

**Analyst:** "Swap What We Do in the Shadows for Shrinking S2 itself — wait, that's the input. Try Atlanta S2 instead."

**Bot:** *(handles "replace": runs disambiguator on "Atlanta", finds the series cleanly, runs rule engine on it as a single candidate)*

> Atlanta S2 is on FX (linear network) — qualifies only as a flagged outlier. Want to:
>   (a) Add it anyway with the linear flag
>   (b) Skip — keep the current list

**Analyst:** "(a) add with flag"

**Bot:** *(removes What We Do in the Shadows; adds Atlanta S2 with `flags=["linear/network outlier"]`; re-renders)*

```
Sure thing — ideas below! ...

One note — including Atlanta S2 here despite linear/network distribution; included for tonal/audience fit.

Ideas ranked by recency (Season 2 comps):
- Severance S2 (2025, Apple TV+)
- The Bear S2 (2023, Hulu)
- Slow Horses S2 (2022, Apple TV+)
- Atlanta S2 (2018, FX) *

* flagged: linear/network distribution, included for tonal fit
```

> Swapped What We Do in the Shadows S2 → Atlanta S2 (flagged: linear). List is 4 titles.

**Analyst:** "done"

## What this example demonstrates

- The streaming-series intake branch and its season-number prompt.
- Rule 4 (season count proxy) filtering out 1-season pilots.
- The linear-network flag path for Atlanta (FX).
- A clean State 5 swap with rule-violation surface, analyst override, re-render.
- The series-specific header line and `SN (Year, Platform)` format.
