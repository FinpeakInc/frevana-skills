---
name: kling-v3.0-pro
description: Generate premium cinematic video with enhanced visual quality using Kling Video v3.0 Pro (kwaivgi/kling-v3.0-pro) via Frevana's OpenRouter video endpoint, supporting 720p resolution, durations from 3 to 15 seconds, synchronized audio, negative prompt, and first/last frame controls.
---

# Kling Video v3.0 Pro

Generate high-end cinematic video with synchronized audio through Frevana's OpenRouter video endpoint using `kwaivgi/kling-v3.0-pro`.

## Model Characteristics

- **Model ID**: `kwaivgi/kling-v3.0-pro`
- **Resolution**: `720p` (fixed)
- **Aspect Ratios**: `16:9` (default), `9:16`, `1:1`
- **Durations**: `3` to `15` seconds (default: `5`)
- **Frame Control**: Supports both `first_frame` and `last_frame` (image-to-video)
- **Audio**: Synchronized audio generation supported (default: enabled)
- **Seed**: Deterministic seed is not supported by this model
- **Passthrough Controls**: `negative_prompt`, `cfg_scale`

## Prerequisites & Authentication

- `FREVANA_TOKEN` (or `--token`) or `FREVANA_API_KEY` (or `--api-key`) in the environment
- Optional `FREVANA_AGENT_APP_INSTANCE_ID` (or `--agent-app-instance-id`) sent as `x-frevana-agent-app-instance-id`
- `curl`, `bash`, and `python3`

## Invocation

```bash
# Text-to-video: submit and wait for video completion
bash skills/kling-v3.0-pro/scripts/generate_video.sh \
  --prompt "A cinematic close-up of an astronaut's visor reflecting a distant exploding nebula" \
  --duration 6 \
  --aspect-ratio 16:9 \
  --download-dir ./output

# Image-to-video with first and last frame
bash skills/kling-v3.0-pro/scripts/generate_video.sh \
  --prompt "The camera smoothly circles the character in dramatic studio lighting" \
  --first-frame ./first.png \
  --last-frame ./last.png \
  --duration 5 \
  --download-dir ./output

# Status check
bash skills/kling-v3.0-pro/scripts/generate_video.sh status --job-id <JOB_ID>
```

## Allowed Options

- `-p, --prompt TEXT`: Text description of the video (required for create)
- `--prompt-file PATH`: Path to file containing prompt
- `--model MODEL`: Model slug (default: `kwaivgi/kling-v3.0-pro`)
- `--duration SEC`: Duration in seconds (`3`-`15`, default: `5`)
- `--aspect-ratio RATIO`: `16:9`, `9:16`, `1:1` (default: `16:9`)
- `--resolution RES`: `720p` (default: `720p`)
- `--first-frame, --image PATH/URL`: Image path or URL for first frame
- `--last-frame PATH/URL`: Image path or URL for last frame
- `--audio`: Generate synchronized audio (default: true)
- `--no-audio`: Disable audio generation
- `--negative-prompt TEXT`: Negative prompt (e.g. "blurry, distorted, artifacts")
- `--cfg-scale NUM`: CFG guidance scale (e.g. 0.5)
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

- Validate that `--duration` is between 3 and 15 seconds.
- Validate that `--resolution` is `720p`.
- Validate that `--aspect-ratio` is one of `16:9`, `9:16`, or `1:1`.
- Do not pass `--seed`; Kling Pro does not support deterministic seed.
