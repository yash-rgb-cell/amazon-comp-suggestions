"""
Output formatter — renders the standard Slack-style comp message.

Three variants:
  - theatrical          → "Ideas ranked by opening weekend:"
  - streaming_film      → "Ideas ranked by recency:"
  - streaming_series    → "Ideas ranked by recency (Season N comps):"

Caveat sentence is inserted ONLY when at least one final title carries a flag.
Footnotes ("* flagged: reason") are appended at the bottom, one per flagged title.

Output is plain text — no markdown, no emoji, no links. The analyst pastes it
straight into Slack/email.

Usage as a module:
    from scripts.output_formatter import render_message
    text = render_message(final_list, intake)

Usage from the CLI:
    python -m scripts.output_formatter --in final.json --intake intake.json
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Boilerplate
# ---------------------------------------------------------------------------

OPENING_LINE = (
    "Sure thing — ideas below! Put together an initial list based on what's "
    "publicly available about the title as of now, but let us know if you've "
    "seen any of the material and it plays differently than it currently sounds."
)

FOOTNOTE_MARKERS = ["*", "**", "***", "****", "*****", "******", "*******"]


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def render_message(final_list: list[dict], intake: dict) -> str:
    """Return the full message text for `final_list` (4-7 titles) and the analyst's intake."""
    if not (4 <= len(final_list) <= 7):
        raise ValueError(f"final_list must have 4-7 items, got {len(final_list)}")

    release_type = intake.get("release_type")
    subtype = intake.get("streaming_subtype")

    flagged = [t for t in final_list if t.get("flags")]

    # 1. opening boilerplate
    lines = [OPENING_LINE, ""]

    # 2. optional caveat sentence — keyed off the *most prominent* flag reason
    if flagged:
        lines.append(_caveat_sentence(flagged))
        lines.append("")

    # 3. header line
    lines.append(_header(release_type, subtype, intake.get("season_number")))

    # 4. ranked items
    footnote_lines: list[str] = []
    marker_idx = 0
    for t in final_list:
        body, footnote = _item_line(t, release_type, subtype)
        if footnote:
            mk = FOOTNOTE_MARKERS[min(marker_idx, len(FOOTNOTE_MARKERS) - 1)]
            body = body + f" {mk}"
            footnote_lines.append(f"{mk} flagged: {footnote}")
            marker_idx += 1
        lines.append(f"- {body}")

    # 5. footnotes
    if footnote_lines:
        lines.append("")
        lines.extend(footnote_lines)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Pieces
# ---------------------------------------------------------------------------

def _caveat_sentence(flagged: list[dict]) -> str:
    """Build a one-line caveat naming the flagged title(s) and the reason category."""
    if len(flagged) == 1:
        t = flagged[0]
        reason = _primary_reason(t.get("flags") or [])
        return (
            f"One note — including {_title_for_caveat(t)} here "
            f"despite {reason}; included for tonal/audience fit."
        )
    names = ", ".join(_title_for_caveat(t) for t in flagged[:3])
    return (
        f"One note — {names} are included with caveats (see footnotes); "
        f"chosen for tonal/audience fit."
    )


def _title_for_caveat(t: dict) -> str:
    return t.get("title") or "this title"


def _primary_reason(flags: list[str]) -> str:
    """Pick the most readable flag for the caveat sentence."""
    for flag in flags:
        f = flag.lower()
        if "linear" in f:
            return "linear/network distribution"
        if "exceeds ideal range" in f or "3-5y" in f:
            return "exceeding our preferred 3-year window"
        if "legacy director" in f:
            return "the title being older than 5 years (legacy director-match)"
        if "bo unverified" in f:
            return "an unverified opening weekend"
        if "non-ip" in f:
            return "the IP-status mismatch"
    return flags[0] if flags else "a soft-tag exception"


def _header(release_type: Optional[str], subtype: Optional[str], season_number: Optional[int]) -> str:
    if release_type == "theatrical":
        return "Ideas ranked by opening weekend:"
    if release_type == "streaming" and subtype == "film":
        return "Ideas ranked by recency:"
    if release_type == "streaming" and subtype == "series":
        sn = season_number or "?"
        return f"Ideas ranked by recency (Season {sn} comps):"
    # safety fallback
    return "Ideas:"


def _item_line(t: dict, release_type: Optional[str], subtype: Optional[str]) -> tuple[str, Optional[str]]:
    """Return (body_text, footnote_reason_or_None)."""
    flags = t.get("flags") or []
    footnote_reason: Optional[str] = None
    if flags:
        footnote_reason = _footnote_reason(flags)

    if release_type == "theatrical":
        body = _theatrical_line(t)
    elif release_type == "streaming" and subtype == "film":
        body = _streaming_film_line(t)
    elif release_type == "streaming" and subtype == "series":
        body = _streaming_series_line(t)
    else:
        body = f"{t.get('title','?')} ({t.get('year','?')})"

    return body, footnote_reason


def _theatrical_line(t: dict) -> str:
    title = t.get("title", "?")
    yr = t.get("year", "?")
    dist = t.get("distributor") or "?"
    ow = t.get("opening_weekend_m")
    if ow is None:
        return f"{title} ({yr}, {dist}) — OW unverified"
    return f"{title} ({yr}, {dist}) — ~${ow:.1f}M OW"


def _streaming_film_line(t: dict) -> str:
    title = t.get("title", "?")
    yr = t.get("year", "?")
    plat = t.get("distributor") or "?"
    return f"{title} ({yr}, {plat})"


def _streaming_series_line(t: dict) -> str:
    title = t.get("title", "?")
    yr = t.get("year", "?")
    plat = t.get("distributor") or "?"
    sn = t.get("comp_season_number")
    if sn:
        return f"{title} S{sn} ({yr}, {plat})"
    return f"{title} ({yr}, {plat})"


def _footnote_reason(flags: list[str]) -> str:
    """Short reason text for the * footnote (different from the caveat sentence)."""
    for flag in flags:
        f = flag.lower()
        if "linear" in f:
            return "linear/network distribution, included for tonal fit"
        if "bo unverified" in f:
            return "opening weekend not verifiable from public sources"
        if "exceeds ideal range" in f or "3-5y" in f:
            return "outside the preferred 3-year recency window"
        if "legacy director" in f:
            return "older than 5 years but kept for director-match relevance"
        if "non-ip" in f:
            return "non-IP comp included for tonal fit"
        if "release year unknown" in f:
            return "release year unavailable"
    return flags[0]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:
    p = argparse.ArgumentParser(prog="output_formatter")
    p.add_argument("--in", dest="in_path", required=True,
                   help="JSON file with the final_list (array of candidate dicts)")
    p.add_argument("--intake", required=True)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    with open(args.in_path, "r", encoding="utf-8") as f:
        final = json.load(f)
    with open(args.intake, "r", encoding="utf-8") as f:
        intake = json.load(f)

    if isinstance(final, dict) and "final" in final:
        final = final["final"]

    text = render_message(final, intake)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"wrote {args.out} — {len(text)} chars")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
