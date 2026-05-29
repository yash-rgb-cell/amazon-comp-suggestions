---
name: refinement_loop
description: The multi-turn edit loop. Classifies analyst instructions into 6 intents (correction, add, remove, replace, reorder, finalize) and runs the per-intent handler. Maintains the current list across turns. Owns State 5 (the most important state) and also routes State 6 (failure).
---

# Skill: refinement_loop

## Purpose

State 5 is where the analyst shapes the draft into the final message. Most sessions go through 1-4 edit turns. The loop is the difference between a useful tool and a chatbot.

## When to invoke

After the initial draft is rendered (transition State 4 → State 5). Stays in State 5 until the analyst signals finalize.

## The six intents

For each analyst message in the loop, classify into exactly one of these:

| Intent | Trigger phrases | Action |
|---|---|---|
| `correction` | "update [title] to $X", "the OW for [title] is actually X", "fix [title]'s year" | Re-scrape BOM (or re-fetch TMDb). If analyst's value matches source → update silently. If it doesn't → surface the discrepancy and ask. |
| `add` | "add [title]", "include [title]", "throw in [title]" | Disambiguate. Then run the rule engine on just that title. If passes → add. If fails → surface the violation, offer override paths. |
| `remove` | "remove [title]", "drop [title]", "kill [title]" | Drop it. **Do NOT auto-replace.** Tell the analyst the list is now N titles (and warn if N < 4). |
| `replace` | "swap [A] for [B]", "replace [A] with [B]" | Remove A, then add B (using the disambiguation + rules flow). |
| `reorder` | "put [title] first", "[A] should be at the top", "move [B] to the bottom" | Re-sort. Regenerate the draft. |
| `finalize` | "looks good", "done", "send it", "ship it", "this is good", "perfect" | Transition to State 7 (Finalize + Log). |

Intent classification is **Claude's job**. Use the language signals above. When ambiguous, ask: "Did you mean to update Fall Guy's box office number, or replace it?"

## Per-intent details

### Correction

```
analyst: "update fall guy to $27.7"
```

1. Find "Fall Guy" in the current list. If not present → tell the analyst it's not in the list.
2. Re-scrape BOM via `bom.opening_weekend(imdb_id)`.
3. Three outcomes:
   - Source value matches `$27.7M` → update silently, re-render, say "Updated Fall Guy to $27.7M ✓"
   - Source value differs ("source says $27.71M, you said $27.7M") → surface and ask which to use
   - Scrape fails → ask the analyst whether to use their value as authoritative

### Add

```
analyst: "add the grey"
```

1. Call `disambiguator.disambiguate(tmdb, "the grey")`. If multiple matches → hand off to `skills/disambiguation/README.md`. **Do not guess.**
2. Run that single candidate through `rule_engine.apply([cand], intake)`.
3. If it passes all rules → add to the list, re-render.
4. If it fails a hard rule → surface the violation and offer two paths:
   - (a) Skip this title — return to list as-is
   - (b) Add it anyway with a visible flag — needs a flag reason ("pre-release reference", "outside time window", etc.)
5. If accepting puts the list >7 → tell the analyst, ask which to drop.

### Remove

```
analyst: "remove the gentlemen"
```

1. Find by title (fuzzy match — drop punctuation, case-insensitive). If multiple matches → list them and ask which.
2. Drop, re-render, say "Removed The Gentlemen — list is now 4 titles."
3. If list drops below 4 → warn: "List is below the minimum (4). Want to add a replacement, or relax a rule and rebuild?"

### Replace

```
analyst: "swap argylle for ferrari"
```

Run remove A, then add B. If add fails, leave A in the list and tell the analyst.

### Reorder

```
analyst: "put bullet train first"
```

Move the named title to position 1; everything else shifts down. Re-render.

For finer reorders ("move The Fall Guy to position 3"), respect the index. Always re-render.

### Finalize

Transition to State 7.

## State variable

Across the loop, maintain a Python dict in memory:

```python
state = {
    "intake": {...},
    "current_list": [...],     # the list as it stands; mutated by each edit
    "edits": [...],            # event log: turn, intent, details
    "turn": 0,
    "started_at": "...",
}
```

Pass this dict through every handler. Append to `edits` on every mutation.

## Token hygiene during the loop

After every edit, output:
1. The regenerated full draft message (via `output_formatter.render_message`)
2. One line summarizing what changed ("Removed The Gentlemen.")

Nothing else. No candidate-pool dumps. No rule explanations unless asked.

## State 6 — failure mode

If at any point:
- Initial candidate generation yields 0 across all 3 pools
- Rule filtering leaves <4 candidates
- A correction reveals the source data is broken (TMDb 5xx persisting, BOM completely unreachable)

Transition to State 6. Output an honest report:

```
Couldn't build a list this time:
  • P1 pool: 0 candidates (director has no other genre-matching films in the last 5 years)
  • P2 pool: 8 candidates (top-3 cast)
  • P3 pool: 124 candidates (genre /discover)
  • After rule filtering: 2 candidates surviving
    - 47 dropped: outside OW range $7-40M
    - 18 dropped: time window >5y not P1
    - 12 dropped: streaming-only (input is theatrical)
    - …
  
Some options:
  (a) Extend the time window from 3y to 7y for soft tag, 10y hard ceiling
  (b) Widen the OW range from $7-40M to $5-60M
  (c) Cancel and reformulate the request
```

`AskUserQuestion` with the relaxation options. On selection, mutate `intake` and re-run the appropriate stage (don't redo what doesn't need to change).

## Hard rules

- **Never auto-pick on disambiguation.** Always ask.
- **Never silently break a hard rule.** Always offer the override path.
- **Never auto-replace on remove.** The analyst asked to remove; let them decide whether to backfill.
- **Final list size after every turn must stay between 1 and 7.** Below 4 → warn but allow temporarily; above 7 → block and require a drop choice.
