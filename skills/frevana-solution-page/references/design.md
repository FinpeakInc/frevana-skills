---
version: alpha
name: Frevana-solution-page-design
description: "A Frevana solution-page design system for AEO and AI visibility landing pages. The style anchors on a white canvas, deep charcoal typography, Frevana green CTAs, soft-green emphasis surfaces, Host Grotesk display headings, and Open Sans body text. The page pattern is website Header/Footer, left-copy/right-visual hero, alternating feature sections, tabbed AEO team module, and a final signup CTA. Images should combine realistic work scenes with clean SaaS dashboard UI and Frevana green accents."

colors:
  primary: "#3d9040"
  primary-active: "#2f7632"
  primary-soft: "#effdf4"
  primary-soft-strong: "#dff5e4"
  primary-border: "#cfe9d1"
  ink: "#111827"
  ink-soft: "#1f2937"
  body: "#4b5563"
  body-muted: "#6b7280"
  muted: "#9ca3af"
  hairline: "#e5e7eb"
  hairline-soft: "#eef0ed"
  canvas: "#ffffff"
  canvas-warm: "#fafbf8"
  surface-soft: "#f7faf6"
  surface-card: "#ffffff"
  surface-green-card: "#f3fbf5"
  surface-dark: "#202124"
  surface-dark-active: "#000000"
  on-primary: "#ffffff"
  on-dark: "#ffffff"
  success: "#3d9040"
  warning: "#d4a017"
  error: "#c64545"

typography:
  display-xl:
    fontFamily: "Host Grotesk, Open Sans, sans-serif"
    fontSize: 84px
    fontWeight: 800
    lineHeight: 0.98
    letterSpacing: "-0.075em"
  display-lg:
    fontFamily: "Host Grotesk, Open Sans, sans-serif"
    fontSize: 64px
    fontWeight: 800
    lineHeight: 1.04
    letterSpacing: "-0.065em"
  display-md:
    fontFamily: "Host Grotesk, Open Sans, sans-serif"
    fontSize: 50px
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.06em"
  display-sm:
    fontFamily: "Host Grotesk, Open Sans, sans-serif"
    fontSize: 36px
    fontWeight: 800
    lineHeight: 1.08
    letterSpacing: "-0.05em"
  title-lg:
    fontFamily: "Host Grotesk, Open Sans, sans-serif"
    fontSize: 28px
    fontWeight: 800
    lineHeight: 1.1
    letterSpacing: "-0.04em"
  title-md:
    fontFamily: "Open Sans, sans-serif"
    fontSize: 20px
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: 0
  title-sm:
    fontFamily: "Open Sans, sans-serif"
    fontSize: 16px
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: 0
  body-lg:
    fontFamily: "Open Sans, sans-serif"
    fontSize: 21px
    fontWeight: 400
    lineHeight: 1.7
    letterSpacing: 0
  body-md:
    fontFamily: "Open Sans, sans-serif"
    fontSize: 18px
    fontWeight: 400
    lineHeight: 1.65
    letterSpacing: 0
  body-sm:
    fontFamily: "Open Sans, sans-serif"
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: 0
  caption:
    fontFamily: "Open Sans, sans-serif"
    fontSize: 14px
    fontWeight: 700
    lineHeight: 1.4
    letterSpacing: 0
  nav-link:
    fontFamily: "Open Sans, sans-serif"
    fontSize: 17px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  button:
    fontFamily: "Open Sans, sans-serif"
    fontSize: 16px
    fontWeight: 800
    lineHeight: 1
    letterSpacing: 0

rounded:
  xs: 6px
  sm: 10px
  md: 13px
  lg: 22px
  xl: 34px
  xxl: 40px
  pill: 9999px
  full: 9999px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 48px
  xxxl: 64px
  section: 104px
  section-tight: 76px
  container-x: 40px
  container-x-mobile: 20px

layout:
  maxWidth: 1220px
  maxWidthRange: "1180px-1280px"
  desktopHeroGrid: "0.98fr 0.82fr"
  desktopFeatureGrid: "0.92fr 0.88fr"
  moduleGrid: "0.42fr 1fr"
  tabletBreakpoint: 1100px
  mobileBreakpoint: 760px

shadow:
  soft: "0 24px 80px rgba(17, 24, 39, 0.08)"
  card: "0 18px 48px rgba(17, 24, 39, 0.10)"
  cta: "0 18px 36px rgba(61, 144, 64, 0.24)"
  dark-cta: "0 18px 36px rgba(17, 24, 39, 0.18)"

