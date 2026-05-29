# Output Template

The exact Slack-style message format the analyst copies and sends to Amazon.

## Theatrical (no flags)

```
Sure thing — ideas below! Put together an initial list based on what's publicly available about the title as of now, but let us know if you've seen any of the material and it plays differently than it currently sounds.

Ideas ranked by opening weekend:
- The Fall Guy (2024, Universal) — ~$27.7M OW
- Argylle (2024, Universal/Apple) — ~$17.3M OW
- The Gentlemen (2020, STX) — ~$11.1M OW
- Bullet Train (2022, Sony) — ~$30.1M OW
```

## Theatrical (with one flag — caveat sentence required)

```
Sure thing — ideas below! Put together an initial list based on what's publicly available about the title as of now, but let us know if you've seen any of the material and it plays differently than it currently sounds.

One note — including The Gray Man here as a streaming-adjacent reference since it shares director DNA with the title; OW comparison is approximate.

Ideas ranked by opening weekend:
- The Fall Guy (2024, Universal) — ~$27.7M OW
- Argylle (2024, Universal/Apple) — ~$17.3M OW
- The Gray Man (2022, Netflix) — streaming-only, no OW *
- The Gentlemen (2020, STX) — ~$11.1M OW
- Bullet Train (2022, Sony) — ~$30.1M OW

* flagged: linear/streaming outlier, included for tonal fit
```

## Streaming film

```
Sure thing — ideas below! Put together an initial list based on what's publicly available about the title as of now, but let us know if you've seen any of the material and it plays differently than it currently sounds.

Ideas ranked by recency:
- Rebel Ridge (2024, Netflix)
- The Gray Man (2022, Netflix)
- Red Notice (2021, Netflix)
- The Tomorrow War (2021, Prime Video)
```

## Streaming series

```
Sure thing — ideas below! Put together an initial list based on what's publicly available about the title as of now, but let us know if you've seen any of the material and it plays differently than it currently sounds.

Ideas ranked by recency (Season 2 comps):
- The Bear S2 (2023, Hulu)
- Shrinking S2 (2024, Apple TV+)
- Severance S2 (2025, Apple TV+)
- Slow Horses S2 (2022, Apple TV+)
```

## Formatting rules

- **Opening line is boilerplate.** Always: `Sure thing — ideas below! Put together an initial list based on what's publicly available about the title as of now, but let us know if you've seen any of the material and it plays differently than it currently sounds.`
- **Hedge sentence is boilerplate** (the "Put together an initial list..." clause) — already in the opening line above.
- **Caveat sentence** appears only if there's a flagged title in the final list. One sentence. Names the flagged title(s) and the reason.
- **"Ideas ranked by..."** changes:
  - Theatrical → `Ideas ranked by opening weekend:`
  - Streaming film → `Ideas ranked by recency:`
  - Streaming series → `Ideas ranked by recency (Season N comps):` where N is the analyst's season number
- **Per-title line format**:
  - Theatrical: `- Title (Year, Distributor) — ~$XX.XM OW`
  - Theatrical with BO unverified: `- Title (Year, Distributor) — OW unverified`
  - Streaming film: `- Title (Year, Platform)`
  - Streaming series: `- Title SN (Year, Platform)`
  - Flagged outlier: append ` *` to the line and add a footnote at the bottom.
- **Footnote format**: blank line, then `* flagged: <one-line reason>` for each flagged title. If multiple, repeat with `* ... ** ... *** ...` markers.
- **Dollar amounts**: rounded to one decimal place, formatted as `~$XX.XM`. Example: `27.7` not `27.71` or `28`.
- **Year**: 4-digit release year (or first_air_date year for series).
- **Distributor for theatrical**: The studio that handled US theatrical (e.g. `Universal`, `Warner Bros.`, `Sony`, `STX`, `Apple Original Films`). Sourced from TMDb's `production_companies` (first entry, preferring the major studio when multiple).
- **Platform for streaming**: One of `Prime Video`, `Netflix`, `HBO Max`, `Hulu`, `Disney+`, `Peacock`, `Paramount+`, or `Apple TV+` (Apple TV+ is allowed; it just wasn't on the original "approved" list — see `approved_platforms.md`).

## What NOT to include

- No emoji.
- No `**bold**` or `*italic*` — keep it plain text since Slack/email rendering varies.
- No links.
- No greeting ("Hi team,") or sign-off ("Thanks,") — analyst adds those.
- No box office numbers for streaming titles. The relevant signal there is platform + recency.
- No "we think you'll like" or "perfect for" editorial framing. Just the list.
