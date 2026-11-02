# Instagram profile reel inputs

The schema's `allOf`/`anyOf` requires `user_id` or `handle`; its empty top-level `required` list does not mean both may be omitted. Both identifiers are permitted, but do not invent a second one or resolve a username automatically. Preserve the exact identifier strings, including long/leading-zero user IDs. Omitted options stay omitted. The backend owns feature combinations not explicitly constrained below and date-string validation.

## Identifiers, ordering and filters

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `handle` / `--handle` | string | Username without `@`; alternative to user ID. |
| `user_id` / `--user-id` | string | Known Instagram user ID, described as faster. Never coerce it into an integer, which could lose precision or leading zeros. |
| `cursor` / `--cursor` | string | Copy `pagination.next_cursor` verbatim; omit for page 1. The API maps it to native `max_id`. |
| `max_id` / `--max-id` | string | Native cursor from a previous compatible response. Prefer universal `cursor`; never send both. |
| `sort` / `--sort` | string `most_viewed` | Highest plays first, instead of default newest first, at the same price per description. Its cursors continue only that order. Cannot combine with any supplied `include`, `trim`, `recent_days`, `since`, `stop_at_id`; explicit false/empty values do not bypass the helper's presence check. |
| `since` / `--since` | string | Inclusive start date at UTC midnight (`YYYY-MM-DD`) or ISO 8601 timestamp. Older non-pinned reels end the walk: no next cursor, `stopped_at="since"`. Pinned reels do not terminate it. Incompatible with most-viewed sort. |
| `until` / `--until` | string | Inclusive end: the entire UTC day or ISO timestamp. Newer rows are filtered but do not stop the walk; undated rows remain. CLI aliases `--published-before`, `--end-date`, `--to-date` map to `until`; those are not JSON keys. |
| `stop_at_id` / `--stop-at-id` | string | Known reel ID (`post.id`) or URL (`post.url`). Stop before it and all subsequent rows; `stopped_at="known_id"` without next cursor. Pinned reels are not stop points. If absent from this page, the page/cursor remains intact; `end` means list exhausted and null means more may remain. Incompatible with most-viewed sort. |
| `recent_days` / `--recent-days` | integer 1–3650 | Filters older posts, pinned included; reaching an older date window stops pagination. Preserve the integer on retries. Incompatible with most-viewed sort. |
| `exclude_pinned` / `--exclude-pinned` | boolean | Drops confirmed pins only. Unknown pin state remains; every trimmed row has unknown pin state. Do not infer complete pin removal from an empty/missing flag. |
| `trim` / `--trim` | boolean | True returns a narrower/faster record retaining engagement, author, caption, timestamp, reel URL and `post.content.thumbnail_url`. Drops `post.content.media_urls`, `post.content.duration_seconds`, `post.ext.coauthors`, `post.flags.pinned`. Incompatible with most-viewed sort. |
| `async` / `--async` | boolean/integer/string | Exact JSON variants: booleans, integers 0/1, strings `"true"`, `"false"`, `"1"`, `"0"`. CLI true/false becomes boolean, 1/0 integer. JSON input preserves string variants. Independent of wrapper JSON response mode. |

One invocation returns one page, not the full account history. Filtering does not erase the base page cost. Explicit continuation uses a new state/client ID and unchanged opaque cursor, identifier, sort and enrichment mode. The helper cannot infer cursor provenance. A most-viewed cursor is not interchangeable with a newest-first cursor. Start intentionally from page 1 when changing sort or enabling stats; do not send the old cursor.

## Goal fitting, enrichment and previews

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `fit` / `--fit` | string `goal` | Retains goal-relevant rows/fields, uncertain content and first/last blocks; stubs the rest. Preserve `data.held_back` IDs and recall ID for a full cached page. No recall route was supplied, so do not invent a follow-up call. |
| `goal` / `--goal` | string | Required for meaningful goal fitting; user's objective up to 300 characters per description. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content budget with goal fitting; uncertain/first/last blocks may exceed it. No numeric bounds are declared. |
| `include` / `--include` | string | Documented tokens: `stats`, `audio`, `audio,stats`. Stats adds a full stat line for 1 extra credit per page; audio adds missing music fields for 1 extra credit per reel filled, refunded if unreadable. Explicit request only. Incompatible with most-viewed sort. |
| `dry_run` / `--dry-run` | string `1` | Cost preview without fetching the page or judging rows, described as 0 credits. Preserve `data.estimate`; never automatically proceed to a paid fetch. |

