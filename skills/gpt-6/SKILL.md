---
name: gpt-6
description: Use when the user wants next-generation frontier intelligence, state-of-the-art reasoning, groundbreaking multimodal synthesis, or advanced cognitive workflows using OpenAI GPT-6 (gpt-6) through the Frevana Responses API.
---

# GPT-6

Generate responses through Frevana's OpenAI Responses API (`POST /openai/v1/responses`) using `gpt-6`.

Return the validated API response JSON unchanged, or use `--text-only` when the user requests only the final text output.

## Model Characteristics

- Model ID: `gpt-6` (OpenAI GPT-6 next-generation frontier model).
- Best suited for state-of-the-art multimodal understanding, breakthrough scientific reasoning, complex codebase refactoring, autonomous problem solving, and highest-tier creative synthesis.
- For high-speed/cost-sensitive tasks, consider `gpt-5.6-luna`. For standard frontier reasoning, consider `gpt-5.6-sol` or `gpt-5.6-terra`.

## What This Skill Needs

- `input` or `prompt` via `--input` or `--input-file` (or raw JSON payload via `--raw-payload-file`)
- optional developer system instructions via `--instructions` or `--instructions-file`
- optional reasoning effort: `--reasoning-effort <low|medium|high>`
- optional sampling: `--temperature`, `--top-p`, `--max-output-tokens`
- optional multi-turn conversation continuation: `--previous-response-id`
- optional tools: `--tools` or `--tools-file`, `--tool-choice`
- optional service tier: `--service-tier <auto|default|flex|priority|ultrafast>`
- authentication: `FREVANA_TOKEN` (or `--token`) / `FREVANA_API_KEY` (or `--api-key`)
- optional attribution: `FREVANA_AGENT_APP_INSTANCE_ID` (or `X_FREVANA_AGENT_APP_INSTANCE_ID`, or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Allowed Options

- `--model`: `gpt-6` (default)
- `--input`, `--prompt`: user prompt string or JSON message array
- `--input-file`: file path containing input prompt or JSON message array
- `--instructions`: system developer instructions
- `--instructions-file`: file path containing system instructions
- `--reasoning-effort`: `low`, `medium`, `high`
- `--temperature`: `0.0 - 2.0`
- `--top-p`: `0.0 - 1.0`
- `--max-output-tokens`: positive integer
- `--session-file`: path to session file to automatically save and restore conversation context across calls
- `--previous-response-id`: ID of a previous response for multi-turn conversations
- `--chat`: start an interactive chat session in the terminal
- `--service-tier`: `auto`, `default`, `flex`, `priority`, `ultrafast`
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
# Frontier reasoning with GPT-6
bash <skill-path>/scripts/create_response.sh \
  --input "Formulate a formal proof for safety invariants in an asynchronous Paxos consensus implementation" \
  --instructions "Provide rigorous mathematical definitions and complete inductive verification steps." \
  --reasoning-effort high \
  --output ./out/gpt6-response.json

# Multi-turn conversation with automatic session persistence
bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/gpt6_session.json \
  --input "Analyze the security vulnerabilities in this smart contract architecture" \
  --text-only

bash <skill-path>/scripts/create_response.sh \
  --session-file ./out/gpt6_session.json \
  --input "Provide a formal patch for the reentrancy issue identified above" \
  --text-only

# Interactive terminal chat
bash <skill-path>/scripts/create_response.sh --chat
```
