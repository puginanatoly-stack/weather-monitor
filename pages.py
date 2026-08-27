"""Page bodies for each tab — Now / Space Weather / Moon / Events.

Each render_* function returns only the <body> content for its tab;
templates.page_shell() wraps it with the shared nav/head/footer.
"""

from __future__ import annotations

from datetime import datetime

import composite
from charts import badge_class, kp_to_level, ring_legend, svg_bar_chart, svg_line_chart, svg_ring_gauge


def render_now(data: dict) -> str:
    current = data["current"]
    kp_rows = data["kp"]

    temp = current["main"]["temp"]
    feels = current["main"]["feels_like"]
    humidity = current["main"]["humidity"]
    pressure = current["main"]["pressure"]
    wind = current["wind"]["speed"]
    clouds = current.get("clouds", {}).get("all", 0)
    visibility_km = current.get("visibility", 0) / 1000
    desc = current["weather"][0]["description"]
    city_name = current.get("name") or data["city"]

    sunrise_ts = current.get("sys", {}).get("sunrise")
    sunset_ts = current.get("sys", {}).get("sunset")
    sunrise = datetime.fromtimestamp(sunrise_ts).strftime("%H:%M") if sunrise_ts else "—"
    sunset = datetime.fromtimestamp(sunset_ts).strftime("%H:%M") if sunset_ts else "—"

    kp_recent = kp_rows[-40:]
    latest_row = kp_recent[-1] if kp_recent else None
    latest_kp = latest_row["Kp"] if latest_row else None
    _kp_badge_word, kp_level_full = kp_to_level(latest_kp) if latest_kp is not None else ("Спокойно", "—")

    sw_rows = data.get("solar_wind", [])
    latest_sw_speed = sw_rows[-1].get("proton_speed") if sw_rows else None
    aurora_pct = data.get("aurora", {}).get("probability")
    schumann = data.get("schumann")

    # The integral indicator — this is what the ring gauge and center status
    # word represent, not just Kp. See composite.py for the weighting.
    index = composite.compute_index(latest_kp, latest_sw_speed, aurora_pct, schumann)
    comps = index["components"]

    rings = [
        ("Kp", comps["kp"] or 0, 100, "var(--storm)" if (comps["kp"] or 0) >= 50 else "var(--calm)"),
        ("Солн. ветер", comps["solar_wind"] or 0, 100, "var(--accent2)"),
        ("Аврора", comps["aurora"] or 0, 100, "var(--accent3)"),
        ("Шуман", comps["schumann"] or 0, 100, "var(--ink-soft)"),
    ]
    center_label = index["level"].upper() if index["score"] is not None else "—"
    center_sub = f"{index['score']:.0f}/100" if index["score"] is not None else "нет данных"
    gauge_svg = svg_ring_gauge(rings, center_label, center_sub)
    legend_html = ring_legend(
        rings,
        fmt={"Kp": "{:.0f}", "Солн. ветер": "{:.0f}", "Аврора": "{:.0f}", "Шуман": "{:.0f}"},
    )

    fetched_at_local = datetime.fromisoformat(data["fetched_at"]).astimezone().strftime("%Y-%m-%d %H:%M")

    return f"""
  <h1>Сейчас — {city_name}</h1>
  <div class="meta">Обновлено: {fetched_at_local}</div>

  <div class="hero">
    {gauge_svg}
    <div>
      {legend_html}
      <div class="badges">
        <span class="badge {badge_class(index["level"])}">{index["level"]} — интегральный индекс</span>
        <span class="badge badge-active">Kp: {kp_level_full}</span>
        <span class="badge badge-active">{desc}</span>
      </div>
    </div>
  </div>

  <div class="cards">
    <div class="card"><div class="n">{temp:.0f}°C</div><div class="cap">сейчас, ощущается {feels:.0f}°C</div></div>
    <div class="card"><div class="n">{pressure} гПа</div><div class="cap">давление</div></div>
    <div class="card"><div class="n">{humidity}%</div><div class="cap">влажность</div></div>
    <div class="card"><div class="n">{wind:.0f} м/с</div><div class="cap">ветер</div></div>
    <div class="card"><div class="n">{clouds}%</div><div class="cap">облачность</div></div>
    <div class="card"><div class="n">{visibility_km:.0f} км</div><div class="cap">видимость</div></div>
    <div class="card"><div class="n">{sunrise} / {sunset}</div><div class="cap">восход / закат</div></div>
    <div class="card"><div class="n">{f"{latest_kp:.1f}" if latest_kp is not None else "—"}</div><div class="cap">Kp-индекс</div></div>
  </div>

  <section>
    <h2>Из чего состоит интегральный индекс</h2>
    <div class="panel sources">
      <div class="source-row"><span>Kp (геомагнитка)</span><span class="status">{f"вес {index['weight_used'].get('kp', 0):.0%}" if 'kp' in index['weight_used'] else "недоступно"}</span></div>
      <div class="source-row"><span>Солнечный ветер</span><span class="status">{f"вес {index['weight_used'].get('solar_wind', 0):.0%}" if 'solar_wind' in index['weight_used'] else "недоступно"}</span></div>
      <div class="source-row"><span>Аврора (в этой точке)</span><span class="status">{f"вес {index['weight_used'].get('aurora', 0):.0%}" if 'aurora' in index['weight_used'] else "недоступно"}</span></div>
      <div class="source-row"><span>Резонанс Шумана</span><span class="status">{f"вес {index['weight_used'].get('schumann', 0):.0%}" if 'schumann' in index['weight_used'] else "исключён (источник stale)"}</span></div>
    </div>
    <p style="margin:10px 0 0;color:var(--ink-soft);font-size:.82rem">Веса перераспределяются на доступные источники — если Шуман недоступен, его доля уходит остальным трём, а не подставляется наугад. Подробности каждого источника — на вкладке «Космическая погода».</p>
  </section>

  <section>
    <h2>Источники</h2>
    <div class="panel sources">
      <div class="source-row"><a href="https://openweathermap.org" target="_blank" rel="noopener">OpenWeatherMap</a><span class="status">погода · обновлено {fetched_at_local}</span></div>
      <div class="source-row"><a href="https://www.spaceweather.gov" target="_blank" rel="noopener">NOAA SWPC</a><span class="status">Kp/Ap, солнечный ветер, аврора · без ключа</span></div>
      <div class="source-row"><a href="https://schumannresonancelive.com" target="_blank" rel="noopener">Schumann Resonance Live</a><span class="status">неофициальный источник</span></div>
    </div>
  </section>
"""


