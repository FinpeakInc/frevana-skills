#!/usr/bin/env python3
"""Render a Frevana solution-style landing page from a compact JSON schema."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import quote

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import render_images  # noqa: E402


DEFAULT_CTA_URL = "/zh-CN/signup"


def text(value: Any, default: str = "") -> str:
    value = str(value).strip() if value is not None else ""
    return value or default


def esc(value: Any, default: str = "") -> str:
    return html.escape(text(value, default), quote=True)


def normalize_cta_url(value: Any) -> str:
    return text(value, DEFAULT_CTA_URL)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def placeholder_svg(label: str) -> str:
    safe_label = html.escape(label or "Frevana visual")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1024" viewBox="0 0 1536 1024">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop stop-color="#effdf4"/>
      <stop offset="0.58" stop-color="#ffffff"/>
      <stop offset="1" stop-color="#dcefdc"/>
    </linearGradient>
  </defs>
  <rect width="1536" height="1024" rx="72" fill="url(#bg)"/>
  <rect x="168" y="156" width="1200" height="712" rx="56" fill="#ffffff" stroke="#cfe9d1" stroke-width="5"/>
  <rect x="232" y="238" width="510" height="44" rx="22" fill="#3d9040" opacity="0.9"/>
  <rect x="232" y="324" width="820" height="30" rx="15" fill="#111827" opacity="0.88"/>
  <rect x="232" y="382" width="680" height="24" rx="12" fill="#6b7280" opacity="0.36"/>
  <rect x="232" y="448" width="384" height="260" rx="34" fill="#effdf4" stroke="#cfe9d1" stroke-width="4"/>
  <rect x="664" y="448" width="552" height="260" rx="34" fill="#f7faf6" stroke="#e5e7eb" stroke-width="4"/>
  <circle cx="1096" cy="280" r="76" fill="#3d9040" opacity="0.18"/>
  <circle cx="1192" cy="300" r="38" fill="#3d9040" opacity="0.32"/>
  <text x="232" y="792" fill="#3d9040" font-family="Open Sans, sans-serif" font-size="42" font-weight="800">{safe_label}</text>
</svg>"""
    return "data:image/svg+xml;charset=utf-8," + quote(svg)


def image_for(
    item: dict[str, Any],
    slot: str,
    image_manifest: dict[str, dict[str, Any]],
    fallback_label: str,
) -> tuple[str, str]:
    explicit = text(item.get("image_url"))
    alt = text(item.get("image_alt"), fallback_label)
    if explicit:
        return explicit, alt
    generated = image_manifest.get(slot) or {}
    generated_url = text(generated.get("image_url"))
    generated_alt = text(generated.get("alt"), alt)
    if generated_url:
        return generated_url, generated_alt
    return placeholder_svg(fallback_label), alt


def render_header() -> str:
    return """
  <header class="site-header" aria-label="Frevana site header">
    <div class="site-header__inner">
      <a class="brand" href="/zh-CN" aria-label="Frevana home">
        <span class="brand__mark" aria-hidden="true"></span>
        <span>Frevana</span>
      </a>
      <nav class="nav" aria-label="Primary navigation">
        <div class="solutions-menu">
          <button class="nav__trigger" type="button" aria-haspopup="true">Solutions</button>
          <div class="solutions-menu__panel" role="menu" aria-label="Solutions menu">
            <div>
              <p class="solutions-menu__title">By business size</p>
              <div class="solutions-menu__list">
                <a class="solution-choice" href="/zh-CN/individual" role="menuitem">
                  <span class="solution-choice__icon" aria-hidden="true">♙</span>
                  <span><strong>Individual</strong><span>For solopreneur and professionals</span></span>
                </a>
                <a class="solution-choice" href="/zh-CN/small-teams" role="menuitem">
                  <span class="solution-choice__icon" aria-hidden="true">♧</span>
                  <span><strong>Small teams</strong><span>For growing businesses</span></span>
                </a>
                <a class="solution-choice" href="/zh-CN/companies" role="menuitem">
                  <span class="solution-choice__icon" aria-hidden="true">♢</span>
                  <span><strong>Companies</strong><span>For larger teams</span></span>
                </a>
              </div>
            </div>
            <div>
              <p class="solutions-menu__title">By industry</p>
              <div class="solutions-menu__list">
                <a class="solution-choice" href="/zh-CN/e-commerce" role="menuitem">
                  <span class="solution-choice__icon" aria-hidden="true">▣</span>
                  <span><strong>E-Commerce</strong></span>
                </a>
                <a class="solution-choice" href="/zh-CN/technology" role="menuitem">
                  <span class="solution-choice__icon" aria-hidden="true">▤</span>
                  <span><strong>Technology</strong></span>
                </a>
                <a class="solution-choice" href="/zh-CN/local-business" role="menuitem">
                  <span class="solution-choice__icon" aria-hidden="true">▥</span>
                  <span><strong>Local business</strong></span>
                </a>
              </div>
            </div>
          </div>
        </div>
        <a class="nav__link" href="/zh-CN/case-study">Case study</a>
        <a class="nav__link" href="https://frevana.gitbook.io/frevana-docs">Docs</a>
        <a class="nav__link" href="/zh-CN/articles">Articles</a>
        <a class="nav__link" href="/zh-CN/homepage#pricing">Pricing</a>
        <a class="nav__link" href="https://frevana.substack.com/">News</a>
      </nav>
      <div class="header-actions">
        <span class="language-pill" aria-label="Current language">🌐 中文</span>
        <a class="login-link" href="/zh-CN/login">Login</a>
        <a class="trial-link" href="/zh-CN/signup">Start free trial</a>
      </div>
    </div>
  </header>""".strip()


