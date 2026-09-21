---
name: seedance-2-0
description: Generate character-consistent video with synchronized audio using ByteDance Seedance 2.0 (bytedance/seedance-2.0) via Frevana's OpenRouter video endpoint, supporting 480p, 720p, 1080p, and 4K resolutions, durations from 4 to 15 seconds, deterministic seed, and first/last frame controls.
---

# ByteDance Seedance 2.0 Video

Generate character-consistent video with synchronized audio through Frevana's OpenRouter video endpoint using `bytedance/seedance-2.0`.

## Model Characteristics

- **Model ID**: `bytedance/seedance-2.0` (variants: `bytedance/seedance-2.0-fast`, `bytedance/seedance-2.0-mini`)
- **Resolutions**: the base model supports `480p`, `720p` (default), `1080p`, and `4K`; Fast and Mini support only `480p` and `720p`
- **Aspect Ratios**: `1:1`, `3:4`, `9:16`, `4:3`, `16:9` (default), `21:9`, `9:21`
- **Durations**: `4` to `15` seconds (default: `5`)
- **Frame Control**: Supports both `first_frame` and `last_frame` (image-to-video)
- **Input References**: Reference images, audio, and video (`image_url`, `audio_url`, `video_url`)
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
bash skills/seedance-2-0/scripts/generate_video.sh \
  --prompt "A warrior meditating in a bamboo forest under falling leaves, cinematic 4K" \
  --duration 5 \
  --resolution 1080p \
  --aspect-ratio 16:9 \
  --download-dir ./output

# Image-to-video with first and last frame
bash skills/seedance-2-0/scripts/generate_video.sh \
  --prompt "The hero turns around and smiles confidently" \
  --first-frame ./first.jpg \
  --last-frame ./last.jpg \
  --duration 6 \
  --download-dir ./output

# Status check
bash skills/seedance-2-0/scripts/generate_video.sh status --job-id <JOB_ID>
```

## Allowed Options

- `-p, --prompt TEXT`: Text description of the video (required for create)
- `--prompt-file PATH`: Path to file containing prompt
- `--model MODEL`: Model slug (default: `bytedance/seedance-2.0`, allowed: `bytedance/seedance-2.0`, `bytedance/seedance-2.0-fast`, `bytedance/seedance-2.0-mini`)
- `--duration SEC`: Duration in seconds (`4`-`15`, default: `5`)
- `--aspect-ratio RATIO`: `1:1`, `3:4`, `9:16`, `4:3`, `16:9`, `21:9`, `9:21` (default: `16:9`)
- `--resolution RES`: base model: `480p`, `720p`, `1080p`, `4K`; Fast/Mini: `480p`, `720p` (default: `720p`)
- `--first-frame, --image PATH/URL`: Image path or URL for first frame
- `--last-frame PATH/URL`: Image path or URL for last frame
- `--reference-image PATH/URL`: Add a reference image; repeatable
- `--reference-audio URL`: Add a reference audio URL; repeatable
- `--reference-video URL`: Add a reference video URL; repeatable
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

- Validate that `--duration` is between 4 and 15 seconds.
- Validate resolution against the selected model; Fast and Mini reject `1080p` and `4K`.
- Validate that `--aspect-ratio` is one of the supported 7 aspect ratios.
- Frame images and input references may be sent together; OpenRouter gives `frameImages` precedence and treats the request as image-to-video.