def render_space_weather(data: dict) -> str:
    kp_rows = data["kp"]
    kp_recent = kp_rows[-56:]  # ~7 days at 3h steps
    kp_points = [(row["time_tag"][5:10], row["Kp"]) for row in kp_recent]
    ap_points = [(row["time_tag"][5:10], row["a_running"]) for row in kp_recent]
    latest_row = kp_recent[-1] if kp_recent else None
    latest_kp = latest_row["Kp"] if latest_row else None
    latest_ap = latest_row["a_running"] if latest_row else None
    _badge_word, kp_level_full = kp_to_level(latest_kp) if latest_kp is not None else ("Спокойно", "—")

    kp_chart = svg_bar_chart(kp_points, max_v=9.0, threshold=5.0)
    ap_chart = svg_line_chart(ap_points, color="#3d6e63", unit="")

    fetched_at_local = datetime.fromisoformat(data["fetched_at"]).astimezone().strftime("%Y-%m-%d %H:%M")

    # solar wind
    sw_rows = data.get("solar_wind", [])
    latest_sw = sw_rows[-1] if sw_rows else {}
    sw_speed = latest_sw.get("proton_speed")
    sw_density = latest_sw.get("proton_density")
    sw_temp = latest_sw.get("proton_temperature")
    sw_points = [
        (row["time_tag"][11:16], row["proton_speed"])
        for row in sw_rows
        if row.get("proton_speed") is not None
    ]
    sw_chart = svg_line_chart(sw_points, color="#8a5a2e", unit=" км/с") if sw_points else "<p>Нет данных.</p>"

    # aurora
    aurora = data.get("aurora", {})
    aurora_prob = aurora.get("probability")

    # schumann — never present stale numbers as if they were live
    schumann = data.get("schumann", {})
    sch_ok = schumann.get("is_ok", False)
    sch_badge_class = "badge-calm" if sch_ok else "badge-storm"
    sch_status_text = schumann.get("status_label", "—")
    sch_freq_rows = "".join(
        f'<div class="source-row"><span>{f["id"]} — {f["value"]} Гц (номинал {f["nominal"]} Гц)</span>'
        f'<span class="status">{"измерено" if f.get("measured") else "не измерено (справочное)"}</span></div>'
        for f in schumann.get("frequencies", [])[:5]
    )

    return f"""
  <h1>Космическая погода</h1>
  <div class="meta">Обновлено: {fetched_at_local}</div>

  <div class="cards">
    <div class="card"><div class="n">{f"{latest_kp:.1f}" if latest_kp is not None else "—"}</div><div class="cap">Kp-индекс сейчас</div></div>
    <div class="card"><div class="n">{f"{latest_ap:.0f}" if latest_ap is not None else "—"}</div><div class="cap">Ap (running)</div></div>
    <div class="card"><div class="n">{kp_level_full}</div><div class="cap">статус</div></div>
    <div class="card"><div class="n">{f"{sw_speed:.0f} км/с" if sw_speed is not None else "—"}</div><div class="cap">солнечный ветер</div></div>
    <div class="card"><div class="n">{f"{aurora_prob}%" if aurora_prob is not None else "—"}</div><div class="cap">аврора (здесь)</div></div>
  </div>

  <section>
    <h2>Kp-индекс — 7 дней</h2>
    <div class="panel">{kp_chart}</div>
  </section>

  <section>
    <h2>Ap (running) — 7 дней</h2>
    <div class="panel">{ap_chart}</div>
  </section>

  <section>
    <h2>Солнечный ветер — скорость (последние часы)</h2>
    <div class="panel">
      {sw_chart}
      <p style="margin:12px 0 0;color:var(--ink-soft);font-size:.85rem">Плотность: {f"{sw_density:.2f} прот/см³" if sw_density is not None else "—"} · Температура: {f"{sw_temp:,.0f} K" if sw_temp is not None else "—"}</p>
    </div>
  </section>

  <section>
    <h2>Аврора — вероятность в этой точке</h2>
    <div class="panel">
      <p style="margin:0 0 6px;font-size:1.1rem;font-weight:700">{f"{aurora_prob}%" if aurora_prob is not None else "—"}</p>
      <p style="margin:0;color:var(--ink-soft);font-size:.85rem">Модель OVATION, сетка ~1°, точка [{aurora.get('lat', '—')}, {aurora.get('lon', '—')}] · прогноз на {aurora.get('forecast_time', '—')}</p>
    </div>
  </section>

  <section>
    <h2>Резонанс Шумана
      <span class="badge {sch_badge_class}" style="margin-left:8px;vertical-align:middle">{sch_status_text}</span>
    </h2>
    <div class="panel sources">
      <div class="source-row"><span>Интенсивность</span><span class="status">{schumann.get("intensity", "—")}</span></div>
      {sch_freq_rows}
    </div>
    {"" if sch_ok else '<p style="margin:8px 0 0;color:var(--storm);font-size:.82rem">Источник сейчас не отдаёт живые измерения — значения выше справочные (номинальные), не текущие показания.</p>'}
  </section>

  <section>
    <h2>Шкала G (NOAA)</h2>
    <div class="panel">
      <p style="margin:0;color:var(--ink-soft);font-size:.9rem">Kp &lt; 5 — спокойно/неустойчиво · Kp 5 — G1 слабая буря · Kp 6 — G2 умеренная · Kp 7 — G3 сильная · Kp 8 — G4 очень сильная · Kp 9 — G5 экстремальная.</p>
    </div>
  </section>

  <section>
    <h2>Источники</h2>
    <div class="panel sources">
      <div class="source-row"><a href="https://www.spaceweather.gov" target="_blank" rel="noopener">NOAA SWPC — Kp/Ap</a><span class="status">без ключа</span></div>
      <div class="source-row"><a href="https://www.spaceweather.gov" target="_blank" rel="noopener">NOAA SWPC — солнечный ветер (rtsw)</a><span class="status">без ключа</span></div>
      <div class="source-row"><a href="https://www.spaceweather.gov" target="_blank" rel="noopener">NOAA SWPC — аврора (OVATION)</a><span class="status">без ключа</span></div>
      <div class="source-row"><a href="https://schumannresonancelive.com" target="_blank" rel="noopener">Schumann Resonance Live</a><span class="status">неофициальный источник, бывает stale</span></div>
    </div>
  </section>
"""


