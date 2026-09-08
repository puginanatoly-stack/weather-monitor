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


# Sri Lanka hazard index — deliberately separate from the space-weather blend
# above (Kp/solar wind/aurora/Schumann are irrelevant to a tropical island):
# scoped to what's actually relevant there, tropical cyclones and regional
# earthquakes with tsunami potential. Quake weighted higher — a distant but
# large quake is a bigger threat to Sri Lanka than a single storm sighting.
SRI_LANKA_WEIGHTS = {
    "quake": 0.6,
    "storm": 0.4,
}


def sl_quake_component(quakes_near: list[dict]) -> float:
    """Strongest nearby *recent* quake's magnitude mapped to 0-100.

    `quakes_near` is expected pre-filtered by sources.earthquakes_near()'s
    max_age_days (see SRI_LANKA_QUAKE_MAX_AGE_DAYS) — without that filter a
    single old quake sits in USGS's 30-day window and produces an unchanged
    score for weeks. M4.5 is used as the floor (~0) purely as a scoring
    anchor, scaling up to 100 at M7.5+ (roughly the class of the 2004 Sumatra
    quake) — the actual USGS feed queried is the curated "significant" one,
    which in practice only carries larger/notable events anyway.
    """
    if not quakes_near:
        return 0.0
    max_mag = max((q.get("properties", {}).get("mag") or 0) for q in quakes_near)
    return _clamp01((max_mag - 4.5) / (7.5 - 4.5)) * 100


def sl_storm_component(storms_near: list[dict]) -> float:
    """Step function, not linear — a single active cyclone in the basin is already the signal that matters."""
    n = len(storms_near)
    if n == 0:
        return 0.0
    if n == 1:
        return 55.0
    return 100.0


def compute_sri_lanka_index(quakes_near: list[dict], storms_near: list[dict]) -> dict:
    """Same blend shape as compute_index(), scoped to Sri Lanka-relevant hazards only.

    Returns {"score", "level", "components", "quakes_count", "quakes_max_mag",
    "nearest_quake_km", "nearest_quake_place", "storms_count"} — quakes_near/
    storms_near are expected pre-filtered by sources.earthquakes_near/storms_near.
    """
    components = {
        "quake": sl_quake_component(quakes_near),
        "storm": sl_storm_component(storms_near),
    }
    weight_sum = sum(SRI_LANKA_WEIGHTS[k] for k in components)
    score = sum(SRI_LANKA_WEIGHTS[k] * v for k, v in components.items()) / weight_sum
    nearest = quakes_near[0] if quakes_near else None

    return {
        "score": round(score, 1),
        "level": level_for(score),
        "components": components,
        "quakes_count": len(quakes_near),
        "quakes_max_mag": max((q.get("properties", {}).get("mag") or 0) for q in quakes_near) if quakes_near else None,
        "nearest_quake_km": nearest.get("distance_km") if nearest else None,
        "nearest_quake_place": nearest.get("properties", {}).get("place") if nearest else None,
        "storms_count": len(storms_near),
    }


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
