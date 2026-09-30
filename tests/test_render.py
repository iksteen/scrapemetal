from datetime import date

from scrapemetal.models import Concert
from scrapemetal.render import _band_url


def concert(**kw):
    return Concert(date=date(2026, 10, 12), band="Integrity", venue="Baroeg", city="Rotterdam", **kw)


def test_band_url_prefers_event_page_then_tickets():
    assert _band_url(concert(event_url="https://baroeg.nl/x", ticket_url="https://tix/x")) == "https://baroeg.nl/x"
    assert _band_url(concert(ticket_url="https://tix/x")) == "https://tix/x"


def test_band_url_falls_back_to_search():
    assert _band_url(concert()) == "https://www.google.com/search?q=Baroeg+Rotterdam+Integrity+12+oktober+2026"
    city_only = Concert(date=date(2026, 11, 1), band="Hellfest", venue="", city="Brussel")
    assert _band_url(city_only) == "https://www.google.com/search?q=Brussel+Hellfest+1+november+2026"
