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
from hazewave.nvidia_optimization import (
    DEEP_HARD,
    DEEP_MEDIUM,
    FAST_CODE,
    FAST_STRUCTURED as OPT_FAST_STRUCTURED,
    reasoning_budget_for_complexity,
    select_nvidia_execution_profile,
)


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
        payload.get("schema") not in {
            "HazewaveNvidiaCapabilityEvalCorpus/v1",
            "HazewaveNvidiaCapabilityEvalCorpus/v2",
        }
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


def _restricted_python_eval(node: ast.AST, env: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, bool, str, type(None))):
            return node.value
        raise ValueError("PYTHON_BEHAVIOR_CONSTANT_FORBIDDEN")
    if isinstance(node, ast.Name):
        if node.id in env:
            return env[node.id]
        raise ValueError("PYTHON_BEHAVIOR_NAME_FORBIDDEN")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        value = _restricted_python_eval(node.operand, env)
        return -value if isinstance(node.op, ast.USub) else +value
    if isinstance(node, ast.BinOp):
        left = _restricted_python_eval(node.left, env)
        right = _restricted_python_eval(node.right, env)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            return left ** right
        raise ValueError("PYTHON_BEHAVIOR_OPERATOR_FORBIDDEN")
    if isinstance(node, ast.IfExp):
        condition = _restricted_python_eval(node.test, env)
        branch = node.body if condition else node.orelse
        return _restricted_python_eval(branch, env)
    if isinstance(node, ast.Compare):
        left = _restricted_python_eval(node.left, env)
        for operator, comparator in zip(node.ops, node.comparators):
            right = _restricted_python_eval(comparator, env)
            if isinstance(operator, ast.Lt):
                ok = left < right
            elif isinstance(operator, ast.LtE):
                ok = left <= right
            elif isinstance(operator, ast.Gt):
                ok = left > right
            elif isinstance(operator, ast.GtE):
                ok = left >= right
            elif isinstance(operator, ast.Eq):
                ok = left == right
            elif isinstance(operator, ast.NotEq):
                ok = left != right
            else:
                raise ValueError("PYTHON_BEHAVIOR_COMPARE_FORBIDDEN")
            if not ok:
                return False
            left = right
        return True
    if isinstance(node, ast.BoolOp):
        values = [_restricted_python_eval(value, env) for value in node.values]
        if isinstance(node.op, ast.And):
            return all(values)
        if isinstance(node.op, ast.Or):
            return any(values)
        raise ValueError("PYTHON_BEHAVIOR_BOOL_FORBIDDEN")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        allowed = {
            "min": min,
            "max": max,
            "int": int,
            "float": float,
            "abs": abs,
            "round": round,
        }
        function = allowed.get(node.func.id)
        if function is None or node.keywords:
            raise ValueError("PYTHON_BEHAVIOR_CALL_FORBIDDEN")
        args = [_restricted_python_eval(arg, env) for arg in node.args]
        return function(*args)
    raise ValueError("PYTHON_BEHAVIOR_NODE_FORBIDDEN")


def _evaluate_restricted_python_behavior(
    source: str,
    evaluation: dict[str, Any],
) -> ProbeEvaluation:
    try:
        tree = ast.parse(_strip_code_fence(source))
    except SyntaxError:
        return ProbeEvaluation(False, 0.0, "PYTHON_SYNTAX_INVALID")
    function_name = str(evaluation.get("function_name") or "")
    functions = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == function_name
    ]
    if len(functions) != 1:
        return ProbeEvaluation(False, 0.0, "FUNCTION_MISSING")
    function = functions[0]
    if function.decorator_list or function.returns is not None:
        return ProbeEvaluation(False, 0.0, "PYTHON_BEHAVIOR_FUNCTION_UNSAFE")
    if len(function.body) != 1 or not isinstance(function.body[0], ast.Return):
        return ProbeEvaluation(False, 0.0, "PYTHON_BEHAVIOR_BODY_UNSAFE")
    parameter_names = [arg.arg for arg in function.args.args]
    if function.args.vararg or function.args.kwarg or function.args.kwonlyargs:
        return ProbeEvaluation(False, 0.0, "PYTHON_BEHAVIOR_SIGNATURE_UNSAFE")

    cases = evaluation.get("cases")
    cases = cases if isinstance(cases, list) else []
    if not cases:
        return ProbeEvaluation(False, 0.0, "PYTHON_BEHAVIOR_CASES_REQUIRED")

    passed = 0
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("args"), list):
            continue
        args = case["args"]
        if len(args) != len(parameter_names):
            continue
        env = dict(zip(parameter_names, args))
        try:
            observed = _restricted_python_eval(function.body[0].value, env)
        except (TypeError, ValueError, ZeroDivisionError, OverflowError):
            continue
        expected = case.get("expected")
        if observed == expected:
            passed += 1
    score = passed / len(cases)
    return ProbeEvaluation(
        score == 1.0,
        score,
        "PASS" if score == 1.0 else "PYTHON_BEHAVIOR_MISMATCH",
    )


