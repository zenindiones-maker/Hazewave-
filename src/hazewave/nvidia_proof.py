from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
import ast
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable

from hazewave.harness import HAZE, WAVE, BRIDGE, HazewaveTask, issue_authorization, route_task
from hazewave.nvidia import (
    DEFAULT_NVIDIA_ADMISSION_PATH,
    DEFAULT_NVIDIA_MODEL,
    DEFAULT_NVIDIA_SECRET_PATH,
    NvidiaNIMAdapter,
    load_nvidia_api_key,
    redact_nvidia_secrets,
)
from hazewave.provider_fabric import (
    DEFAULT_PROVIDER_LEARNING_PATH,
    ProviderRoute,
    record_provider_result,
)
from hazewave.provider_runtime import HazewaveProviderExecutionResult


DEFAULT_NVIDIA_PROOF_RECEIPT = (
    Path.home()
    / ".local"
    / "state"
    / "hazewave"
    / "providers"
    / "nvidia"
    / "runtime-proof-v1.json"
)


@dataclass(frozen=True)
class ProbeEvaluation:
    semantic_pass: bool
    quality_score: float
    reason: str


def load_probe_corpus(path: Path | str) -> dict[str, Any]:
    target = Path(path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    if (
        payload.get("schema") != "HazewaveNvidiaCapabilityEvalCorpus/v1"
        or payload.get("project_id") != "HAZEWAVE"
        or payload.get("authority") != "HAZEWAVE_HARNESS"
        or not isinstance(payload.get("items"), list)
    ):
        raise ValueError("NVIDIA_CAPABILITY_CORPUS_INVALID")
    return payload


def _strip_code_fence(text: str) -> str:
    value = str(text or "").strip()
    match = re.fullmatch(r"```(?:python)?\s*(.*?)\s*```", value, re.DOTALL)
    return match.group(1).strip() if match else value


def _json_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and _json_subset(value, actual[key])
            for key, value in expected.items()
        )
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(
            _json_subset(left, right)
            for left, right in zip(expected, actual)
        )
    return actual == expected


