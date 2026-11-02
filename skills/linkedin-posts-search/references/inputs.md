# LinkedIn post search inputs

The empty top-level required list is qualified by allOf/anyOf: at least one of query/from_member/from_company is required. Combinations are schema-permitted; preserve them without inventing how multiple subject filters combine. Omitted fields stay omitted. Helper checks documented subject-ID forms and mode conflicts; backend owns detailed ID/date/feature validation.

## Scope, ordering and modes

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `query` / `--query` | string | Keyword/phrase. Optional with a subject; omit for unfiltered subject posts. A supplied content word narrows results. Nonempty when supplied; do not insert a name, wildcard or dummy query. |
| `from_member` / `--from-member` | string | Bare ACoAA… member URN (described ID source author.ext.urn from profile data). No URL, public slug or urn:li:fsd_profile: prefix. Helper checks the bare prefix/nonempty form, no whitespace; detailed identity validation backend-owned. Never resolve, strip or guess it automatically. |
| `from_company` / `--from-company` | string | Numeric company ID, example 1035 (described ID source author.id from company data). ASCII digit string, not a slug/URL. Preserve leading zeros/long value rather than integer conversion. No company/profile lookup schema supplied here. |
| `sort_by` / `--sort-by` | date_posted/relevance | Query mode described default relevance. Subject-only mode is date-ordered: omission preserved, explicit date_posted allowed, relevance rejected locally. Do not invent query or change sort to bypass the conflict. |
| `content_type` / `--content-type` | videos/photos/jobs/live_videos/documents/collaborative_articles | Narrow kind of post. Do not switch to job-search/profile APIs or locally drop native mixed/uncertain rows. |
| `date_posted` / `--date-posted` | past_24h/past_week/past_month | Indexed-results date filter with underscores. Not job-search past_24_hours, not actual post timestamp coverage or a since alias. |
| `cursor` / `--cursor` | string | Exact pagination.next_cursor, mapped by API to native page. Omit for page 1. No constructing/decoding/numeric coercion or automatic continuation. Mutually exclusive with page and limit. |
| `page` / `--page` | integer ≥1 | Native 1-based indexed-results page, described default 1. No maximum declared. Prefer universal cursor. Cannot combine with cursor or limit, including page=1. Never automatically increment. |
| `limit` / `--limit` | integer 1–200 | Bounded backend collection from top, paging/deduplicating to return up to this many posts. Requires query, cannot combine with page/cursor. Not ordinary page size; never auto-enable, lower or reinterpret it for subject-only requests. |
| `async` / `--async` | boolean/integer/string | Exact JSON variants: booleans, integers 0/1, strings "true"/"false"/"1"/"0". CLI true/false becomes boolean, 1/0 integer. Independent of fixed wrapper response_mode=json. |

Default is one logical page without helper continuation or enrichment. Explicit ordinary next pages use new state/client ID, same query/subjects/options and exact string cursor or explicitly chosen native page. Retain cursor provenance. A READY task completes an operation, not exhaustive coverage while continuation remains.

Bounded mode costs a described 1 credit per 5 returned posts (200 = 40 credits); identical-call server caching for 2 minutes is described as free. Preserve actual accounting/rounding. A saved completed local state returns the original snapshot regardless of that cache window; cache pricing is not task idempotency or permission to create extra tasks. Bounded next_cursor is null even when has_more=true: report has_more plus native walk.stopped (limit/exhausted/deadline/sources_unavailable), not an invented continuation/exhaustion claim. Deadline/source shortages may yield fewer rows. Do not refill, increase limit or switch sources automatically.

## Row dates and optional processing

| JSON / CLI | Type | Meaning |
| --- | --- | --- |
| `since` / `--since` | string | Inclusive midnight UTC date or ISO timestamp. Per-page filtering on a nonchronological list: keeps undated rows, does not stop walk. CLI --published-after/--start-date/--from-date map here. Does not require a particular sort_by on query-bearing calls. |
| `until` / `--until` | string | Inclusive whole UTC date or ISO timestamp. Filters newer rows, keeps undated rows, does not end walk. CLI --published-before/--end-date/--to-date map here. |
| `relevance` / `--relevance` | score/filter | Omission can add free query judgments without dropping/reordering. Score waits for judgments; filter drops unrelated rows under data.relevance.dropped_ids. Unjudged rows stay with null relevance, pagination unchanged. No placeholder query for subject-only requests. |
| `relevant_to` / `--relevant-to` | string | Custom judgment topic with relevance, up to 200 characters per description, instead of query. Never rewrites source query/subjects. Adds 1 credit per started 25 newly judged rows; same-topic prior judgments/cached pages described as free. |
| `relevance_threshold` / `--relevance-threshold` | string | Probability 0–1, described default 0.5; lower keeps more. Preserve string, no numeric type/formal bounds declared. |
| `fit` / `--fit` | string goal | Retains relevant/uncertain content plus first/last blocks, stubs rest. Preserve data.held_back IDs/recall ID; no recall route supplied. |
| `goal` / `--goal` | string | Objective required for meaningful fit=goal, up to 300 characters per description. |
| `fit_tokens` / `--fit-tokens` | integer | Soft retained-content budget; uncertain/first/last blocks may exceed it. No numeric bounds declared. |
| `dry_run` / `--dry-run` | string 1 | Preview without fetching/judging, described as 0 credits. Preserve data.estimate rows_expected/rows_cached/label_credits_min/max/base_credits; never automatically follow with paid collection/lookup. |

Dates do not imply a chronological stop; empty/old pages can retain continuation and still cost normal page credits. Preserve native walk/stop/accounting metadata without local filtering. Descriptions mention publish_time/max_age_days and aliases, but neither relative field is declared here. Only static CLI aliases above are implemented; alias JSON keys are rejected. Resolve requested relative date to since before invocation with timezone/date context and persist the original literal. No seen, trim, include, sort_rows, location, min_views, job-specific date vocabulary, account-resolution or download controls are declared.

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
