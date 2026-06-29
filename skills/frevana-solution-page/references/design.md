---
version: alpha
name: Frevana-individual-landing-design-analysis
description: A clean SaaS landing page that trades loud gradients for a neutral editorial shell — bright white canvas, near-black CTAs, soft green proof chips, oversized Host Grotesk headlines, and alternating product-illustration feature rows.

colors:
  canvas: "#ffffff"
  ink: "#111827"
  ink-hero: "#1C1F25"
  ink-body: "#565656"
  ink-muted: "#717171"
  ink-subtle: "#6B7280"
  ink-disabled: "#9CA3AF"
  border-soft: "#EDEEF1"
  border-ui: "#D1D5DB"
  surface-success: "#EFFDF4"
  success: "#3D9040"
  cta: "#212121"
  footer: "#283137"
  footer-border: "#3a4149"
  footer-muted: "#b0b0b0"
  white: "#ffffff"

typography:
  display-xl:
    fontFamily: "Host Grotesk, Inter, system-ui, sans-serif"
    fontSize: 58px
    fontWeight: 800
    lineHeight: 77px
    letterSpacing: 0
  display-lg:
    fontFamily: "Host Grotesk, Inter, system-ui, sans-serif"
    fontSize: 48px
    fontWeight: 600
    lineHeight: 64px
    letterSpacing: 0
  display-mobile:
    fontFamily: "Host Grotesk, Inter, system-ui, sans-serif"
    fontSize: 28px
    fontWeight: 800
    lineHeight: 36px
    letterSpacing: 0
  section-title:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: 24px
    fontWeight: 700
    lineHeight: 1.35
    letterSpacing: 0
  body-lg:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: 20px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: 0
  body-md:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 400
    lineHeight: 1.6
    letterSpacing: 0
  nav:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: 15px
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: 0
  eyebrow:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: 20px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  eyebrow-mobile:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: 14px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  button-lg:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: 18px
    fontWeight: 700
    lineHeight: 1
    letterSpacing: 0
  button-md:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 700
    lineHeight: 1
    letterSpacing: 0
  tab:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: 16px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0
  link-cta:
    fontFamily: "Open Sans, system-ui, sans-serif"
    fontSize: 20px
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: 0

rounded:
  xs: 4px
  sm: 6px
  md: 12px
  pill: 9999px

spacing:
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  xxl: 40px
  section: 96px
  section-lg: 150px
  container-pad: 40px
  hero-top: 103px
  feature-gap: 60px
  feature-gap-xl: 110px
  footer-max: 1320px

components:
  header-bar:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink-body}"
    borderBottom: "1px solid {colors.border-soft}"
    layout: "fixed top navigation"
    height: "58px mobile / 70px desktop"
  hero-split:
    backgroundColor: "{colors.canvas}"
    titleColor: "{colors.ink-hero}"
    bodyColor: "{colors.ink-muted}"
    layout: "2-column split"
    gap: "{spacing.feature-gap} to {spacing.feature-gap-xl}"
  success-chip:
    backgroundColor: "{colors.surface-success}"
    textColor: "{colors.success}"
    typography: "{typography.eyebrow}"
    rounded: "{rounded.pill}"
    padding: "8px 24px"
  primary-button:
    backgroundColor: "{colors.cta}"
    textColor: "{colors.white}"
    typography: "{typography.button-lg}"
    rounded: "{rounded.sm}"
    height: "56px desktop / 48px mobile"
    padding: "0 24px"
  feature-row:
    backgroundColor: "{colors.canvas}"
    titleColor: "{colors.ink}"
    bodyColor: "{colors.ink}"
    layout: "alternating text + product illustration"
    gap: "{spacing.feature-gap} to {spacing.feature-gap-xl}"
  tab-strip:
    backgroundColor: "{colors.canvas}"
    activeColor: "{colors.ink}"
    inactiveColor: "{colors.ink-disabled}"
    typography: "{typography.tab}"
    activeBorder: "2px solid {colors.ink}"
  footer-band:
    backgroundColor: "{colors.footer}"
    textColor: "{colors.white}"
    mutedColor: "{colors.footer-muted}"
    borderTop: "1px solid {colors.footer-border}"
