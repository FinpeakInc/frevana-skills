# TikTok search inputs

Only query is required. Omitted options stay omitted. The bundled schema declares all 32 accepted fields, including integer limit/cursor and no include or max_items. The helper validates declared types, exact enums and numeric bounds; the backend owns detailed feature combinations, dates and ISO code syntax. CLI date aliases normalize into since/until before persistence. No relative-time alias is exposed.

## Query, page modes and search scope

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `query` / `--query` | string | Nonempty video search keyword/phrase. Preserve the original string; never construct related queries locally. |
| `sort_by` / `--sort-by` | `relevance`, `most-liked`, `date-posted` | Native search ranking. Preserve on cursor continuation. Expanded fallback rows can have different ranking order. |
| `date_posted` / `--date-posted` | string enum | `yesterday`, `this-week`, `this-month`, `last-3-months`, `last-6-months`, `all-time`. Keep the literal, without recomputing a date. Do not inherit Instagram date enums. |
| `limit` / `--limit` | integer 1–120 | ≤30 truncates a normal page; >30 selects bulk single-page behavior described below. No helper default or local rounding. |
| `cursor` / `--cursor` | integer | Native returned cursor, including 0. No bounds are declared. Copy exactly; do not treat it as a page number or decode/increment it. Ignored by the backend when limit >30. |
| `expand` / `--expand` | boolean | Explicitly permits fallback beyond the original query/ranking into related searches containing every original query word, then the other rankings, retaining date/region. It is not automatic helper pagination. |
| `seen` / `--seen` | string | User-chosen 1–64 letters/digits or `._-` per description. Account-private row-ID memory lasts 24 hours from last use. Share among related searches only when requested; it is independent of task/client ID. |
| `trim` / `--trim` | boolean | Accepted for compatibility only; no effect because the response is already canonical. Never remove fields locally or promise a smaller/faster/cheaper result. |
| `async` / `--async` | boolean/integer/string | Exact JSON variants: booleans, integers 0/1, strings `"true"`, `"false"`, `"1"`, `"0"`. CLI true/false becomes boolean, 1/0 integer. JSON input preserves strings. Independent of wrapper JSON response mode. |

The supplied description prices a normal limit≤30 page at 1 credit. A smaller limit only returns the first N rows, while next_cursor advances the whole approximately 30-row page, skipping its omitted tail. It does not create a lossless small-page walk. Do not claim limit is a total result/walk budget.

Above 30, capacity rounds up to the next 30-slot block (60, 90, 120) in the backend; requested 31 is sent as 31, not rewritten to 60. The description quotes 17 credits at 60 and 32 at 120, with unfilled slots refunded; it does not specify 90-slot pricing. Do not extrapolate that rate. Bulk rows include registered region and source duplicates are removed, so a 120-slot request may return fewer unique videos. Bulk is single-page and ignores a supplied cursor; do not infer that this can page through repeated 120-result requests. Report actual accounting or an explicitly requested preview.

Expand continues past the approximate native 200–400-video boundary using supported related searches and other rankings, at the described normal page cost per fetched page. This range is not a guaranteed cap. Cross-page repeats can occur, so deduplicate by post.id only when building an explicitly requested combined collection, retaining raw pages. Rows from other rankings need not match the initial sort_by order. The description mentions max_items but it is absent from the schema: do not send it or invent a bulk collector option. A normal next-page operation copies the returned integer cursor and unchanged options to a new state/client ID; retries use the original state. The helper never requests additional pages or related queries by itself.

Seen discounts the base page price by the share of newly received rows, rounded up; an all-repeat page is described as base-price free. Joined feature charges are not discounted, and cached/new judgment rules are separate. Do not promise a zero total bill from repetition alone. Preserve data.walk.repeats and native accounting. All prices/cache/refunds here come from the supplied description, not verified live billing.

