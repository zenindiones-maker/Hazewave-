from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from hazewave.provider_policy import (
    evaluate_provider_eligibility,
    load_account_attestations,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "freellmapi-provider-eligibility-v1.json"
ATTESTATION_SCHEMA_PATH = ROOT / "schemas" / "freellmapi-account-attestations-v1.schema.json"


def _store(*rows: dict) -> dict:
    return {
        "schema": "HazewaveProviderAccountAttestationStore/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "provider_gateway": "FREELLMAPI",
        "attestations": list(rows),
    }


def _attestation(
    provider: str,
    key_id: int,
    *,
    expires_at: str = "2099-01-01T00:00:00+00:00",
    paid_billing_enabled: bool = False,
) -> dict:
    return {
        "attestation_id": f"{provider}-key-{key_id}",
        "provider": provider,
        "credential_id": key_id,
        "account_tier": "FREE",
        "paid_billing_enabled": paid_billing_enabled,
        "billing_overflow_policy": "HARD_STOP",
        "evidence_method": "HUMAN_VERIFIED_PROVIDER_ACCOUNT",
        "issued_at": "2026-10-05T00:00:00+00:00",
        "expires_at": expires_at,
        "source_evidence": ["https://example.invalid/provider-free-tier-proof"],
    }


def test_account_attestation_schema_exists_and_missing_store_is_empty(tmp_path: Path) -> None:
    assert ATTESTATION_SCHEMA_PATH.is_file()

    missing = tmp_path / "missing.json"
    store = load_account_attestations(missing)

    assert store["schema"] == "HazewaveProviderAccountAttestationStore/v1"
    assert store["attestations"] == []


def test_account_bound_provider_is_denied_without_attestation() -> None:
    decision = evaluate_provider_eligibility(
        provider="groq",
        model_id="openai/gpt-oss-120b",
        capability_id="reason.general",
        modality="text",
        data_classification="PUBLIC",
        credential_ids=(7,),
        attestations=_store(),
    )

    assert decision.allowed is False
    assert decision.reason == "ACCOUNT_ATTESTATION_REQUIRED"


def test_valid_free_tier_attestation_enables_exact_provider_key() -> None:
    decision = evaluate_provider_eligibility(
        provider="groq",
        model_id="openai/gpt-oss-120b",
        capability_id="reason.general",
        modality="text",
        data_classification="PUBLIC",
        credential_ids=(7,),
        attestations=_store(_attestation("groq", 7)),
        now="2026-10-05T12:00:00+00:00",
    )

    assert decision.allowed is True
    assert decision.zero_cost_verified is True
    assert decision.account_attestation_ids == ("groq-key-7",)


def test_every_possible_provider_key_must_be_attested() -> None:
    decision = evaluate_provider_eligibility(
        provider="groq",
        model_id="whisper-large-v3-turbo",
        capability_id="audio.transcribe",
        modality="transcription",
        data_classification="PUBLIC",
        credential_ids=(7, 8),
        attestations=_store(_attestation("groq", 7)),
        now="2026-10-05T12:00:00+00:00",
    )

    assert decision.allowed is False
    assert decision.reason == "ACCOUNT_ATTESTATION_INCOMPLETE"


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (_attestation("groq", 7, expires_at="2026-10-04T00:00:00+00:00"), "ACCOUNT_ATTESTATION_EXPIRED"),
        (_attestation("groq", 7, paid_billing_enabled=True), "PAID_BILLING_ENABLED"),
    ],
)
def test_expired_or_paid_account_attestation_fails_closed(row: dict, reason: str) -> None:
    decision = evaluate_provider_eligibility(
        provider="groq",
        model_id="openai/gpt-oss-120b",
        capability_id="reason.general",
        modality="text",
        data_classification="PUBLIC",
        credential_ids=(7,),
        attestations=_store(row),
        now="2026-10-05T12:00:00+00:00",
    )

    assert decision.allowed is False
    assert decision.reason == reason


def test_openrouter_and_cloudflare_require_account_attestation() -> None:
    cases = [
        (
            "openrouter",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "reason.general",
            "text",
        ),
        (
            "cloudflare",
            "@cf/openai/whisper-large-v3-turbo",
            "audio.transcribe",
            "transcription",
        ),
    ]

    for provider, model, capability, modality in cases:
        denied = evaluate_provider_eligibility(
            provider=provider,
            model_id=model,
            capability_id=capability,
            modality=modality,
            data_classification="PUBLIC",
            credential_ids=(3,),
            attestations=_store(),
        )
        assert denied.allowed is False
        assert denied.reason == "ACCOUNT_ATTESTATION_REQUIRED"


