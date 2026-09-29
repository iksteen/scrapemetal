from datetime import date

from scrapemetal.dedupe import deduplicate
from scrapemetal.models import Event
from scrapemetal.sources import parse_metalfan_dates, parse_metalfan_page, parse_podiuminfo_page

METALFAN_HTML = """
<div class="pagetitle">Concertagenda 2026</div>
<div class="calentry"><div class="caldate">30 sep.</div><div class="calevent"><a name="2026-09-30"></a><font class="event">Integrity, Ringworm en World I Hate</font><br>Baroeg, Rotterdam</div></div>
<div class="calentry"><div class="caldate">9 &amp; 10 okt.</div><div class="calevent"><font class="event">Soulcrusher</font><br>Doornroosje, Nijmegen</div></div>
<div class="calentry"><div class="caldate">10 okt.</div><div class="calevent"><font class="event">Metal Experience Fest</font><br>Nobel, Leiden<br>
Met Destruction, BEAST en Warfield</div></div>
<div class="calentry"><div class="caldate">17 okt.</div><div class="calevent"><font class="event">Spider Deathfest<br>
Met Rotten Remains en Anomic</font><br>Rockcafé, Balk</div></div>
<div class="calentry"><div class="caldate">31 okt.</div><div class="calevent"><font class="event">Marko Hietala</font><br>Osnabrück</div></div>
<div class="calentry"><div class="caldate">1 nov.</div><div class="calevent"><font class="event">Floor Jansen</font><br>Paradiso</div></div>
<div class="navnext"><a href="/agenda.php?year=2027&sw=">Volgende pagina:<br>2027</a></div>
"""

PODIUMINFO_HTML = """
<section class="twelvecol relative overflow n-mode">
  <section class="concert_rows_info clearfix">
    <div class="td_2 last"><strong><a href="https://www.podiuminfo.nl/concert/1/Integrity/Baroeg/"
      aria-label="Concert Integrity + Ringworm, woensdag 30 september 2026 om 20:00, Baroeg, Rotterdam, tickets beschikbaar">Integrity + Ringworm</a></strong></div>
    <div class="td_3 last">Baroeg</div><div class="td_4 last">Rotterdam</div>
    <div class="td_5 relative last"><figure><a href="https://www.podiuminfo.nl/ticket/99/ca/Integrity/" target="_blank"><span class="concert_ticket"></span></a></figure></div>
  </section>
  <section class="concert_rows_info clearfix">
    <div class="td_2 last"><strong><a href="https://www.podiuminfo.nl/concert/2/Coroner/Nobel/"
      aria-label="Concert Coroner, donderdag  1 oktober 2026, Nobel, Leiden">Coroner</a></strong></div>
    <div class="td_3 last">Nobel</div><div class="td_4 last">Leiden</div>
  </section>
</section>
<section class="twelvecol relative m-mode">
  <div class="concert_rows_info"><div class="td_2 last"><a href="https://www.podiuminfo.nl/concert/1/Integrity/Baroeg/"
    aria-label="Concert Integrity + Ringworm, woensdag 30 september 2026 om 20:00, Baroeg, Rotterdam">x</a></div></div>
</section>
"""


def ev(source, d, band, venue, city, **kw):
    return Event(source=source, date=d, band=band, venue=venue, city=city, url=f"https://{source}/{band}", **kw)


def test_metalfan_dates():
    assert parse_metalfan_dates("4 okt.", 2026) == (date(2026, 10, 4), None)
    assert parse_metalfan_dates("9 & 10 okt.", 2026) == (date(2026, 10, 9), date(2026, 10, 10))
    assert parse_metalfan_dates("11 t/m 13 jun.", 2027) == (date(2027, 6, 11), date(2027, 6, 13))
    assert parse_metalfan_dates("31 okt. & 1 nov.", 2026) == (date(2026, 10, 31), date(2026, 11, 1))
    assert parse_metalfan_dates("31 dec. & 1 jan.", 2026) == (date(2026, 12, 31), date(2027, 1, 1))


