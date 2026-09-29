"""Scrapers for the individual agenda sites."""

from __future__ import annotations

import logging
import re
import time
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .models import Event

log = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (compatible; scrapemetal/0.1; personal metal agenda)"
TIMEOUT = 30

METALFAN_URL = "https://www.metalfan.nl/agenda.php"
PODIUMINFO_URL = "https://www.podiuminfo.nl/concertagenda/genre/metal/?input_event_type=1&input_country=58"
METALAGENDA_URL = "https://www.metalagenda.nl/"
METALAGENDA_AJAX_URL = "https://www.metalagenda.nl/ajax.php"

MONTHS = {
    "jan": 1, "feb": 2, "mrt": 3, "maa": 3, "apr": 4, "mei": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


def month_number(name: str) -> int:
    return MONTHS[name.strip(". ").lower()[:3]]


def fetch(session: requests.Session, url: str) -> str:
    resp = session.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text.lstrip("﻿")


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


# --- metalfan.nl -----------------------------------------------------------


def parse_metalfan_dates(text: str, year: int) -> tuple[date, date | None]:
    """Parse strings like '4 okt.', '9 & 10 okt.', '11 t/m 13 jun.' or '31 okt. & 1 nov.'."""
    parts = re.findall(r"(\d{1,2})(?:\s*([a-z]{3,}))?", text.lower())
    days: list[list] = [[int(d), m or None] for d, m in parts]
    # Days without a month take the month of the next day that has one.
    month = None
    for entry in reversed(days):
        if entry[1]:
            month = month_number(entry[1])
        entry[1] = month
    if not days or month is None:
        raise ValueError(f"Unparseable metalfan date: {text!r}")
    start = date(year, days[0][1], days[0][0])
    end = date(year, days[-1][1], days[-1][0])
    if end < start:  # spans the new year
        end = end.replace(year=year + 1)
    return start, (end if end != start else None)


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.split("\n") if ln.strip()]


