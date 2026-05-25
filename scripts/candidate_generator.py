"""
Candidate generator — builds the P1 / P2 / P3 pools from TMDb.

P1: input title's director (or creator, for TV) → other films/shows in the
    same primary genre, last 5 years.
P2: input title's top-3 billed cast members → other films/shows in the same
    primary genre, last 5 years.
P3: TMDb /discover with the matching primary genre + date window.

Deduplicates across pools, attaching metadata each downstream stage needs.

Usage as a module:
    from scripts.candidate_generator import CandidateGenerator
    cg = CandidateGenerator(tmdb=tmdb)
    candidates = cg.build_pools(input_meta, intake)

Usage from the CLI:
    python -m scripts.candidate_generator \
        --title "How to Rob a Bank" --type theatrical --tmdb-id 1071215
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

# allow `python -m scripts.candidate_generator` and `python candidate_generator.py`
if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.tmdb_client import (
    TMDbClient,
    TMDbNotFound,
    director_of,
    creators_of_tv,
    top_cast,
)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class Candidate:
    """A single comp candidate. All fields are populated by the generator.

    Downstream stages (rule_engine, ranker, formatter) read these fields directly.
    """
    tmdb_id: int
    media_type: str                       # 'movie' | 'tv'
    title: str
    year: Optional[int]
    primary_genre_id: Optional[int]
    genre_ids: list[int] = field(default_factory=list)
    distributor: Optional[str] = None     # populated lazily during rule engine
    pools: set = field(default_factory=set)  # subset of {'P1', 'P2', 'P3'}
    source_person_ids: list[int] = field(default_factory=list)  # which P1/P2 seeds matched
    overview: Optional[str] = None        # short blurb (for disambiguation snippets)

    def to_dict(self) -> dict:
        return {
            "tmdb_id": self.tmdb_id,
            "media_type": self.media_type,
            "title": self.title,
            "year": self.year,
            "primary_genre_id": self.primary_genre_id,
            "genre_ids": self.genre_ids,
            "distributor": self.distributor,
            "pools": sorted(self.pools),
            "source_person_ids": self.source_person_ids,
            "overview": self.overview,
        }


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class CandidateGenerator:
    """Builds P1/P2/P3 candidate pools.

    The class is stateless across calls — `build_pools` does all the work.
    A single TMDbClient is reused so the SQLite cache pays off.
    """

    def __init__(self, tmdb: TMDbClient, *, time_window_years: int = 5):
        self.tmdb = tmdb
        self.time_window_years = time_window_years

    # ---- entrypoint -----------------------------------------------------

    def build_pools(self, input_meta: dict, intake: dict) -> dict[str, Any]:
        """Returns: {
            'input': {tmdb_id, media_type, title, year, primary_genre_id, director_id, cast_ids},
            'pools': {'P1': [Candidate, ...], 'P2': [...], 'P3': [...]},
            'merged': [Candidate, ...],
            'gaps': [{'pool': 'P1', 'reason': '...'}, ...]
        }

        input_meta is the result of `resolve_input(...)`.
        intake is the analyst's 7-question payload (see skills/intake/SKILL.md).
        """
        media_type = input_meta["media_type"]
        primary_genre = input_meta.get("primary_genre_id")
        date_lo, date_hi = _date_window(self.time_window_years)
        gaps: list[dict] = []
        pools: dict[str, list[Candidate]] = {"P1": [], "P2": [], "P3": []}

        # P1 — director / creator credits
        director_ids = input_meta.get("director_ids", [])
        if not director_ids:
            gaps.append({"pool": "P1", "reason": "no director/creator found on input"})
        for pid in director_ids:
            pools["P1"].extend(
                self._person_candidates(
                    pid, media_type, primary_genre, date_lo, date_hi,
                    exclude_id=input_meta["tmdb_id"],
                )
            )

        # P2 — top 3 billed cast credits
        cast_ids = input_meta.get("cast_ids", [])[:3]
        if not cast_ids:
            gaps.append({"pool": "P2", "reason": "no cast found on input"})
        for pid in cast_ids:
            pools["P2"].extend(
                self._person_candidates(
                    pid, media_type, primary_genre, date_lo, date_hi,
                    exclude_id=input_meta["tmdb_id"],
                )
            )

        # P3 — /discover with genre + date window
        if primary_genre is None:
            gaps.append({"pool": "P3", "reason": "no primary genre on input"})
        else:
            pools["P3"].extend(
                self._discover_candidates(media_type, primary_genre, date_lo, date_hi,
                                         exclude_id=input_meta["tmdb_id"])
            )

        merged = _dedupe(pools)
        return {
            "input": input_meta,
            "pools": {k: [c.to_dict() for c in v] for k, v in pools.items()},
            "merged": [c.to_dict() for c in merged],
            "gaps": gaps,
            "window": {"gte": date_lo, "lte": date_hi},
        }

    # ---- helpers --------------------------------------------------------

    def _person_candidates(
        self,
        person_id: int,
        media_type: str,
        primary_genre: Optional[int],
        date_lo: str,
        date_hi: str,
        exclude_id: int,
    ) -> list[Candidate]:
        """Pull a person's credits in the right media type and filter to genre+window."""
        if media_type == "movie":
            credits = self.tmdb.get_person_movie_credits(person_id)
            jobs = credits.get("cast", []) + credits.get("crew", [])
            out: list[Candidate] = []
            for cred in jobs:
                if cred.get("id") == exclude_id:
                    continue
                rd = cred.get("release_date") or ""
                if not _in_window(rd, date_lo, date_hi):
                    continue
                gids = cred.get("genre_ids") or []
                if primary_genre is not None and primary_genre not in gids:
                    continue
                out.append(Candidate(
                    tmdb_id=cred["id"],
                    media_type="movie",
                    title=cred.get("title") or cred.get("name") or "",
                    year=_year_of(rd),
                    primary_genre_id=primary_genre if primary_genre in gids else (gids[0] if gids else None),
                    genre_ids=gids,
                    overview=cred.get("overview"),
                    source_person_ids=[person_id],
                ))
            return out
        elif media_type == "tv":
            credits = self.tmdb.get_person_tv_credits(person_id)
            jobs = credits.get("cast", []) + credits.get("crew", [])
            out = []
            for cred in jobs:
                if cred.get("id") == exclude_id:
                    continue
                rd = cred.get("first_air_date") or ""
                if not _in_window(rd, date_lo, date_hi):
                    continue
                gids = cred.get("genre_ids") or []
                if primary_genre is not None and primary_genre not in gids:
                    continue
                out.append(Candidate(
                    tmdb_id=cred["id"],
                    media_type="tv",
                    title=cred.get("name") or cred.get("original_name") or "",
                    year=_year_of(rd),
                    primary_genre_id=primary_genre if primary_genre in gids else (gids[0] if gids else None),
                    genre_ids=gids,
                    overview=cred.get("overview"),
                    source_person_ids=[person_id],
                ))
            return out
        else:
            raise ValueError(f"unsupported media_type {media_type!r}")

    def _discover_candidates(
        self,
        media_type: str,
        primary_genre: int,
        date_lo: str,
        date_hi: str,
        exclude_id: int,
    ) -> list[Candidate]:
        if media_type == "movie":
            res = self.tmdb.discover_movie(
                with_genres=[primary_genre],
                primary_release_date_gte=date_lo,
                primary_release_date_lte=date_hi,
            )
            out: list[Candidate] = []
            for r in res:
                if r.get("id") == exclude_id:
                    continue
                rd = r.get("release_date") or ""
                out.append(Candidate(
                    tmdb_id=r["id"],
                    media_type="movie",
                    title=r.get("title", ""),
                    year=_year_of(rd),
                    primary_genre_id=primary_genre,
                    genre_ids=r.get("genre_ids", []),
                    overview=r.get("overview"),
                ))
            return out
        else:
            res = self.tmdb.discover_tv(
                with_genres=[primary_genre],
                first_air_date_gte=date_lo,
                first_air_date_lte=date_hi,
            )
            out = []
            for r in res:
                if r.get("id") == exclude_id:
                    continue
                rd = r.get("first_air_date") or ""
                out.append(Candidate(
                    tmdb_id=r["id"],
                    media_type="tv",
                    title=r.get("name", ""),
                    year=_year_of(rd),
                    primary_genre_id=primary_genre,
                    genre_ids=r.get("genre_ids", []),
                    overview=r.get("overview"),
                ))
            return out


