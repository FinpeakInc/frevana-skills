---
name: google-related-questions
description: Use when the user wants Google Related Questions, People Also Ask follow-up questions, or more related question results from a Google Search related_questions next_page_token through Frevana. Use this whenever the task mentions Google Related Questions, PAA expansion, People Also Ask expansion, next_page_token from related_questions, or the Frevana endpoint.
---

# Google Related Questions

Retrieve additional Google "People also ask" / Related Questions results through Frevana.

## Purpose

This skill is for **expanding Google related questions using a `next_page_token`**.

Inputs:

- `next_page_token`

Output:

- validated response JSON with Google Related Questions results

This endpoint follows the Frevana Google Related Questions API. It is not a keyword search endpoint: the required token must come from a `related_questions` item in a regular Google Search API response. If the user only provides a keyword, search phrase, or question, recommend running the regular Google Search skill first to fetch `related_questions[].next_page_token`, then continue this skill with that token.

## What This Skill Needs

- user-provided `next_page_token`
- `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override for the current run
- `curl`
- `bash`
- `python3`

## Execution Order

Use this flow so the request stays simple and reliable:

1. Confirm the user has provided a `next_page_token`.
2. If the user gives only a keyword, search phrase, or question text, do not guess or call this endpoint. Tell the user this skill needs `next_page_token`, recommend running the regular Google Search skill for the keyword first, then use a `related_questions[].next_page_token` from that response to continue.
3. Prefer the script over ad hoc `curl` commands.
4. Let the script read `FREVANA_TOKEN` first.
5. In interactive shell usage, if `FREVANA_TOKEN` is missing, the script may prompt for it.
6. In non-interactive or agent workflows, fail fast if the token is missing and tell the user to set `FREVANA_TOKEN` or pass `--token` explicitly.
7. Return the validated response JSON, or summarize the related questions if the user does not need the full payload.
8. When useful, also save the JSON to a file.

## Commands

### Basic related questions expansion

```bash
bash <skill-path>/scripts/search_google_related_questions.sh \
  --next-page-token "eyJvbnMiOiIxMDA0MSI..."
```

`--next_page_token` is accepted as an alias for `--next-page-token`.

### Save response JSON to a file

```bash
bash <skill-path>/scripts/search_google_related_questions.sh \
  --next-page-token "eyJvbnMiOiIxMDA0MSI..." \
  --output ./out/google-related-questions-result.json
```

### Token override for the current run

```bash
bash <skill-path>/scripts/search_google_related_questions.sh \
  --next-page-token "eyJvbnMiOiIxMDA0MSI..." \
  --token "your bearer token"
```

## Fixed Request Shape

The script sends this payload shape:

```json
{
  "next_page_token": "eyJvbnMiOiIxMDA0MSI..."
}
```

Only `next_page_token` is supported by the Frevana endpoint. Do not add unsupported passthrough fields such as `engine`, `api_key`, `output`, `no_cache`, `async`, or `zero_trace`.

## Response Shape

The API returns Frevana JSON. Common fields include:

- `search_metadata`
- `search_parameters`
- `related_questions`

Each `related_questions` item can include fields such as `question`, `type`, `snippet`, `title`, `link`, `displayed_link`, `source_logo`, `next_page_token`.

## Output

- Success: the script validates that the response body is JSON and prints it to stdout
- With `--output`: the same JSON is also written to the specified file path
- Failure: the script prints the response body or parsing error and exits non-zero

## Notes

- Require `--next-page-token` or `--next_page_token`.
- If the user supplies only a search query or a question, recommend running the regular Google Search skill first to get `related_questions[].next_page_token`, then continue with this skill.
- The token is an input cursor for expanding a specific related question, not a general search term.
- If `curl` is missing, stop and tell the user to install `curl`.
- If `python3` is missing, stop and tell the user to install `python3`.
- Do not echo the Bearer token back to the user.
- Summarize the related questions the user actually cares about instead of dumping raw JSON unless they ask for the full payload.

## Example Prompts

### 中文

- "用这个 next_page_token 查询 Google Related Questions，并总结问题列表"
- "展开这个 People Also Ask 的 next_page_token，保存原始 JSON"
- "查一下 Frevana google-related-questions endpoint，token 是 eyJvbnMiOiIxMDA0MSI..."

### English

- "Use this next_page_token to fetch more Google Related Questions."
- "Expand this People Also Ask result and save the raw JSON."
- "Query Google Related Questions through Frevana with this token."
- "Search Google Related Questions for 'best coffee beans'." → Explain that a `next_page_token` is required and suggest using the regular Google Search skill first to obtain one.
