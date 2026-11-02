# Reddit post search inputs

Only query is required. Omitted options stay omitted. The helper validates the formal schema, nonempty query, cursor/after exclusion and the documented since/sort conflict. Backend validation owns other detailed date/feature combinations. CLI hyphens map to snake_case JSON names. Read the formal bundled schema for exact types/enums/bounds.

## Search, pages and scope

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `query` / `--query` | string | Search words match any, not all. Quote an exact phrase and preserve operators such as subreddit:name. For an unquoted query, fewer than half the rows containing every word is reported under _warnings. Preserve query/warnings without local term filtering or automatic reformulation. |
| `sort` / `--sort` | relevance/new/top/comment_count | Native ranking. Do not import latest, popular or sort_by. No default is declared here; leave it omitted unless selected. With since, omission lets the backend select new; explicit other values are rejected locally. |
| `timeframe` / `--timeframe` | all/day/week/month/year | Applies to relevance/top/comment_count, ignored with new. Do not silently remove or reinterpret it as a since date or claim it constrains newest-first results. |
| `cursor` / `--cursor` | string | Copy pagination.next_cursor exactly; the API maps it to after. Omit on page 1. No decoding, constructing, integer coercion, arithmetic or automatic continuation. |
| `after` / `--after` | string | Native next-page token from a compatible response. Prefer universal cursor. Never send both; the helper rejects ambiguity. Does not use the extension skill's separate data.after result contract. |
| `limit` / `--limit` | integer 1–1000 | Omitted/≤25 leaves the ordinary page unchanged, not truncated. >25 on an initial request selects one bulk answer up to that many posts, with roughly 1000 maximum from one query and no next page. Query/sort/timeframe still apply. A next-page after request ignores limit; universal cursor maps to after too. Preserve exact value rather than rounding, removing or raising it automatically. |
| `trim` / `--trim` | boolean | True skips the second source's widening pass, usually returning fewer rows. It does not remove author.avatar_url/ext.* leaves already present from the first source. Historical measured counts are not guarantees. Preserve native fields and do not compensate with more requests. |
| `include_body` / `--include-body` | boolean | Explicit body/selftext enrichment, described as 1 extra credit per returned body with unused credits refunded. Link posts have no body, so body lookups are not charged for them. Bodies often arrive already; omission never warrants an automatic body fetch. No separate include field is declared. |
| `since` / `--since` | string | Inclusive midnight UTC date or ISO timestamp; older rows omitted, walk ends at stopped_at=since without a next cursor. Keeps undated rows. Requires newest-first new (omitted sort stays omitted). CLI --published-after/--start-date/--from-date map here. |
| `until` / `--until` | string | Inclusive whole UTC date or ISO timestamp, filters newer rows, keeps undated rows and does not end the walk. CLI --published-before/--end-date/--to-date map here. Empty pages may still continue. |
| `max_age_days` / `--max-age-days` | integer 1–3650 | Relative date filter, drops undated rows. Remains the declared integer, not a recomputed since timestamp on retry. Its description also mentions since aliases; do not guess alias precedence. |
| `async` / `--async` | boolean/integer/string | JSON: booleans, integers 0/1, strings "true"/"false"/"1"/"0". CLI true/false becomes boolean and 1/0 integer. Independent of fixed wrapper response_mode=json. |
| `seen` / `--seen` | string | Caller-selected 1–64 letters/digits/`.`/`_`/`-` per description. Account-private row-ID memory, expires 24h after last use. Repeats removed under the same ID; data.walk.repeats reports them. Separate from client_task_id; never generate it automatically. |

One invocation is one logical operation, without helper pagination, body reads or media downloads beyond explicitly requested backend options. For an ordinary next page use a new state/client ID, exact string cursor and unchanged query/options. A completed task is not complete search coverage if continuation remains. An initial bulk answer has no next page per description; do not invent a continuation token or treat the approximate source ceiling as complete history.

Bulk pricing is described as 1 credit per 25 returned posts, with an upfront hold based on limit and unused credits refunded. Seen discounts only the page price as ceil(page credits × new rows / page rows); all-repeat pages are described as free. Joined-data credits are separate and apply to new rows, but include is undeclared here. Preserve returned accounting rather than predicting exact rounding, enrichment interactions or guaranteed result counts. Date filtering retains normal fetched-page costs. Preserve data.walk.discarded/request_ids without automatically querying transaction records.

Static date aliases are CLI-only. The description mentions publish_time relative presets; that property is undeclared. Resolve an explicitly requested relative date to since before invoking with its timezone/date stated, then persist the original payload. Alias JSON keys and undeclared max_items/page/count/q/type/sort_by/min_views/sort_rows/region/subreddit/include/download controls are rejected. Use a user-requested subreddit:name operator inside query rather than inventing a subreddit input.

## Relevance, goal fitting and preview

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `relevance` / `--relevance` | score/filter | Omission can still add free query relevance without dropping/reordering. Score explicitly waits for judgments; filter drops unrelated rows under data.relevance.dropped_ids. Unjudged rows stay with null relevance; shorter pages retain pagination. |
| `relevant_to` / `--relevant-to` | string | Custom judgment topic with relevance, up to 200 characters per description, instead of query. It never rewrites the source search. Adds 1 credit per started 25 newly judged rows; same-topic prior judgments/cached pages described as free. |
| `relevance_threshold` / `--relevance-threshold` | string | Probability 0–1, described default 0.5. Lower keeps more rows. Preserve the string; no numeric type or formal bounds are declared. |
| `fit` / `--fit` | string goal | Keeps relevant/uncertain content and first/last blocks; stubs the rest. Preserve data.held_back IDs/recall ID without inventing a recall API. |
| `goal` / `--goal` | string | Objective required for meaningful fit=goal, up to 300 characters per description. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content budget; uncertain/first/last blocks may exceed it. No numeric bounds are declared. |
| `dry_run` / `--dry-run` | string 1 | Preview without fetching/judging, described as 0 credits. Preserve data.estimate rows_expected/rows_cached/label_credits_min/max/base_credits. Never automatically proceed to a paid fetch. |

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
