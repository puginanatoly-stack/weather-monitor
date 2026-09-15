# HazardMap — API Reference

Exact contracts for the four free, keyless services this skill chains together. Every parameter and gotcha below was hit in practice — treat this as ground truth over memory.

## 1. Nominatim (geocoding) — verify names and coordinates

```
GET https://nominatim.openstreetmap.org/search?q=<place name>&format=json&limit=3
```

- Requires a descriptive `User-Agent` header (name + contact), e.g. `MyProject/1.0 (contact: you@example.com)`. A generic/absent one risks a block under OSM's usage policy.
- Use this to **cross-check** any coordinate a web search hands back before trusting it — search-engine summaries can silently merge two same-named places (e.g. two unrelated landmarks sharing a generic name like "Peace Pagoda") into one wrong coordinate. Nominatim resolving to a materially different location than what a search summary claimed is a real signal the summary was wrong, not the geocoder.
- Response: JSON array with `lat`, `lon` (strings), `display_name`, `boundingbox`.

## 2. Open-Meteo Elevation API — real elevation grid

```
GET https://api.open-meteo.com/v1/elevation?latitude=<lat1,lat2,...>&longitude=<lon1,lon2,...>
```

- No key. Latitude/longitude are **parallel comma-separated lists**, same length, matched by index.
- Returns `{"elevation": [n1, n2, ...]}` in meters.
- **Batch limit in practice:** requests of ~100 points work; large sequential runs (500+) start returning `HTTP 429` after several dozen batches. Use batches of 50–100, add a ~1–1.5s delay between batches, and retry with backoff (a few seconds, growing) on 429. Save results incrementally after each successful batch so a late rate-limit doesn't discard earlier work.
- **Grid strategy:** build a rectangular lat/lon grid over the area of interest (e.g. 25–30 columns × 18–22 rows for a several-km area is enough resolution to find real local high points without excessive request volume). Sort the results by elevation descending to find candidates; then sample a tighter local grid (10–20 points, ~100 m spacing) around the top candidate to pinpoint the actual peak — a single coarse-grid point can undershoot the true local maximum by a wide margin.

## 3. Valhalla (pedestrian isochrones + routing) — real walking-time areas

Public demo instance: `https://valhalla1.openstreetmap.de` (verify it's still live before relying on it in a new session — public demo instances can change).

```
POST https://valhalla1.openstreetmap.de/isochrone
Content-Type: application/json

{
  "locations": [{"lat": <lat>, "lon": <lon>}],
  "costing": "pedestrian",
  "contours": [{"time": 15, "color": "1f8f4e"}, {"time": 40, "color": "bd7a1f"}, {"time": 60, "color": "b2352b"}],
  "polygons": true,
  "denoise": 0.3,
  "generalize": 15
}
```

- **Hard server-side cap: 60 minutes for pedestrian contours.** Requesting `{"time": 90}` returns `{"error_code":151,"error":"Exceeded max time: 60","status_code":400}`. Never request above 60; if a wider band is wanted, say the 60-minute contour is the outer limit the free service will compute, don't quietly cap it without telling the user.
- Response is GeoJSON: `features[].geometry.coordinates[0]` is a ring of `[lon, lat]` pairs (note: **lon, lat order**, not lat, lon) per requested contour, tagged by `features[].properties.contour`.
- `denoise` (0–1) and `generalize` (meters) smooth the polygon; without them the ring can have thousands of jagged points from the underlying road-network graph.
- A single point-to-point walking route (for a real Google-Maps-style comparison) doesn't need this API — see § 5.

## 4. Wikimedia Maps (static basemap render) — the actual street map image

```
GET https://maps.wikimedia.org/img/osm-intl,<zoom>,<lat>,<lon>,<width>x<height>.png
```

- **A generic or missing `User-Agent` gets HTTP 403.** Send a descriptive one, same as Nominatim — the request succeeds immediately once it's present.
- `zoom` follows standard slippy-map levels (higher = more detail, smaller area per pixel). Zoom 14–15 comfortably covers a several-km hazard/isochrone area at readable street-label resolution; go up a level for a tighter, more legible crop once the area of interest is known.
- `lat,lon` is the image **center**, not a corner.
- This is a rendered PNG, not tiles — fetch once at the final center/zoom/size you intend to use as the artifact's base image; refetching after changing the crop is normal and expected, not a sign something went wrong.

## 5. Google Maps — real routable links, no API key needed

For a genuine, user-clickable point-to-point walking route (as a sanity check against the isochrones, or as a deliverable itself):

```
https://www.google.com/maps/dir/?api=1&origin=<lat>,<lon>&destination=<lat>,<lon>&travelmode=walking
```

This opens Google's own router — it costs nothing to construct and needs no key, but it is **not** something this skill can call programmatically to extract a duration; it is a link for the user to open. Never assert a walking-time number from this link without the user (or a prior verified click) actually reporting what it showed — presenting an un-clicked estimate as fact reproduces the exact "assumed proximity = safety" mistake this skill exists to avoid.

## Projection math (tie the above together on one image)

All the above return real-world `lat,lon`. To draw them on the fetched basemap PNG, project each coordinate to pixel space with standard Web Mercator, matched to the exact `zoom`/center/width/height used for the basemap fetch in § 4. Don't hand-derive this per session — use `Tools/GeoProject.ts`, which implements and validates this projection (a center-point round-trip check catches sign/offset errors before they propagate into every marker on the map).
