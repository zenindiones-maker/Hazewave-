"""Fail-closed, Codespace-scoped live proof and shadow observation.

No model download, service spawn, branch switch, paid route or authority promotion.
Live probes always use the actual local Colibri HTTP endpoint unless tests inject a transport.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Mapping

from hazewave.colibri import (
    ColibriHardwareSnapshot,
    detect_colibri_hardware,
    execute_colibri_system_one,
    load_colibri_policy,
    plan_colibri_model,
)
from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.reflex import (
    append_reflex_outcome,
    build_reflex_outcome,
    evaluate_reflex_outcomes,
    load_reflex_outcomes,
    load_reflex_policy,
    reflex_recalibration_readiness,
)
from hazewave.reflex_robustness import execute_robust_reflex_route

EXPECTED_CODESPACE = os.getenv("HAZEWAVE_REFLEX_EXPECTED_CODESPACE", "hazewave-zero-cost-4jxp45676rq6279xx")
BASE_REFLEX_HEAD = "c90e482266e2ee3a39763354e8172c1df484c3a7"
CANDIDATE_REF = os.getenv("HAZEWAVE_REFLEX_CANDIDATE_REF", "refs/remotes/origin/work/reflex-latency-v1")
DEFAULT_SOURCE = Path.home() / ".local/share/hazewave/providers/colibri/source"
DEFAULT_MODEL = Path.home() / ".local/share/hazewave/models/colibri/laya"
DEFAULT_STATE = Path.home() / ".local/state/hazewave/reflex"
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_DOMAIN = frozenset({"HAZE", "WAVE", "BRIDGE"})
_ALLOWED_DATA_CLASS = frozenset({"PUBLIC", "INTERNAL_NON_SECRET"})


class ShadowRuntimeError(RuntimeError):
    pass


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return sha256(canonical(value)).hexdigest()


def _git_head(directory: Path) -> str | None:
    if not (directory / ".git").exists():
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(directory), "rev-parse", "HEAD"],
            text=True, capture_output=True, timeout=8, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip()


def _read_secret(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ShadowRuntimeError("REFLEX_SECRET_FILE_MISSING_OR_SYMLINK")
    info = path.stat()
    if info.st_mode & 0o077:
        raise ShadowRuntimeError("REFLEX_SECRET_FILE_PERMISSIONS_UNSAFE")
    secret = path.read_text(encoding="utf-8").strip()
    if len(secret) < 24:
        raise ShadowRuntimeError("REFLEX_SECRET_TOO_SHORT")
    return secret


def verify_runtime_material(
    *,
    repository_root: Path,
    source_root: Path,
    model_root: Path,
    codespace: str | None,
    hardware: ColibriHardwareSnapshot | None = None,
) -> dict[str, Any]:
    policy = load_colibri_policy()
    upstream = policy["upstream"]
    model = next(x for x in policy["models"] if x["id"] == "laya")
    snapshot = hardware if hardware is not None else detect_colibri_hardware(model_root)
    plan = plan_colibri_model(model_id="laya", hardware=snapshot, policy=policy)
    root_head = _git_head(repository_root)
    try:
        remote_head = subprocess.run(
            ["git", "-C", str(repository_root), "rev-parse", CANDIDATE_REF],
            capture_output=True, text=True, timeout=8, check=True,
        ).stdout.strip()
        ancestry_ok = subprocess.run(
            ["git", "-C", str(repository_root), "merge-base",
             "--is-ancestor", BASE_REFLEX_HEAD, root_head or ""],
            capture_output=True, timeout=8,
        ).returncode == 0
        worktree_clean = not subprocess.run(
            ["git", "-C", str(repository_root), "status", "--porcelain"],
            capture_output=True, text=True, timeout=8, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        remote_head, ancestry_ok, worktree_clean = None, False, False
    source_head = _git_head(source_root)
    weights = model_root / "model.safetensors"
    layout = (
        weights.is_file()
        and (model_root / "rl_agent_config.json").is_file()
        and (model_root / "encoder/config.json").is_file()
        and (model_root / "tokenizer/tokenizer.json").is_file()
    )
    weight_sha: str | None = None
    if layout:
        checksum = sha256()
        with weights.open("rb") as handle:
            while chunk := handle.read(1 << 20):
                checksum.update(chunk)
        weight_sha = checksum.hexdigest()
    model_verified = layout and weight_sha == model["primary_weight_sha256"]
    engine_verified = source_head == upstream["source_commit"] and (source_root / "c/laya").is_file()
    codespace_verified = codespace == EXPECTED_CODESPACE
    workspace_verified = bool(root_head and root_head == remote_head and ancestry_ok and worktree_clean)
    # Snapshot admission is not a claim that real inference, a restart test or
    # Codespaces billing/quota were verified.
    available_ok = (
        snapshot.ram_available_bytes >= int((float(model["ram_min_gb"]) +
                                              float(policy["resource_policy"]["runtime_headroom_ram_gb"])) * 1e9)
    )
    allowed = all((
        codespace_verified, workspace_verified, engine_verified,
        model_verified, available_ok,
        snapshot.disk_free_bytes >= int(float(policy["resource_policy"]["reserve_disk_gb"]) * 1e9),
    ))
    return {
        "schema": "HazewaveReflexMaterialAudit/v1",
        "status": "READY_FOR_LIVE_PROBE" if allowed else "BLOCKED",
        "codespace_expected": EXPECTED_CODESPACE,
        "codespace_match": codespace_verified,
        "worktree_head": root_head,
        "worktree_remote_head": remote_head,
        "base_reflex_ancestry": ancestry_ok,
        "worktree_clean": worktree_clean,
        "worktree_head_match": workspace_verified,
        "upstream_commit_match": source_head == upstream["source_commit"],
        "laya_engine_built": (source_root / "c/laya").is_file(),
        "model_layout_valid": bool(layout),
        "model_weight_sha256_match": bool(model_verified),
        "resource_admission": bool(available_ok and snapshot.disk_free_bytes >= 6_000_000_000),
        "model_plan": plan,
        "ram_total_bytes": snapshot.ram_total_bytes,
        "ram_available_bytes": snapshot.ram_available_bytes,
        "disk_free_bytes": snapshot.disk_free_bytes,
        "paid_route_admitted": False,
        "real_inference_proven": False,
        "codespaces_quota_verified": False,
    }


def _assert_audit_ready(audit: Mapping[str, Any]) -> None:
    if audit.get("status") != "READY_FOR_LIVE_PROBE":
        raise ShadowRuntimeError("REFLEX_MATERIAL_AUDIT_BLOCKED")


@contextmanager
def _exclusive_lock(state_root: Path):
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state_root, 0o700)
    target = state_root / ".runtime.lock"
    fd = os.open(target, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _atomic_receipt(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise ShadowRuntimeError("REFLEX_RECEIPT_ALREADY_EXISTS")
    path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(path.parent, 0o700)
    data = canonical(dict(value)) + b"\n"
    tmp = path.with_name("." + path.name + f".{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def _authorization(task_id: str, domain: str):
    return issue_authorization(route_task(HazewaveTask(
        task_id=task_id, goal="Shadow observation: bounded route advisory",
        required_capability="decision.route", requested_domain=domain,
    )))


def _proof_question() -> dict[str, Any]:
    return {
        "type": "choice",
        "instructions": "Select the best Hazewave domain for this structured operational state.",
        "criteria": {
            "HAZE": "audio engineering, mixing and mastering",
            "WAVE": "animation, images, video, and interactive sites",
            "BRIDGE": "explicit cross-domain media coordination",
        },
    }


def _live_proof(
    *, secret: str, hardware: ColibriHardwareSnapshot,
    audit: Mapping[str, Any], state_root: Path,
) -> dict[str, Any]:
    _assert_audit_ready(audit)
    auth = _authorization("reflex-live-smoke", HAZE)
    robust = execute_robust_reflex_route(
        authorization=auth,
        question_id="route",
        state={"activity": "audio", "requested_operation": "mix", "fixture": True},
        question=_proof_question(),
        api_key=secret,
        deterministic_precheck_complete=True,
        data_classification="INTERNAL_NON_SECRET",
        state_language="en",
        model_installed=True,
        model_revision_verified=True,
        hardware=hardware,
    )
    verdict = robust.base_verdict
    if robust.disposition != "SHADOW_RECOMMENDATION":
        raise ShadowRuntimeError("REFLEX_LIVE_PROOF_LEFT_SHADOW_MODE")
    receipt = {
        "schema": "HazewaveReflexLiveSmokeReceipt/v2",
        "status": "LIVE_ROBUST_ENSEMBLE_INFERENCE_PASS",
        "runtime_identity": "codespace:" + EXPECTED_CODESPACE,
        "worktree_head": audit["worktree_head"],
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "model_id": verdict.model_id,
        "model_sha256_verified": True,
        "request_sha256": verdict.request_sha256,
        "response_sha256": verdict.response_sha256,
        "latency_ms": verdict.latency_ms,
        "disposition": robust.disposition,
        "selected_label": verdict.metrics.selected_label,
        "rotation_count": robust.ensemble.rotations,
        "winner_agreement": robust.ensemble.winner_agreement,
        "normalized_jsd": robust.ensemble.normalized_jsd,
        "robust_eligible": robust.robust_eligible,
        "provider_authority": "NONE",
        "real_inference_proven": True,
        "accuracy_proven": False,
        "codespaces_quota_verified": False,
        "production_calibrated": False,
    }
    with _exclusive_lock(state_root):
        path = state_root / "smoke" / (digest(receipt) + ".json")
        _atomic_receipt(path, receipt)
    return {**receipt, "receipt_path": str(path)}


def _validate_event(event: Any) -> dict[str, Any]:
    if not isinstance(event, dict) or event.get("schema") != "HazewaveReflexShadowEvent/v1":
        raise ShadowRuntimeError("REFLEX_SHADOW_EVENT_SCHEMA_INVALID")
    required = {"schema", "task_id", "requested_domain", "data_classification",
                "state_language", "precheck_status", "state", "decision_key"}
    if set(event) - (required | {"ground_truth"}):
        raise ShadowRuntimeError("REFLEX_SHADOW_EVENT_EXTRA_FIELD")
    if not required.issubset(event):
        raise ShadowRuntimeError("REFLEX_SHADOW_EVENT_MISSING_FIELD")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", str(event["task_id"])):
        raise ShadowRuntimeError("REFLEX_SHADOW_TASK_ID_INVALID")
    if event["requested_domain"] not in _ALLOWED_DOMAIN:
        raise ShadowRuntimeError("REFLEX_SHADOW_DOMAIN_INVALID")
    if event["data_classification"] not in _ALLOWED_DATA_CLASS:
        raise ShadowRuntimeError("REFLEX_SHADOW_DATA_CLASS_FORBIDDEN")
    if event["state_language"] != "en":
        raise ShadowRuntimeError("REFLEX_SHADOW_LANGUAGE_NOT_QUALIFIED")
    if event["precheck_status"] != "UNRESOLVED_PERMITTED_AMBIGUITY":
        raise ShadowRuntimeError("REFLEX_DETERMINISTIC_PRECHECK_REQUIRED")
    if not isinstance(event["state"], dict):
        raise ShadowRuntimeError("REFLEX_SHADOW_STATE_NOT_STRUCTURED")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}", str(event["decision_key"])):
        raise ShadowRuntimeError("REFLEX_SHADOW_DECISION_KEY_INVALID")
    truth = event.get("ground_truth")
    if truth is not None:
        if not isinstance(truth, dict) or set(truth) != {"actual_label", "label_source", "label_evidence_digest"}:
            raise ShadowRuntimeError("REFLEX_SHADOW_TRUTH_SCHEMA_INVALID")
        if truth["actual_label"] not in _ALLOWED_DOMAIN:
            raise ShadowRuntimeError("REFLEX_SHADOW_TRUTH_LABEL_INVALID")
        if truth["label_source"] not in {"HUMAN", "DETERMINISTIC", "RUNTIME_QC"}:
            raise ShadowRuntimeError("REFLEX_SHADOW_TRUTH_SOURCE_INVALID")
        if not _SHA_RE.fullmatch(str(truth["label_evidence_digest"])):
            raise ShadowRuntimeError("REFLEX_SHADOW_TRUTH_EVIDENCE_INVALID")
    return event


def _observe(
    *, event: Mapping[str, Any], secret: str, hardware: ColibriHardwareSnapshot,
    audit: Mapping[str, Any], state_root: Path,
) -> dict[str, Any]:
    _assert_audit_ready(audit)
    item = _validate_event(dict(event))
    event_id = digest(item)
    receipt_path = state_root / "events" / (event_id + ".json")
    with _exclusive_lock(state_root):
        if receipt_path.exists():
            recorded = json.loads(receipt_path.read_text(encoding="utf-8"))
            if recorded.get("event_digest") != event_id:
                raise ShadowRuntimeError("REFLEX_SHADOW_EVENT_RECEIPT_CONFLICT")
            return {**recorded, "receipt_path": str(receipt_path), "replayed": True}
        auth = _authorization(item["task_id"], item["requested_domain"])
        robust = execute_robust_reflex_route(
            authorization=auth,
            question_id="route",
            state=item["state"],
            question=_proof_question(),
            api_key=secret,
            deterministic_precheck_complete=True,
            data_classification=item["data_classification"],
            state_language="en",
            model_installed=True,
            model_revision_verified=True,
            hardware=hardware,
        )
        verdict = robust.base_verdict
        if robust.disposition != "SHADOW_RECOMMENDATION":
            raise ShadowRuntimeError("REFLEX_OBSERVATION_LEFT_SHADOW_MODE")
        receipt = {
            "schema": "HazewaveReflexShadowObservationReceipt/v2",
            "status": "OBSERVED_ROBUST_SHADOW_ONLY",
            "event_digest": event_id,
            "task_id": item["task_id"],
            "decision_key": item["decision_key"],
            "disposition": robust.disposition,
            "selected_label": verdict.metrics.selected_label,
            "threshold_eligible": verdict.threshold_eligible,
            "robust_eligible": robust.robust_eligible,
            "rotation_count": robust.ensemble.rotations,
            "winner_agreement": robust.ensemble.winner_agreement,
            "normalized_jsd": robust.ensemble.normalized_jsd,
            "robustness_reasons": list(robust.robustness_reasons),
            "latency_ms": verdict.latency_ms,
            "policy_sha256": verdict.policy_sha256,
            "request_sha256": verdict.request_sha256,
            "response_sha256": verdict.response_sha256,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "ground_truth_available": item.get("ground_truth") is not None,
            "raw_state_persisted": False,
            "authority": "HAZEWAVE_HARNESS",
            "provider_authority": "NONE",
            "grants_execution_authority": False,
            "production_calibrated": False,
        }
        if item.get("ground_truth") is not None:
            truth = item["ground_truth"]
            outcome = build_reflex_outcome(
                verdict=verdict,
                decision_key=item["decision_key"],
                actual_label=truth["actual_label"],
                label_source=truth["label_source"],
                label_evidence_digest=truth["label_evidence_digest"],
                observed_at=receipt["observed_at"],
            )
            append_reflex_outcome(state_root / "outcomes-v1.jsonl", outcome)
            receipt["outcome_id"] = outcome.outcome_id
        _atomic_receipt(receipt_path, receipt)
        return {**receipt, "receipt_path": str(receipt_path), "replayed": False}


def _report(state_root: Path) -> dict[str, Any]:
    outcomes = load_reflex_outcomes(state_root / "outcomes-v1.jsonl")
    group: dict[tuple[str, str, str, str], list[Any]] = {}
    for row in outcomes:
        key = (row.decision_key, row.capability_id, row.model_id, row.policy_sha256)
        group.setdefault(key, []).append(row)
    cohorts = []
    for (key, capability, model, policy_sha), rows in sorted(group.items()):
        report = evaluate_reflex_outcomes(rows)
        readiness = reflex_recalibration_readiness(outcomes, decision_key=key)
        cohorts.append({
            "decision_key": key, "capability": capability, "model": model,
            "policy_sha256": policy_sha, "metrics": asdict(report),
            "recalibration_readiness": readiness,
        })
    return {
        "schema": "HazewaveReflexShadowReport/v1",
        "status": "NO_LABELED_OUTCOMES" if not outcomes else "EVIDENCE_ONLY",
        "total_labeled_outcomes": len(outcomes),
        "cohorts": cohorts,
        "production_calibrated": False,
        "grants_execution_authority": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hazewave.reflex_shadow_runtime")
    parser.add_argument("command", choices=("doctor", "smoke", "observe", "report"))
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--state-root", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--secret-file", type=Path, default=DEFAULT_STATE / "colibri-api-key")
    parser.add_argument("--event-file", type=Path)
    args = parser.parse_args(argv)
    os.umask(0o077)
    if args.command == "report":
        print(json.dumps(_report(args.state_root), sort_keys=True))
        return 0
    snapshot = detect_colibri_hardware(args.model_root)
    audit = verify_runtime_material(
        repository_root=args.repository_root, source_root=args.source_root,
        model_root=args.model_root, codespace=os.getenv("CODESPACE_NAME"),
        hardware=snapshot,
    )
    if args.command == "doctor":
        print(json.dumps(audit, sort_keys=True))
        return 0 if audit["status"] == "READY_FOR_LIVE_PROBE" else 3
    _assert_audit_ready(audit)
    secret = _read_secret(args.secret_file)
    if args.command == "smoke":
        reply = _live_proof(secret=secret, hardware=snapshot, audit=audit,
                            state_root=args.state_root)
    else:
        if args.event_file is None:
            raise ShadowRuntimeError("REFLEX_SHADOW_EVENT_FILE_REQUIRED")
        event = json.loads(args.event_file.read_text(encoding="utf-8"))
        reply = _observe(event=event, secret=secret, hardware=snapshot,
                         audit=audit, state_root=args.state_root)
    print(json.dumps(reply, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ShadowRuntimeError, ValueError, PermissionError, OSError) as error:
        # Never emit a request payload, secret, private state or model contents.
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(error)}, sort_keys=True))
        raise SystemExit(4)
