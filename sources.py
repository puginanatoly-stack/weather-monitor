"""Data collection for the Weather project.

Sources, deliberately kept independent — one function each, one failure
doesn't take down the others:
  - OpenWeatherMap (current weather + forecast) — needs OPENWEATHERMAP_API_KEY.
  - NOAA SWPC planetary K-index (geomagnetic activity) — no key required.
  - NOAA SWPC real-time solar wind (rtsw) — no key required.
  - NOAA SWPC OVATION aurora probability grid, sampled at the query city's
    coordinates (taken from the OWM response, no separate geocoding) — no key.
  - Schumann resonance (schumannresonancelive.com, unofficial third party) —
    no key, but no official public API exists for this either; the source
    itself reports a `status` that can say "Stale" / "Source unavailable" —
    fetch_schumann() surfaces that honestly (`is_ok` + raw label/tone) rather
    than silently presenting old numbers as live.

Solar activity (NASA DONKI) is not wired in yet — that needs a second key
(api.nasa.gov) that hasn't been provided. Add a fetch_donki() here + a call
in collect() once it exists; nothing else needs to change.
"""

from __future__ import annotations

import json
import math
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent / "data"

# Sri Lanka hazard tracking — earthquakes/storms filtered from the global
# EONET/USGS feeds we already fetch, geo-scoped instead of a second city run.
# Quake radius is generous on purpose: the 2004 tsunami that hit Sri Lanka
# originated off Sumatra, ~1600 km away, so a tight radius would miss exactly
# the class of event that matters most here.
SRI_LANKA_LAT = 7.87
SRI_LANKA_LON = 80.77
SRI_LANKA_QUAKE_RADIUS_KM = 2500
SRI_LANKA_STORM_RADIUS_KM = 1500
# USGS's "significant" feed is a rolling 30-day window — without an age cutoff
# a single old quake sits in range and produces an identical score for weeks
# until it ages out (found 2026-09-08: a M6.9 from Aug 15 was still driving
# an unchanged "Активно" reading three weeks later). Only count quakes from
# the last N days so the index tracks what's actually current.
SRI_LANKA_QUAKE_MAX_AGE_DAYS = 3

# Ground conditions (air/water temp, wind) — Colombo, a coastal point.
# Deliberately NOT the same as SRI_LANKA_LAT/LON above: that pair is the
# island's geometric center (inland, hill country near Kandy), fine for a
# 2500 km hazard-radius search but useless for sea-surface temperature.
SRI_LANKA_COASTAL_LAT = 6.9271
SRI_LANKA_COASTAL_LON = 79.8612

OWM_BASE = "https://api.openweathermap.org/data/2.5"
NOAA_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
NOAA_SOLAR_WIND_URL = "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json"
NOAA_AURORA_URL = "https://services.swpc.noaa.gov/json/ovation_aurora_latest.json"
SCHUMANN_URL = "https://schumannresonancelive.com/api/data.php?lang=en"
NASA_EONET_URL = "https://eonet.gsfc.nasa.gov/api/v3/events"
USGS_QUAKES_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

