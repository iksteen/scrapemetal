"""Remember when each listing was first seen, for the "added this week" filter.

The per-source caches in ``data/`` only hold what a site lists right now, so a listing that is
removed (cancelled, moved) disappears from the page. This ledger outlives them: a listing that
drops out of one scrape and comes back later keeps its original first-seen date. Listings that
were already there when a source was first tracked get no date, so they never count as new.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path

from .dedupe import normalize
from .models import Event


def listing_key(e: Event) -> str:
    # metalfan has no ids; a changed title or venue there counts as a new listing.
    return e.uid or f"{e.date.isoformat()}|{normalize(e.band)}|{normalize(e.venue)}"


def _load(path: Path) -> dict[str, dict[str, dict]]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _apply(events: list[Event], ledger: dict[str, dict[str, dict]]) -> None:
    for e in events:
        entry = ledger.get(e.source, {}).get(listing_key(e))
        e.added = date.fromisoformat(entry["added"]) if entry and entry["added"] else None


def apply_first_seen(events: list[Event], path: Path) -> None:
    """Set ``added`` on ``events`` from the ledger without changing it."""
    _apply(events, _load(path))


def update_first_seen(events: list[Event], path: Path, today: date) -> None:
    """Record listings not seen before as added ``today``, then set ``added`` on ``events``."""
    ledger = _load(path)
    for source in {e.source for e in events}:
        baseline = source not in ledger
        seen = ledger.setdefault(source, {})
        for e in events:
            if e.source != source:
                continue
            entry = seen.setdefault(listing_key(e), {"added": None if baseline else today.isoformat()})
            entry["until"] = max(entry.get("until", ""), e.last_date.isoformat())
    # Forget listings once they are over so the ledger does not grow forever.
    for seen in ledger.values():
        for key in [k for k, v in seen.items() if v["until"] < today.isoformat()]:
            del seen[key]

    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(ledger, indent=1, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    _apply(events, ledger)
