# BuildHazardMap Workflow

## Voice Notification

```bash
curl -s -X POST http://localhost:31337/notify \
  -H "Content-Type: application/json" \
  -d '{"message": "Running the BuildHazardMap workflow in the HazardMap skill to map real elevation and walking-time safety"}' \
  > /dev/null 2>&1 &
```

Running the **BuildHazardMap** workflow in the **HazardMap** skill to build a real-geodata safety map...

## Step 0 — Sufficiency Check

Before building anything, confirm you actually have a located, scoped hazard question — not an abstract one:

1. A specific place (a name a geocoder can resolve, or coordinates already given).
2. A hazard/safety framing that implies "distance from what" (flood/tsunami → elevation and coastline; wildfire → distance from a fire perimeter and road egress; generic "how far to help" → the relevant facility).
3. If (1) or (2) is missing or ambiguous, ask directly rather than guessing a location or a hazard type — a wrong location silently produces a confident, wrong map.

If sufficient, proceed. If speculating on a minor detail (e.g. exact grid resolution), ship the best-effort version with a one-line flag on what was assumed.

## Deliverable

A published HTML artifact containing, at minimum:

1. **A real basemap** (not a schematic drawing) of the area, fetched at a location and zoom that legibly shows both the hazard area and the designated safe point(s).
2. **A verified safe point** — chosen from actual sampled elevation data, not from the nearest road or an assumption that "further away" means "higher." State its coordinates and elevation.
3. **Pedestrian isochrones from that verified point** (15/40/60-minute bands, or whatever bands make sense for the hazard), computed by a real routing engine — never a hand-drawn radius or a straight-line-distance estimate presented as time.
4. **A methodology and sources section** naming every API used and what came from it, so the map is auditable, not just pretty.
5. Where a genuine point-to-point comparison route is useful, real Google Maps walking-direction links (`ApiReference.md` § 5) — clearly marked as unclicked if you haven't verified them yourself, and updated to a confirmed time the moment a click result is reported back.

## Method

Full API contracts, parameters, and every discovered gotcha are in `../ApiReference.md` — read it before making any request; it documents real failure modes (rate limits, User-Agent 403s, the 60-minute isochrone cap, a Windows-curl TLS quirk) that are easy to misdiagnose as something else in the moment.

1. **Locate and verify.** Geocode the place name (Nominatim). If a coordinate came from a web search rather than a geocoder, cross-check it — search summaries can merge two same-named places into one wrong point.
2. **Sample real elevation** over the area of interest (Open-Meteo, batched). Don't assume "inland" or "away from the hazard" means "higher" — verify it. Rank results, then sample a tighter local grid around the top candidate to pinpoint the actual peak before calling it the safe point.
3. **Compute isochrones** from the verified safe point (Valhalla), not from an assumed-safe point picked by eye. If a distance-based intuition and the computed isochrone disagree, trust the isochrone and say so — that disagreement is itself worth surfacing to the user, not smoothing over.
4. **Fetch the basemap** (Wikimedia Maps) at a center/zoom/size that comfortably frames the hazard area, the safe point, and the isochrone extent together. Re-fetching at a tighter crop after seeing the first draft is normal.
5. **Project everything into one pixel space** with `../Tools/GeoProject.ts`, using the exact center/zoom/width/height the basemap was fetched at. Check the tool's own center-point sanity output before trusting anything else it produced.
6. **Compose the SVG overlay**: elevation heatmap as pastel (whitened 40-50%) fills in a group with `mix-blend-mode: multiply` at moderate opacity (map detail must stay legible underneath), isochrone bands as outlined contours (fill or stroke, not both heavily saturated — they'll fight the elevation layer for attention), star or pin markers on verified high points, a legend explaining every encoding used.
7. **Publish** as an HTML artifact (inline SVG, `<image>` reference to the fetched basemap as a supporting file) with the methodology section from the Deliverable list above.

## Gotchas

See `../ApiReference.md` and the skill-level `## Gotchas` in `../SKILL.md` — do not skip these; every one of them was a real, initially-misdiagnosed failure the first time it happened.
