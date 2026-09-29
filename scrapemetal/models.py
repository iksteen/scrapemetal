from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
    time: str | None = None
    lineup: str | None = None
    ticket_url: str | None = None
    event_url: str | None = None  # the event page on the venue's own website

    @property
    def last_date(self) -> date:
        return self.end_date or self.date

    def to_json(self) -> dict:
        d = asdict(self)
        d["date"] = self.date.isoformat()
        d["end_date"] = self.end_date.isoformat() if self.end_date else None
        return d

    @classmethod
    def from_json(cls, d: dict) -> Event:
        d = dict(d)
        d["date"] = date.fromisoformat(d["date"])
        d["end_date"] = date.fromisoformat(d["end_date"]) if d.get("end_date") else None
        return cls(**d)


@dataclass
class Concert:
    """A deduplicated concert, possibly backed by listings from several sources."""

    date: date
    band: str
    venue: str
    city: str
    end_date: date | None = None
    time: str | None = None
    lineup: str | None = None
    ticket_url: str | None = None
    event_url: str | None = None
    venue_url: str | None = None
    links: dict[str, str] = field(default_factory=dict)
