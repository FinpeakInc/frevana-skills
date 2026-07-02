---
name: backlinks-referring-networks
description: Use when the user wants external referring IP or network-level backlink data for one target, useful for checking inbound-link network diversity.
---

# Backlinks Referring Networks

Call Frevana's `/service/backlinks/referring-networks` endpoint and return the Backlinks API response unchanged.

## Purpose

This skill is for **referring IP or network-level backlink data for one target, useful for checking link network diversity**.

Required input:

- `target`

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
bash <skill-path>/scripts/get_backlinks_referring_networks.sh --target frevana.com --limit 100
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/get_backlinks_referring_networks.sh --target frevana.com --limit 100 \
  --output ./out/backlinks-referring-networks-result.json
```

## Request Shape

Frevana endpoint:

```text
POST /service/backlinks/referring-networks
```

Supported request fields for this API:

`target`, `network_address_type`, `limit`, `offset`, `internal_list_limit`, `backlinks_status_type`, `filters`, `order_by`, `backlinks_filters`, `include_subdomains`, `include_indirect_links`, `exclude_internal_backlinks`, `rank_scale`, `tag`

The script only sends fields supported by this API. Do not pass unsupported fields. Do not pass API keys, output paths, or request metadata in the payload; Frevana handles server-side details.

## Response Shape

The API returns JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- Default file path: `./out/backlinks-referring-networks-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Do not echo the Bearer token back to the user
- Use `--filters-json`, `--backlinks-filters-json`, `--custom-mode-json`, `--targets-json`, or `--exclude-targets-json` for structured values
- `--targets`, `--exclude-targets`, and `--order-by` accept comma-separated values
- Boolean options accept `true`, `false`, `1`, `0`, `yes`, `no`, `on`, or `off`
