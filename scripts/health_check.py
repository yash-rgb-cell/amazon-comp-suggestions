"""
Health check — probe TMDb and BOM reachability and report status as JSON.

Used by Claude (the orchestrator) to decide whether to run the normal TMDb
pipeline or fall back to WebSearch. Run silently at the start of every session.

Returns a JSON object:
    {
      "tmdb": {"reachable": true|false, "reason": "..."|null, "key_present": true|false},
      "bom":  {"reachable": true|false, "reason": "..."|null},
      "mode": "tmdb" | "websearch_fallback" | "no_data_source"
    }

The mode field is the orchestrator's decision:
  - "tmdb"               → normal flow (default — both reachable, key present)
  - "websearch_fallback" → TMDb unreachable or key missing — Claude uses WebSearch
                            per skills/websearch_fallback/README.md
  - "no_data_source"     → both TMDb AND BOM unreachable AND WebSearch unavailable —
                            this is fatal; Claude should surface and stop

Usage as a module:
    from scripts.health_check import probe
    status = probe()  # dict matching the schema above

Usage from the CLI:
    python -m scripts.health_check
    python -m scripts.health_check --quiet   # exit code only (0 healthy, 1 fallback, 2 no-data)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx

if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.tmdb_client import ENV_VAR, _load_api_key_from_env_files, BASE_URL as TMDB_BASE
from scripts.box_office_scraper import BASE_URL as BOM_BASE


def _probe_tmdb(timeout: float = 5.0) -> dict[str, Any]:
    """Quick TMDb reachability probe. Doesn't burn quota — uses /configuration."""
    key = os.environ.get(ENV_VAR) or _load_api_key_from_env_files()
    if not key:
        return {"reachable": False, "reason": f"{ENV_VAR} not set", "key_present": False}
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{TMDB_BASE}/configuration", params={"api_key": key})
        if r.status_code == 200:
            return {"reachable": True, "reason": None, "key_present": True}
        if r.status_code == 401:
            return {"reachable": False, "reason": "401 unauthorized — invalid key", "key_present": True}
        return {"reachable": False, "reason": f"HTTP {r.status_code}", "key_present": True}
    except httpx.ProxyError as e:
        return {"reachable": False, "reason": f"proxy blocked: {e}", "key_present": True}
    except httpx.RequestError as e:
        return {"reachable": False, "reason": f"network error: {type(e).__name__}: {e}", "key_present": True}


def _probe_bom(timeout: float = 5.0) -> dict[str, Any]:
    """Quick BOM reachability probe. Hits a known stable title page."""
    url = BOM_BASE.format(imdb_id="tt0111161")  # Shawshank — exists forever
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            r = client.get(url, headers={"User-Agent": "LF-CompSuggestions/healthcheck"})
        if r.status_code == 200:
            return {"reachable": True, "reason": None}
        return {"reachable": False, "reason": f"HTTP {r.status_code}"}
    except httpx.ProxyError as e:
        return {"reachable": False, "reason": f"proxy blocked: {e}"}
    except httpx.RequestError as e:
        return {"reachable": False, "reason": f"network error: {type(e).__name__}"}


def probe() -> dict[str, Any]:
    """Run both probes and decide the session mode."""
    tmdb = _probe_tmdb()
    bom = _probe_bom()
    if tmdb["reachable"]:
        mode = "tmdb"
    else:
        # TMDb unreachable → fall back to WebSearch (Claude's tool); BOM is a nice-to-have
        mode = "websearch_fallback"
    return {"tmdb": tmdb, "bom": bom, "mode": mode}


def _cli() -> int:
    p = argparse.ArgumentParser(prog="health_check")
    p.add_argument("--quiet", action="store_true", help="Suppress JSON output; use exit codes only")
    args = p.parse_args()
    status = probe()
    if not args.quiet:
        print(json.dumps(status, indent=2))
    return {"tmdb": 0, "websearch_fallback": 1, "no_data_source": 2}[status["mode"]]


if __name__ == "__main__":
    sys.exit(_cli())
