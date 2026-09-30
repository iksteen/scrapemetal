"""Render deduplicated concerts into a single self-contained HTML page."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from html import escape
from urllib.parse import quote_plus

from .dedupe import city_key, normalize
from .models import Concert

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]
# For web searches: most venues are Dutch and write their dates in Dutch.
DUTCH_MONTHS = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
                "augustus", "september", "oktober", "november", "december"]

SOURCE_LABELS = {"metalfan": "Metalfan", "podiuminfo": "Podiuminfo", "metalagenda": "MetalAgenda"}
CHIP_LABELS = {"metalfan": "MF", "podiuminfo": "PI", "metalagenda": "MA"}


def _date_label(c: Concert) -> str:
    label = f"{WEEKDAYS[c.date.weekday()]} {c.date.day} {MONTHS[c.date.month - 1][:3]}"
    if c.end_date:
        label += f" – {WEEKDAYS[c.end_date.weekday()]} {c.end_date.day} {MONTHS[c.end_date.month - 1][:3]}"
    return label


def _band_url(c: Concert) -> str:
    """The venue's event page, else the ticket shop, else a web search for the show."""
    day = f"{c.date.day} {DUTCH_MONTHS[c.date.month - 1]} {c.date.year}"
    query = " ".join(part for part in [c.venue, c.city, c.band, day] if part)
    return c.event_url or c.ticket_url or f"https://www.google.com/search?q={quote_plus(query)}"


def _row(c: Concert) -> str:
    search = normalize(" ".join([c.band, c.lineup or "", c.venue, c.city]))
    chips = "".join(
        f'<a class="src src-{escape(src)}" href="{escape(url)}" target="_blank" rel="noopener" '
        f'title="{escape(SOURCE_LABELS.get(src, src))}">{escape(CHIP_LABELS.get(src, src))}</a>'
        for src, url in c.links.items()
    )
    # Fixed slots (empty when missing) so the icons line up from row to row.
    icons = "".join(
        f'<a class="icon" href="{escape(url)}" target="_blank" rel="noopener" title="{label}" aria-label="{label}">{glyph}</a>'
        if url else '<span class="icon"></span>'
        for url, glyph, label in [(c.event_url, "🏛️", "Event page at the venue"), (c.ticket_url, "🎫", "Tickets")]
    )

    lineup = f'<div class="lineup">with {escape(c.lineup)}</div>' if c.lineup else ""
    venue = (
        f'<a href="{escape(c.venue_url)}" target="_blank" rel="noopener">{escape(c.venue)}</a>'
        if c.venue_url else escape(c.venue)
    )
    return (
        f'<tr data-date="{(c.end_date or c.date).isoformat()}" data-city="{escape(city_key(c.city))}" '
        f'data-sources="{escape(" ".join(c.links))}" data-added="{c.added.isoformat() if c.added else ""}" '
        f'data-search="{escape(search)}">'
        f'<td class="date"><time datetime="{c.date.isoformat()}">{escape(_date_label(c))}</time></td>'
        f'<td class="band"><a href="{escape(_band_url(c))}" target="_blank" rel="noopener"><strong>{escape(c.band)}</strong></a>{lineup}</td>'
        f'<td class="venue">{venue}</td>'
        f'<td class="city">{escape(c.city)}</td>'
        f'<td class="links"><span class="icons">{icons}</span><span class="chips">{chips}</span></td>'
        "</tr>"
    )


def render(concerts: list[Concert], status: dict[str, dict], generated: datetime) -> str:
    by_month: dict[tuple[int, int], list[Concert]] = defaultdict(list)
    for c in concerts:
        by_month[(c.date.year, c.date.month)].append(c)

    cities: dict[str, str] = {}
    for c in concerts:
        cities.setdefault(city_key(c.city), c.city)
    city_options = "".join(
        f'<option value="{escape(k)}">{escape(v)}</option>'
        for k, v in sorted(cities.items(), key=lambda kv: kv[1].lower()) if k
    )

    month_nav = "".join(
        f'<a href="#m-{y}-{m:02d}" data-month="m-{y}-{m:02d}">{MONTHS[m - 1][:3]}{"" if y == generated.year else f" {y % 100:02d}"}</a>'
        for (y, m) in sorted(by_month)
    )
    sections = "".join(
        f'<section class="month" id="m-{y}-{m:02d}"><h2>{MONTHS[m - 1]} {y}</h2>'
        f'<table><thead><tr><th class="date">Date</th><th class="band">Band</th><th class="venue">Venue</th><th class="city">City</th><th class="links">Links</th></tr></thead>'
        f'<tbody>{"".join(_row(c) for c in by_month[(y, m)])}</tbody></table></section>'
        for (y, m) in sorted(by_month)
    )
    status_html = " · ".join(
        f'<span class="{"ok" if s.get("ok") else "err"}" title="{escape(s.get("error") or "")}">'
        f'{escape(SOURCE_LABELS.get(name, name))}: {s.get("count", 0)}'
        f'{"" if s.get("ok") else " (stale)"}</span>'
        for name, s in status.items()
    )
    source_options = "".join(
        f'<option value="only:{escape(k)}">Only on {escape(v)}</option>' for k, v in SOURCE_LABELS.items()
    )

    return (TEMPLATE
            .replace("{{generated}}", escape(generated.strftime("%Y-%m-%d %H:%M")))
            .replace("{{total}}", str(len(concerts)))
            .replace("{{status}}", status_html)
            .replace("{{city_options}}", city_options)
            .replace("{{source_options}}", source_options)
            .replace("{{month_nav}}", month_nav)
            .replace("{{sections}}", sections))


TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Metal Agenda</title>
<!-- Only the 🎫 glyph (text=), so ticket links render even without a system emoji font. -->
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&text=%F0%9F%8E%AB%F0%9F%8F%9B%EF%B8%8F&display=swap">
<style>
:root {
  color-scheme: dark;
  --bg: #0f0f10; --panel: #18181b; --panel-2: #202024; --line: #2c2c31;
  --text: #e7e7ea; --muted: #9a9aa3; --accent: #d7263d; --accent-2: #3a86ff; --accent-3: #7a4fd6;
}
* { box-sizing: border-box; }
html { scroll-padding-top: 8.5rem; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
header.top { padding: 1.25rem 1rem .5rem; max-width: 1200px; margin: 0 auto; }
h1 { margin: 0; font-size: 1.6rem; letter-spacing: .02em; }
h1 span { color: var(--accent); }
.meta { color: var(--muted); font-size: .85rem; margin-top: .25rem; }
.meta .err { color: var(--accent); }
.toolbar { position: sticky; top: 0; z-index: 5; background: var(--bg); border-bottom: 1px solid var(--line); }
.toolbar-inner { max-width: 1200px; margin: 0 auto; padding: .6rem 1rem; display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
.toolbar input[type=search], .toolbar select { background: var(--panel); color: var(--text); border: 1px solid var(--line); border-radius: 6px; padding: .45rem .6rem; font: inherit; }
.toolbar input[type=search] { flex: 1 1 16rem; min-width: 0; }
.toolbar select { flex: 0 1 12rem; min-width: 0; }
.toolbar label { color: var(--muted); font-size: .85rem; white-space: nowrap; display: flex; gap: .3rem; align-items: center; }
.toolbar input[type=checkbox] { accent-color: var(--accent); margin: 0; }
.count { color: var(--muted); font-size: .85rem; margin-left: auto; }
nav.months { max-width: 1200px; margin: 0 auto; padding: 0 1rem .6rem; display: flex; gap: .35rem; overflow-x: auto; }
nav.months a { color: var(--text); text-decoration: none; background: var(--panel); border: 1px solid var(--line); border-radius: 999px; padding: .15rem .7rem; white-space: nowrap; font-size: .85rem; }
nav.months a:hover { border-color: var(--accent); }
nav.months a.empty { opacity: .35; }
main { max-width: 1200px; margin: 0 auto; padding: 0 1rem 3rem; }
h2 { font-size: 1.05rem; text-transform: uppercase; letter-spacing: .08em; color: var(--accent); margin: 1.5rem 0 .4rem; }
table { width: 100%; table-layout: fixed; border-collapse: collapse; background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
th { text-align: left; font-size: .75rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); background: var(--panel-2); padding: .45rem .7rem; }
td { padding: .5rem .7rem; border-top: 1px solid var(--line); vertical-align: top; }
tr.newday td { border-top: 2px solid var(--line); }
tbody tr:hover { background: var(--panel-2); }
th.date, td.date { white-space: nowrap; width: 9.5rem; }
th.venue { width: 22%; } th.city { width: 14%; } th.links { width: 11rem; }
td { overflow-wrap: anywhere; }
td.band strong { font-weight: 600; }
.lineup { color: var(--muted); font-size: .82rem; }
td.city { white-space: nowrap; }
td.band a, td.venue a { color: inherit; text-decoration: underline; text-decoration-color: var(--line); text-underline-offset: 3px; }
td.band a:hover, td.venue a:hover { text-decoration-color: var(--accent); }
th.links, td.links { text-align: right; }
.icons { float: right; white-space: nowrap; }
.icon { display: inline-block; width: 1.7rem; text-align: center; text-decoration: none; font-family: "Noto Color Emoji", sans-serif; font-size: 1.1rem; line-height: 1.3rem; }
a.src { display: inline-block; font-size: .75rem; text-decoration: none; padding: .1rem .45rem; border-radius: 4px; margin: 0 .2rem .2rem 0; color: #fff; }
a.src-metalfan { background: var(--accent); }
a.src-podiuminfo { background: var(--accent-2); }
a.src-metalagenda { background: var(--accent-3); }
.hidden { display: none !important; }
.nothing { color: var(--muted); text-align: center; padding: 3rem 0; }
@media (max-width: 760px) {
  .toolbar select { flex: 1 1 8rem; }
  thead { display: none; }
  table, tbody, tr, td { display: block; }
  tr {
    display: grid !important; grid-template-columns: minmax(0, 1fr) auto; column-gap: .75rem; align-items: baseline;
    grid-template-areas: "date links" "band band" "venue city";
    padding: .55rem .7rem; border-top: 1px solid var(--line);
  }
  tr.hidden { display: none !important; }
  td, tr.newday td { border: 0; padding: 0; }
  tr.newday { border-top: 2px solid var(--line); }
  td.date { grid-area: date; color: var(--muted); font-size: .85rem; width: auto; }
  td.links { grid-area: links; justify-self: end; display: flex; flex-direction: row-reverse; align-items: center; gap: .3rem; margin-right: -.35rem; }
  .icons { float: none; }
  .chips { display: flex; }
  td.band { grid-area: band; }
  td.venue, td.city { color: var(--muted); font-size: .88rem; }
  td.venue { grid-area: venue; }
  td.city { grid-area: city; text-align: right; }
}
</style>
</head>
<body>
<header class="top">
  <h1>Metal <span>Agenda</span></h1>
  <div class="meta">Updated {{generated}} · {{total}} concerts · {{status}}</div>
</header>
<div class="toolbar">
  <div class="toolbar-inner">
    <input id="q" type="search" placeholder="Search band, venue or city… (press /)" autocomplete="off">
    <select id="city"><option value="">All cities</option>{{city_options}}</select>
    <select id="source"><option value="">All sources</option><option value="both">On multiple sites</option>{{source_options}}</select>
    <label><input type="checkbox" id="recent"> Added this week</label>
    <span class="count" id="count"></span>
  </div>
  <nav class="months">{{month_nav}}</nav>
</div>
<main>
{{sections}}
<p class="nothing hidden" id="nothing">No concerts match your filters.</p>
</main>
<script>
(() => {
  const q = document.getElementById('q'), city = document.getElementById('city'), source = document.getElementById('source');
  const recent = document.getElementById('recent');
  const rows = [...document.querySelectorAll('tbody tr')];
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const iso = d => d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  const todayIso = iso(today);
  const weekAgoIso = iso(new Date(today.getFullYear(), today.getMonth(), today.getDate() - 6));
  const norm = s => s.normalize('NFKD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();

  function apply() {
    const terms = norm(q.value).split(' ').filter(Boolean), c = city.value, s = source.value;
    let shown = 0;
    for (const r of rows) {
      const srcs = r.dataset.sources.split(' ');
      const ok = r.dataset.date >= todayIso
        && (!c || r.dataset.city === c)
        && (!recent.checked || r.dataset.added >= weekAgoIso)
        && (!s || (s === 'both' ? srcs.length > 1 : srcs.length === 1 && srcs[0] === s.slice(5)))
        && terms.every(t => r.dataset.search.includes(t));
      r.classList.toggle('hidden', !ok);
      if (ok) shown++;
    }
    for (const sec of document.querySelectorAll('section.month')) {
      let prev = null;
      const visible = [...sec.querySelectorAll('tbody tr:not(.hidden)')];
      for (const r of visible) { r.classList.toggle('newday', prev !== null && prev !== r.dataset.date); prev = r.dataset.date; }
      sec.classList.toggle('hidden', visible.length === 0);
      const link = document.querySelector(`nav.months a[data-month="${sec.id}"]`);
      if (link) link.classList.toggle('empty', visible.length === 0);
    }
    document.getElementById('count').textContent = `${shown} shown`;
    document.getElementById('nothing').classList.toggle('hidden', shown > 0);
    const params = new URLSearchParams();
    if (q.value) params.set('q', q.value);
    if (c) params.set('city', c);
    if (s) params.set('source', s);
    if (recent.checked) params.set('recent', '1');
    history.replaceState(null, '', (params.toString() ? '?' + params : location.pathname) + location.hash);
  }

  const params = new URLSearchParams(location.search);
  q.value = params.get('q') || ''; city.value = params.get('city') || ''; source.value = params.get('source') || '';
  recent.checked = params.get('recent') === '1';
  q.addEventListener('input', apply); city.addEventListener('change', apply); source.addEventListener('change', apply);
  recent.addEventListener('change', apply);
  document.addEventListener('keydown', e => {
    if (e.key === '/' && document.activeElement !== q) { e.preventDefault(); q.focus(); }
    else if (e.key === 'Escape' && document.activeElement === q) { q.value = ''; apply(); }
  });
  apply();
})();
</script>
</body>
</html>
"""
