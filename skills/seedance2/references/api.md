# Seedance 2.0 Ark API contract

Sources:

- https://www.volcengine.com/docs/82379/1520757
- https://www.volcengine.com/docs/82379/1521309
- https://www.volcengine.com/docs/82379/2291680

## Endpoints

- Base URL: `https://ark.cn-beijing.volces.com/api/v3`
- Create: `POST /contents/generations/tasks`
- Query: `GET /contents/generations/tasks/{id}`
- Authentication: `Authorization: Bearer <ARK_API_KEY>`
- JSON writes: `Content-Type: application/json`

## Create body

```json
{
  "model": "doubao-seedance-2-0-260128",
  "content": [
    {
      "type": "text",
      "text": "A cinematic scene"
    },
    {
      "type": "image_url",
      "image_url": {
        "url": "https://example.com/reference.jpg"
      },
      "role": "reference_image"
    }
  ],
  "generate_audio": true,
  "ratio": "16:9",
  "duration": 5,
  "resolution": "720p",
  "watermark": false,
  "seed": -1
}
```

The skill sends `model`, `content`, and output parameters at the top level. It intentionally does not expose webhooks; task results are retrieved by polling every 10 seconds. The first `content` item must be a non-empty text prompt.

Supported short model aliases are mapped to official Ark model IDs:

| Alias | Ark model ID |
| --- | --- |
| `seedance-2-0` | `doubao-seedance-2-0-260128` |
| `seedance-2-0-fast` | `doubao-seedance-2-0-fast-260128` |
| `seedance-2-0-mini` | `doubao-seedance-2-0-mini-260615` |

Allowed aspect ratios: `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`, `adaptive`.

Allowed resolutions: `480p`, `720p`, `1080p`, `4k`.

## Generation modes

| Mode | Ark content rules |
| --- | --- |
| `text-to-video` | Prompt only. |
| `image-to-video` | Exactly 1 or 2 image URLs. The first image is sent with `role: "first_frame"` and the second with `role: "last_frame"`. |
| `reference-to-video` | At least one image or video. Images use `role: "reference_image"`, videos use `role: "reference_video"`, and audio uses `role: "reference_audio"`. Maximum 9 images, 3 videos, 3 audio files, and 12 assets total. Audio cannot be used without an image or video. |

## Create response

HTTP success means the task was accepted:

```json
{
  "id": "cgt-2026****-****"
}
```

## Task response

Statuses are:

- `queued`
- `running`
- `cancelled`
- `succeeded`
- `failed`
- `expired`

On success, `content.video_url` contains the generated MP4 URL. `content.last_frame_url` can be present when `return_last_frame` was requested. Output URLs are valid for 24 hours.

Typical successful response shape:

```json
{
  "id": "cgt-2026****-****",
  "model": "doubao-seedance-2-0-260128",
  "status": "succeeded",
  "error": null,
  "content": {
    "video_url": "https://ark-content-generation-cn-beijing.tos-cn-beijing.volces.com/xxx"
  },
  "usage": {
    "completion_tokens": 108900,
    "total_tokens": 108900
  },
  "created_at": 1779348818,
  "updated_at": 1779348874,
  "resolution": "720p",
  "ratio": "16:9",
  "duration": 5,
  "framespersecond": 24,
  "generate_audio": true
}
```

On failure, `error.code` and `error.message` provide the terminal failure reason.

## Errors

Errors may be returned directly from the create/query call, or inside a terminal task response.

| HTTP/status | Retry guidance |
| --- | --- |
| `400` | Fix the request. |
| `401` | Use a valid `ARK_API_KEY`. |
| `403` | Fix model access or key permissions. |
| `404` | Check task ownership and ID. |
| `429` | Respect `Retry-After`. |
| `5xx` | Retry status checks later; never auto-resubmit a create request. |

Preserve the raw Ark JSON for debugging and summarize the task ID, terminal status, `content.video_url`, and token usage for normal user-facing output.
