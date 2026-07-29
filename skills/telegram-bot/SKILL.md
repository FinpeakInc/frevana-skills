---
name: telegram-bot
description: Use when the user wants to build, inspect, or manage a Telegram bot through the Telegram Bot API. Supports bot info, commands, sending messages/photos/documents/locations, polling updates, webhooks, chat info, chat moderation, message editing/deleting/pinning/forwarding, callback query answers, dry-run request preview, raw method calls, and saved bot token reuse.
---

# Telegram Bot

Build and manage Telegram bots through the Telegram Bot API.

## Purpose

This skill is for **calling Telegram Bot API methods** with a bot token created by BotFather.

Inputs:

- Telegram bot token from `--bot-token`, `TELEGRAM_BOT_TOKEN`, or the locally saved token
- an action such as `sendMessage`, `getUpdates`, `setWebhook`, or `getMe`
- method-specific fields such as `chat_id`, `text`, `message_id`, `user_id`, `url`, or media paths

Output:

- raw Telegram JSON for read actions
- dry-run request metadata for write actions by default
- raw Telegram JSON for write actions when `--execute` is explicitly provided

Telegram write actions are externally visible and may affect chats, users, messages, or webhook delivery. Always confirm the target chat and final action before running with `--execute`.

## What This Skill Needs

- Telegram bot token from BotFather
- `curl`
- `bash`
- `python3`

Token resolution order:

1. `--bot-token` for the current run
2. `TELEGRAM_BOT_TOKEN`
3. locally saved token at `~/.config/telegram-bot/bot_token`

Users can save a token with:

```bash
bash <skill-path>/scripts/telegram_bot.sh \
  --bot-token "123456789:ABC..." \
  --save-bot-token
```

or clear it with:

```bash
bash <skill-path>/scripts/telegram_bot.sh --clear-bot-token
```

Never print the bot token back to the user. Treat it as a secret.

## Execution Order

1. Identify the Telegram Bot API method the user needs.
2. Prefer `scripts/telegram_bot.sh` over ad hoc `curl`.
3. Use read actions directly when the user asks for bot info, updates, webhook info, commands, or chat info.
4. For write actions, dry-run first unless the user explicitly asks to execute and all target IDs/content are unambiguous.
5. Run write actions with `--execute` only after confirmation.
6. Return raw Telegram JSON when requested; otherwise summarize `ok`, `result`, and useful message/update IDs.

## Actions

Use `--action ACTION`. Supported actions:

- `getMe`
- `getMyCommands`
- `setMyCommands`
- `sendMessage`
- `sendPhoto`
- `sendDocument`
- `sendLocation`
- `getUpdates`
- `setWebhook`
- `getWebhookInfo`
- `deleteWebhook`
- `getChat`
- `getChatMemberCount`
- `getChatAdministrators`
- `banChatMember`
- `unbanChatMember`
- `editMessageText`
- `deleteMessage`
- `pinChatMessage`
- `forwardMessage`
- `answerCallbackQuery`
- `raw`

`raw` lets you call another Bot API method with `--method METHOD` and `--payload-json`.

## Commands

### Get bot info

```bash
bash <skill-path>/scripts/telegram_bot.sh --action getMe
```

### Send a text message

```bash
bash <skill-path>/scripts/telegram_bot.sh \
  --action sendMessage \
  --chat-id "123456789" \
  --text "Hello from Frevana." \
  --parse-mode HTML
```

The command above dry-runs by default. Add `--execute` to send.

### Send a message with inline keyboard

```bash
bash <skill-path>/scripts/telegram_bot.sh \
  --action sendMessage \
  --chat-id "123456789" \
  --text "Choose an option:" \
  --reply-markup-json '{"inline_keyboard":[[{"text":"Option 1","callback_data":"opt1"},{"text":"Visit Website","url":"https://example.com"}]]}'
```

### Send a photo by URL or local file

