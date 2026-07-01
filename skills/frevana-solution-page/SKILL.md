---
name: frevana-solution-page
description: Generate Frevana solution-style landing pages from natural-language copy. Use when the user wants a Frevana-like solution/landing page, gives Hero/section/CTA text, wants a single-file HTML page, or needs matching gpt-image-2 images generated and cached for a Frevana solution page.
---

# Frevana Solution Page

Create single-file HTML landing pages that match Frevana's solution-page visual system. The user can describe the page in natural language; do not require them to hand-write JSON.

The visual target is the current Frevana `/individual` page: neutral white canvas, oversized Host Grotesk headlines, Open Sans body/UI text, soft-green proof chips, dark charcoal primary CTAs, green inline feature links, alternating product-illustration rows, transparent-background spot illustrations, and a dark slate footer.

## Workflow

1. Read `references/design.md` before generating the page.
2. Extract the user's natural-language brief into the internal page schema.
3. Ask follow-up questions only when a missing detail would materially change the page, such as the audience, product, or required CTA URL.
4. If the user gives only CTA text, use `/zh-CN/signup` as the CTA URL.
5. Generate the page with `scripts/generate_landing_page.py`.
6. By default, generate and cache page images through the sibling `gpt-image-2` skill.

## Internal Schema

The Agent should create a JSON input file from the conversation. The user does not need to see or edit this schema unless they ask for automation.

```json
{
  "page_title": "Frevana Solution Page",
  "meta_description": "A Frevana-style solution landing page.",
  "language": "zh-CN",
  "hero": {
    "eyebrow": "几分钟内启动您的 AI 团队",
    "title": "让 AI 回答成为您下一个增长渠道",
    "body": "描述产品价值和目标用户。",
    "cta_text": "立即开始",
    "cta_url": "/zh-CN/signup",
    "image_prompt": "Simple Frevana-style spot illustration: abstract AI visibility cards and green geometry"
  },
  "intro": {
    "eyebrow": "为什么选择 Frevana",
    "title": "通过 AI 回答赢得更多客户"
  },
  "sections": [
    {
      "eyebrow": "追踪热门 AI 查询",
      "title": "问题研究",
      "body": "说明该模块如何帮助用户增长。",
      "cta_text": "立即开始",
      "cta_url": "/zh-CN/signup",
      "image_prompt": "Simple UI card illustration: short question labels and geometric shapes"
    }
  ],
  "module": {
    "eyebrow": "您将获得",
    "title": "助力您增长的 AEO 团队",
    "image_prompt": "Simple module illustration: two UI cards, icon badge, green geometry",
    "tabs": [
      {
        "label": "问题研究员",
        "title": "问题研究员",
        "body": "从真实用户问题中发现内容机会。"
      }
    ]
  },
  "final_cta": {
    "title": "准备好赢得 AI 流量了吗？",
    "body": "用 Frevana 创建您的下一批 AI 可引用页面。",
    "cta_text": "立即开始",
    "cta_url": "/zh-CN/signup"
  }
}
```

## Commands

Generate a full standalone page with Header and Footer:

```bash
python3 scripts/generate_landing_page.py --input page.json --output dist/landing.html
```

Generate only the middle page body for future embedding into the official site layout:

```bash
python3 scripts/generate_landing_page.py --input page.json --output dist/body.html --body-only
```

Dry-run without calling the image service:

```bash
python3 scripts/generate_landing_page.py --input page.json --output dist/landing.html --skip-images
```

## Image Generation

Images are generated through:

```bash
../gpt-image-2/scripts/generate_image.sh
```

The script requires `FREVANA_TOKEN` unless `--skip-images` is used. It calls `gpt-image-2` with `--background transparent --output-format png` by default. Generated image responses are cached by slot, prompt hash, output options, and background under:

```text
cache/images/<slot>-<hash>.json
```

Standard slots:

- `hero`
- `section-1`
- `section-2`
- `section-3`
- `section-4`
- `section-N` for any additional user-provided feature sections
- `module`

