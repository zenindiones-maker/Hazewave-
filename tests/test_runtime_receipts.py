from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from hazewave.creative_plane import ExecutionReceiptPayload
from hazewave.runtime_receipts import RuntimeReceiptStore, RuntimeReceiptStoreError


def _payload() -> ExecutionReceiptPayload:
    return ExecutionReceiptPayload(
        project_id="HAZEWAVE",
        task_id="vertical-proof-001",
        capability="render.preview",
        domain="HAZE",
        candidate_head="abc123",
        policy_digest="policy-digest",
        runtime_identity="codespace:fixture",
        reaper_project_identity="/tmp/fixture.rpp",
        state_before=10,
        state_after=11,
        idempotency_key="idem-render-a",
        operation_result="PASS",
        artifact_hashes=("sha256:" + "a" * 64,),
    )


def test_runtime_receipt_store_creates_private_key_outside_receipt_state_and_persists_atomically(
    tmp_path: Path,
) -> None:
    config_root = tmp_path / "config"
    state_root = tmp_path / "state"
    store = RuntimeReceiptStore(config_root=config_root, state_root=state_root)

    record = store.sign_and_persist(_payload(), receipt_id="render-a")

    assert store.key_path == config_root / "receipt-hmac.key"
    assert store.key_path.is_file()
    assert stat.S_IMODE(store.key_path.stat().st_mode) == 0o600
    assert record.receipt_path == state_root / "receipts" / "render-a.json"
    assert record.receipt_path.is_file()
    assert record.digest_path.is_file()
    assert not list(record.receipt_path.parent.glob("*.tmp"))
    assert store.verify_persisted(record.receipt_path) is True


def test_runtime_receipts_survive_process_restart_with_same_runtime_key(
    tmp_path: Path,
) -> None:
    config_root = tmp_path / "config"
    state_root = tmp_path / "state"
    first = RuntimeReceiptStore(config_root=config_root, state_root=state_root)
    record = first.sign_and_persist(_payload(), receipt_id="restart-proof")

    restarted = RuntimeReceiptStore(config_root=config_root, state_root=state_root)

    assert restarted.verify_persisted(record.receipt_path) is True


def test_persisted_receipt_tampering_is_detected(tmp_path: Path) -> None:
    store = RuntimeReceiptStore(
        config_root=tmp_path / "config",
        state_root=tmp_path / "state",
    )
    record = store.sign_and_persist(_payload(), receipt_id="tamper")
    payload = json.loads(record.receipt_path.read_text(encoding="utf-8"))
    payload["operation_result"] = "FAIL"
    record.receipt_path.write_text(
        json.dumps(payload, sort_keys=True),
        encoding="utf-8",
    )

    assert store.verify_persisted(record.receipt_path) is False


def test_runtime_receipt_store_rejects_unsafe_existing_key_permissions(
    tmp_path: Path,
) -> None:
    config_root = tmp_path / "config"
    config_root.mkdir()
    key_path = config_root / "receipt-hmac.key"
    key_path.write_bytes(b"k" * 32)
    os.chmod(key_path, 0o644)

    with pytest.raises(
        RuntimeReceiptStoreError,
        match="RUNTIME_ATTESTATION_KEY_PERMISSIONS_UNSAFE",
    ):
        RuntimeReceiptStore(
            config_root=config_root,
            state_root=tmp_path / "state",
        )


@pytest.mark.parametrize("receipt_id", ["../escape", "a/b", "", ".", ".."])
def test_receipt_id_cannot_escape_runtime_state(
    tmp_path: Path,
    receipt_id: str,
) -> None:
    store = RuntimeReceiptStore(
        config_root=tmp_path / "config",
        state_root=tmp_path / "state",
    )

    with pytest.raises(RuntimeReceiptStoreError, match="RECEIPT_ID_INVALID"):
        store.sign_and_persist(_payload(), receipt_id=receipt_id)


def test_receipt_file_is_create_only_and_cannot_overwrite_existing_evidence(
    tmp_path: Path,
) -> None:
    store = RuntimeReceiptStore(
        config_root=tmp_path / "config",
        state_root=tmp_path / "state",
    )
    store.sign_and_persist(_payload(), receipt_id="immutable")

    with pytest.raises(RuntimeReceiptStoreError, match="RECEIPT_ALREADY_EXISTS"):
        store.sign_and_persist(_payload(), receipt_id="immutable")
