from datetime import date

from scrapemetal.added import apply_first_seen, update_first_seen
from scrapemetal.dedupe import deduplicate
from scrapemetal.models import Event


def ev(source, d, band, uid=None, venue="Baroeg"):
    return Event(source=source, date=d, band=band, venue=venue, city="Rotterdam", url=f"https://{source}/", uid=uid)


def test_first_seen(tmp_path):
    path = tmp_path / "first_seen.json"
    # Listings present when a source is first tracked predate tracking.
    first = [ev("podiuminfo", date(2026, 11, 1), "Integrity", "podiuminfo:1")]
    update_first_seen(first, path, date(2026, 10, 1))
    assert first[0].added is None

    # New listings get today's date; a changed title with the same id is not new.
    second = [
        ev("podiuminfo", date(2026, 11, 1), "Integrity + Ringworm", "podiuminfo:1"),
        ev("podiuminfo", date(2026, 11, 2), "Coroner", "podiuminfo:2"),
        ev("metalfan", date(2026, 11, 2), "Coroner"),  # first metalfan run: baseline
    ]
    update_first_seen(second, path, date(2026, 10, 2))
    assert [e.added for e in second] == [None, date(2026, 10, 2), None]

    # A listing missing from one scrape keeps its date when it comes back.
    update_first_seen([], path, date(2026, 10, 3))
    third = [ev("podiuminfo", date(2026, 11, 2), "Coroner", "podiuminfo:2"), ev("metalfan", date(2026, 11, 3), "Myrath")]
    update_first_seen(third, path, date(2026, 10, 4))
    assert [e.added for e in third] == [date(2026, 10, 2), date(2026, 10, 4)]

    # Reading does not record anything; unknown listings have no date.
    cached = [ev("podiuminfo", date(2026, 11, 2), "Coroner", "podiuminfo:2"), ev("podiuminfo", date(2026, 12, 1), "X", "podiuminfo:9")]
    apply_first_seen(cached, path)
    assert [e.added for e in cached] == [date(2026, 10, 2), None]

    # Listings are forgotten once they are over.
    update_first_seen([], path, date(2026, 11, 3))
    assert '"podiuminfo:1"' not in path.read_text() and '"podiuminfo:2"' not in path.read_text()


def test_concert_added_is_earliest_listing():
    a, b = ev("metalfan", date(2026, 11, 2), "Coroner"), ev("podiuminfo", date(2026, 11, 2), "Coroner")
    a.added, b.added = date(2026, 10, 5), date(2026, 10, 2)
    assert deduplicate([a, b])[0].added == date(2026, 10, 2)
    b.added = None  # predates tracking, so the concert is not new
    assert deduplicate([a, b])[0].added is None
