# YouTube content search inputs

Only query is required. Omitted options stay omitted. The helper validates schema types/enums/bounds, nonempty query, cursor/continuationToken exclusion and documented Shorts restrictions. Detailed include CSV/date/feature validation belongs to the backend. Native camelCase names are preserved in JSON; hyphenated CLI conveniences map to them without adding properties.

## Search, type and continuation

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `query` / `--query` | string | Search keyword/phrase, preserved verbatim. No search_query, sp, hl or gl field is declared. |
| `type` / `--type` | videos/shorts/channels/playlists | Explicit kind. Omission may mix kinds. Channels have one page, described as ~20 rows with has_more=false/no next_cursor; other kinds normally page. Do not invent channel continuation. |
| `cursor` / `--cursor` | string | Exact pagination.next_cursor from a compatible prior result, mapped to native continuationToken by the API. Omit for page 1, never decode/construct/coerce or increment. |
| `continuationToken` / `--continuationToken`, `--continuation-token` | string | Native token from a compatible response. Prefer universal cursor; both together are rejected. |
| `sortBy` / `--sortBy`, `--sort-by` | relevance/popular | Popular is weighted ranking, not strict descending views, with described ~20-row cap. Popular+Shorts rejected locally. No sort or sort_by JSON alias. |
| `region` / `--region` | string | Proxy country, described as 2-letter code. No market enum or local code normalization, country filter or language field is declared. |
| `duration` / `--duration` | under_3_min/between_3_and_20_min/over_20_min | Source issue: may be ignored and degrade type filtering. Never auto-select or promise enforcement. A requested duration-derived view should separately use available duration_seconds, retain raw pages, report unknowns and not auto-fetch missing details. |
| `uploadDate` / `--uploadDate`, `--upload-date` | today/this_week/this_month/this_year | Described as reliable with no type. Shorts permits only this_year or omission; narrower values rejected locally. This_year can repeat rows under advancing tokens and reduce unique coverage. Other explicit types may ignore it and mix kinds. No strict date/typed coverage guarantee. |
| `async` / `--async` | boolean/integer/string | Exact JSON variants: booleans, integers 0/1, strings "true"/"false"/"1"/"0". CLI true/false becomes boolean and 1/0 integer. Independent of fixed response_mode=json. |

One invocation returns one page, without automatic continuation/joins/media downloads. Explicit next pages use a new state/client ID, exact string cursor and unchanged query/options; retain cursor provenance. READY finishes an operation, not all matches while continuation remains. Preserve repeats and source order. A request for a view-ranked derived result does not establish global top-view coverage. Advanced-search and per-video routes mentioned by descriptions have no supplied schemas here: do not invent or automatically call them.

## Dates, counters and enrichment

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `since` / `--since` | string | Inclusive YYYY-MM-DD midnight UTC or ISO timestamp. Per-page filter on a nonchronological list: keeps undated rows and does not stop the walk. CLI --published-after/--start-date/--from-date map here. |
| `until` / `--until` | string | Inclusive whole UTC date or ISO timestamp. Keeps undated rows, filters newer rows without stopping. CLI --published-before/--end-date/--to-date map here. |
| `max_age_days` / `--max-age-days` | integer 1–3650 | Keeps recent dated rows, drops undated. Preserve the integer, not a recomputed since date. Description's alias mention does not change the formal type or establish precedence with since. |
| `min_views` / `--min-views` | integer ≥0 | Keeps rows meeting view floor; unknown view counts dropped by backend. No upper bound declared. |
| `sort_rows` / `--sort-rows` | string views | Explicit backend ordering of kept rows highest views first across pages it walked; unknown views last. Distinct from native sortBy and not permission to fetch extra pages or sort raw rows locally. |
| `exact_dates` / `--exact-dates` | string true/false | Described default true and free, replaces relative date estimates with exact publish seconds and often creator titles. Computed language follows creator title. False skips lookup; retains estimate/precision/label and title_maybe_translated markers. Strings, never JSON booleans. |
| `includeExtras` / `--includeExtras`, `--include-extras` | string | True requests likes/comments/description; on Shorts also duration. Without it those three leaves are described as null. Adds latency and can reduce page depth; not required for default exact dates. No enum declared: preserve string, backend validates detail. Does not itself add Shorts channel identity/subscribers. |
| `include` / `--include` | string | Described tokens engagement/channel/engagement,channel; not an enum in schema. Explicit joins only, never auto channel. Engagement fills missing views/likes/comments/duration/channel_id/display_name and exact dates. Channel fills subscriber count/display_name/avatar/username/author_country where available. Both cover rows initially missing a channel ID; video joins skip channel/playlist rows. |

