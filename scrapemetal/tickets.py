"""Resolve podiuminfo's ticket redirect links to the actual ticket shop URLs.

podiuminfo links to ``/ticket/<id>/...`` which redirects (sometimes via an affiliate tracker) to
the ticket shop. Resolved URLs are cached, since podiuminfo rate-limits these requests; links that
cannot be resolved yet keep pointing at the (working) podiuminfo redirect and are retried next run.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests

from .models import Event
from .sources import TIMEOUT

log = logging.getLogger(__name__)

MAX_HOPS = 5
# Query parameters that affiliate trackers use to carry the destination URL.
WRAPPER_PARAMS = ("u", "url", "murl", "dest", "destination")


def clean_url(url: str) -> str:
    """Strip tracking parameters."""
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if not k.lower().startswith("utm_")]
    return urlunsplit(parts._replace(query=urlencode(query)))


def unwrap(url: str) -> str | None:
    """Return the destination URL embedded in an affiliate/tracking URL, if any."""
    for key, value in parse_qsl(urlsplit(url).query):
        if key.lower() in WRAPPER_PARAMS and value.startswith(("http://", "https://")):
            return value
    return None


class RateLimited(Exception):
    pass


def resolve(session: requests.Session, url: str) -> str | None:
    """Follow redirects until leaving podiuminfo, unwrapping affiliate links on the way.

    Returns None when the link does not lead to a ticket shop (e.g. an expired ticket link that
    redirects back to the podiuminfo concert page).
    """
    for _ in range(MAX_HOPS):
        resp = session.get(url, allow_redirects=False, timeout=TIMEOUT, stream=True)
        resp.close()
        if resp.status_code == 429:
            raise RateLimited(url)
        location = resp.headers.get("Location")
        if not resp.is_redirect or not location:
            break
        url = urljoin(url, location)
        if inner := unwrap(url):
            url = inner
            break
        if not _is_podiuminfo(url):
            break
    return None if _is_podiuminfo(url) else clean_url(url)


def _is_podiuminfo(url: str) -> bool:
    return (urlsplit(url).hostname or "").endswith("podiuminfo.nl")


def resolve_ticket_urls(session: requests.Session, events: list[Event], cache_path: Path, delay: float = 1.5) -> None:
    """Replace podiuminfo ticket redirect URLs on ``events`` with direct ticket shop URLs, in place."""
    cache: dict[str, str | None] = {}
    if cache_path.exists():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))

    wanted = {e.ticket_url for e in events if e.ticket_url}
    todo = sorted(u for u in wanted if u not in cache)
    if todo:
        log.info("tickets: resolving %d new ticket links (%d cached)", len(todo), len(wanted) - len(todo))
    for i, url in enumerate(todo):
        if i:
            time.sleep(delay)
        try:
            cache[url] = resolve(session, url)
        except RateLimited:
            log.warning("tickets: rate limited; %d links left for the next run", len(todo) - i)
            break
        except requests.RequestException as exc:
            log.warning("tickets: could not resolve %s: %s", url, exc)

    # Forget links that are no longer listed so the cache does not grow forever.
    cache = {k: v for k, v in cache.items() if k in wanted}
    tmp = cache_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, cache_path)

    for e in events:
        if e.ticket_url in cache:
            e.ticket_url = cache[e.ticket_url]
