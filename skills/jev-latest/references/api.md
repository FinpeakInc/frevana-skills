# JEV Decisions API contract

This skill calls Frevana `POST /openrouter/v1/decisions`, whose server implementation uses `@openrouter/sdk` 1.3.19 and forwards the request to OpenRouter's alpha Decisions API.

## Top-level request

The Frevana endpoint accepts the SDK input shape:

| Field | Required | Shape |
| --- | --- | --- |
| `model` | yes | string; the skill fixes it to `~typesafe/jev-latest` |
| `state` | yes | string, JSON object, or JSON array |
| `questions` | yes | object keyed by stable question names |
| `provider` | no | provider preferences object or `null` |
| `sessionId` | no | string, maximum 256 characters |
| `trace` | no | trace metadata object |
| `user` | no | string, maximum 256 characters |

OpenRouter's public wire schema spells `sessionId` as `session_id`. The script accepts either spelling, rejects conflicting duplicates, and sends the SDK-compatible camelCase field to Frevana.

## Questions

- `choice`: `{ "type": "choice", "instructions": <guidance>, "criteria": { "option": <guidance-or-null> } }`
- `noul`: `{ "type": "noul", "instructions": <guidance>, "criteria"?: { "true": <guidance>, "false": <guidance> } }`
- `score`: `{ "type": "score", "instructions": <guidance>, "criteria": [<lowest>, ..., <highest>] }`; criteria must contain at least one item.

`instructions`, non-null choice criteria, noul criteria, and score criteria items may be a string, object, or array.

## Provider preferences

The server SDK uses these camelCase names. The script also accepts their listed snake_case wire aliases:

| SDK input | Wire alias | Shape |
| --- | --- | --- |
| `allowFallbacks` | `allow_fallbacks` | boolean or null |
| `dataCollection` | `data_collection` | `allow`, `deny`, or null |
| `enforceDistillableText` | `enforce_distillable_text` | boolean or null |
| `ignore` | same | provider slug array or null |
| `maxPrice` | `max_price` | object with string fields `audio`, `completion`, `image`, `prompt`, `request` |
| `only` | same | provider slug array or null |
| `order` | same | ordered provider slug array or null |
| `preferredMaxLatency` | `preferred_max_latency` | number, `{p50,p75,p90,p99}`, or null |
| `preferredMinThroughput` | `preferred_min_throughput` | number, `{p50,p75,p90,p99}`, or null |
| `quantizations` | same | array or null; current values include `int4`, `int8`, `fp4`, `mxfp4`, `nvfp4`, `fp6`, `fp8`, `mxfp8`, `fp16`, `bf16`, `fp32`, `unknown` |
| `requireParameters` | `require_parameters` | boolean or null |
| `sort` | same | `price`, `throughput`, `latency`, `exacto`, a `{by, partition}` object, or null |
| `zdr` | same | boolean or null |

For `sort.partition`, current values are `model` and `none`.

## Trace metadata

Known server SDK fields are `traceId`, `traceName`, `spanName`, `generationName`, and `parentSpanId`. The script also accepts the official wire names `trace_id`, `trace_name`, `span_name`, `generation_name`, and `parent_span_id`.

Additional trace keys are supported. The script moves wire-style custom keys into the SDK's `additionalProperties` object before sending them to Frevana. An already SDK-shaped `additionalProperties` object is also accepted.

## Parameters that do not belong to Decisions

The Decisions request schema does not accept chat/response generation controls such as `messages`, `input`, `temperature`, `top_p`, `max_tokens`, `reasoning`, `response_format`, `tools`, `tool_choice`, or `stream`. Do not add them based on ordinary chat-model parameter lists; this endpoint exposes typed decisions through `state` and `questions` instead.

## Response

Frevana returns the SDK-normalized response:

- `answers`: keyed by the original question names.
- choice answer: `type`, `choice`, optional `confidence`, optional `probabilities`.
- noul answer: `type`, `noul`.
- score answer: `type`, `score`, optional `confidence`, optional `probabilities`, optional `legend`.
- optional `id`, required `model`, optional `provider`.
- `usage`: `cost`, `inputTokens`, `outputTokens`. The server requires a valid non-negative provider `cost` before returning success.

Source references: the current [OpenRouter model page](https://openrouter.ai/~typesafe/jev-latest), [OpenRouter OpenAPI schema](https://openrouter.ai/openapi.json), and the Frevana server's installed OpenRouter SDK request types.
