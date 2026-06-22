---
name: google-maps-search
description: Use when the user wants Google Maps place search results, place details by Google Maps place ID or CID, nearby/location-biased results, map filters, or pagination through Frevana.
---

# Google Maps Search

Search Google Maps through Frevana.

## Purpose

This skill finds Google Maps places or retrieves a specific place record.

Inputs:

- for a search: `q` and `type=search`
- for a place lookup: `place_id` or `data_cid` (and, for `type=place`, `data`)
- optional map origin: `ll`, or `location`/`lat` and `lon` together with `z` or `m`
- optional `nearby`, `google_domain`, `hl`, `gl`, price/rating/opening filters, and `start`

Output:

- validated response JSON with Google Maps results

The script validates that the response is JSON and returns it unchanged. Do not rewrite or reshape returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- a search query with `--type search`, or a `--place-id` / `--data-cid`
- `FREVANA_TOKEN` in the environment variables, or `--token` for the current run
- `curl`, `bash`, and `python3`

## Commands

### Basic place search

```bash
bash <skill-path>/scripts/search_google_maps.sh \
  --q "coffee shops" \
  --type search
```

### Search near a location

```bash
bash <skill-path>/scripts/search_google_maps.sh \
  --q "coffee shops" \
  --type search \
  --location "San Francisco, CA" \
  --z 12 \
  --min-rating 4 \
  --open-state now
```

### Look up a known place

```bash
bash <skill-path>/scripts/search_google_maps.sh \
  --place-id "ChIJIQBpAG2ahYAR_6128GcTUEo"
```

### Override the API host for one environment

```bash
FREVANA_API_BASE_URL="https://api-dev.frevana.com" \
  bash <skill-path>/scripts/search_google_maps.sh --q "coffee shops" --type search
```

## Request Rules

- `--type` accepts `search` or `place`, and is required unless `--place-id` or `--data-cid` is supplied.
- `--type search` requires `--q`; `--type place` requires `--data`.
- `--place-id` and `--data-cid` cannot be used together.
- `--location` or `--lat`/`--lon` must be paired with `--z` or `--m`; `--lat` and `--lon` must be supplied together. Coordinates may be negative, and both `--lon -74.0060` and `--lon=-74.0060` are accepted.
- `--z` is 3–30; `--m` is 1–15028132; `--min-price` and `--max-price` are 1–4; `--min-rating` is one of 2, 2.5, 3, 3.5, 4, 4.5.
- `--open-state` is `now` or `24h` and cannot be used with `--open-on-day` / `--open-at-hour`. `--open-on-day` is `mon` through `sun`; `--open-at-hour` is 0–23 and requires `--open-on-day`.

The API base URL defaults to `https://ai-factory.frevana.com`; set `FREVANA_API_BASE_URL` to target another host.

## Output

- Success: validated JSON on stdout
- With `--output`: the same JSON is also written to the requested file
- Failure: response body or a validation error on stderr, with a non-zero exit code

## Example Prompts

- “Search Google Maps for coffee shops in San Francisco that are open now.”
- “Get this Google Maps place by place ID.”
- “Find restaurants near these coordinates, with a minimum 4-star rating.”