```bash
bash <skill-path>/scripts/telegram_bot.sh \
  --action sendPhoto \
  --chat-id "123456789" \
  --photo "https://example.com/image.jpg" \
  --caption "Image from URL"
```

```bash
bash <skill-path>/scripts/telegram_bot.sh \
  --action sendPhoto \
  --chat-id "123456789" \
  --photo ./image.jpg \
  --caption "Local image" \
  --execute
```

### Send a document

```bash
bash <skill-path>/scripts/telegram_bot.sh \
  --action sendDocument \
  --chat-id "123456789" \
  --document ./report.pdf \
  --caption "Report"
```

### Get updates and find a chat ID

```bash
bash <skill-path>/scripts/telegram_bot.sh \
  --action getUpdates \
  --timeout 30
```

Users must message or `/start` the bot before the bot can message them directly.

### Set bot commands

```bash
bash <skill-path>/scripts/telegram_bot.sh \
  --action setMyCommands \
  --commands-json '[{"command":"start","description":"Start the bot"},{"command":"help","description":"Show help"}]'
```

### Set webhook

```bash
bash <skill-path>/scripts/telegram_bot.sh \
  --action setWebhook \
  --url "https://example.com/telegram/webhook" \
  --allowed-updates-json '["message","callback_query"]'
```

### Raw method call

```bash
bash <skill-path>/scripts/telegram_bot.sh \
  --action raw \
  --method getChat \
  --payload-json '{"chat_id":"@channelname"}'
```

## Script Options

- `--action ACTION`; required unless only configuring/clearing the token
- `--method METHOD`; required for `raw`
- `--payload-json JSON`; full payload object, or raw action payload
- `--payload-file PATH`; full payload object file
- `--chat-id ID`
- `--text TEXT`
- `--text-file PATH`
- `--parse-mode HTML|Markdown|MarkdownV2`
- `--reply-markup-json JSON`
- `--commands-json JSON`
- `--photo PATH_OR_URL`
- `--document PATH_OR_URL`
- `--caption TEXT`
- `--latitude VALUE`
- `--longitude VALUE`
- `--offset VALUE`
- `--timeout SECONDS`
- `--limit N`
- `--url URL`
- `--allowed-updates-json JSON`
- `--message-id ID`
- `--user-id ID`
- `--from-chat-id ID`
- `--callback-query-id ID`
- `--show-alert true|false`
- `--bot-token TOKEN`
- `--save-bot-token`
- `--configure-bot-token`
- `--clear-bot-token`
- `--output PATH`
- `--dry-run`; preview even for read actions
- `--execute`; execute write actions

## Notes

- Bot tokens are secrets. Never echo a token, save it in logs, or include it in user-facing output.
- Bot API base URL is `https://api.telegram.org/bot<TOKEN>/<METHOD_NAME>`.
- Chat IDs can be positive user IDs, negative group/channel IDs, or channel usernames such as `@channelname`.
- Parse modes are `HTML`, `Markdown`, and `MarkdownV2`; escaping rules differ.
- Common HTML tags include `<b>`, `<i>`, `<u>`, `<s>`, `<code>`, `<pre>`, `<a href="...">`, and `<tg-spoiler>`.
- Telegram bots cannot message a user first; the user must start the bot or otherwise expose a chat to the bot.
- Use `getUpdates` after sending a message to the bot to discover chat IDs.
- Avoid bulk sends unless the user explicitly asks. Telegram applies rate limits, including roughly one message per second to the same chat.
- If a user shares a bot token in chat, advise them to rotate it with BotFather.

## Example Prompts

### Chinese

- "用 Telegram bot 发一条消息到这个 chat"
- "查一下这个 Telegram bot 的 getMe"
- "帮我 setWebhook 到这个 URL"
- "获取 updates，找一下 chat_id"
- "设置 Telegram bot commands"

### English

- "Send a Telegram bot message to this chat"
- "Get Telegram bot updates"
- "Set the Telegram bot webhook"
- "Configure Telegram bot commands"
- "Ban this user from the Telegram chat"
