---
name: google-ai-overview
description: Use when the user wants a Google AI Overview through Frevana for a search query, an existing Google Search result, or a fresh ai_overview.page_token. Uses google-search first when needed, then retrieves the overview only if a follow-up request is required.
---

# Google AI Overview

Retrieve a Google AI Overview through Frevana, using `google-search` to obtain the search result and any required continuation token.

## Purpose

This skill calls Frevana's `/service/google-ai-overview` endpoint when Google Search requires a separate AI Overview request, and returns the SerpAPI response unchanged. It is not a keyword-search endpoint or Google AI Mode.

The workflow accepts a search query, an existing Google Search response, or a fresh `ai_overview.page_token`. The endpoint script itself requires `page_token`; it does not accept `q` or run Google Search automatically.

Supported request fields:

- `page_token` (required)
- `no_cache`
- `async`
- `zero_trace`

The script validates that the response is JSON and prints it to stdout. Do not rewrite or reshape returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- a query, an existing Google Search response, or a fresh `ai_overview.page_token`
- the installed `google-search` skill when a search is needed; the `google-ai-overview-bundle` catalog entry installs both skills
- `FREVANA_TOKEN` in the environment variables, or `--token` for the current run
- `curl`, `bash`, and `python3`

The API base URL defaults to `https://ai-factory.frevana.com`. Set `FREVANA_API_BASE_URL` to point at another host.

## Execution Order

1. If the user supplies a fresh `ai_overview.page_token`, use it directly without another search. It is a continuation token, not the Frevana Bearer token or a pagination token.
2. Otherwise, reuse an applicable Google Search response already available, unless the user requests fresh results. If a search is needed, read the installed `google-search/SKILL.md`, apply the Search cache rules below, and run its `scripts/search_google.sh` once with the user's query and requested search options. If that skill is missing, install the bundle or dependency before continuing. Ask for a query only when neither a query nor a usable result/token is available.
3. Inspect the saved response's top-level `ai_overview` immediately:
   - If it already contains overview content such as non-empty `text_blocks`, use that content and its references without a second API call.
   - Otherwise, if it contains a non-empty string `page_token` that is not known to be expired, pass that exact value to `--page-token` immediately. Do not decode, truncate, or replace it with `serpapi_link` or an unrelated token. Do not submit a token already known to be expired.
   - If neither content nor a token is present, report that this search returned no retrievable AI Overview and stop. Report API errors as errors, not as evidence that no overview exists.
4. Summarize the overview and cite its returned source links by default. Preserve the original JSON and return it unchanged when requested.

SerpApi documents that `ai_overview.page_token` expires within **1 minute** of the original search. Do not defer the follow-up while summarizing regular results or doing unrelated work. An older saved response is still useful for embedded content, but its token may no longer work. If a token is expired or the request fails, report the failure; do not automatically repeat searches or follow-up requests. A user-requested refresh must follow the Search cache rules below and may incur another charge.

The workflow uses one Search request, plus one Overview request only when a token is returned without embedded content. A bundle installs these capabilities together; it does not combine their billing or guarantee that Google returns an overview. Do not call this endpoint during an ordinary Google Search task unless the user also requests AI Overview retrieval.

## Search Cache and Token Freshness

- A new Search request does not necessarily return a new token. SerpApi can serve an identical query and parameters from a cache for up to **1 hour**, including an already-expired `ai_overview.page_token`. Receiving or saving the response now does not restart that token's lifetime.
- For every new Search in this Overview workflow, pass **`--no-cache true` to `search_google.sh`**, which sends **`no_cache: true` on the Google Search request**. Then use embedded Overview content directly, or immediately follow a returned token. Keep the user's query and requested search options unchanged. A supplied fresh token or applicable embedded content needs no extra Search request.
- **Deployment requirement:** use the updated Search helper with a Frevana Server version that validates and forwards `GoogleSearchDto.no_cache`. Deploy Server support first, then publish the updated skills and the bundle. Older servers may silently strip this field, so HTTP success alone does not prove cache bypass. If the installed helper or target server is known not to support it, stop and explain the required update; do not silently drop the flag or claim a cached search is fresh.
- If a token is known to be expired or the follow-up reports expiry, stop instead of automatically repeating Search or Overview requests. A user-requested refresh uses a new Search with `--no-cache true` and immediately follows any returned token.
- `--no-cache true` on **`get_google_ai_overview.sh`** controls only the follow-up Overview response cache. It does not refresh the original Google Search or renew its page token. Do not use it as a substitute for Search-stage cache control.

Provider references: [AI Overview results and embedded content](https://serpapi.com/ai-overview), [AI Overview endpoint and token lifetime](https://serpapi.com/google-ai-overview-api), [Search cache behavior](https://serpapi.com/search-api), [expired tokens in cached Search responses](https://serpapi.com/blog/fetching-ai-overviews-with-node-js/).

## Commands

### Search first when only a query is available

Read the installed Google Search skill and confirm the deployment requirement above, then bypass the Search cache:

```bash
bash <google-search-skill-path>/scripts/search_google.sh \
  --q "USER_QUERY" \
  --no-cache true \
  --output "./out/google-search-result.json"
```

Inspect that saved JSON using the branches above. Do not ask the user to find a token that the Search skill can return, and do not invent one when the search has none.

### Get AI Overview using the returned token

```bash
bash <skill-path>/scripts/get_google_ai_overview.sh \
  --page-token "PAGE_TOKEN"
```

### Save JSON to a file

```bash
bash <skill-path>/scripts/get_google_ai_overview.sh \
  --page-token "PAGE_TOKEN" \
  --output "./out/google-ai-overview.json"
```

## Fixed Request Shape

The script sends this payload shape, omitting optional fields that were not provided:

```json
{
  "page_token": "PAGE_TOKEN",
  "no_cache": true,
  "async": true,
  "zero_trace": true
}
```

Do not pass unsupported fields. Do not pass SerpAPI `engine` or `api_key`; Frevana sets those server-side. Use `--output` for local file saving.

## Output

- Success: validated JSON on stdout
- With `--output`: the same JSON is also written to the requested file
- Failure: response body or parsing error on stderr, with a non-zero exit code

## Example Prompts

- "Get Google AI Overview for page token."
- "Get the Google AI Overview for how heat pumps work."
- "Use this saved Google Search response to retrieve its AI Overview."
- "Run Google AI Overview and save the raw JSON."
