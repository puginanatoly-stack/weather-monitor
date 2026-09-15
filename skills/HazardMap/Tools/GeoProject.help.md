# GeoProject.ts

Web Mercator lat/lon → pixel projection, matched to the same math slippy-map tile/render services use (Wikimedia Maps, OpenStreetMap tile servers, etc.). Use this instead of re-deriving the projection by hand — a single sign or offset error propagates into every marker placed on the map.

## Commands

### `point` — project one coordinate

```bash
bun GeoProject.ts point --lat 6.018 --lon 80.245 \
  --center-lat 6.020 --center-lon 80.2495 --zoom 15 --width 1100 --height 1150
```

Prints `{"x":445.1,"y":621.9}` to stdout.

### `batch` — project a list of points

Input file (`points.json`): a JSON array of objects with at least `lat` and `lon`. Any other fields (a `label`, an `elevation`) pass through unchanged.

```bash
bun GeoProject.ts batch --input points.json \
  --center-lat 6.020 --center-lon 80.2495 --zoom 15 --width 1100 --height 1150
```

### `geojson` — convert polygon features to SVG paths

For isochrone or hazard-zone GeoJSON (e.g. a Valhalla `/isochrone` response): reads `features[].geometry.coordinates[0]` (a `[lon, lat]` ring per GeoJSON spec) and emits one SVG `d` path string per feature, in the same order, carrying `properties` through so you can pick fill/stroke by e.g. `properties.contour`.

```bash
bun GeoProject.ts geojson --input isochrone.geojson \
  --center-lat 6.020 --center-lon 80.2495 --zoom 15 --width 1100 --height 1150
```

Output: `[{"properties":{"contour":15,...},"d":"M...Z"}, ...]`

## Flags

| Flag | Required | Meaning |
|------|----------|---------|
| `--center-lat`, `--center-lon` | always | The coordinate the basemap image is centered on — must match exactly what was used to fetch the basemap PNG |
| `--zoom` | always | Slippy-map zoom level used for the basemap fetch |
| `--width`, `--height` | always | Basemap image pixel dimensions |
| `--decimals` | no (default 1) | Rounding precision for output coordinates |
| `--lat`, `--lon` | `point` only | The coordinate to project |
| `--input` | `batch`/`geojson` only | Path to the input JSON/GeoJSON file |

## Sanity check (always printed to stderr)

Every invocation prints the projected pixel position of the center coordinate itself, which must equal `(width/2, height/2)`. If it doesn't, the `--center-lat`/`--center-lon`/`--zoom`/`--width`/`--height` you passed don't match the basemap you actually fetched — fix that before trusting any other output from this run.

## Gotcha

GeoJSON coordinate order is `[longitude, latitude]`, the reverse of how people normally say coordinates aloud. The `geojson` command handles this internally — but if you're reading a GeoJSON file's raw coordinates yourself for any other reason, don't transpose them.
