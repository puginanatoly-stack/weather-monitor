#!/usr/bin/env bun
/**
 * GeoProject.ts - Web Mercator lat/lon -> pixel projection for HazardMap overlays.
 *
 * Matches the projection used by standard slippy-map tile/render services (the
 * same math OpenStreetMap-based basemap renders use), so points project onto
 * the exact pixel position they occupy on a basemap PNG fetched at the same
 * center/zoom/width/height.
 *
 * Usage:
 *   bun GeoProject.ts point   --lat <n> --lon <n> --center-lat <n> --center-lon <n> --zoom <n> --width <n> --height <n>
 *   bun GeoProject.ts batch   --input points.json --center-lat <n> --center-lon <n> --zoom <n> --width <n> --height <n>
 *   bun GeoProject.ts geojson --input isochrone.geojson --center-lat <n> --center-lon <n> --zoom <n> --width <n> --height <n> [--decimals 1]
 *
 * batch input: JSON array of {"lat": n, "lon": n, ...} — extra fields are passed through.
 * geojson input: a FeatureCollection whose features are Polygons (e.g. a Valhalla
 *   isochrone response) — coordinates are [lon, lat] per GeoJSON spec.
 *
 * Every command prints a projection sanity check to stderr: the center point
 * must map to (width/2, height/2). If it doesn't, the center/zoom/width/height
 * you passed don't match reality — fix that before trusting any other output.
 *
 * @author LifeOS System
 * @version 1.0.0
 */

function printHelp() {
  console.log(`GeoProject.ts - lat/lon -> pixel projection for map overlays

Commands:
  point     Project a single lat/lon to pixel x,y
  batch     Project a JSON array of {lat,lon} points
  geojson   Convert GeoJSON polygon features to SVG path "d" strings

Common flags (all commands):
  --center-lat <n>   Latitude the basemap image is centered on
  --center-lon <n>   Longitude the basemap image is centered on
  --zoom <n>          Slippy-map zoom level used for the basemap fetch
  --width <n>         Basemap image width in pixels
  --height <n>        Basemap image height in pixels
  --decimals <n>      Round output to this many decimal places (default 1)

point:
  --lat <n> --lon <n>

batch / geojson:
  --input <path>      JSON (batch) or GeoJSON (geojson) file to read

Examples:
  bun GeoProject.ts point --lat 6.018 --lon 80.245 --center-lat 6.020 --center-lon 80.2495 --zoom 15 --width 1100 --height 1150
  bun GeoProject.ts geojson --input isochrone.geojson --center-lat 6.020 --center-lon 80.2495 --zoom 15 --width 1100 --height 1150
`);
}

function parseArgs(argv: string[]) {
  const args: Record<string, string> = {};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) {
      const key = argv[i].slice(2);
      const val = argv[i + 1];
      args[key] = val;
      i++;
    }
  }
  return args;
}

function worldPx(lat: number, lon: number, zoom: number): [number, number] {
  const worldSize = 256 * Math.pow(2, zoom);
  const x = ((lon + 180) / 360) * worldSize;
  const latRad = (lat * Math.PI) / 180;
  const mercN = Math.log(Math.tan(Math.PI / 4 + latRad / 2));
  const y = worldSize / 2 - (worldSize * mercN) / (2 * Math.PI);
  return [x, y];
}

function makeProjector(centerLat: number, centerLon: number, zoom: number, width: number, height: number) {
  const [cx, cy] = worldPx(centerLat, centerLon, zoom);
  const offX = cx - width / 2;
  const offY = cy - height / 2;
  return (lat: number, lon: number): [number, number] => {
    const [x, y] = worldPx(lat, lon, zoom);
    return [x - offX, y - offY];
  };
}

function round(n: number, decimals: number): number {
  const f = Math.pow(10, decimals);
  return Math.round(n * f) / f;
}

function requireFrame(args: Record<string, string>) {
  const centerLat = parseFloat(args["center-lat"]);
  const centerLon = parseFloat(args["center-lon"]);
  const zoom = parseFloat(args["zoom"]);
  const width = parseFloat(args["width"]);
  const height = parseFloat(args["height"]);
  if ([centerLat, centerLon, zoom, width, height].some((v) => Number.isNaN(v))) {
    console.error("Error: --center-lat --center-lon --zoom --width --height are all required.");
    process.exit(1);
  }
  const decimals = args["decimals"] !== undefined ? parseInt(args["decimals"], 10) : 1;
  const project = makeProjector(centerLat, centerLon, zoom, width, height);
  const [checkX, checkY] = project(centerLat, centerLon);
  console.error(
    `sanity check: center projects to (${round(checkX, 1)}, ${round(checkY, 1)}) — should equal (${width / 2}, ${height / 2})`
  );
  return { project, decimals, width, height };
}

async function main() {
  const [, , cmd, ...rest] = process.argv;
  if (!cmd || cmd === "--help" || cmd === "-h") {
    printHelp();
    return;
  }
  const args = parseArgs(rest);

  if (cmd === "point") {
    const lat = parseFloat(args["lat"]);
    const lon = parseFloat(args["lon"]);
    if (Number.isNaN(lat) || Number.isNaN(lon)) {
      console.error("Error: --lat and --lon are required.");
      process.exit(1);
    }
    const { project, decimals } = requireFrame(args);
    const [x, y] = project(lat, lon);
    console.log(JSON.stringify({ x: round(x, decimals), y: round(y, decimals) }));
    return;
  }

  if (cmd === "batch") {
    if (!args["input"]) {
      console.error("Error: --input <path> is required.");
      process.exit(1);
    }
    const points: Array<Record<string, unknown>> = JSON.parse(await Bun.file(args["input"]).text());
    const { project, decimals } = requireFrame(args);
    const out = points.map((p) => {
      const lat = p.lat as number;
      const lon = p.lon as number;
      const [x, y] = project(lat, lon);
      return { ...p, x: round(x, decimals), y: round(y, decimals) };
    });
    console.log(JSON.stringify(out));
    return;
  }

  if (cmd === "geojson") {
    if (!args["input"]) {
      console.error("Error: --input <path> is required.");
      process.exit(1);
    }
    const gj = JSON.parse(await Bun.file(args["input"]).text());
    const { project, decimals } = requireFrame(args);
    const features = gj.features ?? [gj];
    const paths = features.map((f: any) => {
      const ring: [number, number][] = f.geometry.coordinates[0];
      const pts = ring.map(([lon, lat]: [number, number]) => {
        const [x, y] = project(lat, lon);
        return `${round(x, decimals)},${round(y, decimals)}`;
      });
      return { properties: f.properties ?? {}, d: "M" + pts.join(" L") + " Z" };
    });
    console.log(JSON.stringify(paths));
    return;
  }

  console.error(`Unknown command: ${cmd}`);
  printHelp();
  process.exit(1);
}

main();