def parse_metalfan_page(html: str, page_url: str) -> tuple[list[Event], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one(".pagetitle")
    m = re.search(r"(\d{4})", title.get_text() if title else "") or re.search(r"year=(\d{4})", page_url)
    if not m:
        raise ValueError("Cannot determine year of metalfan agenda page")
    year = int(m.group(1))
    base = page_url.split("#")[0]

    events = []
    for entry in soup.select("div.calentry"):
        caldate = entry.select_one(".caldate")
        calevent = entry.select_one(".calevent")
        band_el = calevent.select_one("font.event") if calevent else None
        if not (caldate and band_el):
            continue
        try:
            start, end = parse_metalfan_dates(caldate.get_text(" ", strip=True), year)
        except (ValueError, KeyError):
            log.warning("metalfan: skipping entry with date %r", caldate.get_text())
            continue
        # Festivals put their line-up either inside the band element or after the location:
        #   <font class="event">Fest<br>Met A, B</font><br>Venue, City
        #   <font class="event">Fest</font><br>Venue, City<br>Met A, B
        band_lines = _lines(band_el.get_text("\n"))
        after = "".join(s if isinstance(s, str) else s.get_text("\n") for s in band_el.next_siblings)
        after_lines = _lines(after)
        band = band_lines[0] if band_lines else ""
        location = after_lines[0] if after_lines else ""
        # No comma: the location is either just a venue or just a city; resolved later (see venues.py).
        venue, _, city = location.rpartition(", ")
        if not venue:
            venue, city = location, ""
        lineup = " ".join(band_lines[1:] + after_lines[1:]) or None
        if lineup:
            lineup = re.sub(r"^met\s+", "", lineup, flags=re.I)
        events.append(Event(
            source="metalfan",
            date=start,
            end_date=end,
            band=band,
            venue=venue.strip(),
            city=city.strip(),
            lineup=lineup,
            url=f"{base}#{start.isoformat()}",
        ))

    nxt = soup.select_one(".navnext a[href]")
    return events, urljoin(page_url, nxt["href"]) if nxt else None


def scrape_metalfan(session: requests.Session, max_pages: int = 3, delay: float = 1.0) -> list[Event]:
    events: list[Event] = []
    url: str | None = METALFAN_URL
    for _ in range(max_pages):
        if not url:
            break
        log.info("metalfan: fetching %s", url)
        page_events, url = parse_metalfan_page(fetch(session, url), url)
        events.extend(page_events)
        if not page_events:
            break
        time.sleep(delay)
    return events


# --- podiuminfo.nl ---------------------------------------------------------

PODIUMINFO_DATE_RE = re.compile(r",\s+[a-z]+\s+(\d{1,2})\s+([a-z]+)\s+(\d{4})")


def parse_podiuminfo_page(html: str) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    events = []
    # The page contains a desktop (n-mode) and a mobile (m-mode) copy of the agenda; only use desktop.
    for row in soup.select("section.n-mode section.concert_rows_info"):
        link = row.select_one(".td_2 a[href]")
        venue = row.select_one(".td_3")
        city = row.select_one(".td_4")
        if not (link and venue and city):
            continue
        m = PODIUMINFO_DATE_RE.search(link.get("aria-label", ""))
        if not m:
            log.warning("podiuminfo: no date in %r", link.get("aria-label"))
            continue
        day, month, year = m.groups()
        try:
            d = date(int(year), month_number(month), int(day))
        except (ValueError, KeyError):
            log.warning("podiuminfo: bad date in %r", link.get("aria-label"))
            continue
        events.append(Event(
            source="podiuminfo",
            date=d,
            band=link.get_text(" ", strip=True),
            venue=venue.get_text(" ", strip=True),
            city=city.get_text(" ", strip=True),
            url=link["href"],
            ticket_url=ticket["href"] if (ticket := row.select_one('.td_5 a[href*="/ticket/"]')) else None,
            uid=f"podiuminfo:{cid.group(1)}" if (cid := re.search(r"/concert/(\d+)/", link["href"])) else None,
        ))
    return events


def scrape_podiuminfo(session: requests.Session, max_pages: int = 30, delay: float = 1.0) -> list[Event]:
    events: list[Event] = []
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        url = PODIUMINFO_URL + (f"&page={page}" if page > 1 else "")
        log.info("podiuminfo: fetching %s", url)
        page_events = [e for e in parse_podiuminfo_page(fetch(session, url)) if e.url not in seen]
        if not page_events:
            break
        seen.update(e.url for e in page_events)
        events.extend(page_events)
        time.sleep(delay)
    return events


# --- metalagenda.nl --------------------------------------------------------

# Badges in the event title; cancelled events are skipped, the others are dropped from the title.
METALAGENDA_CANCELLED = {"cancelled", "geannuleerd", "afgelast"}
METALAGENDA_NO_BANDS = {"", "onbekend"}


def _band_case(name: str) -> str:
    """metalagenda lists bands in lowercase; capitalize words that have no capitals of their own."""
    return " ".join(w if w != w.lower() else w[:1].upper() + w[1:] for w in name.split())


def parse_metalagenda_page(html: str) -> list[Event]:
    soup = BeautifulSoup(html, "html.parser")
    events = []
    day: date | None = None
    for el in soup.select(".dateheader, .agendapunt"):
        if "dateheader" in el["class"]:
            try:
                day = date.fromisoformat(el.get("id", ""))
            except ValueError:
                log.warning("metalagenda: bad date header %r", el.get("id"))
                day = None
            continue
        title = el.select_one(".left h3")
        place = el.select(".left > a[href]")
        venue = next((a for a in place if a["href"].startswith("/venues/")), None)
        city = next((a for a in place if a["href"].startswith("/p/")), None)
        if not (day and title and venue and city):
            continue
        badges = {b.get_text(" ", strip=True).lower() for b in title.find_all(["div", "span"])}
        if badges & METALAGENDA_CANCELLED:
            continue
        for b in title.find_all(["div", "span"]):
            b.decompose()
        band = title.get_text(" ", strip=True)
        event_link = title.find_parent("a", href=True)
        event_url = event_link["href"] if event_link and event_link["href"].startswith(("http://", "https://")) else None
        ical = el.select_one('a[href^="/ical/"]')

        # "Bands: a | b | c" often names support acts that are missing from the title.
        lineup = None
        if (bands := el.select_one(".left > div")) and ":" in bands.get_text():
            names = [n.strip() for n in bands.get_text().split(":", 1)[1].split("|")]
            extra = [n for n in names if n not in METALAGENDA_NO_BANDS and n not in band.lower()]
            lineup = ", ".join(_band_case(n) for n in extra) or None

        events.append(Event(
            source="metalagenda",
            date=day,
            band=band,
            venue=venue.get_text(" ", strip=True),
            city=city.get_text(" ", strip=True),
            lineup=lineup,
            url=f"{METALAGENDA_URL}?datum={day.isoformat()}",
            event_url=event_url,
            uid=f"metalagenda:{ical['href'].rsplit('/', 1)[-1]}" if ical else None,
        ))
    return events


def scrape_metalagenda(session: requests.Session) -> list[Event]:
    # The agenda is loaded by the page's JavaScript; the endpoint rejects requests without a Referer.
    log.info("metalagenda: fetching %s", METALAGENDA_AJAX_URL)
    resp = session.post(
        METALAGENDA_AJAX_URL,
        data={"action": "load_agenda", "postcode": "", "kmrange": "0", "q": "", "zoekdatum": "",
              "favos": "false", "newadd": "false", "belgie": "false"},
        headers={"Referer": METALAGENDA_URL},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    resp.encoding = "utf-8"
    if "agendapunt" not in resp.text:
        raise RuntimeError(f"unexpected response: {resp.text[:100]!r}")
    return parse_metalagenda_page(resp.text)


SOURCES = {
    "metalfan": scrape_metalfan,
    "podiuminfo": scrape_podiuminfo,
    "metalagenda": scrape_metalagenda,
}
