---
name: google-local-services-search
description: Use when the user wants Google Local Services results through Frevana, including local service categories, job type filters, and place/provider identifiers.
---

# Google Local Services Search

Search Google Local Services through Frevana.

## Purpose

This skill calls Frevana's `/service/google-local-services` endpoint and returns the SerpAPI response unchanged.

Required input: `q`, `data_cid`.

Supported request fields:

- `q` (required)
- `data_cid` (required)
- `hl`
- `job_type`
- `cid`
- `bid`
- `pid`
- `no_cache`
- `async`
- `zero_trace`

The script validates that the response is JSON and prints it to stdout. Do not rewrite or reshape returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- query and data CID
- `FREVANA_TOKEN` in the environment variables, or `--token` for the current run
- `curl`, `bash`, and `python3`

The API base URL defaults to `https://ai-factory.frevana.com`. Set `FREVANA_API_BASE_URL` to point at another host.

## Commands

### Search local services

```bash
bash <skill-path>/scripts/search_google_local_services.sh \
  --q "plumbers" \
  --data-cid "14414772292044717666"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/search_google_local_services.sh \
  --q "Q" \
  --data-cid "DATA_CID" \
  --output "./out/google-local-services-search.json"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "q": "Q",
  "data_cid": "DATA_CID",
  "hl": "HL",
  "job_type": "JOB_TYPE",
  "cid": "CID",
  "bid": "BID",
  "pid": "PID",
  "no_cache": true
}
```

Do not pass unsupported fields. Do not pass SerpAPI `engine` or `api_key`; Frevana sets those server-side. Use `--output` for local file saving.

## Output

- Success: validated JSON on stdout
- With `--output`: the same JSON is also written to the requested file
- Failure: response body or parsing error on stderr, with a non-zero exit code

## Example Prompts

- "Search Google Local Services for query and data CID."
- "Run Google Local Services Search and save the raw JSON."
