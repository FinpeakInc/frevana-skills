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
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="16" stdDeviation="18" flood-color="#0f172a" flood-opacity="0.18"/>
    </filter>
  </defs>
  <rect width="1536" height="1024" fill="none"/>
  <path d="M176 204h286l-143 214z" fill="#72bf56" opacity="0.88"/>
  <path d="M884 94h398v300H884z" fill="#ff5b22" opacity="0.92" transform="rotate(8 1083 244)"/>
  <path d="M1018 674c155-70 285-50 390 64v184h-390z" fill="#54bdb8"/>
  <circle cx="1120" cy="250" r="158" fill="none" stroke="#5da1ed" stroke-width="34"/>
  <g filter="url(#shadow)">
    <rect x="138" y="312" width="1260" height="188" rx="38" fill="#ffffff" stroke="#111827" stroke-width="5"/>
    <text x="222" y="432" fill="#111827" font-family="Open Sans, sans-serif" font-size="58" font-weight="800">{safe_label}</text>
    <rect x="1270" y="357" width="78" height="78" rx="18" fill="#111827"/>
    <path d="M1309 411V374m0 0l-18 19m18-19l18 19" stroke="#fff" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <g filter="url(#shadow)">
    <rect x="360" y="560" width="410" height="112" rx="30" fill="#ffffff" stroke="#111827" stroke-width="4"/>
    <text x="412" y="630" fill="#111827" font-family="Open Sans, sans-serif" font-size="34" font-weight="800">AI Visibility</text>
  </g>
  <g filter="url(#shadow)">
    <rect x="848" y="612" width="430" height="152" rx="32" fill="#ffffff" stroke="#111827" stroke-width="4"/>
    <circle cx="918" cy="688" r="26" fill="#3d9040"/>
    <path d="M906 688l11 12 24-31" fill="none" stroke="#fff" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/>
    <text x="970" y="698" fill="#111827" font-family="Open Sans, sans-serif" font-size="34" font-weight="800">Answer-ready</text>
  </g>
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
  <header class="site-header main-header" aria-label="Frevana site header">
    <div class="site-header__frame">
      <div class="site-header__inner">
        <a class="site-logo" href="/zh-CN" aria-label="Frevana home">
          <img src="https://www.frevana.com/common/logo.png" alt="Frevana" width="45" height="45">
        </a>

        <nav class="desktop-nav" aria-label="Primary navigation">
          <div class="nav-dropdown">
            <button class="nav-link nav-dropdown__trigger" type="button" aria-haspopup="true" aria-expanded="false">Solutions</button>
            <div class="nav-dropdown__panel nav-dropdown__panel--solutions" role="menu" aria-label="Solutions menu">
              <div class="solutions-grid">
                <div>
                  <h3 class="dropdown-heading">By business size</h3>
                  <div class="dropdown-list">
                    <a class="dropdown-item" href="/zh-CN/individual" role="menuitem">
                      <img src="https://www.frevana.com/solutions/icon_person_1.svg" alt="" width="20" height="20">
                      <span><strong>Individual</strong><small>For solopreneur and professionals</small></span>
                    </a>
                    <a class="dropdown-item" href="/zh-CN/small-teams" role="menuitem">
                      <img src="https://www.frevana.com/solutions/icon_person_2.svg" alt="" width="20" height="20">
                      <span><strong>Small teams</strong><small>For growing businesses</small></span>
                    </a>
                    <a class="dropdown-item" href="/zh-CN/companies" role="menuitem">
                      <img src="https://www.frevana.com/solutions/icon_person_3.svg" alt="" width="20" height="20">
                      <span><strong>Companies</strong><small>For larger teams</small></span>
                    </a>
                  </div>
                </div>
                <div>
                  <h3 class="dropdown-heading">By industry</h3>
                  <div class="dropdown-list dropdown-list--compact">
                    <a class="dropdown-item" href="/zh-CN/e-commerce" role="menuitem">
                      <img src="https://www.frevana.com/solutions/icon_shopping_outline.svg" alt="" width="20" height="20">
                      <span><strong>E-Commerce</strong></span>
                    </a>
                    <a class="dropdown-item" href="/zh-CN/technology" role="menuitem">
                      <img src="https://www.frevana.com/solutions/icon_computer.svg" alt="" width="20" height="20">
                      <span><strong>Technology</strong></span>
                    </a>
                    <a class="dropdown-item" href="/zh-CN/local-business" role="menuitem">
                      <img src="https://www.frevana.com/solutions/icon_shop.svg" alt="" width="20" height="20">
                      <span><strong>Local business</strong></span>
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="nav-dropdown">
            <button class="nav-link nav-dropdown__trigger" type="button" aria-haspopup="true" aria-expanded="false">Case study</button>
            <div class="nav-dropdown__panel nav-dropdown__panel--case" role="menu" aria-label="Case studies menu">
              <a class="case-link" href="https://www.frevana.com/articles/2025/10/30/from-zero-to-one-and-to-infinity-how-frevana-helps-a-startup-break-the-ice-into-ai-search/" role="menuitem">How empathia.ai achieved 4x organic traffic growth</a>
              <a class="case-link" href="https://www.frevana.com/articles/2025/10/30/how-a-fitness-equipment-brand-increases-their-ai-visibility-by-54-in-one-week-with-frevana/" role="menuitem">How a fitness brand achieved a 54% surge in AI visibility</a>
              <a class="case-link" href="https://www.frevana.com/articles/2026/01/07/lockin-increased-ai-visibility-266-in-one-month-with-frevana/" role="menuitem">Lockin Increased AI Visibility 266% in One Month</a>
            </div>
          </div>

          <a class="nav-link" href="https://frevana.gitbook.io/frevana-docs" target="_blank" rel="noopener noreferrer">Docs</a>
          <a class="nav-link" href="https://www.frevana.com/articles">Articles</a>
          <a class="nav-link" href="/zh-CN/homepage#pricing">Pricing</a>
          <a class="nav-link" href="https://frevana.substack.com/" target="_blank" rel="noopener noreferrer">News</a>
        </nav>

        <div class="site-header__actions">
          <a class="header-login" href="/zh-CN/login">Login</a>
          <a class="header-trial" href="/zh-CN/signup" data-track="landing_header_cta_click" data-track-section="header">Start free trial</a>
          <span class="header-language" aria-label="Current language">中文</span>
          <button class="mobile-menu-button" type="button" aria-label="Open navigation" aria-controls="mobile-drawer" aria-expanded="false" data-drawer-open>
            <span></span><span></span><span></span>
          </button>
        </div>
      </div>
    </div>

    <div class="mobile-drawer-backdrop" data-drawer-close></div>
    <aside class="mobile-drawer" id="mobile-drawer" aria-label="Mobile navigation" aria-hidden="true">
      <div class="mobile-drawer__title">
        <a class="site-logo" href="/zh-CN" aria-label="Frevana home">
          <img src="https://www.frevana.com/common/logo.png" alt="Frevana" width="45" height="45">
        </a>
        <span class="header-language">中文</span>
      </div>
      <nav class="mobile-nav" aria-label="Mobile primary navigation">
        <button class="mobile-nav__toggle" type="button" data-mobile-toggle="solutions">Solutions <span aria-hidden="true">⌄</span></button>
        <div class="mobile-nav__panel" data-mobile-panel="solutions">
          <h4>By business size</h4>
          <a href="/zh-CN/individual"><img src="https://www.frevana.com/solutions/icon_person_1.svg" alt="" width="16" height="16"><span><strong>Individual</strong><small>For solopreneur and professionals</small></span></a>
          <a href="/zh-CN/small-teams"><img src="https://www.frevana.com/solutions/icon_person_2.svg" alt="" width="16" height="16"><span><strong>Small teams</strong><small>For growing businesses</small></span></a>
          <a href="/zh-CN/companies"><img src="https://www.frevana.com/solutions/icon_person_3.svg" alt="" width="16" height="16"><span><strong>Companies</strong><small>For larger teams</small></span></a>
          <h4>By industry</h4>
          <a href="/zh-CN/e-commerce"><img src="https://www.frevana.com/solutions/icon_shopping_outline.svg" alt="" width="16" height="16"><strong>E-Commerce</strong></a>
          <a href="/zh-CN/technology"><img src="https://www.frevana.com/solutions/icon_computer.svg" alt="" width="16" height="16"><strong>Technology</strong></a>
          <a href="/zh-CN/local-business"><img src="https://www.frevana.com/solutions/icon_shop.svg" alt="" width="16" height="16"><strong>Local business</strong></a>
        </div>

        <button class="mobile-nav__toggle" type="button" data-mobile-toggle="case-study">Case study <span aria-hidden="true">⌄</span></button>
        <div class="mobile-nav__panel" data-mobile-panel="case-study">
          <a href="https://www.frevana.com/articles/2025/10/30/from-zero-to-one-and-to-infinity-how-frevana-helps-a-startup-break-the-ice-into-ai-search/"><strong>How empathia.ai achieved 4x organic traffic growth</strong></a>
          <a href="https://www.frevana.com/articles/2025/10/30/how-a-fitness-equipment-brand-increases-their-ai-visibility-by-54-in-one-week-with-frevana/"><strong>How a fitness brand achieved a 54% surge in AI visibility</strong></a>
          <a href="https://www.frevana.com/articles/2026/01/07/lockin-increased-ai-visibility-266-in-one-month-with-frevana/"><strong>Lockin Increased AI Visibility 266% in One Month</strong></a>
        </div>

        <a class="mobile-nav__link" href="https://frevana.gitbook.io/frevana-docs" target="_blank" rel="noopener noreferrer">Docs</a>
        <a class="mobile-nav__link" href="https://www.frevana.com/articles">Articles</a>
        <a class="mobile-nav__link" href="/zh-CN/homepage#pricing">Pricing</a>
        <a class="mobile-nav__link" href="https://frevana.substack.com/" target="_blank" rel="noopener noreferrer">News</a>
      </nav>
    </aside>

    <script>
      (() => {
        const header = document.querySelector('.site-header');
        if (!header) return;
        const openButton = header.querySelector('[data-drawer-open]');
        const drawer = header.querySelector('.mobile-drawer');
        const backdrop = header.querySelector('.mobile-drawer-backdrop');
        const closeDrawer = () => {
          header.classList.remove('is-drawer-open');
          drawer?.setAttribute('aria-hidden', 'true');
          openButton?.setAttribute('aria-expanded', 'false');
        };
        openButton?.addEventListener('click', () => {
          const isOpen = header.classList.toggle('is-drawer-open');
          drawer?.setAttribute('aria-hidden', String(!isOpen));
          openButton.setAttribute('aria-expanded', String(isOpen));
        });
        backdrop?.addEventListener('click', closeDrawer);
        header.querySelectorAll('.mobile-nav a').forEach((link) => link.addEventListener('click', closeDrawer));
        header.querySelectorAll('[data-mobile-toggle]').forEach((button) => {
          button.addEventListener('click', () => {
            const key = button.getAttribute('data-mobile-toggle');
            const panel = header.querySelector(`[data-mobile-panel="${key}"]`);
            const isOpen = button.classList.toggle('is-open');
            if (panel) panel.classList.toggle('is-open', isOpen);
          });
        });
      })();
    </script>
  </header>""".strip()


def render_footer() -> str:
    footer_links = [
        ("Publications", "/zh-CN/publications", False),
        ("Articles", "/zh-CN/articles", False),
        ("Privacy Policy", "/zh-CN/privacy", False),
        ("Pricing", "/zh-CN/homepage#pricing", False),
        ("Terms of Use", "/zh-CN/terms", False),
        ("About Us", "/zh-CN/about", False),
        ("Story: 4x organic traffic", "https://www.frevana.com/articles/2025/10/30/from-zero-to-one-and-to-infinity-how-frevana-helps-a-startup-break-the-ice-into-ai-search/", True),
        ("Story: 54% surge in AI visibility", "https://www.frevana.com/articles/2025/10/30/how-a-fitness-equipment-brand-increases-their-ai-visibility-by-54-in-one-week-with-frevana/", True),
        ("Request a demo", "https://calendly.com/leoliu6/frevana", True),
        ("Discover New Posts", "/zh-CN/discover", False),
        ("FAQ", "https://www.frevana.com/content/frevana-faq---answer-engine-optimization-for-modern-brands-wi8bz7gqn4y19", True),
        ("MCPs", "/zh-CN/mcp", False),
        ("Download App", "#download-app", False),
        ("Chrome Extension", "https://chromewebstore.google.com/detail/frevana-companion/gcicgnlafllbfmpakdaokdmplgpgphib?authuser=0&hl=en", True),
    ]
    rendered_links = []
    for label, url, external in footer_links:
        attrs = ' target="_blank" rel="noopener noreferrer"' if external else ''
        if label == "Download App":
            attrs += ' data-download-app data-track="landing_footer_download_click" data-track-section="footer"'
        rendered_links.append(f'<a href="{esc(url)}" class="footer-link"{attrs}>{esc(label)}</a>')
    link_html = "\n            ".join(rendered_links)
    return f"""
  <footer class="site-footer" aria-label="Frevana footer">
    <div class="site-footer__inner">
      <div class="site-footer__grid">
        <div class="site-footer__brand">
          <a class="footer-logo" href="/zh-CN" aria-label="Frevana home">
            <img src="https://www.frevana.com/common/logo.png" alt="Frevana Logo" width="172" height="38">
          </a>
          <p>Frevana helps teams improve AI visibility, understand what customers ask, and create answer-ready content for modern search.</p>
          <div class="social-links" aria-label="Social links">
            <a href="https://x.com/frevana_ai" target="_blank" rel="noopener noreferrer" aria-label="Twitter"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" /></svg></a>
            <a href="https://www.instagram.com/frevana.ai/" target="_blank" rel="noopener noreferrer" aria-label="Instagram"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838c-3.403 0-6.162 2.759-6.162 6.162S8.597 18.163 12 18.163s6.162-2.759 6.162-6.163c0-3.403-2.759-6.162-6.162-6.162zm0 10.162c-2.209 0-4-1.79-4-4 0-2.209 1.791-4 4-4s4 1.791 4 4c0 2.21-1.791 4-4 4zm6.406-11.845c-.796 0-1.441.645-1.441 1.44s.645 1.44 1.441 1.44c.795 0 1.439-.645 1.439-1.44s-.644-1.44-1.439-1.44z" /></svg></a>
            <a href="https://www.linkedin.com/company/frevana/" target="_blank" rel="noopener noreferrer" aria-label="LinkedIn"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" /></svg></a>
            <a href="https://www.youtube.com/@FrevanaAI" target="_blank" rel="noopener noreferrer" aria-label="YouTube"><svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" /></svg></a>
          </div>
        </div>
        <nav class="footer-links" aria-label="Footer navigation">
            {link_html}
        </nav>
      </div>
      <div class="site-footer__bottom">
        <p>© 2026 Frevana. All rights reserved.</p>
      </div>
    </div>
    <script>
      (() => {{
        const mac = 'https://static.frevana.com/app-updates/darwin/universal/Frevana.dmg';
        const win = 'https://apps.microsoft.com/store/detail/XP9CNTV2TLDXHG';
        document.querySelectorAll('[data-download-app]').forEach((link) => {{
          link.addEventListener('click', (event) => {{
            event.preventDefault();
            if (navigator.userAgent.toLowerCase().includes('win')) {{
              window.open(win, '_blank', 'noopener,noreferrer');
              return;
            }}
            const anchor = document.createElement('a');
            anchor.href = mac;
            anchor.download = 'Frevana.dmg';
            anchor.rel = 'noopener noreferrer';
            document.body.appendChild(anchor);
            anchor.click();
            document.body.removeChild(anchor);
          }});
        }});
      }})();
    </script>
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
          <a class="button" href="{esc(normalize_cta_url(hero.get("cta_url")))}" data-track="landing_hero_cta_click" data-track-section="hero">{esc(hero.get("cta_text"), "立即开始")} <span aria-hidden="true">→</span></a>
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
    for index, section in enumerate(sections, start=1):
        title = text(section.get("title"), f"Feature {index}")
        slot = f"section-{index}"
        image_url, image_alt = image_for(section, slot, image_manifest, title)
        reverse_class = " feature--reverse" if index % 2 == 0 else ""
        cta_text = text(section.get("cta_text"))
        cta_html = ""
        if cta_text:
            cta_html = (
                f'<a class="text-link-arrow" href="{esc(normalize_cta_url(section.get("cta_url")))}" '
                f'data-track="landing_feature_cta_click" data-track-section="section-{index}">'
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
            "label": "科学家",
            "title": "科学家",
            "body": "分析市场、AI 回答和行业信号，帮您找到更高价值的增长方向。",
        },
        {
            "label": "域名分析",
            "title": "域名分析",
            "body": "诊断您的网站在 AI 搜索和答案引擎中的可见度基础。",
        },
        {
            "label": "AEO 使用场景",
            "title": "AEO 使用场景",
            "body": "把客户真实问题转化为可执行的 AEO 内容和页面机会。",
        },
        {
            "label": "FAQ 板块",
            "title": "FAQ 板块",
            "body": "生成清晰、结构化、容易被 AI 引用的问答内容。",
        },
        {
            "label": "着陆页",
            "title": "着陆页写手",
            "body": "生成适合 AI 引用的服务页面，增强搜索和转化表现。",
        },
        {
            "label": "AEO 文章写手",
            "title": "AEO 文章写手",
            "body": "将产品链接和关键词转化为清晰、优化的博客草稿，吸引受众与 AI 引用。",
        },
        {
            "label": "AEO 内容顾问",
            "title": "AEO 内容顾问",
            "body": "规划内容策略、补齐主题缺口，并持续提升 AI 可见度。",
        },
        {
            "label": "AEO Reddit 内容写手",
            "title": "AEO Reddit 内容写手",
            "body": "面向真实社区讨论生成自然、可信的内容切入点。",
        },
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
            <div class="module__image">
              <img data-module-image src="{esc(first["image"])}" alt="{esc(first["alt"])}">
            </div>
            <div class="module__copy">
              <h3 data-module-title>{esc(first["title"])}</h3>
              <p data-module-body>{esc(first["body"])}</p>
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
          <a class="button" href="{esc(normalize_cta_url(final_cta.get("cta_url")))}" data-track="landing_final_cta_click" data-track-section="final_cta">{esc(final_cta.get("cta_text"), "立即开始")} <span aria-hidden="true">→</span></a>
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
