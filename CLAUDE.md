# Amazon Comp Suggestions — Assistant Instructions

This document is loaded automatically whenever Claude is working in this skill's folder. **Read it before responding to any user message in this project.**

---

## Rule #1 — Always run the state machine. Never improvise.

The skill is an 8-state pipeline (see `SKILL.md` for the table). When the user activates the skill, the entry point is **State 1 (Intake)** — owned by `skills/intake/README.md`. Do not generate candidates, do not draft messages, do not call any TMDb endpoint until intake is complete and the analyst has confirmed the summary.

The only valid skip is when the user re-enters at **State 8** ("log feedback for [title]") — that bypasses 1-7 entirely and goes straight to `skills/feedback_log/README.md`.

---

## Rule #2 — Never guess. Always ask.

This is the most important behavioral rule and it appears in three places:

1. **Disambiguation in intake:** if the analyst's title matches more than one TMDb entry, use `skills/disambiguation/README.md` to present the options with full context (year + type + director + distributor + OW if known). Sort by **recency**, not popularity. Never auto-pick the highest-vote result.
2. **Disambiguation in refinement:** same rule applies when the analyst says "add the grey" — multiple matches → present, ask, wait.
3. **Rule violations during refinement:** when the analyst tries to add a title that fails a hard rule (wrong type, out-of-range OW, unreleased, etc.), surface the violation and offer concrete options (skip / add anyway with a flag / abandon). Never silently break a rule.

If you ever find yourself thinking "I'll just pick the most likely one" — stop and ask.

---

## Rule #3 — Scripts do the deterministic work. Claude does the conversation + judgment.

| Task | Where |
|---|---|
| TMDb search, person credits, discover, providers, keywords | `scripts/tmdb_client.py` |
| Box Office Mojo opening-weekend scrape | `scripts/box_office_scraper.py` |
| Build P1/P2/P3 candidate pools | `scripts/candidate_generator.py` |
| Apply hard rules + soft tags | `scripts/rule_engine.py` |
| TMDb search + multi-match resolution | `scripts/disambiguator.py` |
| Render the final message template | `scripts/output_formatter.py` |
| Write/update the JSON feedback log | `scripts/feedback_logger.py` |
| Intake conversation, intent classification, LLM judgment (pick best 4-7, judge tonal fit, decide if a flag is worth the cost), refinement-loop orchestration | **Claude (you)** |

If functionality is missing, **extend a script** rather than dumping logic into the conversation flow. Repeatability matters — the next analyst session must produce the same draft for the same inputs.

---

## Rule #4 — Token hygiene

The analyst-facing surface should stay tight:

- Do not dump TMDb response JSON, candidate pools, or feedback-log contents to chat. Write them to `outputs/candidates_<request_id>.json` and reference counts ("47 candidates after dedupe, 12 after rules").
- In State 5 (refinement), every response should be: regenerated draft message + one line saying what changed. Nothing else.
- Never paste the full feedback log JSON to chat. The log file path goes in the State 7 summary; the contents stay on disk.

---

## Rule #5 — Validate every analyst input

Spec lives in `skills/intake/README.md`. Reject silently-broken inputs at the source:

- Empty title → re-ask.
- Non-positive numbers (box office, season, installment) → re-ask with the reason.
- Box office range with `min >= max` → re-ask, surface the rule.
- Out-of-range answers to button questions (e.g. text where a Yes/No is expected) → re-ask.

After all 7 fields are collected, **always show a confirmation summary** and wait for the analyst to confirm before transitioning to State 2.

---

## Rule #6 — Every interaction must be logged

This is the only way we build the feedback dataset. `scripts/feedback_logger.py init` MUST be called in State 7 with the full draft, edit log, and final list. Path:

```
feedback_log/YYYY-MM/request_<uuid>.json
```

If `feedback_logger.py` fails (disk full, permission denied, etc.), surface the error to the analyst and ask whether to proceed with delivery anyway. Do not silently drop the log.

---

## Rule #7 — Failure is honest, not graceful

If candidate generation produces fewer than 4 surviving candidates, you are in **State 6**. Do not pad with random titles. Do not relax a rule unilaterally. Tell the analyst:

- What pools were tried (P1/P2/P3 counts)
- What rules dropped how many candidates
- Concrete relaxation options ("Extend time window from 3y to 7y? Widen OW range from $7-40M to $5-60M? Drop IP preference?")

The analyst picks the relaxation. Then re-run State 2 or State 3 with the new parameters.

---

## Rule #8 — Hard rule of last resort

If the analyst overrides a hard rule (e.g. "add it anyway as a pre-release reference"), the resulting list still must contain **4-7 titles total** and the override must be visible in the message footnote. The feedback log records the override on that turn so we can audit later.

---

## Rule #9 — Run the health check first. Fall back to WebSearch if TMDb is down.

**At the start of every session**, before transitioning into intake's first question, run:

```bash
python -m scripts.health_check --quiet
```

- Exit code **0** → TMDb is reachable; run the normal pipeline.
- Exit code **1** → TMDb is unreachable but WebSearch is available → activate `skills/websearch_fallback/README.md`. Tell the analyst at the top of the session: *"Heads up — TMDb isn't reachable right now, so I'm using web search as a fallback. Results may be less comprehensive than usual."* Set `payload["mode"] = "websearch_fallback"` in the feedback log.
- Exit code **2** → no data source available → State 6, surface the error and stop.

The fallback uses the same intake questions, the same rules, the same output template, and the same feedback log schema — only the data-source layer changes. Every "unverified" tag from the fallback shows up in the output footnote so the analyst can spot-check.

Do not silently downgrade in the middle of a session. If TMDb was up at session start and dies during the run, surface the failure and ask the analyst whether to switch modes (rather than mixing data sources in one log entry).

---

## Quick-reference cheat sheet

| Analyst says | Do |
|---|---|
| "comps for [title]" | Activate Intake (State 1) — start the 7-question flow |
| "looks good" / "done" / "send it" / "ship it" | Move to State 7 — render clean output, write log |
| "add the grey" with multi-match | Activate disambiguation — never auto-pick |
| "add [unreleased title]" | Surface the violation — offer skip / add-with-flag |
| "log feedback for [title]" | Jump to State 8 — read the existing log entry, update `amazon_feedback` |
| "just send something quick" | Refuse politely — accuracy depends on intake; require at minimum title + release type + (range OR season) |
| "ignore the rules just this once" | The override path is per-rule, per-title, with a visible flag. There is no global "ignore" |
