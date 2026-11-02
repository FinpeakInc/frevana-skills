# TikTok profile video inputs

The schema's allOf/anyOf requires handle or user_id despite an empty top-level required list. Both are permitted; do not invent a second identifier or resolve it automatically. The helper preserves identifier strings and validates declared types/enums and required composition. Other detailed date/feature-combination/ID syntax belongs to the backend. Omitted options stay omitted.

## Identifiers, pagination and boundaries

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `handle` / `--handle` | string | Nonempty TikTok username without `@`. |
| `user_id` / `--user-id` | string | Known TikTok user ID, described as faster. Keep its exact string, including long/leading-zero values; never coerce to integer. No ID pattern/length is declared here. |
| `cursor` / `--cursor` | string | Copy pagination.next_cursor verbatim. The API maps it to native max_cursor. Omit for page 1; do not decode/construct/turn it into an integer. |
| `max_cursor` / `--max-cursor` | string | Native Unix-millisecond timestamp cursor from a compatible response, or an explicitly supplied historical start. `1590969600000` is the supplied example for videos before 2020-06-01 UTC. Prefer universal cursor for ordinary continuation; never send both fields. |
| `since` / `--since` | string | Inclusive start at UTC midnight date (YYYY-MM-DD) or ISO timestamp. Older non-pinned videos end the walk with stopped_at=since and no next cursor. Pins never end the walk. |
| `until` / `--until` | string | Inclusive end: the entire UTC date or ISO timestamp. Newer rows are filtered, undated rows remain, and the walk does not stop. This does not move the starting cursor. CLI aliases --published-before/--end-date/--to-date become until, never extra JSON fields. |
| `stop_at_id` / `--stop-at-id` | string | Known post.id or post.url. Stop just before it and subsequent rows, with stopped_at=known_id; pinned entries are not stop points. If absent, the full page/cursor remains. End means list exhausted; null means more may remain. |
| `region` / `--region` | string | Proxy country, description default US. It does not filter videos by post.ext.region (registered-video country). No market enum or country-filter field is declared; do not insert a default, normalize codes or infer creator location. |
| `async` / `--async` | boolean/integer/string | Exact JSON variants: booleans, integers 0/1, strings "true", "false", "1", "0". CLI true/false becomes boolean, 1/0 integer. JSON input preserves strings. Independent of wrapper JSON response mode. |

One invocation returns one page and never downloads media or follows a cursor. Explicit continuation uses a new state/client ID, unchanged opaque string cursor and identifiers/options. Retries keep original state/body. Until alone cannot jump to history: use an explicitly selected native historical cursor if needed, without inventing a universal cursor or recomputing timestamps on retry. Filtering does not erase the normal page price. Trust backend cursor/stop metadata instead of ordering or pin assumptions.

## Compatibility and stationery grouping

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `trim` / `--trim` | boolean | Compatibility-only, no effect on the canonical response. Never strip media/duration/pin fields locally or promise a smaller/faster/cheaper record. |
| `sort_by` / `--sort-by` | latest or popular | Compatibility-only; both are ignored, and neither reorders source rows. An explicitly requested ranked aggregate can be sorted separately after authorized collection; raw page results stay unchanged. |
| `format` / `--format` | string stationery | Optional backend grouping into wedding, birthday, birth, sympathy, seasonal greeting or ungrouped, with counts/ungrouped share/by-day information under data.format_buckets. No extra credits per description. Do not create local folders or external collections. |
| `brief` / `--brief` | string | Optional subject with stationery format. If the page is off-topic, format_buckets.skip_creator is true and rows are not filed. Report this and respect the skipped walk instead of fetching more pages or changing the subject automatically. |

Preserve null saves as null, not zero. The backend owns classification/grouping; the helper neither classifies nor sorts. Grouping is explicit rather than a default. Brief alone does not make the helper add format=stationery; collect the intended paired options, and let the backend validate combinations not formally specified by the schema. Grouping/price behavior comes from the supplied description, not verified live observations.

## Goal fitting and previews

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `fit` / `--fit` | string goal | Retains goal-relevant rows/fields, uncertain content and first/last blocks; stubs the rest. Preserve data.held_back IDs/recall ID. No recall route was supplied, so do not invent a follow-up call. |
| `goal` / `--goal` | string | Required for meaningful fit=goal; user's objective up to 300 characters per description. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content budget with fit=goal. Uncertain/first/last blocks may exceed it. No numeric bounds are declared. |
| `dry_run` / `--dry-run` | string 1 | Cost preview without fetching a page or judging rows, described as 0 credits. Preserve data.estimate and never automatically proceed to a paid fetch. |

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

This endpoint declares no query, counts, include, limit, numeric search cursor, page, max_items, recent_days, max_age_days, country/exclude_country filter, sort_rows or download controls. Do not import them from TikTok search/profile or Instagram helpers.