def render_footer() -> str:
    links = [
        ("Publications", "/zh-CN/publications"),
        ("Articles", "/zh-CN/articles"),
        ("Privacy", "/zh-CN/privacy"),
        ("Pricing", "/zh-CN/homepage#pricing"),
        ("Terms", "/zh-CN/terms"),
        ("About", "/zh-CN/about"),
        ("stories", "/zh-CN/stories"),
        ("book demo", "/zh-CN/book-demo"),
        ("Discover", "/zh-CN/discover"),
        ("FAQ", "/zh-CN/faq"),
        ("MCPs", "/zh-CN/mcps"),
        ("Download App", "/zh-CN/download"),
        ("Download Extension", "/zh-CN/extension"),
    ]
    link_html = "\n        ".join(
        f'<a href="{esc(url)}">{esc(label)}</a>' for label, url in links
    )
    return f"""
  <footer class="site-footer" aria-label="Frevana footer">
    <div class="site-footer__inner">
      <div class="site-footer__top">
        <a class="brand" href="/zh-CN" aria-label="Frevana home">
          <span class="brand__mark" aria-hidden="true"></span>
          <span>Frevana</span>
        </a>
        <div class="social-links" aria-label="Social links">
          <a href="https://twitter.com/frevana_ai">Twitter</a>
          <a href="https://www.instagram.com/frevana.ai/">Instagram</a>
          <a href="https://www.linkedin.com/company/frevana/">LinkedIn</a>
          <a href="https://www.youtube.com/@Frevana">YouTube</a>
        </div>
      </div>
      <nav class="footer-links" aria-label="Footer navigation">
        {link_html}
      </nav>
      <p class="copyright">© 2026 Frevana. All rights reserved.</p>
    </div>
  </footer>""".strip()


def render_hero(page_data: dict[str, Any], image_manifest: dict[str, dict[str, Any]]) -> str:
    hero = page_data.get("hero") or {}
    title = text(hero.get("title"), "让 AI 回答成为您下一个增长渠道")
    image_url, image_alt = image_for(hero, "hero", image_manifest, title)
    return f"""
    <section class="hero">
      <div class="container hero__grid">
        <div class="hero__copy">
          <span class="eyebrow">{esc(hero.get("eyebrow"),)}</span>
          <h1>{esc(title)}</h1>
          <p class="hero__body">{esc(hero.get("body"), "无论您面向哪类客户，Frevana 都能帮助您的网站获得 AI 回答曝光。")}</p>
          <a class="button" href="{esc(normalize_cta_url(hero.get("cta_url")))}">{esc(hero.get("cta_text"), "立即开始")} <span aria-hidden="true">→</span></a>
        </div>
        <div class="hero__visual visual-card">
          <img src="{esc(image_url)}" alt="{esc(image_alt)}">
        </div>
      </div>
    </section>""".strip()


