#!/usr/bin/env python3
"""Generate and cache Frevana solution-page images through gpt-image-2."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_SIZE = "1536x1024"
DEFAULT_QUALITY = "high"
DEFAULT_FORMAT = "png"


class ImageGenerationError(RuntimeError):
    """Raised when gpt-image-2 cannot generate an image."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _skill_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _default_gpt_image_script() -> Path:
    return _skill_dir().parent / "gpt-image-2" / "scripts" / "generate_image.sh"


def resolve_gpt_image_script() -> Path:
    override = os.environ.get("GPT_IMAGE_2_SCRIPT")
    script = Path(override).expanduser() if override else _default_gpt_image_script()
    if not script.exists():
        raise ImageGenerationError(
            "Cannot find gpt-image-2 script. Expected "
            f"{script}. Set GPT_IMAGE_2_SCRIPT to override."
        )
    return script


def prompt_hash(slot: str, prompt: str, size: str, quality: str, output_format: str) -> str:
    payload = json.dumps(
        {
            "slot": slot,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "output_format": output_format,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_prompt(slot: str, title: str, body: str, extra: str = "") -> str:
    content = " ".join(part for part in [title, body, extra] if part).strip()
    return (
        "Create a Frevana solution-page image asset for the "
        f"{slot} slot, matching the current Frevana /individual page. "
        "Visual system: white-background product illustration collage, not a full-bleed photo. "
        "Use oversized white rounded UI cards with thin dark navy outlines, soft shadows, "
        "bold black UI text, Frevana green accents (#3D9040), and one or two flat geometric "
        "decorative shapes in green, teal, orange, yellow, light cyan, or soft pink. "
        "The asset should feel like a clean product illustration or UI sticker sheet placed on a white page. "
        "Use object-contain composition with generous clean white negative space margins and no rectangular photo frame. "
        "Hero may include a tasteful cropped lifestyle/product-photo element blended with graphic overlays; "
        "feature and module slots should primarily be UI-card collage illustrations. "
        "Avoid generic SaaS screenshots, stock-photo office scenes, purple AI gradients, dark cyberpunk, "
        "3D mascots, fake brand logos, tiny unreadable paragraphs, busy backgrounds, checkerboard patterns, transparency preview grids, and alpha-channel preview backgrounds. "
        f"Page copy context: {content}"
    )


def style_wrapped_prompt(slot: str, prompt: str) -> str:
    return (
        "Render this as a Frevana /individual page visual asset. "
        "Required style: white-background product illustration collage, white rounded UI cards, "
        "thin dark navy outlines, soft shadows, bold black UI labels, Frevana green #3D9040 accents, "
        "flat geometric overlays, object-contain composition, clean white-page compatibility. "
        "Do not create a normal photo, full dashboard screenshot, purple AI graphic, dark background, checkerboard pattern, transparency preview grid, or alpha-channel preview background. "
        f"Slot: {slot}. Content brief: {prompt}"
    )


def collect_image_slots(page_data: dict[str, Any]) -> list[dict[str, str]]:
    slots: list[dict[str, str]] = []
    hero = page_data.get("hero") or {}
    if not _text(hero.get("image_url")):
        slots.append(
            {
                "slot": "hero",
                "prompt": style_wrapped_prompt(
                    "hero",
                    _text(hero.get("image_prompt"))
                    or build_prompt("hero", _text(hero.get("title")), _text(hero.get("body"))),
                ),
                "alt": _text(hero.get("image_alt")) or _text(hero.get("title")) or "Frevana hero visual",
            }
        )

    for index, section in enumerate(page_data.get("sections") or [], start=1):
        if index > 4:
            break
        if _text(section.get("image_url")):
            continue
        slot = f"section-{index}"
        slots.append(
            {
                "slot": slot,
                "prompt": style_wrapped_prompt(
                    slot,
                    _text(section.get("image_prompt"))
                    or build_prompt(slot, _text(section.get("title")), _text(section.get("body"))),
                ),
                "alt": _text(section.get("image_alt")) or _text(section.get("title")) or f"Frevana {slot} visual",
            }
        )

    module = page_data.get("module") or {}
    if module and not _text(module.get("image_url")):
        active_tab = (module.get("tabs") or [{}])[0] if isinstance(module.get("tabs"), list) else {}
        slots.append(
            {
                "slot": "module",
                "prompt": style_wrapped_prompt(
                    "module",
                    _text(module.get("image_prompt"))
                    or build_prompt(
                        "module",
                        _text(module.get("title")) or _text(active_tab.get("title")),
                        _text(active_tab.get("body")),
                    ),
                ),
                "alt": _text(module.get("image_alt")) or _text(module.get("title")) or "Frevana module visual",
            }
        )

    return slots


def generate_slot_image(
    slot_data: dict[str, str],
    cache_dir: Path,
    *,
    size: str = DEFAULT_SIZE,
    quality: str = DEFAULT_QUALITY,
    output_format: str = DEFAULT_FORMAT,
) -> dict[str, Any]:
    slot = slot_data["slot"]
    prompt = slot_data["prompt"]
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = prompt_hash(slot, prompt, size, quality, output_format)
    cache_path = cache_dir / f"{slot}-{digest}.json"

    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        cached["from_cache"] = True
        cached["cache_path"] = str(cache_path)
        return cached

    if not os.environ.get("FREVANA_TOKEN"):
        raise ImageGenerationError(
            "FREVANA_TOKEN is required to generate images with gpt-image-2. "
            "Set FREVANA_TOKEN or rerun generate_landing_page.py with --skip-images."
        )

    script = resolve_gpt_image_script()
    command = [
        str(script),
        "--prompt",
        prompt,
        "--size",
        size,
        "--quality",
        quality,
        "--output-format",
        output_format,
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise ImageGenerationError(
            "gpt-image-2 failed for "
            f"{slot} (exit {result.returncode}). stderr: {result.stderr.strip()}"
        )

    try:
        response = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ImageGenerationError(
            f"gpt-image-2 returned non-JSON output for {slot}: {result.stdout[:500]}"
        ) from exc

    image_url = (
        response.get("data", [{}])[0].get("image_url")
        if isinstance(response.get("data"), list)
        else None
    )
    if not image_url:
        raise ImageGenerationError(
            f"gpt-image-2 response for {slot} did not include data[0].image_url."
        )

    payload = {
        "slot": slot,
        "prompt": prompt,
        "alt": slot_data.get("alt", ""),
        "image_url": image_url,
        "provider_response": response,
        "from_cache": False,
        "cache_path": str(cache_path),
    }
    cache_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def render_images_for_page(
    page_data: dict[str, Any],
    cache_dir: Path,
    *,
    size: str = DEFAULT_SIZE,
    quality: str = DEFAULT_QUALITY,
    output_format: str = DEFAULT_FORMAT,
) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for slot_data in collect_image_slots(page_data):
        generated = generate_slot_image(
            slot_data,
            cache_dir,
            size=size,
            quality=quality,
            output_format=output_format,
        )
        manifest[slot_data["slot"]] = generated
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Frevana solution-page images.")
    parser.add_argument("--input", required=True, help="Page schema JSON file.")
    parser.add_argument("--output", required=True, help="Image manifest JSON output path.")
    parser.add_argument("--cache-dir", default="cache/images", help="Image cache directory.")
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    parser.add_argument("--output-format", default=DEFAULT_FORMAT)
    args = parser.parse_args()

    page_path = Path(args.input)
    output_path = Path(args.output)
    page_data = json.loads(page_path.read_text(encoding="utf-8"))
    manifest = render_images_for_page(
        page_data,
        Path(args.cache_dir),
        size=args.size,
        quality=args.quality,
        output_format=args.output_format,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ImageGenerationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