def render_moon(moon_data: dict) -> str:
    illum = moon_data["illumination_pct"]
    phase = moon_data["phase_name"]
    age = moon_data["age_days"]

    rings = [("Освещённость", illum, 100, "var(--accent3)")]
    gauge_svg = svg_ring_gauge(rings, f"{illum:.0f}%", phase, size=220)

    when_local = datetime.fromisoformat(moon_data["date"]).astimezone().strftime("%Y-%m-%d %H:%M")

    return f"""
  <h1>Луна</h1>
  <div class="meta">Рассчитано: {when_local}</div>

  <div class="hero">
    {gauge_svg}
    <div>
      <div class="ring-legend">
        <div class="ring-legend-item"><span class="dot" style="background:var(--accent3)"></span>Фаза: <b>{phase}</b></div>
        <div class="ring-legend-item"><span class="dot" style="background:var(--ink-soft)"></span>Возраст: <b>{age} дней</b></div>
        <div class="ring-legend-item"><span class="dot" style="background:var(--accent2)"></span>Освещённость: <b>{illum:.0f}%</b></div>
      </div>
      <div class="badges">
        <span class="badge badge-active">{phase}</span>
      </div>
    </div>
  </div>

  <section>
    <h2>Источник</h2>
    <div class="panel sources">
      <div class="source-row"><span style="color:var(--ink-soft)">Локальный расчёт</span><span class="status">синодический месяц 29.53059 дн., без API</span></div>
    </div>
  </section>
"""


