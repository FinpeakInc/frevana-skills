---
name: seedance-2-5
description: Generate next-generation audio-visual video with extended durations using ByteDance Seedance 2.5 (bytedance/seedance-2.5) via Frevana's OpenRouter video endpoint, supporting 480p and 720p resolutions, durations from 4 to 30 seconds, deterministic seed, and first/last frame controls.
---

# ByteDance Seedance 2.5 Video

Generate next-generation audio-visual video with extended duration through Frevana's OpenRouter video endpoint using `bytedance/seedance-2.5`.

## Model Characteristics

- **Model ID**: `bytedance/seedance-2.5` (variant: `bytedance/seedance-1-5-pro`)
- **Resolutions**: `480p`, `720p` (default)
- **Aspect Ratios**: `16:9` (default), `4:3`, `1:1`, `3:4`, `9:16`, `21:9`
- **Durations**: `4` to `30` seconds (default: `5`)
- **Frame Control**: Supports both `first_frame` and `last_frame` (image-to-video)
- **Audio**: Synchronized audio generation supported (default: enabled)
- **Seed**: Deterministic integer seed supported
- **Passthrough Controls**: `watermark`, `req_key`, `output_format`

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
- `--duration SEC`: Duration in seconds (`4`-`30`, default: `5`)
- `--aspect-ratio RATIO`: `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9` (default: `16:9`)
- `--resolution RES`: `480p`, `720p` (default: `720p`)
- `--first-frame, --image PATH/URL`: Image path or URL for first frame
- `--last-frame PATH/URL`: Image path or URL for last frame
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

- Validate that `--duration` is between 4 and 30 seconds.
- Validate that `--resolution` is either `480p` or `720p`. Do not pass 1080p or 4K.
- Validate that `--aspect-ratio` is one of the supported 6 aspect ratios.
