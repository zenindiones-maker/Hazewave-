from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ZERO_COST_VERIFIED = "ZERO_COST_VERIFIED"
FREE_DEVELOPMENT_ENDPOINT = "FREE_DEVELOPMENT_ENDPOINT"
FREE_QUOTA = "FREE_QUOTA"
PAID = "PAID"
UNKNOWN = "UNKNOWN"

ALLOWED_ZERO_CASH_COST_CLASSES = frozenset(
    {ZERO_COST_VERIFIED, FREE_DEVELOPMENT_ENDPOINT, FREE_QUOTA}
)


@dataclass(frozen=True)
class HazewaveProviderExecutionResult:
    provider: str
    model_id: str
    execution_profile: str
    capability_id: str
    status: str
    content: str
    finish_reason: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    reasoning_tokens: int | None
    total_tokens: int | None
    latency_ms: int
    tool_calls: tuple[dict[str, Any], ...]
    error_class: str | None
    http_status: int | None
    retry_after_seconds: int | None
    cost_class: str
    semantic_pass: bool | None
    quality_score: float | None = None
    provider_gateway: str = "DIRECT"
    authority: str = "HAZEWAVE_HARNESS"
    schema: str = "HazewaveProviderExecutionResult/v1"

    @property
    def successful(self) -> bool:
        return self.status == "PASS" and self.semantic_pass is True

    def secret_free_receipt(self) -> dict[str, Any]:
        return {
            "schema": "HazewaveProviderExecutionReceipt/v1",
            "authority": self.authority,
            "provider": self.provider,
            "provider_gateway": self.provider_gateway,
            "model_id": self.model_id,
            "execution_profile": self.execution_profile,
            "capability_id": self.capability_id,
            "status": self.status,
            "finish_reason": self.finish_reason,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "error_class": self.error_class,
            "http_status": self.http_status,
            "retry_after_seconds": self.retry_after_seconds,
            "cost_class": self.cost_class,
            "semantic_pass": self.semantic_pass,
            "quality_score": self.quality_score,
            "tool_call_count": len(self.tool_calls),
        }
