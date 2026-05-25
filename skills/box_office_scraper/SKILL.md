---
name: box_office_scraper
description: Scrapes US opening-weekend dollars from Box Office Mojo. Polite (2-second rate limit), heavily cached, fragile-by-design. Used by the rule engine to filter theatrical candidates into the analyst's $M range.
---

# Skill: box_office_scraper

## Purpose

Provide opening-weekend numbers for theatrical candidates. Box Office Mojo is free, scrapeable, and has the most consistent data — but it has no API, no contract, and redesigns every 18-24 months. This sub-skill encapsulates all the fragility in one place.

## When to invoke

For every theatrical candidate before applying `rules.md` rule 5 (OW range filter). Streaming candidates skip this entirely.

## Public API

```python
from scripts.box_office_scraper import BoxOfficeMojoScraper

bom = BoxOfficeMojoScraper()
ow_m = bom.opening_weekend("tt1235522")    # IMDb ID with 'tt' prefix
# returns float (millions of USD) or None
```

`release_was_recent=True` flips the cache TTL from 90 days to 1 day. Use it for titles released in the last 30 days (their final OW numbers may not be posted yet).

## Where IMDb IDs come from

```python
from scripts.tmdb_client import TMDbClient
tmdb = TMDbClient()
ext = tmdb.get_external_ids("movie", tmdb_id)
imdb_id = ext.get("imdb_id")   # e.g. "tt1235522"
```

Cache TTL for external_ids is 30 days (almost never changes).

## Caching

SQLite at `scripts/.bom_cache.sqlite` (auto-created, gitignored). 90 days for old titles; 1 day for recent. Delete to force re-fetch.

## Politeness

- Hardcoded 2-second delay between actual network calls (cache hits don't count).
- User-Agent identifies the tool: `LF-CompSuggestions/1.0 (internal LF tool; contact: analytics@listenfirstmedia.com)`.

## Failure modes

- **404 from BOM** → returns `None`. Title genuinely not in BOM (some streaming-first releases).
- **Selector returns nothing** → returns `None`. The page exists but our parser couldn't find the OW. Caller tags the candidate "BO unverified" and **keeps it** (per `rules.md` rule 5).
- **Connection error / 5xx** → raises `BOMScrapeError`. Caller catches, logs to audit, tags "BO unverified", keeps.

The skill is designed to fail soft. A broken BOM doesn't break the pipeline — every candidate just gets "BO unverified" and the analyst decides.

## CLI

```bash
python -m scripts.box_office_scraper tt1235522
python -m scripts.box_office_scraper tt1235522 --no-cache
python -m scripts.box_office_scraper tt1235522 --recent
```

## Maintenance — this WILL break someday

When the scraper starts returning all-None and you've confirmed BOM redesigned:

1. Open `https://www.boxofficemojo.com/title/tt1235522/` in a browser. Use DevTools to inspect the "Domestic Opening" or "Opening Weekend" element.
2. In `scripts/box_office_scraper.py`, add the new CSS selector at the **top** of the `SELECTORS` list (keep the old ones below as fallbacks).
3. If the new layout no longer uses the same parsing shape, update `_extract_opening_weekend(html)` accordingly. Keep its API stable — it must always return `Optional[float]` in millions.
4. Run the smoke test from `examples/theatrical_no_ip.md` against 3-5 known titles.
5. Add a dated header comment in `scripts/box_office_scraper.py`.

## Hard rules

- **Never drop a candidate because BOM failed.** Tag it "BO unverified" instead.
- **Never bypass the rate limit.** The 2s delay is the price of access.
- **Never store BOM HTML for longer than the cache window.** It's not ours.