Stats adds documented shares/saves (`engagement.shares`, `engagement.saves`), `post.ext.repost_count`, music ID and audio-cluster ID alongside standard engagement/remix information. It uses a different source, so a cursor from a request without stats cannot continue with stats. Audio adds `post.ext.music_id` and `post.ext.music` where missing; stats and audio may be combined when requested. Keep the complete include value across a walk. Never substitute `tags`, `creator`, `country` or `channel`, which are not documented here. Do not download linked video or audio automatically. Credit amounts above are from the supplied description, not verified live billing.

## Labels and exclusions


| JSON / CLI flag | Type | Meaning |
| --- | --- | --- |
| `label` / `--label` | string CSV | Adds named labels alongside defaults. Options described below. `none` disables default judgments. No token enum is declared; the backend remains authoritative. |
| `judgments` / `--judgments` | string `on` or `off` | Server defaults to on: free sponsored/intent/niche judgments, with complete/partial/skipped status and pending rows. They do not alter existing fields, drop or reorder rows. Pending labels may be null until a later read. Off disables those additions; the helper does not add this option by default. |
| `brand` / `--brand` | string | For `label=mention`, the target brand/product, up to 300 characters per description. Missing brand makes mention skip with `label_mention_needs_brand`, without billing that label. Do not invent the target. |
| `brand_description` / `--brand-description` | string | For mention: one sentence disambiguating the target brand/product. |
| `offer` / `--offer` | string | With intent: 1–2 sentences describing the offer, up to 300 characters; adds `fits_offer`. Without it that field is null. |
| `label_evidence` / `--label-evidence` | string `1` | With explicit labels: adds verbatim supporting quote and sentence index to `computed.labels_evidence`; absent/null if there is no single supporting sentence. |
| `exclude` / `--exclude` | string CSV | `engagement_bait` with quality drops probability ≥0.8; `ai_style` with ai_style drops pattern count ≥2; `ai_written` with ai_written drops likely rows or those reaching the configured threshold. Preserve `data.labels.dropped_ids`. Unjudged rows and too-short AI-written rows are never dropped. |
| `ai_written_threshold` / `--ai-written-threshold` | string | Only with ai_written label and exclusion: probability 0–1, description default 0.95. A lower 0.71 threshold also includes possible cases and more human false positives. Omit unless requested. |

Label meanings:

- `sponsored`: probability of paid/gifted promotion, disclosure markers, possible undisclosed promotion and promoted account. These are review signals, never findings.
- `mention`: target relevance, five-level sentiment (null if unrelated), sarcasm, aspect and first-hand use.
- `intent`: caption purpose, buyer/seller likelihood, urgency and optional offer fit.
- `niche`: caption-only taxonomy assignment with confidence; no video inspection. Insufficient/uncertain captions can have null labels.
- `quality`: checkable detail, engagement bait, rage bait (writing style, not viewpoint), secondhand content and post aim.
- `ai_style`: six judged writing patterns plus text counts. Describes style rather than authorship; people can match it. Short text is counted without judged patterns.
- `ai_written`: calibrated model probability and likely/possible/unlikely/too_short level. Model names identify a scale; shorter text is less certain. This is not proof of authorship.
- `injection`: flags text attempting to direct an AI system. It does not itself drop or rewrite rows.

The description states sponsored/intent/niche are free; mention, quality, ai_style, intent with offer, and injection add 1 credit per started 25 newly judged posts. It does not explicitly specify the ai_written label rate: use a requested preview or returned accounting instead of guessing. Cached pages and previously labeled posts are described as free for labeling; do not infer that every future page fetch is free. Preserve `data.labels` billing information and row-level nulls/warnings.
