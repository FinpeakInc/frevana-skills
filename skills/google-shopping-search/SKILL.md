---
name: google-shopping-search
description: Use when the user wants Google Shopping product search results through Frevana, including product titles, prices, ratings, source merchants, localized country/language results, pagination offsets, device-specific results, or Google Shopping sort order.
---

# Google Shopping Search

Search Google Shopping product listings through Frevana.

## Purpose

This skill is for **finding Google Shopping product results**.

Inputs:

- `q`
- optional `google_domain`
- optional `gl`
- optional `hl`
- optional `start`
- optional `device`
- optional `sort_by`

Output:

- validated response JSON with Google Shopping product results
- the same validated JSON saved to a local file on every successful run

This skill validates that the response is JSON, saves it to disk, and returns it unchanged on stdout. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `q`
- optional `google_domain`
- optional `gl`
- optional `hl`
- optional `start`
- optional `device`
- optional `sort_by`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided `q` or an equivalent product search query.
2. Prefer the script over ad hoc `curl` commands.
3. Let the script read `FREVANA_TOKEN` first.
4. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
5. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
6. Run the script once. It prints the validated JSON to stdout and saves the same JSON to a file.
7. Use the saved JSON file for any follow-up parsing or summarization instead of calling the search API again.
8. Return the validated response JSON, or summarize the most relevant products if the user does not need the full payload.

## Commands

### Basic shopping search

```bash
bash <skill-path>/scripts/search_google_shopping.sh \
  --q "wireless earbuds"
```

`--query` is accepted as an alias for `--q`.

### Search with country, language, and Google domain

```bash
bash <skill-path>/scripts/search_google_shopping.sh \
  --q "wireless earbuds" \
  --google-domain google.com \
  --gl US \
  --hl en
```

### Search with pagination, device, and sort order

```bash
bash <skill-path>/scripts/search_google_shopping.sh \
  --q "wireless earbuds" \
  --start 20 \
  --device mobile \
  --sort-by 1
```

### Save response JSON to a specific file

```bash
bash <skill-path>/scripts/search_google_shopping.sh \
  --q "wireless earbuds" \
  --gl US \
  --hl en \
  --output ./out/google-shopping-search-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_google_shopping.sh \
  --q "wireless earbuds" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "q": "wireless earbuds",
  "google_domain": "google.com",
  "gl": "US",
  "hl": "en",
  "start": 20,
  "device": "mobile",
  "sort_by": "1"
}
```

Only `q` is required. Do not invent `google_domain`, `gl`, `hl`, `start`, `device`, or `sort_by` values when the user did not provide them.

## Response Shape

The API returns Frevana JSON. This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON, writes it to a file, prints the saved path to stderr, and prints the JSON to stdout
- Default file path: `./out/google-shopping-search-<UTC timestamp>-<pid>.json`
- With `--output`: the same JSON is written to the specified file path instead of the default path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--q` or `--query`
- Do not call the script twice just to save and summarize results. It always saves the same JSON that it prints.
- Use `--google-domain` only when the user specifies a Google domain such as `google.com`
- Use `--gl` when the user requests a specific country or region
- Use `--hl` when the user requests a specific language
- Use `--start` when the user requests pagination by result offset
- Use `--device` only for `desktop`, `mobile`, or `tablet`
- Use `--sort-by 1` for price low to high and `--sort-by 2` for price high to low when the user asks for those Google Shopping sort orders
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- Summarize the product results the user actually cares about instead of dumping raw JSON unless they ask for the full payload

## Example Prompts

### 中文

- "搜索 Google Shopping 上的 wireless earbuds"
- "查一下 Google Shopping 里 q=running shoes，gl=US，hl=en"
- "Google Shopping 搜索 wireless earbuds，按价格从低到高排序，并保存原始 JSON"

### English

- "Search Google Shopping for wireless earbuds"
- "Look up Google Shopping results for running shoes with gl=US and hl=en"
- "Search Google Shopping for wireless earbuds sorted by price low to high and save the raw JSON"
