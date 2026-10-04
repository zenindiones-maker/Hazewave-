# Hazewave Telegram Runtime Runbook v1

## Scope

This runbook configures and operates the dedicated Hazewave Telegram bot:

`@HazewaveAgentBot`

It does not configure any other project, bot, runtime, token, or state namespace.

## Prerequisites

The Hazewave immutable Termux runtime must already pass:

```bash
bash scripts/hazewave_termux_control.sh doctor
```

Runtime namespaces:

```text
code:   ~/.local/share/hazewave/deploy/current/
config: ~/.config/hazewave/telegram/
state:  ~/.local/state/hazewave/telegram/
```

## 1. Obtain the token

In Telegram BotFather, select `@HazewaveAgentBot` and choose **API Token**.

Do not paste the token into ChatGPT, GitHub, source files, shell commands, or screenshots.

## 2. Configure securely in Termux

From the Hazewave development session after updating to the release that contains this runtime:

```bash
bash scripts/configure_hazewave_telegram.sh
```

The script prompts for the token with hidden input, calls Telegram `getMe`, and fails unless the token belongs to exactly `HazewaveAgentBot`.

The token is written to:

```text
~/.config/hazewave/telegram/bot-token
```

with private permissions.

If no user is already paired, the script generates a one-time pairing code.

## 3. Install persistence

```bash
bash scripts/install_hazewave_telegram_persistence.sh
```

This creates:

```text
~/.config/hazewave/telegram/supervisor.sh
~/.termux/boot/hazewave-telegram.sh
```

and starts the gateway from the immutable `deploy/current` release.

## 4. Pair the human owner

Open the private chat with `@HazewaveAgentBot` and send the exact command printed by the configuration step:

```text
/pair <ONE_TIME_CODE>
```

On success the bot returns:

```text
HAZEWAVE_PAIRING=PASS
PROJECT=HAZEWAVE
BOT=@HazewaveAgentBot
```

The one-time pairing code is then deleted.

## 5. Verify

```bash
bash scripts/hazewave_telegram_control.sh doctor
bash scripts/hazewave_telegram_control.sh status
```

In Telegram:

```text
/status
```

The response includes the exact runtime SHA.

## Commands

```bash
bash scripts/hazewave_telegram_control.sh start
bash scripts/hazewave_telegram_control.sh stop
bash scripts/hazewave_telegram_control.sh restart
bash scripts/hazewave_telegram_control.sh status
bash scripts/hazewave_telegram_control.sh doctor
bash scripts/hazewave_telegram_control.sh pair-code
bash scripts/hazewave_telegram_control.sh logs
```

## Reset pairing

Only when intentionally changing the authorized Telegram user:

```bash
bash scripts/configure_hazewave_telegram.sh --reset-pairing
```

A new one-time code is generated.

## Current conversational capability

Telegram transport and exact runtime identity are implemented.

The Grok Challenger is deliberately **not connected yet**. Free-text messages therefore report `GROK_CHALLENGER=NOT_CONNECTED` instead of silently routing to an ungoverned external model.

External-model integration must be a separate, project-local, reviewed capability.