def render_intro(page_data: dict[str, Any]) -> str:
    intro = page_data.get("intro") or {}
    eyebrow = text(intro.get("eyebrow"), "为什么选择 Frevana")
    title = text(intro.get("title"), "通过 AI 回答赢得更多客户")
    return f"""
    <section class="intro" aria-labelledby="solution-intro-title">
      <div class="container">
        <span class="eyebrow">{esc(eyebrow)}</span>
        <h2 id="solution-intro-title">{esc(title)}</h2>
      </div>
    </section>""".strip()


def render_features(page_data: dict[str, Any], image_manifest: dict[str, dict[str, Any]]) -> str:
    sections = page_data.get("sections") or []
    if not sections:
        return ""

    feature_html: list[str] = []
    for index, section in enumerate(sections[:4], start=1):
        title = text(section.get("title"), f"Feature {index}")
        slot = f"section-{index}"
        image_url, image_alt = image_for(section, slot, image_manifest, title)
        reverse_class = " feature--reverse" if index % 2 == 0 else ""
        cta_text = text(section.get("cta_text"))
        cta_html = ""
        if cta_text:
            cta_html = (
                f'<a class="button button--green" href="{esc(normalize_cta_url(section.get("cta_url")))}">'
                f'{esc(cta_text)} <span aria-hidden="true">→</span></a>'
            )
        feature_html.append(
            f"""
      <article class="feature{reverse_class}">
        <div class="feature__visual">
          <div class="visual-card">
            <img src="{esc(image_url)}" alt="{esc(image_alt)}">
          </div>
        </div>
        <div class="feature__copy">
          <span class="eyebrow">{esc(section.get("eyebrow"),)}</span>
          <h3>{esc(title)}</h3>
          <p>{esc(section.get("body"), "说明这个模块如何帮助客户在 AI 回答中获得更多曝光。")}</p>
          {cta_html}
        </div>
      </article>""".rstrip()
        )

    return f"""
    <section class="features" aria-label="Frevana solution features">
      <div class="container">
        {''.join(feature_html)}
      </div>
    </section>""".strip()


