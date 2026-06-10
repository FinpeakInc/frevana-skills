---
name: x-topic-search
description: Use when the user wants to search X/Twitter posts by topic, query, hashtag, keyword, or trend through the local Frevana Chrome Extension-backed X search tool.
---

# X Topic Search

Search X/Twitter posts by topic through the local Frevana daemon.

## Purpose

This skill is for **finding X/Twitter posts for a topic or query** using the Chrome Extension-backed Frevana MCP tool `frevana_x_search_topic`.

Inputs:

- `topic` (required) - topic, keyword, hashtag, or query to search on X
- `sort` (optional) - `top` or `live`, defaults to Frevana's tool default
- `count` (optional) - number of posts to fetch, max 100
- `fetchMode` (optional) - `quick` or `full`, defaults to `quick`
- `cursor` (optional) - cursor from a previous result set
- `includeReplies` (optional) - include replies when available
- `includeQuotes` (optional) - include quotes when available
- `includeMedia` (optional) - include media metadata when available
- `maxScrollRounds` (optional) - maximum scroll rounds during collection
- `minCount` (optional) - minimum number of posts to collect before stopping
- `timeout` (optional) - timeout in milliseconds

Output:

- raw Frevana tool result text from `frevana_x_search_topic`

Summarize the results unless the user asks for the raw output.

## What This Skill Needs

- user-provided `topic`
- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through the Frevana Chrome Extension
- the user logged in to X/Twitter in Chrome
- `curl`
- `bash`
- `python3`

This is a Chrome Extension skill. It uses the local daemon and Chrome Extension session.

## Execution Order

Use this flow:

1. Confirm the user has provided `topic` or an equivalent X/Twitter search query.
2. Prefer the script over ad hoc `frevana call` commands.
3. Default `fetchMode` to `quick` when the user does not specify it. Do not invent other optional sort, count, cursor, reply, quote, media, scroll, minimum-count, or timeout fields.
4. Let the script run bundled `scripts/setup.sh` before every Frevana tool call.
5. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
6. Run the X topic search with the provided options only after setup succeeds.
7. If the result looks like login/auth content or the call fails because X is unavailable, tell the user they must be logged in to X/Twitter in Chrome.
8. Return a concise summary of the posts, or the raw output if requested.
9. When useful, save the output to a file.

## Commands

### Basic topic search

```bash
bash <skill-path>/scripts/search_x_topics.sh \
  --topic "vibe coding"
```

`--query` and `--q` are accepted as aliases for `--topic`.

### Live search with a smaller result count

```bash
bash <skill-path>/scripts/search_x_topics.sh \
  --topic "vibe coding" \
  --sort live \
  --count 10 \
  --fetch-mode quick \
  --timeout 60000
```

### Include optional metadata

```bash
bash <skill-path>/scripts/search_x_topics.sh \
  --topic "#buildinpublic" \
  --include-replies \
  --include-quotes \
  --include-media
```

### Continue from a cursor

```bash
bash <skill-path>/scripts/search_x_topics.sh \
  --topic "vibe coding" \
  --cursor "cursor-from-previous-result"
```

### Save output to file

```bash
bash <skill-path>/scripts/search_x_topics.sh \
  --topic "vibe coding" \
  --output ./out/x-topic-search-result.txt
```

## Fixed Tool Call Shape

The script calls:

```bash
frevana call frevana_x_search_topic '<json_args>'
```

The JSON arguments use this shape, omitting optional fields that were not provided:

```json
{
  "topic": "vibe coding",
  "sort": "live",
  "count": 10,
  "fetchMode": "quick",
  "cursor": "cursor-from-previous-result",
  "includeReplies": true,
  "includeQuotes": true,
  "includeMedia": true,
  "maxScrollRounds": 5,
  "minCount": 10,
  "timeout": 60000
}
```

Do not pass unsupported fields to `frevana_x_search_topic`.
Always send `fetchMode`; default it to `quick` when the user does not specify a value.

## Output

- Success: the script prints the Frevana tool result to stdout
- With `--output`: the same result is also written to the specified file path
- Failure: the script prints the Frevana error or preflight failure to stderr and exits non-zero

## Notes

- Require `--topic`, `--query`, or `--q`.
- Use `--sort live` only when the user asks for latest/recent/live X posts. Otherwise omit it or use `top` only if requested.
- `--count` must be an integer from 1 through 100.
- `--fetch-mode` must be `quick` or `full`; it defaults to `quick`.
- Boolean metadata options are sent only when the matching flag is present.
- Use a higher `--timeout` for busy topics or slow X sessions.
- If `curl` is missing, stop and tell the user to install `curl`.
- If `python3` is missing, stop and tell the user to install `python3`.
- The script runs bundled `scripts/setup.sh` before every search, matching the original Frevana skill flow.
- `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.
- If `frevana` is missing, the official setup script installs the Frevana binary before starting/checking the daemon.

## Example Prompts

### 中文

- "搜索 X 上关于 vibe coding 的帖子"
- "查一下 X 最近关于 AI agent 的 live 帖子，取 10 条"
- "继续用这个 cursor 搜 X 话题，并保存原始输出"

### English

- "Search X for posts about vibe coding"
- "Find recent live X posts about AI agents, count 10"
- "Continue this X topic search with the cursor and save the raw output"
