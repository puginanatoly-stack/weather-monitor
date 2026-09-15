---
name: HazardMap
version: 1.0.0
description: Builds a real-geodata hazard/safety map for any location — real elevation grid, verified high ground, and pedestrian walking-time isochrones, overlaid on a real street map and published as an artifact. USE WHEN tsunami evacuation map, flood risk map, elevation map, where is high ground, walking time to safety, isochrone map, disaster evacuation planning, safe zone visualization. NOT FOR abstract diagrams/flowcharts with no real geography (use Mermaid, Drawio, or Excalidraw), NOT FOR decorative or illustrative maps (use Art).
---

# HazardMap

Turns "is this place safe, and how far to safety" into a map backed by real, checkable data: an elevation grid (not a guess), a verified high point (not the nearest road), and pedestrian isochrones computed by an actual routing engine (not a hand-drawn radius).

## Customization

**Before executing, check for user customizations at:**
`~/.claude/LIFEOS/USER/CUSTOMIZATIONS/SKILLS/HazardMap/`

If this directory exists, load and apply `PREFERENCES.md` (e.g. a preferred color palette, a default hazard type, a home region to geocode against). If it does not exist, proceed with skill defaults.

## Voice Notification

**When executing a workflow, do BOTH:**

1. **Send voice notification**:
   ```bash
   curl -s -X POST http://localhost:31337/notify \
     -H "Content-Type: application/json" \
     -d '{"message": "Running the BuildHazardMap workflow in the HazardMap skill to map real elevation and walking-time safety"}' \
     > /dev/null 2>&1 &
   ```

2. **Output text notification**:
   ```
   Running the **BuildHazardMap** workflow in the **HazardMap** skill to ACTION...
   ```

**Full documentation:** `~/.claude/LIFEOS/DOCUMENTATION/Notifications/NotificationSystem.md`

## Workflow Routing

| Workflow | Trigger | File |
|----------|---------|------|
| **BuildHazardMap** | "build a [hazard] map for [place]", "where's high ground near X", "evacuation map", "isochrone map from a safe point" | `Workflows/BuildHazardMap.md` |

## Quick Reference

- **The whole pipeline runs on free, keyless public APIs** — Nominatim (geocoding), Open-Meteo (elevation), Valhalla (pedestrian isochrones), Wikimedia Maps (basemap tiles). No account, no API key, no billing.
- **Never guess the "safe point."** Sample real elevation first; pick the safe point from verified data, not from a road that happens to be nearby (a point can be close to a hazard in walking time and still be adjacent to the hazard itself).
- **Never guess walking time from straight-line distance.** Terrain and road networks make actual walking time diverge sharply from distance — compute it with the routing engine, every time.
- Full API contracts, parameters, and every discovered gotcha: `ApiReference.md`.
- Deterministic lat/lon → pixel projection (do not hand-derive this): `Tools/GeoProject.ts`.

## Examples

**Example 1: Coastal hazard map**
```
User: "Build a tsunami evacuation map for [coastal town]"
→ Invokes BuildHazardMap workflow
→ Geocodes the town, samples a real elevation grid around it, finds the nearest genuinely high point
→ Computes pedestrian isochrones from that point (not from the beach or a nearby road)
→ Publishes an HTML artifact: real basemap + elevation heatmap + isochrone bands + verified high-ground markers + Google Maps walking-route links
```

**Example 2: "Where's actually high ground near here"**
```
User: "Where's the nearest real high ground to [address], and how long to walk there?"
→ Invokes BuildHazardMap workflow
→ Samples elevation grid, ranks candidate high points by elevation and proximity
→ Reports the verified best candidate with its real elevation and a computed (not estimated) walking time
```

## Gotchas

- **Valhalla's free public isochrone endpoint caps pedestrian contours at 60 minutes** (`error_code 151, "Exceeded max time: 60"`). Never request beyond 60; if the user wants "up to 90 minutes," request the maximum (60) and say so explicitly rather than silently truncating or fabricating the outer band.
- **curl on Windows can fail TLS entirely against some hosts while the same host works fine elsewhere** — a Windows-schannel-specific handshake failure (`SEC_E_ILLEGAL_MESSAGE`), not a real network block. Symptom: `curl -v` shows the connection resolve and then die at `InitializeSecurityContext`. Fix: retry the exact same request with Node's built-in `fetch` (different TLS stack) before concluding the service is unreachable.
- **A "safe point" chosen because it's close in walking time is not the same as a safe point** — a spot 150 m from a shoreline is barely safer than the shoreline itself, even if it is the fastest point to reach. Sample real elevation before designating anything "the safe point," and verify the elevation of ANY candidate before trusting it — "further inland" is not a reliable proxy for "higher"; a spot 1 km inland measured 7 m, well below a nearby 75 m peak only slightly farther away.
- **Straight-line distance is not walking time.** A point 1.2 km away by straight line took 57 real minutes to walk to because no direct path existed around the terrain feature between them — the routing engine had to detour around it entirely. Always compute isochrones/routes with the actual routing engine; never present a distance-based estimate as if it were a time estimate.
- **Wikimedia Maps' static render endpoint (`maps.wikimedia.org`) 403s a bare/generic User-Agent.** Send a descriptive one (tool name + contact), per Wikimedia's API etiquette — it then returns 200 normally.
- **Open-Meteo's elevation endpoint rate-limits large sequential batch requests (HTTP 429) after several dozen back-to-back calls.** Batch at ~50-100 coordinates per request, add a short delay between batches, and retry-with-backoff on 429 — never fail the whole grid because one batch got throttled; save progress incrementally so a late failure doesn't lose earlier batches.
- **A single sampled point can undershoot a summit by a wide margin** — one elevation query near a place commonly cited as "~60 m" returned 49 m at the exact coordinate tried. Don't treat one sample as the summit; if precision matters, sample a small local grid around the candidate and take the maximum.
- **`mix-blend-mode: multiply` on an SVG overlay group reads far better than flat opacity** for a color layer sitting on top of a map — it keeps the basemap's road lines and labels legible underneath a color-coded layer instead of just fading everything uniformly. Pair with pastel (whitened) fill colors, not saturated ones — blend each hazard color toward white (40–50%) before using it as a map overlay fill.

## Output Requirements

- **Format:** Self-contained HTML artifact (inline SVG map + a short methodology/sources section) — never a bare image with no caption or source trail.
- **Must include:** the coordinates and elevation of the designated safe point, a note on how it was chosen, the isochrone time bands actually computed (not implied), and links to the primary data sources used.
- **Must avoid:** presenting any modeled or estimated figure without labeling it as such; silently treating "closer" as "safer" without checking elevation.
