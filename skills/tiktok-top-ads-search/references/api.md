# Frevana TikTok Creative Center Top Ads API

Default host: `https://ai-factory.frevana.com`. Authentication: `Authorization: Bearer <FREVANA_TOKEN>`.

## Create

`POST /service/tiktok-top-ads/tasks` returns HTTP 202 with a task object and `client_task_id`. The server also exposes `/apify/tiktok-top-ads/tasks`; the helper uses `/service/`. Unknown fields and null values are rejected. Provide `keyword`, `start_urls`, or both.

| JSON field | CLI option | Contract / server default |
| --- | --- | --- |
| `client_task_id` | `--client-task-id` | Trimmed nonempty string, max 128 characters. Helper generates one before requesting if omitted. Same ID + same normalized options returns the same task; changed options return 409. |
| `keyword` | `--keyword` | Search by brand or product keyword, e.g. `skincare`. Trimmed nonempty string, max 256 characters. |
| `start_urls` | Repeat `--start-url` | 1–5 strings, each max 2048 characters. HTTPS on `ads.tiktok.com`, no credentials or nondefault port. Path begins `/business/creativecenter/topads/` or `/business/creativecenter/inspiration/topads/`. Fragments removed; URLs deduplicated and sorted. URL query `region` corresponds to `country`; `rid`, `is_new_connect`, and `is_new_user` are unnecessary. Omit URLs when searching by keyword alone. |
| `country` | Repeat `--country` | Ad display country/region codes as a nonempty string array, e.g. `["ID", "US"]`. The helper defaults to the 28-country selection below; explicit `--country` values replace it. Direct API callers can omit `country` for no restriction. Do not send `"all"` or an empty array. |
| `industry` | Repeat `--industry` | Industry string-code array, `10` through `30`; e.g. `["14"]` for Beauty & Personal Care. Do not send result `industryKey` or `label_` identifiers. Omit for no restriction. |
| `objective` | Repeat `--objective` | Marketing objective string-code array; e.g. `["15"]` for Product Sales or `["1", "3"]` for Traffic and Conversions. Do not send result `objectiveKey`. Omit for no restriction. |
| `ad_language` | Repeat `--ad-language` | Ad content language string array, e.g. `["id", "en"]`; independent of the webpage interface language `/en` in a start URL. Omit for no restriction. |
| `ad_format` | `--ad-format` | Single string `1` for Spark Ads or `2` for Non-Spark Ads; not an array. Omit for no restriction. |
| `order_by` | `--order-by` | `ctr`, `for_you`, `impression`, `play_2s_rate`, `play_6s_rate`, `cvr`, `like`; default `for_you`. |
| `period` | `--period` | Single string selecting the last `7`, `30`, or `180` days; default `30`. Do not send a JSON number. |
| `max_items` | `--max-items` | Integer 1–100, default 5 **per source**. |

Array filters are case-sensitive, deduplicated, and sorted by the server. Input array length must not exceed its allowlist size. Country/industry/objective/language filters may combine with either input mode. Use the backend-defined mappings below to translate user intent into codes. Industry and objective codes must be quoted strings in JSON; `max_items` is a JSON integer. Sorting selects a metric, not a numeric threshold (e.g. send `"ctr"`, not a CTR value).

### Countries and regions

81 countries and regions are supported. The skill defaults to these 28 codes: `AR AU BR CA CO FR DE ID IT JP MY MX NL PK PH RO SA SG ZA KR ES SE TH TR AE GB US VN`. When `--country` is omitted, the helper sends this array explicitly in both keyword and URL modes. Explicit country flags replace the default list rather than adding to it. Direct API requests without `country` have no country restriction. A start URL may contain a `region` filter; check it for consistency with the requested selection and preserve caller URLs.

| Value | Meaning |
| --- | --- |
| `DZ` | Algeria |
| `AR` | Argentina |
| `AU` | Australia |
| `AT` | Austria |
| `AZ` | Azerbaijan |
| `BH` | Bahrain |
| `BD` | Bangladesh |
| `BY` | Belarus |
| `BE` | Belgium |
| `BO` | Bolivia |
| `BR` | Brazil |
| `BG` | Bulgaria |
| `KH` | Cambodia |
| `CA` | Canada |
| `CL` | Chile |
| `CO` | Colombia |
| `CR` | Costa Rica |
| `HR` | Croatia |
| `CY` | Cyprus |
| `CZ` | Czech Republic |
| `DK` | Denmark |
| `DO` | Dominican Republic |
| `EC` | Ecuador |
| `EG` | Egypt |
| `EE` | Estonia |
| `FI` | Finland |
| `FR` | France |
| `DE` | Germany |
| `GR` | Greece |
| `GT` | Guatemala |
| `JO` | Jordan |
| `HU` | Hungary |
| `ID` | Indonesia |
| `IQ` | Iraq |
| `IE` | Ireland |
| `IL` | Israel |
| `IT` | Italy |
| `JP` | Japan |
| `KZ` | Kazakhstan |
| `KE` | Kenya |
| `KW` | Kuwait |
| `LV` | Latvia |
| `LB` | Lebanon |
| `MY` | Malaysia |
| `MX` | Mexico |
| `MA` | Morocco |
| `NL` | Netherlands |
| `NZ` | New Zealand |
| `NG` | Nigeria |
| `NO` | Norway |
| `OM` | Oman |
| `PK` | Pakistan |
| `PA` | Panama |
| `PY` | Paraguay |
| `PE` | Peru |
| `PH` | Philippines |
| `PL` | Poland |
| `PT` | Portugal |
| `PR` | Puerto Rico |
| `QA` | Qatar |
| `LT` | Lithuania |
| `RO` | Romania |
| `SA` | Saudi Arabia |
| `RS` | Serbia |
| `SG` | Singapore |
| `SK` | Slovakia |
| `SI` | Slovenia |
| `ZA` | South Africa |
| `KR` | South Korea |
| `ES` | Spain |
| `LK` | Sri Lanka |
| `SE` | Sweden |
| `CH` | Switzerland |
| `TW` | Taiwan |
| `TH` | Thailand |
| `TR` | Turkey |
| `AE` | United Arab Emirates |
| `GB` | United Kingdom |
| `US` | United States |
| `UY` | Uruguay |
| `VN` | Vietnam |