Image style must match the current Chinese Frevana `/individual` page assets for every page language. Chinese and English pages should use the same airy, open, lightweight illustration style. Module tabs must match the original horizontal tab strip, not a left-side vertical rail. The script passes `--background transparent`; image prompts should describe floating cutout artwork and should avoid wording that makes the model draw gray tile artifacts:

- Generate simple floating spot illustrations with API-controlled transparent output, not information posters or dense SaaS dashboards.
- Use 1 large pastel geometric shape plus 1-2 white rounded UI cards, thin outlines, flat layers, no image drop shadow, no cast shadow, and optional tiny icon badges. Use a richer pastel palette: coral/salmon, warm yellow, cyan, sky blue, soft pink, lavender, mint, and Frevana green. Frevana green should be a small accent, not the dominant color. Do not draw a white page or white rectangular background behind the artwork.
- Each image slot must use a different composition, silhouette, card arrangement, and accent-color mix. Do not reuse the same search-bar/status-chip illustration across Hero and feature sections.
- Prefer gray placeholder lines over readable text. If text is necessary, use at most one short generic English label, 1-2 words. Do not use Chinese text, platform names, page headlines, section body text, bullets, or long user copy in the image.
- Hero may use an abstract object/workspace photo crop with geometric overlays, but no visible faces, no portraits, no product logos, no Frevana logo, and no brand/platform logos.
- Feature and module images should primarily be simple UI-card + geometric-shape illustrations, not photos.
- Avoid repeating gray tile artifacts, white background plates, large enclosing white cards, browser frames, dashboard containers, bottom label pills, heavy shadows, glossy 3D depth, complex flowcharts, crowded UI collages, purple AI gradients, dark AI art, and ordinary office photography.

Visual variety:

- Do not permanently bind a specific illustration structure to `section-1`, `section-2`, or any other section number.
- For each generated page, assign section images from a reusable motif pool so that images on the same page have visibly different silhouettes, card arrangements, and accent-color mixes.
- The motif pool can include question chips, document stacks, checklist/course cards, compact charts, agent cards, search/input cards, dashboard tiles, content preview cards, and report cards.
- If the user provides more than four sections, continue rendering every section and keep assigning varied motifs instead of dropping, merging, or repeating the same structure.
- Hero and module images use their own small motif pools so they remain appropriate for their page roles; feature sections use a dynamic section motif pool and are not bound to section numbers.
- Image prompts should canonicalize localized page copy into language-neutral visual themes so English input does not drift toward generic English SaaS dashboard visuals.

## Header, Footer, And CTA Policy

Keep Header and Footer as fixed website-level components unless the user explicitly asks for body-only output.

Preserve these default behaviors:

- Logo links to `/zh-CN`.
- Solutions dropdown remains available.
- Docs, Articles, Pricing, News, Login, and Start free trial links remain present.
- Header/Footer should follow the static HTML/CSS/JS equivalent of `frevana-web/components/Header.tsx` and `frevana-web/components/Footer.tsx`: logo image, Solutions dropdown, Case study dropdown, Docs/Articles/Pricing/News links, Login/Start free trial, mobile drawer, dark footer, social icons, footer links, and Download App behavior.
- Language selector stays visually present; static display is acceptable in single-file output.
- Hero, feature, and final CTAs default to `/zh-CN/signup`.
- If the user provides a CTA URL, use that override.
- Hero and final primary CTAs should render as dark charcoal filled buttons.
- Feature-row CTAs should render as green inline text links with arrows, not green filled buttons.


## Module Layout Policy

The AEO team/module area must match the current Frevana solution-page layout:

- Desktop: centered eyebrow/title, then a compact horizontal tab strip with the selected tab underlined. Tab labels should be around 16-18px, not oversized.
- Desktop content: restrained illustration on the left, capped around 560px wide, copy on the right.
- Mobile: keep tabs horizontal and scrollable; do not convert them to a vertical sidebar.
- Do not use card-like vertical tab rails for this section.