# ---------------------------------------------------------------------------
# Input resolution (lookup the analyst's title)
# ---------------------------------------------------------------------------

def resolve_input(tmdb: TMDbClient, title: str, *, media_type: str, tmdb_id: Optional[int] = None) -> dict:
    """Look up the analyst's input title on TMDb and assemble seed metadata.

    If `tmdb_id` is given we skip search. Otherwise we search and *expect a single
    result* — multi-match resolution happens in disambiguator.py; this function
    just trusts what it's given.
    """
    if tmdb_id is None:
        if media_type == "movie":
            results = tmdb.search_movie(title)
        else:
            results = tmdb.search_tv(title)
        if not results:
            raise TMDbNotFound(f"no TMDb results for {title!r} ({media_type})")
        if len(results) > 1:
            raise ValueError(
                f"multiple TMDb results for {title!r} — resolve via disambiguator first"
            )
        tmdb_id = results[0]["id"]

    if media_type == "movie":
        details = tmdb.get_movie(tmdb_id)
        credits = tmdb.get_movie_credits(tmdb_id)
        rd = details.get("release_date") or ""
        d = director_of(credits)
        director_ids = [d["id"]] if d else []
        cast_ids = [c["id"] for c in top_cast(credits, n=3)]
        genres = details.get("genres", [])
        primary_genre = genres[0]["id"] if genres else None
        return {
            "tmdb_id": tmdb_id,
            "media_type": "movie",
            "title": details.get("title", ""),
            "year": _year_of(rd),
            "primary_genre_id": primary_genre,
            "genre_ids": [g["id"] for g in genres],
            "director_ids": director_ids,
            "cast_ids": cast_ids,
        }
    else:
        details = tmdb.get_tv(tmdb_id)
        credits = tmdb.get_tv_credits(tmdb_id)
        creators = creators_of_tv(details)
        director_ids = [c["id"] for c in creators]
        cast_ids = [c["id"] for c in top_cast(credits, n=3)]
        genres = details.get("genres", [])
        primary_genre = genres[0]["id"] if genres else None
        rd = details.get("first_air_date") or ""
        return {
            "tmdb_id": tmdb_id,
            "media_type": "tv",
            "title": details.get("name", ""),
            "year": _year_of(rd),
            "primary_genre_id": primary_genre,
            "genre_ids": [g["id"] for g in genres],
            "director_ids": director_ids,
            "cast_ids": cast_ids,
        }


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _date_window(years: int) -> tuple[str, str]:
    today = date.today()
    lo = today.replace(year=today.year - years)
    return lo.isoformat(), today.isoformat()


