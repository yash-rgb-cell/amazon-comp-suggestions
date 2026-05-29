---
name: intake
description: The 7-question conversational tree that opens every Amazon comp request. Activate at State 1. Never skip — the pipeline has no sensible defaults for these inputs.
---

# Skill: intake

**This is an entry-point conversational skill.** It contains no Python code of its own. It tells Claude which questions to ask, in what order, with what validation, and with what branching — using the `AskUserQuestion` tool for every step.

## When to activate

The user says anything matching:
- "comps for [title]" / "draft a comp message" / "Amazon wants comps"
- "build a comp list" / "what should I send Amazon for X"

Activate **immediately** — do not start TMDb work until intake is complete and the summary confirmation has been accepted.

## The 7 fields, in order

Use `AskUserQuestion` for each step. Prefer multiple-choice buttons over free-text wherever the answer is bounded. Validate every input. Re-ask on failure with the reason.

### Q1. Title name — free text (required)

Use a free-text follow-up: "What title is Amazon asking for comps on?" If the analyst answers empty or whitespace-only, re-ask: "Need a title to work from — what's the launch?"

After the analyst gives a title, immediately call `scripts/disambiguator.py` (or the `disambiguate(...)` Python helper) to look it up. If multiple TMDb matches come back, hand off to `skills/disambiguation/README.md` before continuing intake.

### Q2. Based on pre-existing IP? — Yes / No buttons

```
AskUserQuestion:
  question: "Is [TITLE] based on pre-existing IP (novel, comic, video game, true story, etc.)?"
  options: ["Yes", "No"]
```

### Q2a. (Only if Q2 = Yes) IP type — 5 options

```
AskUserQuestion:
  question: "What kind of IP?"
  options: ["Novel/book", "Comic/graphic novel", "Video game", "True story / real events", "Other"]
```

Map to intake.ip_type: `novel` / `comic` / `video game` / `true story` / `other` (lowercase).

### Q3. Release type — Theatrical / Streaming buttons

```
AskUserQuestion:
  question: "Theatrical release or streaming?"
  options: ["Theatrical", "Streaming"]
```

### Q3a. (Only if Q3 = Theatrical) Franchise? — Yes / No

```
AskUserQuestion:
  question: "Is this part of a franchise (sequel, prequel, spinoff)?"
  options: ["Yes — franchise/sequel", "No — standalone"]
```

### Q3b. (Only if Q3a = Yes) Installment number — number input

Free-text follow-up: "Which installment? (e.g. 2 for a sequel, 3 for a threequel)"
- Validate: positive integer, ≥ 1.
- If 1, ask: "Just so I check — installment 1 usually means an original. Did you mean it's the first in a planned franchise?" If yes, set franchise=true, installment=1.

### Q3c. (Only if Q3 = Theatrical) Box office range — two number inputs

Free-text follow-up: "What US opening-weekend range are we targeting, in $M? (give a min and a max, e.g. '7-40')"
- Parse `min` and `max` floats.
- Validate: both positive, **min < max**. Re-ask if min >= max with the message: "min must be less than max — got $X and $Y. Try again?"
- Save as `box_office_range_m: {min: float, max: float}`.

### Q4. (Only if Q3 = Streaming) Film or series?

```
AskUserQuestion:
  question: "Streaming film or streaming series?"
  options: ["Film", "Series"]
```

### Q4a. (Only if Q4 = Series) Season number — number input

Free-text follow-up: "Which season are we comping? (e.g. 2 if this is the Season 2 launch)"
- Validate positive integer ≥ 1.

## Confirmation summary

After all required fields are collected, **always** show a summary and wait for explicit confirmation:

```
Got it — here's what I'm working with:
  • Title: How to Rob a Bank
  • IP-based? No
  • Release type: Theatrical
  • Franchise? No
  • Opening weekend target: $7M – $40M

Ready to generate candidates? (Yes / Edit something)
```

`AskUserQuestion` options: `["Yes — generate", "Let me fix something"]`. On "fix", re-ask the relevant question.

When the analyst confirms, transition to **State 2 (Candidate Generation)**.

## Outputs

The intake skill produces an `intake` dict matching the feedback-log schema:

```json
{
  "title": "How to Rob a Bank",
  "tmdb_id": 1071215,
  "media_type": "movie",
  "based_on_ip": false,
  "ip_type": null,
  "release_type": "theatrical",
  "streaming_subtype": null,
  "season_number": null,
  "franchise": false,
  "installment": null,
  "box_office_range_m": {"min": 7.0, "max": 40.0}
}
```

This dict is passed unchanged into `candidate_generator.build_pools(...)`, `rule_engine.apply(...)`, and the feedback logger.

## Hard rules

- **Never invent values.** If the analyst declines to answer a required question, stop and explain that the rule engine needs that input. Do not default.
- **Always disambiguate the title BEFORE Q2.** If the title is ambiguous and we collect 6 more answers against the wrong movie, the analyst pays for the round trip.
- **Always show the summary before transitioning.** Even if every answer came in one message.
