---
name: browser-automate
description: Use when the user wants to DRIVE their real logged-in Chrome to perform a task — navigate, search, fill forms, click, add to cart, multi-step flows, even place an order — through the Frevana Chrome Extension. A perceive→act loop that addresses elements by an integer [ref] from a snapshot. Stops before any payment/place-order; submitting an order requires the user's explicit confirmation in chat (one-shot --confirm-payment).
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

Clicking a pay / place-order control is **blocked by default**. When the result contains `NEEDS HUMAN (payment)` (or `needHuman:"payment"`), **STOP acting** — never retry the submit on your own. There is exactly one sanctioned path to place the order: the user's explicit confirmation flow below. Captcha / login challenges (`needHuman:"login"`/`"captcha"`) always hand off to the user — no override exists for those.

### Placing an order — requires the user's explicit confirmation in chat

1. Drive the flow normally (search → add to cart → checkout) until a step returns `NEEDS HUMAN (payment)`.
2. **Present an order summary in chat**, extracted from the CURRENT page (latest snapshot; use `extract`/`getHtml` on specific refs if needed): item name(s), quantity, total price, and — if visible — shipping address and payment method.
3. **Ask the user to confirm and WAIT for their reply**, e.g.: "已到下单确认页:〈商品〉× N,总价 ¥X。回复「确认下单」我就提交订单。" Never proceed on silence or on your own judgment.
4. **Only after the user explicitly confirms** (e.g. "确认下单" / "confirm order"): take a FRESH snapshot (refs go stale), then send ONE call with `--confirm-payment` containing **exactly one mutating step — the single `click` on the place-order control** — plus `waitFor` + `snapshot`. The CLI **refuses** a confirmed call with any `navigate`/`type`/`select`/`pressKey` or a second click, so do not pack extra actions in; if the confirmed page still needs a form filled, do that in a NORMAL (un-confirmed) call first, then confirm only the final click.
5. **Verify before you conclude — and NEVER re-submit on a guess.** The post-click snapshot is often taken before the order POST settles (single-page checkouts return "loaded" immediately), so a still-visible "Place order" button does **not** mean it failed. Judge only the `click` step's own result: if that step returned an error, the click didn't land. If it returned ok, treat the order as **possibly placed**. Before saying anything to the user — and **before ever re-asking to confirm** — independently check order state: navigate to the order-history / "my orders" page, or look for a confirmation banner / order number / emptied cart. Report what you found. If state is inconclusive, tell the user the order **may already be placed** and to check their account — do **not** silently send a second `--confirm-payment` call. Only re-submit if you have positively verified the order did NOT go through and the user confirms again.

**Never** pass `--confirm-payment` in any other situation: not on your own initiative, not because a step failed, not to save a round trip, not to re-try an ambiguous submit. The user's explicit go-ahead authorizes exactly one place-order click.

## Execution Order

1. Let the script run bundled `scripts/setup.sh` before every tool call.
2. If setup reports Chrome disconnected, stop and tell the user to open Chrome, connect the Frevana extension, and retry.
3. Start with `--url <page>` + `[{"op":"snapshot"}]`. Read the snapshot.
4. Act by `[ref]` from the LATEST snapshot only — never reuse stale refs; always end an action batch with `{"op":"snapshot"}` before deciding the next step.
5. On `NEEDS HUMAN (payment)` → follow "Placing an order" above (summary → explicit user confirmation → single `--confirm-payment` call). On login / captcha → STOP and hand off to the user.
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

### Submit a HUMAN-CONFIRMED order (one-shot; only after the user explicitly confirmed in chat)
```bash
bash <skill-path>/scripts/automate.sh --confirm-payment --steps '[{"op":"click","ref":42},{"op":"waitFor","for":"navigation"},{"op":"snapshot"}]'
```
