"""
Disambiguator — when an analyst types a title that matches multiple TMDb entries,
this module returns a ranked list of options with enough context to choose.

Sort order: recency (newest first), not popularity. The point is to surface a
choice, not to make one.

Output context per option: year + media type + director (movie) / creators (tv)
+ distributor + opening weekend if known.

Usage as a module:
    from scripts.disambiguator import disambiguate
    options = disambiguate(tmdb, "the grey")
    # options is a list of dicts; if len > 1, the orchestrator MUST ask the analyst

Usage from the CLI:
    python -m scripts.disambiguator "the grey"
    python -m scripts.disambiguator "the grey" --media-type movie
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.tmdb_client import (
    TMDbClient,
    TMDbNotFound,
    director_of,
    creators_of_tv,
)
from scripts.box_office_scraper import BoxOfficeMojoScraper, BOMScrapeError

DEFAULT_MAX_OPTIONS = 8


def disambiguate(
    tmdb: TMDbClient,
    query: str,
    *,
    media_type: Optional[str] = None,
    max_options: int = DEFAULT_MAX_OPTIONS,
    enrich_box_office: bool = True,
) -> list[dict]:
    """Look up `query` on TMDb and return ranked option dicts.

    media_type: 'movie' | 'tv' | None (None -> /search/multi).
    enrich_box_office: if True, opening-weekend is fetched for theatrical hits.

    Each option dict has shape:
        {
            "tmdb_id": int,
            "media_type": "movie" | "tv",
            "title": str,
            "year": int | None,
            "director": str | None,
            "distributor": str | None,
            "opening_weekend_m": float | None,
            "overview": str | None,
            "context_line": str,        # human-friendly one-liner
        }
    """
    if media_type == "movie":
        raw = tmdb.search_movie(query)
        results = [{**r, "media_type": "movie"} for r in raw]
    elif media_type == "tv":
        raw = tmdb.search_tv(query)
        results = [{**r, "media_type": "tv"} for r in raw]
    else:
        raw = tmdb.search_multi(query)
        # /search/multi includes 'person' — drop those, we want titles
        results = [r for r in raw if r.get("media_type") in ("movie", "tv")]

    if not results:
        return []

    def _date_of(r: dict) -> str:
        if r["media_type"] == "movie":
            return r.get("release_date") or ""
        return r.get("first_air_date") or ""

    # sort by recency (newest first); empty dates go to the bottom
    results.sort(key=lambda r: _date_of(r) or "0000-00-00", reverse=True)
    results = results[:max_options]

    bom = BoxOfficeMojoScraper() if enrich_box_office else None
    options: list[dict] = []
    try:
        for r in results:
            opt = _enrich(tmdb, bom, r)
            options.append(opt)
    finally:
        if bom is not None:
            bom.close()

    return options


def _enrich(tmdb: TMDbClient, bom: Optional[BoxOfficeMojoScraper], r: dict) -> dict:
    mt = r["media_type"]
    tmdb_id = r["id"]
    title = r.get("title") or r.get("name") or ""
    date_str = r.get("release_date") or r.get("first_air_date") or ""
    year = int(date_str[:4]) if date_str[:4].isdigit() else None

    director: Optional[str] = None
    distributor: Optional[str] = None
    ow_m: Optional[float] = None

    try:
        if mt == "movie":
            details = tmdb.get_movie(tmdb_id)
            credits = tmdb.get_movie_credits(tmdb_id)
            d = director_of(credits)
            director = (d or {}).get("name")
            pcs = details.get("production_companies", []) or []
            distributor = pcs[0]["name"] if pcs else None
            if bom is not None:
                ext = _safe(lambda: tmdb.get_external_ids("movie", tmdb_id))
                imdb = (ext or {}).get("imdb_id")
                if imdb:
                    try:
                        ow_m = bom.opening_weekend(imdb)
                    except BOMScrapeError:
                        ow_m = None
        else:
            details = tmdb.get_tv(tmdb_id)
            creators = creators_of_tv(details)
            director = ", ".join(c.get("name", "") for c in creators[:2]) or None
            networks = details.get("networks", []) or []
            distributor = networks[0]["name"] if networks else None
    except TMDbNotFound:
        pass

    context_line = _format_context(mt, title, year, director, distributor, ow_m)
    return {
        "tmdb_id": tmdb_id,
        "media_type": mt,
        "title": title,
        "year": year,
        "director": director,
        "distributor": distributor,
        "opening_weekend_m": ow_m,
        "overview": (r.get("overview") or "").strip() or None,
        "context_line": context_line,
    }


def _format_context(
    media_type: str,
    title: str,
    year: Optional[int],
    director: Optional[str],
    distributor: Optional[str],
    ow_m: Optional[float],
) -> str:
    """Build a 'Title (2024, theatrical, dir. X) — $YY.YM OW' style line."""
    yr = str(year) if year else "?"
    mt_label = "theatrical" if media_type == "movie" else "tv"
    parts = [f"{title} ({yr}, {mt_label}"]
    if director:
        parts.append(f", dir. {director}")
    if distributor:
        parts.append(f", {distributor}")
    parts.append(")")
    line = "".join(parts)
    if ow_m is not None:
        line += f" — ~${ow_m:.1f}M OW"
    elif media_type == "movie":
        line += " — OW unverified"
    return line


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:
    p = argparse.ArgumentParser(prog="disambiguator")
    p.add_argument("query")
    p.add_argument("--media-type", choices=("movie", "tv"))
    p.add_argument("--max", type=int, default=DEFAULT_MAX_OPTIONS)
    p.add_argument("--no-bo", action="store_true",
                   help="Skip box-office enrichment (faster, no scrape)")
    args = p.parse_args()

    tmdb = TMDbClient()
    try:
        opts = disambiguate(tmdb, args.query, media_type=args.media_type,
                            max_options=args.max, enrich_box_office=not args.no_bo)
    finally:
        tmdb.close()

    out = {"query": args.query, "count": len(opts), "options": opts}
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if opts else 1


if __name__ == "__main__":
    sys.exit(_cli())
