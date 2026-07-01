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
DEFAULT_BACKGROUND = "transparent"
DEFAULT_VISUAL_SEED = "frevana-individual-cn-reference-style-v4"


class ImageGenerationError(RuntimeError):
    """Raised when gpt-image-2 cannot generate an image."""


def _text(value: Any) -> str:
    return str(value or "").strip()


def _compact_brief(value: Any, *, limit: int = 72) -> str:
    brief = " ".join(_text(value).split())
    if len(brief) <= limit:
        return brief
    return brief[:limit].rstrip(" ，。,.;；:")


def _has_any(value: str, needles: tuple[str, ...]) -> bool:
    return any(needle in value for needle in needles)


def _canonical_visual_theme(slot: str, *values: Any) -> str:
    raw = " ".join(_text(value) for value in values if _text(value))
    normalized = raw.lower()
    rules = [
        (
            ("question", "query", "queries", "ask", "asking", "intent", "问题", "查询", "提问", "意图"),
            "question discovery and search intent",
        ),
        (
            ("content", "article", "blog", "page", "faq", "answer", "citation", "cite", "引用", "内容", "文章", "页面", "问答", "答案"),
            "ai-readable content creation",
        ),
        (
            ("agent", "team", "module", "assistant", "团队", "模块", "智能体", "助手"),
            "ai agent team and modular workflow",
        ),
        (
            ("course", "learn", "learning", "workflow", "guide", "practice", "best practice", "课程", "学习", "流程", "指南", "实践"),
            "learning workflow and best-practice guidance",
        ),
        (
            ("report", "insight", "analysis", "benchmark", "competitor", "ranking", "报告", "洞察", "分析", "竞品", "排名"),
            "report insight and benchmark analysis",
        ),
        (
            ("visibility", "growth", "recommend", "recommendation", "acquisition", "client", "lead", "可见度", "增长", "推荐", "获客", "客户", "线索"),
            "ai visibility growth and client acquisition",
        ),
    ]
    for needles, theme in rules:
        if _has_any(normalized, needles):
            return theme
    if slot == "hero":
        return "ai visibility growth and client acquisition"
    if slot == "module":
        return "ai agent team and modular workflow"
    return "simple frevana solution feature"


HERO_VISUAL_MOTIFS = [
    "a broad acquisition-channel visual with one wide search/input card, two small status chips, a coral rectangle, a blue ring, and one teal rounded block",
    "an abstract workspace-object crop with layered pastel geometric overlays, one small insight card, and no visible faces or logos",
    "a compact AI visibility command bar with two floating result chips, one folded corner shape, one ring, and one large soft mint backdrop",
]

SECTION_VISUAL_MOTIFS = [
    "three staggered short question chips over a cyan concentric-circle or target motif, with one tiny arrow button",
    "two overlapping document cards with gray placeholder lines, a small sparkle badge, and yellow plus soft-pink circles",
    "a checklist or course card, a dotted route line, a small flag or book icon, and a sky-blue frame or mint blob",
    "a compact chart card, a donut or pie segment, one report pill, and a lavender or cyan semicircle",
    "three small horizontal agent cards connected to a central node, with one rounded mint backdrop and one warm-yellow accent",
    "one compact search/input card plus two floating query chips, a coral folded corner, and a thin blue ring",
    "a simple dashboard tile with one line chart, a tiny check badge, a lavender circle, and a salmon semicircle",
    "a content preview card with skeleton lines, a small magic/spark icon, and overlapping yellow and cyan geometric blocks",
    "a small report document card with a link pill, a soft blue arch, and a peach vertical stripe",
]

MODULE_VISUAL_MOTIFS = [
    "three small horizontal agent cards connected to a central node, with one rounded mint backdrop and one warm-yellow accent",
    "a compact tabbed module card with three tiny role chips, a central sparkle badge, and soft cyan plus lavender geometric accents",
]


def _page_visual_offset(page_data: dict[str, Any], pool_size: int, salt: str) -> int:
    sections = page_data.get("sections") or []
    seed_parts = [
        salt,
        _text(page_data.get("visual_seed")) or DEFAULT_VISUAL_SEED,
        str(len(sections)),
        str(bool(page_data.get("module"))),
    ]
    seed = "|".join(part for part in seed_parts if part)
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % pool_size


def _visual_direction(page_data: dict[str, Any], ordinal: int, *, kind: str = "section") -> str:
    if kind == "hero":
        pool = HERO_VISUAL_MOTIFS
        salt = "hero"
    elif kind == "module":
        pool = MODULE_VISUAL_MOTIFS
        salt = "module"
    else:
        pool = SECTION_VISUAL_MOTIFS
        salt = "section"

    index = (_page_visual_offset(page_data, len(pool), salt) + ordinal) % len(pool)
    cycle = ordinal // len(pool)
    variant = "" if cycle == 0 else f" Use a visibly different scale, rotation, and spacing variant #{cycle + 1}."
    return (
        f"Assigned visual motif: {pool[index]}. "
        "This motif is assigned dynamically for this page; do not treat the section number as a fixed design type."
        f"{variant} "
    )


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


