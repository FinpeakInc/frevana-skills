---
name: amazon-related-keywords
description: Find as many related Amazon keywords as possible from one seed keyword through Frevana's DataForSEO-backed Amazon Related Keywords API, with maximum-depth defaults and automatic offset pagination. Use when the user wants Amazon keyword ideas, related search terms, semantic keyword expansion, synonym-aware Amazon keyword research, or exhaustive related-keyword results for SEO, PPC, and listing optimization.
---

# Amazon Related Keywords

Retrieve related Amazon keywords from a seed keyword through Frevana.

## Requirements

- Require one seed `keyword`.
- Accept at most one of `location_name` or `location_code`.
- Accept at most one of `language_name` or `language_code`.
- Default missing location to `location_name="United States"`.
- Default missing language to `language_name="English"`.
- Read `FREVANA_TOKEN` from the environment, or accept a one-time `--token` override.
- Require `bash`, `curl`, and `python3`.

## Workflow

1. Collect the seed keyword and any location or language selector the user supplied.
2. Normalize the seed keyword to lowercase as required by the endpoint.
3. Apply `United States / English` when location or language is missing. State this default in the user-facing response when relevant.
4. Maximize keyword coverage with these script defaults:
   - `limit`: `1000`
   - `offset`: `0`
   - `depth`: `4`
5. Let the API apply the remaining defaults:
   - `include_seed_keyword`: `false`
   - `ignore_synonyms`: `false`
6. When a response contains a full page, increase `offset` by `limit` and continue until a page is not full or `total_count` is reached.
7. Prefer the bundled script over ad hoc HTTP requests.
8. In non-interactive runs, fail fast when `FREVANA_TOKEN` is missing.
9. Use the saved JSON for follow-up analysis instead of calling the endpoint again.
10. Preserve every raw page under `pages` in the aggregated output.

## Commands

### Use the default United States / English market

```bash
bash <skill-path>/scripts/search_amazon_related_keywords.sh \
  --keyword "Wireless Earbuds"
```

### Use location and language names

```bash
bash <skill-path>/scripts/search_amazon_related_keywords.sh \
  --keyword "Wireless Earbuds" \
  --location-name "United States" \
  --language-name "English"
```

### Use DataForSEO codes and request deeper expansion

```bash
bash <skill-path>/scripts/search_amazon_related_keywords.sh \
  --keyword "wireless earbuds" \
  --location-code 2840 \
  --language-code en \
  --depth 2 \
  --include-seed-keyword true \
  --limit 250
```

### Start automatic pagination from a custom offset

```bash
bash <skill-path>/scripts/search_amazon_related_keywords.sh \
  --keyword "wireless earbuds" \
  --location-code 2840 \
  --language-code en \
  --offset 1000 \
  --output ./out/amazon-related-keywords-from-1000.json
```

## Request Contract

Send `POST /service/amazon/related-keywords` with:

- at most one of `location_name` (string) or `location_code` (integer); default to `location_name="United States"` when neither is supplied
- at most one of `language_name` (string) or `language_code` (string); default to `language_name="English"` when neither is supplied
- `keyword` (required string, converted to lowercase)
- `limit` (optional integer, `1..1000`; script default `1000`)
- `offset` (optional integer, minimum `0`; starting offset defaults to `0`)
- `tag` (optional string, maximum `255` characters)
- `depth` (optional integer, `0..4`; script default `4`)
- `include_seed_keyword` (optional boolean)
- `ignore_synonyms` (optional boolean)

Do not send output paths, Bearer tokens, API keys, or unsupported fields in the JSON payload.

Example payload:

```json
{
  "location_name": "United States",
  "language_name": "English",
  "keyword": "wireless earbuds",
  "limit": 1000,
  "offset": 0,
  "depth": 4
}
```

## Output

- Validate that every successful response body is JSON.
- Automatically fetch the next offset whenever the current page contains `limit` items.
- Stop when a page contains fewer than `limit` items or the accumulated offset reaches `total_count`.
- Stop with an error if the API repeats the same non-empty page, preventing an infinite loop.
- Print one aggregate JSON object containing `pagination` metadata and the untouched raw responses in `pages`.
- Save it by default to `./out/amazon-related-keywords-<UTC timestamp>-<pid>.json`.
- With `--output`, save it to the requested path instead.
- On failure, print the HTTP response or validation error and exit non-zero.
- When summarizing, highlight the strongest related terms and useful listing, SEO, or PPC clusters.

## Example Prompts

- "查一下 wireless earbuds 的 Amazon 相关关键词，美国、英文"
- "查一下 wireless earbuds 的 Amazon 相关关键词"
- "用 location code 2840 和 language code en 扩展 coffee grinder，深度 3"
- "获取 Amazon related keywords，包含种子词并忽略同义词"
- "尽可能多地获取 wireless earbuds 的 Amazon 相关关键词"
- "Find related Amazon keywords for portable monitor in the United States and English"
- "Get page two of Amazon related keywords for running shoes and save the raw JSON"
