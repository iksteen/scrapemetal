import json

from scrapemetal.models import Event
from scrapemetal.tickets import clean_url, resolve_ticket_urls, unwrap


class FakeResponse:
    def __init__(self, status, location=None):
        self.status_code = status
        self.headers = {"Location": location} if location else {}
        self.is_redirect = location is not None and status in (301, 302, 303, 307, 308)

    def close(self):
        pass


class FakeSession:
    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, **kw):
        self.calls.append(url)
        return self.routes[url]


def test_unwrap_and_clean():
    tm = "https://ticketmaster.evyy.net/c/1/2/3?u=https%3A%2F%2Fwww.ticketmaster.nl%2Fevent%2Fx%2F1&utm_medium=affiliate"
    assert unwrap(tm) == "https://www.ticketmaster.nl/event/x/1"
    assert unwrap("https://www.doornroosje.nl/event/myrath/") is None
    assert clean_url("https://a.stager.co/shop/events/1?utm_campaign=x&utm_source=Podiuminfo&id=5") == "https://a.stager.co/shop/events/1?id=5"


def test_resolve_ticket_urls(tmp_path):
    a, b, d, c = (f"https://www.podiuminfo.nl/ticket/{i}/ca/x/" for i in (1, 2, 3, 4))  # c (rate limited) sorts last
    session = FakeSession({
        a: FakeResponse(301, "https://ticketmaster.evyy.net/c/1?u=https%3A%2F%2Fwww.ticketmaster.nl%2Fevent%2F1"),
        b: FakeResponse(301, "https://venue.stager.co/shop/events/2?utm_source=Podiuminfo"),
        d: FakeResponse(301, "https://www.podiuminfo.nl/concert/4/x/?err=old_ticket"),
        "https://www.podiuminfo.nl/concert/4/x/?err=old_ticket": FakeResponse(200),
        c: FakeResponse(429),
    })
    events = [Event("podiuminfo", None, "x", "v", "c", "u", ticket_url=u) for u in (a, b, d, c)]
    cache = tmp_path / "tickets.json"
    resolve_ticket_urls(session, events, cache, delay=0)
    assert [e.ticket_url for e in events] == [
        "https://www.ticketmaster.nl/event/1",
        "https://venue.stager.co/shop/events/2",
        None,  # expired: redirects back to podiuminfo
        c,  # rate limited: keeps the working podiuminfo redirect, retried next run
    ]
    assert set(json.loads(cache.read_text())) == {a, b, d}

    # Second run only requests the unresolved link.
    session.calls.clear()
    session.routes[c] = FakeResponse(302, "https://www.doornroosje.nl/event/x/")
    events = [Event("podiuminfo", None, "x", "v", "c", "u", ticket_url=u) for u in (a, b, d, c)]
    resolve_ticket_urls(session, events, cache, delay=0)
    assert session.calls == [c]
    assert events[3].ticket_url == "https://www.doornroosje.nl/event/x/"
