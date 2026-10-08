"""Fail-closed LLaMA-Factory distribution and training-readiness assertions.

Package presence and a checked wheel SHA-256 do NOT prove that PyTorch,
Transformers, a GPU, model weights or a fine-tuning session are functional.
Training requires a separate owner-controlled model and dataset grant.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any

RELEASE_VERSION = "0.9.5"
RELEASE_SHA256 = "10776e9b259798bf65f6c5343f6298f0302e92e9cd47472abe29eef69e286c6a"
WHEEL_FILENAME = "llamafactory-0.9.5-py3-none-any.whl"


class LlamaFactoryError(ValueError):
    pass


def admitted_wheel_name(filename: str) -> bool:
    return isinstance(filename, str) and filename == WHEEL_FILENAME


def assert_wheel_integrity(path: Path) -> str:
    item = Path(path)
    if item.is_symlink() or not item.is_file() or not admitted_wheel_name(item.name):
        raise LlamaFactoryError("LLAMA_WHEEL_SOURCE_UNTRUSTED")
    h = hashlib.sha256()
    with item.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    if h.hexdigest() != RELEASE_SHA256:
        raise LlamaFactoryError("LLAMA_WHEEL_SHA256_MISMATCH")
    return h.hexdigest()


def validate_installed_metadata(record: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise LlamaFactoryError("PACKAGE_METADATA_INVALID")
    if str(record.get("name", "")).lower().replace("_", "-") != "llamafactory":
        raise LlamaFactoryError("PACKAGE_NAME_DRIFT")
    if record.get("version") != RELEASE_VERSION:
        raise LlamaFactoryError("PACKAGE_VERSION_DRIFT")
    if record.get("license") != "Apache-2.0":
        raise LlamaFactoryError("PACKAGE_LICENSE_DRIFT")
    if not {"llamafactory-cli", "lmf"} <= set(record.get("entry_points", [])):
        raise LlamaFactoryError("PACKAGE_ENTRY_POINTS_MISSING")
    return {
        "schema": "HazewaveLlamaFactoryMetadataProof/v1",
        "package": "llamafactory",
        "version": RELEASE_VERSION,
        "license": "Apache-2.0",
        "expected_release_wheel_sha256": RELEASE_SHA256,
        "package_installed": True,
        "full_dependency_stack_verified": False,
        "cli_runnable": False,
        "training_runnable": False,
        "models_downloaded": False,
        "harness_agent_connected": False,
        "production_approved": False,
        "source_type": "INSTALLED_PACKAGE_METADATA_ONLY",
    }


def training_readiness(
    *,
    cuda_available: bool,
    vram_gib: float,
    ram_gib: float,
    free_disk_gib: float,
    dependencies_ok: bool,
) -> dict[str, Any]:
    for v in (vram_gib, ram_gib, free_disk_gib):
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v) or v < 0:
            raise LlamaFactoryError("RESOURCE_METRIC_INVALID")
    if not cuda_available:
        reason = "GPU_UNAVAILABLE"
    elif ram_gib < 16:
        reason = "HOST_RAM_BELOW_16GIB"
    elif free_disk_gib < 20:
        reason = "DISK_BELOW_20GIB"
    elif vram_gib < 12:
        reason = "GPU_VRAM_BELOW_12GIB"
    elif not dependencies_ok:
        reason = "TRAINING_DEPENDENCIES_NOT_VERIFIED"
    else:
        reason = "OWNER_MODEL_AND_DATASET_GRANT_MISSING"
    return {
        "schema": "HazewaveLlamaFactoryTrainingAdmission/v1",
        "authority": "HAZEWAVE_HARNESS",
        "training_admitted": False,
        "reason": reason,
        "cost_policy": "NO_PAID_FALLBACK",
        "license_and_dataset_rights_verified": False,
        "model_weights_downloaded": False,
        "owner_model_dataset_grant": "NOT_PROVEN",
        "production_approved": False,
    }


def inspect_environment(python: Path) -> dict[str, Any]:
    path = Path(python)
    if path.is_symlink() or not path.is_file():
        raise LlamaFactoryError("PYTHON_RUNTIME_NOT_ADMITTED")
    code = (
        "import importlib.metadata as m,json;"
        "x=m.distribution('llamafactory');"
        "e=sorted(z.name for z in x.entry_points if z.group=='console_scripts');"
        "print(json.dumps({'name':x.metadata['Name'],'version':x.version,"
        "'license':x.metadata.get('License-Expression') or x.metadata.get('License'),"
        "'entry_points':e}))"
    )
    try:
        r = subprocess.run([str(path), "-c", code], capture_output=True,
                           text=True, check=False, timeout=15, env={"PYTHONNOUSERSITE": "1"})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LlamaFactoryError("ISOLATED_PYTHON_UNAVAILABLE") from exc
    if r.returncode != 0:
        raise LlamaFactoryError("LLAMA_PACKAGE_NOT_INSTALLED")
    try:
        return validate_installed_metadata(json.loads(r.stdout))
    except (ValueError, json.JSONDecodeError) as exc:
        raise LlamaFactoryError("LLAMA_METADATA_VERIFICATION_FAILED") from exc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("doctor", "verify-wheel"))
    p.add_argument("--python", type=Path)
    p.add_argument("--wheel", type=Path)
    args = p.parse_args(argv)
    try:
        if args.mode == "verify-wheel":
            if args.wheel is None:
                raise LlamaFactoryError("WHEEL_PATH_REQUIRED")
            value = {"status": "PASS:OFFICIAL_WHEEL_SHA256", "sha256": assert_wheel_integrity(args.wheel)}
        else:
            if args.python is None:
                raise LlamaFactoryError("ISOLATED_PYTHON_REQUIRED")
            value = inspect_environment(args.python)
    except LlamaFactoryError as exc:
        print("HAZEWAVE_LLAMA_FACTORY=BLOCKED:" + str(exc), file=sys.stderr)
        return 20
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