def test_parse_metalfan_page():
    events, next_url = parse_metalfan_page(METALFAN_HTML, "https://www.metalfan.nl/agenda.php")
    assert next_url == "https://www.metalfan.nl/agenda.php?year=2027&sw="
    assert [(e.date, e.band, e.venue, e.city) for e in events] == [
        (date(2026, 9, 30), "Integrity, Ringworm en World I Hate", "Baroeg", "Rotterdam"),
        (date(2026, 10, 9), "Soulcrusher", "Doornroosje", "Nijmegen"),
        (date(2026, 10, 10), "Metal Experience Fest", "Nobel", "Leiden"),
        (date(2026, 10, 17), "Spider Deathfest", "Rockcafé", "Balk"),
        (date(2026, 10, 31), "Marko Hietala", "Osnabrück", ""),
        (date(2026, 11, 1), "Floor Jansen", "Paradiso", ""),
    ]
    assert events[3].lineup == "Rotten Remains en Anomic"
    assert events[1].end_date == date(2026, 10, 10)
    assert events[2].lineup == "Destruction, BEAST en Warfield"
    assert events[0].url == "https://www.metalfan.nl/agenda.php#2026-09-30"


def test_parse_podiuminfo_page():
    events = parse_podiuminfo_page(PODIUMINFO_HTML)
    assert [(e.date, e.time, e.band, e.venue, e.city) for e in events] == [
        (date(2026, 9, 30), "20:00", "Integrity + Ringworm", "Baroeg", "Rotterdam"),
        (date(2026, 10, 1), None, "Coroner", "Nobel", "Leiden"),
    ]
    assert events[0].ticket_url == "https://www.podiuminfo.nl/ticket/99/ca/Integrity/"
    assert events[1].ticket_url is None


def test_dedupe_merges_across_sources():
    concerts = deduplicate([
        ev("metalfan", date(2026, 10, 2), "Belphegor en Krisiun", "Metropool", "Hengelo"),
        ev("podiuminfo", date(2026, 10, 2), "Belphegor + Krisiun", "Metropool", "Hengelo", time="20:00"),
        ev("metalfan", date(2026, 11, 11), "Enter Shakiri en Holding Absence", "013", "Tilburg"),
        ev("podiuminfo", date(2026, 11, 11), "Enter Shikari", "013", "Tilburg"),
        ev("metalfan", date(2026, 11, 1), "Floor Jansen", "Paradiso", ""),
        ev("podiuminfo", date(2026, 11, 1), "Floor Jansen", "Paradiso", "Amsterdam"),
        ev("metalfan", date(2026, 10, 9), "Soulcrusher", "Doornroosje", "Nijmegen", end_date=date(2026, 10, 10)),
        ev("podiuminfo", date(2026, 10, 10), "Soulcrusher Festival", "Doornroosje", "Nijmegen"),
        ev("metalfan", date(2026, 11, 11), "Fabio Lione", "Amsterdam", ""),  # city-only location
        ev("podiuminfo", date(2026, 11, 11), "Fabio Lione", "Melkweg", "Amsterdam"),
    ])
    assert len(concerts) == 5
    assert all(set(c.links) == {"metalfan", "podiuminfo"} for c in concerts)
    belphegor = next(c for c in concerts if c.band.startswith("Belphegor"))
    assert belphegor.band == "Belphegor en Krisiun" and belphegor.time == "20:00"
    floor = next(c for c in concerts if c.band == "Floor Jansen")
    assert floor.city == "Amsterdam"


def test_dedupe_keeps_distinct_concerts():
    concerts = deduplicate([
        ev("metalfan", date(2026, 10, 2), "Coroner", "De Pul", "Uden"),
        ev("podiuminfo", date(2026, 10, 1), "Coroner", "Nobel", "Leiden"),  # other day
        ev("podiuminfo", date(2026, 10, 2), "Coroner", "Het Podium", "Hoogeveen"),  # other city
        ev("podiuminfo", date(2026, 10, 2), "Myrath", "De Pul", "Uden"),  # other band
        ev("podiuminfo", date(2026, 10, 3), "Ploegendienst", "Fluor", "Amersfoort"),
        ev("podiuminfo", date(2026, 10, 3), "Ploegendienst", "Fluor", "Amersfoort"),  # exact duplicate
    ])
    assert len(concerts) == 5
