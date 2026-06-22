---
name: reddit-url-mentions
description: Use when the user provides URLs and wants to check for Reddit mentions, social media mentions on Reddit, or Reddit discussions about specific web pages.
---

# Reddit URL Mentions

Check which Reddit posts mention specific URLs through Frevana.

## Purpose

This skill is for **looking up Reddit mentions of one or more URLs**.

Inputs:

- `targets` (required) — array of absolute URLs (max 10)
- `tag` (optional) — user-defined task identifier returned by Frevana (max 255 chars)

Output:

- validated response JSON with Reddit mention results per URL

This skill validates that the response is JSON and returns it unchanged. Do **not** rewrite or reshape the returned data unless the user explicitly asks for a transformation.

## What This Skill Needs

- user-provided `targets` (array of URLs, max 10)
- optional `tag`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided at least one target URL.
2. Validate targets — max 10 URLs, each must be an absolute URL (include `http://` or `https://`).
3. Prefer the script over ad hoc `curl` commands.
4. Let the script read `FREVANA_TOKEN` first.
5. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
6. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
7. Return the validated response JSON, or summarize the fields the user actually cares about if they do not need the full payload.
8. When useful, also save the JSON to a file.

## Commands

### Basic lookup by target URLs

```bash
bash <skill-path>/scripts/search_reddit_mentions.sh \
  --targets "https://example.com,https://example.org"
```

### With tag

```bash
bash <skill-path>/scripts/search_reddit_mentions.sh \
  --targets "https://example.com" \
  --tag "my-campaign-001"
```

### Save output to file

```bash
bash <skill-path>/scripts/search_reddit_mentions.sh \
  --targets "https://example.com,https://example.org" \
  --tag "my-campaign-001" \
  --output ./out/reddit-mentions-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_reddit_mentions.sh \
  --targets "https://example.com" \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape:

```json
{
  "targets": ["https://example.com", "https://example.org"],
  "tag": "my-campaign-001"
}
```

## Response Shape

The API returns JSON with this top-level structure:

```json
{
  "version": "0.1.20210713",
  "status_code": 20000,
  "status_message": "Ok.",
  "time": "0.9068 sec.",
  "cost": 0.00024,
  "tasks_count": 1,
  "tasks_error": 0,
  "tasks": [
    {
      "id": "uuid",
      "status_code": 20000,
      "status_message": "Ok.",
      "time": "0.8277 sec.",
      "cost": 0.00024,
      "result_count": 6,
      "data": { "...": "..." },
      "result": [
        {
          "type": "social_media_reddit_item",
          "page_url": "https://example.com",
          "reddit_reviews": [
            {
              "subreddit": "subreddit_name",
              "author_name": "author_nickname",
              "title": "Post title",
              "permalink": "/r/subreddit/comments/...",
              "subreddit_members": 2350423
            }
          ]
        }
      ]
    }
  ]
}
```

When a URL has no Reddit mentions, `reddit_reviews` is `null`.

This skill validates the response as JSON and returns it unchanged.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- With `--output`: the same JSON is also written to the specified file path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require at least one target URL via `--targets`
- Targets must be comma-separated in a single string argument (e.g. `--targets "https://a.com,https://b.com"`)
- Each URL must be an absolute URL including `http://` or `https://`
- Max 10 targets per request
- If `curl` is missing, stop and tell the user to install `curl`
- If `python3` is missing, stop and tell the user to install `python3`
- Do not echo the Bearer token back to the user
- If `reddit_reviews` is `null`, the URL has no mentions on Reddit
- Summarize the key findings instead of dumping raw JSON unless the user asks for the full payload

## Example Prompts

### 中文

- "查一下 https://example.com 在 Reddit 上有没有被提到"
- "检查这几个 URL 在 Reddit 上的提及情况：https://url1.com, https://url2.com"
- "调用 Reddit URL mentions API 并把原始 JSON 保存到文件"

### English

- "Check if https://example.com is mentioned on Reddit"
- "Search for Reddit mentions of these URLs: https://url1.com, https://url2.com"
- "Query the Reddit URL mentions API and save the raw JSON to a file"
