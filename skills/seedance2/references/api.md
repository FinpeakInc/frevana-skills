# Seedance 2.0 API contract

Source: https://seedance2.ai/zh/api-docs

## Endpoints

- Base URL: `https://api.seedance2.ai`
- Create: `POST /v1/videos/generations`
- Query: `GET /v1/tasks/:id`
- Authentication: `Authorization: Bearer <API key>`
- JSON writes: `Content-Type: application/json`

## Create body

```json
{
  "model": "seedance-2-0",
  "input": {
    "prompt": "A cinematic scene",
    "generation_type": "text-to-video",
    "image_urls": [],
    "video_urls": [],
    "audio_urls": [],
    "duration": 5,
    "aspect_ratio": "adaptive",
    "resolution": "720p",
    "generate_audio": true,
    "watermark": false,
    "web_search": false,
    "return_last_frame": false,
    "seed": -1
  }
}
```

The skill sends the required top-level fields `model` and `input`. It intentionally does not expose `callback_url`; task results are retrieved by polling every 10 seconds. `input.prompt` is required and non-empty. Defaults documented by the API are:

- `generation_type`: `text-to-video`
- `image_urls`, `video_urls`, `audio_urls`: empty arrays
- `duration`: `5`
- `aspect_ratio`: `adaptive`
- `resolution`: `720p`
- `generate_audio`: `true`
- `watermark`, `web_search`, `return_last_frame`: `false`
- `seed`: `-1` for random

Allowed models: `seedance-2-0`, `seedance-2-0-fast`, `seedance-2-0-mini`.

Allowed aspect ratios: `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`, `adaptive`.

Allowed resolutions: `480p`, `720p`, `1080p`, `4k`.

## Generation modes

| Mode | Media rules |
| --- | --- |
| `text-to-video` | Prompt only; omit all media arrays. |
| `image-to-video` | Exactly 1 or 2 image URLs. One sets the first frame; two set first and last frames. Video and audio references are not used. |
| `reference-to-video` | At least one image or video. Maximum 9 images, 3 videos, 3 audio files, and 12 assets total. Video total duration <=15 seconds and audio total duration <=15 seconds. Audio cannot be used without an image or video. |

## Create response

HTTP success means the task was accepted and credits were reserved:

```json
{"taskId":"3f2aK9mR...","credits":60}
```

## Task response

Statuses are `queued`, `generating`, `completed`, and `failed`. Billing states are `reserved`, `charged`, `refunded`, and `refund_failed`.

On completion, `data.results` contains video URLs. `data.video_expires_at` records their expiry. `data.last_frame_url` can be present when requested. A failed response reports `failed_reason`.

The skill polls once every 10 seconds, matching the API's minimum polling interval.

## Errors

Errors have an `error` object with `code` and `message`, and may include fields such as `required`, `available`, or `retry_after`.

| Code | HTTP | Retry guidance |
| --- | ---: | --- |
| `invalid_request` | 400 | Fix the request. |
| `invalid_api_key` | 401 | Use a valid key. |
| `insufficient_credits` | 402 | Add credits, then retry only with user approval. |
| `forbidden` | 403 | Fix key permissions. |
| `not_found` | 404 | Check task ownership and ID. |
| `rate_limited` | 429 | Respect `Retry-After`. |
| `internal_error` | 500 | Retry later; never auto-resubmit a create request. |

The documented default generation rate is 60 requests per minute per API key.
