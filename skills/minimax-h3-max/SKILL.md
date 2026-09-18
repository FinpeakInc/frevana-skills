---
name: minimax-h3-max
description: Generate videos with fast turnaround using MiniMax H3 Max (minimax/hailuo-3-max) via Frevana's OpenRouter video endpoint, supporting text-to-video, image-to-video (first and last frame), 768p and 480p resolutions, and durations from 5 to 15 seconds.
---

# MiniMax H3 Max Video

Generate video clips with fast turnaround through Frevana's OpenRouter video endpoint using `minimax/hailuo-3-max`.

## Model Characteristics

- **Model ID**: `minimax/hailuo-3-max`
- **Resolutions**: `768p` (default), `480p`
- **Aspect Ratios**: `16:9` (default), `9:16`, `1:1`, `4:3`, `3:4`, `21:9`
- **Durations**: `5` to `15` seconds (default: `6`)
- **Frame Control**: Supports both `first_frame` and `last_frame` (image-to-video)
- **Audio**: Audio generation is not supported by this model
- **Seed**: Deterministic seed is not supported by this model

## Prerequisites & Authentication

- `FREVANA_TOKEN` (or `--token`) or `FREVANA_API_KEY` (or `--api-key`) in the environment
- Optional `FREVANA_AGENT_APP_INSTANCE_ID` (or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Invocation

```bash
# Text-to-video: submit and wait for video completion
bash skills/minimax-h3-max/scripts/generate_video.sh \
  --prompt "A cute red panda running through snow, soft natural light" \
  --duration 6 \
  --resolution 768p \
  --aspect-ratio 16:9 \
  --download-dir ./output

# Image-to-video with first frame
bash skills/minimax-h3-max/scripts/generate_video.sh \
  --prompt "Camera zooms in smoothly on the character" \
  --first-frame ./character.png \
  --duration 5 \
  --download-dir ./output

# Check status of an existing job
bash skills/minimax-h3-max/scripts/generate_video.sh status --job-id <JOB_ID>
```

## Allowed Options

- `-p, --prompt TEXT`: Text description of the video (required for create)
- `--prompt-file PATH`: Path to file containing prompt
- `--model MODEL`: Model slug (default: `minimax/hailuo-3-max`)
- `--duration SEC`: Duration in seconds (`5`-`15`, default: `6`)
- `--aspect-ratio RATIO`: `16:9`, `9:16`, `1:1`, `4:3`, `3:4`, `21:9` (default: `16:9`)
- `--resolution RES`: `768p`, `480p` (default: `768p`)
- `--first-frame, --image PATH/URL`: Image path or URL for first frame
- `--last-frame PATH/URL`: Image path or URL for last frame
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

- Validate that `--duration` is between 5 and 15 seconds.
- Validate that `--resolution` is either `768p` or `480p`. Do not pass 2K or 1080p.
- Do not pass `--audio`; MiniMax H3 Max does not generate audio.
- Do not pass `--seed`; seed parameters are unsupported.
