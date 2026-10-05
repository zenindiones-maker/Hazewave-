from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import json
import os
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Final

PROJECT_ID: Final = "HAZEWAVE"
AUTHORITY: Final = "HAZEWAVE_HARNESS"
PORTFOLIO_AUTHORITY: Final = "NONE"
EXPECTED_BOT_USERNAME: Final = "HazewaveAgentBot"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")


@dataclass(frozen=True)
class PairingDecision:
    authorized: bool
    pair_user_id: int | None
    reason: str


def pairing_decision(
    *,
    configured_user_id: int | None,
    pairing_code: str,
    sender_user_id: int,
    text: str,
) -> PairingDecision:
    message = str(text or "").strip()
    if configured_user_id is not None:
        if int(sender_user_id) == int(configured_user_id):
            return PairingDecision(True, None, "AUTHORIZED_USER")
        return PairingDecision(False, None, "UNAUTHORIZED_USER")

    parts = message.split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "/pair":
        return PairingDecision(False, None, "PAIRING_REQUIRED")
    supplied = parts[1].strip()
    if not supplied or supplied != str(pairing_code or "").strip():
        return PairingDecision(False, None, "PAIRING_CODE_INVALID")
    return PairingDecision(True, int(sender_user_id), "PAIRING_ACCEPTED")


def runtime_status_payload(runtime_sha: str) -> dict[str, str]:
    sha = str(runtime_sha or "").strip().lower()
    if not _SHA40.fullmatch(sha):
        raise ValueError("HAZEWAVE_RUNTIME_SHA_INVALID")
    return {
        "project_id": PROJECT_ID,
        "authority": AUTHORITY,
        "runtime_sha": sha,
        "telegram_bot_username": EXPECTED_BOT_USERNAME,
        "portfolio_authority": PORTFOLIO_AUTHORITY,
    }