### Industries

| Value | Meaning |
| --- | --- |
| `10` | Education |
| `11` | Automotive & Transportation |
| `12` | Baby, Kids & Maternity |
| `13` | Financial Services |
| `14` | Beauty & Personal Care |
| `15` | Technology & Electronics |
| `16` | Home Appliances |
| `17` | Travel |
| `18` | Household Products |
| `19` | Pets |
| `20` | Apps |
| `21` | Home Improvement |
| `22` | Apparel & Accessories |
| `23` | News & Entertainment |
| `24` | Business Services |
| `25` | Games |
| `26` | Life Services |
| `27` | Food & Beverages |
| `28` | Sports & Outdoors |
| `29` | Health |
| `30` | E-commerce (Non-App) |

### Marketing objectives

| Value | Meaning |
| --- | --- |
| `1` | Traffic |
| `2` | App Installs |
| `3` | Conversions |
| `4` | Video Views |
| `5` | Reach |
| `8` | Lead Generation |
| `15` | Product Sales |

### Ad content languages

| Value | Meaning |
| --- | --- |
| `en` | English |
| `es` | Spanish |
| `ar` | Arabic |
| `vi` | Vietnamese |
| `th` | Thai |
| `de` | German |
| `id` | Indonesian |
| `pt` | Portuguese |
| `fr` | French |
| `ms` | Malay |
| `nl` | Dutch |
| `ja` | Japanese |
| `it` | Italian |
| `ro` | Romanian |
| `zh-Hant` | Traditional Chinese |
| `ko` | Korean |

### Ad formats

| Value | Meaning |
| --- | --- |
| `1` | Spark Ads: ads using native TikTok posts, including authorized creator posts |
| `2` | Non-Spark Ads |

### Sort order

| Value | Meaning |
| --- | --- |
| `ctr` | CTR: click-through rate |
| `for_you` | For You: recommended order (default) |
| `impression` | Reach |
| `play_2s_rate` | 2-second views rate |
| `play_6s_rate` | 6-second views rate |
| `cvr` | CVR: conversion rate |
| `like` | Likes |

### Time period

| Value | Meaning |
| --- | --- |
| `7` | Last 7 days |
| `30` | Last 30 days (default) |
| `180` | Last 180 days |

```json
{"client_task_id":"stable-search","keyword":"skincare","country":["ID","US"],"industry":["14"],"objective":["15"],"ad_language":["id","en"],"ad_format":"1","period":"30","order_by":"ctr","max_items":20}
```

Creation checks estimated credits and actual usage settles asynchronously. Multiple URL sources and a keyword can increase the estimate and result count; `max_items` is not a global limit or a guaranteed final charge cap.

## Status and polling

`GET /service/tiktok-top-ads/tasks/{task_id}` requires an owned UUID v4. The public task response has no `billing_status`.

```json
{"task_id":"7af283fe-13aa-431d-a7cf-b58675701884","status":"RUNNING","result_available":false,"result_count":0,"error_code":null,"error_message":null,"next_poll_after_ms":5000}
```

- `PENDING`, `RUNNING`, `SETTLING`: follow `next_poll_after_ms` (currently 5000); settlement can include billing retries.
- `READY`: retrieve only when `result_available=true` (currently implies billing complete).
- `FAILED`, `REVIEW_REQUIRED`, `RESULT_EXPIRED`: stop and report the returned error fields. Do not resubmit automatically.
- Zero poll delay without an available result stops automatic polling.

The helper defaults to a six-hour wait budget. `--timeout 0` disables the budget. Resume `wait` with the same task ID; creation failures are never automatically retried.

## Result

`GET /service/tiktok-top-ads/tasks/{task_id}/result` streams a JSON array in stored item order. HTTP 409 means unavailable, 410 means expired, and 404 can mean nonexistent or inaccessible. Preserve successful response bytes and do not overwrite existing output on HTTP or JSON errors.

Each ad requires string `id` (1–32 decimal digits). Optional fields can include `title`, `brandName`, `countryCodes`, `landingPage`, `source`, `industryKey`, `objectiveKey`, `objectives`, `ctr`, `cost`, `likes`, `comments`, `shares`, `videoId`, `videoDuration`, `videoCover`, `videoUrls`, `videoWidth`, `videoHeight`, `retainCvr`, `retainCtr`, `clickCount`, `conversionCount`, and `playRetainCount`. Full upstream JSON is preserved. Do not convert missing metrics to zero or describe `cost` as monetary spend without further evidence. Media are not archived by this API; URLs may expire.

The server limits stored results to 50 MiB and items to 1 MiB; the helper limits responses to 52 MiB.

The backend also offers `GET /service/tiktok-top-ads/tasks/{task_id}/items?offset=0&limit=100` (offset >= 0, limit 1–1000) returning `{task_id, offset, limit, count, total, items}`. The helper uses the full `/result` endpoint and does not paginate `/items`.
