# User tweet inputs

Only handle is required. Omitted options stay omitted. The helper validates declared properties/types/enums and a nonempty handle without @; detailed dates/feature combinations belong to the backend. CLI hyphens map to declared snake_case properties.

## Account, pages and boundaries

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `handle` / `--handle` | string | X / Twitter username without @. No user_id, account URL or automatic ID-resolution step is declared. Preserve the supplied handle without rewriting it. |
| `cursor` / `--cursor` | string | Exact pagination.next_cursor from the preceding response. Omit for page 1; never decode, construct, increment or convert to integer. Explicit continuation uses a new state/client ID with unchanged handle/options. |
| `since` / `--since` | string | Inclusive YYYY-MM-DD midnight UTC or ISO timestamp. Older tweets are omitted; the backend stops at an older non-pinned tweet with stopped_at=since and no next cursor. Pins are out of date order and never end the walk. CLI convenience aliases --published-after/--start-date/--from-date map here. No ranking field is declared or inserted. |
| `until` / `--until` | string | Inclusive whole UTC date or ISO timestamp. Filters newer rows, keeps undated rows and does not stop the walk. CLI --published-before/--end-date/--to-date become until, never extra JSON properties. |
| `stop_at_id` / `--stop-at-id` | string | Known post.id or post.url: stop just before that non-pinned tweet and subsequent rows, with stopped_at=known_id and no next cursor. A pin never triggers it. If absent, the full page/cursor remains. End means exhausted; null means more may remain. Preserve long IDs/URLs verbatim; no integer conversion. |
| `trim` / `--trim` | boolean | Compatibility-only and ignored; it has no visible effect on canonical results. Never strip fields or promise faster/cheaper results. |
| `async` / `--async` | boolean/integer/string | JSON: true/false, 1/0, "true"/"false"/"1"/"0" with exact types preserved. CLI true/false becomes boolean and 1/0 integer. Independent of fixed wrapper response_mode=json. |

One operation returns one page and never follows a cursor or downloads media automatically. Filtering retains normal page costs. An empty until-filtered page can keep a cursor, while old pins do not prove chronological exhaustion. Trust native stop/cursor metadata rather than reapplying local date/pin logic. A completed state is a saved snapshot; an intentionally new refresh/daily check needs a new state/client ID and the desired since/stop_at_id boundary. Retries reuse the original request instead.

Static date aliases are CLI-only conveniences. JSON accepts only declared fields; resolve relative dates before invoking and preserve the chosen date on retries. No publish_time, max_age_days, max_cursor, query, sort/sort_rows, seen, switch_from, relevance, min_views, include, limit, page, count, user_id, URL, exclude_replies or exclude_retweets control is declared. Do not synthesize a query with from:handle or switch to a search route automatically. This schema does not establish the reply/retweet coverage of the native page.

## Goal fitting and previews

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `fit` / `--fit` | string goal | Retains goal-relevant rows/fields, uncertain content and first/last blocks; stubs the rest. Preserve data.held_back IDs/recall ID without inventing a follow-up route. |
| `goal` / `--goal` | string | Objective required for meaningful fit=goal, up to 300 characters per description. Do not invent it. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content budget; uncertain/first/last blocks may exceed it. No numeric bounds are declared. |
| `dry_run` / `--dry-run` | string 1 | Cost preview without fetching/judging, described as 0 credits. Preserve data.estimate rows_expected/rows_cached/label_credits_min/max/base_credits. Never automatically follow it with a paid fetch. |

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
