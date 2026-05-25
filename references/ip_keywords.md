# IP Keywords

TMDb keyword IDs we use to determine whether a title is based on pre-existing IP. Sourced from `/keyword/{id}` lookups on TMDb and stable as of 2026-05.

## How IP detection works

1. The rule engine calls `tmdb_client.get_keywords(media_type, id)`.
2. Compares each keyword ID against the lists below.
3. If any match → tag the candidate as `ip_based: true` with the matching `ip_type`.
4. The ranker uses this tag to bias toward/against IP candidates depending on the input title's IP status (see `rules.md` rule 13).

## Keyword IDs

### Based on novel / book

| TMDb keyword ID | Name |
|---|---|
| 818 | based on novel or book |
| 9663 | sequel |
| 10661 | based on young adult novel |
| 173272 | based on memoir or autobiography |
| 161176 | based on short story |
| 207263 | based on non-fiction book |

### Based on comic / graphic novel

| TMDb keyword ID | Name |
|---|---|
| 9717 | based on comic book |
| 254835 | based on graphic novel |
| 9714 | based on comic |
| 282085 | based on manga |
| 207928 | based on dc comics |
| 180547 | based on marvel comic |

### Based on video game

| TMDb keyword ID | Name |
|---|---|
| 282 | video game |
| 233824 | based on video game |
| 240073 | based on mobile game |

### Based on true story / real events

| TMDb keyword ID | Name |
|---|---|
| 9672 | based on true story |
| 211733 | based on real events |
| 207317 | based on real person |
| 207928 | dramatization of real events |

### Based on other IP (TV remake, play, podcast, etc.)

| TMDb keyword ID | Name |
|---|---|
| 167043 | based on tv series |
| 9849 | remake |
| 165824 | based on play |
| 270783 | based on podcast |
| 222243 | based on toy |
| 232614 | based on theme park ride |
| 207926 | based on web series |

## Mapping intake.ip_type → keyword lists

When the analyst answers intake question 2a (IP type), the ranker prefers candidates whose keyword IDs intersect the corresponding list above:

| intake.ip_type | preferred keyword IDs |
|---|---|
| `novel` | based-on-novel list |
| `comic` | based-on-comic list |
| `video game` | based-on-video-game list |
| `true story` | based-on-true-story list |
| `other` | union of all IP lists |

A candidate that matches the intake's specific IP type is preferred over a candidate that matches any IP type, which is preferred over a non-IP candidate.

## Maintenance

TMDb occasionally renumbers keywords (rare but it happens). Spot-check this file quarterly:

```bash
# Pick any keyword ID from the table above
python -m scripts.tmdb_client get-keyword 818
# Should return: {"id": 818, "name": "based on novel or book"}
```

If a lookup returns a different name or 404, update the table. The rule engine reads keyword IDs only — never the human names — so a renamed keyword doesn't matter, but a renumbered one does.
