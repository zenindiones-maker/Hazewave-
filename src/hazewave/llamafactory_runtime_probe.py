"""LLaMA-Factory 0.9.5 independent package integrity and CPU-safe runtime audit.

This is NOT an inference/training tool. A no-deps wheel is expected to
import but fail the dependency/CLI gates. Only mark each observed stage,
never fabricate a training-ready provider or install anything on inspection.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from typing import Any, Iterable


class LlamaRuntimeError(RuntimeError):
    pass


_VERSION = "0.9.5"
_OFFICIAL_WHEEL_SHA256 = "10776e9b259798bf65f6c5343f6298f0302e92e9cd47472abe29eef69e286c6a"
_SHA = re.compile(r"^[A-Za-z0-9_-]{43}$")


def check_record_hashes(root: Path, rows: Iterable[tuple[Path, str, str]]) -> int:
    """Validate PEP376 RECORD digests without trusting installed package code.

    Reject symlinked payloads and files outside the isolated venv.
    Empty RECORD hashes are not accepted as evidence; at least 20 hashed
    payload files must be independently checked by the calling probe.
    """
    root = Path(root).resolve(strict=True)
    good = 0
    for file, entry_hash, expected_size in rows:
        path = Path(file)
        if path.is_symlink():
            raise LlamaRuntimeError("INSTALLED_FILE_SYMLINK")
        try:
            absolute = path.resolve(strict=True)
        except OSError as exc:
            raise LlamaRuntimeError("INSTALLED_FILE_UNAVAILABLE") from exc
        if not absolute.is_relative_to(root):
            raise LlamaRuntimeError("INSTALLED_FILE_OUTSIDE_VENV")
        if not absolute.is_file():
            raise LlamaRuntimeError("INSTALLED_FILE_UNSAFE")
        if not entry_hash:
            continue
        if not isinstance(entry_hash, str) or not entry_hash.startswith("sha256="):
            raise LlamaRuntimeError("RECORD_DIGEST_ALGORITHM_INVALID")
        digest = entry_hash.split("=", 1)[1]
        if not _SHA.fullmatch(digest):
            raise LlamaRuntimeError("RECORD_DIGEST_FORMAT_INVALID")
        try:
            n = int(expected_size)
        except (ValueError, TypeError) as exc:
            raise LlamaRuntimeError("RECORD_SIZE_INVALID") from exc
        if n < 0 or path.stat().st_size != n:
            raise LlamaRuntimeError("RECORD_SIZE_MISMATCH")
        h = hashlib.sha256()
        with absolute.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        observed = base64.urlsafe_b64encode(h.digest()).decode().rstrip("=")
        if observed != digest:
            raise LlamaRuntimeError("RECORD_HASH_MISMATCH")
        good += 1
    return good


# This code executes in the ISOLATED venv interpreter under '-I': only stdlib
# plus the pinned package itself. Its result is NOT trusted unless exit=0.
_PROBE_CODE = r"""
import base64, hashlib, importlib.metadata as meta, json, os, pathlib, sys, zipfile
if sys.prefix == sys.base_prefix:
    raise RuntimeError("UNISOLATED_PYTHON")
root=pathlib.Path(sys.prefix).resolve(strict=True)
dist=meta.distribution("llamafactory")
if dist.metadata.get("Name","").lower().replace("_","-")!="llamafactory" or dist.version!="0.9.5":
    raise RuntimeError("BAD_INSTALLED_DISTRIBUTION")
rows=dist.files
if not rows:
    raise RuntimeError("MISSING_DISTRIBUTION_RECORD")
count=0
for item in rows:
    path=pathlib.Path(dist.locate_file(item))
    if path.is_symlink():
        raise RuntimeError("INSTALLED_FILE_SYMLINK")
    real=path.resolve(strict=True)
    if not real.is_relative_to(root) or not real.is_file():
        raise RuntimeError("INSTALLED_FILE_OUT_OF_VENV")
    if item.hash is not None:
        if item.hash.mode!="sha256" or not item.hash.value:
            raise RuntimeError("UNSUPPORTED_RECORD_HASH")
        blob=real.read_bytes()
        digest=base64.urlsafe_b64encode(hashlib.sha256(blob).digest()).decode().rstrip("=")
        if digest!=item.hash.value or (item.size is not None and len(blob)!=item.size):
            raise RuntimeError("INSTALLED_WHEEL_FILE_TAMPERED")
        count+=1
if count < 20:
    raise RuntimeError("INSUFFICIENT_VERIFIED_FILES")
wheel=pathlib.Path(sys.argv[1])
if wheel.is_symlink() or not wheel.is_file() or wheel.stat().st_size > 8_000_000:
    raise RuntimeError("OFFICIAL_WHEEL_NOT_AVAILABLE")
wheel_digest=hashlib.sha256(wheel.read_bytes()).hexdigest()
if wheel_digest!="10776e9b259798bf65f6c5343f6298f0302e92e9cd47472abe29eef69e286c6a":
    raise RuntimeError("OFFICIAL_WHEEL_SHA256_MISMATCH")
