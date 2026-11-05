---
name: heygen-video-1
description: Generate videos with native sound using HeyGen Video 1 (heygen/heygen-video-1) through Frevana's OpenRouter video endpoint, from text, a first-frame image, or image/video/audio references. Also check, wait for, and download existing video jobs. Use for scene generation, not HeyGen avatar or lip-sync APIs.
---

# HeyGen Video 1

Use `scripts/generate_video.sh` for `heygen/heygen-video-1`. It follows the existing Frevana video skills' create/status/wait workflow. Read [references/api.md](references/api.md) for the OpenRouter request contract and model metadata, Frevana field mapping, and separately identified upstream safeguards.

## Authentication

- Requires `bash`, `curl`, and `python3`.
- Use runtime `FREVANA_TOKEN` with a Frevana JWT, or override with `--token`. The current Server video route uses `JwtAuthGuard`; ordinary Frevana API keys are not supported. The helper ignores `FREVANA_API_KEY` and rejects `--api-key` before HTTP.
- Optional `FREVANA_AGENT_APP_INSTANCE_ID` / `--agent-app-instance-id` sets the corresponding Frevana header.
- Default origin: `https://ai-factory.frevana.com`; override with `FREVANA_API_BASE_URL` or `--api-base-url` for an explicitly chosen environment.
- No direct HeyGen or OpenRouter key is needed. `--dry-run` needs no credentials and makes no HTTP requests.

## Workflow

For creation, obtain a non-empty prompt or prompt file. Use a first frame to animate that image; use references to guide a new scene. OpenRouter accepts both fields together, but gives `frame_images` precedence and selects image-to-video. The helper preserves both fields and prints a note; do not promise that references control this mode. For reference mode without a first frame, the upstream safeguard requires an image or video alongside audio.

```bash
# Inspect a request locally without submitting it
bash skills/heygen-video-1/scripts/generate_video.sh \
  --prompt 'A ceramic mug rotates slowly on a wooden table, with quiet room ambience.' \
  --duration 10 --resolution 768p --aspect-ratio 16:9 --dry-run

# Submit once, retain the job ID and original response
bash skills/heygen-video-1/scripts/generate_video.sh \
  --prompt-file ./scene.txt --duration 20 --prompt-enhancement quality \
  --resolution 1080p --aspect-ratio 9:16 --no-wait --output ./job.json

# Animate a local image (encoded in the request; no separate upload)
bash skills/heygen-video-1/scripts/generate_video.sh \
  --prompt 'A breeze moves the curtains; the camera slowly pulls back.' \
  --first-frame ./room.png --duration 8 --download-dir ./output

# Reference labels are numbered independently by media type
bash skills/heygen-video-1/scripts/generate_video.sh \
  --prompt 'Show the mug from <Picture 1> with the camera movement from <Video 1>.' \
  --reference-image https://example.com/mug.png \
  --reference-video https://example.com/movement.mp4 \
  --duration 10 --seed 42 --download-dir ./output

# Resume with GET only, never a new creation request
bash skills/heygen-video-1/scripts/generate_video.sh status --job-id JOB_ID
bash skills/heygen-video-1/scripts/generate_video.sh wait \
  --job-id JOB_ID --max-wait 1200 --download-dir ./output
```

The example media URLs are placeholders; use user-provided or authorized assets.

## Generation options

The OpenRouter catalog confirms duration/resolution/ratio enums, first-frame support, seed support, and the allowed passthrough key. Numeric reference/prompt/seed limits and mode-dependent combinations below are additional safeguards from HeyGen's native documentation, not constraints published in OpenRouter's normalized schema. The helper defaults (5 seconds, 768p, 16:9, quality enhancement) are explicit local choices.

| Option | Accepted values / behavior |
| --- | --- |
| `--prompt`, `-p` / `--prompt-file` | Prompt text or UTF-8 file; 1–32,000 characters |
| `--model` | Only `heygen/heygen-video-1` |
| `--duration` | OpenRouter: integer 5–30; helper default 5. Upstream safeguard: reference mode without a first frame, `disabled`, or `ultraquality` limits it to 15 |
| `--resolution` | `480p`, `768p` (default), `1080p`, `2K` |
| `--aspect-ratio` | `16:9` (default), `9:16`, `1:1`, `4:3`, `3:4`, `21:9` |
| `--size` | Explicit `WIDTHxHEIGHT`; replaces resolution and aspect ratio; provider validates compatibility |
| `--first-frame`, `--image` | Local image, image data URI, or public HTTPS URL; no last frame |
| `--reference-image` | Repeat for up to 9 images; local files, data URIs, or public HTTPS URLs |
| `--reference-video` / `--reference-audio` | Repeat for up to 3 of each; public HTTPS URLs |
| `--prompt-enhancement` | `turbo`, `quality` (helper default), `ultraquality`, `disabled` |
| `--seed` | Integer 0–4294967295; omitted for random generation |

The helper applies HeyGen's documented safeguard of `16:9` or `9:16` for text/reference generation at `1080p` or `2K`. First-frame generation follows the image shape upstream. Prefer resolution plus aspect ratio to exact pixels. Local image files are limited to 5 MiB each; the complete encoded JSON must also fit Frevana's 50 MiB body limit. Use smaller images or public HTTPS URLs when the combined Base64 payload is too large. These additional checks are not claimed to be OpenRouter catalog restrictions.

Audio is native to this model. Describe dialogue, ambience, and sound effects in the prompt. The helper omits `generateAudio` and rejects both `--audio` and `--no-audio`; neither is a supported mute control. There is no watermark option. Do not add avatar IDs, voice IDs, scripts, or direct HeyGen `mode` fields to this OpenRouter request.

## Job handling and output

- `create` waits by default. `--no-wait` returns the submission response immediately. Keep its ID; it is also printed to stderr.
- `status --job-id` performs one GET and returns the raw response. `wait --job-id` polls GET, every 10 seconds for up to 600 seconds by default; configure positive integer `--poll-interval` / `--max-wait` values.
- `--output FILE.json` saves raw submission/status JSON, including the last successful poll on timeout. `--download-dir DIR` or `--output FILE.mp4` downloads only when waiting completes. Downloads are optional.
- `--text-only` / `-t` returns a job ID for create without waiting, or a video URL/local path after waiting. Status always returns raw JSON.
- `--dry-run` prints a create payload, or a GET request description for status/wait, without sending it.
- Stop on API errors, unknown status, failed/cancelled/expired jobs, or failed delivery. A generated job with pending Frevana delivery still needs polling. Preserve raw errors and IDs; generation, delivery, and billing are separate outcomes.
- Never automatically repeat a POST after a transport error, missing ID, timeout, or local output/download failure. Resume a known ID with status/wait. This helper does not expose a verified idempotency contract for the Frevana route. Its no-retry behavior applies to the helper only: the locally inspected Server SDK retries upstream POSTs by default; see the Server compatibility findings in [references/api.md](references/api.md).
- Frevana credentials are sent only to the configured API origin. External video links are downloaded without those headers; authenticated downloads do not follow redirects.

Summarize the result and provide the video URL or saved path plus job ID. Do not imply a live generation was tested when only dry-run or mocked tests ran.

Offline validation (all HTTP mocked):

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s skills/heygen-video-1/tests -v
```