def render_events(data: dict, moon_data: dict, index: dict, history: list[dict]) -> str:
    """Events tab — natural catastrophes (EONET + USGS), plus the growing
    history log this needs a bare eyeball comparison against moon/Kp/index."""
    events = data.get("natural_events", [])
    quakes = data.get("earthquakes", [])

    # events per day, from each event's most recent geometry date
    from collections import Counter

    day_counts: Counter[str] = Counter()
    for e in events:
        geom = e.get("geometry") or []
        if geom:
            day = geom[-1].get("date", "")[:10]
            if day:
                day_counts[day] += 1
    quake_day_counts: Counter[str] = Counter()
    for q in quakes:
        ts = q.get("properties", {}).get("time")
        if ts:
            day = datetime.fromtimestamp(ts / 1000, tz=None).strftime("%Y-%m-%d")
            quake_day_counts[day] += 1

    events_points = [(d[5:], c) for d, c in sorted(day_counts.items())]
    quake_points = [(d[5:], c) for d, c in sorted(quake_day_counts.items())]
    events_chart = svg_bar_chart(events_points, max_v=max((c for _, c in events_points), default=1), threshold=1e9) if events_points else "<p>Нет данных.</p>"
    quakes_chart = svg_bar_chart(quake_points, max_v=max((c for _, c in quake_points), default=1), threshold=1e9) if quake_points else "<p>Нет данных.</p>"

    event_rows = "".join(
        f'<div class="source-row"><a href="{e.get("link", "#")}" target="_blank" rel="noopener">{e["title"]}</a>'
        f'<span class="status">{e["categories"][0]["title"] if e.get("categories") else "—"} · {(e["geometry"][-1].get("date") or "—")[:10] if e.get("geometry") else "—"}</span></div>'
        for e in events[:10]
    )
    quake_rows = "".join(
        f'<div class="source-row"><a href="{q["properties"].get("url", "#")}" target="_blank" rel="noopener">{q["properties"].get("title", "—")}</a>'
        f'<span class="status">alert: {q["properties"].get("alert") or "—"} · {datetime.fromtimestamp(q["properties"]["time"] / 1000).strftime("%Y-%m-%d")}</span></div>'
        for q in quakes[:10]
    )

    history_rows = "".join(
        f'<div class="source-row"><span>{row.get("ts", "—")[:16]}</span>'
        f'<span class="status">Луна: {row.get("moon_phase", "—")} · Kp: {row.get("kp", "—")} · Индекс: {row.get("index_score", "—")} '
        f'· событий: {row.get("events_count", "—")} · землетр.: {row.get("quakes_count", "—")} · новостей: {row.get("news_count", "—")}</span></div>'
        for row in history[-10:][::-1]
    )
    if not history_rows:
        history_rows = '<div class="source-row"><span style="color:var(--ink-soft)">Пока пусто — накопится после нескольких запусков build.py</span></div>'

    # digital noise — headline volume as an indirect proxy for "shock events"
    # no clean structured API exists for; compared against the running
    # average from history once there's enough of it to mean something.
    news = data.get("news", {})
    news_total = news.get("total_recent", 0)
    news_window = news.get("window_hours", 3)
    news_feed_rows = "".join(
        f'<div class="source-row"><span>{name}</span><span class="status">{count if count >= 0 else "ошибка запроса"}</span></div>'
        for name, count in news.get("per_feed", {}).items()
    )
    past_news_counts = [r.get("news_count") for r in history[:-1] if isinstance(r.get("news_count"), (int, float))]
    if past_news_counts:
        avg_news = sum(past_news_counts) / len(past_news_counts)
        delta_pct = ((news_total - avg_news) / avg_news * 100) if avg_news else 0
        news_compare = f"среднее за {len(past_news_counts)} прошлых запусков: {avg_news:.0f} ({delta_pct:+.0f}%)"
    else:
        news_compare = "пока не с чем сравнивать — первый запуск"

    # market volatility — same "broad, shallow, indirect" logic as news noise
    market = data.get("market", [])
    market_row_parts = []
    for m in market:
        price_txt = f"{m['price']:.2f}" if m.get("price") is not None else "—"
        change_txt = f" ({m['change_pct']:+.2f}%)" if m.get("change_pct") is not None else ""
        market_row_parts.append(
            f'<div class="source-row"><span>{m["label"]}</span><span class="status">{price_txt}{change_txt}</span></div>'
        )
    market_rows = "".join(market_row_parts)
    abs_changes = [abs(m["change_pct"]) for m in market if m.get("change_pct") is not None]
    avg_volatility = sum(abs_changes) / len(abs_changes) if abs_changes else None

    fetched_at_local = datetime.fromisoformat(data["fetched_at"]).astimezone().strftime("%Y-%m-%d %H:%M")

    return f"""
  <h1>События</h1>
  <div class="meta">Обновлено: {fetched_at_local}</div>

  <div class="cards">
    <div class="card"><div class="n">{len(events)}</div><div class="cap">открытых природных событий (NASA EONET)</div></div>
    <div class="card"><div class="n">{len(quakes)}</div><div class="cap">значимых землетрясений за месяц (USGS)</div></div>
    <div class="card"><div class="n">{news_total}</div><div class="cap">заголовков за {news_window}ч (digital noise)</div></div>
    <div class="card"><div class="n">{f"{avg_volatility:.2f}%" if avg_volatility is not None else "—"}</div><div class="cap">средняя волатильность рынков</div></div>
    <div class="card"><div class="n">{moon_data.get("phase_name", "—")}</div><div class="cap">фаза Луны сейчас</div></div>
    <div class="card"><div class="n">{index.get("level", "—")}</div><div class="cap">интегральный индекс сейчас</div></div>
  </div>

  <section>
    <h2>Природные события — по дням (~20 дней, NASA EONET)</h2>
    <div class="panel">{events_chart}</div>
  </section>

  <section>
    <h2>Значимые землетрясения — по дням (~30 дней, USGS)</h2>
    <div class="panel">{quakes_chart}</div>
  </section>

  <section>
    <h2>Последние природные события</h2>
    <div class="panel sources">{event_rows or '<p style="margin:0;color:var(--ink-soft)">Нет данных.</p>'}</div>
  </section>

  <section>
    <h2>Последние значимые землетрясения</h2>
    <div class="panel sources">{quake_rows or '<p style="margin:0;color:var(--ink-soft)">Нет данных.</p>'}</div>
  </section>

  <section>
    <h2>Цифровой шум — заголовки за {news_window}ч</h2>
    <p style="margin:0 0 10px;color:var(--ink-soft);font-size:.9rem">Косвенный индикатор: не что случилось, а сколько вообще публикуется. {news_compare}.</p>
    <div class="panel sources">{news_feed_rows}</div>
  </section>

  <section>
    <h2>Рыночная волатильность — базовые индексы и валюты</h2>
    <p style="margin:0 0 10px;color:var(--ink-soft);font-size:.9rem">Намеренно широко и неглубоко — 5 базовых тикеров, дневное изменение, не торговая панель.</p>
    <div class="panel sources">{market_rows}</div>
  </section>

  <section>
    <h2>История для сравнения ({len(history)} запусков накоплено)</h2>
    <div class="panel sources">{history_rows}</div>
    <p style="margin:10px 0 0;color:var(--ink-soft);font-size:.82rem">Каждый запуск build.py дописывает одну строку в data/history.jsonl — луна/Kp/индекс/число событий/новостей на момент запуска. Реальная корреляция (не просто «на глаз») станет возможна, когда строк накопится достаточно — для этого build.py нужно гонять регулярно, а не разово.</p>
  </section>

  <section>
    <h2>Источники</h2>
    <div class="panel sources">
      <div class="source-row"><a href="https://eonet.gsfc.nasa.gov" target="_blank" rel="noopener">NASA EONET</a><span class="status">природные события · без ключа</span></div>
      <div class="source-row"><a href="https://earthquake.usgs.gov" target="_blank" rel="noopener">USGS Earthquake Hazards</a><span class="status">значимые землетрясения · без ключа</span></div>
      <div class="source-row"><span>BBC / Google News / Al Jazeera / RIA Novosti</span><span class="status">RSS, частота публикаций · без ключа</span></div>
      <div class="source-row"><span>Yahoo Finance chart API</span><span class="status">S&amp;P 500, VIX, MOEX, USD/RUB, EUR/USD · без ключа, нужен браузерный User-Agent</span></div>
    </div>
  </section>
"""