components:
  top-nav:
    backgroundColor: "rgba(255, 255, 255, 0.92)"
    textColor: "{colors.body}"
    typography: "{typography.nav-link}"
    height: 82px
    borderBottom: "1px solid rgba(229, 231, 235, 0.9)"
    backdropFilter: "blur(18px)"
  brand-wordmark:
    textColor: "{colors.ink}"
    typography: "{typography.title-lg}"
    markBackground: "linear-gradient(135deg, #61b968, {colors.primary})"
  solutions-dropdown:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    mutedTextColor: "{colors.muted}"
    border: "1px solid {colors.hairline}"
    rounded: "{rounded.lg}"
    padding: "38px 48px"
    shadow: "{shadow.card}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: "0 24px"
    height: 54px
    shadow: "{shadow.cta}"
  button-primary-active:
    backgroundColor: "{colors.primary-active}"
    textColor: "{colors.on-primary}"
  button-dark:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.on-dark}"
    typography: "{typography.button}"
    rounded: "{rounded.md}"
    padding: "0 24px"
    height: 54px
    shadow: "{shadow.dark-cta}"
  eyebrow-pill:
    backgroundColor: "{colors.primary-soft}"
    textColor: "{colors.primary}"
    typography: "{typography.caption}"
    rounded: "{rounded.pill}"
    border: "1px solid {colors.primary-border}"
    padding: "0 14px"
    height: 36px
  hero-band:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.display-xl}"
    paddingBlock: "96px 110px"
    grid: "{layout.desktopHeroGrid}"
  hero-visual-card:
    backgroundColor: "{colors.surface-card}"
    border: "1px solid {colors.primary-border}"
    rounded: "{rounded.xl}"
    padding: 16px
    shadow: "{shadow.soft}"
  feature-section:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    grid: "{layout.desktopFeatureGrid}"
    gap: 76px
    paddingBlock: 66px
  module-panel:
    backgroundColor: "{colors.canvas}"
    border: "1px solid {colors.hairline}"
    rounded: "{rounded.xl}"
    padding: 18px
    shadow: "{shadow.soft}"
  module-tab-active:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.primary}"
    border: "1px solid {colors.primary-border}"
    shadow: "0 10px 24px rgba(17, 24, 39, 0.06)"
  final-cta-card:
    backgroundColor: "{colors.surface-green-card}"
    textColor: "{colors.ink}"
    border: "1px solid {colors.primary-border}"
    rounded: "{rounded.xxl}"
    padding: "74px 32px"
    shadow: "{shadow.soft}"
  footer:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.body}"
    typography: "{typography.body-sm}"
    borderTop: "1px solid {colors.hairline}"
    paddingBlock: "54px 44px"

links:
  home: "/zh-CN"
  signup: "/zh-CN/signup"
  login: "/zh-CN/login"
  caseStudy: "/zh-CN/case-study"
  docs: "https://frevana.gitbook.io/frevana-docs"
  articles: "/zh-CN/articles"
  pricing: "/zh-CN/homepage#pricing"
  news: "https://frevana.substack.com/"
  download: "/zh-CN/download"

image:
  providerSkill: "gpt-image-2"
  script: "../gpt-image-2/scripts/generate_image.sh"
  defaultSize: "1536x1024"
  defaultQuality: "high"
  defaultFormat: "png"
  cachePattern: "cache/images/<slot>-<hash>.json"
  slots:
    - hero
    - section-1
    - section-2
    - section-3
    - section-4
    - module
---

## Overview

Frevana solution pages are clean, spacious, and growth-oriented. The base canvas is pure white (`{colors.canvas}`), while Frevana green (`{colors.primary}`) carries conversion energy through CTAs, eyebrow pills, active module tabs, and subtle visual accents.

The signature contrast is **white canvas + deep charcoal text + green action accents**. Do not drift into purple AI gradients, generic blue SaaS dashboards, or dark-mode-first visuals. Large rounded visual cards and generous whitespace create the polished Frevana feel.

**Key Characteristics:**
- White page canvas with deep charcoal headings (`{colors.ink}`) and muted body copy (`{colors.body-muted}`).
- Frevana green (`{colors.primary}`) for signup CTAs, active tabs, UI accents, and high-confidence labels.
- Heavy Host Grotesk display typography with tight negative letter-spacing; Open Sans for body and UI labels.
- Website-level Header/Footer remain stable and are not rewritten from user copy.
- Hero uses left copy and right visual card; feature sections alternate image/text orientation.
- Imagery combines realistic work scenes with clean SaaS dashboards, not abstract AI art.

## Colors

### Brand & Accent

