# Data Sources

Two external sources. Both are free. One has an API, one does not.

## TMDb (The Movie Database)

Free API. Requires a key at `https://www.themoviedb.org/settings/api` (~15 minute approval). Read the key from the `TMDB_API_KEY` environment variable.

Base URL: `https://api.themoviedb.org/3`

### Endpoints we use

| Endpoint | Purpose | Cache TTL |
|---|---|---|
| `/search/movie?query=<q>` | Find candidate title (theatrical) | 7d |
| `/search/tv?query=<q>` | Find candidate title (series) | 7d |
| `/search/multi?query=<q>` | Disambiguation — returns movies + TV + people | 7d |
| `/movie/{id}` | Movie details (genres, runtime, release_date) | 7d |
| `/tv/{id}` | TV details (genres, seasons, first_air_date) | 7d |
| `/movie/{id}/credits` | Cast + crew (extract director, top-3 billed) | 7d |
| `/tv/{id}/credits` | Series cast | 7d |
| `/movie/{id}/external_ids` | Get IMDb ID for BOM scrape | 30d |
| `/tv/{id}/external_ids` | Get IMDb ID | 30d |
| `/movie/{id}/keywords` | Keywords — IP detection (based_on_novel, etc.) | 30d |
| `/tv/{id}/keywords` | Keywords | 30d |
| `/movie/{id}/watch/providers` | US streaming availability | **1h** (current, changes weekly) |
| `/tv/{id}/watch/providers` | US streaming availability | **1h** |
| `/person/{id}/movie_credits` | All movies by a person (P1, P2 pools) | 7d |
| `/person/{id}/tv_credits` | All TV by a person | 7d |
| `/discover/movie?with_genres=...&primary_release_date.gte=...` | P3 pool: genre + date window | 7d |
| `/discover/tv?with_genres=...&first_air_date.gte=...` | P3 pool for series | 7d |

### Rate limiting

TMDb's published limit is 50 requests / second / IP. We're nowhere near that. The retry logic in `tmdb_client.py` handles transient 429s with exponential backoff (1s → 2s → 4s, then give up).

### Cache

SQLite, file at `scripts/.tmdb_cache.sqlite` (auto-created; gitignored). Keyed by full URL + sorted query params. Two TTL buckets: 7-day (stable: search, credits, keywords) and 1-hour (mutable: watch providers).

## Box Office Mojo

No API. We scrape. The URL pattern is:

```
https://www.boxofficemojo.com/title/tt<IMDB_ID>/
```

Get the IMDb ID from TMDb's `/movie/{id}/external_ids` endpoint.

### What we extract

Opening weekend in US dollars. On the page, this lives in the "Domestic Opening" section.

Primary selector (the most stable as of 2026-05):
```css
table tr:has(td:contains("Opening")) td.money
```

Fallback selector (used if primary returns nothing):
```css
.mojo-performance-summary .a-section .money
```

If both selectors return nothing → return `None`. The candidate gets tagged "BO unverified" downstream and is kept (per `rules.md` rule 5).

### Politeness

- 2-second delay between requests (hardcoded in `box_office_scraper.py`).
- Aggressive on-disk cache: 90-day TTL for any title released >30 days ago (their numbers don't change). 1-day TTL for any title released in the last 30 days.
- User-Agent string identifies us as a non-malicious tool: `LF-CompSuggestions/1.0 (internal LF tool; contact: analytics@listenfirstmedia.com)`.

### Maintenance — this WILL break someday

Box Office Mojo (an IMDb-owned property) redesigns roughly every 18-24 months. When the scraper starts returning all-None:

1. Manually visit `https://www.boxofficemojo.com/title/tt<some_known_id>/` in a browser.
2. Inspect the new DOM around the "Opening" text.
3. Update both selectors in `scripts/box_office_scraper.py`. Keep the old selectors as additional fallbacks (try every selector in order).
4. Run `python -m scripts.box_office_scraper tt1234567 --no-cache` against 3-5 known titles to verify.
5. Add a dated comment in the file header noting the redesign and the change.

The skill survives a BOM outage in degraded mode: every candidate gets "BO unverified" and the analyst sees that in the draft. They can choose to ship anyway or wait for the fix.

## What we explicitly do NOT use

- **Paid APIs.** No Numbers, no The-Numbers paid tier, no Variety Insight, no Comscore.
- **OMDb.** Has rate limits even on the free tier and the OW data is sparse.
- **Wikipedia scraping.** OW numbers there are inconsistent and editorialized.
- **TMDb's "revenue" field for movies.** That's lifetime gross, not opening weekend. Useless for our band-matching rule.
