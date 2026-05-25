"""
Box Office Mojo opening-weekend scraper.

Polite, cached, fragile-by-design.

The URL pattern is https://www.boxofficemojo.com/title/tt<IMDB_ID>/
(IMDb IDs come from TMDb's /external_ids endpoint.)

Returns opening weekend USD as a float, or None if BOM doesn't have the data
(unreleased title, theatrical-only metric missing for streaming releases, etc.).

Fragility note: BOM redesigns ~every 18-24 months. When this stops working,
update the CSS selectors below and add a dated comment to the changelog. See
references/data_sources.md "Maintenance" section.

Usage as a module:
    from scripts.box_office_scraper import BoxOfficeMojoScraper
    bom = BoxOfficeMojoScraper()
    ow = bom.opening_weekend("tt1235522")   # returns 27.7 (millions) or None

Usage from the CLI:
    python -m scripts.box_office_scraper tt1235522
    python -m scripts.box_office_scraper tt1235522 --no-cache
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "https://www.boxofficemojo.com/title/{imdb_id}/"
USER_AGENT = "LF-CompSuggestions/1.0 (internal LF tool; contact: analytics@listenfirstmedia.com)"
REQUEST_DELAY_S = 2.0

# Caching: 90 days for "old" titles, 1 day for recent ones. The cutoff is
# 30 days post-release — past that, OW numbers are final.
CACHE_PATH = Path(__file__).resolve().parent / ".bom_cache.sqlite"
TTL_OLD = 90 * 24 * 60 * 60
TTL_RECENT = 1 * 24 * 60 * 60

# Selectors — ordered, primary first. Add new selectors at the TOP when BOM
# redesigns and keep the old ones below as fallback.
SELECTORS = [
    # 2026-05-25 — primary: structured Mojo performance summary
    ".mojo-performance-summary-table .a-section .money",
    # legacy: table cell labeled "Opening"
    "tr td.money",  # broader, validated by context match below
]

# Money regex — handles $27,712,495 / $27.7M / $5,000 etc.
_MONEY_RE = re.compile(r"\$([0-9,]+(?:\.[0-9]+)?)([MK]?)")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class BOMNotFound(RuntimeError):
    pass


class BOMScrapeError(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_connect(path: Path = CACHE_PATH) -> sqlite3.Connection:
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


def _cache_key(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _cache_get(conn: sqlite3.Connection, key: str) -> Optional[str]:
    row = conn.execute(
        "SELECT body, expires_at FROM cache WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        return None
    body, expires_at = row
    if expires_at < int(time.time()):
        return None
    return body


def _cache_put(conn: sqlite3.Connection, key: str, url: str, body: str, ttl: int) -> None:
    expires_at = int(time.time()) + ttl
    conn.execute(
        "INSERT OR REPLACE INTO cache(key, url, body, expires_at) VALUES (?, ?, ?, ?)",
        (key, url, body, expires_at),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Scraper
# ---------------------------------------------------------------------------

@dataclass
class BoxOfficeMojoScraper:
    timeout: float = 20.0
    use_cache: bool = True
    delay_s: float = REQUEST_DELAY_S
    _last_fetch_at: float = 0.0

    def __post_init__(self) -> None:
        self._client = httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
            follow_redirects=True,
        )
        self._cache = _cache_connect() if self.use_cache else None

    def close(self) -> None:
        self._client.close()
        if self._cache is not None:
            self._cache.close()

    # ---- network --------------------------------------------------------

    def _fetch(self, url: str, release_was_recent: bool) -> str:
        ck = _cache_key(url)
        if self._cache is not None:
            cached = _cache_get(self._cache, ck)
            if cached is not None:
                return cached

        # Politeness: enforce delay between actual network calls
        wait = self.delay_s - (time.monotonic() - self._last_fetch_at)
        if wait > 0:
            time.sleep(wait)

        resp = self._client.get(url)
        self._last_fetch_at = time.monotonic()

        if resp.status_code == 404:
            raise BOMNotFound(f"404 at {url}")
        if resp.status_code != 200:
            raise BOMScrapeError(f"{resp.status_code} at {url}")
        body = resp.text

        if self._cache is not None:
            ttl = TTL_RECENT if release_was_recent else TTL_OLD
            _cache_put(self._cache, ck, url, body, ttl)
        return body

    # ---- public ---------------------------------------------------------

    def opening_weekend(self, imdb_id: str, release_was_recent: bool = False) -> Optional[float]:
        """
        Return the US opening weekend in millions of dollars, or None.

        `imdb_id` must include the 'tt' prefix (e.g. 'tt1235522').
        `release_was_recent` controls cache TTL — set True for titles released
        within the last 30 days; their final numbers may not be posted yet.
        """
        if not imdb_id.startswith("tt"):
            raise ValueError(f"imdb_id must start with 'tt', got {imdb_id!r}")
        url = BASE_URL.format(imdb_id=imdb_id)
        try:
            html = self._fetch(url, release_was_recent=release_was_recent)
        except BOMNotFound:
            return None

        return _extract_opening_weekend(html)


# ---------------------------------------------------------------------------
# HTML parsing
# ---------------------------------------------------------------------------

def _extract_opening_weekend(html: str) -> Optional[float]:
    """Pull the opening-weekend dollar figure out of a BOM title page.

    Strategy: walk the DOM looking for a money value adjacent to the word
    'Opening' (in a label cell or label span). Returns dollars in millions.
    Returns None if not found — caller treats that as 'BO unverified'.
    """
    tree = HTMLParser(html)

    # Approach 1: structured performance summary block
    # The current Mojo layout (2026-05) puts the opening weekend inside
    # `.mojo-performance-summary-table` with a child div whose text starts
    # with 'Opening' and a `.money` sibling.
    for section in tree.css(".mojo-performance-summary-table .a-section"):
        text = section.text(separator=" ").strip()
        if "Opening" not in text:
            continue
        money_node = section.css_first(".money")
        if money_node is None:
            continue
        val = _money_to_millions(money_node.text(strip=True))
        if val is not None:
            return val

    # Approach 2: tabular layout — find <tr> whose first cell starts with Opening
    for tr in tree.css("tr"):
        cells = tr.css("td")
        if not cells:
            continue
        first_text = cells[0].text(strip=True)
        if not first_text.lower().startswith("opening"):
            continue
        # money is one of the other cells
        for c in cells[1:]:
            ctxt = c.text(strip=True)
            v = _money_to_millions(ctxt)
            if v is not None:
                return v

    # Approach 3: structured-data nearest fallback — scan all money nodes
    # near anywhere the word "Opening" appears
    for label in tree.css("*"):
        try:
            txt = label.text(strip=True)
        except Exception:
            continue
        if txt and txt.lower() == "opening":
            parent = label.parent
            if parent is None:
                continue
            # Look at siblings for a money string
            for sib in parent.iter():
                stxt = sib.text(strip=True) if hasattr(sib, "text") else ""
                v = _money_to_millions(stxt)
                if v is not None:
                    return v

    return None


def _money_to_millions(text: str) -> Optional[float]:
    """Parse a money string into a float in millions of dollars.

    Examples:
        '$27,712,495' -> 27.7
        '$27.7M'      -> 27.7
        '$27,700,000' -> 27.7
        '$985,000'    -> 0.985   (BOM uses dollars, not millions)
        'n/a'         -> None
        ''            -> None
    """
    if not text:
        return None
    m = _MONEY_RE.search(text)
    if not m:
        return None
    num_str, suffix = m.groups()
    try:
        n = float(num_str.replace(",", ""))
    except ValueError:
        return None
    if suffix == "M":
        return round(n, 1)
    if suffix == "K":
        return round(n / 1000.0, 3)
    # plain dollar figure
    return round(n / 1_000_000.0, 1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:
    p = argparse.ArgumentParser(prog="box_office_scraper")
    p.add_argument("imdb_id", help="IMDb ID with the 'tt' prefix")
    p.add_argument("--no-cache", action="store_true")
    p.add_argument("--recent", action="store_true",
                   help="Released within the last 30 days (use shorter cache TTL)")
    args = p.parse_args()

    bom = BoxOfficeMojoScraper(use_cache=not args.no_cache)
    try:
        v = bom.opening_weekend(args.imdb_id, release_was_recent=args.recent)
    except (BOMNotFound, BOMScrapeError) as e:
        print(json.dumps({"imdb_id": args.imdb_id, "opening_weekend_m": None, "error": str(e)}, indent=2))
        return 1
    finally:
        bom.close()

    print(json.dumps({"imdb_id": args.imdb_id, "opening_weekend_m": v}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
