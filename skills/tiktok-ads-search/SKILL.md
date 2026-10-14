---
name: tiktok-ads-search
description: Search the public TikTok Ads Library by keyword, advertiser, country, or ad IDs through Frevana, with asynchronous status polling and JSON results. Use for competitor ad research and creative discovery, not TikTok Business account or campaign management.
---

# TikTok Ads Search

Use the bundled script to search public TikTok advertisements or retrieve specific ad details. It calls only the three Frevana `/apify/tiktok-ads/tasks` create, status, and result APIs. Requires Bash and Python 3.9+ with the standard library; no TikTok access token or SDK is needed.

## Workflow

1. Require a keyword (`--query`), advertiser (`--advertiser-name`), specific supported country, or one to one hundred unique `--ad-id` values. Do not combine ad IDs with any search filter. For account/campaign management, use `tiktok-ads`; for ordinary public posts, use a TikTok public-data skill.
2. Prefer `run` to create, wait, and retrieve results. Use `create`, `status`, `wait`, and `result` for separate phases. Read [references/api.md](references/api.md) for filters, defaults, supported countries, and task states.
3. Treat creation as billable: the server checks estimated credits and settles actual usage asynchronously. Record the printed `client_task_id` and returned `task_id`. After an uncertain create response, retry only with identical options and the same client ID; never automatically create a replacement task. Different parameters with the same ID return HTTP 409.
4. Wait for `status=READY` and `result_available=true`. Follow `next_poll_after_ms`; zero stops automatic polling. Stop on `FAILED`, `REVIEW_REQUIRED`, or `RESULT_EXPIRED`. A wait timeout can be resumed with the same `task_id`.
5. Preserve raw JSON in saved files. Summarize relevant ads for the user unless they request raw JSON. Do not imply a pending or settling task has completed. `quick_search=true` and unavailable ads may omit detail fields; never invent missing details.

## Commands

Resolve `{baseDir}` to the directory containing this file.

```bash
bash {baseDir}/scripts/tiktok_ads_search.sh run --query 'pikoya' --country ES
bash {baseDir}/scripts/tiktok_ads_search.sh run --advertiser-name 'Nike' --max-pages 2 --start-date 2026-10-01 --end-date 2026-10-13 --timezone UTC --sort-by impression,desc --output ./out/ads.json
bash {baseDir}/scripts/tiktok_ads_search.sh run --ad-id 1878055429367345
bash {baseDir}/scripts/tiktok_ads_search.sh create --client-task-id caller-stable-id --query 'shoes' --quick-search true
bash {baseDir}/scripts/tiktok_ads_search.sh status --task-id TASK_UUID
bash {baseDir}/scripts/tiktok_ads_search.sh wait --task-id TASK_UUID --timeout 1800
bash {baseDir}/scripts/tiktok_ads_search.sh result --task-id TASK_UUID --output ./out/ads.json
```

`create --wait` is equivalent to `run`. `--help` lists all flags. Defaults are one page (up to 12 ads), country `all`, timezone `UTC`, sort `last_shown_date,desc`, and `quick_search=false`. Omitted dates use the server's UTC today and one year earlier; the script leaves them omitted to keep retries stable. Supported country filters cover the listed European markets; `US` is unsupported.

## Authentication and output

Use `FREVANA_TOKEN` (JWT) or `FREVANA_API_KEY`. One-time `--token` or `--api-key` overrides environment credentials; when both environment variables exist, JWT takes priority. Credentials go only to Frevana. The default base URL is `https://ai-factory.frevana.com`; override with `FREVANA_API_BASE_URL` or `--api-base-url`, e.g. `http://127.0.0.1:3001`. Redirects are not followed.

`create` and `status` print unchanged task JSON. `result` prints the unchanged JSON array. `run`, `create --wait`, and `wait` save the final array under `./out/` by default and print the same bytes. `--output` chooses the destination for any action. Progress and IDs go to stderr. HTTP errors, malformed responses, and terminal failures exit nonzero without fetching a new task.

For creative previews use returned `adVideoUrl`, `adVideoCover`, or `adImageUrls` when present; `adLandingUrl` is the advertiser's destination page. These media links are not archived by this API and may expire. This helper fetches JSON only. On Windows, run the wrapper in Git Bash or WSL with Python 3 available; use output paths appropriate to that Python environment.