release_count=0
with zipfile.ZipFile(wheel) as archive:
    for info in archive.infolist():
        name=info.filename
        if not name.startswith("llamafactory/") or info.is_dir():
            continue
        if ".." in pathlib.PurePosixPath(name).parts:
            raise RuntimeError("WHEEL_ARCHIVE_TRAVERSAL")
        installed=pathlib.Path(dist.locate_file(name))
        if installed.is_symlink():
            raise RuntimeError("INSTALLED_FILE_SYMLINK")
        target=installed.resolve(strict=True)
        if not target.is_relative_to(root) or not target.is_file():
            raise RuntimeError("INSTALLED_FILE_OUTSIDE_VENV")
        if hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(archive.read(info)).digest():
            raise RuntimeError("INSTALLED_FILE_TAMPERED")
        release_count+=1
if release_count<20:
    raise RuntimeError("OFFICIAL_WHEEL_PAYLOAD_INCOMPLETE")
# Only import installed package code AFTER comparing it with pinned upstream.
import llamafactory
if llamafactory.__version__!="0.9.5":
    raise RuntimeError("PACKAGE_IMPORT_VERSION_DRIFT")
print(json.dumps({"distribution":"llamafactory","version":dist.version,
                  "imported_version":llamafactory.__version__,
                  "hash_files_verified":count,"environment_isolated":True,
                  "release_files_verified":release_count,
                  "release_wheel_sha256":wheel_digest,
                  "python_version":".".join(map(str,sys.version_info[:3]))},sort_keys=True))
