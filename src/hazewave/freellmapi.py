from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable
from urllib.parse import urlparse

import httpx

from hazewave.harness import AUTHORITY, HazewaveAuthorization, validate_authorization
from hazewave.provider_policy import (
    MediaEgressGrant,
    ProviderEligibilityDecision,
    evaluate_provider_eligibility,
    load_provider_registry,
)


FREELLMAPI_REPOSITORY = "https://github.com/tashfeenahmed/freellmapi.git"
FREELLMAPI_VERSION = "v0.13.4"
FREELLMAPI_PINNED_REF = "716948f20b12ec1c9b7c6fcebd22a3e7233cda1b"
DEFAULT_BASE_URL = "http://127.0.0.1:3001/v1"
DEFAULT_LOCAL_DB_PATH = (
    Path.home()
    / ".local"
    / "state"
    / "hazewave"
    / "providers"
    / "freellmapi"
    / "freellmapi.db"
)

_ALLOWED_EGRESS_CLASSES = frozenset({"PUBLIC"})
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
    receipt: dict[str, Any] | None = None


@dataclass(frozen=True)
class FreeLLMAPIModelCandidate:
    provider: str
    model_id: str
    display_name: str
    intelligence_rank: int
    speed_rank: int
    context_window: int | None
    supports_vision: bool
    supports_tools: bool

    @property
    def qualified_model_id(self) -> str:
        return f"{self.provider}:{self.model_id}"


