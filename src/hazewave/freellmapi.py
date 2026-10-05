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


@dataclass(frozen=True)
class FreeLLMAPIEmbeddingCandidate:
    family: str
    provider: str
    model_id: str
    display_name: str
    dimensions: int
    max_input_tokens: int | None
    priority: int


@dataclass(frozen=True)
class FreeLLMAPIEmbeddingFamily:
    family: str
    dimensions: int
    members: tuple[FreeLLMAPIEmbeddingCandidate, ...]


@dataclass(frozen=True)
class FreeLLMAPIMediaCandidate:
    provider: str
    model_id: str
    display_name: str
    modality: str
    priority: int


@dataclass(frozen=True)
class FreeLLMAPIProviderResult:
    raw: Any
    content_type: str | None
    receipt: dict[str, Any]


class FreeLLMAPIStream:
    """One governed OpenAI-compatible SSE stream.

    The stream emits text deltas. Its secret-free execution receipt becomes
    available only after the iterator is exhausted successfully.
    """

    def __init__(
        self,
        *,
        client: httpx.Client,
        payload: dict[str, Any],
        headers: dict[str, str],
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        candidate: FreeLLMAPIModelCandidate,
        decision: ProviderEligibilityDecision,
        input_value: Any,
    ) -> None:
        self._client = client
        self._payload = payload
        self._headers = headers
        self._authorization = authorization
        self._task_id = task_id
        self._capability_id = capability_id
        self._classification = str(data_classification).upper()
        self._candidate = candidate
        self._decision = decision
        self._input_value = input_value
        self.receipt: dict[str, Any] | None = None

    def __iter__(self):
        chunks: list[str] = []
        routed_via: str | None = None
        served_model: str | None = None
        try:
            with self._client.stream(
                "POST",
                "chat/completions",
                json=self._payload,
                headers=self._headers,
            ) as response:
                response.raise_for_status()
                routed_via = response.headers.get("X-Routed-Via") or None
                if routed_via and not routed_via.casefold().startswith(
                    self._candidate.provider.casefold() + "/"
                ):
                    raise FreeLLMAPIError("FREELLMAPI_PROVIDER_ROUTE_MISMATCH")
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        event = json.loads(data)
                    except ValueError as exc:
                        raise FreeLLMAPIError("FREELLMAPI_STREAM_EVENT_INVALID") from exc
                    if not isinstance(event, dict):
                        continue
                    if event.get("model") is not None:
                        served_model = str(event.get("model"))
                    choices = event.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    choice = choices[0]
                    if not isinstance(choice, dict):
                        continue
                    delta = choice.get("delta")
                    if not isinstance(delta, dict):
                        continue
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        chunks.append(content)
                        yield content
        except httpx.HTTPError as exc:
            raise FreeLLMAPIError(
                f"FREELLMAPI_STREAM_REQUEST_FAILED:{type(exc).__name__}"
            ) from exc

        output = "".join(chunks)
        self.receipt = {
            "schema": "HazewaveProviderExecutionReceipt/v1",
            "status": "PASS",
            "project_id": "HAZEWAVE",
            "authority": AUTHORITY,
            "task_id": self._task_id,
            "authorization_id": self._authorization.authorization_id,
            "capability_id": self._capability_id,
            "domain": self._authorization.domain,
            "data_classification": self._classification,
            "provider_gateway": "FREELLMAPI",
            "provider": self._candidate.provider,
            "requested_model": self._candidate.qualified_model_id,
            "served_model": served_model,
            "routed_via": routed_via,
            "trust_lane": self._decision.trust_lane,
            "zero_cost_verified": self._decision.zero_cost_verified,
            "input_sha256": sha256(
                json.dumps(
                    self._input_value,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                ).encode("utf-8")
            ).hexdigest(),
            "output_sha256": sha256(output.encode("utf-8")).hexdigest(),
        }


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

    @staticmethod
    def _has_enabled_key(
        db: sqlite3.Connection, provider: str, key_id: int | None
    ) -> bool:
        row = db.execute(
            """
            SELECT 1
            FROM api_keys
            WHERE platform = ?
              AND enabled = 1
              AND (? IS NULL OR id = ?)
            LIMIT 1
            """,
            (provider, key_id, key_id),
        ).fetchone()
        return row is not None

    def embedding_candidates(self) -> list[FreeLLMAPIEmbeddingCandidate]:
        try:
            with self._connect() as db:
                rows = db.execute(
                    """
                    SELECT
                      family,
                      platform,
                      model_id,
                      display_name,
                      dimensions,
                      max_input_tokens,
                      priority,
                      key_id
                    FROM embedding_models
                    WHERE enabled = 1
                    ORDER BY family, priority, id
                    """
                ).fetchall()
                out: list[FreeLLMAPIEmbeddingCandidate] = []
                for row in rows:
                    if not self._has_enabled_key(
                        db,
                        str(row["platform"]),
                        int(row["key_id"]) if row["key_id"] is not None else None,
                    ):
                        continue
                    out.append(
                        FreeLLMAPIEmbeddingCandidate(
                            family=str(row["family"]),
                            provider=str(row["platform"]),
                            model_id=str(row["model_id"]),
                            display_name=str(row["display_name"]),
                            dimensions=int(row["dimensions"]),
                            max_input_tokens=(
                                int(row["max_input_tokens"])
                                if row["max_input_tokens"] is not None
                                else None
                            ),
                            priority=int(row["priority"]),
                        )
                    )
                return out
        except sqlite3.Error as exc:
            raise FreeLLMAPIError(
                f"FREELLMAPI_LOCAL_CATALOG_SCHEMA_INVALID:{type(exc).__name__}"
            ) from exc

    def eligible_embedding_families(
        self,
        *,
        capability_id: str,
        data_classification: str,
        registry: dict[str, Any] | None = None,
    ) -> list[FreeLLMAPIEmbeddingFamily]:
        policy_registry = registry if registry is not None else load_provider_registry()
        grouped: dict[str, list[FreeLLMAPIEmbeddingCandidate]] = {}
        for candidate in self.embedding_candidates():
            grouped.setdefault(candidate.family, []).append(candidate)

        eligible: list[FreeLLMAPIEmbeddingFamily] = []
        for family, members in grouped.items():
            dimensions = {member.dimensions for member in members}
            if len(dimensions) != 1:
                continue
            decisions = [
                evaluate_provider_eligibility(
                    provider=member.provider,
                    model_id=member.model_id,
                    capability_id=capability_id,
                    modality="embedding",
                    data_classification=data_classification,
                    registry=policy_registry,
                )
                for member in members
            ]
            # FreeLLMAPI embeddings fail over across every provider serving a
            # family. One ineligible member therefore makes the whole family
            # unsafe for a governed request.
            if not decisions or not all(decision.allowed for decision in decisions):
                continue
            ordered = tuple(sorted(members, key=lambda item: (item.priority, item.provider, item.model_id)))
            eligible.append(
                FreeLLMAPIEmbeddingFamily(
                    family=family,
                    dimensions=next(iter(dimensions)),
                    members=ordered,
                )
            )
        return sorted(
            eligible,
            key=lambda item: (
                min(member.priority for member in item.members),
                item.family,
            ),
        )

    def media_candidates(self, modality: str) -> list[FreeLLMAPIMediaCandidate]:
        db_modality = "audio" if modality == "speech" else modality
        try:
            with self._connect() as db:
                rows = db.execute(
                    """
                    SELECT platform, model_id, display_name, modality, priority, key_id
                    FROM media_models
                    WHERE modality = ? AND enabled = 1
                    ORDER BY priority, id
                    """,
                    (db_modality,),
                ).fetchall()
                out: list[FreeLLMAPIMediaCandidate] = []
                for row in rows:
                    provider = str(row["platform"])
                    key_id = int(row["key_id"]) if row["key_id"] is not None else None
                    routable = provider == "pollinations" or self._has_enabled_key(
                        db, provider, key_id
                    )
                    if not routable:
                        continue
                    out.append(
                        FreeLLMAPIMediaCandidate(
                            provider=provider,
                            model_id=str(row["model_id"]),
                            display_name=str(row["display_name"]),
                            modality=str(row["modality"]),
                            priority=int(row["priority"]),
                        )
                    )
                return out
        except sqlite3.Error as exc:
            raise FreeLLMAPIError(
                f"FREELLMAPI_LOCAL_CATALOG_SCHEMA_INVALID:{type(exc).__name__}"
            ) from exc

    def eligible_media_candidates(
        self,
        *,
        modality: str,
        capability_id: str,
        data_classification: str,
        registry: dict[str, Any] | None = None,
        media_grant: MediaEgressGrant | None = None,
        task_id: str | None = None,
        authorization_id: str | None = None,
        asset_digest: str | None = None,
    ) -> list[tuple[FreeLLMAPIMediaCandidate, ProviderEligibilityDecision]]:
        policy_registry = registry if registry is not None else load_provider_registry()
        candidates = self.media_candidates(modality)

        counts: dict[str, int] = {}
        for candidate in candidates:
            counts[candidate.model_id] = counts.get(candidate.model_id, 0) + 1
        ambiguous = sorted(model_id for model_id, count in counts.items() if count > 1)
        if ambiguous:
            raise FreeLLMAPIError(
                "FREELLMAPI_AMBIGUOUS_MEDIA_MODEL:" + ",".join(ambiguous)
            )

        eligible: list[tuple[FreeLLMAPIMediaCandidate, ProviderEligibilityDecision]] = []
        for candidate in candidates:
            decision = evaluate_provider_eligibility(
                provider=candidate.provider,
                model_id=candidate.model_id,
                capability_id=capability_id,
                modality=modality,
                data_classification=data_classification,
                registry=policy_registry,
                media_grant=media_grant,
                task_id=task_id,
                authorization_id=authorization_id,
                asset_digest=asset_digest,
            )
            if decision.allowed:
                eligible.append((candidate, decision))
        return eligible


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
        tools: Iterable[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
        response_format: dict[str, Any] | None = None,
        cache: bool | None = None,
        compression: str | None = None,
        task_type: str | None = None,
        session_id: str | None = None,
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
                if tools is not None and not candidate.supports_tools:
                    continue
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
                    tools=tools,
                    tool_choice=tool_choice,
                    response_format=response_format,
                    request_headers=self._efficiency_headers(
                        cache=cache,
                        compression=compression,
                        task_type=task_type,
                        session_id=session_id,
                    ),
                )
            except FreeLLMAPIError as exc:
                last_error = exc
                continue

            self._assert_routed_provider(result.routed_via, candidate.provider)
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
                "tool_execution_authority": AUTHORITY if tools is not None else None,
                "cache_requested": cache,
                "compression_requested": compression,
                "task_type_requested": task_type,
                "session_id_sha256": (
                    sha256(session_id.encode("utf-8")).hexdigest()
                    if session_id is not None
                    else None
                ),
            }
            return replace(result, receipt=receipt)

        if last_error is not None:
            raise FreeLLMAPIError(
                f"FREELLMAPI_ZERO_COST_POOL_EXHAUSTED:{last_error}"
            ) from last_error
        raise FreeLLMAPIError("FREELLMAPI_ZERO_COST_POOL_EXHAUSTED")

    @staticmethod
    def _efficiency_headers(
        *,
        cache: bool | None = None,
        compression: str | None = None,
        task_type: str | None = None,
        session_id: str | None = None,
    ) -> dict[str, str]:
        headers: dict[str, str] = {}
        if cache is not None:
            headers["X-FreeLLM-Cache"] = "on" if cache else "off"
        if compression is not None:
            mode = str(compression).strip().lower()
            if mode not in {"off", "on", "lossless", "standard", "aggressive"}:
                raise FreeLLMAPIError("FREELLMAPI_COMPRESSION_MODE_INVALID")
            headers["X-FreeLLM-Compress"] = mode
        if task_type is not None:
            kind = str(task_type).strip().lower()
            if kind not in {"auto", "code", "chat"}:
                raise FreeLLMAPIError("FREELLMAPI_TASK_TYPE_INVALID")
            headers["X-FreeLLM-Task-Type"] = kind
        if session_id is not None:
            session = str(session_id).strip()
            if not session or len(session) > 256:
                raise FreeLLMAPIError("FREELLMAPI_SESSION_ID_INVALID")
            headers["X-Session-Id"] = session
        return headers

    def _eligible_text_candidates(
        self,
        *,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None,
        registry: dict[str, Any] | None,
        require_vision: bool = False,
        require_tools: bool = False,
        modality: str = "text",
        media_grant: MediaEgressGrant | None = None,
        task_id: str | None = None,
        authorization_id: str | None = None,
        asset_digest: str | None = None,
    ) -> list[tuple[FreeLLMAPIModelCandidate, ProviderEligibilityDecision]]:
        source = catalog if catalog is not None else FreeLLMAPILocalCatalog()
        policy_registry = registry if registry is not None else load_provider_registry()
        eligible: list[tuple[FreeLLMAPIModelCandidate, ProviderEligibilityDecision]] = []
        for candidate in source.chat_candidates():
            if require_vision and not candidate.supports_vision:
                continue
            if require_tools and not candidate.supports_tools:
                continue
            decision = evaluate_provider_eligibility(
                provider=candidate.provider,
                model_id=candidate.model_id,
                capability_id=capability_id,
                modality=modality,
                data_classification=data_classification,
                registry=policy_registry,
                media_grant=media_grant,
                task_id=task_id,
                authorization_id=authorization_id,
                asset_digest=asset_digest,
            )
            if decision.allowed:
                eligible.append((candidate, decision))
        return eligible

    @staticmethod
    def _assert_routed_provider(routed_via: str | None, provider: str) -> None:
        if routed_via and not routed_via.casefold().startswith(provider.casefold() + "/"):
            raise FreeLLMAPIError("FREELLMAPI_PROVIDER_ROUTE_MISMATCH")

    def governed_vision(
        self,
        *,
        prompt: str,
        image_url: str,
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        media_grant: MediaEgressGrant | None = None,
        asset_digest: str | None = None,
    ) -> FreeLLMAPICompletionResult:
        validate_authorization(
            authorization,
            expected_task_id=str(task_id),
            expected_capability=str(capability_id),
        )
        if not str(prompt).strip() or not str(image_url).strip():
            raise FreeLLMAPIError("FREELLMAPI_VISION_INPUT_REQUIRED")
        eligible = self._eligible_text_candidates(
            capability_id=capability_id,
            data_classification=data_classification,
            catalog=catalog,
            registry=registry,
            require_vision=True,
            modality="vision",
            media_grant=media_grant,
            task_id=task_id,
            authorization_id=authorization.authorization_id,
            asset_digest=asset_digest,
        )
        if not eligible:
            raise FreeLLMAPIError("FREELLMAPI_ZERO_COST_VISION_POOL_UNAVAILABLE")
        candidate, decision = eligible[0]
        blocks = [
            {"type": "text", "text": str(prompt)},
            {"type": "image_url", "image_url": {"url": str(image_url)}},
        ]
        payload = {
            "model": candidate.qualified_model_id,
            "messages": [{"role": "user", "content": blocks}],
            "stream": False,
        }
        try:
            response = self._client.post("chat/completions", json=payload)
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FreeLLMAPIError(f"FREELLMAPI_VISION_REQUEST_FAILED:{type(exc).__name__}") from exc
        if not isinstance(raw, dict):
            raise FreeLLMAPIError("FREELLMAPI_VISION_RESPONSE_INVALID")
        choices = raw.get("choices")
        message = choices[0].get("message") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise FreeLLMAPIError("FREELLMAPI_VISION_RESPONSE_CONTENT_INVALID")
        routed_via = response.headers.get("X-Routed-Via") or None
        self._assert_routed_provider(routed_via, candidate.provider)
        usage = dict(raw.get("usage") or {}) if isinstance(raw.get("usage"), dict) else {}
        receipt = self._receipt_base(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            provider=candidate.provider,
            requested_model=candidate.qualified_model_id,
            trust_lane=decision.trust_lane,
            input_value={"prompt": prompt, "image_ref": asset_digest or image_url},
            output_value=content,
            media_egress_grant_id=decision.media_egress_grant_id,
        )
        receipt.update({"usage": usage, "routed_via": routed_via})
        return FreeLLMAPICompletionResult(
            content=content,
            served_model=str(raw.get("model")) if raw.get("model") is not None else None,
            usage=usage,
            raw=raw,
            routed_via=routed_via,
            receipt=receipt,
        )

    def _select_compat_candidate(
        self,
        *,
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None,
        registry: dict[str, Any] | None,
    ) -> tuple[FreeLLMAPIModelCandidate, ProviderEligibilityDecision]:
        validate_authorization(
            authorization,
            expected_task_id=str(task_id),
            expected_capability=str(capability_id),
        )
        eligible = self._eligible_text_candidates(
            capability_id=capability_id,
            data_classification=data_classification,
            catalog=catalog,
            registry=registry,
        )
        if not eligible:
            raise FreeLLMAPIError("FREELLMAPI_ZERO_COST_POOL_UNAVAILABLE")
        return eligible[0]

    def governed_gemini_generate_content(
        self,
        *,
        contents: Iterable[dict[str, Any]],
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        system_instruction: dict[str, Any] | None = None,
        generation_config: dict[str, Any] | None = None,
        tools: Iterable[dict[str, Any]] | None = None,
    ) -> FreeLLMAPIProviderResult:
        """Use FreeLLMAPI's native Gemini wire without surrendering routing policy."""

        candidate, decision = self._select_compat_candidate(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            catalog=catalog,
            registry=registry,
        )
        rows = list(contents)
        if not rows:
            raise FreeLLMAPIError("FREELLMAPI_GEMINI_CONTENTS_REQUIRED")
        payload: dict[str, Any] = {"contents": rows}
        if system_instruction is not None:
            payload["systemInstruction"] = dict(system_instruction)
        if generation_config is not None:
            payload["generationConfig"] = dict(generation_config)
        if tools is not None:
            payload["tools"] = list(tools)

        try:
            response = self._client.post(
                f"/v1beta/models/{candidate.qualified_model_id}:generateContent",
                json=payload,
            )
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FreeLLMAPIError(
                f"FREELLMAPI_GEMINI_REQUEST_FAILED:{type(exc).__name__}"
            ) from exc
        if not isinstance(raw, dict):
            raise FreeLLMAPIError("FREELLMAPI_GEMINI_RESPONSE_INVALID")
        routed_via = response.headers.get("X-Routed-Via") or None
        self._assert_routed_provider(routed_via, candidate.provider)
        receipt = self._receipt_base(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            provider=candidate.provider,
            requested_model=candidate.qualified_model_id,
            trust_lane=decision.trust_lane,
            input_value=payload,
            output_value=raw,
        )
        receipt.update(
            {
                "routed_via": routed_via,
                "wire_surface": "GEMINI_V1BETA",
                "usage": (
                    dict(raw.get("usageMetadata") or {})
                    if isinstance(raw.get("usageMetadata"), dict)
                    else {}
                ),
            }
        )
        return FreeLLMAPIProviderResult(
            raw=raw,
            content_type=response.headers.get("Content-Type"),
            receipt=receipt,
        )

    def governed_ollama_chat(
        self,
        *,
        messages: Iterable[dict[str, Any]],
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        tools: Iterable[dict[str, Any]] | None = None,
        options: dict[str, Any] | None = None,
        response_format: str | dict[str, Any] | None = None,
    ) -> FreeLLMAPIProviderResult:
        """Use the Ollama-compatible loopback surface with an explicit eligible model."""

        candidate, decision = self._select_compat_candidate(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            catalog=catalog,
            registry=registry,
        )
        rows = _validate_messages(messages)
        payload: dict[str, Any] = {
            "model": candidate.qualified_model_id,
            "messages": rows,
            "stream": False,
        }
        if tools is not None:
            payload["tools"] = list(tools)
        if options is not None:
            payload["options"] = dict(options)
        if response_format is not None:
            payload["format"] = response_format

        try:
            response = self._client.post("/api/chat", json=payload)
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FreeLLMAPIError(
                f"FREELLMAPI_OLLAMA_REQUEST_FAILED:{type(exc).__name__}"
            ) from exc
        if not isinstance(raw, dict):
            raise FreeLLMAPIError("FREELLMAPI_OLLAMA_RESPONSE_INVALID")
        routed_via = response.headers.get("X-Routed-Via") or None
        self._assert_routed_provider(routed_via, candidate.provider)
        receipt = self._receipt_base(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            provider=candidate.provider,
            requested_model=candidate.qualified_model_id,
            trust_lane=decision.trust_lane,
            input_value=rows,
            output_value=raw,
        )
        receipt.update({"routed_via": routed_via, "wire_surface": "OLLAMA_API"})
        return FreeLLMAPIProviderResult(
            raw=raw,
            content_type=response.headers.get("Content-Type"),
            receipt=receipt,
        )

    def mcp_readonly(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call only FreeLLMAPI MCP observability tools.

        Inference and state mutation are deliberately excluded: model execution
        stays behind Hazewave authorization and routing policy, while routing
        mutations remain project-governed.
        """

        allowed = frozenset(
            {
                "healthcheck",
                "list_models",
                "provider_health",
                "usage_summary",
                "routing_info",
                "cache_stats",
                "compression_stats",
            }
        )
        name = str(tool_name or "").strip()
        if name not in allowed:
            raise FreeLLMAPIError("FREELLMAPI_MCP_TOOL_NOT_ALLOWED")

        payload = {
            "jsonrpc": "2.0",
            "id": "hazewave-observe-1",
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": dict(arguments or {}),
            },
        }
        try:
            response = self._client.post("/mcp", json=payload)
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FreeLLMAPIError(
                f"FREELLMAPI_MCP_REQUEST_FAILED:{type(exc).__name__}"
            ) from exc
        if not isinstance(raw, dict):
            raise FreeLLMAPIError("FREELLMAPI_MCP_RESPONSE_INVALID")
        if isinstance(raw.get("error"), dict):
            message = str(raw["error"].get("message") or "unknown")
            raise FreeLLMAPIError(f"FREELLMAPI_MCP_ERROR:{message}")
        return raw

    def governed_responses(
        self,
        *,
        input_data: Any,
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        instructions: str | None = None,
        max_output_tokens: int | None = None,
    ) -> FreeLLMAPIProviderResult:
        candidate, decision = self._select_compat_candidate(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            catalog=catalog,
            registry=registry,
        )
        payload: dict[str, Any] = {
            "model": candidate.qualified_model_id,
            "input": input_data,
            "stream": False,
        }
        if instructions is not None:
            payload["instructions"] = str(instructions)
        if max_output_tokens is not None:
            payload["max_output_tokens"] = int(max_output_tokens)
        try:
            response = self._client.post("responses", json=payload)
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FreeLLMAPIError(f"FREELLMAPI_RESPONSES_REQUEST_FAILED:{type(exc).__name__}") from exc
        routed_via = response.headers.get("X-Routed-Via") or None
        self._assert_routed_provider(routed_via, candidate.provider)
        receipt = self._receipt_base(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            provider=candidate.provider,
            requested_model=candidate.qualified_model_id,
            trust_lane=decision.trust_lane,
            input_value=input_data,
            output_value=raw,
        )
        receipt["routed_via"] = routed_via
        return FreeLLMAPIProviderResult(raw=raw, content_type=response.headers.get("Content-Type"), receipt=receipt)

    def governed_completion(
        self,
        *,
        prompt: str,
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        suffix: str | None = None,
        max_tokens: int | None = None,
    ) -> FreeLLMAPIProviderResult:
        candidate, decision = self._select_compat_candidate(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            catalog=catalog,
            registry=registry,
        )
        payload: dict[str, Any] = {
            "model": candidate.qualified_model_id,
            "prompt": str(prompt),
            "stream": False,
        }
        if suffix is not None:
            payload["suffix"] = str(suffix)
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        try:
            response = self._client.post("completions", json=payload)
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FreeLLMAPIError(f"FREELLMAPI_COMPLETION_REQUEST_FAILED:{type(exc).__name__}") from exc
        routed_via = response.headers.get("X-Routed-Via") or None
        self._assert_routed_provider(routed_via, candidate.provider)
        receipt = self._receipt_base(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            provider=candidate.provider,
            requested_model=candidate.qualified_model_id,
            trust_lane=decision.trust_lane,
            input_value=prompt,
            output_value=raw,
        )
        receipt["routed_via"] = routed_via
        return FreeLLMAPIProviderResult(raw=raw, content_type=response.headers.get("Content-Type"), receipt=receipt)

    def governed_anthropic_messages(
        self,
        *,
        messages: Iterable[dict[str, Any]],
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        max_tokens: int,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        system: str | None = None,
    ) -> FreeLLMAPIProviderResult:
        candidate, decision = self._select_compat_candidate(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            catalog=catalog,
            registry=registry,
        )
        rows = _validate_messages(messages)
        payload: dict[str, Any] = {
            "model": candidate.qualified_model_id,
            "messages": rows,
            "max_tokens": int(max_tokens),
            "stream": False,
        }
        if system is not None:
            payload["system"] = str(system)
        headers = {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
        }
        try:
            response = self._client.post("messages", json=payload, headers=headers)
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FreeLLMAPIError(f"FREELLMAPI_ANTHROPIC_REQUEST_FAILED:{type(exc).__name__}") from exc
        routed_via = response.headers.get("X-Routed-Via") or None
        self._assert_routed_provider(routed_via, candidate.provider)
        receipt = self._receipt_base(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            provider=candidate.provider,
            requested_model=candidate.qualified_model_id,
            trust_lane=decision.trust_lane,
            input_value=rows,
            output_value=raw,
        )
        receipt["routed_via"] = routed_via
        return FreeLLMAPIProviderResult(raw=raw, content_type=response.headers.get("Content-Type"), receipt=receipt)

    def governed_stream_chat(
        self,
        *,
        messages: Iterable[dict[str, Any]],
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        cache: bool | None = None,
        compression: str | None = None,
        task_type: str | None = None,
        session_id: str | None = None,
    ) -> FreeLLMAPIStream:
        validate_authorization(
            authorization,
            expected_task_id=str(task_id),
            expected_capability=str(capability_id),
        )
        rows = _validate_messages(messages)
        eligible = self._eligible_text_candidates(
            capability_id=capability_id,
            data_classification=data_classification,
            catalog=catalog,
            registry=registry,
        )
        if not eligible:
            raise FreeLLMAPIError("FREELLMAPI_ZERO_COST_POOL_UNAVAILABLE")
        candidate, decision = eligible[0]
        payload = {
            "model": candidate.qualified_model_id,
            "messages": rows,
            "stream": True,
        }
        return FreeLLMAPIStream(
            client=self._client,
            payload=payload,
            headers=self._efficiency_headers(
                cache=cache,
                compression=compression,
                task_type=task_type,
                session_id=session_id,
            ),
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            candidate=candidate,
            decision=decision,
            input_value=rows,
        )

    @staticmethod
    def _digest_payload(value: Any) -> str:
        if isinstance(value, bytes):
            payload = value
        elif isinstance(value, str):
            payload = value.encode("utf-8")
        else:
            payload = json.dumps(
                value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode("utf-8")
        return sha256(payload).hexdigest()

    @staticmethod
    def _receipt_base(
        *,
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        provider: str,
        requested_model: str,
        trust_lane: str,
        input_value: Any,
        output_value: Any,
        media_egress_grant_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "schema": "HazewaveProviderExecutionReceipt/v1",
            "status": "PASS",
            "project_id": "HAZEWAVE",
            "authority": AUTHORITY,
            "task_id": str(task_id),
            "authorization_id": authorization.authorization_id,
            "capability_id": str(capability_id),
            "domain": authorization.domain,
            "data_classification": str(data_classification).upper(),
            "provider_gateway": "FREELLMAPI",
            "provider": provider,
            "requested_model": requested_model,
            "trust_lane": trust_lane,
            "zero_cost_verified": True,
            "input_sha256": FreeLLMAPIClient._digest_payload(input_value),
            "output_sha256": FreeLLMAPIClient._digest_payload(output_value),
            "media_egress_grant_id": media_egress_grant_id,
        }

    def governed_embeddings(
        self,
        *,
        input_texts: str | Iterable[str],
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        family: str | None = None,
        dimensions: int | None = None,
    ) -> FreeLLMAPIProviderResult:
        validate_authorization(
            authorization,
            expected_task_id=str(task_id),
            expected_capability=str(capability_id),
        )
        inputs = [input_texts] if isinstance(input_texts, str) else list(input_texts)
        if not inputs or any(not isinstance(value, str) or not value for value in inputs):
            raise FreeLLMAPIError("FREELLMAPI_EMBEDDING_INPUT_REQUIRED")
        source = catalog if catalog is not None else FreeLLMAPILocalCatalog()
        families = source.eligible_embedding_families(
            capability_id=capability_id,
            data_classification=data_classification,
            registry=registry,
        )
        if family is not None:
            if str(family).casefold() == "auto":
                raise FreeLLMAPIError("FREELLMAPI_UNRESTRICTED_AUTO_FORBIDDEN")
            families = [item for item in families if item.family == str(family)]
        if not families:
            raise FreeLLMAPIError("FREELLMAPI_ZERO_COST_EMBEDDING_POOL_UNAVAILABLE")
        selected = families[0]

        payload: dict[str, Any] = {
            "model": selected.family,
            "input": inputs if len(inputs) > 1 else inputs[0],
        }
        expected_dimensions = selected.dimensions
        if dimensions is not None:
            if int(dimensions) < 1:
                raise FreeLLMAPIError("FREELLMAPI_EMBEDDING_DIMENSIONS_INVALID")
            payload["dimensions"] = int(dimensions)
            expected_dimensions = int(dimensions)

        try:
            response = self._client.post("embeddings", json=payload)
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FreeLLMAPIError(
                f"FREELLMAPI_EMBEDDING_REQUEST_FAILED:{type(exc).__name__}"
            ) from exc
        if not isinstance(raw, dict):
            raise FreeLLMAPIError("FREELLMAPI_EMBEDDING_RESPONSE_INVALID")
        provider = str(raw.get("provider") or "")
        member = next((item for item in selected.members if item.provider == provider), None)
        if member is None:
            raise FreeLLMAPIError("FREELLMAPI_EMBEDDING_PROVIDER_ESCAPED_ELIGIBLE_FAMILY")
        data = raw.get("data")
        if not isinstance(data, list) or not data:
            raise FreeLLMAPIError("FREELLMAPI_EMBEDDING_RESPONSE_MISSING_DATA")
        for item in data:
            vector = item.get("embedding") if isinstance(item, dict) else None
            if not isinstance(vector, list) or len(vector) != expected_dimensions:
                raise FreeLLMAPIError("FREELLMAPI_EMBEDDING_DIMENSION_MISMATCH")
        decision = evaluate_provider_eligibility(
            provider=member.provider,
            model_id=member.model_id,
            capability_id=capability_id,
            modality="embedding",
            data_classification=data_classification,
            registry=registry if registry is not None else load_provider_registry(),
        )
        receipt = self._receipt_base(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            provider=provider,
            requested_model=selected.family,
            trust_lane=decision.trust_lane,
            input_value=inputs,
            output_value=raw,
        )
        receipt.update(
            {
                "embedding_family": selected.family,
                "dimensions": expected_dimensions,
                "eligible_providers": [item.provider for item in selected.members],
                "usage": dict(raw.get("usage") or {}) if isinstance(raw.get("usage"), dict) else {},
            }
        )
        return FreeLLMAPIProviderResult(
            raw=raw,
            content_type=response.headers.get("Content-Type"),
            receipt=receipt,
        )

    def _select_media_candidate(
        self,
        *,
        modality: str,
        capability_id: str,
        data_classification: str,
        authorization: HazewaveAuthorization,
        task_id: str,
        catalog: FreeLLMAPILocalCatalog | None,
        registry: dict[str, Any] | None,
        media_grant: MediaEgressGrant | None,
        asset_digest: str | None,
    ) -> tuple[FreeLLMAPIMediaCandidate, ProviderEligibilityDecision]:
        validate_authorization(
            authorization,
            expected_task_id=str(task_id),
            expected_capability=str(capability_id),
        )
        source = catalog if catalog is not None else FreeLLMAPILocalCatalog()
        eligible = source.eligible_media_candidates(
            modality=modality,
            capability_id=capability_id,
            data_classification=data_classification,
            registry=registry,
            media_grant=media_grant,
            task_id=task_id,
            authorization_id=authorization.authorization_id,
            asset_digest=asset_digest,
        )
        if not eligible:
            raise FreeLLMAPIError(
                f"FREELLMAPI_ZERO_COST_{modality.upper()}_POOL_UNAVAILABLE"
            )
        return eligible[0]

    def governed_image(
        self,
        *,
        prompt: str,
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        media_grant: MediaEgressGrant | None = None,
        asset_digest: str | None = None,
        size: str | None = None,
    ) -> FreeLLMAPIProviderResult:
        candidate, decision = self._select_media_candidate(
            modality="image",
            capability_id=capability_id,
            data_classification=data_classification,
            authorization=authorization,
            task_id=task_id,
            catalog=catalog,
            registry=registry,
            media_grant=media_grant,
            asset_digest=asset_digest,
        )
        payload: dict[str, Any] = {"model": candidate.model_id, "prompt": str(prompt)}
        if size is not None:
            payload["size"] = str(size)
        try:
            response = self._client.post("images/generations", json=payload)
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FreeLLMAPIError(f"FREELLMAPI_IMAGE_REQUEST_FAILED:{type(exc).__name__}") from exc
        if not isinstance(raw, dict) or str(raw.get("provider") or "") != candidate.provider:
            raise FreeLLMAPIError("FREELLMAPI_MEDIA_PROVIDER_MISMATCH")
        receipt = self._receipt_base(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            provider=candidate.provider,
            requested_model=candidate.model_id,
            trust_lane=decision.trust_lane,
            input_value=payload,
            output_value=raw,
            media_egress_grant_id=decision.media_egress_grant_id,
        )
        return FreeLLMAPIProviderResult(raw=raw, content_type=response.headers.get("Content-Type"), receipt=receipt)

    def governed_video(
        self,
        *,
        prompt: str,
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        media_grant: MediaEgressGrant | None = None,
        asset_digest: str | None = None,
        duration: int | None = None,
        aspect_ratio: str | None = None,
    ) -> FreeLLMAPIProviderResult:
        candidate, decision = self._select_media_candidate(
            modality="video",
            capability_id=capability_id,
            data_classification=data_classification,
            authorization=authorization,
            task_id=task_id,
            catalog=catalog,
            registry=registry,
            media_grant=media_grant,
            asset_digest=asset_digest,
        )
        payload: dict[str, Any] = {"model": candidate.model_id, "prompt": str(prompt)}
        if duration is not None:
            payload["duration"] = int(duration)
        if aspect_ratio is not None:
            payload["aspect_ratio"] = str(aspect_ratio)
        try:
            response = self._client.post("videos/generations", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FreeLLMAPIError(f"FREELLMAPI_VIDEO_REQUEST_FAILED:{type(exc).__name__}") from exc
        provider = response.headers.get("X-Provider") or ""
        model = response.headers.get("X-Model") or candidate.model_id
        if provider != candidate.provider or model != candidate.model_id:
            raise FreeLLMAPIError("FREELLMAPI_MEDIA_PROVIDER_MISMATCH")
        raw = response.content
        receipt = self._receipt_base(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            provider=candidate.provider,
            requested_model=candidate.model_id,
            trust_lane=decision.trust_lane,
            input_value=payload,
            output_value=raw,
            media_egress_grant_id=decision.media_egress_grant_id,
        )
        return FreeLLMAPIProviderResult(raw=raw, content_type=response.headers.get("Content-Type"), receipt=receipt)

    def governed_speech(
        self,
        *,
        text: str,
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        media_grant: MediaEgressGrant | None = None,
        asset_digest: str | None = None,
        voice: str | None = None,
        response_format: str | None = None,
    ) -> FreeLLMAPIProviderResult:
        candidate, decision = self._select_media_candidate(
            modality="speech",
            capability_id=capability_id,
            data_classification=data_classification,
            authorization=authorization,
            task_id=task_id,
            catalog=catalog,
            registry=registry,
            media_grant=media_grant,
            asset_digest=asset_digest,
        )
        payload: dict[str, Any] = {"model": candidate.model_id, "input": str(text)}
        if voice is not None:
            payload["voice"] = str(voice)
        if response_format is not None:
            payload["response_format"] = str(response_format)
        try:
            response = self._client.post("audio/speech", json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FreeLLMAPIError(f"FREELLMAPI_SPEECH_REQUEST_FAILED:{type(exc).__name__}") from exc
        provider = response.headers.get("X-Provider") or ""
        if provider != candidate.provider:
            raise FreeLLMAPIError("FREELLMAPI_MEDIA_PROVIDER_MISMATCH")
        raw = response.content
        receipt = self._receipt_base(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            provider=candidate.provider,
            requested_model=candidate.model_id,
            trust_lane=decision.trust_lane,
            input_value=payload,
            output_value=raw,
            media_egress_grant_id=decision.media_egress_grant_id,
        )
        return FreeLLMAPIProviderResult(raw=raw, content_type=response.headers.get("Content-Type"), receipt=receipt)

    def governed_transcription(
        self,
        *,
        audio_bytes: bytes,
        filename: str,
        mime_type: str,
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        media_grant: MediaEgressGrant | None = None,
        asset_digest: str | None = None,
        language: str | None = None,
    ) -> FreeLLMAPIProviderResult:
        digest = asset_digest or ("sha256:" + sha256(audio_bytes).hexdigest())
        candidate, decision = self._select_media_candidate(
            modality="transcription",
            capability_id=capability_id,
            data_classification=data_classification,
            authorization=authorization,
            task_id=task_id,
            catalog=catalog,
            registry=registry,
            media_grant=media_grant,
            asset_digest=digest,
        )
        data: dict[str, str] = {"model": candidate.model_id, "response_format": "json"}
        if language is not None:
            data["language"] = str(language)
        files = {"file": (str(filename), bytes(audio_bytes), str(mime_type))}
        try:
            response = self._client.post("audio/transcriptions", data=data, files=files)
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FreeLLMAPIError(
                f"FREELLMAPI_TRANSCRIPTION_REQUEST_FAILED:{type(exc).__name__}"
            ) from exc
        provider = response.headers.get("X-Provider") or ""
        model = response.headers.get("X-Model") or candidate.model_id
        if provider != candidate.provider or model != candidate.model_id:
            raise FreeLLMAPIError("FREELLMAPI_MEDIA_PROVIDER_MISMATCH")
        receipt = self._receipt_base(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            provider=candidate.provider,
            requested_model=candidate.model_id,
            trust_lane=decision.trust_lane,
            input_value=audio_bytes,
            output_value=raw,
            media_egress_grant_id=decision.media_egress_grant_id,
        )
        receipt["asset_digest"] = digest
        return FreeLLMAPIProviderResult(raw=raw, content_type=response.headers.get("Content-Type"), receipt=receipt)

    def governed_fusion(
        self,
        *,
        messages: Iterable[dict[str, Any]],
        authorization: HazewaveAuthorization,
        task_id: str,
        capability_id: str,
        data_classification: str,
        catalog: FreeLLMAPILocalCatalog | None = None,
        registry: dict[str, Any] | None = None,
        panel_size: int = 4,
        strategy: str = "synthesize",
    ) -> FreeLLMAPICompletionResult:
        validate_authorization(
            authorization,
            expected_task_id=str(task_id),
            expected_capability=str(capability_id),
        )
        if capability_id != "reason.fusion":
            raise FreeLLMAPIError("FREELLMAPI_FUSION_CAPABILITY_REQUIRED")
        rows = _validate_messages(messages)
        policy_registry = registry if registry is not None else load_provider_registry()
        source = catalog if catalog is not None else FreeLLMAPILocalCatalog()
        eligible: list[tuple[FreeLLMAPIModelCandidate, ProviderEligibilityDecision]] = []
        seen_providers: set[str] = set()
        for candidate in source.chat_candidates():
            decision = evaluate_provider_eligibility(
                provider=candidate.provider,
                model_id=candidate.model_id,
                capability_id=capability_id,
                modality="text",
                data_classification=data_classification,
                registry=policy_registry,
            )
            if decision.allowed and candidate.provider not in seen_providers:
                eligible.append((candidate, decision))
                seen_providers.add(candidate.provider)
        wanted = max(2, min(int(panel_size), 8))
        panel = eligible[:wanted]
        if len(panel) < 2:
            raise FreeLLMAPIError("FREELLMAPI_ZERO_COST_FUSION_POOL_UNAVAILABLE")
        panel_models = [candidate.qualified_model_id for candidate, _ in panel]
        judge_model = panel_models[0]
        payload = {
            "model": "fusion",
            "messages": rows,
            "stream": False,
            "fusion": {
                "models": panel_models,
                "judge": judge_model,
                "strategy": str(strategy),
                "expose_panel": True,
            },
        }
        try:
            response = self._client.post("chat/completions", json=payload)
            response.raise_for_status()
            raw = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise FreeLLMAPIError(f"FREELLMAPI_FUSION_REQUEST_FAILED:{type(exc).__name__}") from exc
        if not isinstance(raw, dict):
            raise FreeLLMAPIError("FREELLMAPI_FUSION_RESPONSE_INVALID")
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise FreeLLMAPIError("FREELLMAPI_FUSION_RESPONSE_MISSING_CHOICE")
        message = choices[0].get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise FreeLLMAPIError("FREELLMAPI_FUSION_RESPONSE_CONTENT_INVALID")
        content = str(message["content"])
        usage = dict(raw.get("usage") or {}) if isinstance(raw.get("usage"), dict) else {}
        first_decision = panel[0][1]
        receipt = self._receipt_base(
            authorization=authorization,
            task_id=task_id,
            capability_id=capability_id,
            data_classification=data_classification,
            provider="FUSION",
            requested_model="fusion",
            trust_lane=first_decision.trust_lane,
            input_value=rows,
            output_value=content,
        )
        receipt.update(
            {
                "panel_models": panel_models,
                "judge_model": judge_model,
                "quota_cost_class": "HIGH",
                "usage": usage,
            }
        )
        return FreeLLMAPICompletionResult(
            content=content,
            served_model=(str(raw.get("model")) if raw.get("model") is not None else "fusion"),
            usage=usage,
            raw=raw,
            routed_via=response.headers.get("X-Routed-Via") or "fusion",
            receipt=receipt,
        )

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
        tools: Iterable[dict[str, Any]] | None = None,
        tool_choice: Any | None = None,
        response_format: dict[str, Any] | None = None,
        request_headers: dict[str, str] | None = None,
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
        if tools is not None:
            tool_rows = [dict(item) for item in tools]
            if not tool_rows:
                raise FreeLLMAPIError("FREELLMAPI_TOOLS_REQUIRED")
            payload["tools"] = tool_rows
        if tool_choice is not None:
            payload["tool_choice"] = tool_choice
        if response_format is not None:
            payload["response_format"] = dict(response_format)

        try:
            response = self._client.post(
                "chat/completions",
                json=payload,
                headers=request_headers,
            )
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
        if content is None and isinstance(message.get("tool_calls"), list) and message["tool_calls"]:
            content = ""
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



def build_free_fabric_inventory(
    *,
    catalog: FreeLLMAPILocalCatalog | None = None,
) -> dict[str, Any]:
    """Return a secret-free view of the locally routable FreeLLMAPI surface."""

    source = catalog if catalog is not None else FreeLLMAPILocalCatalog()
    chat = source.chat_candidates()
    embeddings = source.embedding_candidates()
    media: dict[str, list[FreeLLMAPIMediaCandidate]] = {}
    for modality in ("image", "video", "speech", "transcription"):
        try:
            media[modality] = source.media_candidates(modality)
        except FreeLLMAPIError:
            media[modality] = []

    providers = sorted(
        {
            *(candidate.provider for candidate in chat),
            *(candidate.provider for candidate in embeddings),
            *(
                candidate.provider
                for candidates in media.values()
                for candidate in candidates
            ),
        }
    )

    return {
        "schema": "HazewaveFreeFabricInventory/v1",
        "project_id": "HAZEWAVE",
        "authority": AUTHORITY,
        "provider_gateway": "FREELLMAPI",
        "provider_gateway_authority": "NONE",
        "providers": providers,
        "counts": {
            "providers_routable": len(providers),
            "chat_routable": len(chat),
            "vision_routable": sum(1 for candidate in chat if candidate.supports_vision),
            "tool_routable": sum(1 for candidate in chat if candidate.supports_tools),
            "embedding_routable": len(embeddings),
            "image_routable": len(media["image"]),
            "video_routable": len(media["video"]),
            "speech_routable": len(media["speech"]),
            "transcription_routable": len(media["transcription"]),
        },
        "chat_models": [candidate.qualified_model_id for candidate in chat],
        "embedding_families": sorted({candidate.family for candidate in embeddings}),
        "media_models": {
            modality: [
                f"{candidate.provider}:{candidate.model_id}"
                for candidate in candidates
            ]
            for modality, candidates in media.items()
        },
    }


def _eligible_text_model_ids(
    *,
    source: FreeLLMAPILocalCatalog,
    registry: dict[str, Any],
    capability_id: str,
    data_classification: str,
    modality: str = "text",
    require_vision: bool = False,
    require_tools: bool = False,
) -> list[str]:
    rows: list[str] = []
    for candidate in source.chat_candidates():
        if require_vision and not candidate.supports_vision:
            continue
        if require_tools and not candidate.supports_tools:
            continue
        decision = evaluate_provider_eligibility(
            provider=candidate.provider,
            model_id=candidate.model_id,
            capability_id=capability_id,
            modality=modality,
            data_classification=data_classification,
            registry=registry,
        )
        if decision.allowed:
            rows.append(candidate.qualified_model_id)
    return rows


def build_free_fabric_eligibility_report(
    *,
    catalog: FreeLLMAPILocalCatalog | None = None,
    data_classification: str = "PUBLIC",
    registry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Intersect live local discovery with Hazewave zero-cost policy.

    Catalog presence never grants authority. Every surfaced route has already
    passed the project-owned eligibility policy for the requested data class.
    """

    source = catalog if catalog is not None else FreeLLMAPILocalCatalog()
    policy_registry = registry if registry is not None else load_provider_registry()
    classification = str(data_classification or "").strip().upper()

    text_models = _eligible_text_model_ids(
        source=source,
        registry=policy_registry,
        capability_id="reason.general",
        data_classification=classification,
    )
    tool_models = _eligible_text_model_ids(
        source=source,
        registry=policy_registry,
        capability_id="reason.general",
        data_classification=classification,
        require_tools=True,
    )
    vision_models = _eligible_text_model_ids(
        source=source,
        registry=policy_registry,
        capability_id="visual.analyze",
        data_classification=classification,
        modality="vision",
        require_vision=True,
    )

    embedding_families = [
        family.family
        for family in source.eligible_embedding_families(
            capability_id="embedding.create",
            data_classification=classification,
            registry=policy_registry,
        )
    ]

    media_specs = {
        "image": ("image", "visual.image"),
        "video": ("video", "visual.video"),
        "speech": ("speech", "audio.voice"),
        "transcription": ("transcription", "audio.transcribe"),
    }
    media_surfaces: dict[str, dict[str, Any]] = {}
    for name, (modality, capability) in media_specs.items():
        try:
            eligible = source.eligible_media_candidates(
                modality=modality,
                capability_id=capability,
                data_classification=classification,
                registry=policy_registry,
            )
            media_surfaces[name] = {
                "models": [
                    f"{candidate.provider}:{candidate.model_id}"
                    for candidate, _ in eligible
                ],
                "status": "AVAILABLE" if eligible else "UNAVAILABLE",
            }
        except FreeLLMAPIError as exc:
            media_surfaces[name] = {
                "models": [],
                "status": "DENIED_AMBIGUOUS",
                "reason": str(exc),
            }

    fusion_candidates = _eligible_text_model_ids(
        source=source,
        registry=policy_registry,
        capability_id="reason.fusion",
        data_classification=classification,
    )
    fusion_providers = {value.split(":", 1)[0] for value in fusion_candidates}

    return {
        "schema": "HazewaveFreeFabricEligibilityReport/v1",
        "project_id": "HAZEWAVE",
        "authority": AUTHORITY,
        "provider_gateway": "FREELLMAPI",
        "provider_gateway_authority": "NONE",
        "data_classification": classification,
        "paid_fallback": str(policy_registry.get("paid_fallback") or "FORBIDDEN"),
        "unknown_cost": str(policy_registry.get("unknown_cost") or "DENY"),
        "surfaces": {
            "text": {
                "models": text_models,
                "status": "AVAILABLE" if text_models else "UNAVAILABLE",
            },
            "tools": {
                "models": tool_models,
                "status": "AVAILABLE" if tool_models else "UNAVAILABLE",
                "execution_authority": AUTHORITY,
            },
            "vision": {
                "models": vision_models,
                "status": "AVAILABLE" if vision_models else "UNAVAILABLE",
            },
            "embeddings": {
                "families": embedding_families,
                "status": "AVAILABLE" if embedding_families else "UNAVAILABLE",
            },
            "fusion": {
                "models": fusion_candidates,
                "status": (
                    "AVAILABLE"
                    if len(fusion_providers) >= 2
                    else "UNAVAILABLE"
                ),
                "quota_cost_class": "HIGH",
            },
            **media_surfaces,
            "credential_egress": "DENY",
            "private_media_default_egress": "DENY",
        },
    }


def run_live_probe(
    *,
    api_key: str,
    task_id: str = "hazewave-freellmapi-live-proof",
    base_url: str = DEFAULT_BASE_URL,
    catalog: Any | None = None,
) -> dict[str, Any]:
    """Execute one bounded governed zero-cost provider call.

    The proof uses a provider-qualified route selected only after Hazewave
    policy evaluation. It never uses unrestricted FreeLLMAPI auto-routing.
    """

    from hazewave.harness import HazewaveTask, issue_authorization, route_task

    task = HazewaveTask(
        task_id=str(task_id),
        goal="Analyze a synthetic non-secret sonic descriptor as a provider connectivity proof.",
        required_capability="audio.analyze",
        requested_domain="HAZE",
    )
    route = route_task(task)
    authorization = issue_authorization(route)
    source = catalog if catalog is not None else FreeLLMAPILocalCatalog()

    with FreeLLMAPIClient(base_url, api_key=api_key) as client:
        result = client.governed_chat(
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
            catalog=source,
            temperature=0.0,
            max_tokens=64,
            cache=True,
            compression="lossless",
            task_type="chat",
            session_id=f"hazewave-probe:{task.task_id}",
        )

    execution = dict(result.receipt or {})
    if execution.get("zero_cost_verified") is not True:
        raise FreeLLMAPIError("FREELLMAPI_PROBE_ZERO_COST_NOT_VERIFIED")

    usage = dict(result.usage)
    reported_cost = usage.get("cost")
    if isinstance(reported_cost, (int, float)) and float(reported_cost) > 0:
        raise FreeLLMAPIError("FREELLMAPI_PROBE_REPORTED_NONZERO_COST")

    return {
        "schema": "HazewaveProviderProbeReceipt/v2",
        "status": "PASS",
        "project_id": "HAZEWAVE",
        "authority": AUTHORITY,
        "task_id": task.task_id,
        "authorization_id": authorization.authorization_id,
        "capability_id": task.required_capability,
        "domain": route.selected_domain,
        "data_classification": "PUBLIC",
        "provider_gateway": result.provider_gateway,
        "provider": execution.get("provider"),
        "requested_model": execution.get("requested_model"),
        "trust_lane": execution.get("trust_lane"),
        "zero_cost_verified": True,
        "routed_via": result.routed_via,
        "served_model": result.served_model,
        "content_sha256": sha256(result.content.encode("utf-8")).hexdigest(),
        "usage": usage,
    }

