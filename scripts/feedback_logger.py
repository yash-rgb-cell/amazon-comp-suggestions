"""
Feedback logger — one JSON file per request, monthly folders.

Two modes:

  init    — called at State 7 (Finalize). Writes a new log file with full
            intake, draft, edits, final_list, timings, etc.
  update  — called at State 8 (Post-delivery feedback). Loads an existing entry
            and merges in the analyst's notes on Amazon's response.

Schema is versioned via the `schema_version` field. Bump and migrate carefully
if you change the shape.

Path: feedback_log/YYYY-MM/request_<uuid>.json

Usage as a module:
    from scripts.feedback_logger import write_request_log, update_amazon_feedback
    path = write_request_log(payload)
    update_amazon_feedback(request_id, response="accepted", notes="...")

Usage from the CLI:
    python -m scripts.feedback_logger init --in payload.json
    python -m scripts.feedback_logger update --request-id <uuid> --response accepted
    python -m scripts.feedback_logger find-by-title "How to Rob a Bank"
    python -m scripts.feedback_logger list --month 2026-05
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 1

# Default base path: <repo>/feedback_log/  (sibling of scripts/)
DEFAULT_BASE = Path(__file__).resolve().parent.parent / "feedback_log"


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _month_dir(base: Path, when: dt.datetime) -> Path:
    return base / when.strftime("%Y-%m")


def empty_payload() -> dict:
    """Return a blank payload with the canonical schema. Sub-skills mutate this
    in-memory across the session, then hand to `write_request_log`."""
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": str(uuid.uuid4()),
        "timestamp": _now_iso(),
        "analyst": None,
        "inputs": {
            "title": None,
            "based_on_ip": None,
            "ip_type": None,
            "release_type": None,
            "streaming_subtype": None,
            "season_number": None,
            "franchise": None,
            "installment": None,
            "box_office_range_m": None,
        },
        "initial_draft": [],
        "edits": [],
        "final_list": [],
        "total_turns": 0,
        "duration_seconds": 0,
        "amazon_feedback": None,
        "events": [],   # free-form timeline
    }


def append_event(payload: dict, name: str, detail: Optional[dict] = None) -> None:
    payload.setdefault("events", []).append({
        "at": _now_iso(),
        "name": name,
        "detail": detail or {},
    })


# ---------------------------------------------------------------------------
# Write / read
# ---------------------------------------------------------------------------

def write_request_log(payload: dict, base: Path = DEFAULT_BASE) -> Path:
    """Persist a payload. Returns the file path written.

    The caller is responsible for setting `request_id` if reusing one — otherwise
    `empty_payload()` would have generated a fresh UUID.
    """
    if "request_id" not in payload:
        payload["request_id"] = str(uuid.uuid4())
    if "schema_version" not in payload:
        payload["schema_version"] = SCHEMA_VERSION
    when = dt.datetime.now(dt.timezone.utc)
    folder = _month_dir(base, when)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"request_{payload['request_id']}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def read_request_log(request_id: str, base: Path = DEFAULT_BASE) -> tuple[dict, Path]:
    """Find an existing log by request_id (searches all months)."""
    for path in sorted(base.glob(f"*/request_{request_id}.json")):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), path
    raise FileNotFoundError(f"no log found for request_id={request_id!r}")


def update_amazon_feedback(
    request_id: str,
    response: str,
    notes: Optional[str] = None,
    accepted_titles: Optional[list[str]] = None,
    rejected_titles: Optional[list[str]] = None,
    base: Path = DEFAULT_BASE,
) -> Path:
    """Append Amazon's response to an existing log entry (State 8)."""
    if response not in ("accepted_all", "rejected_all", "partial", "requested_changes", "no_response"):
        raise ValueError(f"unknown response value {response!r}")
    payload, path = read_request_log(request_id, base=base)
    fb = {
        "received_at": _now_iso(),
        "response": response,
        "notes": notes,
        "accepted_titles": accepted_titles or [],
        "rejected_titles": rejected_titles or [],
    }
    payload["amazon_feedback"] = fb
    append_event(payload, "amazon_feedback_logged", {"response": response})
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path


def find_by_title(title_query: str, base: Path = DEFAULT_BASE, limit: int = 10) -> list[dict]:
    """Return matching log files, newest first. Case-insensitive substring match on inputs.title."""
    q = (title_query or "").strip().lower()
    if not q:
        return []
    matches: list[tuple[str, Path]] = []
    for path in sorted(base.glob("*/request_*.json"), reverse=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        title = (data.get("inputs", {}) or {}).get("title") or ""
        if q in title.lower():
            matches.append((data["request_id"], path))
        if len(matches) >= limit:
            break
    return [
        {"request_id": rid, "path": str(p),
         "timestamp": json.load(open(p, "r", encoding="utf-8")).get("timestamp")}
        for rid, p in matches
    ]


def list_month(month: str, base: Path = DEFAULT_BASE) -> list[dict]:
    """`month` formatted as YYYY-MM."""
    folder = base / month
    if not folder.exists():
        return []
    out = []
    for path in sorted(folder.glob("request_*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        out.append({
            "request_id": data.get("request_id"),
            "timestamp": data.get("timestamp"),
            "title": (data.get("inputs", {}) or {}).get("title"),
            "release_type": (data.get("inputs", {}) or {}).get("release_type"),
            "final_count": len(data.get("final_list") or []),
            "amazon_feedback": (data.get("amazon_feedback") or {}).get("response"),
            "path": str(path),
        })
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:
    p = argparse.ArgumentParser(prog="feedback_logger")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init")
    sp.add_argument("--in", dest="in_path", required=True, help="JSON payload to write")

    sp = sub.add_parser("update")
    sp.add_argument("--request-id", required=True)
    sp.add_argument("--response", required=True,
                    choices=("accepted_all", "rejected_all", "partial", "requested_changes", "no_response"))
    sp.add_argument("--notes")
    sp.add_argument("--accepted", nargs="*", default=[])
    sp.add_argument("--rejected", nargs="*", default=[])

    sp = sub.add_parser("find-by-title")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=10)

    sp = sub.add_parser("list")
    sp.add_argument("--month", required=True, help="YYYY-MM")

    sp = sub.add_parser("empty")  # debug helper — dump empty payload

    args = p.parse_args()

    if args.cmd == "init":
        with open(args.in_path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        path = write_request_log(payload)
        print(json.dumps({"written": str(path), "request_id": payload["request_id"]}, indent=2))
    elif args.cmd == "update":
        path = update_amazon_feedback(
            args.request_id, args.response,
            notes=args.notes,
            accepted_titles=args.accepted, rejected_titles=args.rejected,
        )
        print(json.dumps({"updated": str(path)}, indent=2))
    elif args.cmd == "find-by-title":
        print(json.dumps(find_by_title(args.query, limit=args.limit), indent=2))
    elif args.cmd == "list":
        print(json.dumps(list_month(args.month), indent=2))
    elif args.cmd == "empty":
        print(json.dumps(empty_payload(), indent=2))
    else:
        print(f"Unknown command: {args.cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
