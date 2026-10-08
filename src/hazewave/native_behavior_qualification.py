"""Real source-owned ELF behavioral qualification with optional REA/Ghidra observation.

Differential input/output runs establish *bounded sampled behavioral agreement*,
not full mathematical equivalence, automatic binary-to-source reconstruction,
or license to operate on arbitrary software. Fail-closed negative mutation.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

from hazewave.harness import HazewaveTask, issue_authorization, route_task, validate_authorization


class NativeBehaviorError(RuntimeError):
    pass


_ROOT = Path(__file__).resolve().parents[2]
_OWNED = _ROOT / "tests" / "fixtures" / "native-owned-reconstruction"
_ORIGINAL = _OWNED / "original.c"
_CANDIDATES = frozenset({"reconstruction.c", "mutant.c"})
_BOUNDS = (-1000, 1000)
_BASE = {-1000, -999, -8, -7, -6, -1, 0, 1, 8, 9, 10, 11, 999, 1000}


def make_test_inputs(*, seed: int, count: int) -> list[int]:
    if type(seed) is not int or type(count) is not int or not (len(_BASE) <= count <= 1800):
        raise NativeBehaviorError("VECTOR_BUDGET_INVALID")
    values = set(_BASE)
    rng = random.Random(seed)
    while len(values) < count:
        values.add(rng.randint(*_BOUNDS))
    return sorted(values)


def _fixture_source(path: Path, *, original: bool) -> Path:
    p = Path(path)
    if p.is_symlink():
        raise NativeBehaviorError("SOURCE_NOT_ADMITTED")
    try:
        real = p.resolve(strict=True)
    except OSError as exc:
        raise NativeBehaviorError("SOURCE_NOT_ADMITTED") from exc
    if not real.is_file():
        raise NativeBehaviorError("SOURCE_NOT_ADMITTED")
    if original and real != _ORIGINAL.resolve():
        raise NativeBehaviorError("SOURCE_NOT_ADMITTED")
    if not original and (real.parent != _OWNED.resolve() or real.name not in _CANDIDATES):
        raise NativeBehaviorError("SOURCE_NOT_ADMITTED")
    return real


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(65536), b""):
            h.update(data)
    return h.hexdigest()


def _run(args: list[str], *, timeout: float = 7.0, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, text=True, capture_output=True, timeout=timeout, check=False, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NativeBehaviorError("NATIVE_SUBPROCESS_UNAVAILABLE_OR_TIMEOUT") from exc


def _compile(cc: str, source: Path, target: Path) -> None:
    result = _run([cc, "-std=c11", "-O0", "-g", "-fno-inline", "-fno-omit-frame-pointer",
                   "-Wall", "-Wextra", "-Werror", "-o", str(target), str(source)], timeout=50)
    if result.returncode != 0 or not target.is_file():
        raise NativeBehaviorError("NATIVE_COMPILER_FAILED")


def _output(binary: Path, value: int) -> int:
    result = _run([str(binary), str(value)], timeout=3)
    if result.returncode != 0:
        raise NativeBehaviorError("NATIVE_TARGET_NONZERO")
    text = result.stdout.strip()
    if len(text) > 28 or not text.lstrip("-").isdigit() or result.stderr.strip():
        raise NativeBehaviorError("NATIVE_TARGET_OUTPUT_INVALID")
    return int(text)


def _save(report: dict[str, Any], state_root: Path) -> Path:
    root = Path(state_root).expanduser()
    if root.resolve(strict=False).is_relative_to(_ROOT.resolve()) or root.is_symlink():
        raise NativeBehaviorError("UNSAFE_RECEIPT_DESTINATION")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = root / ("native-behavior-" + stamp + "-" + str(os.getpid()) + ".json")
    payload = (json.dumps(report, sort_keys=True, allow_nan=False, separators=(",", ":")) + "\n").encode()
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
    return target


def _ghidra_observation(rea: Path, oracle_bin: Path) -> dict[str, Any]:
    """Query the real native provider; its Evidence is NOT a reconstruction."""
    from hazewave.rea6_integration import inspect_ghidra_evidence, Rea6ContractError
    if rea.is_symlink() or not rea.is_file() or not os.access(rea, os.X_OK):
        raise NativeBehaviorError("REA6_EXECUTABLE_UNTRUSTED")
    version = _run([str(rea), "--version"])
    if version.returncode != 0 or "6.0.0" not in version.stdout:
        raise NativeBehaviorError("REA6_VERSION_MISMATCH")
    ghidra = os.environ.get("GHIDRA_INSTALL_DIR", "")
    if not ghidra or not (Path(ghidra) / "support" / "analyzeHeadless").is_file():
        raise NativeBehaviorError("GHIDRA_HOST_NOT_CONFIGURED")
    env = {k: os.environ[k] for k in ("HOME", "PATH", "LANG", "JAVA_HOME", "GHIDRA_INSTALL_DIR",
                                     "REA_ANALYSIS_PROVIDER", "TMPDIR") if k in os.environ}
    env["REA_ANALYSIS_PROVIDER"] = "ghidra"
    result = _run([str(rea), "function", str(oracle_bin), "main",
                   "--provider", "ghidra", "--json"], timeout=330, env=env)
    if result.returncode != 0 or len(result.stdout) > 4_000_000:
        raise NativeBehaviorError("GHIDRA_NATIVE_FUNCTION_FAILED")
    try:
        audit = inspect_ghidra_evidence(json.loads(result.stdout), expected_sha256=_sha(oracle_bin))
    except (Rea6ContractError, ValueError) as exc:
        raise NativeBehaviorError("GHIDRA_EVIDENCE_NOT_BOUND:" + str(exc)[:150]) from exc
    return {"evidence_id": audit["evidence_id"], "target_sha256": audit["target_sha256"],
            "provider_id": "ghidra", "operation": audit["operation"],
            "observation": "DIRECT_PROVIDER_EVIDENCE", "runtime_attested": False}


def qualify_native_behavior(
    *,
    original_source: Path,
    candidate_source: Path,
    state_root: Path,
    compiler: str,
    seed: int,
    count: int,
    rea_binary: Path | None = None,
) -> dict[str, Any]:
    original = _fixture_source(original_source, original=True)
    candidate = _fixture_source(candidate_source, original=False)
    if Path(compiler).name not in {"cc", "gcc", "clang"} or not shutil.which(compiler):
        raise NativeBehaviorError("NATIVE_COMPILER_NOT_ADMITTED")
    vectors = make_test_inputs(seed=seed, count=count)
    task = HazewaveTask("owned-native-behavior", "Owner-created native behavior differential proof",
                        "research.visual.inspect", "WAVE")
    decision = route_task(task)
    auth = validate_authorization(issue_authorization(decision),
                                  expected_task_id=task.task_id,
                                  expected_capability=task.required_capability)
    since = time.monotonic()
    original_sha, candidate_sha = _sha(original), _sha(candidate)
    with tempfile.TemporaryDirectory(prefix="hazewave-owned-native-") as directory:
        root = Path(directory)
        oracle = root / "oracle"
        reconstructed = root / "candidate"
        _compile(compiler, original, oracle)
        _compile(compiler, candidate, reconstructed)
        oracle_sha, reconstruction_sha = _sha(oracle), _sha(reconstructed)
        results = hashlib.sha256()
        mismatch = None
        for n in vectors:
            a, b = _output(oracle, n), _output(reconstructed, n)
            results.update(f"{n}:{a}:{b};".encode())
            if a != b and mismatch is None:
                mismatch = n
        native = None
        if mismatch is None and rea_binary is not None:
            native = _ghidra_observation(Path(rea_binary), oracle)
    status = "BOUNDED_BEHAVIOR_MATCH" if mismatch is None else "REJECTED_BEHAVIOR_MISMATCH"
    report = {
        "schema": "HazewaveOwnedNativeBehaviorQualification/v1",
        "harness_authority": auth.authority,
        "harness_authorization_id": auth.authorization_id,
        "semantic_status": status,
        "original_source_sha256": original_sha,
        "candidate_source_sha256": candidate_sha,
        "oracle_elf_sha256": oracle_sha,
        "candidate_elf_sha256": reconstruction_sha,
        "test_vectors_sha256": hashlib.sha256(json.dumps(vectors).encode()).hexdigest(),
        "observed_outputs_sha256": results.hexdigest(),
        "seed": seed, "sample_count": len(vectors),
        "oracle_runs": len(vectors), "candidate_runs": len(vectors),
        "first_mismatch_input": mismatch,
        "elapsed_ms": round(1000 * (time.monotonic() - since), 2),
        "native_binary_executed": True,
        "ghidra_provider_attested": False,
        "ghidra_direct_observation": native,
        "reconstruction_automatically_generated": False,
        "universal_equivalence_proven": False,
        "owner_agent_mcp_connected": False,
        "codespace_runtime_proven": False,
        "production_approved": False,
        "evidence_extent": "FINITE_SOURCE_OWNED_INPUTS_ONLY",
    }
    receipt = _save(report, Path(state_root))
    if mismatch is not None:
        raise NativeBehaviorError("BEHAVIOR_MISMATCH")
    report["receipt_sha256"] = _sha(receipt)
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Source-owned native differential semantic proof")
    p.add_argument("--state-root", type=Path, required=True)
    p.add_argument("--candidate", choices=("reconstruction", "mutant"), default="reconstruction")
    p.add_argument("--compiler", default="cc")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--count", type=int, default=300)
    p.add_argument("--rea", type=Path)
    args = p.parse_args(argv)
    try:
        result = qualify_native_behavior(
            original_source=_ORIGINAL,
            candidate_source=_OWNED / (args.candidate + ".c"),
            state_root=args.state_root, compiler=args.compiler,
            seed=args.seed, count=args.count, rea_binary=args.rea,
        )
    except NativeBehaviorError as exc:
        print("HAZEWAVE_NATIVE_BEHAVIOR=BLOCKED:" + str(exc), file=sys.stderr)
        return 20
    print("HAZEWAVE_NATIVE_BEHAVIOR=PASS_BOUNDED")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