## Proxy, registered-country and row filters

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `region` / `--region` | string | Proxy country, intended ISO 3166-1 alpha-2. Does not restrict video registered country. No market enum is declared. |
| `country` / `--country` | string CSV | Keep only videos registered to listed codes (e.g. `US,GB`) at post.ext.region. Unknown-country rows are discarded. Does not select proxy location. |
| `exclude_country` / `--exclude-country` | string CSV | Drop listed registered countries (e.g. `IN`). Unknown-country rows are kept. Do not guess precedence for overlapping include/exclude lists; the backend owns it. |
| `since` / `--since` | string | Inclusive start: UTC midnight date (`YYYY-MM-DD`) or ISO timestamp. Older rows are omitted but search does not stop at the date; undated rows remain. CLI aliases `--published-after`, `--start-date`, `--from-date` become since. |
| `until` / `--until` | string | Inclusive end: whole UTC day or ISO timestamp. Newer rows are omitted without ending the walk; undated rows remain. CLI aliases `--published-before`, `--end-date`, `--to-date` become until. |
| `max_age_days` / `--max-age-days` | integer 1–3650 | Keep recent post.published_at values; unknown dates are discarded. This declared integer stays unchanged on retries, even though the date description also mentions it as an alias. |
| `min_views` / `--min-views` | integer ≥0 | Keep post.engagement.views at/above the floor; unknown counts are discarded. |
| `sort_rows` / `--sort-rows` | string `views` | Backend orders kept rows by descending views across the pages it processes, unknown counts last. Distinct from native sort_by. The helper does not fetch extra pages, sort or merge responses. |

Country fields concern the video registration leaf, not creator origin or filming location; no creator-card lookup/include option is supplied. Region alone never makes results country-exclusive. Country/date/view filtering happens after fetching each page; walked pages retain normal charges even if all rows are discarded. Preserve data.walk.discarded/request_ids and continuation metadata. An empty date-filtered result can still have a next cursor; no local chronological stopping rule is applied.

## Relevance, goal fitting and previews

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `relevance` / `--relevance` | `score` or `filter` | Default query-topic relevance is free, potentially pending/null, without dropping/reordering. Score requests explicit completion; filter also drops irrelevant rows and reports IDs. Unjudged rows remain and pagination is unchanged. |
| `relevant_to` / `--relevant-to` | string | With relevance: custom topic up to 200 characters per description, replacing query as judgment topic. Can add costs; never infer it from goal automatically. |
| `relevance_threshold` / `--relevance-threshold` | string | With relevance filtering: probability threshold 0–1, description default 0.5. Lower keeps more rows; higher keeps fewer. Keep the string type. |
| `fit` / `--fit` | string `goal` | Retains goal-relevant rows/fields, uncertain content and first/last blocks; stubs the rest. Preserve data.held_back IDs/recall ID. No recall route was supplied; do not invent a follow-up call. |
| `goal` / `--goal` | string | Required for meaningful goal fitting; user's objective up to 300 characters per description. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content budget with fit=goal; uncertain/first/last blocks can exceed it. No numeric bounds are declared. |
| `dry_run` / `--dry-run` | string `1` | Cost preview without fetching the page or judging rows, described as 0 credits. Preserve data.estimate and never automatically proceed to a paid search. |

Query-topic relevance is described as free; relevant_to adds 1 credit per started 25 newly judged rows, with same-topic cached judgments free. Preserve pending/null/dropped metadata and do not treat model scores as certainty.

## Labels and exclusions


| JSON / CLI flag | Type | Meaning |
| --- | --- | --- |
| `label` / `--label` | string CSV | Adds named labels alongside defaults. Options described below. `none` disables default judgments. No token enum is declared; the backend remains authoritative. |
| `judgments` / `--judgments` | string `on` or `off` | Server defaults to on: free sponsored/intent/niche judgments and query relevance, with complete/partial/skipped status and pending rows. They do not alter existing fields, drop or reorder rows. Pending labels may be null until a later read. Off disables those additions; the helper does not add this option by default. |
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
