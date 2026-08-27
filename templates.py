"""Shared page shell — nav tabs, earth-tone CSS (sungeo.net-inspired), badge styles.

Every page in pages.py returns just its body HTML; page_shell() wraps it with
the same head/nav/footer so the three tabs feel like one site, not three
disconnected files.
"""

from __future__ import annotations

TABS = [
    ("index.html", "Сейчас"),
    ("space-weather.html", "Космическая погода"),
    ("moon.html", "Луна"),
    ("events.html", "События"),
]

CSS = """
  :root {
    --ink:#241f1a; --ink-soft:#6b5f52; --paper:#f6f2ea; --surface:#ffffff;
    --line:#e3dccd; --calm:#4f7a5c; --active:#c98a3e; --storm:#b6472f;
    --accent:#8a5a2e; --accent2:#3d6e63; --accent3:#a67c4e;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --ink:#efe9df; --ink-soft:#b5a999; --paper:#1c1712; --surface:#26201a;
      --line:#3c3327; --calm:#7fae8c; --active:#e0a862; --storm:#e0745a;
      --accent:#c39566; --accent2:#7fb0a3; --accent3:#c9a374;
    }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--paper); color:var(--ink); font-family: -apple-system, "Segoe UI", Roboto, sans-serif; line-height:1.5; }
  .page { max-width: 900px; margin: 0 auto; padding: 0 20px 64px; }
  nav.tabs { display:flex; gap:4px; border-bottom:1px solid var(--line); margin-bottom:28px; padding-top:20px; overflow-x:auto; }
  nav.tabs a { padding:10px 16px; text-decoration:none; color:var(--ink-soft); font-size:.92rem; font-weight:600; border-bottom:2px solid transparent; white-space:nowrap; }
  nav.tabs a.active { color:var(--ink); border-bottom-color:var(--accent); }
  nav.tabs a:hover { color:var(--ink); }
  h1 { font-size: 1.5rem; margin: 8px 0 4px; font-weight: 700; }
  .meta { color: var(--ink-soft); font-size: .85rem; margin-bottom: 24px; }
  .hero { display:flex; gap:32px; align-items:center; flex-wrap:wrap; background:var(--surface); border:1px solid var(--line); border-radius:14px; padding:24px 28px; margin-bottom:28px; }
  .ring-bg { stroke: var(--line); }
  .ring-center-label { font-size: 20px; font-weight: 800; fill: var(--ink); letter-spacing: .04em; }
  .ring-center-sub { font-size: 13px; fill: var(--ink-soft); }
  .ring-legend { display:flex; flex-direction:column; gap:8px; font-size:.92rem; }
  .ring-legend-item { display:flex; align-items:center; gap:8px; }
  .ring-legend .dot { width:10px; height:10px; border-radius:50%; display:inline-block; flex-shrink:0; }
  .badges { display:flex; gap:8px; flex-wrap:wrap; margin-top:14px; }
  .badge { display:inline-flex; align-items:center; font-size:.78rem; font-weight:600; padding:5px 12px; border-radius:20px; }
  .badge-calm { background:color-mix(in srgb, var(--calm) 18%, transparent); color:var(--calm); }
  .badge-active { background:color-mix(in srgb, var(--active) 20%, transparent); color:var(--active); }
  .badge-storm { background:color-mix(in srgb, var(--storm) 20%, transparent); color:var(--storm); }
  .cards { display:grid; grid-template-columns: repeat(auto-fit, minmax(130px,1fr)); gap:1px; background:var(--line); border:1px solid var(--line); border-radius:10px; overflow:hidden; margin-bottom:28px; }
  .card { background:var(--surface); padding:14px 16px; }
  .card .n { font-size:1.3rem; font-weight:700; }
  .card .cap { font-size:.76rem; color:var(--ink-soft); margin-top:4px; }
  section { margin: 32px 0; }
  section h2 { font-size:1.05rem; margin-bottom:10px; font-weight:700; }
  .panel { background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:16px 18px; overflow-x:auto; }
  .grid { stroke: var(--line); }
  .axis { fill: var(--ink-soft); }
  .bar-ok { fill: var(--calm); }
  .bar-storm { fill: var(--storm); }
  .threshold { stroke: var(--storm); stroke-dasharray: 4 3; }
  .threshold-label { fill: var(--storm); }
  .sources { display:flex; flex-direction:column; gap:10px; }
  .source-row { display:flex; justify-content:space-between; gap:10px; font-size:.88rem; padding:8px 0; border-bottom:1px solid var(--line); flex-wrap:wrap; }
  .source-row:last-child { border-bottom:none; }
  .source-row a { color:var(--accent); text-decoration:none; }
  .source-row a:hover { text-decoration:underline; }
  .source-row .status { color:var(--ink-soft); font-size:.82rem; }
  footer { margin-top:40px; font-size:.76rem; color:var(--ink-soft); }
"""


def page_shell(title: str, active_page: str, body_html: str) -> str:
    nav_items = "".join(
        f'<a href="{href}" class="{"active" if href == active_page else ""}">{label}</a>'
        for href, label in TABS
    )
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Погода и космос</title>
<style>{CSS}</style>
</head>
<body>
<div class="page">
  <nav class="tabs">{nav_items}</nav>
  {body_html}
  <footer>Дизайн вдохновлён sungeo.net (Earth Core ring gauge).</footer>
</div>
</body>
</html>"""
