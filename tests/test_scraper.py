from datetime import date

from scrapemetal.dedupe import deduplicate
from scrapemetal.models import Event
from scrapemetal.sources import (
    parse_metalagenda_page,
    parse_metalfan_dates,
    parse_metalfan_page,
    parse_podiuminfo_page,
)

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


METALAGENDA_HTML = """
<div id="cont_left"><div class="dateheader hanginthere" id="2026-09-30"><span class="bg">3</span> <sub>woensdag</sub></div>
<div class="agendapunt"><div class="left"><a href="https://baroeg.nl/productie/integrity/" target="_blank"><h3> Live Hard Bookings presents: Integrity + Ringworm + World I Hate</h3></a><a href="/venues/baroeg" target="_blank">Baroeg</a> <a href="/p/rotterdam" target="_blank">Rotterdam</a><div style="font-size: 10px;"><span style="font-weight: bold">Bands: </span> integrity | <a href="https://www.metal-archives.com/bands/ringworm/81102">ringworm</a> | world i hate</div></div><div class="right blck"><a href="/ical/7018" title="Voeg toe aan je agenda"></a></div></div>
<div class="dateheader hanginthere" id="2026-10-01"><span class="bg">0</span> <sub>donderdag</sub></div>
<div class="agendapunt"><div class="left"><a href="https://nobel.nl/agenda/coroner" target="_blank"><h3> Coroner</h3></a><a href="/venues/nobel" target="_blank">Nobel</a> <a href="/p/leiden" target="_blank">Leiden</a><div style="font-size: 10px;"><span style="font-weight: bold">Bands: </span> coroner | tar pond | onbekend</div></div></div>
<div class="agendapunt"><div class="left"><a href="https://hedon-zwolle.nl/x" target="_blank"><h3><div class="soldout">uitverkocht</div> A LIFE ALIGNED</h3></a><a href="/venues/hedon" target="_blank">Hedon</a> <a href="/p/zwolle" target="_blank">Zwolle</a></div></div>
<div class="agendapunt"><div class="left"><a href="https://example.org/" target="_blank"><h3><div class="soldout">cancelled</div> Gone</h3></a><a href="/venues/x" target="_blank">X</a> <a href="/p/y" target="_blank">Y</a></div></div>
<div class="agendapunt"><div class="left"><h3><div class="soldout">geen eventpagina</div>  Dogfest</h3><a href="/venues/paraplufabriek" target="_blank">Paraplufabriek</a> <a href="/p/nijmegen" target="_blank">Nijmegen</a><div><span>Bands: </span> rauss! | fulgurite</div></div></div>
</div><div id="cont_right"></div>
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
    assert [e.uid for e in events] == ["podiuminfo:1", "podiuminfo:2"]


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
        ev("metalagenda", date(2026, 10, 10), "Up the Irons – Iron Maiden Tribute", "Capsloc", "Capelle ad IJssel"),
        ev("podiuminfo", date(2026, 10, 10), "Up the Irons - Iron Maiden Tribute", "Capsloc", "Capelle aan den IJssel"),
        ev("metalagenda", date(2026, 10, 12), "Ritual — The Dutch Ghost Experience", "Boerderij", "Zoetermeer"),
        ev("metalfan", date(2026, 10, 12), "The Dutch Ghost Experience", "Boerderij", "Zoetermeer"),
    ])
    assert len(concerts) == 7
    irons = next(c for c in concerts if c.venue == "Capsloc")
    assert irons.city == "Capelle aan den IJssel" and len(irons.links) == 2
    assert len(next(c for c in concerts if "Ghost" in c.band).links) == 2
    assert sum(set(c.links) == {"metalfan", "podiuminfo"} for c in concerts) == 5
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


def test_parse_metalagenda_page():
    events = parse_metalagenda_page(METALAGENDA_HTML)
    assert [(e.date, e.band, e.venue, e.city, e.lineup) for e in events] == [
        (date(2026, 9, 30), "Live Hard Bookings presents: Integrity + Ringworm + World I Hate", "Baroeg", "Rotterdam", None),
        (date(2026, 10, 1), "Coroner", "Nobel", "Leiden", "Tar Pond"),
        (date(2026, 10, 1), "A LIFE ALIGNED", "Hedon", "Zwolle", None),
        (date(2026, 10, 1), "Dogfest", "Paraplufabriek", "Nijmegen", "Rauss!, Fulgurite"),
    ]
    assert events[0].url == "https://www.metalagenda.nl/?datum=2026-09-30"
    assert events[0].event_url == "https://baroeg.nl/productie/integrity/"
    assert events[3].event_url is None  # "geen eventpagina"
    assert events[0].uid == "metalagenda:7018" and events[1].uid is None


def test_dedupe_merges_three_sources():
    concerts = deduplicate([
        ev("metalagenda", date(2026, 10, 1), "Coroner", "Nobel", "Leiden", lineup="Tar Pond", event_url="https://nobel.nl/x"),
        ev("metalfan", date(2026, 10, 1), "Coroner", "Nobel", "Leiden", lineup="Tar Pond en Schizophrenia"),
        ev("podiuminfo", date(2026, 10, 1), "Coroner", "Nobel", "Leiden", time="20:00"),
    ])
    assert len(concerts) == 1
    assert set(concerts[0].links) == {"metalagenda", "metalfan", "podiuminfo"}
    assert concerts[0].lineup == "Tar Pond en Schizophrenia" and concerts[0].time == "20:00"
    assert concerts[0].event_url == "https://nobel.nl/x"
