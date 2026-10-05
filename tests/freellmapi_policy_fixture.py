from __future__ import annotations

from copy import deepcopy


def synthetic_provider_registry() -> dict:
    """Policy fixture for transport/adapter tests.

    This intentionally does not mirror production provider admissions. Tests
    using it verify routing mechanics against synthetic providers without
    weakening the real zero-cost registry.
    """

    def provider(
        name: str,
        *,
        modalities: list[str],
        capabilities: list[str],
        patterns: list[str] | None = None,
    ) -> dict:
        return {
            "provider": name,
            "enabled": True,
            "trust_lane": "REMOTE_PUBLIC_FREE",
            "monetary_policy": "ZERO_COST_VERIFIED",
            "billing_overflow_policy": "HARD_STOP",
            "allowed_data_classes": ["PUBLIC"],
            "allowed_modalities": modalities,
            "allowed_capabilities": capabilities,
            "model_patterns": patterns or ["*"],
            "terms_status": "TEST_FIXTURE",
            "privacy_status": "TEST_FIXTURE",
            "requires_endpoint_attestation": False,
            "last_reviewed_at": "2099-01-01",
            "source_evidence": ["test://synthetic-provider-policy"],
        }

    return {
        "schema": "HazewaveProviderEligibilityRegistry/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "provider_gateway": "FREELLMAPI",
        "paid_fallback": "FORBIDDEN",
        "unknown_cost": "DENY",
        "default_policy": {
            "enabled": False,
            "trust_lane": "QUARANTINED",
            "monetary_policy": "UNKNOWN_COST",
            "billing_overflow_policy": "UNKNOWN",
            "allowed_data_classes": [],
        },
        "providers": [
            provider(
                "kilo",
                modalities=["text", "tools", "vision"],
                capabilities=["reason.*", "code.*", "audio.analyze", "visual.analyze"],
            ),
            provider(
                "github",
                modalities=["text", "tools", "vision", "embedding"],
                capabilities=["reason.*", "code.*", "visual.analyze", "embedding.create"],
            ),
            provider(
                "pollinations",
                modalities=["image", "video", "speech"],
                capabilities=["visual.image", "visual.video", "audio.voice"],
            ),
            provider(
                "ovh",
                modalities=["text", "tools"],
                capabilities=["reason.*", "code.*"],
            ),
            provider(
                "groq",
                modalities=["text", "tools", "transcription"],
                capabilities=["reason.*", "code.*", "audio.transcribe"],
            ),
        ],
    }


def install_synthetic_provider_registry(monkeypatch) -> dict:
    registry = synthetic_provider_registry()
    monkeypatch.setattr(
        "hazewave.freellmapi.load_provider_registry",
        lambda *args, **kwargs: deepcopy(registry),
    )
    monkeypatch.setattr(
        "hazewave.provider_policy.load_provider_registry",
        lambda *args, **kwargs: deepcopy(registry),
    )
    return registry
