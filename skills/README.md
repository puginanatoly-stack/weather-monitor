# skills/

Claude Code skills related to this project's domain (environmental/geo data monitoring), kept alongside the app rather than only in a local `~/.claude/skills/` install.

## HazardMap

Builds a real-geodata hazard/safety map for any location: a real elevation grid, a verified high point, and pedestrian walking-time isochrones from that point, overlaid on a real street map. Uses free, keyless public APIs (Nominatim, Open-Meteo, Valhalla, Wikimedia Maps) — no account or billing required.

To use it in a Claude Code session, copy the folder into your own skills directory:

```bash
cp -r skills/HazardMap ~/.claude/skills/HazardMap
```

See `skills/HazardMap/SKILL.md` for triggers and workflow, and `skills/HazardMap/ApiReference.md` for the underlying API contracts and gotchas.