- **Frevana Green** (`{colors.primary}` — #3d9040): Primary action and identity color for signup CTAs, active tabs, selected states, and emphasis.
- **Frevana Green Active** (`{colors.primary-active}` — #2f7632): Hover/pressed state for green CTAs.
- **Soft Green** (`{colors.primary-soft}` — #effdf4): Eyebrow pills, gentle callouts, and background glows.
- **Green Border** (`{colors.primary-border}` — #cfe9d1): Low-contrast border for green-tinted cards and pills.

### Surface

- **Canvas** (`{colors.canvas}` — #ffffff): Default body background.
- **Warm Canvas** (`{colors.canvas-warm}` — #fafbf8): Module bands and subtle pacing backgrounds.
- **Surface Soft** (`{colors.surface-soft}` — #f7faf6): Tab containers and quiet product UI backgrounds.
- **Dark CTA** (`{colors.surface-dark}` — #202124): Hero primary button.

### Text

- **Ink** (`{colors.ink}` — #111827): H1/H2/H3, primary nav, and important labels.
- **Body** (`{colors.body}` — #4b5563): Navigation and UI labels.
- **Body Muted** (`{colors.body-muted}` — #6b7280): Paragraphs and supporting copy.
- **Muted** (`{colors.muted}` — #9ca3af): Dropdown group headings, captions, footer-adjacent text.

## Typography

The system uses **Host Grotesk** for display headings and **Open Sans** for body, navigation, buttons, and tabs.

| Token | Size | Weight | Line Height | Letter Spacing | Use |
|---|---:|---:|---:|---:|---|
| `{typography.display-xl}` | 84px | 800 | 0.98 | -0.075em | Hero H1 desktop |
| `{typography.display-lg}` | 64px | 800 | 1.04 | -0.065em | Section H2 / final CTA H2 |
| `{typography.display-md}` | 50px | 800 | 1.05 | -0.06em | Feature title |
| `{typography.display-sm}` | 36px | 800 | 1.08 | -0.05em | Module title |
| `{typography.body-lg}` | 21px | 400 | 1.7 | 0 | Hero and feature body |
| `{typography.nav-link}` | 17px | 600 | 1.4 | 0 | Top navigation |
| `{typography.button}` | 16px | 800 | 1 | 0 | CTA labels |

Mobile adjustments: Hero H1 42-48px, section H2 34-40px, feature titles 30-34px, body copy 16-18px.

## Layout

Use a centered `{layout.maxWidth}` container with generous whitespace. Desktop horizontal padding is `{spacing.container-x}`; mobile padding is `{spacing.container-x-mobile}`. Major sections use `{spacing.section}` vertical rhythm.

Hero pattern:

- Left copy column, right visual card.
- Eyebrow pill above headline.
- CTA below paragraph.

Feature pattern:

- Up to four alternating image/text rows.
- Green eyebrow, short title, muted body.
- Optional CTA defaults to `{links.signup}`.

Module pattern:

- Centered heading.
- Tab rail plus content card.
- Active tab uses green text, green border, and elevated white background.

## Components

### Header And Footer

Header and Footer are website-level components. Keep them stable unless the user explicitly requests `--body-only`.

Header links:

- Logo -> `{links.home}`
- Solutions dropdown
- Case study -> `{links.caseStudy}`
- Docs -> `{links.docs}`
- Articles -> `{links.articles}`
- Pricing -> `{links.pricing}`
- News -> `{links.news}`
- Login -> `{links.login}`
- Start free trial -> `{links.signup}`

Footer includes social links, Publications, Articles, Privacy, Pricing, Terms, About, stories, book demo, Discover, FAQ, MCPs, Download App, Download Extension, and copyright.

### Solutions Dropdown

The dropdown has two groups:

- **By business size:** Individual, Small teams, Companies
- **By industry:** E-Commerce, Technology, Local business

Hover/focus behavior is sufficient for single-file HTML.

### CTA Rules

- Default CTA URL is `{links.signup}`.
- If the user gives CTA text but no URL, keep `{links.signup}`.
- If the user gives a URL, preserve it exactly.
- Do not remove anchor behavior when changing copy.

## Image System

Images are generated with `gpt-image-2` through `{image.script}` and cached at `{image.cachePattern}`. The script requires `FREVANA_TOKEN` unless running with placeholders.

Image direction:

- Real founder, marketer, operator, or small team context.
- Laptop/desktop showing AEO, AI visibility, question research, or content workflow UI.
- White interface, deep gray typography, Frevana green highlights.
- Warm natural light and calm productivity mood.
- No fake logos, no abstract AI blobs, no purple gradients.

Slot guidance:

- `hero`: broad aspirational product value and outcome.
- `section-1`: user questions, search intelligence, topic demand.
- `section-2`: content creation, FAQ, landing page, article workflow.
- `section-3`: course, guidance, best practices, team learning.
- `section-4`: industry report, competitor ranking, benchmark dashboard.
- `module`: modular AI team or AEO dashboard experience.

## Responsiveness

Desktop uses two-column hero/features and a tabbed module panel. Tablet stacks major grids below `{layout.tabletBreakpoint}`. Mobile uses 20px padding, stacked columns, horizontally scrollable module tabs, and no horizontal overflow.

## Accessibility

Use semantic landmarks, real anchors for CTAs and navigation, visible focus states, meaningful alt text, and a selected-tab state that does not rely only on color.

## Body-Only Mode

`--body-only` omits the HTML shell, Header, and Footer. It keeps Hero, Intro, Features, Module tabs, Final CTA, and any JavaScript required for module tabs.

