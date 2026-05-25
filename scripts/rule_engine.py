"""
Rule engine — apply hard drops + soft tags, in the exact order spec'd by rules.md.

Inputs:
  - candidate_generator output (the `merged` list)
  - intake dict (release type, franchise/installment, season, box office band, IP status)

Outputs:
  - kept list (each item is the candidate dict + 'flags' + 'priority_tier' + 'opening_weekend_m' fields)
  - dropped list (with reason)
  - audit log of every rule application

The engine is deterministic. It is *not* responsible for picking the final 4-7
(that's the ranker). It just outputs every candidate that survives, tagged.

Usage as a module:
    from scripts.rule_engine import RuleEngine
    eng = RuleEngine(tmdb=tmdb, bom=bom)
    kept, dropped, audit = eng.apply(candidates, intake)

Usage from the CLI:
    python -m scripts.rule_engine --in pool.json --intake intake.json --out kept.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.tmdb_client import TMDbClient, TMDbNotFound
from scripts.box_office_scraper import BoxOfficeMojoScraper, BOMScrapeError


# ---------------------------------------------------------------------------
# Approved-platform configuration (mirrors references/approved_platforms.md)
# ---------------------------------------------------------------------------

# TMDb provider IDs that count as "approved" streaming for US comps.
APPROVED_PROVIDER_IDS: set[int] = {
    9, 119,        # Amazon / Prime Video
    8,             # Netflix
    384, 1899,     # HBO Max / Max
    15,            # Hulu
    337,           # Disney+
    386, 387,      # Peacock
    531,           # Paramount+
    350,           # Apple TV+ (accepted with caveat)
}

# Friendly display labels (id -> output string)
PROVIDER_DISPLAY: dict[int, str] = {
    9: "Prime Video", 119: "Prime Video",
    8: "Netflix",
    384: "HBO Max", 1899: "HBO Max",
    15: "Hulu",
    337: "Disney+",
    386: "Peacock", 387: "Peacock",
    531: "Paramount+",
    350: "Apple TV+",
}

# Linear networks (kept-with-flag set)
LINEAR_NETWORKS: set[str] = {
    "ABC", "NBC", "CBS", "Fox", "FOX", "The CW", "CW",
    "FX", "FXX", "Showtime", "Starz", "AMC", "BBC", "BBC America",
    "BBC One", "BBC Two", "USA Network", "TNT", "TBS",
    "History", "Discovery", "Lifetime", "Hallmark", "ESPN",
}


# IP keyword IDs (mirrors references/ip_keywords.md)
IP_KEYWORDS_BY_TYPE: dict[str, set[int]] = {
    "novel":      {818, 9663, 10661, 173272, 161176, 207263},
    "comic":      {9717, 254835, 9714, 282085, 207928, 180547},
    "video game": {282, 233824, 240073},
    "true story": {9672, 211733, 207317, 207928},
    "other":      {167043, 9849, 165824, 270783, 222243, 232614, 207926},
}
ALL_IP_KEYWORDS: set[int] = {kid for s in IP_KEYWORDS_BY_TYPE.values() for kid in s}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    candidate_id: int
    title: str
    rule: str
    action: str   # 'drop' | 'tag' | 'keep'
    detail: Optional[str] = None


@dataclass
class RuleEngine:
    tmdb: TMDbClient
    bom: BoxOfficeMojoScraper
    audit: list[AuditEntry] = field(default_factory=list)

    # ---- entrypoint ----------------------------------------------------

    def apply(self, candidates: list[dict], intake: dict) -> tuple[list[dict], list[dict], list[dict]]:
        """Apply all rules in the spec'd order. Returns (kept, dropped, audit_as_dicts)."""
        kept: list[dict] = list(candidates)
        dropped: list[dict] = []

        # Rule 1: wrong release type
        kept, drops = self._drop_wrong_release_type(kept, intake)
        dropped.extend(drops)

        # Rule 2: wrong streaming sub-type (film vs series)
        kept, drops = self._drop_wrong_streaming_subtype(kept, intake)
        dropped.extend(drops)

        # Rule 3: wrong franchise installment
        if intake.get("release_type") == "theatrical" and intake.get("franchise"):
            kept, drops = self._drop_wrong_installment(kept, intake)
            dropped.extend(drops)

        # Rule 4: wrong series season
        if intake.get("release_type") == "streaming" and intake.get("streaming_subtype") == "series":
            kept, drops = self._drop_wrong_season(kept, intake)
            dropped.extend(drops)

        # Rule 5: theatrical OW outside range (BO-unverified → tag, keep)
        if intake.get("release_type") == "theatrical":
            kept, drops = self._filter_box_office(kept, intake)
            dropped.extend(drops)

        # Rule 6 + 7: streaming approved platform / linear-outlier flag
        if intake.get("release_type") == "streaming":
            kept, drops = self._filter_streaming_platform(kept, intake)
            dropped.extend(drops)

        # Rule 8: time window (>5y AND not P1 → drop; 3-5y → tag)
        kept, drops = self._filter_time_window(kept)
        dropped.extend(drops)

        # Rule 13: IP status soft tag
        if intake.get("based_on_ip"):
            self._tag_ip_status(kept, intake)

        # Rule 14: priority tier tagging
        self._tag_priority_tier(kept)

        return kept, dropped, [a.__dict__ for a in self.audit]

    # ---- individual rules ----------------------------------------------

    def _drop_wrong_release_type(self, cs: list[dict], intake: dict) -> tuple[list[dict], list[dict]]:
        rel = intake.get("release_type")
        # theatrical → only movies; streaming film → only movies; streaming series → only tv
        want_media = "tv" if (rel == "streaming" and intake.get("streaming_subtype") == "series") else "movie"
        keep = [c for c in cs if c["media_type"] == want_media]
        drop = [c for c in cs if c["media_type"] != want_media]
        for c in drop:
            self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "release_type",
                                         "drop", f"wanted media_type={want_media}, got {c['media_type']}"))
        return keep, [{**c, "drop_reason": "wrong release type / media type"} for c in drop]

    def _drop_wrong_streaming_subtype(self, cs: list[dict], intake: dict) -> tuple[list[dict], list[dict]]:
        if intake.get("release_type") != "streaming":
            return cs, []
        sub = intake.get("streaming_subtype")
        if sub not in ("film", "series"):
            return cs, []
        # if film, drop tv; if series, drop movie (covered by Rule 1 already, but explicit here)
        want_media = "movie" if sub == "film" else "tv"
        keep = [c for c in cs if c["media_type"] == want_media]
        drop = [c for c in cs if c["media_type"] != want_media]
        for c in drop:
            self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "streaming_subtype",
                                         "drop", f"wanted {want_media} (streaming {sub})"))
        return keep, [{**c, "drop_reason": "wrong streaming subtype"} for c in drop]

    def _drop_wrong_installment(self, cs: list[dict], intake: dict) -> tuple[list[dict], list[dict]]:
        """Best-effort: drop candidates whose TMDb collection puts them at a different installment.
        Standalones (no collection) are kept — they're potential same-genre comps even if not
        themselves sequels.
        """
        want_inst = intake.get("installment")
        if not want_inst:
            return cs, []
        keep: list[dict] = []
        drop: list[dict] = []
        for c in cs:
            try:
                details = self.tmdb.get_movie(c["tmdb_id"])
            except TMDbNotFound:
                keep.append(c)
                continue
            coll = details.get("belongs_to_collection")
            if not coll:
                # standalone → keep
                keep.append(c)
                continue
            inst = _infer_installment(self.tmdb, coll["id"], c["tmdb_id"])
            if inst is None or inst == want_inst:
                keep.append(c)
            else:
                drop.append({**c, "drop_reason": f"wrong installment ({inst} != {want_inst})"})
                self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "franchise_installment",
                                             "drop", f"{inst} != {want_inst}"))
        return keep, drop

    def _drop_wrong_season(self, cs: list[dict], intake: dict) -> tuple[list[dict], list[dict]]:
        """For series comping: drop series that don't have at least the wanted season number.

        Note: TMDb doesn't tell us *which season was the launch* — we use 'has at least N seasons' as
        the proxy. A series with at least N seasons can be a Season N comp.
        """
        want_season = intake.get("season_number")
        if not want_season:
            return cs, []
        keep: list[dict] = []
        drop: list[dict] = []
        for c in cs:
            try:
                details = self.tmdb.get_tv(c["tmdb_id"])
            except TMDbNotFound:
                keep.append(c)
                continue
            num_seasons = details.get("number_of_seasons") or 0
            # Exclude season 0 (specials)
            real_seasons = [s for s in (details.get("seasons") or []) if s.get("season_number", 0) > 0]
            real_count = len(real_seasons) if real_seasons else num_seasons
            if real_count >= want_season:
                # Record which season number this candidate has at the right slot
                c["comp_season_number"] = want_season
                keep.append(c)
            else:
                drop.append({**c, "drop_reason": f"only {real_count} seasons, need season {want_season}"})
                self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "season",
                                             "drop", f"has {real_count} seasons, need {want_season}"))
        return keep, drop

    def _filter_box_office(self, cs: list[dict], intake: dict) -> tuple[list[dict], list[dict]]:
        rng = intake.get("box_office_range_m") or {}
        lo, hi = rng.get("min"), rng.get("max")
        if lo is None or hi is None:
            return cs, []
        keep: list[dict] = []
        drop: list[dict] = []
        for c in cs:
            imdb = _safe_imdb_id(self.tmdb, "movie", c["tmdb_id"])
            ow: Optional[float] = None
            if imdb:
                try:
                    ow = self.bom.opening_weekend(imdb)
                except (BOMScrapeError, Exception) as e:
                    self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "bom_scrape",
                                                 "tag", f"BO unverified (scrape error: {e})"))
            c["opening_weekend_m"] = ow
            if ow is None:
                c.setdefault("flags", []).append("BO unverified")
                keep.append(c)
                self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "box_office",
                                             "tag", "BO unverified, kept"))
                continue
            if lo <= ow <= hi:
                keep.append(c)
                self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "box_office",
                                             "keep", f"${ow:.1f}M in range [{lo},{hi}]"))
            else:
                drop.append({**c, "drop_reason": f"OW ${ow:.1f}M outside [${lo},${hi}]M"})
                self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "box_office",
                                             "drop", f"${ow:.1f}M outside [{lo},{hi}]"))
        return keep, drop

    def _filter_streaming_platform(self, cs: list[dict], intake: dict) -> tuple[list[dict], list[dict]]:
        keep: list[dict] = []
        drop: list[dict] = []
        for c in cs:
            providers = self.tmdb.get_watch_providers(c["media_type"], c["tmdb_id"])
            flatrate = providers.get("flatrate", []) or []
            ids = {p.get("provider_id") for p in flatrate if p.get("provider_id") is not None}
            approved = ids & APPROVED_PROVIDER_IDS
            if approved:
                # pick a display label for the first approved provider id we recognize
                pick = next((pid for pid in ids if pid in PROVIDER_DISPLAY), None)
                c["distributor"] = PROVIDER_DISPLAY.get(pick, "Prime Video")
                keep.append(c)
                self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "streaming_platform",
                                             "keep", f"approved providers: {sorted(approved)}"))
                continue

            # Check linear networks via /tv/{id}.networks
            if c["media_type"] == "tv":
                try:
                    tv = self.tmdb.get_tv(c["tmdb_id"])
                except TMDbNotFound:
                    tv = {}
                networks = [n.get("name") for n in tv.get("networks", []) if n.get("name")]
                hit = next((n for n in networks if n in LINEAR_NETWORKS), None)
                if hit:
                    c["distributor"] = hit
                    c.setdefault("flags", []).append("linear/network outlier")
                    keep.append(c)
                    self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "streaming_platform",
                                                 "tag", f"linear outlier: {hit}"))
                    continue

            drop.append({**c, "drop_reason": "not on approved streaming platform"})
            self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "streaming_platform",
                                         "drop", "no approved providers, no linear network"))
        return keep, drop

    def _filter_time_window(self, cs: list[dict]) -> tuple[list[dict], list[dict]]:
        today = date.today()
        keep: list[dict] = []
        drop: list[dict] = []
        for c in cs:
            yr = c.get("year")
            if not yr:
                # missing release year — keep but flag
                c.setdefault("flags", []).append("release year unknown")
                keep.append(c)
                continue
            age = today.year - yr
            is_p1 = "P1" in (c.get("pools") or [])
            if age <= 3:
                keep.append(c)
            elif age <= 5:
                c.setdefault("flags", []).append("exceeds ideal range (3-5y)")
                keep.append(c)
                self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "time_window",
                                             "tag", f"{age}y old"))
            else:
                if is_p1:
                    c.setdefault("flags", []).append(f"legacy director match, {age}y old")
                    keep.append(c)
                    self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "time_window",
                                                 "tag", f"P1 override, {age}y old"))
                else:
                    drop.append({**c, "drop_reason": f"{age}y old, not P1"})
                    self.audit.append(AuditEntry(c["tmdb_id"], c["title"], "time_window",
                                                 "drop", f"{age}y old"))
        return keep, drop

    def _tag_ip_status(self, cs: list[dict], intake: dict) -> None:
        wanted = intake.get("ip_type") or "other"
        preferred = IP_KEYWORDS_BY_TYPE.get(wanted, ALL_IP_KEYWORDS)
        for c in cs:
            try:
                kw_resp = self.tmdb.get_keywords(c["media_type"], c["tmdb_id"])
            except TMDbNotFound:
                kw_resp = {}
            # /movie returns 'keywords'; /tv returns 'results'
            kws = kw_resp.get("keywords") or kw_resp.get("results") or []
            kw_ids = {k.get("id") for k in kws if k.get("id") is not None}
            if kw_ids & preferred:
                c["ip_match"] = "exact"
            elif kw_ids & ALL_IP_KEYWORDS:
                c["ip_match"] = "any"
            else:
                c["ip_match"] = "none"
                c.setdefault("flags", []).append("non-IP")

    def _tag_priority_tier(self, cs: list[dict]) -> None:
        for c in cs:
            pools = set(c.get("pools") or [])
            if "P1" in pools:
                c["priority_tier"] = "P1"
            elif "P2" in pools:
                c["priority_tier"] = "P2"
            else:
                c["priority_tier"] = "P3"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_imdb_id(tmdb: TMDbClient, media_type: str, tmdb_id: int) -> Optional[str]:
    try:
        ext = tmdb.get_external_ids(media_type, tmdb_id)
    except TMDbNotFound:
        return None
    return ext.get("imdb_id") or None


