"""Link venues to their websites using the hand-maintained venues.toml."""

from __future__ import annotations

import logging
import re
import tomllib
from collections import Counter
from pathlib import Path

from .dedupe import city_key, normalize
from .models import Concert

log = logging.getLogger(__name__)

# Words that the agenda sites add or leave out inconsistently.
_IGNORED_WORDS_RE = re.compile(r"\b(?:poppodium)\b")
_LEADING_ARTICLE_RE = re.compile(r"^(?:de|het|the|t)\s+")


def venue_key(name: str) -> str:
    key = _IGNORED_WORDS_RE.sub(" ", normalize(name))
    key = re.sub(r"\s+", " ", key).strip()
    return _LEADING_ARTICLE_RE.sub("", key)


class VenueDirectory:
    def __init__(self, entries: list[dict]):
        self.by_place: dict[tuple[str, str], str] = {}
        self.by_name: dict[str, set[str]] = {}
        for entry in entries:
            for name in [entry["name"], *entry.get("aliases", [])]:
                key = venue_key(name)
                self.by_place[(key, city_key(entry.get("city", "")))] = entry["url"]
                self.by_name.setdefault(key, set()).add(entry["url"])

    @classmethod
    def load(cls, path: Path) -> VenueDirectory:
        if not path.exists():
            return cls([])
        with path.open("rb") as f:
            data = tomllib.load(f)
        for key in data.keys() - {"venue"}:
            log.warning("%s: ignoring unknown section %r (did you mean [[venue]]?)", path, key)
        entries = []
        for i, entry in enumerate(data.get("venue", []), 1):
            if not entry.get("name") or not entry.get("url"):
                log.warning("%s: venue #%d (%s) needs both name and url; ignored", path, i, entry.get("name", "?"))
                continue
            entries.append(entry)
        return cls(entries)

    def lookup(self, venue: str, city: str) -> str | None:
        key = venue_key(venue)
        if url := self.by_place.get((key, city_key(city))):
            return url
        if not city_key(city):
            # City unknown: only use the name if it identifies a single venue.
            urls = self.by_name.get(key, set())
            if len(urls) == 1:
                return next(iter(urls))
        return None

    def apply(self, concerts: list[Concert]) -> None:
        for c in concerts:
            c.venue_url = self.lookup(c.venue, c.city)
            if not c.venue_url and not city_key(c.city) and venue_key(c.venue) not in self.by_name:
                # A lone location that isn't a known venue ("Brussel", "Wacken (Duitsland)") is a city.
                c.venue, c.city = "", c.venue

    def missing(self, concerts: list[Concert]) -> list[tuple[str, str, int]]:
        """Venues without a URL as (venue, city, number of concerts), most frequent first."""
        counts: Counter[tuple[str, str]] = Counter()
        labels: dict[tuple[str, str], tuple[str, str]] = {}
        for c in concerts:
            if c.venue and not self.lookup(c.venue, c.city):
                key = (venue_key(c.venue), city_key(c.city))
                counts[key] += 1
                labels.setdefault(key, (c.venue, c.city))
        return [(*labels[key], n) for key, n in counts.most_common()]
