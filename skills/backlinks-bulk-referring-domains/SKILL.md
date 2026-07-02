---
name: backlinks-bulk-referring-domains
description: Use when the user wants external referring-domain count totals for many domains or URLs in one batch request.
---

# Backlinks Bulk Referring Domains

Call Frevana's `/service/backlinks/bulk-referring-domains` endpoint and return the Backlinks API response unchanged.

## Purpose

This skill is for **referring-domain count totals for many domains or URLs in one batch request**.

Required input:

- `targets`

Output:

- validated response JSON from Frevana/Backlinks provider

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

1. Confirm the user has provided the required input.
2. Prefer the bundled script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Return the validated response JSON, or summarize it only if the user asks for a summary.
7. The script saves the JSON response to `./out/` by default.

## Command

```bash
bash <skill-path>/scripts/get_backlinks_bulk_referring_domains.sh --targets frevana.com,example.com
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/get_backlinks_bulk_referring_domains.sh --targets frevana.com,example.com \
  --output ./out/backlinks-bulk-referring-domains-result.json
```

## Request Shape

Frevana endpoint:

```text
POST /service/backlinks/bulk-referring-domains
```

Supported request fields for this API:

`targets`, `tag`

The script only sends fields supported by this API. Do not pass unsupported fields. Do not pass API keys, output paths, or request metadata in the payload; Frevana handles server-side details.

## Response Shape

The API returns JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- Default file path: `./out/backlinks-bulk-referring-domains-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Do not echo the Bearer token back to the user
- Use `--filters-json`, `--backlinks-filters-json`, `--custom-mode-json`, `--targets-json`, or `--exclude-targets-json` for structured values
- `--targets`, `--exclude-targets`, and `--order-by` accept comma-separated values
- Boolean options accept `true`, `false`, `1`, `0`, `yes`, `no`, `on`, or `off`