Default free exact-date lookup also fills Shorts channel_id/display_name. Handles/avatars remain null without channel enrichment; exact_dates=false can leave the Shorts author entirely null. Preserve missing IDs rather than infer a handle from display name or fetch another endpoint. IncludeExtras does not replace either include join. A title not replaced retains title_maybe_translated; unresolved exact dates retain published_precision/published_label and warnings exact_dates_partial/unavailable. Preserve precision/title/language markers instead of claiming all dates or titles were resolved. No channel/videos call is made by this skill.

Each include join is described as 1 credit per distinct video/channel filled and capped at 5 per 50; unresolved IDs refunded. Data.hydration reports rows/lookups/held/kept credits/time. Fresh joins add latency; historical timings/counts are examples, not guarantees. Channel subscribers above 1000 are rounded to three significant figures; owner-set author_country may be null and does not establish filming location. Preserve actual data/accounting without local filling, rounding, country filtering or retries for unresolved IDs. Source/enrichment combinations do not authorize more pages or media downloads.

Filtering retains normal page costs. Since/until can leave empty/old pages with next_cursor; do not infer exhaustion. Max_age_days/min_views discard unknowns in backend; preserve data.walk.discarded/request_ids without automatically querying billing records. Static aliases are CLI-only; publish_time and alias JSON keys are rejected. Resolve requested relative date aliases before invocation with timezone/date context and persist the original chosen payload. No limit, max_items, trim, page, hl/gl/sp, order=viewCount, separate country filter or download controls are declared.

## Relevance, fitting, deduplication and previews

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `seen` / `--seen` | string | Caller-selected 1–64 letters/digits/`.`/`_`/`-` per description; account-private row-ID memory expires 24h after last use. Repeats removed under the same ID, reported in data.walk.repeats. Distinct from client_task_id; never generate automatically. Page price discounted as ceil(page credits × new rows / page rows); all-repeat page described as free. Joined-data credits apply to new rows separately, without that discount. Preserve actual accounting. |
| `relevance` / `--relevance` | score/filter | Omission can add free query relevance without dropping/reordering. Score waits for judgments; filter drops unrelated rows under data.relevance.dropped_ids. Unjudged rows remain with null relevance, pagination unchanged. |
| `relevant_to` / `--relevant-to` | string | Custom judgment topic with relevance, up to 200 characters per description, instead of query. Does not rewrite source search. Adds 1 credit per started 25 newly judged rows; same-topic prior judgments/cached pages described as free. |
| `relevance_threshold` / `--relevance-threshold` | string | Probability 0–1, described default 0.5. Lower keeps more. Preserve string; no numeric type or formal bounds declared. |
| `fit` / `--fit` | string goal | Retains relevant/uncertain content and first/last blocks, stubs the rest. Preserve data.held_back IDs/recall ID; no recall API supplied. |
| `goal` / `--goal` | string | Objective required for meaningful fit=goal, up to 300 characters per description. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content budget, uncertain/first/last blocks may exceed it; no numeric bounds declared. |
| `dry_run` / `--dry-run` | string 1 | Preview without fetching/judging, described as 0 credits. Preserve data.estimate rows_expected/rows_cached/label_credits_min/max/base_credits; never automatically proceed to paid fetch/joins. |

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