def prompt_hash(slot: str, prompt: str, size: str, quality: str, output_format: str, background: str) -> str:
    payload = json.dumps(
        {
            "slot": slot,
            "prompt": prompt,
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "background": background,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_prompt(slot: str, title: str, body: str, extra: str = "") -> str:
    # Use a canonical theme so localized Chinese/English page copy does not steer image style differently.
    return _canonical_visual_theme(slot, extra, title, body)


def style_wrapped_prompt(slot: str, prompt: str, visual_direction: str) -> str:
    theme = _canonical_visual_theme(slot, prompt)
    return (
        "Render a simple spot illustration that matches the current Chinese Frevana /individual reference page style. "
        "Use the same airy, open, lightweight illustration style for every page language, including English pages. "
        "This is not an information poster, not a SaaS dashboard screenshot, and not an app mockup inside a large frame. "
        "Use the canonical visual theme only as a loose concept cue; do not copy user-provided wording into the image. "
        "Every image slot must have a clearly different composition, silhouette, card arrangement, and accent-color mix from the other slots. "
        f"{visual_direction}"
        "General composition rules: floating cutout artwork with generous empty space around the objects, 1 large pastel geometric shape "
        "plus 1-2 white rounded UI cards unless the slot pattern says otherwise. Use simple shapes such as semi-circle, triangle, pill, ring, starburst, folded corner, or rounded blob. "
        "thin light-gray or dark-navy outlines, flat layers with no cast shadow and no drop shadow. "
        "Use a richer pastel palette: choose 2-3 colors from coral/salmon, warm yellow, cyan, sky blue, soft pink, lavender, mint, and Frevana green; "
        "Frevana green #3D9040 should be a small accent, not the dominant color. "
        "Optional tiny icon badges are allowed. Do not draw any page, canvas, rectangular plate, tiled pattern, background fill, "
        "large enclosing white card, browser frame, dashboard container, app window, bottom label pills, or platform-name chips behind or around the artwork. "
        "Text rules: avoid readable text; use gray placeholder lines whenever possible. If text is absolutely necessary, use at most one short generic English label of 1-2 words. "
        "No Chinese text, no paragraphs, no bullet lists, no copied landing-page headline/body text, no platform names, no dense dashboard tables. "
        "Strictly avoid: product logos, Frevana logo, brand logos, platform logos, real human faces, "
        "real human portraits, detailed people, normal office stock photos for feature/module slots, "
        "busy UI collages, complex flowcharts, repeating gray tile artifacts, big white presentation cards, reused hero layouts, repeated compositions across slots, "
        "purple AI art, dark backgrounds, 3D mascots, heavy shadows, glossy 3D depth, and tiny unreadable text. "
        f"Slot: {slot}. Canonical visual theme: {theme}"
    )


def collect_image_slots(page_data: dict[str, Any]) -> list[dict[str, str]]:
    slots: list[dict[str, str]] = []
    section_visual_ordinal = 0
    hero = page_data.get("hero") or {}
    if not _text(hero.get("image_url")):
        slots.append(
            {
                "slot": "hero",
                "prompt": style_wrapped_prompt(
                    "hero",
                    _text(hero.get("image_prompt"))
                    or build_prompt("hero", _text(hero.get("title")), _text(hero.get("body"))),
                    _visual_direction(page_data, 0, kind="hero"),
                ),
                "alt": _text(hero.get("image_alt")) or _text(hero.get("title")) or "Frevana hero visual",
            }
        )

    for index, section in enumerate(page_data.get("sections") or [], start=1):
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
                    _visual_direction(page_data, section_visual_ordinal, kind="section"),
                ),
                "alt": _text(section.get("image_alt")) or _text(section.get("title")) or f"Frevana {slot} visual",
            }
        )
        section_visual_ordinal += 1

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
                    _visual_direction(page_data, 0, kind="module"),
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
    background: str = DEFAULT_BACKGROUND,
) -> dict[str, Any]:
    slot = slot_data["slot"]
    prompt = slot_data["prompt"]
    cache_dir.mkdir(parents=True, exist_ok=True)
    digest = prompt_hash(slot, prompt, size, quality, output_format, background)
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
        "bash",
        str(script),
        "--prompt",
        prompt,
        "--size",
        size,
        "--quality",
        quality,
        "--output-format",
        output_format,
        "--background",
        background,
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
        "background": background,
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
    background: str = DEFAULT_BACKGROUND,
) -> dict[str, dict[str, Any]]:
    manifest: dict[str, dict[str, Any]] = {}
    for slot_data in collect_image_slots(page_data):
        generated = generate_slot_image(
            slot_data,
            cache_dir,
            size=size,
            quality=quality,
            output_format=output_format,
            background=background,
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
    parser.add_argument("--background", default=DEFAULT_BACKGROUND, choices=["transparent", "opaque", "auto"])
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
        background=args.background,
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