def _in_window(date_str: str, lo: str, hi: str) -> bool:
    if not date_str or len(date_str) < 10:
        return False
    return lo <= date_str[:10] <= hi


def _year_of(date_str: str) -> Optional[int]:
    if not date_str or len(date_str) < 4:
        return None
    try:
        return int(date_str[:4])
    except ValueError:
        return None


def _dedupe(pools: dict[str, list[Candidate]]) -> list[Candidate]:
    """Merge pools by tmdb_id. A candidate that appears in multiple pools keeps
    all pool tags (`{'P1','P3'}`) — the ranker uses the highest (P1)."""
    by_id: dict[tuple[str, int], Candidate] = {}
    for pool_name, items in pools.items():
        for c in items:
            key = (c.media_type, c.tmdb_id)
            existing = by_id.get(key)
            if existing is None:
                c.pools = {pool_name}
                by_id[key] = c
            else:
                existing.pools.add(pool_name)
                # merge source_person_ids
                existing.source_person_ids = sorted(set(existing.source_person_ids + c.source_person_ids))
    return list(by_id.values())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:
    p = argparse.ArgumentParser(prog="candidate_generator")
    p.add_argument("--title", required=True)
    p.add_argument("--type", choices=("theatrical", "streaming_film", "streaming_series"), required=True)
    p.add_argument("--tmdb-id", type=int, help="Skip search; use this TMDb id")
    p.add_argument("--out", default=None, help="Write the result to this JSON path")
    p.add_argument("--window-years", type=int, default=5)
    args = p.parse_args()

    media_type = "tv" if args.type == "streaming_series" else "movie"

    tmdb = TMDbClient()
    try:
        t0 = time.time()
        input_meta = resolve_input(tmdb, args.title, media_type=media_type, tmdb_id=args.tmdb_id)
        cg = CandidateGenerator(tmdb=tmdb, time_window_years=args.window_years)
        # intake is mostly read by the rule engine, not the generator — passing a stub here
        intake_stub = {"release_type": args.type}
        result = cg.build_pools(input_meta, intake_stub)
        dt = time.time() - t0
        result["elapsed_s"] = round(dt, 2)
    except TMDbNotFound as e:
        print(f"NOT FOUND: {e}", file=sys.stderr)
        return 1
    finally:
        tmdb.close()

    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"wrote {args.out} — P1={len(result['pools']['P1'])} P2={len(result['pools']['P2'])} "
              f"P3={len(result['pools']['P3'])} merged={len(result['merged'])} ({result['elapsed_s']}s)")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
