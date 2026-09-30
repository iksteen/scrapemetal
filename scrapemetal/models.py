from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import date


@dataclass
class Event:
    """A single concert listing as scraped from one source."""

    source: str
    date: date
    band: str
    venue: str
    city: str
    url: str
    end_date: date | None = None
    lineup: str | None = None
    ticket_url: str | None = None
    event_url: str | None = None  # the event page on the venue's own website
    uid: str | None = None  # the source's own id for the listing, if it has one
    added: date | None = None  # first seen; None if it predates tracking (see added.py)

    @property
    def last_date(self) -> date:
        return self.end_date or self.date

    def to_json(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        d["end_date"] = self.end_date.isoformat() if self.end_date else None
        d["added"] = self.added.isoformat() if self.added else None
        return d

    @classmethod
    def from_json(cls, d: dict) -> Event:
        # Ignore fields that older caches have but the model no longer does.
        d = {k: v for k, v in d.items() if k in {f.name for f in fields(cls)}}
        d["date"] = date.fromisoformat(d["date"])
        d["end_date"] = date.fromisoformat(d["end_date"]) if d.get("end_date") else None
        d["added"] = date.fromisoformat(d["added"]) if d.get("added") else None
        return cls(**d)


@dataclass
class Concert:
    """A deduplicated concert, possibly backed by listings from several sources."""

    date: date
    band: str
    venue: str
    city: str
    end_date: date | None = None
    lineup: str | None = None
    ticket_url: str | None = None
    event_url: str | None = None
    added: date | None = None
    venue_url: str | None = None
    venue_aliases: list[str] = field(default_factory=list)  # other spellings, for search
    links: dict[str, str] = field(default_factory=dict)
