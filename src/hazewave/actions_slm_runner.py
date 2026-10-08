"""Actions-only, pinned compact HAZE inference proof, never A15 inference.

The runner performs a real FFmpeg signal modification and compares actual
volumedetect results. It calls a loopback llama.cpp server built from pinned
source and loaded with a known SHA-256 model. Unit-test transports are not
treated as operational proof. No production or general mastering certification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import secrets
import stat
import subprocess
import sys
import time
from typing import Any, Mapping
from urllib.request import Request, ProxyHandler, HTTPRedirectHandler, build_opener

from hazewave.harness import HazewaveTask, issue_authorization, route_task, validate_authorization
from hazewave.slm_audio_specialist import evaluate_audio_decision, build_audio_prompt

MANIFEST = Path(__file__).resolve().parents[2] / "config" / "slm-actions-runner-model-v1.json"
EXPECTED_ID = "Qwen/Qwen3-0.6B-GGUF"
EXPECTED_HASH = "b0638f08417a2d3c8652760462eb5407c6e30173cf9608ad0820757a281eea0e"
EXPECTED_REVISION = "1208e45d782fe18602c5eaf10e5758d5b0f24c03"
EXPECTED_LLAMA = "d81235049384534c167caea52b85a694f6103d14"
LOOPBACK = "http://127.0.0.1:18216"
_SHA = re.compile(r"^[a-f0-9]{64}$")
_LIMIT = 131072


class RunnerProofError(RuntimeError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_model_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    try:
        raw = Path(path).read_bytes()
        if len(raw) > 8192:
            raise RunnerProofError("MANIFEST_OVERSIZE")
        info = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise RunnerProofError("MANIFEST_INVALID") from exc
    required = {
        "schema": "HazewaveActionsCompactModel/v1",
        "execution_plane": "GITHUB_ACTIONS_STANDARD_PUBLIC_ONLY",
        "authority": "HAZEWAVE_HARNESS",
        "model_id": EXPECTED_ID, "sha256": EXPECTED_HASH,
        "revision": EXPECTED_REVISION,
        "model_file": "Qwen3-0.6B-Q4_K_M.gguf",
        "license": "apache-2.0", "llama_cpp_commit": EXPECTED_LLAMA,
        "served_alias": "hazewave-qwen3-0.6b",
        "production_approved": False, "professional_approved": False,
        "a15_inference_forbidden": True
    }
    if not isinstance(info, dict) or any(info.get(k) != v or type(info.get(k)) is not type(v)
                                        for k, v in required.items()):
        raise RunnerProofError("MANIFEST_POLICY_MISMATCH")
    n = info.get("total_parameters_estimated")
    if type(n) is not int or not 100_000_000 <= n <= 1_000_000_000:
        raise RunnerProofError("PARAMETER_CLASS_MISMATCH")
    return info


def authorize_runner(environment: Mapping[str, str]):
    if (environment.get("GITHUB_ACTIONS") != "true"
            or environment.get("GITHUB_REPOSITORY") != "zenindiones-maker/Hazewave-"
            or environment.get("RUNNER_OS") != "Linux"
            or environment.get("HAZEWAVE_REPOSITORY_PUBLIC") != "true"
            or environment.get("CODESPACES") == "true"
            or bool(environment.get("TERMUX_VERSION"))):
        raise RunnerProofError("ACTIONS_PUBLIC_RUNNER_REQUIRED_A15_FORBIDDEN")
    task = HazewaveTask(
        task_id="actions-haze-qc-" + secrets.token_hex(8),
        goal="Inspect owned synthetic FFmpeg gain anomaly on public Actions runner",
        requested_domain="HAZE", required_capability="reason.general"
    )
    grant = issue_authorization(route_task(task))
    validate_authorization(grant, expected_task_id=task.task_id,
                           expected_capability="reason.general")
    if grant.domain != "HAZE":
        raise RunnerProofError("HARNESS_DOMAIN_MISMATCH")
    return grant


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_model_bytes(path: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RunnerProofError("MODEL_FILE_NOT_REGULAR")
    size = path.stat().st_size
    if not 350_000_000 <= size <= 450_000_000:
        raise RunnerProofError("MODEL_FILE_SIZE_INVALID")
    sha = _sha256(path)
    if sha != manifest["sha256"]:
        raise RunnerProofError("MODEL_CHECKSUM_MISMATCH")
    return {"model_sha256": sha, "model_size_bytes": size}


def _process(command: list[str], *, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as exc:
        raise RunnerProofError("FFMPEG_EXECUTION_FAILED") from exc


def _volumedetect(path: Path) -> float:
    run = _process(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(path),
                    "-af", "volumedetect", "-f", "null", "-"], timeout=25)
    found = re.findall(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", run.stderr)
    if len(found) != 1:
        raise RunnerProofError("FFMPEG_MEASUREMENT_MISSING")
    return float(found[0])


def evaluate_audio_metric(reference_db: float, modified_db: float, *,
                          reference_sha: str, modified_sha: str) -> dict[str, Any]:
    if not (_SHA.fullmatch(reference_sha) and _SHA.fullmatch(modified_sha)):
        raise RunnerProofError("AUDIO_DIGEST_INVALID")
    if reference_sha == modified_sha:
        raise RunnerProofError("AUDIO_NEGATIVE_CONTROL_FAILED")
    attenuation = round(reference_db - modified_db, 3)
    if not 11.5 <= attenuation <= 12.5:
        raise RunnerProofError("AUDIO_NEGATIVE_CONTROL_FAILED")
    return {"attenuation_db": attenuation,
            "metric_negative_control": "PASS",
            "reference_audio_sha256": reference_sha,
            "altered_audio_sha256": modified_sha,
            "mean_reference_dbfs": reference_db,
            "mean_altered_dbfs": modified_db}


def make_audio_evidence(root: Path) -> dict[str, Any]:
    ref, changed = root / "reference.wav", root / "attenuated.wav"
    _process(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
              "-f", "lavfi", "-i",
              "sine=frequency=440:sample_rate=16000:duration=1",
              "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(ref)])
    _process(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
              "-i", str(ref), "-af", "volume=0.25",
              "-c:a", "pcm_s16le", str(changed)])
    return evaluate_audio_metric(
        _volumedetect(ref), _volumedetect(changed),
        reference_sha=_sha256(ref), modified_sha=_sha256(changed)
    )


def verify_llama_response(body: Any, expected_model: str) -> dict[str, Any]:
    if not isinstance(body, dict) or body.get("model") != expected_model:
        raise RunnerProofError("MODEL_RESPONSE_IDENTITY_INVALID")
    choices = body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise RunnerProofError("MODEL_RESPONSE_CHOICES_INVALID")
    choice = choices[0]
    if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
        raise RunnerProofError("MODEL_RESPONSE_UNFINISHED")
    msg = choice.get("message")
    if (not isinstance(msg, dict) or msg.get("role") != "assistant"
            or msg.get("tool_calls") or msg.get("function_call")):
        raise RunnerProofError("MODEL_RESPONSE_UNAUTHORIZED_OR_INVALID")
    content = msg.get("content")
    if not isinstance(content, str) or not 0 < len(content) <= 4096:
        raise RunnerProofError("MODEL_RESPONSE_CONTENT_INVALID")
    try:
        decision = json.loads(content)
    except ValueError:
        decision = None
    usage = body.get("usage")
    if not isinstance(usage, dict) or any(
        type(usage.get(k)) is not int or usage[k] < 0
        for k in ("prompt_tokens", "completion_tokens", "total_tokens")
    ):
        raise RunnerProofError("MODEL_TOKEN_METRICS_INVALID")
    return {"decision": decision, "tokens": usage["total_tokens"],
            "prompt_tokens": usage["prompt_tokens"], "completion_tokens": usage["completion_tokens"],
            "content_sha256": hashlib.sha256(content.encode()).hexdigest()}


_AUDIO_DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "finding": {"type": "string", "enum": ["ATTENUATION_DETECTED", "NO_ISSUE_DETECTED"]},
        "action": {"type": "string", "enum": ["REVIEW_GAIN_STAGE", "NO_ACTION"]},
        "evidence_keys": {
            "type": "array",
            "items": {"type": "string", "enum": ["audio_attenuation_db"]},
            "minItems": 1, "maxItems": 1,
        },
        "requires_human_review": {"type": "boolean"},
    },
    "required": ["finding", "action", "evidence_keys", "requires_human_review"],
    "additionalProperties": False,
}


def classify_audio_decision_failure(decision: Any, attenuation: float) -> str:
    """Return a non-sensitive fixed reason; independent strict grader decides PASS."""
    if type(decision) is not dict:
        return "NONOBJECT_OR_INVALID_JSON"
    if set(decision) != set(_AUDIO_DECISION_SCHEMA["required"]):
        return "EXTRA_OR_MISSING_KEYS"
    target = ("ATTENUATION_DETECTED", "REVIEW_GAIN_STAGE") if 10 <= attenuation <= 14 else (
        "NO_ISSUE_DETECTED", "NO_ACTION"
    )
    if decision.get("finding") != target[0]:
        return "FINDING_MISMATCH"
    if decision.get("action") != target[1]:
        return "ACTION_MISMATCH"
    if decision.get("evidence_keys") != ["audio_attenuation_db"]:
        return "EVIDENCE_KEYS_MISMATCH"
    if decision.get("requires_human_review") is not True:
        return "HUMAN_REVIEW_FLAG_MISMATCH"
    return "NONE"


def _model_request_payload(prompt: str, model: str) -> dict[str, Any]:
    # Both semantic choices remain possible in the grammar. Grammar does not
    # supply the correct answer: the model must reason about the FFmpeg metric.
    return {
        "model": model, "stream": False, "temperature": 0,
        "max_tokens": 240,
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {
            "type": "json_schema",
            "schema": _AUDIO_DECISION_SCHEMA,
        },
        "messages": [
            {"role": "system", "content":
             "You evaluate a single measured audio anomaly. Never call tools. "
             "Return exactly one JSON object with the four requested keys."},
            {"role": "user", "content": prompt},
        ],
    }


def _request_model(prompt: str, model: str) -> dict[str, Any]:
    # Network is limited to one literal process-local HTTP endpoint.
    request = Request(LOOPBACK + "/v1/chat/completions",
        method="POST", headers={"Content-Type": "application/json"},
        data=json.dumps(_model_request_payload(prompt, model)).encode())
    try:
        with build_opener(ProxyHandler({}), _NoRedirect()).open(request, timeout=90) as answer:
            payload = answer.read(_LIMIT + 1)
        if len(payload) > _LIMIT:
            raise RunnerProofError("MODEL_HTTP_RESPONSE_OVERSIZE")
        result = json.loads(payload)
    except (OSError, ValueError) as exc:
        if isinstance(exc, RunnerProofError):
            raise
        raise RunnerProofError("MODEL_LOCAL_HTTP_FAILED") from exc
    return result


def write_receipt(path: Path, data: dict[str, Any]) -> str:
    raw = (json.dumps(data, sort_keys=True, allow_nan=False) + "\n").encode()
    if len(raw) > 32768:
        raise RunnerProofError("RECEIPT_TOO_LARGE")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    except FileExistsError as exc:
        raise RunnerProofError("RECEIPT_EXISTS") from exc
    with os.fdopen(fd, "wb") as output:
        output.write(raw)
        output.flush()
        os.fsync(output.fileno())
    return hashlib.sha256(raw).hexdigest()


def _memory_available() -> int:
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemAvailable:"):
                return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--inventory", action="store_true")
    modes.add_argument("--prove", action="store_true")
    parser.add_argument("--model", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        manifest = validate_model_manifest()
        grant = authorize_runner(os.environ)
        if args.inventory:
            result = {
                "schema": "HazewaveActionsRunnerPreflight/v1",
                "authority": "HAZEWAVE_HARNESS",
                "runner_scope": "EPHEMERAL_PUBLIC_REPOSITORY",
                "model_preinstalled": False,
                "model_download_permitted_only_after_inventory": True,
                "models_on_a15": "NOT_INSPECTED_OR_REQUIRED",
                "model_source": manifest["model_source"],
                "model_checksum_expected": manifest["sha256"],
                "ram_available_bytes": _memory_available(),
                "cost": "STANDARD_PUBLIC_GITHUB_HOSTED_NO_PAID_RUNNER",
                "production_approved": False,
            }
            if result["ram_available_bytes"] < 3 * 1024**3:
                raise RunnerProofError("RUNNER_MEMORY_HEADROOM_INSUFFICIENT")
            print(json.dumps(result, sort_keys=True))
            return 0
        if not args.model or not args.output:
            raise RunnerProofError("PROOF_ARGUMENTS_MISSING")
        model_evidence = verify_model_bytes(args.model, manifest)
        if _memory_available() < 3 * 1024**3:
            raise RunnerProofError("RUNNER_MEMORY_HEADROOM_INSUFFICIENT")
        started = time.monotonic()
        metrics = make_audio_evidence(args.output.parent)
        prompt = build_audio_prompt(metrics["attenuation_db"],
                                    knowledge=("FFmpeg volumedetect measures signal level; not mastering quality.",))
        result = _request_model(prompt, manifest["served_alias"])
        judged = verify_llama_response(result, manifest["served_alias"])
        grade = evaluate_audio_decision(judged["decision"], attenuation=metrics["attenuation_db"])
        failure_class = classify_audio_decision_failure(judged["decision"], metrics["attenuation_db"])
        # Never upgrade based on a categorizer. Reject internal disagreements.
        if (failure_class == "NONE") != (grade["grade"] == "PASS"):
            raise RunnerProofError("AUDIO_VERIFIER_CLASSIFIER_DISAGREEMENT")
        record = {
            "schema": "HazewaveActionsSLMExecution/v1",
            "authority": "HAZEWAVE_HARNESS",
            "task_id": grant.task_id,
            "authorization_id_sha256": hashlib.sha256(grant.authorization_id.encode()).hexdigest(),
            "model_id": manifest["model_id"],
            "model_revision": manifest["revision"],
            **model_evidence,
            "runtime_commit": manifest["llama_cpp_commit"],
            "model_parameter_class": "0.6B_DENSE_REPORTED",
            "model_identity": "PINNED_PUBLIC_REPO_AND_VERIFIED_FILE_DIGEST",
            "model_response_sha256": judged["content_sha256"],
            "model_real_request": True, "model_real_response": True,
            "transport": "GITHUB_ACTIONS_CPU_RUNNER_LOOPBACK",
            "audio_metrics": metrics,
            "audio_verifier_result": grade["grade"],
            "audio_verifier_error": grade["error"],
            "audio_failure_class": failure_class,
            "json_schema_constrained_generation_requested": True,
            "json_schema_server_enforcement_independently_proven": False,
            "tokens": judged["tokens"], "prompt_tokens": judged["prompt_tokens"],
            "completion_tokens": judged["completion_tokens"],
            "total_elapsed_ms": round((time.monotonic()-started)*1000, 1),
            "maxrss_kib_this_runner_process": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "case_count": 1,
            "independent_case_diversity_proven": False,
            "agent_tools_connected": False,
            "model_benchmark_superiority_proven": False,
            "professional_audio": False,
            "production_approved": False,
            "a15_inference": False,
            "cost": "NO_PAID_RUNNER_PUBLIC_REPOSITORY",
        }
        sha = write_receipt(args.output, record)
        print("HAZE_ACTIONS_MODEL_REAL_RESPONSE=PASS")
        print("HAZE_ACTIONS_AUDIO_VERIFIER=" + grade["grade"])
        print("HAZE_ACTIONS_FAILURE_CLASS=" + failure_class)
        print("HAZE_ACTIONS_RECEIPT_SHA256=" + sha)
        print("HAZE_ACTIONS_MODEL_SHA256=" + manifest["sha256"])
        print("A15_INFERENCE=FORBIDDEN")
        print("HAZE_PROFESSIONAL=FALSE")
        return 0 if grade["grade"] == "PASS" else 21
    except (RunnerProofError, OSError, ValueError) as exc:
        reason = str(exc) if isinstance(exc, RunnerProofError) else type(exc).__name__.upper()
        if not re.fullmatch(r"[A-Z0-9_]{3,128}", reason):
            reason = "VERIFICATION_FAILED"
        print("HAZE_ACTIONS_INFERENCE=BLOCKED:" + reason, file=sys.stderr)
        return 20


if __name__ == "__main__":
    raise SystemExit(main())
