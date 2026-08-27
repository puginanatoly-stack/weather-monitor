"""Composite 'activity index' — one 0-100 number blending every space-weather
source we have, kept as its own module (not inlined in pages.py) because the
principal plans to compare it against other data later — it needs a stable,
testable function, not page-rendering logic.

Weighting is a judgment call, documented inline — adjust WEIGHTS once real
data accumulates and the balance feels off. Kp gets the most weight (most
authoritative, always available); solar wind next (real-time NOAA feed,
always available); aurora and Schumann get less — aurora because a single
mid-latitude point is a narrow, often-near-zero signal, Schumann because the
only available source is unofficial and frequently stale.

A source that's missing or stale (Schumann's `is_ok: False`) is dropped from
the blend and the remaining weights are renormalized — never filled with a
guessed/nominal value, so the score never silently leans on data it doesn't
actually have.
"""

from __future__ import annotations

WEIGHTS = {
    "kp": 0.45,
    "solar_wind": 0.30,
    "aurora": 0.10,
    "schumann": 0.15,
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def kp_component(kp: float | None) -> float | None:
    if kp is None:
        return None
    return _clamp01(kp / 9.0) * 100


def solar_wind_component(speed_km_s: float | None) -> float | None:
    """300 km/s ~ quiet solar wind, 700 km/s ~ storm-level — both fairly standard reference points."""
    if speed_km_s is None:
        return None
    return _clamp01((speed_km_s - 300) / (700 - 300)) * 100


def aurora_component(probability_pct: float | None) -> float | None:
    if probability_pct is None:
        return None
    return _clamp01(probability_pct / 100) * 100


def schumann_component(schumann: dict | None) -> float | None:
    """Only contributes when the source itself reports live data (`is_ok`).

    Uses SR1's deviation from its 7.83 Hz nominal as the activity signal —
    a 2 Hz deviation is treated as "fully active"; this is a rough heuristic,
    not a scientifically standardized scale, since the source doesn't publish
    one.
    """
    if not schumann or not schumann.get("is_ok"):
        return None
    freqs = schumann.get("frequencies") or []
    sr1 = next((f for f in freqs if f.get("id") == "SR1"), None)
    if not sr1 or sr1.get("value") is None or sr1.get("nominal") is None:
        return None
    deviation = abs(sr1["value"] - sr1["nominal"])
    return _clamp01(deviation / 2.0) * 100


def level_for(score: float) -> str:
    if score < 25:
        return "Спокойно"
    if score < 50:
        return "Активно"
    return "Буря"


def compute_index(
    kp: float | None,
    solar_wind_speed: float | None,
    aurora_pct: float | None,
    schumann: dict | None,
) -> dict:
    """Weighted blend of every available component, renormalized over what's present.

    Returns {"score": 0-100 or None, "level": str, "components": {...}, "weight_used": {...}}.
    `components` keeps every per-source 0-100 value (or None) so a page or a
    future comparison can inspect the breakdown, not just the final number.
    """
    components = {
        "kp": kp_component(kp),
        "solar_wind": solar_wind_component(solar_wind_speed),
        "aurora": aurora_component(aurora_pct),
        "schumann": schumann_component(schumann),
    }
    available = {k: v for k, v in components.items() if v is not None}
    if not available:
        return {"score": None, "level": "—", "components": components, "weight_used": {}}

    weight_sum = sum(WEIGHTS[k] for k in available)
    score = sum(WEIGHTS[k] * v for k, v in available.items()) / weight_sum

    return {
        "score": round(score, 1),
        "level": level_for(score),
        "components": components,
        # Normalized so these sum to 1.0 — "how much this source actually
        # counted toward the final score," not the raw table above.
        "weight_used": {k: round(WEIGHTS[k] / weight_sum, 3) for k in available},
    }
