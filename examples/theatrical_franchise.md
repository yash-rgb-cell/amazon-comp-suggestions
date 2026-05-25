# Example: theatrical franchise sequel — "Spider-Man 4" (hypothetical)

A walkthrough showing how the franchise-installment rule narrows candidates. Hypothetical request — there's no real *Spider-Man 4* TMDb entry yet — so this example illustrates the flow with synthetic but realistic numbers.

## Intake transcript

**Analyst:** "Need comps for Spider-Man 4 — Amazon's asking"

**Bot:** *(disambiguator returns multiple — there are several Spider-Man entries)*

> Found multiple titles matching "Spider-Man 4":
> 1. Spider-Man: Brand New Day (2026, theatrical, dir. Destin Daniel Cretton) — Marvel/Sony — upcoming
> 2. The Amazing Spider-Man 2 (2014, theatrical, Sony) — ~$92.8M OW
> 3. Spider-Man (2002, theatrical, Sony) — ~$114.8M OW
> 4. Spider-Man: Across the Spider-Verse (2023, theatrical, Sony) — ~$120.7M OW
>
> Which one did you mean?

**Analyst:** "the 2026 one — Brand New Day"

**Bot:** Is *Spider-Man: Brand New Day* based on pre-existing IP?
> [Yes] [No]

**Analyst:** Yes

**Bot:** What kind of IP?
> [Novel/book] [Comic/graphic novel] [Video game] [True story / real events] [Other]

**Analyst:** Comic

**Bot:** Theatrical or streaming?

**Analyst:** Theatrical

**Bot:** Is this part of a franchise?

**Analyst:** Yes

**Bot:** Which installment?

**Analyst:** "4 — it's Tom Holland's 4th solo Spider-Man"

**Bot:** What US opening-weekend range are we targeting, in $M?

**Analyst:** "70-180"

**Bot:** Summary:
> • Title: Spider-Man: Brand New Day (2026)
> • IP-based? Yes — comic
> • Release type: Theatrical
> • Franchise? Yes — installment 4
> • Opening weekend target: $70M – $180M
>
> [Yes — generate] [Let me fix something]

**Analyst:** Yes

## What the rule engine does differently here

- Rule 3 (franchise installment): for any candidate that belongs to a TMDb collection, the engine pulls `/collection/{id}` and computes the candidate's index by release date. Anything that's not installment 4 in its own series gets dropped. Standalones (no collection) are kept — they're potential same-genre comps even if not sequels themselves.
- Rule 13 (IP tag): since `based_on_ip=true` with type=comic, candidates whose TMDb keywords intersect the comic-IP set (9717, 254835, 9714, 282085, 207928, 180547) are preferred. Non-comic candidates get a `non-IP` flag.

## Candidate generation (illustrative)

Director: Destin Daniel Cretton → P1: 2 candidates in Action/Adventure within 5y window (e.g. *Shang-Chi*, *Just Mercy* if it qualifies on genre).

Top-3 cast: Tom Holland, Zendaya, Sadie Sink → P2: ~12 candidates (their other action/blockbusters in window).

P3 /discover: Action genre, 2021-05 to 2026-05 → 80+ candidates.

After dedupe: 87 merged.

## Rule filtering — installment-aware

Sample of rule-3 (installment) outcomes:
- *Doctor Strange in the Multiverse of Madness* (2022) — installment 2 of the Doctor Strange collection → **drop** (wrong installment).
- *Thor: Love and Thunder* (2022) — installment 4 of the Thor collection → **keep** (installment matches).
- *Mission: Impossible — Dead Reckoning Part One* (2023) — installment 7 → **drop**.
- *Mission: Impossible — The Final Reckoning* (2025) — installment 8 → **drop**.
- *Dune: Part Two* (2024) — installment 2 → **drop**.
- *Bullet Train* (2022) — standalone, no collection → **keep**.

After rule 5 (OW $70-180M) the surviving installment-4 sequels and rule-passing standalones land at ~9 candidates.

## Final pick (illustrative)

| # | Title | Year | Distributor | OW | Tier | Flags |
|---|---|---|---|---|---|---|
| 1 | Spider-Man: Across the Spider-Verse | 2023 | Sony | $120.7M | P2 | — |
| 2 | Thor: Love and Thunder | 2022 | Marvel | $144.2M | P2 | — |
| 3 | Doctor Strange in the Multiverse of Madness (S4 of MCU phase) | 2022 | Marvel | $187.4M | P2 | exceeds OW band $180M cap? — actually $187M is over, so DROP |
| ... |

Reworked picks after re-check:

| # | Title | Year | Distributor | OW |
|---|---|---|---|---|
| 1 | Thor: Love and Thunder | 2022 | Marvel | $144.2M |
| 2 | Spider-Man: Across the Spider-Verse | 2023 | Sony | $120.7M |
| 3 | Wonka | 2023 | Warner Bros. | $39M (out of band — would actually drop) |
| 4 | ... |

This example surfaces a real risk: with a franchise installment >= 3 requirement AND a $70-180M band, the surviving pool is often thin. The bot would likely surface this as a **State 6 warning** ("only 3 candidates pass — relax band? extend window?") rather than ship a weak list.

## Rendered draft (post State-6 relaxation)

After the analyst widens the band to $50-200M:

```
Sure thing — ideas below! Put together an initial list based on what's publicly available about the title as of now, but let us know if you've seen any of the material and it plays differently than it currently sounds.

Ideas ranked by opening weekend:
- Doctor Strange in the Multiverse of Madness (2022, Marvel) — ~$187.4M OW
- Thor: Love and Thunder (2022, Marvel) — ~$144.2M OW
- Spider-Man: Across the Spider-Verse (2023, Sony) — ~$120.7M OW
- Deadpool & Wolverine (2024, Marvel) — ~$211.4M OW  ←  would still be over, so dropped
```

The analyst would refine in State 5: "remove Deadpool & Wolverine, add Fast X" → bot disambiguates "Fast X" (cleanly single match) → runs rules → installment 10 of Fast & Furious → wrong installment, surfaces violation → analyst chooses "(b) add with flag — franchise installment mismatch".

## What this example demonstrates

- The franchise/installment rule and how TMDb collections drive it.
- The IP-type tag biasing toward comic-based candidates.
- A realistic State 6 trigger (thin surviving pool) and the relaxation flow.
- A realistic State 5 override (add-with-flag for installment mismatch).
