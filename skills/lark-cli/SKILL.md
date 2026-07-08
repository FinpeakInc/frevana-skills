---
name: lark-cli
description: Use when the user needs to install, locate, initialize, authenticate, verify, upgrade, or troubleshoot the official Lark/Feishu `lark-cli` before using Lark skills. Covers `npx @larksuite/cli@latest install`, global install location, product suite selection for Lark versus Feishu authorization links, manual handling of setup/auth URLs, `lark-cli config init --new --brand lark|feishu`, `lark-cli auth login --recommend`, auth status checks, user/bot identity selection, output formats, dry-run safety, and when to hand off to domain skills such as `lark-im`, `lark-contact`, `lark-doc`, `lark-sheets`, or `lark-markdown`.
---

# Lark CLI

Install and bootstrap the official Lark/Feishu CLI for later Lark operations.

This skill is for **CLI setup and shared operating rules**. It does not replace domain skills such as `lark-im` for messages, `lark-contact` for resolving people, or `lark-markdown` for Drive-native Markdown files.

## Source

This workflow follows the official larksuite/cli README quick start for AI agents, with one repo rule: always pass an explicit `--brand`.

```bash
npx @larksuite/cli@latest install
lark-cli config init --new --brand lark
lark-cli auth login --recommend
lark-cli auth status
```

The upstream quick start omits `--brand`. This skill must not omit it: use `--brand lark` when the user explicitly says Lark, otherwise use `--brand feishu`.

## What This Skill Does

- checks whether `lark-cli` is already available
- installs or upgrades the CLI through the official npm package
- explains where the command and package are installed
- initializes Lark/Feishu Open Platform app credentials with the correct product suite
- starts OAuth login with recommended scopes and the saved product suite
- prints setup/auth URLs from the CLI for the user to open manually
- verifies the active auth state
- gives shared rules for identity, output parsing, and side-effect safety

## What This Skill Needs

- Node.js with `npm` and `npx`
- network access to npm and the binary download source
- a browser or manual access to the URLs printed by `config init` and `auth login`
- user approval for app setup and OAuth authorization

If Node.js/npm is missing, stop and ask the user to install Node.js first. Do not try to install system Node.js from this skill.

## Install Timing

Use this skill before other Lark skills when:

- the user asks to set up Lark/Feishu CLI
- `lark-cli` is not found
- a Lark skill fails because CLI config or auth is missing
- the user asks where `lark-cli` is installed
- the user wants to switch or verify `user` versus `bot` execution

Do not reinstall on every Lark request. First run:

```bash
bash <skill-path>/scripts/setup_lark_cli.sh check
```

Install only if the check says `lark-cli` is missing, or if the user explicitly asks to upgrade/reinstall.

## Install Method

Preferred installer:

```bash
npx @larksuite/cli@latest install
```

The installer performs a guided setup. It globally installs `@larksuite/cli`, installs the upstream Lark AI skills, then offers app configuration and authorization.

For non-interactive agent setup, use the wrapper script:

```bash
bash <skill-path>/scripts/setup_lark_cli.sh setup --suite lark
```

This runs:

1. install when `lark-cli` is missing
2. `lark-cli config init --new --brand <lark|feishu>`
3. `lark-cli auth login --recommend`
4. `lark-cli auth status`

The config and login steps may print browser URLs. Send those URLs to the user and wait for them to finish authorization when needed.

## Product Suite

Choose the product suite before `config init`.

- If the user says **Lark**, international Lark, larksuite, global, overseas, or English Lark, pass `--suite lark`.
- If the user says **Feishu**, 飞书, 国内飞书, or Chinese Feishu, pass `--suite feishu`.
- If the user does not specify Lark versus Feishu, default to `--suite feishu`.
- If the CLI is already configured, `auth login` uses the saved product suite. To change the authorization link family, rerun `config-init` or `setup` with the desired `--suite`.

The wrapper maps `--suite` to the official `lark-cli config init --brand` option. If `--suite` is omitted, the wrapper still passes `--brand feishu` explicitly:

```bash
bash <skill-path>/scripts/setup_lark_cli.sh config-init --suite lark
bash <skill-path>/scripts/setup_lark_cli.sh config-init --suite feishu
bash <skill-path>/scripts/setup_lark_cli.sh config-init
```

Do not confuse product suite with auth business domains:

- `--suite lark|feishu` chooses the Lark versus Feishu setup/authorization link family.
- `--domain calendar|docs|drive|all` on `auth login` chooses permission business domains.

## Setup Command Rules

Avoid raw ambiguous setup commands during agent setup:

```bash
lark-cli config init
lark-cli config init --new
```

Raw `lark-cli config init` commands rely on upstream defaults and make it too easy to miss a user request for Lark.

