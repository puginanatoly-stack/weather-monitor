"""Builds the 4-tab site: index.html (Сейчас) / space-weather.html / moon.html / events.html.

Run:
    python build.py [город]

City resolution order: CLI arg > WEATHER_CITY env var > DEFAULT_CITY (a
generic placeholder — this repo is public, so no real city is hardcoded
here; the scheduled workflow supplies the real one via a repo secret).

Each run appends one row to data/history.jsonl and writes
data/latest_summary.json (consumed by notify.py) — both stay untracked in
this repo (.gitignore); the workflow syncs history.jsonl to a private repo
instead, since a public git history would otherwise leak the query city and
usage pattern over time.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import composite
import moon
import pages
import templates
from sources import append_history, collect, read_history

OUT_DIR = Path(__file__).parent
DATA_DIR = OUT_DIR / "data"
DEFAULT_CITY = "London,GB"  # generic placeholder — see module docstring


def build(city: str) -> None:
    data = collect(city)
    moon_data = moon.compute()

    sw_rows = data.get("solar_wind", [])
    latest_kp = data["kp"][-1]["Kp"] if data.get("kp") else None
    latest_sw_speed = sw_rows[-1].get("proton_speed") if sw_rows else None
    aurora_pct = data.get("aurora", {}).get("probability")
    index = composite.compute_index(latest_kp, latest_sw_speed, aurora_pct, data.get("schumann"))

    market = data.get("market", [])
    abs_changes = [abs(m["change_pct"]) for m in market if m.get("change_pct") is not None]
    avg_volatility = sum(abs_changes) / len(abs_changes) if abs_changes else None
    news_total = data.get("news", {}).get("total_recent")

    append_history({
        "ts": datetime.now(timezone.utc).isoformat(),
        "city": city,
        "moon_phase": moon_data.get("phase_name"),
        "moon_illumination_pct": moon_data.get("illumination_pct"),
        "kp": latest_kp,
        "solar_wind_speed": latest_sw_speed,
        "aurora_pct": aurora_pct,
        "index_score": index.get("score"),
        "index_level": index.get("level"),
        "events_count": len(data.get("natural_events", [])),
        "quakes_count": len(data.get("earthquakes", [])),
        "news_count": news_total,
        "market_volatility_pct": avg_volatility,
    })
    history = read_history()

    # Historical averages, excluding this run's own just-appended row, for
    # notify.py's relative-threshold checks.
    past = history[:-1]
    past_news = [r["news_count"] for r in past if isinstance(r.get("news_count"), (int, float))]
    past_vol = [r["market_volatility_pct"] for r in past if isinstance(r.get("market_volatility_pct"), (int, float))]

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "latest_summary.json").write_text(
        json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "city": city,
            "index_score": index.get("score"),
            "index_level": index.get("level"),
            "kp": latest_kp,
            "solar_wind_speed": latest_sw_speed,
            "moon_phase": moon_data.get("phase_name"),
            "market_volatility_pct": avg_volatility,
            "news_count": news_total,
            "history_sample_size": len(past),
            "history_avg_market_volatility_pct": sum(past_vol) / len(past_vol) if past_vol else None,
            "history_avg_news_count": sum(past_news) / len(past_news) if past_news else None,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (OUT_DIR / "index.html").write_text(
        templates.page_shell("Сейчас", "index.html", pages.render_now(data)), encoding="utf-8"
    )
    (OUT_DIR / "space-weather.html").write_text(
        templates.page_shell("Космическая погода", "space-weather.html", pages.render_space_weather(data)),
        encoding="utf-8",
    )
    (OUT_DIR / "moon.html").write_text(
        templates.page_shell("Луна", "moon.html", pages.render_moon(moon_data)), encoding="utf-8"
    )
    (OUT_DIR / "events.html").write_text(
        templates.page_shell("События", "events.html", pages.render_events(data, moon_data, index, history)),
        encoding="utf-8",
    )
    print(f"OK: 4 HTML files -> {OUT_DIR} (history: {len(history)} rows, index: {index.get('level')} {index.get('score')})")


def main() -> None:
    city = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("WEATHER_CITY", DEFAULT_CITY)
    build(city)


if __name__ == "__main__":
    main()
