---
name: feedback_log
description: JSON log writer (State 7) and updater (State 8). One file per request, monthly folders. Every comp session must log to disk so we can build a feedback dataset and tighten the rules over time.
---

# Skill: feedback_log

## Purpose

We have no feedback data today. This skill is how we build the dataset. Every session writes a structured JSON record. Later, when Amazon responds, the analyst can re-enter at State 8 to update the same record with the response.

## When to invoke

- **State 7 (Finalize):** after the analyst signals "looks good / done / send it" — write the full session log.
- **State 8 (Post-delivery feedback):** when the analyst re-enters with "log feedback for [title]" — update the existing record.

## Public API

```python
from scripts.feedback_logger import empty_payload, append_event, write_request_log, \
    read_request_log, update_amazon_feedback, find_by_title

# during the session, mutate this in-memory dict
payload = empty_payload()
payload["analyst"] = "lfiqa@listenfirstmedia.com"
payload["inputs"] = intake_dict
payload["initial_draft"] = [c.to_dict() for c in initial_pick]
# ... edit turns
append_event(payload, "edit_turn", {"turn": 1, "intent": "remove", "title": "The Gentlemen"})
payload["edits"].append({"turn": 1, "intent": "remove", "details": {"title": "The Gentlemen"}})
payload["final_list"] = [c for c in final_list]
payload["total_turns"] = state["turn"]
payload["duration_seconds"] = int(time.time() - state["started_at"])

# State 7
path = write_request_log(payload)
print(f"Logged to {path}")

# State 8 — later
update_amazon_feedback(
    request_id="b27f...",
    response="partial",
    notes="They liked everything except The Fall Guy, asked for one comedy swap",
    accepted_titles=["Argylle", "The Gentlemen", "Bullet Train"],
    rejected_titles=["The Fall Guy"],
)
```

## File layout

```
feedback_log/
└── 2026-05/
    ├── request_b27fdee2-…json
    ├── request_e913afd1-…json
    └── …
```

One file per request keeps the diffs clean for any future audit / git-tracking.

## Schema (current: v1)

```json
{
  "schema_version": 1,
  "request_id": "uuid",
  "timestamp": "ISO 8601 UTC",
  "analyst": "lfiqa@listenfirstmedia.com" or null,
  "inputs": {
    "title": "...",
    "based_on_ip": true,
    "ip_type": "novel",
    "release_type": "theatrical",
    "streaming_subtype": null,
    "season_number": null,
    "franchise": false,
    "installment": null,
    "box_office_range_m": {"min": 7.0, "max": 40.0}
  },
  "initial_draft": [
    {"title": "...", "year": 2024, "distributor": "...", "opening_weekend_m": 27.7, "priority_tier": "P2", "flags": []}
  ],
  "edits": [
    {"turn": 1, "intent": "remove", "details": {"title": "The Gentlemen"}}
  ],
  "final_list": [...],
  "total_turns": 3,
  "duration_seconds": 412,
  "amazon_feedback": null,
  "events": [
    {"at": "...", "name": "intake_complete", "detail": {}},
    {"at": "...", "name": "draft_rendered", "detail": {"count": 5}},
    {"at": "...", "name": "edit_turn", "detail": {"turn": 1, "intent": "remove"}},
    {"at": "...", "name": "finalize", "detail": {}}
  ]
}
```

## Schema changes

If we change shape, bump `SCHEMA_VERSION` in `feedback_logger.py` and add a migration. Old logs stay valid at their original version. Don't retro-edit them.

## Failure handling

- **Disk full / permission denied** in State 7 → surface to the analyst with the error message. Ask whether to proceed with delivery anyway (yes/no). If yes, mark the orchestrator state to retry the log later (e.g. write to /tmp and surface the path).
- **No matching log found** in State 8 (`find_by_title` returns empty) → tell the analyst, offer to start a new feedback-only record.

## CLI

```bash
# write a log (after the session)
python -m scripts.feedback_logger init --in /tmp/session_payload.json

# look up by title
python -m scripts.feedback_logger find-by-title "How to Rob a Bank"

# update with Amazon's response
python -m scripts.feedback_logger update \
  --request-id b27fdee2-... \
  --response partial \
  --notes "Liked everything except The Fall Guy" \
  --accepted "Argylle" "The Gentlemen" "Bullet Train"

# list all sessions in a month
python -m scripts.feedback_logger list --month 2026-05
```

## Hard rules

- **Write the log even on a partial session** (analyst aborts mid-flow). Set a `status` event in `events[]` to "aborted" — we want to track failure modes too.
- **Never paste log contents to chat.** The path is what goes in the State 7 summary. Contents stay on disk.
- **Never overwrite an existing log on init.** `write_request_log` generates a fresh request_id by default — collisions are astronomically unlikely.
