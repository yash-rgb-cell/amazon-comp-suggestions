---
name: tmdb_client
description: Thin wrapper around TMDb's free REST API with SQLite caching and polite retry. Used by every other sub-skill that needs movie/TV metadata, cast, keywords, watch providers, or person credits.
---

# Skill: tmdb_client

## Purpose

One canonical entry point for every TMDb call the skill makes. Avoid duplicating endpoint URLs, query params, and retry logic across the codebase.

## When to invoke

Anytime you need:
- Title search (single or multi)
- Movie/TV details
- Cast / crew / creators
- External IDs (IMDb ID — needed for the box office scraper)
- Keywords (IP detection)
- Watch providers (streaming distribution)
- Person credits (P1, P2 pools)
- /discover (P3 pool)

## Public API

```python
from scripts.tmdb_client import TMDbClient, director_of, creators_of_tv, top_cast

tmdb = TMDbClient()  # reads TMDB_API_KEY from env

# search
tmdb.search_movie("How to Rob a Bank")
tmdb.search_tv("Reservation Dogs")
tmdb.search_multi("the grey")    # mixed movies + tv + persons (we filter)

# details
tmdb.get_movie(1071215)
tmdb.get_tv(54321)

# credits
credits = tmdb.get_movie_credits(1071215)
director = director_of(credits)        # first {job: 'Director'} crew entry
cast = top_cast(credits, n=3)          # top 3 billed

# external ids (used for BOM)
tmdb.get_external_ids("movie", 1071215)

# keywords (IP detection)
tmdb.get_keywords("movie", 1071215)

# watch providers (US only, single dict)
tmdb.get_watch_providers("movie", 1071215)

# person credits (P1/P2 pools)
tmdb.get_person_movie_credits(person_id=123)
tmdb.get_person_tv_credits(person_id=123)

# discover (P3 pool)
tmdb.discover_movie(with_genres=[28], primary_release_date_gte="2021-01-01")
tmdb.discover_tv(with_genres=[10765], first_air_date_gte="2021-01-01")
```

## Caching

SQLite at `scripts/.tmdb_cache.sqlite` (auto-created, gitignored). Two TTL buckets:

- 7 days — stable data: search, details, credits, keywords
- 1 hour — watch providers (they change weekly)
- 30 days — external IDs (effectively immutable)

Clear the cache by deleting the file.

## Error handling

- `TMDbConfigError` — missing `TMDB_API_KEY`. Tell the analyst the URL to get one: https://www.themoviedb.org/settings/api
- `TMDbNotFound` — 404 from TMDb. Caller decides whether to fail or skip.
- `TMDbAPIError` — 5xx after retry exhaustion. Caller surfaces this and offers to retry later.

## Retry policy

Exponential backoff at 1s → 2s → 4s for 429 and 5xx. Then give up.

## CLI

Every endpoint has a CLI subcommand for ad-hoc debugging:

```bash
python -m scripts.tmdb_client search-movie "How to Rob a Bank"
python -m scripts.tmdb_client movie 1071215
python -m scripts.tmdb_client credits movie 1071215
python -m scripts.tmdb_client watch-providers movie 1071215
python -m scripts.tmdb_client get-keyword 818
```

## Hard rules

- **Never call TMDb without going through this client.** Cache hit rate matters.
- **Never log the API key.** It's a query param, but never echo the constructed URL to chat.
