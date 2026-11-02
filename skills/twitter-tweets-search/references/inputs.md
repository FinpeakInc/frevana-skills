# Tweet search inputs

Only query is required. Omitted options stay omitted, including the backend's described latest ranking and free default judgments. The helper validates schema types/enums/bounds, a nonempty query and the explicitly documented since/sort conflict. Detailed feature combinations and date syntax belong to the backend. CLI hyphens map to snake_case JSON names.

## Search, pagination and boundaries

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `query` / `--query` | string | Nonempty keyword/phrase. Preserve quotes and X operators verbatim: since:YYYY-MM-DD, until:YYYY-MM-DD, from:handle, min_faves:20, filter:images, filter:videos. They constrain the source query itself. Quote multi-word phrases when relevant to the user's request; never silently rewrite a supplied query. |
| `sort` / `--sort` | latest or top | Latest is the described default, newest first. Top ranks engagement rather than relevance and can return popular posts matching none of the unquoted terms. No relevance/popular enum or sort_by field is declared. |
| `cursor` / `--cursor` | string | Exact pagination.next_cursor from the preceding response; omit for page 1. New requested page means new state/client ID, same query/options and exact cursor. No decoding, integer conversion, arithmetic or automatic paging. |
| `since` / `--since` | string | Inclusive YYYY-MM-DD midnight UTC or ISO timestamp. Drops older rows and stops the walk at stopped_at=since with no next cursor. Keeps undated rows. Requires latest: omitted sort stays omitted; explicit top is rejected without changing it. CLI --published-after/--start-date/--from-date map here. Query-embedded since: remains independent and is never extracted. |
| `until` / `--until` | string | Inclusive whole UTC date or ISO timestamp. Drops newer rows, keeps undated rows and does not end the walk. CLI --published-before/--end-date/--to-date map here. It is separate from a query-embedded until: operator. |
| `max_age_days` / `--max-age-days` | integer 1–3650 | Keeps dated rows within that many days; undated rows are dropped. Remains the declared integer, rather than being converted into since or recomputed at retry. Its description also mentions relative since aliases: preserve the formal schema boundary and do not guess alias precedence. |
| `min_views` / `--min-views` | integer ≥0 | Keeps rows with post.engagement.views at least the floor; unknown counts are discarded. No upper bound is declared. |
| `sort_rows` / `--sort-rows` | string views | Orders kept rows highest views first across the pages walked by the backend; unknown views last. This is distinct from native search sort. It does not authorize helper continuation or local sorting of raw results. |
| `async` / `--async` | boolean/integer/string | Exact JSON variants: booleans, integers 0/1, strings "true", "false", "1", "0". CLI true/false becomes boolean and 1/0 integer. Independent of fixed wrapper response_mode=json. |
| `seen` / `--seen` | string | Caller-chosen 1–64 letters/digits/`.`/`_`/`-` per description. Account-private row-ID memory, expires 24 hours after last use. Share it across related searches only when requested; it is not client_task_id. Repeats are removed and data.walk.repeats reports them. Page price discounts as ceil(page credits × new rows / all rows); all-repeat page is described as free. Joined-data credits are described separately, but include is undeclared here. Preserve returned accounting instead of predicting all costs. |

One helper operation returns one page and never automatically follows a cursor. Filtering keeps normal fetched-page costs; data.walk.discarded and request_ids identify the filtering/accounting scope. Preserve them without automatically fetching transaction details. Until can leave an empty page with continuation. Trust native stop metadata instead of inferring exhaustion from an empty/old row. No output schema or fixed page size was supplied.

The description mentions publish_time relative presets and other date aliases. Only the static CLI aliases above are implemented; alias keys are not valid JSON properties. Resolve a requested relative date into an explicit since before invoking, with its timezone/date stated, and persist that original payload. Do not forward publish_time, start_date or published_before as undeclared extras. Keep declared max_age_days as an integer.

## Relevance, goal fitting and receipts

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `relevance` / `--relevance` | score or filter | Omission can still add free query relevance without dropping/reordering rows. Score explicitly waits for judgments; filter drops unrelated rows and reports data.relevance.dropped_ids. Unjudged rows remain, with null relevance. Pagination is unchanged, so pages can be shorter. |
| `relevant_to` / `--relevant-to` | string | Custom topic with relevance, up to 200 characters per description, replacing the query as judgment topic. The source query remains unchanged. Custom-topic judgments add 1 credit per started 25 newly judged rows; same-topic cached judgments/pages are described as free. Omit unless requested. |
| `relevance_threshold` / `--relevance-threshold` | string | Probability 0–1, described default 0.5 for filtering. Lower keeps more rows. No numeric type, enum or formal bounds are declared; preserve the supplied string. |
| `fit` / `--fit` | string goal | Keeps relevant/uncertain rows/fields plus first/last blocks, stubs the rest. Preserve data.held_back IDs/recall ID without inventing a recall API. |
| `goal` / `--goal` | string | Objective required for meaningful fit=goal, up to 300 characters per description. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content cap; uncertain/first/last blocks may exceed it. No numeric bounds are declared. |
| `switch_from` / `--switch-from` | string | Optional brand. data.switch_receipts lists first-hand statements about leaving that brand, verbatim text, reason, destination and link, without a percentage. No extra credits per description. Do not infer total churn or causality. |
| `dry_run` / `--dry-run` | string 1 | Preview without fetching/judging, described as 0 credits. Preserve data.estimate rows_expected/rows_cached/label_credits_min/max/base_credits. Never automatically follow a preview with a paid fetch. |

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

No limit, include, page, max_items, expand, trim, sort_by, max_cursor, region/country, handle/user_id, format, media-download or profile-enrichment field is declared. Do not import controls from video/profile or extension skills.