class FreeLLMAPILocalCatalog:
    """Read-only view of the managed FreeLLMAPI SQLite model catalog.

    This reader never selects encrypted key material. It exists only because
    FreeLLMAPI's public /v1/models surface deliberately unifies provider copies,
    while Hazewave governance must bind execution to an exact provider.
    """

    def __init__(self, db_path: str | Path = DEFAULT_LOCAL_DB_PATH) -> None:
        self.db_path = Path(db_path).expanduser()

    def _connect(self) -> sqlite3.Connection:
        if not self.db_path.is_file():
            raise FreeLLMAPIError(f"FREELLMAPI_LOCAL_CATALOG_MISSING:{self.db_path}")
        uri = self.db_path.resolve().as_uri() + "?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    def chat_candidates(self) -> list[FreeLLMAPIModelCandidate]:
        try:
            with self._connect() as db:
                rows = db.execute(
                    """
                    SELECT
                      m.platform,
                      m.model_id,
                      m.display_name,
                      m.intelligence_rank,
                      m.speed_rank,
                      m.context_window,
                      m.supports_vision,
                      m.supports_tools
                    FROM models m
                    WHERE m.enabled = 1
                      AND EXISTS (
                        SELECT 1
                        FROM api_keys k
                        WHERE k.platform = m.platform
                          AND k.enabled = 1
                          AND (m.key_id IS NULL OR k.id = m.key_id)
                      )
                    ORDER BY
                      m.intelligence_rank ASC,
                      m.speed_rank ASC,
                      m.id ASC
                    """
                ).fetchall()
        except sqlite3.Error as exc:
            raise FreeLLMAPIError(
                f"FREELLMAPI_LOCAL_CATALOG_SCHEMA_INVALID:{type(exc).__name__}"
            ) from exc

        return [
            FreeLLMAPIModelCandidate(
                provider=str(row["platform"]),
                model_id=str(row["model_id"]),
                display_name=str(row["display_name"]),
                intelligence_rank=int(row["intelligence_rank"]),
                speed_rank=int(row["speed_rank"]),
                context_window=(
                    int(row["context_window"])
                    if row["context_window"] is not None
                    else None
                ),
                supports_vision=bool(row["supports_vision"]),
                supports_tools=bool(row["supports_tools"]),
            )
            for row in rows
        ]


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

    def models(self, *, available_only: bool = False) -> list[dict[str, Any]]:
        if not self.api_key:
            raise FreeLLMAPIError("FREELLMAPI_UNIFIED_API_KEY_REQUIRED")
        params = {"available": "true"} if available_only else None
        response = self._client.get("models", params=params)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise FreeLLMAPIError("FREELLMAPI_MODELS_RESPONSE_INVALID")
        return [dict(item) for item in data if isinstance(item, dict)]

    def governed_chat(
        self,
        *,
        messages: Iterable[dict[str, Any]],
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        model: str | None = None,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        media_grant: MediaEgressGrant | None = None,
        asset_digest: str | None = None,
    ) -> FreeLLMAPICompletionResult:
        """Execute a policy-bound chat call with provider-qualified routing.

        Unrestricted FreeLLMAPI auto-routing is intentionally not accepted here.
        Every attempted model is evaluated by Hazewave before provider egress.
        """

        validate_authorization(
            authorization,
            expected_task_id=str(task_id),
            expected_capability=str(capability_id),
        )
        classification = str(data_classification or "").strip().upper()
        rows = _validate_messages(messages)
        policy_registry = registry if registry is not None else load_provider_registry()

        candidates: list[tuple[FreeLLMAPIModelCandidate, ProviderEligibilityDecision]] = []

        if model is not None:
            requested = str(model).strip()
            if requested.casefold() == "auto" or requested.casefold().startswith("auto:"):
                raise FreeLLMAPIError("FREELLMAPI_UNRESTRICTED_AUTO_FORBIDDEN")
            if ":" not in requested:
                raise FreeLLMAPIError("FREELLMAPI_PROVIDER_QUALIFIED_MODEL_REQUIRED")
            provider, model_id = requested.split(":", 1)
            candidate = FreeLLMAPIModelCandidate(
                provider=provider,
                model_id=model_id,
                display_name=model_id,
                intelligence_rank=0,
                speed_rank=0,
                context_window=None,
                supports_vision=False,
                supports_tools=False,
            )
            decision = evaluate_provider_eligibility(
                provider=candidate.provider,
                model_id=candidate.model_id,
                capability_id=capability_id,
                modality="text",
                data_classification=classification,
                registry=policy_registry,
                media_grant=media_grant,
                task_id=task_id,
                authorization_id=authorization.authorization_id,
                asset_digest=asset_digest,
            )
            if not decision.allowed:
                raise FreeLLMAPIError(f"FREELLMAPI_ROUTE_DENIED:{decision.reason}")
            candidates.append((candidate, decision))
        else:
            source = catalog if catalog is not None else FreeLLMAPILocalCatalog()
            for candidate in source.chat_candidates():
                decision = evaluate_provider_eligibility(
                    provider=candidate.provider,
                    model_id=candidate.model_id,
                    capability_id=capability_id,
                    modality="text",
                    data_classification=classification,
                    registry=policy_registry,
                    media_grant=media_grant,
                    task_id=task_id,
                    authorization_id=authorization.authorization_id,
                    asset_digest=asset_digest,
                )
                if decision.allowed:
                    candidates.append((candidate, decision))

        if not candidates:
            raise FreeLLMAPIError("FREELLMAPI_ZERO_COST_POOL_UNAVAILABLE")

        canonical_input = json.dumps(
            rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        last_error: FreeLLMAPIError | None = None

        for candidate, decision in candidates:
            try:
                result = self.chat(
                    messages=rows,
                    authorization=authorization,
                    task_id=task_id,
                    capability_id=capability_id,
                    data_classification=classification,
                    model=candidate.qualified_model_id,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except FreeLLMAPIError as exc:
                last_error = exc
                continue

            receipt = {
                "schema": "HazewaveProviderExecutionReceipt/v1",
                "status": "PASS",
                "project_id": "HAZEWAVE",
                "authority": AUTHORITY,
                "task_id": str(task_id),
                "authorization_id": authorization.authorization_id,
                "capability_id": str(capability_id),
                "domain": authorization.domain,
                "data_classification": classification,
                "provider_gateway": "FREELLMAPI",
                "provider": candidate.provider,
                "requested_model": candidate.qualified_model_id,
                "served_model": result.served_model,
                "routed_via": result.routed_via,
                "trust_lane": decision.trust_lane,
                "zero_cost_verified": decision.zero_cost_verified,
                "usage": result.usage,
                "input_sha256": sha256(canonical_input).hexdigest(),
                "output_sha256": sha256(result.content.encode("utf-8")).hexdigest(),
                "media_egress_grant_id": decision.media_egress_grant_id,
            }
            return replace(result, receipt=receipt)

        if last_error is not None:
            raise FreeLLMAPIError(
                f"FREELLMAPI_ZERO_COST_POOL_EXHAUSTED:{last_error}"
            ) from last_error
        raise FreeLLMAPIError("FREELLMAPI_ZERO_COST_POOL_EXHAUSTED")

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
        except httpx.HTTPStatusError as exc:
            code = "unknown"
            try:
                body = exc.response.json()
                if isinstance(body, dict):
                    error = body.get("error")
                    if isinstance(error, dict) and error.get("code"):
                        code = str(error["code"])
            except ValueError:
                pass
            raise FreeLLMAPIError(
                f"FREELLMAPI_REQUEST_FAILED:HTTP_{exc.response.status_code}:{code}"
            ) from exc
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
        available = client.models(available_only=True)
        if not available:
            raise FreeLLMAPIError("FREELLMAPI_NO_AVAILABLE_MODELS")
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
            data_classification="PUBLIC",
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
        "data_classification": "PUBLIC",
        "provider_gateway": result.provider_gateway,
        "routed_via": result.routed_via,
        "served_model": result.served_model,
        "content_sha256": sha256(result.content.encode("utf-8")).hexdigest(),
        "usage": result.usage,
    }