---

## Overview

This page presents Frevana for individuals through a **clean, neutral SaaS landing-page system** that avoids bright startup gradients and instead leans on restraint: a white `{colors.canvas}` background, near-black typography, one dark charcoal CTA, and soft green utility chips that signal momentum without taking over the page. The impression is polished, calm, and conversion-minded rather than playful or highly branded.

The visual identity is carried mostly by **scale and spacing**. Large `{typography.display-xl}` Host Grotesk headlines do the heavy lifting, while Open Sans handles navigation, body copy, chips, tabs, and buttons. Illustrations are treated as roomy side-by-side companions to the copy, not as decorative backgrounds, so the page reads like a sequence of product proof modules rather than a glossy campaign microsite.

There are three recurring stylistic moves: **dark CTA surfaces**, **green success labeling**, and **alternating split-layout feature rows**. Each section repeats the same structure with different content, which gives the page a modular, systemized rhythm.

**Key Characteristics:**

- White `{colors.canvas}` page shell with deep neutral text instead of a saturated brand wash
- Oversized Host Grotesk headlines paired with pragmatic Open Sans body copy
- Green `{colors.success}` used as a supporting success/insight accent, not as the main CTA fill
- Fixed white header, flat content sections, and a dark footer slab for visual closure
- Repeating 50/50 feature rows with generous gaps and product illustrations
- Minimal depth; hierarchy comes from typography, spacing, and color contrast more than shadow

## Colors

### Core Palette

