---
name: seedance-2-5
description: Generate next-generation audio-visual video with extended durations using ByteDance Seedance 2.5 (bytedance/seedance-2.5) via Frevana's OpenRouter video endpoint, supporting 480p and 720p resolutions, durations from 4 to 30 seconds, deterministic seed, and first/last frame controls.
---

# ByteDance Seedance 2.5 Video

Generate next-generation audio-visual video with extended duration through Frevana's OpenRouter video endpoint using `bytedance/seedance-2.5`.

## Model Characteristics

- **Model ID**: `bytedance/seedance-2.5` (variant: `bytedance/seedance-1-5-pro`)
- **Resolutions**: Seedance 2.5 supports `480p` and `720p` (default); Seedance 1.5 Pro also supports `1080p`
- **Aspect Ratios**: `16:9` (default), `4:3`, `1:1`, `3:4`, `9:16`, `21:9`; Seedance 1.5 Pro also supports `9:21`
- **Durations**: Seedance 2.5 supports `4` to `30` seconds; Seedance 1.5 Pro supports `4` to `12` seconds (default: `5`)
- **Frame Control**: Supports both `first_frame` and `last_frame` (image-to-video)
- **Input References**: Seedance 2.5 supports reference images, audio, and video; Seedance 1.5 Pro supports reference images only
- **Audio**: Synchronized audio generation supported (default: enabled)
- **Seed**: Deterministic integer seed supported
- **Passthrough Controls**: `watermark`

## Prerequisites & Authentication

- `FREVANA_TOKEN` (or `--token`) or `FREVANA_API_KEY` (or `--api-key`) in the environment
- Optional `FREVANA_AGENT_APP_INSTANCE_ID` (or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Invocation

```bash
# Text-to-video: submit and wait for video completion
bash skills/seedance-2-5/scripts/generate_video.sh \
  --prompt "An epic sci-fi spaceship journey through a crystalline nebula with intense synchronized audio" \
  --duration 10 \
  --resolution 720p \
  --aspect-ratio 16:9 \
  --download-dir ./output

# Image-to-video with first frame
bash skills/seedance-2-5/scripts/generate_video.sh \
  --prompt "The character starts speaking with natural facial expressions" \
  --first-frame ./portrait.jpg \
  --duration 6 \
  --download-dir ./output

# Status check
bash skills/seedance-2-5/scripts/generate_video.sh status --job-id <JOB_ID>
```

## Allowed Options

- `-p, --prompt TEXT`: Text description of the video (required for create)
- `--prompt-file PATH`: Path to file containing prompt
- `--model MODEL`: Model slug (default: `bytedance/seedance-2.5`, allowed: `bytedance/seedance-2.5`, `bytedance/seedance-1-5-pro`)
- `--duration SEC`: Seedance 2.5: `4`-`30`; Seedance 1.5 Pro: `4`-`12` (default: `5`)
- `--aspect-ratio RATIO`: `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`; Seedance 1.5 Pro also accepts `9:21` (default: `16:9`)
- `--resolution RES`: Seedance 2.5: `480p`, `720p`; Seedance 1.5 Pro also accepts `1080p` (default: `720p`)
- `--size WIDTHxHEIGHT`: Exact output dimensions; overrides `--resolution` and `--aspect-ratio`
- `--first-frame, --image PATH/URL`: Image path or URL for first frame
- `--last-frame PATH/URL`: Image path or URL for last frame
- `--reference-image PATH/URL`: Add a reference image; repeatable for both models
- `--reference-audio URL`: Add a reference audio URL for Seedance 2.5; rejected for Seedance 1.5 Pro
- `--reference-video URL`: Add a reference video URL for Seedance 2.5; rejected for Seedance 1.5 Pro
- `--audio`: Generate synchronized audio (default: true)
- `--no-audio`: Disable audio generation
- `--seed INT`: Deterministic integer seed for reproducible generation
- `--watermark`: Enable watermark
- `--no-watermark`: Disable watermark
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

- For semantic requests such as "720p landscape" or "vertical video", use `--resolution` with `--aspect-ratio`.
- Use `--size` only when the user explicitly requires exact `WIDTHxHEIGHT` pixels; it overrides and replaces both semantic dimension fields in the request payload.
- Validate duration, resolution, and aspect ratio against the selected model.
- `--size` is format-checked locally but not matched against a static model allowlist; model/provider compatibility is validated by the API.
- Seedance 2.5 accepts 4-30 seconds at 480p/720p; Seedance 1.5 Pro accepts 4-12 seconds, adds 1080p and `9:21`.
- Frame images and input references may be sent together; OpenRouter gives `frameImages` precedence and treats the request as image-to-video.
