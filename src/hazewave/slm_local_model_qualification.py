"""Local, install-free, fail-closed compact model discovery and HAZE smoke proof.

No Ollama process is started. No model is pulled. The sole network destination is
literal 127.0.0.1:11434 with proxies disabled. The actual Harness authorizes
the bounded inference call; verified owner synthetic FFmpeg evidence is required.
Mock transport tests NEVER claim that a live model ran.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import sys
import time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from hazewave.harness import HazewaveTask, issue_authorization, route_task, validate_authorization
from hazewave.host_av_evidence import verify_host_av_evidence
from hazewave.slm_audio_specialist import build_audio_prompt, evaluate_audio_decision

BASE_URL = "http://127.0.0.1:11434"
_SHA64 = re.compile(r"^[a-f0-9]{64}$")
_TRIAL = re.compile(r"^[a-z0-9][a-z0-9_-]{7,31}$")
_KNOWN_COMPACT = frozenset({"qwen3:4b", "qwen3:4b-instruct"})
_MAX_BYTES = 131072
_TIMEOUT_SECONDS = 70
_MAX_PARAMS = 5_000_000_000


class ModelQualificationError(ValueError):
    pass


def _direct_loopback_request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if (method, path) not in {
        ("GET", "/api/tags"), ("POST", "/api/show"), ("POST", "/api/chat")
    }:
        raise ModelQualificationError("LOCAL_ENDPOINT_NOT_ALLOWLISTED")
    body = json.dumps(payload, separators=(",", ":")).encode() if payload is not None else None
    request = Request(BASE_URL + path, data=body, method=method,
                      headers={"Content-Type": "application/json"} if body else {})
    try:
        # ProxyHandler({}) forbids HTTP_PROXY from redirecting a local request.
        with build_opener(ProxyHandler({})).open(
            request, timeout=_TIMEOUT_SECONDS if path == "/api/chat" else 8
        ) as response:
            raw = response.read(_MAX_BYTES + 1)
        if len(raw) > _MAX_BYTES:
            raise ModelQualificationError("OLLAMA_RESPONSE_OVERSIZE")
        obj = json.loads(raw)
    except (OSError, HTTPError, URLError, ValueError) as exc:
        if isinstance(exc, ModelQualificationError):
            raise
        raise ModelQualificationError("OLLAMA_LOCAL_UNAVAILABLE") from exc
    if not isinstance(obj, dict):
        raise ModelQualificationError("OLLAMA_RESPONSE_INVALID")
    return obj


def _parameters(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([MB])\s*", value, re.IGNORECASE)
    if not match:
        return None
    raw = float(match.group(1)) * (1_000_000 if match.group(2).lower() == "m" else 1_000_000_000)
    if not math.isfinite(raw) or raw <= 0:
        return None
    return int(raw)


def inventory_local_ollama(
    *, transport: Callable[[str, str, dict[str, Any] | None], dict[str, Any]] | None = None
) -> dict[str, Any]:
    """One read-only list and narrow metadata inspection per known compact candidate."""
    request = transport if transport is not None else _direct_loopback_request
    obj = request("GET", "/api/tags")
    if not isinstance(obj, dict) or not isinstance(obj.get("models"), list):
        raise ModelQualificationError("OLLAMA_TAGS_INVALID")
    rows = obj["models"]
    if len(rows) > 200:
        raise ModelQualificationError("OLLAMA_CATALOG_OVERSIZE")
    seen: set[str] = set()
    models: list[dict[str, Any]] = []
    for entry in rows:
        if not isinstance(entry, dict):
            raise ModelQualificationError("OLLAMA_CATALOG_INVALID")
        name = entry.get("name")
        if not isinstance(name, str) or not 0 < len(name) <= 128 or name in seen:
            raise ModelQualificationError("OLLAMA_MODEL_ID_INVALID_OR_DUPLICATE")
        seen.add(name)
        details = entry.get("details")
        details = details if isinstance(details, dict) else {}
        digest = entry.get("digest")
        size_bytes = entry.get("size")
        valid_hash = isinstance(digest, str) and bool(_SHA64.fullmatch(digest))
        installed_size = type(size_bytes) is int and size_bytes > 0
        candidate_name = name in _KNOWN_COMPACT
        observed = {
            "name": name,
            "local_identity_digest_sha256": digest if valid_hash else None,
            "local_identity_verified": bool(valid_hash and installed_size),
            "total_parameters": None,
            "size_verified": False,
            "license_metadata_verified": False,
            "license_evidence_scope": "LOCAL_OLLAMA_EMBEDDED_METADATA_ONLY",
            "upstream_weights_provenance_verified": False,
            "quantization": details.get("quantization_level"),
            "model_size_bytes": size_bytes if installed_size else None,
            "runtime_available": True,
            "inference_tested": False,
            "candidate_admitted_for_smoke": False,
            "model_is_slm_proven": False,
            "production_approved": False,
        }
        if candidate_name and valid_hash and installed_size:
            show = request("POST", "/api/show", {"model": name})
            if not isinstance(show, dict):
                raise ModelQualificationError("OLLAMA_SHOW_INVALID")
            sd = show.get("details")
            mi = show.get("model_info")
            sd = sd if isinstance(sd, dict) else {}
            mi = mi if isinstance(mi, dict) else {}
            count = mi.get("general.parameter_count")
            by_name = _parameters(details.get("parameter_size"))
            by_show = _parameters(sd.get("parameter_size"))
            arch = mi.get("general.architecture")
            license_text = show.get("license")
            license_ok = (
                isinstance(license_text, str) and
                (("Apache License" in license_text and "Version 2.0" in license_text)
                 or "Apache-2.0" in license_text)
            )
            stable_count = (
                type(count) is int and count > 0 and by_name is not None
                and by_show is not None
                and abs(by_name - count) <= 0.05 * count
                and abs(by_show - count) <= 0.05 * count
            )
            compatible_family = details.get("family") == "qwen3" and sd.get("family") == "qwen3" and arch == "qwen3"
            observed.update({
                "total_parameters": count if stable_count else None,
                "size_verified": bool(stable_count and compatible_family and count <= _MAX_PARAMS),
                "license_metadata_verified": license_ok,
                "candidate_admitted_for_smoke": bool(
                    stable_count and compatible_family and count <= _MAX_PARAMS and license_ok
                ),
                "model_family": "qwen3" if compatible_family else None,
            })
        models.append(observed)
    return {
        "schema": "HazewaveLocalModelInventory/v3",
        "harness_authority": "HAZEWAVE_HARNESS",
        "runtime_available": True,
        "endpoint_scope": "OLLAMA_LOOPBACK_ONLY",
        "total_models_installed": len(rows),
        "models": models,
        "mimo_remote_alias_exact_model_verified": False,
        "no_new_weights_downloaded": True,
        "professional_approved": False,
    }


def _available_memory_bytes() -> int:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def probe_verified_audio_case(
    *, log_path: Path, receipt_path: Path, reviewed_sha: str,
    log_sha256: str, receipt_sha256: str, model_name: str,
    expected_digest: str, transport: Callable[..., dict[str, Any]] | None = None,
    trial_id: str | None = None,
) -> dict[str, Any]:
    """A single genuine model request only when invoked with the real transport."""
    trial = secrets.token_hex(8) if trial_id is None else trial_id
    if not isinstance(trial, str) or not _TRIAL.fullmatch(trial):
        raise ModelQualificationError("TRIAL_ID_INVALID")
    if not isinstance(model_name, str) or model_name not in _KNOWN_COMPACT:
        raise ModelQualificationError("MODEL_NOT_ALLOWLISTED")
    if not isinstance(expected_digest, str) or not _SHA64.fullmatch(expected_digest):
        raise ModelQualificationError("EXPECTED_DIGEST_INVALID")
    # All evidence validation occurs before ANY potentially expensive inference.
    observation = verify_host_av_evidence(
        log_path=log_path, receipt_path=receipt_path,
        reviewed_sha=reviewed_sha,
        expected_log_sha256=log_sha256,
        expected_receipt_sha256=receipt_sha256
    )
    models = inventory_local_ollama(transport=transport)["models"]
    rows = [r for r in models if r["name"] == model_name]
    if len(rows) != 1:
        raise ModelQualificationError("LOCAL_MODEL_NOT_INSTALLED")
    qualified = rows[0]
    if qualified["local_identity_digest_sha256"] != expected_digest:
        raise ModelQualificationError("MODEL_DIGEST_MISMATCH")
    if not qualified["candidate_admitted_for_smoke"]:
        raise ModelQualificationError("MODEL_NOT_ELIGIBLE")
    if transport is None and _available_memory_bytes() < qualified["model_size_bytes"] + 536_870_912:
        raise ModelQualificationError("LOCAL_MEMORY_HEADROOM_INSUFFICIENT")
    task = HazewaveTask(
        task_id=f"local-haze-{reviewed_sha[:12]}-{trial}",
        goal="Interpret one verified synthetic audio attenuation measurement",
        required_capability="reason.general", requested_domain="HAZE"
    )
    auth = issue_authorization(route_task(task))
    validate_authorization(auth, expected_task_id=task.task_id,
                           expected_capability="reason.general")
    prompt = build_audio_prompt(
        float(observation["metrics"]["audio_attenuation_db"]),
        knowledge=("FFmpeg volumedetect quantifies level, not artistic quality.",)
    )
    request = transport if transport is not None else _direct_loopback_request
    started = time.monotonic()
    result = request("POST", "/api/chat", {
        "model": model_name, "stream": False, "format": "json",
        "messages": [
            {"role": "system", "content": "You may only analyze numeric public synthetic audio data. Do not use tools."},
            {"role": "user", "content": prompt},
        ],
        "options": {"num_predict": 128, "temperature": 0}
    })
    elapsed = time.monotonic() - started
    if not isinstance(result, dict) or result.get("model") != model_name or result.get("done") is not True:
        raise ModelQualificationError("MODEL_RESPONSE_UNFINISHED_OR_IDENTITY_MISMATCH")
    message = result.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ModelQualificationError("MODEL_RESPONSE_INVALID")
    if message.get("tool_calls"):
        raise ModelQualificationError("UNAUTHORIZED_MODEL_TOOL_CALL")
    answer = message.get("content")
    if not isinstance(answer, str) or len(answer) > 4096:
        raise ModelQualificationError("MODEL_CONTENT_INVALID")
    if type(result.get("eval_count")) is not int or type(result.get("prompt_eval_count")) is not int:
        raise ModelQualificationError("MODEL_TOKEN_METRICS_MISSING")
    if type(result.get("total_duration")) is not int or result["total_duration"] <= 0:
        raise ModelQualificationError("MODEL_DURATION_MISSING")
    try:
        parsed = json.loads(answer)
    except (TypeError, ValueError):
        parsed = None
    evaluation = evaluate_audio_decision(parsed, attenuation=float(observation["metrics"]["audio_attenuation_db"]))
    live = transport is None
    return {
        "schema": "HazewaveLocalAudioInferenceProof/v3",
        "harness_authority": "HAZEWAVE_HARNESS",
        "authorization_id": auth.authorization_id,
        "harness_authorization": "PASS",
        "task_id": auth.task_id,
        "trial_id": trial,
        "source_evidence_sha256": observation["receipt_sha256"],
        "evidence_validation": "PASS",
        "model_name": model_name,
        "model_local_digest_sha256": expected_digest,
        "model_identity_scope": "LOCAL_DIGEST_ONLY_NOT_ORIGINAL_WEIGHTS_ATTESTATION",
        "candidate_type": "LOCALLY_IDENTIFIED_COMPACT_MODEL",
        "model_is_slm_proven": False,
        "qualified_slm_production": False,
        "transport_provenance": "LOCAL_LOOPBACK" if live else "INJECTED_TEST_DOUBLE",
        "real_model_request_observed": live,
        "real_model_response_observed": live,
        "model_response_observed": True,
        "model_response_sha256": hashlib.sha256(answer.encode()).hexdigest(),
        "verifier_result": evaluation["grade"],
        "verifier_error": evaluation["error"],
        "prompt_tokens": result["prompt_eval_count"],
        "completion_tokens": result["eval_count"],
        "total_duration_ns": result["total_duration"],
        "elapsed_ms": round(elapsed * 1000, 3),
        "model_side_tool_calls": 0,
        "production_approved": False,
        "professional_audio": False,
        "limitations": [
            "One owned synthetic attenuation case cannot qualify professional audio.",
            "Ollama local digest identifies installed bytes only, not upstream original weights.",
            "Model response graded by deterministic Harness evaluator; no model-side tool execution."
        ],
    }


def write_private_result(path: Path, result: dict[str, Any]) -> str:
    path = Path(path)
    raw = (json.dumps(result, sort_keys=True, allow_nan=False) + "\n").encode()
    if len(raw) > 65536:
        raise ModelQualificationError("RECEIPT_OVERSIZE")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink() or path.exists():
        raise ModelQualificationError("RECEIPT_EXISTS")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "wb") as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
    except FileExistsError as exc:
        raise ModelQualificationError("RECEIPT_EXISTS") from exc
    return hashlib.sha256(raw).hexdigest()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover existing local compact models; do not pull or install.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--inventory", action="store_true")
    mode.add_argument("--probe", action="store_true")
    parser.add_argument("--model")
    parser.add_argument("--expected-digest")
    parser.add_argument("--log", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--reviewed-sha")
    parser.add_argument("--log-sha256")
    parser.add_argument("--receipt-sha256")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.inventory:
            outcome = inventory_local_ollama()
        else:
            if not all((args.model, args.expected_digest, args.log, args.receipt,
                        args.reviewed_sha, args.log_sha256, args.receipt_sha256, args.output)):
                raise ModelQualificationError("PROBE_INPUTS_INCOMPLETE")
            outcome = probe_verified_audio_case(
                log_path=args.log, receipt_path=args.receipt,
                reviewed_sha=args.reviewed_sha, log_sha256=args.log_sha256,
                receipt_sha256=args.receipt_sha256, model_name=args.model,
                expected_digest=args.expected_digest
            )
            outcome["checkpoint_sha256"] = write_private_result(args.output, outcome)
    except Exception as exc:
        # Treat arbitrary provider data, filesystem paths, and model outputs
        # as untrusted and never print their content on stdout/stderr.
        code = str(exc) if isinstance(exc, ModelQualificationError) else "UNCLASSIFIED_ERROR"
        if not re.fullmatch(r"[A-Z0-9_]{3,80}", code):
            code = "UNCLASSIFIED_ERROR"
        print("HAZEWAVE_LOCAL_MODEL=BLOCKED:" + code, file=sys.stderr)
        return 20
    print(json.dumps(outcome, sort_keys=True, allow_nan=False))
    return 0 if args.inventory or outcome["verifier_result"] == "PASS" else 21


if __name__ == "__main__":
    raise SystemExit(main())