"""


def validate_probe(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise LlamaRuntimeError("PROBE_RESULT_INVALID")
    if (record.get("distribution") != "llamafactory"
            or record.get("version") != _VERSION
            or record.get("imported_version") != _VERSION):
        raise LlamaRuntimeError("INSTALLED_VERSION_OR_IMPORT_DRIFT")
    if record.get("environment_isolated") is not True:
        raise LlamaRuntimeError("VENV_ISOLATION_NOT_VERIFIED")
    if (record.get("release_wheel_sha256") != _OFFICIAL_WHEEL_SHA256
            or type(record.get("release_files_verified")) is not int
            or record["release_files_verified"] < 20):
        raise LlamaRuntimeError("OFFICIAL_WHEEL_REFERENCE_MISSING")

    n = record.get("hash_files_verified")
    if type(n) is not int or n < 20:
        raise LlamaRuntimeError("INSTALLED_HASH_COVERAGE_INSUFFICIENT")
    ok = record.get("dependency_check_ok")
    if type(ok) is not bool:
        raise LlamaRuntimeError("DEPENDENCY_STATUS_INVALID")
    missing = record.get("missing_dependencies_count")
    if type(missing) is not int or missing < 0:
        raise LlamaRuntimeError("DEPENDENCY_COUNT_INVALID")
    cli = record.get("cli_status")
    if cli not in ("NOT_ATTEMPTED_MISSING_DEPS", "EXECUTED", "EXECUTION_FAILED"):
        raise LlamaRuntimeError("CLI_STATUS_INVALID")
    if ok and missing != 0:
        raise LlamaRuntimeError("DEPENDENCY_REPORT_CONTRADICTION")
    if not ok and cli == "EXECUTED":
        raise LlamaRuntimeError("CLI_READY_WITH_MISSING_DEPENDENCIES")
    if ok and cli == "NOT_ATTEMPTED_MISSING_DEPS":
        raise LlamaRuntimeError("CLI_NOT_EXECUTED_DESPITE_READY_DEPS")
    version = record.get("python_version")
    if not isinstance(version, str) or not re.match(r"^3\.(11|12|13)\.", version):
        raise LlamaRuntimeError("UNSUPPORTED_ISOLATED_PYTHON")
    return {
        "schema": "HazewaveLlamaFactoryRuntimeIntegrity/v1",
        "authority": "HAZEWAVE_HARNESS",
        "package": "llamafactory",
        "version": _VERSION,
        "package_imported": True,
        "installed_files_hash_verified": True,
        "source_release_payload_verified": True,
        "release_files_verified": record["release_files_verified"],
        "official_wheel_sha256": _OFFICIAL_WHEEL_SHA256,
        "hash_files_verified": n,
        "isolated_venv": True,
        "dependencies_satisfied": ok,
        "dependency_issues_detected": missing,
        "cli_status": cli,
        "cli_runnable": bool(ok and cli == "EXECUTED"),
        "model_training_ready": False,
        "model_inference_ready": False,
        "model_weights_present": "NOT_TESTED",
        "owner_model_and_data_grant": "NOT_PROVEN",
        "harness_connected": False,
        "codespace_identity_verified": False,
        "training_admitted": False,
        "production_approved": False,
        "scope": "PACKAGE_IMPORT_AND_HASHED_PAYLOAD_DIAGNOSTIC_ONLY",
    }


def _safe_env() -> dict[str, str]:
    env = {name: os.environ[name] for name in ("HOME","PATH","LANG","LC_ALL") if name in os.environ}
    env.update({
        "PYTHONNOUSERSITE":"1", "PYTHONDONTWRITEBYTECODE":"1",
        "HF_HUB_OFFLINE":"1", "HF_DATASETS_OFFLINE":"1",
        "TRANSFORMERS_OFFLINE":"1", "WANDB_MODE":"disabled",
        "PIP_NO_INDEX":"1", "CUDA_VISIBLE_DEVICES":"",
    })
    return env


def _run(args: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, capture_output=True, check=False, timeout=timeout,
                              text=True, env=_safe_env())
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LlamaRuntimeError("ISOLATED_PROCESS_UNAVAILABLE_OR_TIMEOUT") from exc


def diagnose_runtime(python: Path, wheel: Path) -> dict[str, Any]:
    path = Path(python).expanduser()
    # Linux venv/bin/python is commonly a symlink to the base interpreter.
    # Isolation is attested by executing it and checking sys.prefix != base_prefix;
    # symlink presence alone is not evidence of a compromised venv.
    if not path.is_file() or path.parent.name != "bin":
        raise LlamaRuntimeError("PYTHON_UNAVAILABLE")
    if not (path.parent.parent / "pyvenv.cfg").is_file():
        raise LlamaRuntimeError("VENV_CONFIGURATION_NOT_FOUND")
    # Never inherit connected GitHub tokens, private Telegram keys or model tokens.
    result = _run([str(path), "-I", "-c", _PROBE_CODE, str(Path(wheel).expanduser())], 25)
    if result.returncode or len(result.stdout)>10000:
        raise LlamaRuntimeError("ISOLATED_PACKAGE_IMPORT_OR_RECORD_FAILED")
    try:
        data = json.loads(result.stdout.strip())
    except (ValueError, json.JSONDecodeError) as exc:
        raise LlamaRuntimeError("ISOLATED_DIAGNOSTIC_OUTPUT_INVALID") from exc
    check = _run([str(path), "-I", "-m", "pip", "check"], 20)
    if check.returncode not in (0,1):
        raise LlamaRuntimeError("PACKAGE_DEPENDENCY_INSPECTION_FAILED")
    missing = 0 if check.returncode == 0 else max(1, len(check.stdout.strip().splitlines()))
    data.update({
        "dependency_check_ok":check.returncode == 0,
        "missing_dependencies_count":missing,
        "cli_status":"NOT_ATTEMPTED_MISSING_DEPS",
    })
    if check.returncode == 0:
        cli = path.parent / "llamafactory-cli"
        if cli.is_symlink() or not cli.is_file():
            raise LlamaRuntimeError("CLI_ENTRYPOINT_UNAVAILABLE")
        response = _run([str(cli),"version"], 35)
        data["cli_status"] = "EXECUTED" if response.returncode == 0 else "EXECUTION_FAILED"
    return validate_probe(data)


def _persist(result: dict[str, Any], receipt_root: Path) -> Path:
    root = Path(receipt_root).expanduser()
    if root.is_symlink() or root.parent.is_symlink():
        raise LlamaRuntimeError("RECEIPT_ROOT_UNSAFE")
    if root.resolve(strict=False).is_relative_to(Path(__file__).resolve().parents[2]):
        raise LlamaRuntimeError("RECEIPT_IN_REPOSITORY_FORBIDDEN")
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    root.chmod(0o700)
    name = "llamafactory-runtime-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + str(os.getpid()) + ".json"
    path = root / name
    data = (json.dumps(result,sort_keys=True,allow_nan=False) + "\n").encode()
    fd = os.open(path,os.O_WRONLY|os.O_EXCL|os.O_CREAT|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return path


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description="LLaMA-Factory pinned real import and on-host integrity audit")
    parser.add_argument("action",choices=("doctor",))
    parser.add_argument("--python",type=Path,required=True)
    parser.add_argument("--wheel",type=Path,required=True)
    parser.add_argument("--receipt-root",type=Path)
    args=parser.parse_args(argv)
    try:
        data=diagnose_runtime(args.python,args.wheel)
        if args.receipt_root is not None:
            receipt=_persist(data,args.receipt_root)
            data["local_receipt_path"]=str(receipt)
        print(json.dumps(data,sort_keys=True))
        print("LLAMA_FACTORY_IMPORT_AND_RECORD_INTEGRITY=PASS")
        print("LLAMA_FACTORY_CLI_RUNTIMEREADY=" + ("TRUE" if data["cli_runnable"] else "FALSE"))
        print("LLAMA_FACTORY_REAL_TRAINING=NOT_PROVEN")
    except LlamaRuntimeError as exc:
        print("LLAMA_FACTORY_RUNTIME_DIAGNOSTIC=BLOCKED:"+str(exc),file=sys.stderr)
        return 20
    return 0


if __name__=="__main__":
    raise SystemExit(main())