def test_catalog_reports_all_enabled_provider_key_ids_for_unpinned_model(tmp_path: Path) -> None:
    from hazewave.freellmapi import FreeLLMAPILocalCatalog

    db = tmp_path / "freellmapi.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE api_keys (
          id INTEGER PRIMARY KEY,
          platform TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 1,
          status TEXT NOT NULL DEFAULT 'unknown'
        );
        CREATE TABLE models (
          id INTEGER PRIMARY KEY,
          platform TEXT NOT NULL,
          model_id TEXT NOT NULL,
          display_name TEXT NOT NULL,
          intelligence_rank INTEGER NOT NULL DEFAULT 999,
          speed_rank INTEGER NOT NULL DEFAULT 999,
          context_window INTEGER,
          enabled INTEGER NOT NULL DEFAULT 1,
          supports_vision INTEGER NOT NULL DEFAULT 0,
          supports_tools INTEGER NOT NULL DEFAULT 0,
          key_id INTEGER
        );
        INSERT INTO api_keys VALUES(7,'groq',1,'healthy');
        INSERT INTO api_keys VALUES(8,'groq',1,'healthy');
        INSERT INTO api_keys VALUES(9,'groq',0,'healthy');
        INSERT INTO models VALUES(
          1,'groq','openai/gpt-oss-120b','GPT OSS',1,1,131072,1,0,1,NULL
        );
        """
    )
    con.commit()
    con.close()

    catalog = FreeLLMAPILocalCatalog(db)

    assert catalog.routing_key_ids("groq", model_key_id=None) == (7, 8)
    assert catalog.routing_key_ids("groq", model_key_id=7) == (7,)


def test_registry_marks_account_bounded_providers_as_conditional_not_unconditional() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    by_provider = {row["provider"]: row for row in registry["providers"]}

    for provider in ("groq", "openrouter", "cloudflare"):
        row = by_provider[provider]
        assert row["enabled"] is True
        assert row["monetary_policy"] == "ZERO_COST_REQUIRES_ACCOUNT_HARD_CAP"
        assert row["billing_overflow_policy"] == "ACCOUNT_ATTESTATION_REQUIRED"


def test_cli_exposes_account_attestation_status_and_write_commands() -> None:
    from hazewave.cli import build_parser

    status = build_parser().parse_args(["freellmapi", "attest", "status"])
    assert status.freellmapi_command == "attest"
    assert status.attest_command == "status"

    write = build_parser().parse_args(
        [
            "freellmapi",
            "attest",
            "write",
            "--provider",
            "groq",
            "--credential-id",
            "7",
            "--expires-at",
            "2026-11-05T00:00:00+00:00",
            "--source-evidence",
            "https://console.groq.com/docs/billing-faqs",
            "--confirm-free-tier",
            "--confirm-no-paid-billing",
        ]
    )
    assert write.attest_command == "write"
    assert write.provider == "groq"
    assert write.credential_id == 7
    assert write.confirm_free_tier is True
    assert write.confirm_no_paid_billing is True


def test_write_account_attestation_is_atomic_owner_only_and_upserts(tmp_path: Path) -> None:
    from hazewave.provider_policy import write_account_attestation

    path = tmp_path / "account-attestations.json"
    record = write_account_attestation(
        provider="groq",
        credential_id=7,
        expires_at="2026-11-05T00:00:00+00:00",
        source_evidence=["https://console.groq.com/docs/billing-faqs"],
        path=path,
        now="2026-10-05T12:00:00+00:00",
    )
    replacement = write_account_attestation(
        provider="groq",
        credential_id=7,
        expires_at="2026-12-05T00:00:00+00:00",
        source_evidence=["https://console.groq.com/docs/rate-limits"],
        path=path,
        now="2026-10-05T13:00:00+00:00",
    )

    assert record["provider"] == "groq"
    assert replacement["credential_id"] == 7
    store = load_account_attestations(path)
    assert len(store["attestations"]) == 1
    assert store["attestations"][0]["expires_at"] == "2026-12-05T00:00:00+00:00"
    assert path.stat().st_mode & 0o777 == 0o600


def test_write_account_attestation_refuses_non_account_bound_provider(tmp_path: Path) -> None:
    from hazewave.provider_policy import write_account_attestation

    with pytest.raises(ValueError, match="HAZEWAVE_ACCOUNT_ATTESTATION_PROVIDER_NOT_ACCOUNT_BOUND"):
        write_account_attestation(
            provider="kilo",
            credential_id=1,
            expires_at="2026-11-05T00:00:00+00:00",
            source_evidence=["https://kilo.ai/docs/gateway/usage-and-billing"],
            path=tmp_path / "account-attestations.json",
            now="2026-10-05T12:00:00+00:00",
        )


def test_catalog_lists_provider_keys_without_exposing_encrypted_material(tmp_path: Path) -> None:
    from hazewave.freellmapi import FreeLLMAPILocalCatalog

    db = tmp_path / "freellmapi.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE api_keys (
          id INTEGER PRIMARY KEY,
          platform TEXT NOT NULL,
          label TEXT NOT NULL DEFAULT '',
          encrypted_key TEXT NOT NULL DEFAULT '',
          enabled INTEGER NOT NULL DEFAULT 1,
          status TEXT NOT NULL DEFAULT 'unknown'
        );
        INSERT INTO api_keys VALUES(7,'groq','free-main','ciphertext',1,'healthy');
        INSERT INTO api_keys VALUES(8,'cloudflare','workers-free','ciphertext2',0,'unknown');
        """
    )
    con.commit()
    con.close()

    rows = FreeLLMAPILocalCatalog(db).provider_keys()

    assert rows == [
        {
            "credential_id": 7,
            "provider": "groq",
            "label": "free-main",
            "enabled": True,
            "status": "healthy",
        },
        {
            "credential_id": 8,
            "provider": "cloudflare",
            "label": "workers-free",
            "enabled": False,
            "status": "unknown",
        },
    ]
    assert "ciphertext" not in json.dumps(rows)