- **Canvas** (`{colors.canvas}` — #ffffff): the dominant page background and the base for almost every section.
- **Ink** (`{colors.ink}` — #111827): primary dark neutral used for section headings, feature titles, and most body-adjacent content.
- **Hero Ink** (`{colors.ink-hero}` — #1C1F25): slightly deeper hero-title tone that sharpens the opening message.
- **Body Neutral** (`{colors.ink-body}` — #565656): navigation and supporting neutral copy.
- **Muted Body** (`{colors.ink-muted}` — #717171): softer explanatory paragraph tone in the hero.
- **Subtle Neutral** (`{colors.ink-subtle}` — #6B7280): secondary utility state such as hamburger lines and some subdued text.
- **Disabled / Inactive** (`{colors.ink-disabled}` — #9CA3AF): inactive tab labels and low-emphasis utility states.

### Accent & Utility

- **Success Surface** (`{colors.surface-success}` — #EFFDF4): pale green fill behind section chips and proof labels.
- **Success Text** (`{colors.success}` — #3D9040): the page’s main accent. Used for chips, inline CTA text, and arrow icons.
- **Primary CTA** (`{colors.cta}` — #212121): dark charcoal used for the strongest call-to-action fills.

### Structural Surfaces

- **Soft Border** (`{colors.border-soft}` — #EDEEF1): thin page-shell divider on the fixed header.
- **UI Border** (`{colors.border-ui}` — #D1D5DB): form/select border styling in the header utility controls.
- **Footer Surface** (`{colors.footer}` — #283137): deep slate footer block that anchors the page ending.
- **Footer Border** (`{colors.footer-border}` — #3a4149): muted divider line separating the footer from the page body.
- **Footer Muted Text** (`{colors.footer-muted}` — #b0b0b0): secondary footer copy and link color.

### Color Principles

This is a **neutral-first palette**. The design does not try to win attention through multiple brand colors. Instead, it keeps almost everything white, charcoal, or gray, then uses green sparingly to imply growth, relevance, and “AI visibility” success. The darker CTA color reinforces seriousness and trust more than excitement.

## Typography

### Font Roles

The page uses a simple two-layer type identity in practice:

- **Host Grotesk** for major headlines and high-salience section titles
- **Open Sans** for navigation, labels, body copy, tabs, and buttons

Several other fonts are globally loaded in the CSS bundle (`League Spartan`, `Inter`), but the visible page language is driven primarily by Host Grotesk + Open Sans.

### Hierarchy

| Token | Size | Weight | Line Height | Use |
|---|---|---|---|---|
| `{typography.display-xl}` | 58px | 800 | 77px | Main desktop hero and major section headlines |
| `{typography.display-lg}` | 48px | 600 | 64px | Closing CTA headline |
| `{typography.display-mobile}` | 28px | 800 | 36px | Mobile hero and section headlines |
| `{typography.section-title}` | 24px | 700 | 1.35 | Feature-card headings and detail headers |
| `{typography.body-lg}` | 20px | 400 | 1.6 | Desktop body text, chips, link-like CTAs |
| `{typography.body-md}` | 16px | 400 | 1.6 | Mobile body text and compact button text |
| `{typography.nav}` | 15px | 400 | 1.4 | Top navigation links |
| `{typography.tab}` | 16px | 600 | 1.4 | Team-strip tabs |
| `{typography.button-lg}` | 18px | 700 | 1 | Primary desktop buttons |
| `{typography.eyebrow}` | 20px | 600 | 1.4 | Desktop section chips |
| `{typography.eyebrow-mobile}` | 14px | 600 | 1.4 | Mobile section chips |

### Typography Principles

The system combines **assertive display scale** with **plainspoken UI typography**. Headlines are large, dense, and geometric; paragraphs stay readable and practical rather than editorial. There is very little decorative type treatment — no italic flourishes, no ultra-tight tracking experiments, and almost no color-based hierarchy inside paragraphs. The typography is there to make the promise clear, fast, and credible.

## Layout

### Overall Structure

The page follows a classic product-marketing flow:

1. **Fixed utility header** with logo, nav, language select, and mobile menu trigger
2. **Hero split** with large copy on one side and an illustration on the other
3. **Why Frevana** feature sequence using alternating two-column modules
4. **Team / capabilities strip** with horizontal tabs and one active detail panel
5. **Final CTA block** centered in a narrower container
6. **Dark footer** with brand, social links, and navigation lists

### Grid & Container Behavior

- Main content sits inside a broad `max-w-7xl` shell with `{spacing.container-pad}` horizontal padding on desktop.
- Most hero and feature rows use a **50/50 two-column split**.
- Desktop feature gaps sit around `{spacing.feature-gap}` and widen toward `{spacing.feature-gap-xl}` on larger screens.
- The closing CTA compresses into a narrower centered container (`max-w-[852px]`) to create a focused conversion endpoint.
- The footer expands to a wider `{spacing.footer-max}` max width and uses a more information-dense column structure.

### Spacing Rhythm

- Common in-section values: 8, 12, 16, 24, 32, and 40px
- Large sectional cadence: 96, 135, 150, 220, and 235px
- Hero top spacing is notably generous at about `{spacing.hero-top}` on desktop
- Buttons hold clear vertical standards: 56px desktop and 48px mobile
- Section labels and tabs use compact spacing so the larger page rhythm can stay airy

The design feels spacious because it **creates contrast between compact controls and large inter-section whitespace**.

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| Flat | White background, no visible shadow | Most page sections |
| Rule-defined | Thin gray dividers | Header and footer separation |
| Contrast block | Dark footer surface | Page ending and brand anchor |
| Accent-only | Pale green fill without shadow | Eyebrow / success chips |
| Motion depth | Fade-up and arrow rotation transitions | Section entrance and inline CTA feedback |

This page is mostly **flat and frictionless**. It does not rely on card shadows, glassmorphism, gradients, or dramatic overlays. Depth comes from section spacing, fixed-header layering, and the stark contrast between the white body and the slate footer.

## Shapes

### Radius Scale

| Token | Value | Use |
|---|---|---|
| `{rounded.xs}` | 4px | Minor icon-line rounding and small utility details |
| `{rounded.sm}` | 6px | Primary CTA buttons and standard control corners |
| `{rounded.md}` | 12px | Hero badge, secondary CTA button, and compact panels |
| `{rounded.pill}` | 9999px | Success chips and rounded status labels |

### Geometry Notes

The geometry is soft but disciplined. The page avoids playful blobs and oversized card curvature. Most surfaces stay rectangular; rounding appears mainly on buttons, pills, and utility controls. Full-pill shapes are reserved for labels, while CTA buttons use a friendlier medium radius rather than a fully rounded capsule.

## Components

### `header-bar`

A fixed white navigation bar with a light bottom rule, muted gray link text, and a compact control cluster on the right. On desktop it exposes nav links and a language selector; on mobile it collapses into a minimalist hamburger icon.

### `hero-split`

A two-column hero with oversized `{typography.display-xl}` headline text, muted supporting copy, a hidden-on-mobile green proof chip, and a dark primary button. The illustration sits as a product-adjacent object rather than a decorative background, which keeps the hero practical and product-led.

### `success-chip`

Pale green pill or rounded badge using `{colors.surface-success}` and `{colors.success}`. This pattern appears repeatedly to label sections and reinforce growth-oriented messaging without becoming the dominant CTA language.

### `primary-button`

Dark charcoal filled button with white text, compact radius, bold weight, and generous height. It is the clearest conversion affordance on the page and intentionally stronger than the green accent links.

### `feature-row`

A modular split section pairing one illustration with one copy block. Each row includes a chip, title, supporting paragraph, and a green inline text CTA with arrow icon. Rows alternate orientation to keep the page from feeling repetitive.

### `text-link-arrow`

A green inline CTA styled more like emphasized text than a filled button. The attached arrow icon rotates on hover, which adds motion without making the page feel animated for animation’s sake.

### `tab-strip`

A horizontally scrollable set of capability labels in the “AEO team” section. The active item turns dark with a 2px bottom border; inactive items sit in muted gray. A desktop-only white gradient mask on the right hints that the strip continues beyond the visible area.

### `footer-band`

A dark slate footer with white brand elements, muted gray support text, social icons, and link columns. It functions as the page’s only major high-contrast slab and gives the overall composition a firm ending.

## Do's and Don'ts

### Do

- Keep the page predominantly white and neutral, with green used as a supporting signal rather than a primary fill color.
- Use oversized Host Grotesk headlines to create authority and immediate scannability.
- Preserve the repeating text-plus-illustration module structure with large horizontal gaps.
- Keep CTA hierarchy clear: dark filled buttons first, green inline links second.
- Maintain generous sectional whitespace so the layout feels calm and premium.
- Use pill-like chips to frame benefits, section labels, and progress cues.

### Don't

- Don’t introduce bright gradients, noisy color blocks, or multi-accent rainbow marketing styling.
- Don’t replace the dark CTA with a green fill everywhere; green is a support accent here, not the dominant action surface.
- Don’t turn every section into a bordered or shadowed card; the page reads best as clean stacked bands.
- Don’t overcomplicate body copy with multiple font families or decorative display treatments.
- Don’t shrink the headline scale too aggressively; the page’s confidence depends on large typographic contrast.

## Responsive Behavior

### Breakpoints

| Context | Key Changes |
|---|---|
| Desktop (`md` and up) | Fixed full header, visible nav, 2-column hero, alternating split feature rows, 58px display headlines, 20px body copy |
| Mobile (below `md`) | Navigation collapses to hamburger, hero and feature rows stack vertically, headline scale drops to 28px, body copy drops to 16px |
| Narrow mobile | Buttons stretch fuller width, chips shrink to `{typography.eyebrow-mobile}`, padding reduces, and vertical spacing becomes more compact |

### Behavior Notes

- The hero uses `flex-col-reverse` on mobile, so imagery and copy are re-stacked for a tighter small-screen composition.
- The desktop proof chip in the hero is hidden on smaller screens to reduce clutter.
- Feature sections collapse from side-by-side modules into single-column sequences while preserving generous internal spacing.
- The capability tab strip becomes horizontally scrollable rather than wrapping into a dense multi-row control.
- The final CTA remains centered and simplified, preserving conversion focus even as padding reduces from about 150px to 96px.

## Known Gaps

- The extracted guide is based on the server-rendered page HTML and linked CSS; hidden drawer states, dropdown-open states, and deeper interactive variants are only partially visible.
- The global CSS bundle loads multiple font families, but the visible page identity mainly exercises Host Grotesk and Open Sans; other loaded fonts may belong to broader site usage.
- The generic component system includes broader focus, invalid, and dark-theme tokens, but this specific page is authored overwhelmingly as a light-theme landing experience.
- Motion behavior is inferred from class-based transitions and hover states rather than from a full runtime interaction recording.

## Skill-Specific Additions

These additions are for the `frevana-solution-page` skill runtime. They do not replace the design tokens above; use the tokens above as the source of truth for font sizes, colors, spacing, radii, CTA hierarchy, and layout.

### Output Modes

- Default output is a standalone single-file HTML page with Header, main content, Footer, responsive CSS, and small module-tab JavaScript.
- `--body-only` omits the HTML shell, Header, and Footer. It keeps the Hero, Intro, Feature rows, Module tabs, Final CTA, and any JavaScript needed for module tabs.

### CTA Defaults

- Hero CTA defaults to `/zh-CN/signup` if the user gives CTA text but no URL.
- Feature-row CTA defaults to `/zh-CN/signup` and should render as `{components.text-link-arrow}`: green inline text plus arrow, not a filled green button.
- Final CTA defaults to `/zh-CN/signup` unless the user explicitly requests a different destination such as `/zh-CN/download`.
- Header/Footer links remain website-level chrome and should not be rewritten from user copy.

### Image Generation

Images are generated with the sibling `gpt-image-2` skill:

```bash
../gpt-image-2/scripts/generate_image.sh
```

Generated image responses are cached by slot and prompt hash:

```text
cache/images/<slot>-<hash>.json
```

Required slots:

- `hero`
- `section-1`
- `section-2`
- `section-3`
- `section-4`
- `module`

Image direction should stay compatible with the current `/individual` page. The renderer supplies transparent output through the image API, so the natural-language prompt should describe the artwork as a floating cutout and should avoid wording that makes the model draw gray tile artifacts:

- Use simple floating spot illustrations with API-controlled transparent output, not information posters. The image is a visual accent, not a second copy area.
- Keep each illustration sparse: 1 large pastel geometric shape, 1-2 white rounded UI cards, optional tiny icon badge, thin outlines, flat layers, no image drop shadow, and no cast shadow. Do not draw a white page or white rectangular background behind the artwork.
- Text inside images must be minimal: at most two short English labels, each 2-4 words. Never copy page headlines, section body text, bullets, or long user copy into artwork.
- Hero may include an abstract object/workspace photo crop with geometric overlays, but no visible faces, no real portraits, no product logos, no Frevana logo, and no brand/platform logos.
- Feature and module slots should be simple UI-card + geometric-shape illustrations, not photos, full dashboards, or dense product collages.
- Use a richer pastel palette across illustrations: coral/salmon, warm yellow, cyan, sky blue, soft pink, lavender, mint, and Frevana green. Frevana green should be a small accent, not the dominant color.
- Avoid fake logos, generic SaaS screenshots, abstract AI blobs, purple gradients, dark backgrounds, full-bleed stock-photo scenes, repeating gray tile artifacts, white background plates, heavy shadows, and glossy 3D depth.

If `FREVANA_TOKEN` is missing, image generation should fail with a clear message and suggest rerunning with `--skip-images`.


### Header/Footer Source Parity

Standalone HTML output should translate `frevana-web/components/Header.tsx` and `frevana-web/components/Footer.tsx` into static HTML/CSS/JS equivalents. Preserve the logo asset, Solutions dropdown structure, Case Study dropdown links, Docs/Articles/Pricing/News destinations, Login and Start free trial links, mobile drawer behavior, dark footer grid, social icon links, footer link list, and Download App click behavior.

### AEO Team Tabs

The AEO team/module section uses a horizontal tab strip like the original `/individual` page. Use compact tab typography around `{typography.tab}` (16-18px), not oversized labels. The selected tab has dark text and a bottom underline. The content below uses a restrained illustration/product-collage image on the left, capped around 560px wide on desktop, and text on the right. On mobile, tabs remain horizontal and scrollable instead of becoming a vertical rail.