def module_tabs_data(
    page_data: dict[str, Any],
    image_manifest: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    module = page_data.get("module") or {}
    default_tabs = [
        {
            "label": "问题研究员",
            "title": "问题研究员",
            "body": "从真实用户问题中发现内容机会，识别最值得被 AI 回答引用的话题。",
        }
    ]
    tabs = module.get("tabs") if isinstance(module.get("tabs"), list) else default_tabs
    image_url, image_alt = image_for(module, "module", image_manifest, text(module.get("title"), "Frevana module visual"))
    normalized: list[dict[str, str]] = []
    for tab in tabs or default_tabs:
        normalized.append(
            {
                "label": text(tab.get("label"), text(tab.get("title"), "Module")),
                "title": text(tab.get("title"), text(tab.get("label"), "Module")),
                "body": text(tab.get("body"), "说明该模块如何帮助用户执行 AEO 增长工作。"),
                "image": text(tab.get("image_url"), image_url),
                "alt": text(tab.get("image_alt"), image_alt),
            }
        )
    return normalized


def render_module(page_data: dict[str, Any], image_manifest: dict[str, dict[str, Any]]) -> tuple[str, str]:
    module = page_data.get("module") or {}
    if module is None:
        return "", ""

    tabs = module_tabs_data(page_data, image_manifest)
    first = tabs[0]
    tab_buttons = "\n          ".join(
        f'<button class="module__tab" type="button" role="tab" aria-selected="{"true" if i == 0 else "false"}" data-tab-index="{i}">{esc(tab["label"])}</button>'
        for i, tab in enumerate(tabs)
    )
    tabs_json = json.dumps(tabs, ensure_ascii=False).replace("</", "<\\/")
    script = f"""
  <script>
    (() => {{
      const tabs = {tabs_json};
      const root = document.querySelector('[data-module-tabs]');
      if (!root || !tabs.length) return;
      const buttons = Array.from(root.querySelectorAll('[data-tab-index]'));
      const title = root.querySelector('[data-module-title]');
      const body = root.querySelector('[data-module-body]');
      const image = root.querySelector('[data-module-image]');
      const activate = (index) => {{
        const tab = tabs[index];
        if (!tab) return;
        buttons.forEach((button, buttonIndex) => {{
          button.setAttribute('aria-selected', String(buttonIndex === index));
        }});
        title.textContent = tab.title;
        body.textContent = tab.body;
        image.src = tab.image;
        image.alt = tab.alt;
      }};
      buttons.forEach((button) => {{
        button.addEventListener('click', () => activate(Number(button.dataset.tabIndex)));
      }});
    }})();
  </script>""".rstrip()

    html_block = f"""
    <section class="module" aria-labelledby="solution-module-title">
      <div class="container">
        <div class="module__head">
          <span class="eyebrow">{esc(module.get("eyebrow"), "您将获得")}</span>
          <h2 id="solution-module-title">{esc(module.get("title"), "助力您增长的 AEO 团队")}</h2>
        </div>
        <div class="module__panel" data-module-tabs>
          <div class="module__tabs" role="tablist" aria-label="Frevana modules">
          {tab_buttons}
          </div>
          <div class="module__content">
            <div class="module__copy">
              <h3 data-module-title>{esc(first["title"])}</h3>
              <p data-module-body>{esc(first["body"])}</p>
            </div>
            <div class="module__image">
              <img data-module-image src="{esc(first["image"])}" alt="{esc(first["alt"])}">
            </div>
          </div>
        </div>
      </div>
    </section>""".strip()
    return html_block, script


def render_final_cta(page_data: dict[str, Any]) -> str:
    final_cta = page_data.get("final_cta") or {}
    return f"""
    <section class="final-cta" aria-labelledby="final-cta-title">
      <div class="container">
        <div class="final-cta__card">
          <span class="eyebrow">{esc(final_cta.get("eyebrow"), "准备开始")}</span>
          <h2 id="final-cta-title">{esc(final_cta.get("title"), "准备好赢得 AI 流量了吗？")}</h2>
          <p>{esc(final_cta.get("body"), "用 Frevana 创建您的下一批 AI 可引用页面。")}</p>
          <a class="button button--green" href="{esc(normalize_cta_url(final_cta.get("cta_url")))}">{esc(final_cta.get("cta_text"), "立即开始")} <span aria-hidden="true">→</span></a>
        </div>
      </div>
    </section>""".strip()


def render_main(page_data: dict[str, Any], image_manifest: dict[str, dict[str, Any]]) -> tuple[str, str]:
    module_html, module_script = render_module(page_data, image_manifest)
    content = "\n".join(
        part
        for part in [
            '<main class="solution-page">',
            render_hero(page_data, image_manifest),
            render_intro(page_data),
            render_features(page_data, image_manifest),
            module_html,
            render_final_cta(page_data),
            "</main>",
        ]
        if part
    )
    return content, module_script


def render_page(
    page_data: dict[str, Any],
    image_manifest: dict[str, dict[str, Any]],
    *,
    body_only: bool = False,
) -> str:
    main_content, module_script = render_main(page_data, image_manifest)
    if body_only:
        return main_content + ("\n" + module_script if module_script else "") + "\n"

    template_path = SCRIPT_DIR.parent / "assets" / "template.html"
    template = template_path.read_text(encoding="utf-8")
    return template.format(
        language=esc(page_data.get("language"), "zh-CN"),
        page_title=esc(page_data.get("page_title"), "Frevana Solution Page"),
        meta_description=esc(page_data.get("meta_description"), "A Frevana-style solution landing page."),
        site_header=render_header(),
        main_content=main_content,
        site_footer=render_footer(),
        module_script=module_script,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a Frevana solution landing page.")
    parser.add_argument("--input", required=True, help="Page schema JSON file.")
    parser.add_argument("--output", required=True, help="HTML output path.")
    parser.add_argument("--body-only", action="store_true", help="Output only the middle page body.")
    parser.add_argument("--skip-images", action="store_true", help="Use placeholders instead of calling gpt-image-2.")
    parser.add_argument("--cache-dir", default="cache/images", help="Image cache directory.")
    parser.add_argument("--image-manifest", help="Optional path to write the image manifest JSON.")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    page_data = read_json(input_path)

    image_manifest: dict[str, dict[str, Any]] = {}
    if not args.skip_images:
        image_manifest = render_images.render_images_for_page(page_data, Path(args.cache_dir))
        manifest_path = Path(args.image_manifest) if args.image_manifest else output_path.with_suffix(".images.json")
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(image_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    html_output = render_page(page_data, image_manifest, body_only=args.body_only)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_output, encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except render_images.ImageGenerationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