def evaluate_probe_item(
    item: dict[str, Any],
    result: HazewaveProviderExecutionResult,
) -> ProbeEvaluation:
    if result.status != "PASS" or result.semantic_pass is not True:
        return ProbeEvaluation(False, 0.0, result.error_class or "PROVIDER_RESULT_NOT_PASS")

    evaluation = item.get("evaluation")
    evaluation = evaluation if isinstance(evaluation, dict) else {}
    kind = str(evaluation.get("kind") or "")

    if kind == "JSON_SUBSET":
        try:
            actual = json.loads(result.content)
        except (TypeError, json.JSONDecodeError):
            return ProbeEvaluation(False, 0.0, "JSON_INVALID")
        passed = _json_subset(evaluation.get("expected"), actual)
        return ProbeEvaluation(passed, 1.0 if passed else 0.0, "PASS" if passed else "JSON_SUBSET_MISMATCH")

    if kind == "PYTHON_AST":
        source = _strip_code_fence(result.content)
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return ProbeEvaluation(False, 0.0, "PYTHON_SYNTAX_INVALID")
        function_name = str(evaluation.get("function_name") or "")
        functions = [
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        target = next((node for node in functions if node.name == function_name), None)
        if target is None:
            return ProbeEvaluation(False, 0.0, "FUNCTION_MISSING")
        names = {node.id for node in ast.walk(target) if isinstance(node, ast.Name)}
        constants = {
            node.value
            for node in ast.walk(target)
            if isinstance(node, ast.Constant)
        }
        required_names = {str(value) for value in evaluation.get("required_names") or []}
        required_constants = set(evaluation.get("required_constants") or [])
        checks = [
            required_names.issubset(names),
            required_constants.issubset(constants),
            any(isinstance(node, ast.Return) for node in ast.walk(target)),
        ]
        score = sum(1 for value in checks if value) / len(checks)
        passed = all(checks)
        return ProbeEvaluation(passed, score, "PASS" if passed else "PYTHON_AST_CONTRACT_MISMATCH")

    if kind == "KEYWORD_GROUPS":
        content = result.content.casefold()
        groups = evaluation.get("groups")
        groups = groups if isinstance(groups, list) else []
        checks = [
            any(str(term).casefold() in content for term in group)
            for group in groups
            if isinstance(group, list)
        ]
        if not checks:
            return ProbeEvaluation(False, 0.0, "KEYWORD_GROUPS_INVALID")
        score = sum(1 for value in checks if value) / len(checks)
        passed = all(checks)
        return ProbeEvaluation(passed, score, "PASS" if passed else "KEYWORD_GROUP_MISSING")

    return ProbeEvaluation(False, 0.0, "EVALUATOR_KIND_UNSUPPORTED")


def scan_paths_for_secret(
    *,
    secret: str,
    paths: Iterable[Path],
    root: Path | None = None,
) -> dict[str, Any]:
    needle = secret.encode("utf-8")
    found: list[str] = []
    base = root.resolve() if root is not None else None
    for path in paths:
        target = Path(path)
        if not target.is_file():
            continue
        try:
            data = target.read_bytes()
        except OSError:
            continue
        if needle not in data:
            continue
        try:
            shown = str(target.resolve().relative_to(base)) if base is not None else str(target)
        except ValueError:
            shown = str(target)
        found.append(shown)
    return {
        "leak_count": len(found),
        "paths": sorted(found),
    }


def _git_tracked_files(repo_root: Path) -> list[Path]:
    completed = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [
        repo_root / raw.decode("utf-8")
        for raw in completed.stdout.split(b"\0")
        if raw
    ]


def _worktree_files(repo_root: Path) -> list[Path]:
    output: list[Path] = []
    skipped_dirs = {".git", ".venv", "__pycache__", ".pytest_cache"}
    for current, dirs, files in os.walk(repo_root):
        dirs[:] = [name for name in dirs if name not in skipped_dirs]
        base = Path(current)
        for name in files:
            output.append(base / name)
    return output


def _state_files(roots: Iterable[Path]) -> list[Path]:
    output: list[Path] = []
    for root in roots:
        target = Path(root).expanduser()
        if not target.exists():
            continue
        for path in target.rglob("*"):
            if path.is_file():
                output.append(path)
    return output


def audit_nvidia_secret_boundary(
    *,
    repo_root: Path,
    secret_path: Path | str = DEFAULT_NVIDIA_SECRET_PATH,
    state_roots: Iterable[Path] | None = None,
) -> dict[str, Any]:
    secret = load_nvidia_api_key(secret_path)
    tracked = _git_tracked_files(repo_root)
    worktree = _worktree_files(repo_root)
    state = _state_files(
        state_roots
        or (
            Path.home() / ".local" / "state" / "hazewave",
            Path.home() / ".cache" / "hazewave",
            Path.home() / ".local" / "share" / "hazewave",
        )
    )
    repo_scan = scan_paths_for_secret(
        secret=secret,
        paths=tracked,
        root=repo_root,
    )
    worktree_scan = scan_paths_for_secret(
        secret=secret,
        paths=worktree,
        root=repo_root,
    )
    state_scan = scan_paths_for_secret(
        secret=secret,
        paths=state,
        root=Path.home(),
    )
    return {
        "schema": "HazewaveNvidiaSecretBoundaryAudit/v1",
        "NVIDIA_KEY_IN_GIT": "PASS" if repo_scan["leak_count"] == 0 else "FAIL",
        "NVIDIA_KEY_IN_WORKTREE": "PASS" if worktree_scan["leak_count"] == 0 else "FAIL",
        "NVIDIA_KEY_IN_STATE": "PASS" if state_scan["leak_count"] == 0 else "FAIL",
        "git_leak_count": repo_scan["leak_count"],
        "worktree_leak_count": worktree_scan["leak_count"],
        "state_leak_count": state_scan["leak_count"],
        "git_paths": repo_scan["paths"],
        "worktree_paths": worktree_scan["paths"],
        "state_paths": state_scan["paths"],
    }


def _write_private_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    temp.write_text(
        json.dumps(payload, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temp.chmod(0o600)
    os.replace(temp, path)
    path.chmod(0o600)


def probe_request_options(item: dict[str, Any]) -> dict[str, Any]:
    capability = str(item.get("capability") or "")
    evaluation = item.get("evaluation")
    evaluation = evaluation if isinstance(evaluation, dict) else {}
    options: dict[str, Any] = {}
    if capability == "reason.deep":
        options["max_tokens"] = 4096
    elif capability == "code.review":
        options["max_tokens"] = 2048
    elif capability in {"reason.general", "code.generate"}:
        options["max_tokens"] = 1024
    if evaluation.get("kind") == "JSON_SUBSET":
        options["response_format"] = {"type": "json_object"}
    return options


def run_nvidia_capability_probes(
    *,
    adapter: NvidiaNIMAdapter,
    corpus: dict[str, Any],
    learning_path: Path | str = DEFAULT_PROVIDER_LEARNING_PATH,
    receipt_path: Path | str = DEFAULT_NVIDIA_PROOF_RECEIPT,
    now: str | None = None,
    diagnostic_sink: Any | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    domain_map = {"HAZE": HAZE, "WAVE": WAVE, "BRIDGE": BRIDGE}

    for item in corpus.get("items") or []:
        capability = str(item["capability"])
        profile = str(item["execution_profile"])
        domain = domain_map[str(item.get("domain") or "HAZE")]
        task = HazewaveTask(
            task_id=str(item["id"]),
            goal=str(item["prompt"]),
            required_capability=capability,
            requested_domain=domain,
        )
        authorization = issue_authorization(route_task(task))
        request_options = probe_request_options(item)
        raw_result = adapter.execute(
            authorization=authorization,
            model_id=DEFAULT_NVIDIA_MODEL,
            execution_profile=profile,
            messages=[{"role": "user", "content": str(item["prompt"])}],
            now=now,
            **request_options,
        )
        evaluation = evaluate_probe_item(item, raw_result)
        if not evaluation.semantic_pass and diagnostic_sink is not None:
            sanitized_content = redact_nvidia_secrets(raw_result.content)
            diagnostic_sink(
                {
                    "capability": capability,
                    "execution_profile": profile,
                    "provider_status": raw_result.status,
                    "finish_reason": raw_result.finish_reason,
                    "error_class": raw_result.error_class,
                    "evaluation_reason": evaluation.reason,
                    "content": str(sanitized_content)[:4000],
                }
            )
        final_result = replace(
            raw_result,
            status="PASS" if evaluation.semantic_pass else (
                raw_result.status if raw_result.status != "PASS" else "FAIL"
            ),
            semantic_pass=evaluation.semantic_pass,
            quality_score=evaluation.quality_score,
            error_class=(
                raw_result.error_class
                if raw_result.status != "PASS"
                else (None if evaluation.semantic_pass else evaluation.reason)
            ),
        )
        route = ProviderRoute(
            provider="nvidia",
            model_id=DEFAULT_NVIDIA_MODEL,
            execution_profile=profile,
            capability_id=capability,
            cost_class=final_result.cost_class,
        )
        record_provider_result(
            path=learning_path,
            route=route,
            result=final_result,
            fallback_used=False,
            now=now,
        )
        receipt = final_result.secret_free_receipt()
        receipt["task_id"] = item["id"]
        receipt["task_family"] = item["task_family"]
        receipt["output_sha256"] = sha256(
            final_result.content.encode("utf-8")
        ).hexdigest()
        receipt["evaluation_reason"] = evaluation.reason
        results.append(receipt)

    payload = {
        "schema": "HazewaveNvidiaRuntimeProof/v1",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "provider": "nvidia",
        "model_id": DEFAULT_NVIDIA_MODEL,
        "results": results,
        "all_semantic_pass": bool(results) and all(
            row.get("semantic_pass") is True for row in results
        ),
    }
    _write_private_json(Path(receipt_path).expanduser(), payload)
    return payload
