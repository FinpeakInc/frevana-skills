# Facebook post search inputs

Only query is required. Omitted options stay omitted. The helper validates declared types/enums/bounds and nonempty query; detailed date/feature combinations and location-ID syntax belong to the backend. CLI hyphens map to snake_case JSON names. Preserve the caller's exact query/options rather than adding search operators or profile controls.

## Search scope and continuation

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `query` / `--query` | string | Nonempty keyword/phrase, preserved verbatim. No separate profile, account, page ID or URL input is declared. |
| `cursor` / `--cursor` | string | Exact token from a compatible prior response. No native alternate token field or token-construction rule supplied. Explicit next page uses new state/client ID, same query/options and exact token. No automatic paging, decoding, arithmetic or integer conversion. |
| `recent_posts` / `--recent-posts` | boolean | True ranks by recency rather than relevance. False/omission preserved. It is not an enum or sort/sort_by field. Does not authorize local re-ranking or date-based stopping. |
| `location_uid` / `--location-uid` | string | Facebook location ID scopes search. Preserve long/leading-zero strings verbatim. No formal numeric pattern, place-name lookup, code normalization or country/author-origin inference is declared. Never guess the ID. |
| `start_date` / `--start-date` | string | Include posts on/after YYYY-MM-DD. Declared native field, not a since alias. Detailed cursor/undated semantics and precedence with since are not specified. |
| `end_date` / `--end-date` | string | Include posts on/before YYYY-MM-DD. Declared native field, not an until alias. Do not assume another endpoint's period-carrying cursor behavior. |
| `since` / `--since` | string | Inclusive YYYY-MM-DD midnight UTC or ISO timestamp. Per-page filtering, keeps undated rows, and does not stop the nonchronological walk. CLI --published-after/--from-date map here; --start-date does not. |
| `until` / `--until` | string | Inclusive whole UTC date or ISO timestamp. Filters newer rows, keeps undated rows and does not end the walk. CLI --published-before/--to-date map here; --end-date does not. |
| `max_age_days` / `--max-age-days` | integer 1–3650 | Relative date filter; undated rows dropped. Preserve integer, never recompute as since on retry. Description's alias mention does not change the formal schema or establish precedence with other dates. |
| `async` / `--async` | boolean/integer/string | Exact JSON variants: booleans, integers 0/1, strings "true"/"false"/"1"/"0". CLI true/false becomes boolean, 1/0 integer. Independent of fixed wrapper response_mode=json. |
| `seen` / `--seen` | string | Caller-selected 1–64 letters/digits/`.`/`_`/`-` per description. Account-private row-ID memory expires 24h after last use. Removes repeats under the same ID, reports data.walk.repeats. Distinct from client_task_id; never generate automatically. |

One invocation returns one logical page without automatic profile/media reads or continuation. A READY task does not exhaust search while a cursor remains. Empty/old filtered pages can keep next_cursor and still cost normal page credits. Trust native continuation/discard metadata instead of local chronology assumptions, including when recent_posts=true. Preserve raw order/duplicates/nulls. No fixed page size, complete output schema or guarantee of exhaustive coverage was supplied.

Native start_date/end_date and row filters since/until are separate declared inputs. Preserve all explicitly supplied values without normalizing one into another or guessing precedence. Static noncolliding CLI aliases above map only to since/until. Publish_time and undeclared alias JSON keys are rejected despite descriptions mentioning them. Resolve requested relative-date aliases before invoking with timezone/date context and persist the chosen literal. Max_age_days remains the declared integer. No limit, max_items, trim, sort/sort_by/sort_rows, after, include, region/country, separate profile, body-read or download controls are declared.

Filtering retains normal page price; data.walk.discarded/request_ids report native filtering and billing scope. Do not automatically query transaction records. Seen discounts only page price as ceil(page credits × new rows / page rows); all-repeat pages are described as free. Shared descriptions mention separate joined-data charges, but include is undeclared here. Preserve actual accounting rather than predict all costs or introduce an enrichment field.

## Relevance, goal fitting and previews

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `relevance` / `--relevance` | score/filter | Omission can still add free query relevance without dropping/reordering. Score explicitly waits for judgments; filter drops unrelated rows under data.relevance.dropped_ids. Unjudged rows remain with null relevance, pagination unchanged. |
| `relevant_to` / `--relevant-to` | string | Custom judgment topic with relevance, up to 200 characters per description, instead of query. Does not rewrite source search. Adds 1 credit per started 25 newly judged rows; same-topic prior judgments/cached pages described as free. |
| `relevance_threshold` / `--relevance-threshold` | string | Probability 0–1, described default 0.5. Lower keeps more. Preserve string; no numeric type or formal bounds declared. |
| `fit` / `--fit` | string goal | Retains relevant/uncertain content plus first/last blocks; stubs the rest. Preserve data.held_back IDs/recall ID; no recall API supplied. |
| `goal` / `--goal` | string | Objective required for meaningful fit=goal, up to 300 characters per description. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content budget; uncertain/first/last blocks may exceed it. No numeric bounds declared. |
| `dry_run` / `--dry-run` | string 1 | Preview without fetching/judging, described as 0 credits. Preserve data.estimate rows_expected/rows_cached/label_credits_min/max/base_credits; never automatically proceed to a paid fetch. |

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
