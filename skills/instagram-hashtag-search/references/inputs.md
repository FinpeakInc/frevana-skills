# Instagram hashtag search inputs

Only `hashtag` is required. The leading `#` is optional and preserved; quote it in shell commands. Omitted options stay omitted. The helper validates the supplied schema's declared types, enums and numeric bounds, plus a nonempty hashtag. The backend owns detailed hashtag/date syntax. No native page-number or secondary cursor field is declared.

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `hashtag` / `--hashtag` | string | Tag to retrieve, such as `makeup` or `#makeup`. Preserve spelling, Unicode and prefix; no automatic conversion from a keyword query. |
| `type` / `--type` | `top`, `recent`, `clips` | Ranking: top is the backend default, recent progresses through newest-first pages, clips returns reels only. Every ranking paginates. The helper never adds a default value. |
| `cursor` / `--cursor` | string | Previous response's `pagination.next_cursor`, copied verbatim. Send the same type on continuation, or keep the default consistently omitted. No decoding/construction or mode switching. |
| `since` / `--since` | string | Inclusive start at UTC midnight for `YYYY-MM-DD`, or an ISO 8601 timestamp. Older rows are omitted; undated rows remain. Recent has the page-level stopping rule below; top/clips do not stop at the date. CLI aliases `--published-after`, `--start-date`, `--from-date` become `since`. |
| `until` / `--until` | string | Inclusive end: a whole UTC date or ISO timestamp. Newer rows are omitted, undated rows remain, and the walk does not stop at that date. CLI aliases `--published-before`, `--end-date`, `--to-date` become `until`. |
| `max_age_days` / `--max-age-days` | integer 1–3650 | Keeps sufficiently recent `post.published_at` values; undated rows are discarded. It stays a declared integer even though the date description also mentions this name as an alias. No date recomputation on retry. |
| `min_views` / `--min-views` | integer ≥0 | Keeps `post.engagement.views` at/above the floor; unknown counts are discarded. Runs after fetching each page, so walked pages retain their usual charges. Preserve `data.walk.discarded` and `request_ids`. |
| `sort_rows` / `--sort-rows` | string `views` | Backend orders kept rows by descending views across the pages it processes; unknown counts go last. The helper does not fetch more pages, sort or merge multiple responses itself. This does not change the cursor's requested ranking. |
| `seen` / `--seen` | string | User-chosen deduplication scope: 1–64 letters/digits or `._-` per description. Account-private row-ID memory lasts 24 hours from the last call using it. Share among related hashtag calls only when requested; it is not task identity. |
| `include` / `--include` | string `country` | Adds creator-declared country under `post.ext.author_country`, using creator numeric ID `post.ext.author_id`. It is not filming location and remains null when unpublished. Enum permits only country: no channel/creator/audio/stats/combined tokens. Adds costs below. |
| `safe_url` / `--safe-url` | boolean | True requests URL-safe media links suitable for embedding. No lifetime/durable-hosting guarantee was supplied. The helper preserves links and does not fetch them locally. |
| `async` / `--async` | boolean/integer/string | Exact JSON variants: booleans, integers 0/1 or strings `"true"`, `"false"`, `"1"`, `"0"`. CLI true/false becomes boolean, 1/0 integer; JSON input preserves string variants. Independent of wrapper `response_mode="json"`. |

## Ranking and date boundaries

With `type=recent`, pages progress newest to oldest but posts within one page are not necessarily in date order. The backend stops at the first page with no post on/after `since`: empty page, no next cursor, `pagination.stopped_at="since"`. Do not stop based on the first older row or locally reorder rows to decide continuation. Preserve returned stop/cursor metadata.

Top/clips are not chronological. Even if every dated row is removed, a page can still have a next cursor; a user-requested walk can continue. An empty result alone does not establish completion. `until` does not end the walk. Filtering happens after page retrieval, so pages can still cost their usual amount when all rows are filtered. Undated rows survive `since`/`until`, unlike the stricter `max_age_days` filter. The helper submits exactly one page and leaves explicitly requested continuation to the caller, with a new state/client ID and unchanged options/cursor.

## Deduplication and optional country lookup

The supplied description discounts the base page price under seen as `ceil(page credits × new rows / rows on page)`; an all-repeat page has no base-page charge. Only the base price is discounted. Joined data is charged for rows not previously received and is not discounted. Preserve `data.walk.repeats` and returned accounting; do not promise that every all-repeat request has zero total feature cost.

Country enrichment is described as 1 extra credit per creator whose country is returned. Multiple posts from one creator share a lookup; a creator looked up in the last 30 days is free, and unpublished country/unfound creator lookups are refunded. Do not infer unknown countries, drop rows with null country or add country filtering. `include=country` is opt-in; no additional lookups are performed by the helper. Prices/cache/refund statements come from the supplied description and are not verified live billing.

## Field boundaries

Aliases are CLI-only and become declared `since`/`until` fields before the original payload is saved. `publish_time`, `published_after`, `start_date`, `from_date`, `published_before`, `end_date`, `to_date` are not JSON properties. No ambiguous relative-time alias is exposed. `max_age_days` is explicitly declared and is sent unchanged. `limit`, `page`, `max_pages`, `query`, account identifiers, region/country filters, labels, relevance, goal fitting, previews and durable-media controls are not declared; do not inherit them from other Instagram skills.
