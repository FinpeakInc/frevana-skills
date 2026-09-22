---
name: wan-3.0
description: Generate flexible video from text or image prompts using Alibaba Wan 3.0 (alibaba/wan-3.0) via Frevana's OpenRouter video endpoint, supporting 480p, 720p, and 1080p resolutions, durations from 2 to 30 seconds, audio, and seed control.
---

# Alibaba Wan 3.0 Video

Generate high-quality video from text or image prompts through Frevana's OpenRouter video endpoint using `alibaba/wan-3.0`.

## Model Characteristics

- **Model ID**: `alibaba/wan-3.0` (variant: `alibaba/wan-3.0-prime`)
- **Resolutions**: `480p`, `720p` (default), `1080p`
- **Aspect Ratios**: `16:9` (default), `4:3`, `1:1`, `3:4`, `9:16`
- **Durations**: `2` to `30` seconds (default: `5`)
- **Frame Control**: Supports `first_frame` (image-to-video; does not support `last_frame`)
- **Input References**: Wan 3.0 supports reference images; Wan 3.0 Prime does not currently list input-reference support
- **Audio**: Synchronized audio generation supported (default: enabled)
- **Seed**: Deterministic integer seed supported

## Prerequisites & Authentication

- `FREVANA_TOKEN` (or `--token`) or `FREVANA_API_KEY` (or `--api-key`) in the environment
- Optional `FREVANA_AGENT_APP_INSTANCE_ID` (or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Invocation

```bash
# Text-to-video: submit and wait for video completion
bash skills/wan-3.0/scripts/generate_video.sh \
  --prompt "An ink-wash painting style landscape coming alive with flowing waterfall and misty mountains" \
  --duration 5 \
  --resolution 720p \
  --aspect-ratio 16:9 \
  --download-dir ./output

# Image-to-video with first frame
bash skills/wan-3.0/scripts/generate_video.sh \
  --prompt "The character blinks and smiles gently as petals fall around her" \
  --first-frame ./portrait.jpg \
  --duration 6 \
  --download-dir ./output

# Status check
bash skills/wan-3.0/scripts/generate_video.sh status --job-id <JOB_ID>
```

## Allowed Options

- `-p, --prompt TEXT`: Text description of the video (required for create)
- `--prompt-file PATH`: Path to file containing prompt
- `--model MODEL`: Model slug (default: `alibaba/wan-3.0`, allowed: `alibaba/wan-3.0`, `alibaba/wan-3.0-prime`)
- `--duration SEC`: Duration in seconds (`2`-`30`, default: `5`)
- `--aspect-ratio RATIO`: `16:9`, `4:3`, `1:1`, `3:4`, `9:16` (default: `16:9`)
- `--resolution RES`: `480p`, `720p`, `1080p` (default: `720p`)
- `--size WIDTHxHEIGHT`: Exact output dimensions; overrides `--resolution` and `--aspect-ratio`
- `--first-frame, --image PATH/URL`: Image path or URL for first frame
- `--reference-image PATH/URL`: Add a reference image for Wan 3.0; repeatable and rejected for Wan 3.0 Prime
- `--reference-audio URL`: Unsupported by these models
- `--reference-video URL`: Unsupported by these models
- `--audio`: Generate audio (default: true)
- `--no-audio`: Disable audio generation
- `--seed INT`: Deterministic integer seed for reproducible generation
- `--wait`: Wait for job completion and download/output (default in CLI)
- `--no-wait`: Submit job and return immediately with Job ID
- `--poll-interval SEC`: Seconds between status checks (default: `10`)
- `--max-wait SEC`: Maximum seconds to wait before timeout (default: `600`)
- `--download-dir DIR`: Directory to download completed MP4 video
- `-o, --output FILE`: Path to save output JSON or MP4 file
- `-t, --text-only`: Output only the video URL or downloaded file path
- `--dry-run`: Print request payload JSON and exit without network calls
- `--token TOKEN`: Frevana Bearer token override
- `--api-key KEY`: Frevana API key override
- `--agent-app-instance-id ID`: Agent App instance ID override

## Guardrails

- For semantic requests such as "720p landscape" or "1080p vertical", use `--resolution` with `--aspect-ratio`.
- Use `--size` only when the user explicitly requires exact `WIDTHxHEIGHT` pixels; it overrides and replaces both semantic dimension fields in the request payload.
- Validate that `--duration` is between 2 and 30 seconds.
- Validate that `--resolution` is one of `480p`, `720p`, or `1080p`.
- Do not pass `--last-frame`; Wan 3.0 only supports `first_frame`.
- `--size` is format-checked locally but not matched against a static model allowlist; model/provider compatibility is validated by the API.
- A first-frame image and input references may be sent together; OpenRouter gives `frameImages` precedence and treats the request as image-to-video.
