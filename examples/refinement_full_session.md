# Example: full refinement session — every edit intent

This walkthrough exercises every edit intent in State 5 against a single session. Input is the *How to Rob a Bank* (2024 documentary) example from `theatrical_no_ip.md` — pick up after the initial draft.

## Starting state

After State 4, the draft is:

```
Sure thing — ideas below! Put together an initial list based on what's publicly available about the title as of now, but let us know if you've seen any of the material and it plays differently than it currently sounds.

Ideas ranked by opening weekend:
- Bullet Train (2022, Sony) — ~$30.1M OW
- The Fall Guy (2024, Universal) — ~$27.7M OW
- Argylle (2024, Universal) — ~$17.3M OW
- The Gentlemen (2020, STX) — ~$11.1M OW
```

State variable:
```python
state = {
  "intake": {...},
  "current_list": [
    {"title": "Bullet Train", "year": 2022, "distributor": "Sony", "opening_weekend_m": 30.1, ...},
    {"title": "The Fall Guy", "year": 2024, "distributor": "Universal", "opening_weekend_m": 27.7, ...},
    {"title": "Argylle", "year": 2024, "distributor": "Universal", "opening_weekend_m": 17.3, ...},
    {"title": "The Gentlemen", "year": 2020, "distributor": "STX", "opening_weekend_m": 11.1, ...},
  ],
  "edits": [],
  "turn": 0,
}
```

---

## Turn 1 — CORRECTION

**Analyst:** "actually the fall guy did $28.3"

**Bot:** *(intent: correction; find "The Fall Guy"; re-scrape BOM via `bom.opening_weekend("tt1804513")`)*

BOM returns `$27.7M`. Analyst's value (`$28.3M`) differs.

