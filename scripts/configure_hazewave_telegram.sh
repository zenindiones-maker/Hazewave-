#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

HAZEWAVE_TELEGRAM_CONFIG_ROOT="${HAZEWAVE_TELEGRAM_CONFIG_ROOT:-$HOME/.config/hazewave/telegram}"
TOKEN_FILE="$HAZEWAVE_TELEGRAM_CONFIG_ROOT/bot-token"
PAIRING_FILE="$HAZEWAVE_TELEGRAM_CONFIG_ROOT/pairing-code"
ALLOWED_USER_FILE="$HAZEWAVE_TELEGRAM_CONFIG_ROOT/allowed-user-id"
EXPECTED_USERNAME="HazewaveAgentBot"

mkdir -p "$HAZEWAVE_TELEGRAM_CONFIG_ROOT"
chmod 700 "$HAZEWAVE_TELEGRAM_CONFIG_ROOT" 2>/dev/null || true
umask 077

reset_pairing=0
if [ "${1:-}" = "--reset-pairing" ]; then
  reset_pairing=1
fi

printf 'Hazewave Telegram bot token (input hidden): '
IFS= read -r -s TOKEN
printf '\n'
test -n "$TOKEN" || {
  echo "HAZEWAVE_TELEGRAM_CONFIG=FAIL empty_token" >&2
  exit 2
}

export HAZEWAVE_TELEGRAM_CONFIG_TOKEN="$TOKEN"
export HAZEWAVE_TELEGRAM_EXPECTED_USERNAME="$EXPECTED_USERNAME"

python - <<'PY'
from __future__ import annotations
import json
import os
import urllib.parse
import urllib.request

token = os.environ["HAZEWAVE_TELEGRAM_CONFIG_TOKEN"].strip()
expected = os.environ["HAZEWAVE_TELEGRAM_EXPECTED_USERNAME"].strip()

def call(method: str):
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=urllib.parse.urlencode({}).encode(),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        body = json.load(response)
    if not body.get("ok"):
        raise SystemExit(f"TELEGRAM_API_{method}=FAIL")
    return body.get("result") or {}

me = call("getMe")
actual = str(me.get("username") or "")
if actual != expected:
    raise SystemExit(
        f"HAZEWAVE_TELEGRAM_BOT_IDENTITY_MISMATCH expected={expected} actual={actual or 'MISSING'}"
    )
webhook = call("getWebhookInfo")
if str(webhook.get("url") or "").strip():
    raise SystemExit("HAZEWAVE_TELEGRAM_WEBHOOK_CONFLICT remove_webhook_before_long_polling")
print(f"HAZEWAVE_TELEGRAM_BOT=@{actual}")
print(f"HAZEWAVE_TELEGRAM_BOT_ID={me.get('id')}")
print("HAZEWAVE_TELEGRAM_API=PASS")
PY

printf '%s\n' "$TOKEN" > "$TOKEN_FILE"
chmod 600 "$TOKEN_FILE"
unset TOKEN HAZEWAVE_TELEGRAM_CONFIG_TOKEN

if [ "$reset_pairing" -eq 1 ]; then
  rm -f "$ALLOWED_USER_FILE"
fi

if [ ! -s "$ALLOWED_USER_FILE" ]; then
  PAIRING_CODE="$(python - <<'PY'
import secrets
print(secrets.token_hex(8).upper())
PY
)"
  printf '%s\n' "$PAIRING_CODE" > "$PAIRING_FILE"
  chmod 600 "$PAIRING_FILE"
  echo "HAZEWAVE_TELEGRAM_PAIRING=REQUIRED"
  echo "Send this message to @HazewaveAgentBot:"
  echo "/pair $PAIRING_CODE"
else
  rm -f "$PAIRING_FILE"
  echo "HAZEWAVE_TELEGRAM_PAIRING=ALREADY_BOUND"
fi

echo "HAZEWAVE_TELEGRAM_CONFIG=PASS"
echo "HAZEWAVE_TELEGRAM_CONFIG_ROOT=$HAZEWAVE_TELEGRAM_CONFIG_ROOT"
