---
name: jev-latest
description: Use when the user wants structured classification, boolean judgment, or ordered scoring with TypeSafe JEV Latest through Frevana's OpenRouter Decisions API.
---

# JEV Latest

Evaluate a state with one or more structured questions through `POST /openrouter/v1/decisions`. The model is fixed to `~typesafe/jev-latest`.

Use `scripts/create_decision.sh`. Return the validated API response JSON unchanged unless the user asks for only the `answers` object, in which case use `--answers-only`.

## Required inputs

- State: `--state` for text or an inline JSON object/array, or `--state-file` for text or JSON content.
- Questions: `--questions` with a JSON object, or `--questions-file` with a JSON object.
- Authentication: `FREVANA_TOKEN` in the environment variables, or an explicit `--token` override.

For a complete request body, use `--raw-payload-file`. It cannot be combined with state, questions, provider, trace, session, or user flags. The script still fixes and validates the model.

Read [references/api.md](references/api.md) when using provider routing, trace metadata, raw payloads, or when exact request and response fields matter.

## Question types

Each property of `questions` is a named question:

- `choice`: requires `instructions` and a `criteria` object mapping choice names to guidance.
- `noul`: requires `instructions`; optional `criteria` must contain both `true` and `false` guidance. The answer's `noul` value is a continuous boolean-like score, so do not rewrite it as a strict boolean unless the user asks for a threshold.
- `score`: requires `instructions` and an ordered `criteria` array.

Instructions, criteria entries, and state may be structured JSON where the API contract permits it. Keep question names stable because response answers use the same keys.

## Optional inputs

- `--token`: Frevana Bearer token override for this run.
- `--session-id`: observability grouping identifier, at most 256 characters.
- `--user`: end-user identifier, at most 256 characters.
- `--provider` or `--provider-file`: OpenRouter provider preferences JSON object.
- `--trace` or `--trace-file`: trace metadata JSON object.
- `--agent-app-instance-id`: Frevana Agent App attribution header.
- `--output`: save the full response JSON while still printing the selected output form.

Do not invent optional provider routing, trace metadata, session IDs, or user IDs. Do not automatically retry a request: a timed-out request may still have completed and incurred cost.

The Frevana server uses the OpenRouter SDK's camelCase input shape. For convenience, the script also accepts the official OpenRouter wire-format snake_case names in provider, trace, and raw-payload JSON and normalizes them before sending the request.

## Examples

```bash
# Boolean-like judgment
bash <skill-path>/scripts/create_decision.sh \
  --state '{"ticket":"Please refund this duplicate charge"}' \
  --questions '{"escalate":{"type":"noul","instructions":"Should this ticket be escalated?","criteria":{"true":"Needs human intervention","false":"Can be handled automatically"}}}'

# Choice and ordered score questions from files
bash <skill-path>/scripts/create_decision.sh \
  --state-file ./ticket.json \
  --questions-file ./questions.json \
  --session-id "ticket-workflow-42" \
  --output ./out/jev-decision.json

# Print only the keyed answers
bash <skill-path>/scripts/create_decision.sh \
  --raw-payload-file ./decision-request.json \
  --answers-only
```
