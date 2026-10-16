---
name: tiktok-video-search
description: Find public TikTok videos by keyword, hashtag, or username through Frevana, with date and popularity filters, downloadable video URLs, and optional subtitles or enrichment. Use for organic video discovery, not Ads Library or TikTok Business management.
---

# TikTok Video Search

Find public TikTok videos by keyword, hashtag, or username through Frevana's asynchronous video API. Requires Bash and Python 3.9+; no browser extension, daemon, Apify SDK, or provider token is needed.

## Workflow

1. Choose exactly one source type per task: `--query`/`--keyword` for keyword video searches, `--hashtag` for topic videos (without `#`), or `--username` for videos from specific creators (without `@`, not profile URLs). Repeat the chosen flag for 1–5 values. Resolve `{baseDir}` to this skill's folder and prefer `scripts/tiktok_video_search.sh`. Keyword mode sends `search_queries` with `search_section=/video`; hashtag mode sends `hashtags`; username mode sends `profiles` and uses the Server's original-video feed with latest-first sorting. Exact post collection, Top/user search, and ads are separate workflows.
2. Authenticate with `FREVANA_TOKEN` or `FREVANA_API_KEY`, or a one-time `--token`/`--api-key`. Explicit credentials override environment credentials; otherwise the token takes precedence. Never print credentials.
3. Use `run` to submit and wait, or `create` to return immediately. Keep the printed `client_task_id` and returned `task_id`. The helper omits the video download field and uses the Server default, which enables downloads. Do not pass a video download toggle. Leave other paid enrichment off unless requested; see [references/api.md](references/api.md) for parameters and cost semantics.
4. Follow `next_poll_after_ms`. Fetch results only when `status=READY` and `result_available=true`. Stop on `FAILED`, `REVIEW_REQUIRED`, `RESULT_EXPIRED`, or a zero polling interval without available results. Resume timeouts with `wait --task-id`; never automatically submit another paid task. If creation is uncertain, retry only with the same `client_task_id` and identical options. Changed inputs under that ID return HTTP 409.
5. Preserve the JSON file and summarize relevant videos unless the user asks for raw JSON. Useful fields include `id`, `text`, `webVideoUrl`, `authorMeta`, `playCount`, `diggCount`, and `video_url`. Keep IDs as strings, missing metrics as unknown, and individual `errorCode` records visible. A ready task does not guarantee every item has a downloaded video.

## Commands

```bash
bash {baseDir}/scripts/tiktok_video_search.sh run --query 'artificial intelligence' --results-per-page 20
bash {baseDir}/scripts/tiktok_video_search.sh run --hashtag 'skincare' --hashtag 'beauty'
bash {baseDir}/scripts/tiktok_video_search.sh run --username 'tiktok'
bash {baseDir}/scripts/tiktok_video_search.sh run --query 'skincare' --query 'beauty routine' --video-search-sorting MOST_LIKED --video-search-date-filter PAST_WEEK --output ./out/videos.json
bash {baseDir}/scripts/tiktok_video_search.sh create --query 'robotics' --client-task-id caller-stable-id --max-total-charge-usd 2.50
bash {baseDir}/scripts/tiktok_video_search.sh status --task-id TASK_UUID
bash {baseDir}/scripts/tiktok_video_search.sh wait --task-id TASK_UUID --timeout 1800
bash {baseDir}/scripts/tiktok_video_search.sh result --task-id TASK_UUID --output ./out/videos.json
bash {baseDir}/scripts/tiktok_video_search.sh items --task-id TASK_UUID --offset 0 --limit 100
```

`create --wait` is equivalent to `run`. `--keyword` is an alias for `--query`. `results_per_page` defaults to 20 **per keyword, hashtag, or username**, with a maximum of 100. Leave sorting omitted to retain the Server default `MOST_RELEVANT`. `--video-search-sorting`, `--video-search-date-filter`, and `--scrape-related-search-words` apply only to keyword mode. Do not combine source types in one request. The helper explicitly sends `results_per_page=20` when omitted and leaves other defaults to the Server. Other boolean flags take explicit `true` or `false`.

`run`/`wait` save the full JSON array under `./out/` unless `--output` is supplied, and also write unchanged JSON to stdout; progress goes to stderr. `status`, `create`, `items`, and `result` save only when `--output` is supplied. `--timeout` is a waiting budget in seconds (default 21600, zero means unlimited); HTTP requests have a separate cap of 600 seconds. Base URL defaults to `https://ai-factory.frevana.com`, overridden by `FREVANA_API_BASE_URL` or `--api-base-url`.

The `items` command returns one page, not the complete result. Advance `offset` by `count` until reaching `total`; stop and report an incomplete response if `count=0` before `total`. Use `result` for the full array.

Downloaded `video_url` values are direct Apify signed URLs, with `video_url_expires_at=null`; the Server imposes no fixed 24-hour expiry, but availability depends on the stored file. Do not promise permanent storage. Do not attach Frevana credentials when accessing media or auxiliary dataset URLs. Comments remain in a separate dataset linked by `commentsDatasetUrl`/`commentsDatasetURL`; they are not merged into the main result.

## Offline validation

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s {baseDir}/tests -v
```

Tests use a local mock server and do not call paid providers.
