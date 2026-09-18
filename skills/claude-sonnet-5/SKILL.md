---
name: claude-sonnet-5
description: Use when the user wants enterprise-grade reasoning, fast and reliable coding, technical analysis, and balanced production intelligence using Anthropic Claude Sonnet 5 (anthropic/claude-sonnet-5) through the Frevana OpenRouter Responses API.
---

# Claude Sonnet 5

Generate responses through Frevana's OpenRouter Responses API (`POST /openrouter/v1/responses`) using `anthropic/claude-sonnet-5`.

Return the validated API response JSON unchanged, or use `--text-only` when the user requests only the final text output.

## Model Characteristics

- Model ID: `anthropic/claude-sonnet-5` (Anthropic Claude Sonnet 5 balanced model via OpenRouter).
- Best suited for production-grade coding, full-stack software development, structured data generation, complex technical workflows, and balanced reasoning at high speed.
- For deep theoretical research or highest-order reasoning, consider `anthropic/claude-opus-5` or `gpt-5.6-sol`. For high-throughput cost-optimized tasks, consider `deepseek/deepseek-v4.1-flash`.

## What This Skill Needs

- `input` or `prompt` via `--input` or `--input-file` (or raw JSON payload via `--raw-payload-file`)
- optional developer system instructions via `--instructions` or `--instructions-file`
- optional reasoning effort: `--reasoning-effort <low|medium|high>`
- optional sampling: `--temperature`, `--top-p`, `--max-output-tokens`
- optional multi-turn conversation continuation: `--previous-response-id`
- optional session persistence: `--session-file` or `--session`
- optional tools: `--tools` or `--tools-file`, `--tool-choice`
- optional service tier: `--service-tier <auto|default|flex|priority>`
- authentication: `FREVANA_TOKEN` (or `--token`) / `FREVANA_API_KEY` (or `--api-key`)
- optional attribution: `FREVANA_AGENT_APP_INSTANCE_ID` (or `X_FREVANA_AGENT_APP_INSTANCE_ID`, or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Allowed Options

- `--model`: `anthropic/claude-sonnet-5` (default; alias `claude-sonnet-5` accepted)
- `--input`, `--prompt`: user prompt string or JSON message array
- `--input-file`: file path containing input prompt or JSON message array
- `--instructions`: system developer instructions
- `--instructions-file`: file path containing system instructions
- `--reasoning-effort`: `low`, `medium`, `high`
- `--temperature`: `0.0 - 2.0`
- `--top-p`: `0.0 - 1.0`
- `--max-output-tokens`: positive integer
- `--session`: session name (e.g. default, chat1) saved under `~/.frevana/sessions`
- `--session-file`: path to session file to automatically save and restore conversation context across calls
- `--new-session`, `--new`: reset conversation context and start a fresh session
- `--no-session`: disable session persistence for this run
- `--previous-response-id`: ID of a previous response for multi-turn conversations
- `--chat`: start an interactive chat session in the terminal
- `--service-tier`: `auto`, `default`, `flex`, `priority`
- `--tools`: JSON array string defining available tools/functions
- `--tools-file`: path to JSON file defining tools
- `--tool-choice`: tool choice behavior (`auto`, `required`, `none`, or JSON)
- `--raw-payload-file`: path to raw JSON request body
- `--api-key`: Frevana API key (sent as `X-API-Key`)
- `--token`: Frevana Bearer token (sent as `Authorization: Bearer`)
- `--agent-app-instance-id`: Agent App instance/team ID (sent as `x-frevana-agent-app-instance-id`)
- `--text-only`, `-t`: output only the response text
- `--output`: save full response JSON to path

## Commands

```bash
# Complex coding and software engineering
bash <skill-path>/scripts/create_response.sh \
  --input "Implement a lock-free ring buffer queue in C++20 with atomic operations" \
  --instructions "Include comprehensive thread-safety explanations and benchmarks." \
  --reasoning-effort high \
  --output ./out/sonnet-code.json

# Tool-calling workflow
bash <skill-path>/scripts/create_response.sh \
  --input "Check deploy status for cluster 'prod-eu-west'" \
  --tools '[{"type":"function","name":"get_cluster_status","parameters":{"type":"object","properties":{"cluster_name":{"type":"string"}},"required":["cluster_name"]}}]' \
  --tool-choice auto \
  --text-only

# Multi-turn conversation with automatic session persistence (Recommended)
bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/sonnet_session.json \
  --input "We need to refactor our GraphQL API gateway to support federated schemas" \
  --text-only

bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/sonnet_session.json \
  --input "Write Apollo Router configuration YAML for the subgraphs" \
  --text-only

# Multi-turn conversation by previous response ID
bash <skill-path>/scripts/create_response.sh \
  --input "How do we write integration tests for this federated setup?" \
  --previous-response-id "resp_sonnet_456" \
  --text-only

# Interactive terminal chat
bash <skill-path>/scripts/create_response.sh --chat
```
