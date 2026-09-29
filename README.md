# scrapemetal

Scrapes the metal concert agendas of [metalfan.nl](https://www.metalfan.nl/agenda.php) and
[podiuminfo.nl](https://www.podiuminfo.nl/concertagenda/genre/metal/?input_event_type=1&input_country=58),
merges listings that describe the same concert, and writes a single searchable page
(`public/index.html`) with date, band, venue, city and links to the sources.

## Usage

```sh
uv sync

# Scrape once (e.g. from cron) and write public/index.html + public/concerts.json
uv run scrapemetal scrape

# Serve the page on http://127.0.0.1:8000/ and re-scrape every 6 hours
uv run scrapemetal serve --host 0.0.0.0 --port 8000 --interval 6
```

Cron alternative (serve `public/` with any web server):

```
0 */6 * * * cd /path/to/scrapemetal && uv run scrapemetal scrape
```

The page has a search box (press `/`), a city filter, a source filter (e.g. "only on
metalfan") and month jump links. Filters are kept in the URL so they can be bookmarked.

## How deduplication works

Two listings from different sources are the same concert when their dates overlap
(metalfan multi-day events count as a range), they are in the same city (or the same venue if
a city is missing), and a band name from one listing appears in the other (with a small
tolerance for typos). Merged concerts use metalfan's band line-up and podiuminfo's
venue/city/start time, and link to both sources.

## Venue links

Venue names link to the venue's website when the venue is listed in `venues.toml`
(name + city + URL, with optional `aliases` for other spellings). To extend it:

```sh
uv run scrapemetal venues   # venues without a website, most concerts first
$EDITOR venues.toml
uv run scrapemetal render   # rebuild the page from cached data, no scraping
```

The file is re-read on every scrape, so a running `serve` picks up changes at the next run.

## Ticket links

When podiuminfo lists a ticket link, the page shows a 🎫 link. podiuminfo's
links are redirects (sometimes through an affiliate tracker), so they are resolved to the
actual ticket shop URL (Ticketmaster, the venue's Stager shop, etc.) with tracking parameters
removed. podiuminfo rate-limits these redirects, so they are resolved slowly (one per 1.5 s),
cached in `data/tickets.json`, and only new links are resolved on later runs. Links that could
not be resolved yet still work via the podiuminfo redirect. metalfan has no ticket links.

Raw per-source results are cached in `data/`. If a source fails to scrape, the last good
result is used and the page marks that source as stale.

## Tests

```sh
uv run pytest
```