def evaluate_probe_item(
    item: dict[str, Any],
    result: HazewaveProviderExecutionResult,
) -> ProbeEvaluation:
    if result.status != "PASS" or result.semantic_pass is not True:
        return ProbeEvaluation(False, 0.0, result.error_class or "PROVIDER_RESULT_NOT_PASS")

    evaluation = item.get("evaluation")
    evaluation = evaluation if isinstance(evaluation, dict) else {}
    kind = str(evaluation.get("kind") or "")

    if kind == "RANKING_EQUIVALENT":
        try:
            actual = json.loads(result.content)
        except (TypeError, json.JSONDecodeError):
            return ProbeEvaluation(False, 0.0, "JSON_INVALID")
        labels = [str(value) for value in evaluation.get("labels") or []]
        if not labels:
            return ProbeEvaluation(False, 0.0, "RANKING_LABELS_INVALID")

        if isinstance(actual, dict) and isinstance(actual.get("order"), list):
            observed_order = [str(value) for value in actual["order"]]
        elif isinstance(actual, dict):
            try:
                ranks = {label: int(actual[label]) for label in labels}
            except (KeyError, TypeError, ValueError):
                return ProbeEvaluation(False, 0.0, "RANKING_SHAPE_INVALID")
            if sorted(ranks.values()) != list(range(1, len(labels) + 1)):
                return ProbeEvaluation(False, 0.0, "RANKING_VALUES_INVALID")
            observed_order = [
                label for label, _ in sorted(ranks.items(), key=lambda item: item[1])
            ]
        else:
            return ProbeEvaluation(False, 0.0, "RANKING_SHAPE_INVALID")

        passed = observed_order == labels
        return ProbeEvaluation(
            passed,
            1.0 if passed else 0.0,
            "PASS" if passed else "RANKING_MISMATCH",
        )

    if kind == "JSON_FIELD_SEMANTICS":
        try:
            actual = json.loads(result.content)
        except (TypeError, json.JSONDecodeError):
            return ProbeEvaluation(False, 0.0, "JSON_INVALID")
        if not isinstance(actual, dict):
            return ProbeEvaluation(False, 0.0, "JSON_OBJECT_REQUIRED")

        fields = evaluation.get("fields")
        fields = fields if isinstance(fields, dict) else {}
        if not fields:
            return ProbeEvaluation(False, 0.0, "JSON_FIELD_SEMANTICS_INVALID")

        checks: list[bool] = []
        for field, contract in fields.items():
            if field not in actual or not isinstance(contract, dict):
                checks.append(False)
                continue
            value = actual[field]
            if "equals" in contract:
                checks.append(value == contract["equals"])
                continue
            groups = contract.get("keyword_groups")
            groups = groups if isinstance(groups, list) else []
            if not isinstance(value, str) or not groups:
                checks.append(False)
                continue
            folded = value.casefold()
            field_pass = all(
                isinstance(group, list)
                and any(str(term).casefold() in folded for term in group)
                for group in groups
            )
            checks.append(field_pass)

        passed = bool(checks) and all(checks)
        score = sum(1 for check in checks if check) / max(1, len(checks))
        return ProbeEvaluation(
            passed,
            score,
            "PASS" if passed else "JSON_FIELD_SEMANTICS_MISMATCH",
        )

    if kind == "JSON_SUBSET":
        try:
            actual = json.loads(result.content)
        except (TypeError, json.JSONDecodeError):
            return ProbeEvaluation(False, 0.0, "JSON_INVALID")
        passed = _json_subset(evaluation.get("expected"), actual)
        return ProbeEvaluation(passed, 1.0 if passed else 0.0, "PASS" if passed else "JSON_SUBSET_MISMATCH")

    if kind == "PYTHON_RESTRICTED_BEHAVIOR":
        return _evaluate_restricted_python_behavior(result.content, evaluation)

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


def resolve_probe_profile(item: dict[str, Any]) -> str:
    complexity = item.get("complexity")
    if complexity is None:
        return str(item.get("execution_profile") or OPT_FAST_STRUCTURED)
    return select_nvidia_execution_profile(
        capability_id=str(item.get("capability") or ""),
        complexity=str(complexity),
        structured_output=bool(item.get("structured_output")),
    )


def probe_request_options(item: dict[str, Any]) -> dict[str, Any]:
    capability = str(item.get("capability") or "")
    evaluation = item.get("evaluation")
    evaluation = evaluation if isinstance(evaluation, dict) else {}
    profile = resolve_probe_profile(item)
    is_v2 = item.get("complexity") is not None
    complexity = str(item.get("complexity") or "SIMPLE").upper()
    options: dict[str, Any] = {
        "sampling_policy": "DETERMINISTIC_STRUCTURED",
        "seed": int(item.get("seed") or 20261005),
    }
    if not is_v2:
        if profile == "DEEP_REASONING":
            options["max_tokens"] = int(item.get("max_tokens") or 4096)
        elif capability == "code.review":
            options["max_tokens"] = int(item.get("max_tokens") or 2048)
        else:
            options["max_tokens"] = int(item.get("max_tokens") or 1024)
    elif profile == DEEP_HARD:
        options["max_tokens"] = int(item.get("max_tokens") or 8192)
    elif profile == DEEP_MEDIUM:
        options["max_tokens"] = int(item.get("max_tokens") or 4096)
    elif profile == FAST_CODE:
        options["max_tokens"] = int(item.get("max_tokens") or 2048)
    else:
        options["max_tokens"] = int(item.get("max_tokens") or 1024)

    if not is_v2 and profile == "DEEP_REASONING":
        budget = 2048
    else:
        budget = (
            0
            if profile in {OPT_FAST_STRUCTURED, FAST_CODE}
            else reasoning_budget_for_complexity(complexity)
        )
    options["reasoning_budget"] = budget

    if evaluation.get("kind") in {
        "JSON_SUBSET",
        "JSON_FIELD_SEMANTICS",
        "RANKING_EQUIVALENT",
    }:
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
        profile = resolve_probe_profile(item)
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
            task_family=str(item.get("task_family") or "generic"),
            complexity=str(item.get("complexity") or "UNSPECIFIED"),
            reasoning_budget=int(request_options.get("reasoning_budget") or 0),
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
        receipt["complexity"] = str(item.get("complexity") or "UNSPECIFIED")
        receipt["reasoning_budget"] = int(
            request_options.get("reasoning_budget") or 0
        )
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
