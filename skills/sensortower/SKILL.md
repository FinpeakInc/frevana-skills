---
name: sensortower
description: Query Sensor Tower app intelligence through its API for app or publisher search, download and revenue estimates, top charts, DAU/WAU/MAU active users, publisher app portfolios, and advertising intelligence. Use when the user asks for Sensor Tower data, mobile app or game market estimates, app rankings, publisher titles, active-user metrics, competitor ad creatives, or SensorTower API lookups.
---

# Sensor Tower

Use the bundled CLI for Sensor Tower queries. Return the API JSON unchanged unless the user asks for a summary or transformation.

## Requirements

- Python 3.9 or newer
- `SENSORTOWER_AUTH_TOKEN` in the environment
- Sensor Tower API access for the requested endpoint

No manual `pip install` is required. Always invoke `scripts/run.py`; it reads
`requirements.txt` and installs any future pinned dependencies into an isolated
per-user cache on first use. Dependencies must include trusted artifact hashes.
The current release has no third-party dependencies.

Never print, quote, or return the token. Do not pass it as a command-line argument.

## Workflow

1. Identify the smallest matching action.
2. Collect required IDs, platform, countries, and dates. Do not guess them.
3. Run `python3 <skill-path>/scripts/run.py <action> ...` once. Do not bypass the runner.
4. If the command fails, report the sanitized error. Do not retry with different parameters unless the error identifies an invalid field or the user approves a change.
5. Summarize relevant fields by default and preserve uncertainty: Sensor Tower values are estimates, not audited financials.

## Actions

### Search apps or publishers

```bash
python3 <skill-path>/scripts/run.py search \
  --term "Royal Match" \
  --entity-type app \
  --os unified \
  --limit 10
```

Use `--entity-type publisher` for publisher lookup.

### Downloads and revenue estimates

```bash
python3 <skill-path>/scripts/run.py sales \
  --app-id 1482938460 \
  --os ios \
  --countries US,GB \
  --start 2026-03-01 \
  --end 2026-03-31 \
  --granularity monthly
```

Pass exactly one of `--app-id` or `--publisher-id`. Use only `ios` or `android`.

### Top charts

```bash
python3 <skill-path>/scripts/run.py top-charts \
  --measure revenue \
  --countries US \
  --category 6014 \
  --limit 20
```

Optional dates default to the trailing 30 days.

### Active users

```bash
python3 <skill-path>/scripts/run.py active-users \
  --app-id 1482938460 \
  --os ios \
  --metric DAU \
  --countries US \
  --start 2026-03-01 \
  --end 2026-03-31
```

Require a platform-specific app ID and one platform. Never reuse one ID across both platforms automatically.

### Publisher apps

```bash
python3 <skill-path>/scripts/run.py publisher-apps \
  --publisher-id 12345 \
  --os unified
```

### Advertising intelligence

```bash
python3 <skill-path>/scripts/run.py ad-intelligence \
  --action creatives \
  --app-id 1482938460 \
  --countries US \
  --limit 20
```

`overview` and `creatives` require `--app-id`; `top-advertisers` does not.

## Output and errors

- Success: validated JSON on stdout.
- Optional `--output PATH`: write the same JSON to the selected file.
- Failure: sanitized diagnostic on stderr and non-zero exit status.
- No action silently converts API failures into empty results.
- The CLI validates dates, country codes, positive limits, and response JSON before returning.

For endpoint and parameter details, read [references/api.md](references/api.md).
