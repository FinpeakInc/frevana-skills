# Frevana TikTok video search contract

Derived from Server `src/modules/apify/tiktok/{tiktok.controller.ts,dto/tiktok.dto.ts,tiktok.constants.ts,tiktok.adapter.ts,tiktok-result.ts}` and `src/modules/apify/async/apify-async.dto.ts`, inspected 2026-10-16. This documents the local code contract; it does not establish production deployment.

## Routes and responses

Use an origin base URL without a service suffix. Authentication: Bearer Frevana JWT or `x-api-key` Frevana API key. No TikTok Business or Apify token is needed.

| Operation | Route | Response |
| --- | --- | --- |
| Create | `POST /service/tiktok-videos/tasks` | HTTP 202 task object, plus `client_task_id` |
| Status | `GET /service/tiktok-videos/tasks/{task_id}` | Task object |
| Page | `GET /service/tiktok-videos/tasks/{task_id}/items?offset=0&limit=100` | `{task_id,offset,limit,count,total,items}` |
| Full result | `GET /service/tiktok-videos/tasks/{task_id}/result` | JSON array |

The Server also exposes `/apify/tiktok-videos`; the helper consistently uses `/service/tiktok-videos`. Task IDs must be UUID v4. Item `offset` is nonnegative; `limit` is 1–1000 (default 100). Results require READY; HTTP 409 indicates unavailable results and HTTP 410 expired results.

Task fields: `task_id`, `status`, `result_available`, `result_count`, `error_code`, `error_message`, `next_poll_after_ms`. Statuses: `PENDING`, `RUNNING`, `SETTLING`, `READY`, `FAILED`, `REVIEW_REQUIRED`, `RESULT_EXPIRED`. Do not infer success from an accepted request, existing rows, or a result count alone. Poll only at the suggested interval; zero stops automatic polling. There is no cancel endpoint in this controller.

Example body:

```json
{
  "client_task_id": "caller-stable-id",
  "search_queries": ["artificial intelligence"],
  "search_section": "/video",
  "results_per_page": 20,
  "video_search_date_filter": "PAST_WEEK"
}
```

## Search options

CLI flags use hyphens; JSON uses snake_case. `--query`/`--keyword` map to `search_queries`, `--hashtag` to `hashtags`, and `--username` to `profiles`; all other creation flags map directly. Exactly one source type is required per task. The Server uses `profile_scrape_sections=["videos"]` and `profile_sorting="latest"` for username mode; this helper leaves these defaults intact. The helper sends `results_per_page=20` when omitted; other unspecified defaults are left to the Server.

| Field | Contract / default |
| --- | --- |
| `client_task_id` | Optional stable ID, 1–128 characters; helper generates and prints one before submission |
| `search_queries` | 1–5 nonempty strings, at most 256 characters each; trimmed, deduplicated and sorted |
| `hashtags` | Alternative to keywords: 1–5 nonempty strings, at most 128 characters each; no `#`, whitespace, `/`, or `?` |
| `profiles` | Alternative to keywords: 1–5 usernames, at most 128 characters each, letters/digits/underscore/dot; no `@` or URL |
| `search_section` | Helper fixes `/video` only for keyword requests; omitted for hashtag/username modes |
| `results_per_page` | 1–100 per keyword/hashtag/username; skill default 20 (sent explicitly; Server fallback is 10) |
| `video_search_sorting` | `MOST_RELEVANT` (default), `MOST_LIKED`, `LATEST` |
| `video_search_date_filter` | `ALL_TIME` (default), `PAST_24_HOURS`, `PAST_WEEK`, `PAST_MONTH`, `LAST_3_MONTHS`, `LAST_6_MONTHS` |
| `least_diggs` | Inclusive lower like-count bound, 1–9007199254740991 |
| `most_diggs` | Exclusive upper like-count bound, 1–9007199254740991; must exceed `least_diggs` |
| `proxy_country_code` | Server allowlist (available in CLI help); default literal `None`. Proxy exit country, not author location |
| `max_total_charge_usd` | Upstream Run budget, 0.50–1000 USD, at most two decimal places |
| `video_kv_store_id_or_name` | Optional alias, 1–63 ASCII letters/digits/hyphens; Server scopes actual storage to the authenticated owner |

Video search sorting/date filters and related search words apply only to keyword mode, including explicit default or false values. Non-ALL_TIME date filters cannot be combined with `least_diggs` or `most_diggs`. Nondefault sorting can be combined with a search date filter. Do not infer author-country filtering from proxy selection. Do not substitute older Bright Data `/service/tiktok/posts/...` routes.

## Enrichment and download options

The helper does not expose a video download toggle and never sends `should_download_videos`. The Server default enables video downloads.

AI video descriptions and summaries are not exposed by the current Server. Do not send `ai_video_description` or `ai_video_summary`; unknown fields are rejected even when false.

| Field | Contract / default |
| --- | --- |
| `should_download_covers` | Boolean, false |
| `should_download_slideshow_images` | Boolean, false |
| `should_download_avatars` | Boolean, false |
| `should_download_music_covers` | Boolean, false |
| `scrape_related_search_words` | Boolean, false; related search terms |
| `scrape_additional_author_meta` | Boolean, false |
| `download_subtitles_options` | `NEVER_DOWNLOAD_SUBTITLES` (default), `DOWNLOAD_SUBTITLES`, `DOWNLOAD_AND_TRANSCRIBE_VIDEOS_WITHOUT_SUBTITLES`, `TRANSCRIBE_ALL_VIDEOS` |
| `comments_per_post` | Integer 0–1000, default 0 (off) |
| `top_level_comments_per_post` | Integer 0–1000, default 0 (provider behavior); cannot exceed `comments_per_post` |
| `max_replies_per_comment` | Integer 0–100, default 0 (provider behavior); provider may omit replies |

Nonzero top-level/reply limits require `comments_per_post > 0`. Comments and follow data use separate dataset links, not inline merged records. The helper does not request follower/following extraction or expose profile-specific sorting/date/section controls, direct-post collection, or user-search modes.

Video downloads, nondefault date/sort filters, like-count filtering, proxy selection, comment extraction, and transcription can add cost. Transcription charges by each video's rounded-up minutes. Default budget is the Server estimate plus 10%, at least $0.50. Unknown duration for transcription is estimated at one minute per video, so a budget can stop processing early. A USD budget is neither a credit amount nor a minimum spend; settlement uses actual provider `usageTotalUsd`. Do not quote estimated cost as final billing.

## Result semantics

Preserve all returned fields. Typical fields: string `id`, `text`, `textLanguage`, `createTime` (Unix seconds), `createTimeISO`, `webVideoUrl`, `authorMeta`, `videoMeta`, `musicMeta`, `hashtags`, `playCount`, `diggCount`, `shareCount`, `collectCount`, `commentCount`, `mediaUrls`. Field presence varies.

The Server adds nullable `video_url` and `video_url_expires_at` (currently null), and updates download/media fields with task-scoped signed Apify links. A null `video_url` means no usable downloaded video is available; inspect item errors instead of claiming a successful download. Signed file links remain usable while the underlying file is available; auxiliary dataset links have their own expiry; do not impose or promise a fixed expiry. Auxiliary comments dataset links are signed only when ownership can be verified; unavailable links may be null.

The helper saves the full response bytes unchanged, accepts an empty result array, and refuses to save malformed JSON/non-array full results. A local 52 MiB response cap bounds memory use. Never send Frevana authorization headers to returned media or dataset hosts.
