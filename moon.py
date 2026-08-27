"""Moon phase — pure calculation from a known reference new moon, no API, no data file.

Accurate to within roughly a day, which is plenty for a dashboard tile.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

SYNODIC_MONTH_DAYS = 29.530588853
KNOWN_NEW_MOON = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)

# (fraction-of-cycle threshold, name) — walked in order, last match wins.
PHASE_NAMES = [
    (0.00, "Новолуние"),
    (0.03, "Растущий серп"),
    (0.22, "Первая четверть"),
    (0.28, "Растущая луна"),
    (0.47, "Полнолуние"),
    (0.53, "Убывающая луна"),
    (0.72, "Последняя четверть"),
    (0.78, "Убывающий серп"),
    (0.97, "Новолуние"),
]


def phase_name(fraction: float) -> str:
    name = PHASE_NAMES[0][1]
    for threshold, label in PHASE_NAMES:
        if fraction >= threshold:
            name = label
        else:
            break
    return name


def compute(when: datetime | None = None) -> dict:
    when = when or datetime.now(timezone.utc)
    days_since = (when - KNOWN_NEW_MOON).total_seconds() / 86400
    age_days = days_since % SYNODIC_MONTH_DAYS
    fraction = age_days / SYNODIC_MONTH_DAYS  # 0..1, 0/1=new, 0.5=full
    illumination = (1 - math.cos(2 * math.pi * fraction)) / 2  # 0..1 approximation

    return {
        "date": when.isoformat(),
        "age_days": round(age_days, 1),
        "fraction": round(fraction, 4),
        "illumination_pct": round(illumination * 100, 1),
        "phase_name": phase_name(fraction),
    }
