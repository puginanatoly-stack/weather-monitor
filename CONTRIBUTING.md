# Contributing

Bug reports, ideas, and pull requests are welcome.

## Reporting a bug

Open an issue with:
- what you ran (`python build.py <city>` or the scheduled workflow)
- what you expected vs. what happened
- the relevant snippet of `data/*.json` if a source looks wrong (redact `WEATHER_CITY` if it's not the demo city)

## Suggesting a feature

Open an issue describing the use case first — a short discussion before a PR saves everyone a rewrite, especially for anything that touches `composite.py`'s scoring or adds a new data source.

## Development setup

```bash
pip install -r requirements.txt
export OPENWEATHERMAP_API_KEY=...   # openweathermap.org/api, free tier
python build.py "London,GB"          # or any other city
```

Open the generated `index.html` locally in a browser. No test suite yet — a PR that adds one for `composite.py` or `sources.py` is very welcome.

## Code style

Plain, dependency-light Python (the whole project imports only `requests` beyond the standard library). Keep it that way unless a new dependency earns its place. Match the existing module split: `sources.py` (fetch), `composite.py` (scoring), `charts.py`/`templates.py`/`pages.py` (render), `build.py` (orchestration).

## Privacy note

Never commit a real city, real coordinates, or `data/history.jsonl` — see the docstrings in `build.py` and `history_sync.py` for why. The `demo/` folder and its screenshots use a neutral placeholder city (London) on purpose; keep it that way in any PR that touches them.
