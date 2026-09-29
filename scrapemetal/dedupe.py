"""Merge listings from multiple sources that describe the same concert.

Two listings are considered the same concert when their dates overlap, they are in the
same place (same city, or the same venue when a city is missing) and at least one band
name from one listing occurs in the other listing (allowing for small typos).
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

from .models import Concert, Event

# Preferred source per field when merging; the first source that has a value wins.
BAND_PREFERENCE = ["metalfan", "podiuminfo", "metalagenda"]  # metalfan lists full line-ups
PLACE_PREFERENCE = ["podiuminfo", "metalagenda", "metalfan"]  # metalfan often lacks a separate city

CITY_ALIASES = {
    "s hertogenbosch": "den bosch",
    "hertogenbosch": "den bosch",
    "the hague": "den haag",
    "s gravenhage": "den haag",
    "cologne": "keulen",
    "koln": "keulen",
    "rottterdam": "rotterdam",
    "sittard geleen": "sittard",  # the municipality; Volt is in Sittard
    "de westereen": "zwaagwesteinde",  # Frisian name
}

DASHES = "-‐‑‒–—―−"  # hyphen-minus, hyphens, figure/en/em dashes, horizontal bar, minus

ARTIST_SPLIT_RE = re.compile(rf"\s*(?:,|\+|&|/|\s[{DASHES}]\s|:|\b[eé]n\b|\band\b|\bw/|\bwith\b|\bguests?\b|\bsupport\b)\s*", re.I)
NOISE_WORDS = {"the", "tour", "live", "support", "guests", "special", "and", "en", "met", "tba"}

_TRANSLITERATE = str.maketrans({"æ": "ae", "ø": "o", "ß": "ss", "œ": "oe", "đ": "d", "ł": "l"})


def normalize(text: str) -> str:
    text = text.lower().translate(_TRANSLITERATE)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def city_key(city: str) -> str:
    key = normalize(re.sub(r"\(.*?\)", "", city))
    # "Capelle aan den IJssel" is also written "Capelle a/d IJssel" or "Capelle ad IJssel".
    key = re.sub(r"\b(?:a d|ad|aan de|aan den|aan het)\b", "aan", key)
    return CITY_ALIASES.get(key, key)


def artists(event: Event) -> set[str]:
    raw = event.band + (", " + event.lineup if event.lineup else "")
    names = {normalize(part) for part in ARTIST_SPLIT_RE.split(raw)}
    return {n for n in names if len(n) >= 3 and n not in NOISE_WORDS}


def full_text(event: Event) -> str:
    return f" {normalize(event.band + ' ' + (event.lineup or ''))} "


def same_place(a: Event, b: Event) -> bool:
    city_a, city_b = city_key(a.city), city_key(b.city)
    if city_a and city_b:
        return city_a == city_b
    # One listing lacks a city, so its single location string is either a venue or a city.
    venue_a, venue_b = normalize(a.venue), normalize(b.venue)
    if venue_a and venue_b and (venue_a in venue_b or venue_b in venue_a):
        return True
    return (not city_a and city_key(a.venue) == city_b) or (not city_b and city_key(b.venue) == city_a)


def similar_artists(a: Event, b: Event) -> bool:
    text_a, text_b = full_text(a), full_text(b)
    names_a, names_b = artists(a), artists(b)
    if any(f" {n} " in text_b for n in names_a) or any(f" {n} " in text_a for n in names_b):
        return True
    # Tolerate typos such as "Enter Shakiri" vs "Enter Shikari".
    return any(
        SequenceMatcher(None, x, y).ratio() >= 0.8
        for x in names_a if len(x) >= 5
        for y in names_b if len(y) >= 5
    )


def same_concert(a: Event, b: Event) -> bool:
    if a.date > b.last_date or b.date > a.last_date:
        return False
    if not same_place(a, b):
        return False
    if a.source == b.source:
        # Within one source only collapse exact duplicates.
        return normalize(a.band) == normalize(b.band) and normalize(a.venue) == normalize(b.venue)
    return similar_artists(a, b)


def _pick(events: list[Event], attr: str, preference: list[str]):
    ranked = sorted(events, key=lambda e: preference.index(e.source) if e.source in preference else len(preference))
    for e in ranked:
        if value := getattr(e, attr):
            return value
    return None


def merge(group: list[Event]) -> Concert:
    return Concert(
        date=min(e.date for e in group),
        end_date=max((e.end_date for e in group if e.end_date), default=None),
        band=_pick(group, "band", BAND_PREFERENCE),
        lineup=_pick(group, "lineup", BAND_PREFERENCE),
        ticket_url=_pick(group, "ticket_url", PLACE_PREFERENCE),
        event_url=_pick(group, "event_url", PLACE_PREFERENCE),
        # A listing without a date predates tracking, so the concert is not new.
        added=None if any(e.added is None for e in group) else min(e.added for e in group),
        venue=_pick(group, "venue", PLACE_PREFERENCE) or "",
        city=_pick(group, "city", PLACE_PREFERENCE) or "",
        links={e.source: e.url for e in sorted(group, key=lambda e: e.source)},
    )


def group_events(events: list[Event]) -> list[list[Event]]:
    """Group listings that refer to the same concert."""
    groups: list[list[Event]] = []
    for event in sorted(events, key=lambda e: (e.date, e.source)):
        for group in groups:
            # Only merge one listing per source into a group.
            if event.source not in {e.source for e in group} and any(same_concert(event, e) for e in group):
                group.append(event)
                break
            if any(e.source == event.source and same_concert(event, e) for e in group):
                break  # exact duplicate within the same source; drop it
        else:
            groups.append([event])
    return groups


def deduplicate(events: list[Event]) -> list[Concert]:
    concerts = [merge(g) for g in group_events(events)]
    concerts.sort(key=lambda c: (c.date, normalize(c.band)))
    return concerts
