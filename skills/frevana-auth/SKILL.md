---
name: frevana-auth
description: Use when the user needs to sign in to Frevana from the CLI, bootstrap the `frevana` command on a new machine, start the device authorization flow, or obtain/store a Frevana API key for later terminal workflows. Use this whenever the user mentions `frevana login`, Frevana API keys, CLI authentication, or setting up Frevana access before running other Frevana commands or skills.
---

# Frevana Auth

Authenticate the Frevana CLI and save the resulting API key to the local CLI config.

This skill is for **CLI login and auth bootstrap**, not for calling Frevana HTTP APIs directly.

## What This Skill Does

- starts the device authorization flow with `frevana login`
- if the `frevana login` command is unavailable, attempts to install `@frevana/frevana` with `npm i -g` and retries
- relies on the CLI to save credentials locally after approval

By default, the wrapper script passes `--server https://api.frevana.com` unless the user provides a different `--server` value.

After a successful login, the CLI stores credentials at:

```text
~/.frevana/cli-config.json
```

Treat the API key as sensitive. Do not echo it back to the user unless they explicitly ask to inspect it.

## What This Skill Needs

- `bash`
- `npm` only if the initial `frevana login` attempt fails because the CLI is unavailable
- browser access or a manual way to open the device authorization URL
- optional `server` URL when the user wants a non-default Frevana server

## Execution Order

Use this flow so login stays predictable:

1. If the user provides a custom Frevana server URL, pass it through with `--server`.
2. Prefer the repo wrapper script over ad hoc commands.
3. Run `frevana login --server <effective-server>` first to start the device authorization flow.
4. If the command is unavailable, attempt installation with `npm i -g @frevana/frevana`.
5. If `npm` is missing and the command is unavailable, stop and tell the user to install Node.js/npm first.
6. If that install step fails because the package is unavailable in the current registry, stop and ask the user for the correct private registry or local package source.
7. Retry `frevana login --server <effective-server>` after a successful install.
8. Let the CLI open the browser when possible. If it cannot, follow the printed authorization URL and user code manually.
9. After login completes, confirm that credentials were saved to `~/.frevana/cli-config.json`.
10. Do not print the API key in summaries unless the user explicitly asks for the raw secret.

## Command

### Default server

```bash
bash <skill-path>/scripts/login.sh
```

This uses `https://api.frevana.com`.

### Custom server

```bash
bash <skill-path>/scripts/login.sh \
  --server "http://localhost:3001"
```

## Expected Output

This is an interactive CLI flow. Expect:

- login instructions from `frevana login`
- an authorization URL and device code, or an automatically opened browser
- a success message when the API key has been saved locally
- the saved config path printed at the end when available

## Notes

- Use this skill before other Frevana CLI workflows when the machine has not been authenticated yet.
- This skill does not require `FREVANA_TOKEN`.
- The wrapper script intentionally does not pre-check `frevana` before every run. It installs only after the login command proves unavailable.
- The wrapper script does not rely on the CLI's internal default server. It explicitly uses `https://api.frevana.com` unless overridden.
- If the current environment blocks global npm installs, request approval before running the install step.
- If `npm i -g @frevana/frevana` is unavailable in the current registry, ask the user for the correct private registry, tarball, git URL, or local package path instead of guessing.
- If the authorization flow times out, the CLI may fall back to a manual API key entry prompt.
- Prefer reporting the saved config path instead of exposing the API key value.

## Example Prompts

### 中文

- "帮我给这台机器登录 Frevana，先直接跑授权；如果 `frevana` 不可用，再安装后重试"
- "启动 `frevana login`，我要拿到后面跑 Frevana CLI 用的 API key"
- "帮我把 Frevana CLI 授权到 `http://localhost:3001`，不要把 key 直接打印出来"

### English

- "Set up Frevana CLI auth on this machine. If `frevana login` is unavailable, install it and retry."
- "Run `frevana login` for me and tell me where the API key gets stored locally."
- "Authenticate the Frevana CLI against a custom server and keep the API key private."
