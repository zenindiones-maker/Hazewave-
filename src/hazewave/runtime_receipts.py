from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any

from hazewave.creative_plane import (
    ExecutionReceipt,
    ExecutionReceiptPayload,
    RuntimeReceiptSigner,
)


class RuntimeReceiptStoreError(RuntimeError):
    pass


@dataclass(frozen=True)
class DurableReceiptRecord:
    receipt_path: Path
    digest_path: Path
    receipt_sha256: str
    receipt: ExecutionReceipt
    schema: str = "DurableReceiptRecord/v1"


_RECEIPT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class RuntimeReceiptStore:
    def __init__(
        self,
        *,
        config_root: Path | str,
        state_root: Path | str,
    ) -> None:
        self.config_root = Path(config_root).expanduser()
        self.state_root = Path(state_root).expanduser()
        self.key_path = self.config_root / "receipt-hmac.key"
        self.receipts_dir = self.state_root / "receipts"

        self.config_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.receipts_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._restrict_dir(self.config_root)
        self._restrict_dir(self.receipts_dir)

        key = self._load_or_create_key()
        self.signer = RuntimeReceiptSigner(key)

    @staticmethod
    def _restrict_dir(path: Path) -> None:
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
            if mode & 0o077:
                os.chmod(path, mode & ~0o077)
        except OSError as exc:
            raise RuntimeReceiptStoreError(
                f"RUNTIME_RECEIPT_DIRECTORY_UNSAFE:{path}"
            ) from exc

    @staticmethod
    def _fsync_dir(path: Path) -> None:
        try:
            fd = os.open(path, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _load_or_create_key(self) -> bytes:
        try:
            fd = os.open(
                self.key_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
            )
        except FileExistsError:
            return self._load_existing_key()
        except OSError as exc:
            raise RuntimeReceiptStoreError(
                "RUNTIME_ATTESTATION_KEY_CREATE_FAILED"
            ) from exc

        key = os.urandom(32)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(key)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(self.key_path, 0o600)
            self._fsync_dir(self.config_root)
        except Exception:
            try:
                self.key_path.unlink()
            except OSError:
                pass
            raise
        return key

    def _load_existing_key(self) -> bytes:
        try:
            mode = stat.S_IMODE(self.key_path.stat().st_mode)
        except OSError as exc:
            raise RuntimeReceiptStoreError(
                "RUNTIME_ATTESTATION_KEY_STAT_FAILED"
            ) from exc
        if mode != 0o600:
            raise RuntimeReceiptStoreError(
                "RUNTIME_ATTESTATION_KEY_PERMISSIONS_UNSAFE"
            )
        try:
            key = self.key_path.read_bytes()
        except OSError as exc:
            raise RuntimeReceiptStoreError(
                "RUNTIME_ATTESTATION_KEY_READ_FAILED"
            ) from exc
        if len(key) < 32:
            raise RuntimeReceiptStoreError("RUNTIME_ATTESTATION_KEY_INVALID")
        return key

    @staticmethod
    def _validate_receipt_id(receipt_id: str) -> str:
        value = str(receipt_id or "").strip()
        if (
            not _RECEIPT_ID_RE.fullmatch(value)
            or value in {".", ".."}
            or "/" in value
            or "\\" in value
        ):
            raise RuntimeReceiptStoreError("RECEIPT_ID_INVALID")
        return value

    @staticmethod
    def _canonical_receipt_bytes(receipt: ExecutionReceipt) -> bytes:
        value = asdict(receipt)
        value["artifact_hashes"] = list(receipt.artifact_hashes)
        return (
            json.dumps(
                value,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")

    @classmethod
    def _atomic_create_bytes(
        cls,
        path: Path,
        content: bytes,
        *,
        mode: int,
        exists_code: str,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path: Path | None = None
        try:
            fd, tmp_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                suffix=".tmp",
                dir=path.parent,
            )
            tmp_path = Path(tmp_name)
            os.fchmod(fd, mode)
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(tmp_path, path)
            except FileExistsError as exc:
                raise RuntimeReceiptStoreError(exists_code) from exc
            os.chmod(path, mode)
            cls._fsync_dir(path.parent)
        finally:
            if tmp_path is not None:
                try:
                    tmp_path.unlink()
                except FileNotFoundError:
                    pass

    def sign_and_persist(
        self,
        payload: ExecutionReceiptPayload,
        *,
        receipt_id: str,
    ) -> DurableReceiptRecord:
        rid = self._validate_receipt_id(receipt_id)
        receipt = self.signer.sign(payload)
        receipt_bytes = self._canonical_receipt_bytes(receipt)
        digest = sha256(receipt_bytes).hexdigest()
        receipt_path = self.receipts_dir / f"{rid}.json"
        digest_path = self.receipts_dir / f"{rid}.sha256"

        self._atomic_create_bytes(
            receipt_path,
            receipt_bytes,
            mode=0o600,
            exists_code="RECEIPT_ALREADY_EXISTS",
        )
        try:
            self._atomic_create_bytes(
                digest_path,
                (digest + "  " + receipt_path.name + "\n").encode("ascii"),
                mode=0o600,
                exists_code="RECEIPT_DIGEST_ALREADY_EXISTS",
            )
        except Exception:
            # Never erase a durable receipt after its creation. A missing digest
            # is an incomplete record and verify_persisted() fails closed.
            raise

        return DurableReceiptRecord(
            receipt_path=receipt_path,
            digest_path=digest_path,
            receipt_sha256=digest,
            receipt=receipt,
        )

    @staticmethod
    def _receipt_from_mapping(payload: dict[str, Any]) -> ExecutionReceipt:
        required = {
            "project_id",
            "task_id",
            "capability",
            "domain",
            "candidate_head",
            "policy_digest",
            "runtime_identity",
            "reaper_project_identity",
            "state_before",
            "state_after",
            "idempotency_key",
            "operation_result",
            "artifact_hashes",
            "signature",
            "attestation",
            "schema",
        }
        if required.difference(payload):
            raise RuntimeReceiptStoreError("RECEIPT_MALFORMED")
        artifacts = payload.get("artifact_hashes")
        if not isinstance(artifacts, list) or not all(
            isinstance(value, str) for value in artifacts
        ):
            raise RuntimeReceiptStoreError("RECEIPT_MALFORMED")
        try:
            return ExecutionReceipt(
                project_id=str(payload["project_id"]),
                task_id=str(payload["task_id"]),
                capability=str(payload["capability"]),
                domain=str(payload["domain"]),
                candidate_head=str(payload["candidate_head"]),
                policy_digest=str(payload["policy_digest"]),
                runtime_identity=str(payload["runtime_identity"]),
                reaper_project_identity=str(payload["reaper_project_identity"]),
                state_before=int(payload["state_before"]),
                state_after=int(payload["state_after"]),
                idempotency_key=str(payload["idempotency_key"]),
                operation_result=str(payload["operation_result"]),
                artifact_hashes=tuple(artifacts),
                signature=str(payload["signature"]),
                attestation=str(payload["attestation"]),
                schema=str(payload["schema"]),
            )
        except (TypeError, ValueError) as exc:
            raise RuntimeReceiptStoreError("RECEIPT_MALFORMED") from exc

    def verify_persisted(self, receipt_path: Path | str) -> bool:
        path = Path(receipt_path)
        try:
            resolved = path.resolve()
            resolved.relative_to(self.receipts_dir.resolve())
        except (OSError, ValueError):
            return False
        if resolved.suffix != ".json" or not resolved.is_file():
            return False

        digest_path = resolved.with_suffix(".sha256")
        if not digest_path.is_file():
            return False
        try:
            receipt_bytes = resolved.read_bytes()
            digest_line = digest_path.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            return False

        actual_digest = sha256(receipt_bytes).hexdigest()
        fields = digest_line.split()
        if len(fields) < 2 or fields[0] != actual_digest:
            return False
        if fields[-1] != resolved.name:
            return False

        try:
            payload = json.loads(receipt_bytes)
            if not isinstance(payload, dict):
                return False
            receipt = self._receipt_from_mapping(payload)
        except (json.JSONDecodeError, RuntimeReceiptStoreError):
            return False

        return self.signer.verify(receipt)


def default_runtime_receipt_store() -> RuntimeReceiptStore:
    home = Path.home()
    return RuntimeReceiptStore(
        config_root=home / ".config" / "hazewave" / "creative",
        state_root=home / ".local" / "state" / "hazewave" / "creative",
    )
