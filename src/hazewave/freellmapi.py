from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx

from hazewave.harness import AUTHORITY, HazewaveAuthorization, validate_authorization


FREELLMAPI_REPOSITORY = "https://github.com/tashfeenahmed/freellmapi.git"
FREELLMAPI_VERSION = "v0.13.4"
FREELLMAPI_PINNED_REF = "716948f20b12ec1c9b7c6fcebd22a3e7233cda1b"
DEFAULT_BASE_URL = "http://127.0.0.1:3001/v1"

_ALLOWED_EGRESS_CLASSES = frozenset({"PUBLIC", "INTERNAL_NON_SECRET"})
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class FreeLLMAPIError(RuntimeError):
    """Raised when the Hazewave-scoped FreeLLMAPI gateway cannot be used safely."""


@dataclass(frozen=True)
class FreeLLMAPICompletionResult:
    content: str
    served_model: str | None
    usage: dict[str, Any]
    raw: dict[str, Any]
    routed_via: str | None = None
    provider_gateway: str = "FREELLMAPI"
    authority: str = AUTHORITY


def _normalized_base_url(value: str, *, allow_remote: bool) -> str:
    text = str(value or "").strip().rstrip("/")
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise FreeLLMAPIError("FREELLMAPI_BASE_URL_INVALID")
    if not allow_remote and parsed.hostname.casefold() not in _LOOPBACK_HOSTS:
        raise FreeLLMAPIError(
            "FreeLLMAPI must use a loopback endpoint unless remote access is explicitly authorized"
        )
    path = parsed.path.rstrip("/")
    if not path.endswith("/v1"):
        raise FreeLLMAPIError("FREELLMAPI_BASE_URL_MUST_END_IN_V1")
    return text + "/"


def _origin_from_base_url(base_url: str) -> str:
    parsed = urlparse(base_url)
    host = parsed.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    port = f":{parsed.port}" if parsed.port is not None else ""
    return f"{parsed.scheme}://{host}{port}"


def _validate_messages(messages: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in messages:
        if not isinstance(item, dict):
            raise FreeLLMAPIError("FREELLMAPI_MESSAGE_MUST_BE_OBJECT")
        role = str(item.get("role") or "").strip()
        content = item.get("content")
        if role not in {"system", "user", "assistant", "tool"}:
            raise FreeLLMAPIError("FREELLMAPI_MESSAGE_ROLE_INVALID")
        if not isinstance(content, str) or not content.strip():
            raise FreeLLMAPIError("FREELLMAPI_MESSAGE_CONTENT_REQUIRED")
        rows.append({"role": role, "content": content})
    if not rows:
        raise FreeLLMAPIError("FREELLMAPI_MESSAGES_REQUIRED")
    return rows


class FreeLLMAPIClient:
    """Hazewave subordinate client for a locally hosted FreeLLMAPI gateway.

    The gateway is an execution substrate only. Hazewave Harness remains the
    project authority and must authorize the task/capability before provider
    egress occurs.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        api_key: str | None,
        timeout_seconds: float = 120.0,
        allow_remote: bool = False,
    ) -> None:
        self.base_url = _normalized_base_url(base_url, allow_remote=allow_remote)
        self.origin = _origin_from_base_url(self.base_url)
        self.api_key = str(api_key or "").strip() or None
        headers: dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "FreeLLMAPIClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def health(self) -> bool:
        try:
            response = self._client.get(f"{self.origin}/api/ping")
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    def models(self) -> list[dict[str, Any]]:
        if not self.api_key:
            raise FreeLLMAPIError("FREELLMAPI_UNIFIED_API_KEY_REQUIRED")
        response = self._client.get("models")
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise FreeLLMAPIError("FREELLMAPI_MODELS_RESPONSE_INVALID")
        return [dict(item) for item in data if isinstance(item, dict)]

    def chat(
        self,
        *,
        messages: Iterable[dict[str, Any]],
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        model: str = "auto",
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> FreeLLMAPICompletionResult:
        classification = str(data_classification or "").strip().upper()
        if classification not in _ALLOWED_EGRESS_CLASSES:
            raise FreeLLMAPIError(
                f"DATA_CLASS_NOT_ALLOWED_FOR_FREELLMAPI:{classification or 'MISSING'}"
            )
        if not self.api_key:
            raise FreeLLMAPIError("FREELLMAPI_UNIFIED_API_KEY_REQUIRED")
        validate_authorization(
            authorization,
            expected_task_id=str(task_id),
            expected_capability=str(capability_id),
        )
        rows = _validate_messages(messages)
        payload: dict[str, Any] = {
            "model": str(model or "auto").strip() or "auto",
            "messages": rows,
            "stream": False,
        }
        if temperature is not None:
            payload["temperature"] = float(temperature)
        if max_tokens is not None:
            if int(max_tokens) < 1:
                raise FreeLLMAPIError("FREELLMAPI_MAX_TOKENS_INVALID")
            payload["max_tokens"] = int(max_tokens)

        try:
            response = self._client.post("chat/completions", json=payload)
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FreeLLMAPIError(f"FREELLMAPI_REQUEST_FAILED:{type(exc).__name__}") from exc

        if not isinstance(raw, dict):
            raise FreeLLMAPIError("FREELLMAPI_RESPONSE_INVALID")
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise FreeLLMAPIError("FREELLMAPI_RESPONSE_MISSING_CHOICE")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise FreeLLMAPIError("FREELLMAPI_RESPONSE_MISSING_MESSAGE")
        content = message.get("content")
        if not isinstance(content, str):
            raise FreeLLMAPIError("FREELLMAPI_RESPONSE_CONTENT_INVALID")
        usage = raw.get("usage")
        return FreeLLMAPICompletionResult(
            content=content,
            served_model=(str(raw.get("model")) if raw.get("model") is not None else None),
            usage=dict(usage) if isinstance(usage, dict) else {},
            raw=raw,
            routed_via=(response.headers.get("X-Routed-Via") or None),
        )



def run_live_probe(
    *,
    api_key: str,
    task_id: str = "hazewave-freellmapi-live-proof",
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any]:
    """Execute one bounded real provider call and return a secret-free receipt."""

    from hazewave.harness import HazewaveTask, issue_authorization, route_task

    task = HazewaveTask(
        task_id=str(task_id),
        goal="Analyze a synthetic non-secret sonic descriptor as a provider connectivity proof.",
        required_capability="audio.analyze",
        requested_domain="HAZE",
    )
    decision = route_task(task)
    authorization = issue_authorization(decision)

    with FreeLLMAPIClient(base_url, api_key=api_key) as client:
        result = client.chat(
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Synthetic sonic descriptor: 120 BPM, C minor, 4/4, "
                        "steady kick on quarter notes. Return one concise structural observation."
                    ),
                }
            ],
            authorization=authorization,
            task_id=task.task_id,
            capability_id=task.required_capability,
            data_classification="INTERNAL_NON_SECRET",
            model="auto",
            temperature=0.0,
            max_tokens=64,
        )

    return {
        "schema": "HazewaveProviderProbeReceipt/v1",
        "status": "PASS",
        "project_id": "HAZEWAVE",
        "authority": AUTHORITY,
        "task_id": task.task_id,
        "authorization_id": authorization.authorization_id,
        "capability_id": task.required_capability,
        "domain": decision.selected_domain,
        "data_classification": "INTERNAL_NON_SECRET",
        "provider_gateway": result.provider_gateway,
        "routed_via": result.routed_via,
        "served_model": result.served_model,
        "content_sha256": sha256(result.content.encode("utf-8")).hexdigest(),
        "usage": result.usage,
    }
