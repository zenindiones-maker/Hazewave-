from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import statistics
import sys
from typing import Any, Iterable, Mapping

from hazewave.colibri import (
    ColibriDecisionResult,
    detect_colibri_hardware,
    execute_colibri_system_one,
)
from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.reflex_robustness import execute_robust_reflex_route


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "config" / "reflex-latency-v1.json"
DEFAULT_STATE = Path.home() / ".local/state/hazewave/reflex"
DEFAULT_SOURCE = Path.home() / ".local/share/hazewave/providers/colibri/source"
DEFAULT_MODEL = Path.home() / ".local/share/hazewave/models/colibri/laya"


class ReflexLatencyError(RuntimeError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any) -> str:
    return sha256(_canonical(value)).hexdigest()


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(_canonical(dict(payload)) + b"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def load_latency_policy(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else DEFAULT_POLICY
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("schema") != "HazewaveReflexLatencyPolicy/v1":
        raise ValueError("REFLEX_LATENCY_POLICY_SCHEMA_INVALID")
    if payload.get("project_id") != "HAZEWAVE":
        raise ValueError("REFLEX_LATENCY_PROJECT_INVALID")
    if payload.get("authority") != "HAZEWAVE_HARNESS":
        raise ValueError("REFLEX_LATENCY_AUTHORITY_INVALID")
    if payload.get("provider_authority") != "NONE":
        raise ValueError("REFLEX_LATENCY_PROVIDER_AUTHORITY_INVALID")
    if payload.get("activation_state") != "MEASURE_BEFORE_ACTIVATE":
        raise ValueError("REFLEX_LATENCY_ACTIVATION_POLICY_INVALID")

    profiles = payload.get("profiles")
    runtime = payload.get("runtime") or {}
    safety = payload.get("safety") or {}
    if not isinstance(profiles, dict) or len(profiles) < 2:
        raise ValueError("REFLEX_LATENCY_PROFILES_INVALID")
    default = runtime.get("persistent_profile_default")
    if default not in profiles:
        raise ValueError("REFLEX_LATENCY_DEFAULT_PROFILE_INVALID")

    allowed = set(safety.get("allowed_environment_keys") or [])
    for name, row in profiles.items():
        if not isinstance(name, str) or not name:
            raise ValueError("REFLEX_LATENCY_PROFILE_NAME_INVALID")
        if not isinstance(row, dict):
            raise ValueError("REFLEX_LATENCY_PROFILE_INVALID")
        env = row.get("environment")
        if not isinstance(env, dict):
            raise ValueError("REFLEX_LATENCY_PROFILE_ENV_INVALID")
        if set(env) - allowed:
            raise ValueError("REFLEX_LATENCY_PROFILE_ENV_NOT_ALLOWLISTED")
        for key, value in env.items():
            if not isinstance(key, str) or not isinstance(value, str) or not value:
                raise ValueError("REFLEX_LATENCY_PROFILE_ENV_VALUE_INVALID")
        if env.get("OMP_WAIT_POLICY", "").lower() == "active":
            raise ValueError("REFLEX_LATENCY_ACTIVE_SPIN_PROFILE_FORBIDDEN")
        if "OMP_NUM_THREADS" in env:
            try:
                threads = int(env["OMP_NUM_THREADS"])
            except ValueError as exc:
                raise ValueError("REFLEX_LATENCY_THREADS_INVALID") from exc
            if threads not in {1, 2}:
                raise ValueError("REFLEX_LATENCY_THREADS_OUTSIDE_WORKSTATION")
    return payload


def policy_digest(policy: Mapping[str, Any]) -> str:
    return _digest(policy)


def profile_environment(
    profile: str,
    *,
    policy: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    selected = dict(policy) if policy is not None else load_latency_policy()
    row = (selected.get("profiles") or {}).get(profile)
    if not isinstance(row, dict):
        raise ReflexLatencyError("REFLEX_LATENCY_PROFILE_UNKNOWN")
    env = row.get("environment")
    if not isinstance(env, dict):
        raise ReflexLatencyError("REFLEX_LATENCY_PROFILE_ENV_INVALID")
    return {str(k): str(v) for k, v in env.items()}


def _percentile_nearest_rank(values: Iterable[float], percentile: float) -> float | None:
    rows = sorted(float(v) for v in values if math.isfinite(float(v)))
    if not rows:
        return None
    rank = max(1, math.ceil(percentile * len(rows)))
    return rows[min(rank - 1, len(rows) - 1)]


def _summary(values: Iterable[float | None]) -> dict[str, Any]:
    rows = [
        float(v)
        for v in values
        if isinstance(v, (int, float)) and math.isfinite(float(v))
    ]
    if not rows:
        return {"count": 0, "min_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None}
    return {
        "count": len(rows),
        "min_ms": min(rows),
        "p50_ms": statistics.median(rows),
        "p95_ms": _percentile_nearest_rank(rows, 0.95),
        "max_ms": max(rows),
    }


def _authorization():
    task = HazewaveTask(
        task_id="reflex-latency-benchmark",
        goal="Synthetic latency benchmark for bounded local route advisory",
        required_capability="decision.route",
        requested_domain=HAZE,
    )
    return issue_authorization(route_task(task))


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


def _read_secret(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ReflexLatencyError("REFLEX_LATENCY_SECRET_MISSING")
    if path.stat().st_mode & 0o077:
        raise ReflexLatencyError("REFLEX_LATENCY_SECRET_PERMISSIONS_UNSAFE")
    value = path.read_text(encoding="utf-8").strip()
    if len(value) < 24:
        raise ReflexLatencyError("REFLEX_LATENCY_SECRET_TOO_SHORT")
    return value


def measure_profile(
    *,
    profile: str,
    secret: str,
    warmup_requests: int,
    measured_requests: int,
    timeout_seconds: float,
) -> dict[str, Any]:
    policy = load_latency_policy()
    if profile not in policy["profiles"]:
        raise ReflexLatencyError("REFLEX_LATENCY_PROFILE_UNKNOWN")
    hardware = detect_colibri_hardware(DEFAULT_MODEL)
    auth = _authorization()
    captures: list[ColibriDecisionResult] = []

    def capture_executor(**kwargs):
        kwargs["timeout_seconds"] = timeout_seconds
        result = execute_colibri_system_one(**kwargs)
        captures.append(result)
        return result

    def one(index: int, measured: bool) -> dict[str, Any]:
        before = len(captures)
        try:
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
                executor=capture_executor,
            )
            if len(captures) != before + 1:
                raise ReflexLatencyError("REFLEX_LATENCY_CAPTURE_MISSING")
            result = captures[-1]
            return {
                "index": index,
                "measured": measured,
                "status": "PASS",
                "selected_label": robust.base_verdict.metrics.selected_label,
                "robust_eligible": robust.robust_eligible,
                "winner_agreement": robust.ensemble.winner_agreement,
                "normalized_jsd": robust.ensemble.normalized_jsd,
                "wall_ms": result.latency_ms,
                "health_ms": result.health_ms,
                "system_one_ms": result.system_one_ms,
                "engine_ms": result.engine_ms,
                "server_elapsed_ms": result.server_elapsed_ms,
                "queue_wait_ms": result.queue_wait_ms,
                "request_sha256": result.request_sha256,
                "response_sha256": result.response_sha256,
            }
        except Exception as exc:
            return {
                "index": index,
                "measured": measured,
                "status": "FAIL",
                "reason": type(exc).__name__ + ":" + str(exc),
            }

    warmups = [one(i, False) for i in range(warmup_requests)]
    samples = [one(i, True) for i in range(measured_requests)]
    passed = [row for row in samples if row.get("status") == "PASS"]
    failures = [row for row in samples if row.get("status") != "PASS"]
    labels = sorted({str(row["selected_label"]) for row in passed})
    robust_all = bool(passed) and all(bool(row.get("robust_eligible")) for row in passed)

    report = {
        "schema": "HazewaveReflexLatencyProfileReport/v1",
        "status": "PASS" if not failures and len(passed) == measured_requests else "FAIL",
        "profile": profile,
        "policy_sha256": policy_digest(policy),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "warmup_requests": warmup_requests,
        "measured_requests": measured_requests,
        "passed_requests": len(passed),
        "failed_requests": len(failures),
        "selected_labels": labels,
        "all_robust_eligible": robust_all,
        "latency": {
            "wall": _summary(row.get("wall_ms") for row in passed),
            "health": _summary(row.get("health_ms") for row in passed),
            "system_one": _summary(row.get("system_one_ms") for row in passed),
            "engine": _summary(row.get("engine_ms") for row in passed),
            "server_elapsed": _summary(row.get("server_elapsed_ms") for row in passed),
            "queue_wait": _summary(row.get("queue_wait_ms") for row in passed),
        },
        "samples": samples,
        "warmups": warmups,
        "provider_authority": "NONE",
        "production_calibrated": False,
        "grants_execution_authority": False,
    }
    report["report_sha256"] = _digest(report)
    return report


def _load_profile_reports(run_dir: Path) -> dict[str, dict[str, Any]]:
    reports: dict[str, dict[str, Any]] = {}
    for path in sorted(run_dir.glob("*.json")):
        if path.name in {"selection.json", "selected-profile.json"}:
            continue
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if row.get("schema") != "HazewaveReflexLatencyProfileReport/v1":
            continue
        name = row.get("profile")
        if isinstance(name, str):
            reports[name] = row
    return reports


def select_profile(
    *,
    run_dir: Path,
    state_root: Path = DEFAULT_STATE,
) -> dict[str, Any]:
    policy = load_latency_policy()
    cfg = policy["benchmark"]
    profiles = policy["profiles"]
    reports = _load_profile_reports(run_dir)
    default = str(policy["runtime"]["persistent_profile_default"])

    if len(reports) < int(cfg["minimum_profiles"]):
        raise ReflexLatencyError("REFLEX_LATENCY_INSUFFICIENT_PROFILE_REPORTS")
    baseline = reports.get(default)
    if not isinstance(baseline, dict) or baseline.get("status") != "PASS":
        raise ReflexLatencyError("REFLEX_LATENCY_BASELINE_REPORT_INVALID")
    if baseline.get("policy_sha256") != policy_digest(policy):
        raise ReflexLatencyError("REFLEX_LATENCY_BASELINE_POLICY_DRIFT")

    baseline_labels = baseline.get("selected_labels")
    if not isinstance(baseline_labels, list) or len(baseline_labels) != 1:
        raise ReflexLatencyError("REFLEX_LATENCY_BASELINE_LABEL_UNSTABLE")
    baseline_label = baseline_labels[0]
    base_p50 = baseline["latency"]["wall"]["p50_ms"]
    base_p95 = baseline["latency"]["wall"]["p95_ms"]
    if not isinstance(base_p50, (int, float)) or not isinstance(base_p95, (int, float)):
        raise ReflexLatencyError("REFLEX_LATENCY_BASELINE_TIMING_MISSING")

    candidates = []
    rejected = []
    improvement_needed = float(cfg["minimum_p50_improvement_fraction"])
    p95_regression = float(cfg["maximum_p95_regression_fraction"])

    for name, report in sorted(reports.items()):
        row = profiles.get(name)
        reasons: list[str] = []
        if not isinstance(row, dict) or row.get("persistent_eligible") is not True:
            reasons.append("NOT_PERSISTENT_ELIGIBLE")
        if report.get("status") != "PASS":
            reasons.append("PROFILE_REPORT_FAILED")
        if report.get("policy_sha256") != policy_digest(policy):
            reasons.append("POLICY_DRIFT")
        if report.get("failed_requests") != 0:
            reasons.append("MEASURED_FAILURES")
        if report.get("all_robust_eligible") is not True:
            reasons.append("ROBUST_ELIGIBILITY_FAILED")
        if report.get("selected_labels") != [baseline_label]:
            reasons.append("SELECTED_LABEL_DRIFT")
        p50 = ((report.get("latency") or {}).get("wall") or {}).get("p50_ms")
        p95 = ((report.get("latency") or {}).get("wall") or {}).get("p95_ms")
        if not isinstance(p50, (int, float)) or not isinstance(p95, (int, float)):
            reasons.append("TIMING_MISSING")

        if name != default and not reasons:
            improvement = (float(base_p50) - float(p50)) / float(base_p50)
            p95_ratio = float(p95) / float(base_p95)
            if improvement < improvement_needed:
                reasons.append("P50_IMPROVEMENT_TOO_SMALL")
            if p95_ratio > 1.0 + p95_regression:
                reasons.append("P95_REGRESSION")
            if not reasons:
                candidates.append({
                    "profile": name,
                    "p50_ms": float(p50),
                    "p95_ms": float(p95),
                    "improvement_fraction": improvement,
                    "p95_ratio": p95_ratio,
                })
        if reasons:
            rejected.append({"profile": name, "reasons": reasons})

    candidates.sort(key=lambda row: (row["p50_ms"], row["p95_ms"], row["profile"]))
    winner = candidates[0]["profile"] if candidates else default
    winner_report = reports[winner]
    status = "MEASURED_PROFILE_SELECTED" if winner != default else "BASELINE_RETAINED"

    selection = {
        "schema": "HazewaveReflexLatencySelection/v1",
        "status": status,
        "profile": winner,
        "policy_sha256": policy_digest(policy),
        "source_run_directory": str(run_dir),
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "baseline_profile": default,
        "baseline_p50_ms": float(base_p50),
        "baseline_p95_ms": float(base_p95),
        "selected_p50_ms": float(winner_report["latency"]["wall"]["p50_ms"]),
        "selected_p95_ms": float(winner_report["latency"]["wall"]["p95_ms"]),
        "candidates": candidates,
        "rejected": rejected,
        "provider_authority": "NONE",
        "grants_execution_authority": False,
        "production_calibrated": False,
    }
    selection["selection_sha256"] = _digest(selection)

    selection_path = run_dir / "selection.json"
    _atomic_json(selection_path, selection)
    active_path = state_root / "latency" / "selected-profile.json"
    _atomic_json(active_path, selection)
    return {**selection, "selection_path": str(selection_path), "active_profile_path": str(active_path)}


def selected_profile(
    *,
    state_root: Path = DEFAULT_STATE,
    policy: Mapping[str, Any] | None = None,
) -> str:
    selected = dict(policy) if policy is not None else load_latency_policy()
    default = str(selected["runtime"]["persistent_profile_default"])
    path = state_root / "latency" / "selected-profile.json"
    if not path.exists():
        return default
    try:
        row = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ReflexLatencyError("REFLEX_LATENCY_SELECTION_UNREADABLE") from exc
    if row.get("schema") != "HazewaveReflexLatencySelection/v1":
        raise ReflexLatencyError("REFLEX_LATENCY_SELECTION_SCHEMA_INVALID")
    if row.get("policy_sha256") != policy_digest(selected):
        raise ReflexLatencyError("REFLEX_LATENCY_SELECTION_POLICY_DRIFT")
    profile = row.get("profile")
    if profile not in selected["profiles"]:
        raise ReflexLatencyError("REFLEX_LATENCY_SELECTION_PROFILE_INVALID")
    if selected["profiles"][profile].get("persistent_eligible") is not True:
        raise ReflexLatencyError("REFLEX_LATENCY_SELECTION_NOT_PERSISTENT")
    return str(profile)


def exec_server(
    *,
    source_root: Path,
    model_root: Path,
    secret_file: Path,
    port: int,
    profile: str | None,
    state_root: Path,
) -> None:
    policy = load_latency_policy()
    chosen = profile or selected_profile(state_root=state_root, policy=policy)
    profile_env = profile_environment(chosen, policy=policy)
    secret = _read_secret(secret_file)
    launcher = source_root / "c" / "coli"
    engine = source_root / "c" / "laya"
    if not launcher.is_file() or not engine.is_file():
        raise ReflexLatencyError("REFLEX_LATENCY_ENGINE_MISSING")

    env = os.environ.copy()
    for key in policy["safety"]["allowed_environment_keys"]:
        env.pop(key, None)
    env.update(profile_env)
    env["COLI_MODEL"] = str(model_root)
    env["COLI_API_KEY"] = secret
    env["COLI_MODEL_ID"] = "laya"
    env["HAZEWAVE_REFLEX_LATENCY_PROFILE"] = chosen

    print(f"REFLEX_LATENCY_PROFILE={chosen}", file=sys.stderr, flush=True)
    for key in sorted(profile_env):
        print(f"REFLEX_LATENCY_ENV_{key}={profile_env[key]}", file=sys.stderr, flush=True)

    argv = [
        str(launcher),
        "serve",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--model-id",
        "laya",
    ]
    os.execvpe(str(launcher), argv, env)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hazewave.reflex_latency")
    sub = parser.add_subparsers(dest="command", required=True)

    p_profiles = sub.add_parser("profiles")
    p_profiles.add_argument("--json", action="store_true")

    p_measure = sub.add_parser("measure")
    p_measure.add_argument("--profile", required=True)
    p_measure.add_argument("--secret-file", type=Path, required=True)
    p_measure.add_argument("--warmup", type=int)
    p_measure.add_argument("--repeats", type=int)

    p_select = sub.add_parser("select")
    p_select.add_argument("--run-dir", type=Path, required=True)
    p_select.add_argument("--state-root", type=Path, default=DEFAULT_STATE)

    p_selected = sub.add_parser("selected")
    p_selected.add_argument("--state-root", type=Path, default=DEFAULT_STATE)

    p_server = sub.add_parser("server")
    p_server.add_argument("--source-root", type=Path, default=DEFAULT_SOURCE)
    p_server.add_argument("--model-root", type=Path, default=DEFAULT_MODEL)
    p_server.add_argument("--secret-file", type=Path, required=True)
    p_server.add_argument("--state-root", type=Path, default=DEFAULT_STATE)
    p_server.add_argument("--port", type=int, default=28080)
    p_server.add_argument("--profile")

    args = parser.parse_args(argv)
    policy = load_latency_policy()
    cfg = policy["benchmark"]

    if args.command == "profiles":
        names = list(policy["profiles"])
        if args.json:
            print(json.dumps(names))
        else:
            for name in names:
                print(name)
        return 0
    if args.command == "measure":
        secret = _read_secret(args.secret_file)
        report = measure_profile(
            profile=args.profile,
            secret=secret,
            warmup_requests=int(args.warmup if args.warmup is not None else cfg["warmup_requests"]),
            measured_requests=int(args.repeats if args.repeats is not None else cfg["measured_requests"]),
            timeout_seconds=float(cfg["request_timeout_seconds"]),
        )
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] == "PASS" else 4
    if args.command == "select":
        reply = select_profile(run_dir=args.run_dir, state_root=args.state_root)
        print(json.dumps(reply, sort_keys=True))
        return 0
    if args.command == "selected":
        print(selected_profile(state_root=args.state_root, policy=policy))
        return 0
    if args.command == "server":
        exec_server(
            source_root=args.source_root,
            model_root=args.model_root,
            secret_file=args.secret_file,
            port=args.port,
            profile=args.profile,
            state_root=args.state_root,
        )
        return 0
    raise AssertionError("unreachable")


if __name__ == "__main__":
    try:
        raise SystemExit(_main())
    except (ReflexLatencyError, ValueError, OSError) as exc:
        print(json.dumps({"status": "FAIL_CLOSED", "reason": str(exc)}, sort_keys=True))
        raise SystemExit(4)