Prefer the wrapper:

```bash
bash <skill-path>/scripts/setup_lark_cli.sh config-init --suite lark
bash <skill-path>/scripts/setup_lark_cli.sh config-init --suite feishu
bash <skill-path>/scripts/setup_lark_cli.sh config-init
bash <skill-path>/scripts/setup_lark_cli.sh setup --suite lark
bash <skill-path>/scripts/setup_lark_cli.sh setup --suite feishu
bash <skill-path>/scripts/setup_lark_cli.sh setup
```

The wrapper default is Feishu. If an existing run accidentally created a Feishu profile when the user requested Lark, rerun `config-init --suite lark` before `auth login`; plain `auth login` will keep using the saved Feishu brand.

## Authorization Links

The wrapper does not open browser links automatically. Run setup/login and copy the printed setup or authorization URL to the user:

```bash
bash <skill-path>/scripts/setup_lark_cli.sh setup --suite lark
```

Keep URLs intact and send them to the user exactly as printed. Treat setup/auth URLs as opaque strings: do not edit, re-encode, or add punctuation inside the URL.

## Install Location

The official npm package installs globally.

On macOS/Linux, the command normally resolves to:

```text
$(npm prefix -g)/bin/lark-cli
```

The npm package normally lives at:

```text
$(npm root -g)/@larksuite/cli
```

Inside that package, the downloaded native binary is:

```text
$(npm root -g)/@larksuite/cli/bin/lark-cli
```

On Windows, the command is normally under:

```text
%APPDATA%\npm\lark-cli.cmd
```

Use the wrapper to print the current machine's resolved paths without exposing credentials:

```bash
bash <skill-path>/scripts/setup_lark_cli.sh check
```

## Commands

### Check current install

```bash
bash <skill-path>/scripts/setup_lark_cli.sh check
```

### Install the CLI

```bash
bash <skill-path>/scripts/setup_lark_cli.sh install
```

### Initialize app credentials

```bash
bash <skill-path>/scripts/setup_lark_cli.sh config-init
```

This defaults to `lark-cli config init --new --brand feishu`. Use `--suite lark` for international Lark. The command may require the user to open a browser URL and complete app setup.

### Log in

```bash
bash <skill-path>/scripts/setup_lark_cli.sh login
```

This runs `lark-cli auth login --recommend`. If it prints an authorization URL, send that URL to the user and wait for them to complete authorization.

Use exact scopes only when the user or downstream skill requires them:

```bash
bash <skill-path>/scripts/setup_lark_cli.sh login --scope "im:message:send_as_bot"
```

### Verify auth

```bash
bash <skill-path>/scripts/setup_lark_cli.sh status
```

## Identity Rules

Lark commands can run as a user or bot. Do not guess when it matters.

- Use `--as user` when the user wants actions under their personal Lark identity.
- Use `--as bot` when sending from or operating as the configured app bot.
- For user-facing write actions, confirm the target, message/content, and identity before executing without dry-run.

Example:

```bash
lark-cli im +messages-send --as bot --chat-id "oc_xxx" --text "Hello" --dry-run
```

## Output Rules

Prefer JSON for parsing:

```bash
lark-cli auth status --format json
```

With `--format json`, success is indicated by:

```json
{ "ok": true }
```

Errors are written to stderr with:

```json
{ "ok": false, "error": { "type": "...", "message": "..." } }
```

Check exit code or `ok == true`. Do not expect a top-level `code: 0` in shortcut command success envelopes.

## Safety Rules

- For side-effect commands, run `--dry-run` first when the command supports it.
- Do not print tokens, cookies, app secrets, refresh tokens, or raw local credential files.
- Do not relax lark-cli default security settings unless the user explicitly asks and understands the risk.
- If a command reports missing scopes, use `lark-cli auth check <scope>` or rerun `lark-cli auth login` with the needed scope/domain.
- If a user asks to send a Lark message, use `lark-im` after this setup skill has verified install and auth.
- If a user provides only a person name or email for messaging, use a contact lookup skill before sending.
- If a user asks to manage Drive-native `.md` files, use `lark-markdown`; it is not the IM message sender.

## Example Prompts

### Chinese

- "帮我安装 lark-cli，并说明安装到哪里"
- "检查这台机器有没有 lark-cli，没装就初始化"
- "配置 Lark CLI app credentials，然后登录推荐权限"
- "查一下当前 lark-cli 是 user 还是 bot 身份"
- "发飞书消息前先把 lark-cli 装好并登录"

### English

- "Install lark-cli and show me where it was installed."
- "Set up Lark CLI for AI agent usage."
- "Run lark-cli config init and auth login with recommended scopes."
- "Check whether lark-cli is authenticated."
- "Prepare lark-cli before using lark-im to send a message."
