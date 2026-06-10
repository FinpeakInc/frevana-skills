---
name: chatgpt-ask
description: Use when the user wants to ask ChatGPT a question through Frevana using the user's logged-in Chrome Extension session.
---

# ChatGPT Ask

Ask ChatGPT through the local Frevana daemon and Chrome Extension session.

## Purpose

This skill is for **asking ChatGPT a prompt** using the Chrome Extension-backed Frevana MCP tool `frevana_ask` with fixed provider `chatgpt`.

Inputs:

- `prompt` (required) - one or more questions or instructions to send to ChatGPT
- `prompt_file` (optional) - UTF-8 text file with one prompt per non-empty line
- `format` (optional) - `text` or `json`, defaults to `text`
- `timeout` (optional) - Frevana tool timeout in milliseconds, default comes from the tool

Output:

- ChatGPT's answer returned by Frevana

Return the answer directly unless the user asks for raw output or a saved file.

## What This Skill Needs

- user-provided `prompt`
- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through the Frevana Chrome Extension
- the user logged in to ChatGPT in Chrome
- `curl`
- `bash`
- `python3`

This is a Chrome Extension skill. It uses the local daemon and Chrome Extension session.

## Execution Order

1. Confirm the user provided one or more prompts, or a prompt file with one prompt per non-empty line.
2. Prefer the script over ad hoc `frevana call` commands.
3. Do not invent optional timeout values. Default output format to `text` unless the user asks for JSON.
4. Let the script run bundled `scripts/setup.sh` before every Frevana tool call.
5. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
6. Run the ChatGPT ask only after setup succeeds.
7. If the call returns login/auth content or fails because ChatGPT is unavailable, tell the user they must be logged in to ChatGPT in Chrome.
8. Return text output by default. If `format` is `json`, return structured JSON with `provider`, `count`, and `results`.
9. Save output with `--output` when useful.

## Commands

```bash
bash <skill-path>/scripts/ask_chatgpt.sh \
  --prompt "Explain quantum computing in simple terms"
```

```bash
bash <skill-path>/scripts/ask_chatgpt.sh \
  --prompt "Summarize this topic" \
  --timeout 120000 \
  --output ./out/chatgpt-answer.txt
```

```bash
bash <skill-path>/scripts/ask_chatgpt.sh \
  --prompt "Question 1" \
  --prompt "Question 2"
```

```bash
bash <skill-path>/scripts/ask_chatgpt.sh \
  --prompt-file ./prompts.txt \
  --format json \
  --output ./out/chatgpt-batch-answers.txt
```

## Fixed Tool Call Shape

The script calls:

```bash
frevana call frevana_ask '<json_args>'
```

The JSON arguments use this shape:

```json
{
  "provider": "chatgpt",
  "prompt": "Explain quantum computing in simple terms",
  "timeout": 120000
}
```

Always send `provider: "chatgpt"`. Do not pass unsupported fields.

## Notes

- Require at least one `--prompt`, `--question`, or `--prompt-file`.
- `--prompt` and `--question` may be repeated.
- `--prompt-file` reads one prompt per non-empty line.
- `--format` must be `text` or `json`; default is `text`.
- `--timeout` must be a positive integer when provided.
- `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.

## Example Prompts

- "Ask ChatGPT to explain quantum computing"
- "用 ChatGPT 回答这个问题：..."
