---
name: perplexity-ask
description: Use when the user wants to ask Perplexity a question through Frevana using the user's logged-in Chrome session.
---

# Perplexity Ask

Ask Perplexity through the local Frevana daemon and Chrome session.

## Purpose

This skill is for **asking Perplexity a prompt** using the Chrome-backed Frevana MCP tool `frevana_ask` with fixed provider `perplexity`.

Inputs:

- `prompt` (required) - one or more questions or instructions to send to Perplexity
- `prompt_file` (optional) - UTF-8 text file with one prompt per non-empty line
- `format` (optional) - `text` or `json`, defaults to `text`
- `timeout` (optional) - Frevana tool timeout in milliseconds, default comes from the tool

Output:

- Perplexity's answer returned by Frevana

Return the answer directly unless the user asks for raw output or a saved file.

## What This Skill Needs

- user-provided `prompt`
- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through Frevana
- the user logged in to Perplexity in Chrome
- `curl`
- `bash`
- `python3`

This skill uses the local daemon and Chrome session. It does not use `FREVANA_TOKEN`.

## Execution Order

1. Confirm the user provided one or more prompts, or a prompt file with one prompt per non-empty line.
2. Prefer the script over ad hoc `frevana call` commands.
3. Do not invent optional timeout values. Default output format to `text` unless the user asks for JSON.
4. Let the script run bundled `scripts/setup.sh` before every Frevana tool call.
5. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
6. Run the Perplexity ask only after setup succeeds.
7. If the call returns login/auth content or fails because Perplexity is unavailable, tell the user they must be logged in to Perplexity in Chrome.
8. Return text output by default. If `format` is `json`, return structured JSON with `provider`, `count`, and `results`.
9. Save output with `--output` when useful.

## Commands

```bash
bash <skill-path>/scripts/ask_perplexity.sh \
  --prompt "Explain quantum computing in simple terms"
```

```bash
bash <skill-path>/scripts/ask_perplexity.sh \
  --prompt "Summarize this topic" \
  --timeout 120000 \
  --output ./out/perplexity-answer.txt
```

```bash
bash <skill-path>/scripts/ask_perplexity.sh \
  --prompt "Question 1" \
  --prompt "Question 2"
```

```bash
bash <skill-path>/scripts/ask_perplexity.sh \
  --prompt-file ./prompts.txt \
  --format json \
  --output ./out/perplexity-batch-answers.txt
```

## Fixed Tool Call Shape

The script calls:

```bash
frevana call frevana_ask '<json_args>'
```

The JSON arguments use this shape:

```json
{
  "provider": "perplexity",
  "prompt": "Explain quantum computing in simple terms",
  "timeout": 120000
}
```

Always send `provider: "perplexity"`. Do not pass unsupported fields.

## Notes

- Require at least one `--prompt`, `--question`, or `--prompt-file`.
- `--prompt` and `--question` may be repeated.
- `--prompt-file` reads one prompt per non-empty line.
- `--format` must be `text` or `json`; default is `text`.
- `--timeout` must be a positive integer when provided.
- `scripts/setup.sh` downloads and executes the latest official setup script from `https://raw.githubusercontent.com/FinpeakInc/frevana-cli-releases/refs/heads/main/skills/frevana/scripts/setup.sh`.
- Do not ask for or echo bearer tokens; this workflow is local-daemon based.

## Example Prompts

- "Ask Perplexity to explain quantum computing"
- "用 Perplexity 回答这个问题：..."
