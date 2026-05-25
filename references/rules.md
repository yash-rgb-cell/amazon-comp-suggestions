# Authoritative Rules — Amazon Comp Suggestions

These are the rules every sub-skill enforces. The file is the single source of truth — when a rule changes, change it here first, then update the sub-skill that consumes it.

## Distribution-type integrity (hard)

1. **Theatrical and streaming titles never mix in the same suggestion list.** Determined by the analyst's answer to intake question 3 (Release type).
2. **Streaming films and streaming series never mix.** Determined by the analyst's answer to intake question 4a (Film/Series).

## Franchise / installment / season integrity (hard)

3. **Franchise titles must match installment number.** If the input is a sequel (e.g. installment 3), comp candidates that are themselves sequels must be installment 3. Standalones in the same genre are fine; sequels at the wrong installment are dropped. Source: TMDb `collection` info + manual heuristics for non-collection sequels.
4. **Series titles must match season number.** If comping season 2, candidates must be a season 2 of some other series. Pilot/season 1 launches go in their own pool.

## Box office band (hard, theatrical only)

5. **Theatrical opening weekend must fall within the analyst-provided $M range.** Inclusive on both ends. Source: Box Office Mojo scrape. If the scrape fails, the candidate is **tagged "BO unverified" and kept** (not dropped) — see Rule 12 below for how that surfaces.

## Distribution channel (hard, streaming only)

6. **Streaming candidates must be on the approved platform list.** Approved: Amazon Prime Video, Netflix, HBO Max, Hulu, Disney+, Peacock, Paramount+. Source: TMDb watch providers endpoint (US region only).
7. **Linear TV (ABC, NBC, CBS, FX, Showtime, AMC, etc.) is allowed only as an explicitly flagged outlier.** It is not a default suggestion and must never appear unflagged. The footnote in the output must explain the distribution-type exception.

## Recency (soft tags + one hard drop)

8. **Preferred time window: past 3 years.**
   - ≤3y → no flag
   - 3-5y → **flag: "exceeds ideal range"**
   - \>5y → **drop** unless it's a P1 (director/creator) match; in that case keep with a heavier flag ("legacy director-match, outside 5y window")

## Output composition (hard)

9. **Prefer ≤1 flagged title per final list.** This is a soft constraint enforced by the ranker — the LLM picks the final 4-7 from the ranked, filtered list and should optimize for at most one flag. If the only way to fill the list is with 2+ flagged titles, surface a note in the State 7 summary.
10. **Final list must contain exactly 4-7 titles.** Not 3, not 8. If filtering leaves <4 candidates, go to State 6.

## Disambiguation (hard, behavioral)

11. **Never guess when disambiguating.** If a title query returns more than one TMDb match, always present the options to the analyst with enough context (year + type + director + distributor + OW if known) that they can pick instantly. Sort by recency. Do NOT pick the most popular result.
12. **Never silently break a rule.** When the analyst tries to add a title that fails a hard rule, surface the violation and offer concrete options (skip / add anyway with a visible flag / abandon the edit). "BO unverified" candidates show up with that tag visible in the draft so the analyst can decide.

## IP-status (soft tag, ranker hint)

13. **If the input title is IP-based** (based on novel / comic / video game / true story / other, per intake question 2): prefer IP-based candidates in the ranking. Non-IP candidates are not dropped, just flagged as "non-IP" so the ranker can deprioritize them when picking the final 4-7. Source: TMDb keywords (see `references/ip_keywords.md`).

## Priority tier (mandatory tagging)

14. **Every surviving candidate gets a P1, P2, or P3 tag.** A candidate that appears in multiple pools takes the highest priority. Rankings always go P1 → P2 → P3 before recency tie-breaking.

## Rule application order

The rule engine MUST apply rules in this exact order (each rule operates on the surviving set from the previous step):

1. Wrong release type → drop
2. Wrong streaming sub-type (film vs series) → drop
3. Wrong franchise installment → drop
4. Wrong series season → drop
5. Theatrical OW outside range → drop (BO unverified → tag, keep)
6. Streaming not on approved platform → drop (linear TV → tag, keep, must be flagged in output)
7. Time window: >5y AND not P1 → drop; 3-5y → tag; ≤3y → no tag
8. IP status: tag non-IP if input is IP-based
9. Priority tier: tag P1/P2/P3 (highest wins on multi-pool overlap)

## Rule ownership

Rule changes are **developer-owned**, not user-configurable. If the analyst suggests a rule change ("can we extend time window default to 5y?"), thank them and tell them you'll log it as a feedback note — then add the suggestion to `feedback_log/` as a `rule_change_suggestion` entry. Do not edit `rules.md` at runtime.
