---
name: output_formatter
description: Renders the final Slack-style message. Three variants (theatrical, streaming film, streaming series). Boilerplate opening sentence is always included. Caveat sentence and footnotes are inserted only when flagged titles are present.
---

# Skill: output_formatter

## Purpose

Take a final 4-7 candidates and produce the exact text the analyst will paste into Slack/email.

## When to invoke

After the ranker picks the final list (State 4) — and again every turn in State 5 after any edit.

## Public API

```python
from scripts.output_formatter import render_message

text = render_message(final_list, intake)
```

`final_list` items must have these fields (the rule engine + ranker populate them):
- `title` (str)
- `year` (int)
- `distributor` (str)  — studio for theatrical, platform for streaming
- `opening_weekend_m` (float | None) — theatrical only
- `flags` (list[str], optional)
- `comp_season_number` (int) — for streaming-series only

`intake` must have:
- `release_type`: `"theatrical" | "streaming"`
- `streaming_subtype`: `"film" | "series" | null`
- `season_number`: int | null

## Template selection

| release_type | streaming_subtype | Header line | Per-item format |
|---|---|---|---|
| theatrical | (n/a) | `Ideas ranked by opening weekend:` | `- Title (Year, Distributor) — ~$XX.XM OW` |
| streaming | film | `Ideas ranked by recency:` | `- Title (Year, Platform)` |
| streaming | series | `Ideas ranked by recency (Season N comps):` | `- Title SN (Year, Platform)` |

## Flag handling

A title with `flags` gets a footnote marker (`*`, `**`, ...) appended. The footnote line goes below the list, blank line above it.

If the final list contains **any** flagged titles, a single caveat sentence is inserted between the opening boilerplate and the header line. It names the flagged title(s) and the primary reason category.

Examples in `references/output_template.md`.

## Hard rules

- **Always include the opening boilerplate** — it's part of the LF voice on these messages.
- **No emoji, no markdown formatting** — Slack/email rendering varies, plain text is safest.
- **Round dollar amounts to one decimal place.** `27.7` not `27.71` or `28`.
- **No box office in streaming sections.** Even if we have the data, the relevant signal is platform + recency.
- **List length must be 4-7.** `render_message` raises ValueError otherwise (defensive guard).
