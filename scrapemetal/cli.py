"""Command line entry point: scrape once, or serve the page while re-scraping periodically."""

from __future__ import annotations

import argparse
import functools
import json
import logging
import os
import threading
from datetime import date, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .dedupe import deduplicate
from .models import Concert, Event
from .render import render
from .sources import SOURCES, new_session
from .tickets import resolve_ticket_urls
from .venues import VenueDirectory

log = logging.getLogger("scrapemetal")


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _load_cached(data_dir: Path, name: str) -> tuple[list[Event], str | None]:
    cache = data_dir / f"{name}.json"
    if not cache.exists():
        return [], None
    cached = json.loads(cache.read_text(encoding="utf-8"))
    return [Event.from_json(e) for e in cached["events"]], cached["scraped_at"]


def load_cached_events(data_dir: Path) -> list[Event]:
    """Events from the last successful scrape of each source, with resolved ticket links."""
    events = [e for name in SOURCES for e in _load_cached(data_dir, name)[0]]
    cache = data_dir / "tickets.json"
    tickets = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    for e in events:
        e.ticket_url = tickets.get(e.ticket_url, e.ticket_url)
    return events


def build_concerts(events: list[Event], venues_path: Path) -> list[Concert]:
    today = date.today()
    concerts = [c for c in deduplicate(events) if (c.end_date or c.date) >= today]
    VenueDirectory.load(venues_path).apply(concerts)
    return concerts


def write_output(concerts: list[Concert], status: dict[str, dict], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_atomic(out_dir / "index.html", render(concerts, status, datetime.now()))
    _write_atomic(out_dir / "concerts.json", json.dumps([
        {
            "date": c.date.isoformat(),
            "end_date": c.end_date.isoformat() if c.end_date else None,
            "time": c.time,
            "band": c.band,
            "lineup": c.lineup,
            "venue": c.venue,
            "venue_url": c.venue_url,
            "city": c.city,
            "links": c.links,
            "tickets": c.ticket_url,
            "event_page": c.event_url,
        } for c in concerts
    ], indent=1, ensure_ascii=False))


def run_once(data_dir: Path, out_dir: Path, venues_path: Path) -> None:
    """Scrape all sources, deduplicate and write index.html + concerts.json.

    If a source fails, its most recent successful result is reused so the page never loses data
    because of a temporary outage.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    session = new_session()
    events: list[Event] = []
    status: dict[str, dict] = {}

    for name, scrape in SOURCES.items():
        cache = data_dir / f"{name}.json"
        try:
            found = scrape(session)
            if not found:
                raise RuntimeError("no events found; page layout may have changed")
            _write_atomic(cache, json.dumps({
                "scraped_at": datetime.now().isoformat(timespec="seconds"),
                "events": [e.to_json() for e in found],
            }, indent=1, ensure_ascii=False))
            status[name] = {"ok": True, "count": len(found)}
        except Exception as exc:
            log.exception("Scraping %s failed", name)
            found, scraped_at = _load_cached(data_dir, name)
            if found:
                log.warning("Using %d cached %s events from %s", len(found), name, scraped_at)
            status[name] = {"ok": False, "count": len(found), "error": str(exc)}
        events.extend(found)

    try:
        resolve_ticket_urls(session, events, data_dir / "tickets.json")
    except Exception:
        log.exception("Resolving ticket links failed; using podiuminfo ticket redirects")

    concerts = build_concerts(events, venues_path)
    log.info("%d listings -> %d unique concerts", len(events), len(concerts))
    write_output(concerts, status, out_dir)


def _scrape_loop(data_dir: Path, out_dir: Path, venues_path: Path, interval: float, stop: threading.Event) -> None:
    while True:
        try:
            run_once(data_dir, out_dir, venues_path)
        except Exception:
            log.exception("Scrape run failed")
        if stop.wait(interval):
            return


def serve(data_dir: Path, out_dir: Path, venues_path: Path, host: str, port: int, interval_hours: float) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    if not (out_dir / "index.html").exists():
        run_once(data_dir, out_dir, venues_path)  # make sure there is something to serve right away
        first_delay_done = True
    else:
        first_delay_done = False

    stop = threading.Event()
    interval = interval_hours * 3600

    def loop():
        if first_delay_done and stop.wait(interval):
            return
        _scrape_loop(data_dir, out_dir, venues_path, interval, stop)

    threading.Thread(target=loop, daemon=True, name="scraper").start()

    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(out_dir))
    server = ThreadingHTTPServer((host, port), handler)
    log.info("Serving %s on http://%s:%d/ (re-scraping every %g h)", out_dir, host, port, interval_hours)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        server.server_close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="scrapemetal", description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="where raw per-source results are cached")
    parser.add_argument("--out-dir", type=Path, default=Path("public"), help="where index.html is written")
    parser.add_argument("--venues", type=Path, default=Path("venues.toml"), help="venue website list (default: venues.toml)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scrape", help="scrape once and write the page (e.g. from cron)")
    sub.add_parser("render", help="rebuild the page from cached data without scraping (e.g. after editing venues.toml)")
    sub.add_parser("venues", help="list venues from cached data that have no website in the venue list yet")
    p_serve = sub.add_parser("serve", help="serve the page and re-scrape periodically")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--interval", type=float, default=6, help="hours between scrapes (default: 6)")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    if args.command == "scrape":
        run_once(args.data_dir, args.out_dir, args.venues)
    elif args.command == "render":
        concerts = build_concerts(load_cached_events(args.data_dir), args.venues)
        status = {name: {"ok": True, "count": len(_load_cached(args.data_dir, name)[0])} for name in SOURCES}
        write_output(concerts, status, args.out_dir)
        log.info("Rendered %d concerts from cached data", len(concerts))
    elif args.command == "venues":
        concerts = build_concerts(load_cached_events(args.data_dir), args.venues)
        missing = VenueDirectory.load(args.venues).missing(concerts)
        print(f"{len(missing)} venues without a website ({sum(n for *_, n in missing)} of {len(concerts)} concerts):")
        for venue, city, n in missing:
            print(f"{n:4}  {venue} ({city or 'unknown city'})")
    else:
        serve(args.data_dir, args.out_dir, args.venues, args.host, args.port, args.interval)


if __name__ == "__main__":
    main()