class TelegramApi:
    def __init__(self, token: str, *, timeout_seconds: int = 35):
        value = str(token or "").strip()
        if not value:
            raise ValueError("HAZEWAVE_TELEGRAM_TOKEN_REQUIRED")
        self._base = f"https://api.telegram.org/bot{value}"
        self._timeout_seconds = timeout_seconds

    def call(self, method: str, payload: dict[str, Any] | None = None) -> Any:
        data = urllib.parse.urlencode(payload or {}, doseq=True).encode("utf-8")
        request = urllib.request.Request(
            f"{self._base}/{method}",
            data=data,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
            body = json.load(response)
        if not isinstance(body, dict) or not body.get("ok"):
            raise RuntimeError(f"TELEGRAM_API_{method}=FAIL")
        return body.get("result")


@dataclass(frozen=True)
class GatewayPaths:
    config_root: Path
    state_root: Path

    @classmethod
    def from_env(cls) -> "GatewayPaths":
        home = Path.home()
        return cls(
            config_root=Path(
                os.environ.get(
                    "HAZEWAVE_TELEGRAM_CONFIG_ROOT",
                    str(home / ".config" / "hazewave" / "telegram"),
                )
            ),
            state_root=Path(
                os.environ.get(
                    "HAZEWAVE_TELEGRAM_STATE_ROOT",
                    str(home / ".local" / "state" / "hazewave" / "telegram"),
                )
            ),
        )

    @property
    def token_file(self) -> Path:
        return self.config_root / "bot-token"

    @property
    def pairing_code_file(self) -> Path:
        return self.config_root / "pairing-code"

    @property
    def allowed_user_file(self) -> Path:
        return self.config_root / "allowed-user-id"

    @property
    def offset_file(self) -> Path:
        return self.state_root / "update-offset"

    @property
    def revision_file(self) -> Path:
        return self.state_root / "runtime-revision"

    @property
    def ready_file(self) -> Path:
        return self.state_root / "ready"


def _read_required(path: Path, label: str) -> str:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise RuntimeError(f"{label}_MISSING:{path}") from exc
    if not value:
        raise RuntimeError(f"{label}_EMPTY:{path}")
    return value


def _load_pairing_code(paths: GatewayPaths) -> str:
    if not paths.pairing_code_file.exists():
        return ""
    return paths.pairing_code_file.read_text(encoding="utf-8").strip()


def _load_allowed_user(paths: GatewayPaths) -> int | None:
    if not paths.allowed_user_file.exists():
        return None
    raw = paths.allowed_user_file.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError("HAZEWAVE_TELEGRAM_ALLOWED_USER_INVALID") from exc


def _write_private(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    path.chmod(0o600)


def _runtime_sha() -> str:
    value = str(os.environ.get("HAZEWAVE_RUNTIME_SHA", "")).strip().lower()
    if not _SHA40.fullmatch(value):
        raise RuntimeError("HAZEWAVE_RUNTIME_SHA_INVALID")
    return value


def _verify_bot_identity(api: TelegramApi) -> dict[str, Any]:
    me = api.call("getMe") or {}
    username = str(me.get("username") or "")
    if username != EXPECTED_BOT_USERNAME:
        raise RuntimeError(
            f"HAZEWAVE_TELEGRAM_BOT_IDENTITY_MISMATCH:"
            f"expected={EXPECTED_BOT_USERNAME}:actual={username or 'MISSING'}"
        )
    return me


def doctor() -> int:
    paths = GatewayPaths.from_env()
    token = _read_required(paths.token_file, "HAZEWAVE_TELEGRAM_TOKEN")
    api = TelegramApi(token)
    me = _verify_bot_identity(api)
    webhook = api.call("getWebhookInfo") or {}
    if str(webhook.get("url") or "").strip():
        raise RuntimeError("HAZEWAVE_TELEGRAM_WEBHOOK_CONFLICT")
    status = runtime_status_payload(_runtime_sha())
    print("HAZEWAVE_TELEGRAM_API=PASS")
    print(f"HAZEWAVE_TELEGRAM_BOT=@{me.get('username')}")
    print(f"HAZEWAVE_TELEGRAM_BOT_ID={me.get('id')}")
    print(f"HAZEWAVE_TELEGRAM_RUNTIME_SHA={status['runtime_sha']}")
    print(
        "HAZEWAVE_TELEGRAM_PAIRED="
        + ("YES" if _load_allowed_user(paths) is not None else "NO")
    )
    return 0


def _message_text(update: dict[str, Any]) -> tuple[int, int, str, str] | None:
    message = update.get("message")
    if not isinstance(message, dict):
        return None
    sender = message.get("from")
    chat = message.get("chat")
    if not isinstance(sender, dict) or not isinstance(chat, dict):
        return None
    if str(chat.get("type") or "") != "private":
        return None
    try:
        sender_user_id = int(sender["id"])
        chat_id = int(chat["id"])
    except (KeyError, TypeError, ValueError):
        return None
    text = str(message.get("text") or "").strip()
    return sender_user_id, chat_id, text, str(sender.get("username") or "")


def _status_text(runtime_sha: str, paired: bool) -> str:
    status = runtime_status_payload(runtime_sha)
    return "\n".join(
        (
            "HAZEWAVE_STATUS=ONLINE",
            f"PROJECT={status['project_id']}",
            f"AUTHORITY={status['authority']}",
            f"RUNTIME_SHA={status['runtime_sha']}",
            f"BOT=@{status['telegram_bot_username']}",
            f"PAIRED={'YES' if paired else 'NO'}",
            f"PORTFOLIO_AUTHORITY={status['portfolio_authority']}",
        )
    )


def serve() -> int:
    paths = GatewayPaths.from_env()
    paths.config_root.mkdir(parents=True, exist_ok=True)
    paths.state_root.mkdir(parents=True, exist_ok=True)

    token = _read_required(paths.token_file, "HAZEWAVE_TELEGRAM_TOKEN")
    api = TelegramApi(token, timeout_seconds=40)
    _verify_bot_identity(api)
    webhook = api.call("getWebhookInfo") or {}
    if str(webhook.get("url") or "").strip():
        raise RuntimeError("HAZEWAVE_TELEGRAM_WEBHOOK_CONFLICT")

    runtime_sha = _runtime_sha()

    offset = 0
    if paths.offset_file.exists():
        try:
            offset = max(0, int(paths.offset_file.read_text(encoding="utf-8").strip()))
        except ValueError:
            offset = 0

    paths.revision_file.write_text(runtime_sha + "\n", encoding="utf-8")
    paths.ready_file.write_text("READY\n", encoding="utf-8")
    paths.revision_file.chmod(0o600)
    paths.ready_file.chmod(0o600)

    print(
        f"HAZEWAVE_TELEGRAM_GATEWAY=ONLINE "
        f"BOT=@{EXPECTED_BOT_USERNAME} RUNTIME_SHA={runtime_sha}",
        flush=True,
    )

    while True:
        updates = api.call(
            "getUpdates",
            {
                "offset": offset,
                "timeout": 25,
                "allowed_updates": json.dumps(["message"]),
            },
        ) or []
        if not isinstance(updates, list):
            raise RuntimeError("HAZEWAVE_TELEGRAM_UPDATES_INVALID")

        for update in updates:
            if not isinstance(update, dict):
                continue
            try:
                update_id = int(update.get("update_id"))
            except (TypeError, ValueError):
                continue
            offset = max(offset, update_id + 1)
            _write_private(paths.offset_file, str(offset) + "\n")

            parsed = _message_text(update)
            if parsed is None:
                continue
            sender_user_id, chat_id, text, _username = parsed
            configured_user_id = _load_allowed_user(paths)
            pairing_code = _load_pairing_code(paths)
            decision = pairing_decision(
                configured_user_id=configured_user_id,
                pairing_code=pairing_code,
                sender_user_id=sender_user_id,
                text=text,
            )

            if not decision.authorized:
                if configured_user_id is None:
                    api.call(
                        "sendMessage",
                        {
                            "chat_id": chat_id,
                            "text": "HAZEWAVE_PAIRING=REQUIRED",
                        },
                    )
                continue

            if decision.pair_user_id is not None:
                _write_private(paths.allowed_user_file, str(decision.pair_user_id) + "\n")
                if paths.pairing_code_file.exists():
                    paths.pairing_code_file.unlink()
                api.call(
                    "sendMessage",
                    {
                        "chat_id": chat_id,
                        "text": (
                            "HAZEWAVE_PAIRING=PASS\n"
                            f"PROJECT={PROJECT_ID}\n"
                            f"BOT=@{EXPECTED_BOT_USERNAME}"
                        ),
                    },
                )
                continue

            lowered = text.lower()
            if lowered.startswith("/status") or lowered.startswith("/harness"):
                response = _status_text(runtime_sha, paired=True)
            elif lowered.startswith("/help") or lowered.startswith("/start"):
                response = (
                    "HAZEWAVE_BOT=ONLINE\n"
                    "COMMANDS=/status /harness /help\n"
                    "GROK_CHALLENGER=NOT_CONNECTED"
                )
            else:
                response = (
                    "HAZEWAVE_INGRESS=READY\n"
                    "GROK_CHALLENGER=NOT_CONNECTED\n"
                    "Use /status for exact runtime identity."
                )
            api.call("sendMessage", {"chat_id": chat_id, "text": response})

        time.sleep(0.2)


def _main() -> int:
    parser = argparse.ArgumentParser(prog="python -m hazewave.telegram_gateway")
    parser.add_argument("command", choices=("serve", "doctor"))
    args = parser.parse_args()
    if args.command == "serve":
        return serve()
    return doctor()


if __name__ == "__main__":
    raise SystemExit(_main())
