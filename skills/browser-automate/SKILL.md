---
name: browser-automate
description: Use when the user wants to DRIVE their real logged-in Chrome to perform a task — navigate, search, fill forms, click, add to cart, multi-step flows — through the Frevana Chrome Extension. A perceive→act loop that addresses elements by an integer [ref] from a snapshot. Stops before any payment/place-order.
---

# Browser Automate

Drive the user's **real, logged-in Chrome** to accomplish a task: navigate, search, fill forms, click, shop. Runs in a dedicated "Frevana" browser tab — it never hijacks the tab the user is on. Uses the Chrome Extension-backed Frevana MCP tool `frevana_automate`.

## Purpose

This skill performs interactive browser automation via `frevana_automate`. Elements are addressed by an integer `[ref]` from a snapshot, never by CSS selector. Use it for tasks that require *clicking through a UI* (search a site, fill a form, add to cart, go to checkout) — as opposed to just fetching data (use Authenticated Fetch) or generating a collector (use Site Data Collector).

## What This Skill Needs

- bundled `scripts/setup.sh` wrapper, which downloads and runs the latest official Frevana setup script
- Frevana local daemon running after setup, default port `12306`
- Chrome connected through the Frevana Chrome Extension
- `curl`, `bash`, `python3`

This is a Chrome Extension skill. It uses the local daemon and Chrome Extension session.

## How it works — perceive → act loop

Call `scripts/automate.sh` **repeatedly**:

1. **First call**: pass `--url` to open the page plus a single `snapshot` step. The result lists interactable elements as `[ref] role "name"`.
   ```bash
   bash <skill-path>/scripts/automate.sh --url "https://duckduckgo.com/" --steps '[{"op":"snapshot"}]'
   ```
2. **Read the snapshot**, then call again **without `--url`** (reuses the same tab) with action steps that reference the `[ref]`s you saw, ending in a `snapshot` to see the new state:
   ```bash
   bash <skill-path>/scripts/automate.sh --steps '[{"op":"type","ref":2,"text":"frevana","submit":true},{"op":"wait","ms":1500},{"op":"snapshot"}]'
   ```
3. **Repeat** until the task is done.

Step ops: `navigate{url}` · `snapshot` · `click{ref}` · `type{ref,text,submit?}` · `select{ref,value}` · `scroll{to:"ref|top|bottom",ref?}` · `pressKey{key}` · `waitFor{for:"navigation|idle|ref",ref?}` · `assert{ref,exists?}` · `extract{ref,as}` · `getHtml{ref,as?}` · `wait{ms}`.

Optional flags: `--allow-domains '["amazon.com"]'` (restrict navigation to these domains), `--timeout <ms>`.

## PAYMENT / CHALLENGE SAFETY (critical)

Clicking a pay / place-order control is **blocked by default**. When the result contains `NEEDS HUMAN (payment)` (or `needHuman:"payment"`), **STOP immediately** and tell the user to complete the payment themselves. Never retry a payment/checkout submit. Same for captcha / login challenges (`needHuman:"login"`/`"captcha"`).

## Execution Order

1. Let the script run bundled `scripts/setup.sh` before every tool call.
2. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
3. Start with `--url <page>` + `[{"op":"snapshot"}]`. Read the snapshot.
4. Act by `[ref]` from the LATEST snapshot only — never reuse stale refs; always end an action batch with `{"op":"snapshot"}` before deciding the next step.
5. On `NEEDS HUMAN (payment)` / login / captcha → STOP and hand off to the user.
6. When done, give a short plain-text summary of what you did and the final state.

## Commands

### Open a page and snapshot it
```bash
bash <skill-path>/scripts/automate.sh --url "https://www.amazon.com/" --steps '[{"op":"snapshot"}]'
```

### Act on the current page (reuse the tab)
```bash
bash <skill-path>/scripts/automate.sh --steps '[{"op":"click","ref":13},{"op":"waitFor","for":"navigation"},{"op":"snapshot"}]'
```