**Bot:** Quick check — BoxOfficeMojo has The Fall Guy's opening at $27.7M. You said $28.3M. Which should I use?
> [Use BOM's $27.7M] [Use my $28.3M]

**Analyst:** "use mine — bom undercounted previews"

**Bot:** *(updates current_list; appends to edits; re-renders)*

> Updated The Fall Guy to $28.3M (analyst override; BOM said $27.7M). Re-ordered by OW.

```
Sure thing — ideas below! ...

Ideas ranked by opening weekend:
- Bullet Train (2022, Sony) — ~$30.1M OW
- The Fall Guy (2024, Universal) — ~$28.3M OW
- Argylle (2024, Universal) — ~$17.3M OW
- The Gentlemen (2020, STX) — ~$11.1M OW
```

`edits.append({"turn": 1, "intent": "correction", "details": {"title": "The Fall Guy", "old_ow": 27.7, "new_ow": 28.3, "source_disagreed": True}})`

---

## Turn 2 — ADD (clean, single match)

**Analyst:** "add bullet train sequel" — wait that doesn't exist. "Add Mission Impossible 7"

**Bot:** *(intent: add; disambiguator returns single match for "Mission Impossible 7" → Dead Reckoning Part One, 2023)*

Runs rule engine on the single candidate:
- Release type: theatrical ✓
- OW: $54.7M → outside range [$7M, $40M] ✗

**Bot:** Mission: Impossible — Dead Reckoning Part One (2023) opened at $54.7M — above our $7-40M band.
> Want to:
>   (a) Skip this title
>   (b) Add it anyway with a "out-of-band reference" flag

**Analyst:** "(a) skip"

**Bot:** Skipped. List unchanged.

`edits.append({"turn": 2, "intent": "add", "details": {"title": "Mission: Impossible — Dead Reckoning Part One", "outcome": "skipped (out of OW band)"}})`

---

## Turn 3 — ADD (multi-match → disambiguation)

**Analyst:** "add the grey"

**Bot:** *(intent: add; disambiguator returns 4 matches)*

> Found multiple titles matching "the grey":
>   1. The Grey (2011, theatrical, dir. Joe Carnahan) — Liam Neeson survival thriller — ~$19.6M OW
>   2. The Gray Man (2022, streaming, Netflix) — Russo brothers action film
>   3. In the Grey (2025, theatrical, dir. Guy Ritchie) — not yet released
>   4. The Gentlemen (2020, theatrical, STX) — already in your list
>
> Which one did you mean?

**Analyst:** "1 — the 2011 Liam Neeson one"

**Bot:** *(runs rule engine on The Grey 2011 as a single candidate)*

- Release type: theatrical ✓
- OW: $19.6M ✓ (in $7-40M band)
- Time window: 2011 → 15 years old → drops on rule 7 (>5y AND not P1)

**Bot:** The Grey (2011) is 15 years old and didn't come from our director/creator pool — that fails the time-window rule.
> Want to:
>   (a) Skip
>   (b) Add anyway with a "legacy reference" flag

**Analyst:** "(b)"

**Bot:** *(adds with `flags=["legacy reference, 15y old"]`; re-renders)*

```
Sure thing — ideas below! ...

One note — including The Grey here despite the title being older than 5 years (legacy director-match); included for tonal/audience fit.

Ideas ranked by opening weekend:
- Bullet Train (2022, Sony) — ~$30.1M OW
- The Fall Guy (2024, Universal) — ~$28.3M OW
- Argylle (2024, Universal) — ~$17.3M OW
- The Grey (2011, Universal) — ~$19.6M OW *
- The Gentlemen (2020, STX) — ~$11.1M OW

* flagged: older than 5 years but kept for director-match relevance
```

Wait — sorted by OW desc, The Grey ($19.6M) belongs above Argylle ($17.3M):

```
- Bullet Train (2022, Sony) — ~$30.1M OW
- The Fall Guy (2024, Universal) — ~$28.3M OW
- The Grey (2011, Universal) — ~$19.6M OW *
- Argylle (2024, Universal) — ~$17.3M OW
- The Gentlemen (2020, STX) — ~$11.1M OW

* flagged: older than 5 years but kept for director-match relevance
```

> Added The Grey (2011) with legacy flag. List is 5 titles.

---

## Turn 4 — REMOVE

**Analyst:** "remove the gentlemen"

**Bot:** *(intent: remove; finds match by title; removes; re-renders)*

```
Sure thing — ideas below! ...

One note — including The Grey here despite the title being older than 5 years; included for tonal/audience fit.

Ideas ranked by opening weekend:
- Bullet Train (2022, Sony) — ~$30.1M OW
- The Fall Guy (2024, Universal) — ~$28.3M OW
- The Grey (2011, Universal) — ~$19.6M OW *
- Argylle (2024, Universal) — ~$17.3M OW

* flagged: older than 5 years but kept for director-match relevance
```

> Removed The Gentlemen. List is 4 titles.

---

## Turn 5 — REPLACE

**Analyst:** "swap the grey for ferrari"

**Bot:** *(intent: replace = remove A + add B)*

Removes The Grey. Then runs disambiguator on "Ferrari" → 3 matches:
> 1. Ferrari (2023, theatrical, dir. Michael Mann) — Adam Driver biographical drama — ~$8.0M OW
> 2. Ferrari (2003, TV mini-series) — older series
> 3. Ferrari: Race to Immortality (2017, documentary) — older

**Analyst:** "1, the Michael Mann one"

**Bot:** Runs rules on Ferrari (2023):
- Theatrical ✓
- OW $8.0M ✓ (in $7-40M)
- Time window: 3y old ✓
- All hard rules pass

Adds. Re-renders:

```
Sure thing — ideas below! ...

Ideas ranked by opening weekend:
- Bullet Train (2022, Sony) — ~$30.1M OW
- The Fall Guy (2024, Universal) — ~$28.3M OW
- Argylle (2024, Universal) — ~$17.3M OW
- Ferrari (2023, NEON) — ~$8.0M OW
```

(Note: no caveat sentence now — The Grey's flag is gone.)

> Swapped The Grey → Ferrari (2023). List is 4 titles, no flags.

---

## Turn 6 — REORDER

**Analyst:** "put argylle first"

**Bot:** *(intent: reorder)*

Reorder is a manual move, so we override the OW-desc sort. After moving Argylle to position 1, the rest stay in their relative order:

```
Sure thing — ideas below! ...

Ideas ranked by opening weekend:
- Argylle (2024, Universal) — ~$17.3M OW
- Bullet Train (2022, Sony) — ~$30.1M OW
- The Fall Guy (2024, Universal) — ~$28.3M OW
- Ferrari (2023, NEON) — ~$8.0M OW
```

> Moved Argylle to position 1. (Note: the header still says "ranked by opening weekend" — if you want a different rationale framing, let me know.)

---

## Turn 7 — FINALIZE

**Analyst:** "send it"

**Bot:** *(intent: finalize; transition to State 7)*

```
Final message — ready to copy and send to Amazon:
═══════════════════════════════════════════════════
Sure thing — ideas below! Put together an initial list based on what's publicly available about the title as of now, but let us know if you've seen any of the material and it plays differently than it currently sounds.

Ideas ranked by opening weekend:
- Argylle (2024, Universal) — ~$17.3M OW
- Bullet Train (2022, Sony) — ~$30.1M OW
- The Fall Guy (2024, Universal) — ~$28.3M OW
- Ferrari (2023, NEON) — ~$8.0M OW
═══════════════════════════════════════════════════

Summary of this session:
  • 58 initial candidates
  • 6 edits during refinement
  • 4 titles in final list
  • Logged to: feedback_log/2026-05/request_b27fdee2-….json
```

## State 8 — three days later

**Analyst:** "log feedback for How to Rob a Bank"

**Bot:** *(searches feedback_log via `find_by_title("How to Rob a Bank")`; finds 1 match)*

> Found your How to Rob a Bank session from 2026-05-25 (4 titles: Argylle, Bullet Train, The Fall Guy, Ferrari).
> What did Amazon say?
>   [Accepted all] [Rejected all] [Partial — they liked some] [Requested changes] [No response yet]

**Analyst:** "partial — they kept argylle and fall guy, said ferrari was too somber"

**Bot:** Got it. Anything else worth noting?

**Analyst:** "they want me to find one more comedy comp"

**Bot:** *(calls `update_amazon_feedback(...)` with response=partial, accepted=[Argylle, Fall Guy], rejected=[Ferrari], notes=...)*

> Logged. The feedback's in `feedback_log/2026-05/request_b27fdee2-….json`. Want me to start a follow-up session to find that extra comedy comp?

---

## What this example demonstrates

- Every intent: correction (with source-disagreement), add (clean), add (multi-match → disambiguation), add (rule violation → override), remove, replace, reorder, finalize.
- Edit log accumulates faithfully across turns.
- Output formatter re-renders correctly after every edit, including conditional caveat sentence and footnotes.
- State 8 re-entry via `find_by_title`, and the partial-acceptance pattern.
- Token hygiene: every turn returns exactly the regenerated draft + a 1-line summary.