def _infer_installment(tmdb: TMDbClient, collection_id: int, tmdb_id: int) -> Optional[int]:
    """Return the 1-indexed position of `tmdb_id` within its collection, by
    release date. Returns None if the collection isn't loadable.
    """
    try:
        # /collection/{id} isn't on TMDbClient directly; do a one-off get
        coll = tmdb._get(f"/collection/{collection_id}")  # type: ignore[attr-defined]
    except Exception:
        return None
    parts = coll.get("parts", []) or []
    # sort by release_date ascending; missing date sorts last
    parts = sorted(parts, key=lambda p: (p.get("release_date") or "9999-12-31"))
    for i, p in enumerate(parts, start=1):
        if p.get("id") == tmdb_id:
            return i
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> int:
    p = argparse.ArgumentParser(prog="rule_engine")
    p.add_argument("--in", dest="in_path", required=True, help="candidate_generator output JSON")
    p.add_argument("--intake", required=True, help="intake JSON")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    with open(args.in_path, "r", encoding="utf-8") as f:
        gen = json.load(f)
    with open(args.intake, "r", encoding="utf-8") as f:
        intake = json.load(f)

    candidates = gen.get("merged") or []
    tmdb = TMDbClient()
    bom = BoxOfficeMojoScraper()
    try:
        eng = RuleEngine(tmdb=tmdb, bom=bom)
        kept, dropped, audit = eng.apply(candidates, intake)
    finally:
        tmdb.close()
        bom.close()

    out = {
        "kept": kept,
        "dropped": dropped,
        "audit": audit,
        "counts": {"in": len(candidates), "kept": len(kept), "dropped": len(dropped)},
    }
    payload = json.dumps(out, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(payload)
        print(f"wrote {args.out} — kept {len(kept)} / {len(candidates)}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