# "Digital noise" proxy for the events no clean structured API exists for
# (unrest, mass incidents, ...): not classifying WHAT is happening, just
# measuring headline VOLUME across a few major RSS feeds — if feeds are
# flooded, something's generating unusual news volume, whatever it is.
NEWS_FEEDS = [
    ("BBC World", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Google News", "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("RIA Novosti", "https://ria.ru/export/rss2/archive/index.xml"),
]

# Market volatility — another indirect "something's happening" proxy.
# Deliberately shallow per the principal's own framing ("очень крупно, не
# уходя в глубину, базовые валюты и базовые индексы"): five symbols, one
# day-over-day % change each, no sector/stock-picking depth. ^VIX is the
# most direct one — it's literally CBOE's volatility ("fear") index.
MARKET_SYMBOLS = [
    ("^GSPC", "S&P 500"),
    ("^VIX", "VIX (индекс страха)"),
    ("IMOEX.ME", "MOEX Russia"),
    ("RUB=X", "USD/RUB"),
    ("EURUSD=X", "EUR/USD"),
]
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
# Yahoo's chart endpoint 429s without a browser-shaped UA — not a key, just
# a header it insists on.
YAHOO_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def load_env_var(name: str) -> str | None:
    """Reads KEY=VALUE from ~/.claude/.env (LifeOS canonical secrets file)."""
    env_path = Path.home() / ".claude" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == name:
                return value.strip()
    return os.environ.get(name)


def fetch_current_weather(city: str, api_key: str) -> dict:
    resp = requests.get(
        f"{OWM_BASE}/weather",
        params={"q": city, "appid": api_key, "units": "metric", "lang": "ru"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_forecast(city: str, api_key: str) -> dict:
    """5-day / 3-hour forecast (free tier)."""
    resp = requests.get(
        f"{OWM_BASE}/forecast",
        params={"q": city, "appid": api_key, "units": "metric", "lang": "ru"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_kp_index() -> list[dict]:
    """Recent planetary Kp-index readings. No API key needed."""
    resp = requests.get(NOAA_KP_URL, timeout=15)
    resp.raise_for_status()
    rows = resp.json()
    return [r for r in rows if isinstance(r, dict) and "Kp" in r]


def fetch_solar_wind(minutes: int = 180) -> list[dict]:
    """Recent real-time solar wind (rtsw), 1-minute cadence. No API key needed.

    The full feed covers multiple days at 1-min resolution (megabytes) — we
    only need a recent window for a trend chart, so slice it down here rather
    than caching the whole thing.
    """
    resp = requests.get(NOAA_SOLAR_WIND_URL, timeout=20)
    resp.raise_for_status()
    rows = [r for r in resp.json() if isinstance(r, dict)]
    active = [r for r in rows if r.get("active")]
    chosen = active if active else rows
    return chosen[-minutes:]


def fetch_aurora(lat: float, lon: float) -> dict:
    """Aurora probability at the nearest 1-degree grid cell. No API key needed."""
    resp = requests.get(NOAA_AURORA_URL, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    coords = payload.get("coordinates", [])
    lon_i, lat_i = round(lon) % 360, round(lat)
    match = next((c for c in coords if c[0] == lon_i and c[1] == lat_i), None)
    return {
        "observation_time": payload.get("Observation Time"),
        "forecast_time": payload.get("Forecast Time"),
        "probability": match[2] if match else None,
        "lat": lat_i,
        "lon": lon_i,
    }


def fetch_schumann() -> dict:
    """Schumann resonance — unofficial third-party source, no key.

    Surfaces the source's own status honestly instead of hiding it: when the
    upstream feed is stale, the API itself marks frequencies `measured: false`
    (nominal/reference values, not live readings) — that flag is passed
    through untouched so the page can say so rather than presenting old
    numbers as current.

    The endpoint itself has gone away before (HTTP 404, not just "stale") —
    that's a fetch failure, not a data-quality flag, but gets the same
    `is_ok: False` treatment rather than raising: one source being gone
    shouldn't take the whole build down, same contract as every other
    fetch_* here.
    """
    try:
        resp = requests.get(SCHUMANN_URL, timeout=15)
        resp.raise_for_status()
        payload = resp.json()
    except (requests.RequestException, ValueError):
        return {
            "updated": None,
            "is_ok": False,
            "status_label": "Источник недоступен",
            "status_tone": "error",
            "intensity": None,
            "frequencies": [],
        }
    status = payload.get("status") or {}
    label = status.get("label", "")
    tone = status.get("tone", "")
    is_ok = "stale" not in label.lower() and "unavailable" not in tone.lower()
    return {
        "updated": payload.get("updated"),
        "is_ok": is_ok,
        "status_label": label or "—",
        "status_tone": tone or "",
        "intensity": payload.get("intensity"),
        "frequencies": payload.get("frequencies", []),
    }


def fetch_natural_events(days: int = 20, limit: int = 50) -> list[dict]:
    """Open natural events (storms, wildfires, volcanoes, floods, ...) from NASA EONET. No key."""
    resp = requests.get(NASA_EONET_URL, params={"status": "open", "days": days, "limit": limit}, timeout=15)
    resp.raise_for_status()
    return resp.json().get("events", [])


def fetch_significant_earthquakes() -> list[dict]:
    """M4.5+ earthquakes over the past month (USGS 'significant' feed). No key."""
    resp = requests.get(USGS_QUAKES_URL, timeout=15)
    resp.raise_for_status()
    return resp.json().get("features", [])


def fetch_sri_lanka_weather(lat: float = SRI_LANKA_COASTAL_LAT, lon: float = SRI_LANKA_COASTAL_LON) -> dict:
    """Air temperature + wind speed at a Sri Lanka coastal point (Open-Meteo). No key.

    Same soft-failure contract as the other fetch_* here: a network hiccup or
    upstream error returns is_ok: False with None values rather than raising.
    """
    try:
        resp = requests.get(
            OPEN_METEO_FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,wind_speed_10m",
                "wind_speed_unit": "ms",
                "timezone": "auto",
            },
            timeout=15,
        )
        resp.raise_for_status()
        current = resp.json().get("current", {})
        return {
            "is_ok": True,
            "air_temp_c": current.get("temperature_2m"),
            "wind_speed_ms": current.get("wind_speed_10m"),
        }
    except (requests.RequestException, ValueError):
        return {"is_ok": False, "air_temp_c": None, "wind_speed_ms": None}


def fetch_sri_lanka_marine(lat: float = SRI_LANKA_COASTAL_LAT, lon: float = SRI_LANKA_COASTAL_LON) -> dict:
    """Sea surface temperature near Sri Lanka (Open-Meteo Marine). No key."""
    try:
        resp = requests.get(
            OPEN_METEO_MARINE_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "sea_surface_temperature",
                "timezone": "auto",
            },
            timeout=15,
        )
        resp.raise_for_status()
        current = resp.json().get("current", {})
        return {"is_ok": True, "water_temp_c": current.get("sea_surface_temperature")}
    except (requests.RequestException, ValueError):
        return {"is_ok": False, "water_temp_c": None}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def earthquakes_near(
    earthquakes: list[dict],
    lat: float,
    lon: float,
    radius_km: float,
    max_age_days: float | None = None,
) -> list[dict]:
    """USGS GeoJSON features within radius_km of (lat, lon), nearest first, each tagged with distance_km.

    max_age_days, if given, drops quakes older than that (by `properties.time`,
    epoch ms) — without it, USGS's rolling monthly feed keeps an old quake in
    range for up to 30 days, producing an unchanged reading long after the
    event stopped being current.
    """
    now = datetime.now(timezone.utc)
    out = []
    for eq in earthquakes:
        coords = (eq.get("geometry") or {}).get("coordinates")
        if not coords or len(coords) < 2:
            continue
        if max_age_days is not None:
            time_ms = (eq.get("properties") or {}).get("time")
            if time_ms is None:
                continue
            age = now - datetime.fromtimestamp(time_ms / 1000, tz=timezone.utc)
            if age > timedelta(days=max_age_days):
                continue
        eq_lon, eq_lat = coords[0], coords[1]
        dist = _haversine_km(lat, lon, eq_lat, eq_lon)
        if dist <= radius_km:
            tagged = dict(eq)
            tagged["distance_km"] = round(dist, 1)
            out.append(tagged)
    return sorted(out, key=lambda e: e["distance_km"])


def storms_near(events: list[dict], lat: float, lon: float, radius_km: float) -> list[dict]:
    """EONET events categorized as storms, within radius_km — uses each event's most recent tracked position."""
    out = []
    for ev in events:
        categories = ev.get("categories") or ev.get("category") or []
        is_storm = any("storm" in ((c.get("id", "") + c.get("title", "")).lower()) for c in categories)
        if not is_storm:
            continue
        geometry = ev.get("geometry") or []
        if not geometry:
            continue
        coords = geometry[-1].get("coordinates")
        if not coords or len(coords) < 2:
            continue
        ev_lon, ev_lat = coords[0], coords[1]
        dist = _haversine_km(lat, lon, ev_lat, ev_lon)
        if dist <= radius_km:
            tagged = dict(ev)
            tagged["distance_km"] = round(dist, 1)
            out.append(tagged)
    return sorted(out, key=lambda e: e["distance_km"])


def _parse_rss_pubdates(xml_text: str) -> list[datetime]:
    dates: list[datetime] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return dates
    for item in root.iter("item"):
        pub = item.find("pubDate")
        if pub is None or not pub.text:
            continue
        try:
            dt = parsedate_to_datetime(pub.text)
        except (TypeError, ValueError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dates.append(dt.astimezone(timezone.utc))
    return dates


def fetch_news_frequency(window_hours: int = 3) -> dict:
    """Headline volume across a few major RSS feeds in the last `window_hours`.

    No API key for any of these. One feed failing (network hiccup, a site
    changing its RSS path) doesn't take the others down — recorded as -1 for
    that feed rather than raising, since this is a soft proxy signal, not a
    load-bearing data source the page should break over.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)
    per_feed: dict[str, int] = {}
    total_recent = 0

    for name, url in NEWS_FEEDS:
        try:
            resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (weather-project)"})
            resp.raise_for_status()
            dates = _parse_rss_pubdates(resp.text)
        except requests.RequestException:
            per_feed[name] = -1
            continue
        recent = sum(1 for d in dates if d >= cutoff)
        per_feed[name] = recent
        total_recent += recent

    return {
        "fetched_at": now.isoformat(),
        "window_hours": window_hours,
        "total_recent": total_recent,
        "per_feed": per_feed,
    }


def fetch_market_snapshot() -> list[dict]:
    """Day-over-day % change for a handful of base indices/FX pairs. No key.

    One symbol failing doesn't take the others down — recorded with
    price/change_pct as None rather than raising.
    """
    out = []
    for symbol, label in MARKET_SYMBOLS:
        entry = {"symbol": symbol, "label": label, "price": None, "change_pct": None}
        try:
            resp = requests.get(
                YAHOO_CHART_URL.format(symbol=symbol),
                params={"range": "5d", "interval": "1d"},
                headers={"User-Agent": YAHOO_UA},
                timeout=10,
            )
            resp.raise_for_status()
            result = resp.json()["chart"]["result"][0]
            meta = result["meta"]
            entry["price"] = meta.get("regularMarketPrice")
            closes = [c for c in result["indicators"]["quote"][0].get("close", []) if c is not None]
            prev_close = None
            if len(closes) >= 2:
                prev_close = closes[-2]
            elif meta.get("chartPreviousClose"):
                # Some symbols (seen on IMOEX.ME) return an empty quote.close
                # array but still carry chartPreviousClose in meta.
                prev_close = meta["chartPreviousClose"]
            if prev_close and entry["price"] is not None:
                entry["change_pct"] = (entry["price"] - prev_close) / prev_close * 100
        except (requests.RequestException, KeyError, IndexError, TypeError, ValueError):
            pass
        out.append(entry)
    return out


def append_history(row: dict) -> Path:
    """Append-only time series — one line per build.py run.

    This is what makes a real correlation (e.g. moon phase vs. event counts)
    possible later: collect() only ever returns a snapshot, save_snapshot()
    only ever overwrites, so without this nothing accumulates across runs.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / "history.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def read_history() -> list[dict]:
    path = DATA_DIR / "history.jsonl"
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def save_snapshot(name: str, payload) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = DATA_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def collect(city: str) -> dict:
    """Fetch all wired-in sources and cache raw responses under data/."""
    api_key = load_env_var("OPENWEATHERMAP_API_KEY")
    if not api_key:
        raise RuntimeError("OPENWEATHERMAP_API_KEY not found in ~/.claude/.env")

    current = fetch_current_weather(city, api_key)
    save_snapshot("current_weather", current)

    forecast = fetch_forecast(city, api_key)
    save_snapshot("forecast", forecast)

    kp = fetch_kp_index()
    save_snapshot("kp_index", kp)

    solar_wind = fetch_solar_wind()
    save_snapshot("solar_wind", solar_wind)

    coord = current.get("coord", {})
    aurora = fetch_aurora(coord.get("lat", 0), coord.get("lon", 0))
    save_snapshot("aurora", aurora)

    schumann = fetch_schumann()
    save_snapshot("schumann", schumann)

    natural_events = fetch_natural_events()
    save_snapshot("natural_events", natural_events)

    earthquakes = fetch_significant_earthquakes()
    save_snapshot("earthquakes", earthquakes)

    news = fetch_news_frequency()
    save_snapshot("news_frequency", news)

    market = fetch_market_snapshot()
    save_snapshot("market", market)

    return {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "city": city,
        "current": current,
        "forecast": forecast,
        "kp": kp,
        "solar_wind": solar_wind,
        "aurora": aurora,
        "schumann": schumann,
        "natural_events": natural_events,
        "earthquakes": earthquakes,
        "news": news,
        "market": market,
    }
