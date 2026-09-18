---
name: minimax-h3
description: Generate high-definition 2K videos using MiniMax H3 (minimax/hailuo-3) via Frevana's OpenRouter video endpoint, supporting text-to-video, image-to-video (first frame and last frame), native audio, and durations from 5 to 15 seconds.
---

# MiniMax H3 Video

Generate high-definition 2K videos through Frevana's OpenRouter video endpoint using `minimax/hailuo-3`.

## Model Characteristics

- **Model ID**: `minimax/hailuo-3`
- **Resolution**: `2K` (fixed)
- **Aspect Ratios**: `16:9` (default), `9:16`, `1:1`, `4:3`, `3:4`, `21:9`
- **Durations**: `5` to `15` seconds (default: `6`)
- **Frame Control**: Supports both `first_frame` and `last_frame` (image-to-video)
- **Audio**: Native synchronized audio generation supported (enabled by default)
- **Seed**: Deterministic seed is not supported by this model

## Prerequisites & Authentication

- `FREVANA_TOKEN` (or `--token`) or `FREVANA_API_KEY` (or `--api-key`) in the environment
- Optional `FREVANA_AGENT_APP_INSTANCE_ID` (or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Invocation

```bash
# Text-to-video: submit and wait for video completion
bash skills/minimax-h3/scripts/generate_video.sh \
  --prompt "A cinematic drone shot flying over misty autumn mountains at sunrise, photorealistic, 2K" \
  --duration 6 \
  --aspect-ratio 16:9 \
  --download-dir ./output

# Image-to-video with first frame
bash skills/minimax-h3/scripts/generate_video.sh \
  --prompt "The camera slowly pans out as waves lap against the shore" \
  --first-frame ./beach.jpg \
  --duration 6 \
  --download-dir ./output

# Check status of an existing job
bash skills/minimax-h3/scripts/generate_video.sh status --job-id <JOB_ID>

# Wait for an existing job to complete
bash skills/minimax-h3/scripts/generate_video.sh wait --job-id <JOB_ID> --download-dir ./output
```

## Allowed Options

- `-p, --prompt TEXT`: Text description of the video (required for create)
- `--prompt-file PATH`: Path to file containing prompt
- `--model MODEL`: Model slug (default: `minimax/hailuo-3`)
- `--duration SEC`: Duration in seconds (`5`-`15`, default: `6`)
- `--aspect-ratio RATIO`: `16:9`, `9:16`, `1:1`, `4:3`, `3:4`, `21:9` (default: `16:9`)
- `--resolution RES`: `2K` (default: `2K`)
- `--first-frame, --image PATH/URL`: Image path or URL for first frame
- `--last-frame PATH/URL`: Image path or URL for last frame
- `--audio`: Generate audio (default: true)
- `--no-audio`: Disable audio generation
- `--watermark`: Enable AIGC watermark
- `--no-watermark`: Disable AIGC watermark
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

- Validate that `--duration` is an integer between 5 and 15 seconds.
- Validate that `--resolution` is `2K`. Unsupported resolutions will be rejected client-side before calling the API.
- Do not pass `--seed`; MiniMax H3 does not support seed parameters.
- If `--first-frame` or `--last-frame` points to a local file, the script automatically encodes it as a base64 data URI.
