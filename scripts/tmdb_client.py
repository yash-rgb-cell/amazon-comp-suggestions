"""
TMDb API client with SQLite cache and polite retry.

Reads TMDB_API_KEY from the environment. Fails fast if missing.
Two TTL buckets: 7 days for stable data, 1 hour for current streaming providers.

Usage as a module:
    from scripts.tmdb_client import TMDbClient
    tmdb = TMDbClient()
    results = tmdb.search_movie("How to Rob a Bank")
    credits = tmdb.get_movie_credits(results[0]["id"])

Usage from the CLI:
    python -m scripts.tmdb_client search-movie "How to Rob a Bank"
    python -m scripts.tmdb_client search-multi "the grey"
    python -m scripts.tmdb_client movie 12345
    python -m scripts.tmdb_client tv 54321
    python -m scripts.tmdb_client credits movie 12345
    python -m scripts.tmdb_client person-movie-credits 67890
    python -m scripts.tmdb_client watch-providers movie 12345
    python -m scripts.tmdb_client keywords movie 12345
    python -m scripts.tmdb_client external-ids movie 12345
    python -m scripts.tmdb_client get-keyword 818
    python -m scripts.tmdb_client discover-movie --genres 28 --year-min 2022
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional
from urllib.parse import urlencode

import httpx

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://api.themoviedb.org/3"
DEFAULT_REGION = "US"
USER_AGENT = "LF-CompSuggestions/1.0 (internal LF tool)"

# Cache TTLs in seconds
TTL_STABLE = 7 * 24 * 60 * 60       # 7 days
TTL_PROVIDERS = 60 * 60             # 1 hour
TTL_EXTERNAL_IDS = 30 * 24 * 60 * 60  # 30 days — these almost never change

# Endpoints that should use the short TTL
SHORT_TTL_ENDPOINTS = ("/watch/providers",)
EXTERNAL_ID_ENDPOINTS = ("/external_ids",)

CACHE_PATH = Path(__file__).resolve().parent / ".tmdb_cache.sqlite"
ENV_VAR = "TMDB_API_KEY"

# Retry policy
RETRY_BACKOFFS = (1.0, 2.0, 4.0)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class TMDbConfigError(RuntimeError):
    """Raised when the TMDb client is misconfigured (e.g. missing API key)."""


class TMDbNotFound(RuntimeError):
    """Raised when an endpoint returns a 404."""


class TMDbAPIError(RuntimeError):
    """Raised for non-404 non-200 responses after exhausting retries."""


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_connect(path: Path = CACHE_PATH) -> sqlite3.Connection:
    """Open (or create) the SQLite cache. Pragmas tuned for read-heavy workloads."""
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            body TEXT NOT NULL,
            expires_at INTEGER NOT NULL
        )
        """
    )
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _cache_key(url: str, params: dict) -> str:
    """Stable hash of URL + sorted params, excluding the API key."""
    safe_params = {k: v for k, v in sorted(params.items()) if k != "api_key"}
    raw = url + "?" + urlencode(safe_params)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_get(conn: sqlite3.Connection, key: str) -> Optional[dict]:
    """Return cached body if present and not expired, else None."""
    row = conn.execute(
        "SELECT body, expires_at FROM cache WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        return None
    body, expires_at = row
    if expires_at < int(time.time()):
        return None
    return json.loads(body)


def _cache_put(conn: sqlite3.Connection, key: str, url: str, body: dict, ttl: int) -> None:
    """Insert or replace a cache entry."""
    expires_at = int(time.time()) + ttl
    conn.execute(
        "INSERT OR REPLACE INTO cache(key, url, body, expires_at) VALUES (?, ?, ?, ?)",
        (key, url, json.dumps(body), expires_at),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

@dataclass
class TMDbClient:
    """TMDb API wrapper. Single instance per process is fine — SQLite is concurrent-safe in WAL mode."""

    api_key: Optional[str] = None
    region: str = DEFAULT_REGION
    timeout: float = 15.0
    use_cache: bool = True

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.environ.get(ENV_VAR)
        if not self.api_key:
            raise TMDbConfigError(
                f"Missing {ENV_VAR}. Get a free key at "
                "https://www.themoviedb.org/settings/api and `export "
                f"{ENV_VAR}=<your-key>`."
            )
        self._client = httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        self._cache = _cache_connect() if self.use_cache else None

    def close(self) -> None:
        self._client.close()
        if self._cache is not None:
            self._cache.close()

    # ---- internal --------------------------------------------------------

    def _ttl_for(self, path: str) -> int:
        if any(path.endswith(suf) for suf in SHORT_TTL_ENDPOINTS):
            return TTL_PROVIDERS
        if any(path.endswith(suf) for suf in EXTERNAL_ID_ENDPOINTS):
            return TTL_EXTERNAL_IDS
        return TTL_STABLE

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        """GET with cache + retry. 404 -> TMDbNotFound. Other errors raise after retries."""
        params = dict(params or {})
        params["api_key"] = self.api_key
        url = f"{BASE_URL}{path}"

        ck = _cache_key(url, params)
        if self._cache is not None:
            cached = _cache_get(self._cache, ck)
            if cached is not None:
                return cached

        last_exc: Optional[Exception] = None
        for attempt, backoff in enumerate((0.0, *RETRY_BACKOFFS)):
            if backoff:
                time.sleep(backoff)
            try:
                resp = self._client.get(url, params=params)
                if resp.status_code == 404:
                    raise TMDbNotFound(f"404 at {path} with {params}")
                if resp.status_code == 429:
                    # rate-limited — backoff and retry
                    last_exc = TMDbAPIError(f"429 at {path}")
                    continue
                if resp.status_code >= 500:
                    last_exc = TMDbAPIError(f"{resp.status_code} at {path}")
                    continue
                resp.raise_for_status()
                body = resp.json()
                if self._cache is not None:
                    _cache_put(self._cache, ck, url, body, self._ttl_for(path))
                return body
            except TMDbNotFound:
                raise
            except httpx.RequestError as e:
                last_exc = e
                continue

        raise TMDbAPIError(
            f"GET {path} failed after {len(RETRY_BACKOFFS)+1} attempts: {last_exc!r}"
        )

    # ---- public ----------------------------------------------------------

    # search ---------------------------------------------------------------

    def search_movie(self, query: str, year: Optional[int] = None) -> list[dict]:
        params: dict[str, Any] = {"query": query, "include_adult": "false"}
        if year:
            params["primary_release_year"] = year
        return self._get("/search/movie", params).get("results", [])

    def search_tv(self, query: str, year: Optional[int] = None) -> list[dict]:
        params: dict[str, Any] = {"query": query, "include_adult": "false"}
        if year:
            params["first_air_date_year"] = year
        return self._get("/search/tv", params).get("results", [])

    def search_multi(self, query: str) -> list[dict]:
        """Returns mixed movies + tv + persons. Used by the disambiguator."""
        return self._get("/search/multi", {"query": query, "include_adult": "false"}).get("results", [])

    # details --------------------------------------------------------------

    def get_movie(self, movie_id: int) -> dict:
        return self._get(f"/movie/{movie_id}")

    def get_tv(self, tv_id: int) -> dict:
        return self._get(f"/tv/{tv_id}")

    def get_movie_credits(self, movie_id: int) -> dict:
        return self._get(f"/movie/{movie_id}/credits")

    def get_tv_credits(self, tv_id: int) -> dict:
        # /tv/{id}/aggregate_credits is more thorough for series, but slower; cast list works for our use case
        return self._get(f"/tv/{tv_id}/credits")

    def get_external_ids(self, media_type: str, media_id: int) -> dict:
        if media_type not in ("movie", "tv"):
            raise ValueError(f"media_type must be 'movie' or 'tv', got {media_type!r}")
        return self._get(f"/{media_type}/{media_id}/external_ids")

    def get_keywords(self, media_type: str, media_id: int) -> dict:
        if media_type not in ("movie", "tv"):
            raise ValueError(f"media_type must be 'movie' or 'tv', got {media_type!r}")
        return self._get(f"/{media_type}/{media_id}/keywords")

    def get_watch_providers(self, media_type: str, media_id: int) -> dict:
        if media_type not in ("movie", "tv"):
            raise ValueError(f"media_type must be 'movie' or 'tv', got {media_type!r}")
        body = self._get(f"/{media_type}/{media_id}/watch/providers")
        # Return only the user's region (default US) for downstream simplicity
        return body.get("results", {}).get(self.region, {})

    def get_keyword(self, keyword_id: int) -> dict:
        return self._get(f"/keyword/{keyword_id}")

    # person credits -------------------------------------------------------

    def get_person_movie_credits(self, person_id: int) -> dict:
        return self._get(f"/person/{person_id}/movie_credits")

    def get_person_tv_credits(self, person_id: int) -> dict:
        return self._get(f"/person/{person_id}/tv_credits")

    # discover -------------------------------------------------------------

    def discover_movie(
        self,
        with_genres: Optional[Iterable[int]] = None,
        primary_release_date_gte: Optional[str] = None,
        primary_release_date_lte: Optional[str] = None,
        with_original_language: str = "en",
        sort_by: str = "popularity.desc",
        page: int = 1,
    ) -> list[dict]:
        params: dict[str, Any] = {
            "sort_by": sort_by,
            "include_adult": "false",
            "include_video": "false",
            "page": page,
            "with_original_language": with_original_language,
        }
        if with_genres:
            params["with_genres"] = ",".join(str(g) for g in with_genres)
        if primary_release_date_gte:
            params["primary_release_date.gte"] = primary_release_date_gte
        if primary_release_date_lte:
            params["primary_release_date.lte"] = primary_release_date_lte
        return self._get("/discover/movie", params).get("results", [])

    def discover_tv(
        self,
        with_genres: Optional[Iterable[int]] = None,
        first_air_date_gte: Optional[str] = None,
        first_air_date_lte: Optional[str] = None,
        with_original_language: str = "en",
        sort_by: str = "popularity.desc",
        page: int = 1,
    ) -> list[dict]:
        params: dict[str, Any] = {
            "sort_by": sort_by,
            "include_adult": "false",
            "page": page,
            "with_original_language": with_original_language,
        }
        if with_genres:
            params["with_genres"] = ",".join(str(g) for g in with_genres)
        if first_air_date_gte:
            params["first_air_date.gte"] = first_air_date_gte
        if first_air_date_lte:
            params["first_air_date.lte"] = first_air_date_lte
        return self._get("/discover/tv", params).get("results", [])


# ---------------------------------------------------------------------------
# Helpers used by other scripts
# ---------------------------------------------------------------------------

def director_of(credits: dict) -> Optional[dict]:
    """Return the first crew entry with job == 'Director', else None."""
    for c in credits.get("crew", []):
        if c.get("job") == "Director":
            return c
    return None


def creators_of_tv(tv_details: dict) -> list[dict]:
    """For TV, 'created_by' is the analog of director."""
    return tv_details.get("created_by", []) or []


def top_cast(credits: dict, n: int = 3) -> list[dict]:
    cast = credits.get("cast", []) or []
    cast = sorted(cast, key=lambda c: c.get("order", 9999))
    return cast[:n]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print(obj: Any) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _cli() -> int:
    p = argparse.ArgumentParser(prog="tmdb_client")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("search-movie")
    sp.add_argument("query")
    sp.add_argument("--year", type=int)

    sp = sub.add_parser("search-tv")
    sp.add_argument("query")
    sp.add_argument("--year", type=int)

    sp = sub.add_parser("search-multi")
    sp.add_argument("query")

    sp = sub.add_parser("movie")
    sp.add_argument("id", type=int)

    sp = sub.add_parser("tv")
    sp.add_argument("id", type=int)

    sp = sub.add_parser("credits")
    sp.add_argument("media_type", choices=("movie", "tv"))
    sp.add_argument("id", type=int)

    sp = sub.add_parser("external-ids")
    sp.add_argument("media_type", choices=("movie", "tv"))
    sp.add_argument("id", type=int)

    sp = sub.add_parser("keywords")
    sp.add_argument("media_type", choices=("movie", "tv"))
    sp.add_argument("id", type=int)

    sp = sub.add_parser("watch-providers")
    sp.add_argument("media_type", choices=("movie", "tv"))
    sp.add_argument("id", type=int)

    sp = sub.add_parser("person-movie-credits")
    sp.add_argument("id", type=int)

    sp = sub.add_parser("person-tv-credits")
    sp.add_argument("id", type=int)

    sp = sub.add_parser("get-keyword")
    sp.add_argument("id", type=int)

    sp = sub.add_parser("discover-movie")
    sp.add_argument("--genres", nargs="*", type=int, default=[])
    sp.add_argument("--year-min", type=int)
    sp.add_argument("--year-max", type=int)

    sp = sub.add_parser("discover-tv")
    sp.add_argument("--genres", nargs="*", type=int, default=[])
    sp.add_argument("--year-min", type=int)
    sp.add_argument("--year-max", type=int)

    args = p.parse_args()
    try:
        tmdb = TMDbClient()
    except TMDbConfigError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    try:
        if args.cmd == "search-movie":
            _print(tmdb.search_movie(args.query, year=args.year))
        elif args.cmd == "search-tv":
            _print(tmdb.search_tv(args.query, year=args.year))
        elif args.cmd == "search-multi":
            _print(tmdb.search_multi(args.query))
        elif args.cmd == "movie":
            _print(tmdb.get_movie(args.id))
        elif args.cmd == "tv":
            _print(tmdb.get_tv(args.id))
        elif args.cmd == "credits":
            getter = tmdb.get_movie_credits if args.media_type == "movie" else tmdb.get_tv_credits
            _print(getter(args.id))
        elif args.cmd == "external-ids":
            _print(tmdb.get_external_ids(args.media_type, args.id))
        elif args.cmd == "keywords":
            _print(tmdb.get_keywords(args.media_type, args.id))
        elif args.cmd == "watch-providers":
            _print(tmdb.get_watch_providers(args.media_type, args.id))
        elif args.cmd == "person-movie-credits":
            _print(tmdb.get_person_movie_credits(args.id))
        elif args.cmd == "person-tv-credits":
            _print(tmdb.get_person_tv_credits(args.id))
        elif args.cmd == "get-keyword":
            _print(tmdb.get_keyword(args.id))
        elif args.cmd == "discover-movie":
            yr_min = f"{args.year_min}-01-01" if args.year_min else None
            yr_max = f"{args.year_max}-12-31" if args.year_max else None
            _print(tmdb.discover_movie(
                with_genres=args.genres or None,
                primary_release_date_gte=yr_min,
                primary_release_date_lte=yr_max,
            ))
        elif args.cmd == "discover-tv":
            yr_min = f"{args.year_min}-01-01" if args.year_min else None
            yr_max = f"{args.year_max}-12-31" if args.year_max else None
            _print(tmdb.discover_tv(
                with_genres=args.genres or None,
                first_air_date_gte=yr_min,
                first_air_date_lte=yr_max,
            ))
        else:
            print(f"Unknown command: {args.cmd}", file=sys.stderr)
            return 2
    except TMDbNotFound as e:
        print(f"NOT FOUND: {e}", file=sys.stderr)
        return 1
    except TMDbAPIError as e:
        print(f"API ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        tmdb.close()
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
