---
name: tiktok-top-ads-search
description: Search TikTok Creative Center Top Ads through Frevana by keyword or Top Ads list/detail URLs, with country, industry, objective, language, and performance sorting filters. Use for top-performing creative research; use tiktok-ads-search for the public Ads Library.
---

# TikTok Top Ads Search

Use the bundled Bash/Python helper for Creative Center Top Ads research. Requires Bash and Python 3.9+ with the standard library. No TikTok Business token or SDK is needed.

## Workflow

1. Require `--keyword`, one to five `--start-url` values, or both. Country or other filters alone are insufficient. URLs must be HTTPS on `ads.tiktok.com` under `/business/creativecenter/topads/` or `/business/creativecenter/inspiration/topads/`. For Ads Library research use `tiktok-ads-search`; for account/campaign management use `tiktok-ads`.
2. Prefer `run` to create, wait, and fetch the complete JSON array. Use `create`, `status`, `wait`, and `result` for separate phases. Read [references/api.md](references/api.md) for all parameter allowlists, defaults, and task states.
3. Creation is billable: the server checks estimated credits and settles actual usage asynchronously. Record the printed `client_task_id` and returned `task_id`. If creation has an uncertain outcome, retry only with identical options and the same client ID; never automatically create a replacement. Changed parameters with the same ID return HTTP 409.
4. Wait for `READY` with `result_available=true`. Follow `next_poll_after_ms`; zero stops automatic polling. Stop on `FAILED`, `REVIEW_REQUIRED`, or `RESULT_EXPIRED`. Resume a timeout with `wait --task-id` using the existing ID.
5. Preserve saved JSON bytes and summarize relevant ads unless raw JSON is requested. Keep `id` as a string. Metrics and media are optional; do not infer missing values or treat media URLs as permanent archived assets.

## Commands

Resolve `{baseDir}` to the directory containing this file.

```bash
bash {baseDir}/scripts/tiktok_top_ads_search.sh run --keyword 'shoes' --country US --order-by ctr --max-items 10
bash {baseDir}/scripts/tiktok_top_ads_search.sh run --keyword 'skincare' --country US --country GB --ad-language en --period 7 --order-by like --output ./out/top-ads.json
bash {baseDir}/scripts/tiktok_top_ads_search.sh run --start-url 'https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en?period=30&region=US'
bash {baseDir}/scripts/tiktok_top_ads_search.sh create --client-task-id caller-stable-id --keyword 'skincare' --industry 14 --objective 15 --ad-format 1
bash {baseDir}/scripts/tiktok_top_ads_search.sh status --task-id TASK_UUID
bash {baseDir}/scripts/tiktok_top_ads_search.sh wait --task-id TASK_UUID --timeout 1800
bash {baseDir}/scripts/tiktok_top_ads_search.sh result --task-id TASK_UUID --output ./out/top-ads.json
```

`create --wait` is equivalent to `run`. Repeat `--country`, `--industry`, `--objective`, and `--ad-language` to send arrays. Server defaults are `order_by=for_you`, `period="30"`, and `max_items=5` **per source**, not a global result cap. The helper leaves these omitted defaults to the server and explicitly sends its country selection. Numeric-looking industry/objective/format/period codes remain strings. Use the English code mappings in [references/api.md](references/api.md) to select filters: Beauty & Personal Care is industry `14`, Product Sales is objective `15`, Spark Ads is format `1`, and Non-Spark Ads is format `2`. `impression` means Reach in the Creative Center sorting options. Default to these 28 countries: `AR AU BR CA CO FR DE ID IT JP MY MX NL PK PH RO SA SG ZA KR ES SE TH TR AE GB US VN`. The helper explicitly sends this selection when `--country` is omitted, for both keyword and URL requests. Explicit `--country` values replace the entire default selection. The country filter still supports 81 countries and regions. Omit other array filters for no restriction; do not send `all` or empty arrays. A start URL may contain its own `region` filter; check it against the intended selection without modifying caller URLs automatically. Ad content language is independent of the start URL webpage language. Do not use result `industryKey`, `objectiveKey`, or `label_` identifiers as request codes.

## Authentication and output

Use `FREVANA_TOKEN` or one-time `--token` Bearer authentication; never print credentials. Default base URL: `https://ai-factory.frevana.com`. Override with `FREVANA_API_BASE_URL` or `--api-base-url`. Redirects are not followed.

`create` and `status` print unchanged task JSON; `result` prints the unchanged JSON array. `run`, `create --wait`, and `wait` also save the final array under `./out/` by default. `--output` chooses a destination for any action. IDs/progress go to stderr. HTTP errors, malformed results, and terminal failures exit nonzero; failed result responses do not overwrite the requested file. This helper fetches JSON only and uses the create/status/result endpoints. On Windows use Git Bash or WSL with Python 3 available.
