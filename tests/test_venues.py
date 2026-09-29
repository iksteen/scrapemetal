from pathlib import Path

from scrapemetal.venues import VenueDirectory, venue_key

ENTRIES = [
    {"name": "013", "city": "Tilburg", "url": "https://www.013.nl/"},
    {"name": "Metropool", "city": "Hengelo", "url": "https://metropool.nl/hengelo"},
    {"name": "Metropool", "city": "Enschede", "url": "https://metropool.nl/enschede", "aliases": ["Metropool Enschede"]},
    {"name": "Paradiso", "city": "Amsterdam", "url": "https://www.paradiso.nl/"},
    {"name": "Het Podium", "city": "Hoogeveen", "url": "https://hetpodium.nl/"},
]


def test_venue_key():
    assert venue_key("Poppodium 013") == venue_key("013") == "013"
    assert venue_key("Willem Twee poppodium") == "willem twee"
    assert venue_key("De Pul") == venue_key("Pul")
    assert venue_key("Het Podium") == "podium"


def test_lookup():
    d = VenueDirectory(ENTRIES)
    assert d.lookup("Poppodium 013", "Tilburg") == "https://www.013.nl/"
    assert d.lookup("Metropool", "Hengelo") == "https://metropool.nl/hengelo"
    assert d.lookup("Metropool Enschede", "Enschede") == "https://metropool.nl/enschede"
    assert d.lookup("Paradiso", "") == "https://www.paradiso.nl/"  # city missing, name is unique
    assert d.lookup("Metropool", "") is None  # city missing, name is ambiguous
    assert d.lookup("013", "Utrecht") is None
    assert d.lookup("Het Podium", "Hoogeveen (NL)") == "https://hetpodium.nl/"


def test_shipped_venue_list_loads():
    d = VenueDirectory.load(Path(__file__).parent.parent / "venues.toml")
    assert d.lookup("TivoliVredenburg", "Utrecht")
    assert d.lookup("SPOT / De Oosterpoort", "Groningen")


def test_load_warns_about_typos(tmp_path, caplog):
    path = tmp_path / "venues.toml"
    path.write_text('''
[[venue]]
name = "Paradiso"
city = "Amsterdam"
url = "https://www.paradiso.nl/"

[[venu]]
name = "Typo"
city = "X"
url = "https://x/"

[[venue]]
name = "No URL"
city = "Y"
''')
    d = VenueDirectory.load(path)
    assert d.lookup("Paradiso", "Amsterdam")
    assert "unknown section 'venu'" in caplog.text
    assert "No URL" in caplog.text


def test_apply_moves_city_only_location_to_city():
    from datetime import date
    from scrapemetal.models import Concert
    d = VenueDirectory(ENTRIES)
    city_only = Concert(date=date(2026, 11, 10), band="x", venue="Brussel", city="")
    venue_only = Concert(date=date(2026, 11, 1), band="y", venue="Paradiso", city="")
    d.apply([city_only, venue_only])
    assert (city_only.venue, city_only.city, city_only.venue_url) == ("", "Brussel", None)
    assert (venue_only.venue, venue_only.city, venue_only.venue_url) == ("Paradiso", "", "https://www.paradiso.nl/")
