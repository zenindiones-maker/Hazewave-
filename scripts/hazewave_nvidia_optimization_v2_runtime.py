#!/usr/bin/env python3
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hazewave.harness import HAZE, WAVE, BRIDGE, HazewaveTask, issue_authorization, route_task
from hazewave.nvidia import (
    DEFAULT_NVIDIA_ADMISSION_PATH,
    DEFAULT_NVIDIA_MODEL,
    DEFAULT_NVIDIA_SECRET_PATH,
    FAST_STRUCTURED,
    NvidiaNIMAdapter,
    load_nvidia_admission,
    load_nvidia_api_key,
    probe_hosted_guided_json,
)
from hazewave.nvidia_experiments import (
    compare_parameter_ab,
    select_minimum_reasoning_budget,
    select_sustainable_concurrency,
)
from hazewave.nvidia_optimization import (
    DEEP_HARD,
    DEFAULT_NVIDIA_OPTIMIZATION_STATE_PATH,
)
from hazewave.nvidia_proof import (
    evaluate_probe_item,
    load_probe_corpus,
    probe_request_options,
    resolve_probe_profile,
)

DEFAULT_CORPUS = ROOT / "config" / "nvidia-capability-eval-v2.json"
DEFAULT_EXPERIMENT_ROOT = (
    Path.home() / ".local" / "state" / "hazewave" / "providers" / "nvidia" / "experiments-v2"
)


def _write_private(path: Path, payload: dict[str, Any]) -> None:
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


def _authorization(item: dict[str, Any]):
    domain_map = {"HAZE": HAZE, "WAVE": WAVE, "BRIDGE": BRIDGE}
    task = HazewaveTask(
        task_id=str(item["id"]),
        goal=str(item["prompt"]),
        required_capability=str(item["capability"]),
        requested_domain=domain_map[str(item.get("domain") or "HAZE")],
    )
    return issue_authorization(route_task(task))


def _finalize(item: dict[str, Any], result):
    evaluation = evaluate_probe_item(item, result)
    return replace(
        result,
        status="PASS" if evaluation.semantic_pass else (
            result.status if result.status != "PASS" else "FAIL"
        ),
        semantic_pass=evaluation.semantic_pass,
        quality_score=evaluation.quality_score,
        error_class=(
            result.error_class
            if result.status != "PASS"
            else (None if evaluation.semantic_pass else evaluation.reason)
        ),
    )


def _evidence_row(item: dict[str, Any], result, *, seed: int, budget: int | None = None):
    return {
        "task_id": str(item["id"]),
        "task_family": str(item.get("task_family") or "generic"),
        "capability": str(item["capability"]),
        "model_id": result.model_id,
        "execution_profile": result.execution_profile,
        "seed": seed,
        "reasoning_budget": budget,
        "semantic_pass": result.semantic_pass,
        "quality_score": result.quality_score,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "reasoning_tokens": result.reasoning_tokens,
        "total_tokens": result.total_tokens,
        "latency_ms": result.latency_ms,
        "error_class": result.error_class,
        "output_sha256": sha256(result.content.encode("utf-8")).hexdigest(),
    }


def _adapter(args) -> NvidiaNIMAdapter:
    return NvidiaNIMAdapter(
        secret_path=args.secret_file,
        receipt_path=args.admission,
        optimization_state_path=args.optimization_state,
    )


def run_guided_json(args) -> int:
    result = probe_hosted_guided_json(
        secret_path=args.secret_file,
        model_id=DEFAULT_NVIDIA_MODEL,
    )
    payload = {
        "schema": "HazewaveNvidiaGuidedJsonCanaryReceipt/v1",
        "authority": "HAZEWAVE_HARNESS",
        "provider": "nvidia",
        "model_id": DEFAULT_NVIDIA_MODEL,
        "status": result.status,
        "http_status": result.http_status,
        "schema_valid": result.schema_valid,
        "error_class": result.error_class,
        "auto_admission": False,
    }
    receipt = Path(args.receipt or (DEFAULT_EXPERIMENT_ROOT / "guided-json-canary.json")).expanduser()
    _write_private(receipt, payload)
    print(f"GUIDED_JSON_HOSTED_STATUS={result.status}")
    print(f"GUIDED_JSON_SCHEMA_VALID={str(result.schema_valid).lower()}")
    print("GUIDED_JSON_AUTO_ADMISSION=false")
    print(f"GUIDED_JSON_RECEIPT={receipt}")
    return 0 if result.status in {"SUPPORTED", "UNSUPPORTED"} else 1


def run_parameter_ab(args) -> int:
    corpus = load_probe_corpus(args.corpus)
    item = next(
        row for row in corpus["items"]
        if row["capability"] == "reason.general"
        and row.get("structured_output") is True
    )
    auth = _authorization(item)
    seed = int(args.seed)
    common = {
        "authorization": auth,
        "model_id": DEFAULT_NVIDIA_MODEL,
        "execution_profile": FAST_STRUCTURED,
        "messages": [{"role": "user", "content": str(item["prompt"])}],
        "response_format": {"type": "json_object"},
        "sampling_policy": "DETERMINISTIC_STRUCTURED",
        "seed": seed,
        "max_tokens": 1024,
    }
    adapter = _adapter(args)
    try:
        off = _finalize(
            item,
            adapter.execute(
                **common,
                enable_thinking_override=False,
                reasoning_budget=512,
            ),
        )
        on = _finalize(
            item,
            adapter.execute(
                **common,
                enable_thinking_override=True,
                reasoning_budget=512,
            ),
        )
    finally:
        adapter.close()

    control = _evidence_row(item, off, seed=seed, budget=0)
    candidate = _evidence_row(item, on, seed=seed, budget=512)
    delta = compare_parameter_ab(control, candidate)
    payload = {
        "schema": "HazewaveNvidiaParameterABReceipt/v1",
        "authority": "HAZEWAVE_HARNESS",
        "hypothesis": "thinking_off_vs_on_short_structured",
        "experimental_dimension": "enable_thinking",
        "control": control,
        "candidate": candidate,
        "delta": delta,
    }
    receipt = Path(args.receipt or (DEFAULT_EXPERIMENT_ROOT / "parameter-ab-thinking.json")).expanduser()
    _write_private(receipt, payload)
    print(f"AB_SEMANTIC_DELTA={delta['semantic_success_delta']}")
    print(f"AB_QUALITY_DELTA={delta['quality_delta']:.6f}")
    print(f"AB_TOKEN_DELTA={delta['token_delta']}")
    print(f"AB_LATENCY_DELTA_MS={delta['latency_delta_ms']}")
    print(f"AB_RECEIPT={receipt}")
    return 0


def run_reasoning_sweep(args) -> int:
    corpus = load_probe_corpus(args.corpus)
    item = next(
        row for row in corpus["items"]
        if row["capability"] == "reason.deep"
        and str(row.get("complexity")) == "HARD"
    )
    auth = _authorization(item)
    seed = int(args.seed)
    rows = []
    adapter = _adapter(args)
    try:
        for budget in (512, 1024, 2048, 4096):
            result = adapter.execute(
                authorization=auth,
                model_id=DEFAULT_NVIDIA_MODEL,
                execution_profile=DEEP_HARD,
                messages=[{"role": "user", "content": str(item["prompt"])}],
                response_format={"type": "json_object"},
                sampling_policy="DETERMINISTIC_STRUCTURED",
                seed=seed,
                max_tokens=8192,
                reasoning_budget=budget,
            )
            rows.append(
                _evidence_row(
                    item,
                    _finalize(item, result),
                    seed=seed,
                    budget=budget,
                )
            )
    finally:
        adapter.close()

    selected = select_minimum_reasoning_budget(
        rows,
        quality_floor=float(args.quality_floor),
    )
    payload = {
        "schema": "HazewaveNvidiaReasoningBudgetSweepReceipt/v1",
        "authority": "HAZEWAVE_HARNESS",
        "hypothesis": "minimum_reasoning_budget_preserving_quality",
        "same_model": True,
        "same_task": True,
        "same_seed": True,
        "rows": rows,
        "selected_budget": selected,
        "quality_floor": float(args.quality_floor),
    }
    receipt = Path(args.receipt or (DEFAULT_EXPERIMENT_ROOT / "reasoning-budget-sweep.json")).expanduser()
    _write_private(receipt, payload)
    print(f"REASONING_BUDGET_SELECTED={selected}")
    print(f"REASONING_SWEEP_RECEIPT={receipt}")
    return 0 if selected is not None else 1


def run_concurrency_sweep(args) -> int:
    corpus = load_probe_corpus(args.corpus)
    item = next(
        row for row in corpus["items"]
        if row["capability"] == "reason.general"
        and row.get("complexity") == "SIMPLE"
    )
    levels = [value for value in (1, 2, 4, 8) if value <= int(args.max_concurrency)]
    points = []
    # This runner itself is the Harness-owned experiment controller. Durable
    # production AIMD is intentionally not mutated by experimental concurrency.
    adapter = NvidiaNIMAdapter(
        secret_path=args.secret_file,
        receipt_path=args.admission,
        optimization_state_path=None,
        max_connections=max(levels),
        max_keepalive_connections=max(1, min(4, max(levels))),
    )
    try:
        for level in levels:
            samples = max(4, level * 2)
            results = []
            with ThreadPoolExecutor(max_workers=level) as pool:
                futures = [
                    pool.submit(
                        adapter.execute,
                        authorization=_authorization(item),
                        model_id=DEFAULT_NVIDIA_MODEL,
                        execution_profile=resolve_probe_profile(item),
                        messages=[{"role": "user", "content": str(item["prompt"])}],
                        **probe_request_options(item),
                    )
                    for _ in range(samples)
                ]
                for future in as_completed(futures):
                    results.append(_finalize(item, future.result()))
            semantic = sum(1 for row in results if row.semantic_pass is True)
            latencies = sorted(row.latency_ms for row in results)
            p95_index = max(0, min(len(latencies) - 1, int((0.95 * len(latencies) + 0.9999)) - 1))
            point = {
                "concurrency": level,
                "sample_count": len(results),
                "semantic_success_rate": semantic / max(1, len(results)),
                "p95_latency_ms": float(latencies[p95_index]),
                "429_rate": sum(1 for row in results if row.error_class == "RATE_LIMITED") / max(1, len(results)),
                "fallback_rate": 0.0,
            }
            points.append(point)
            if level > 1:
                try:
                    selected_so_far = select_sustainable_concurrency(points)
                except ValueError:
                    selected_so_far = 1
                if selected_so_far < level:
                    break
    finally:
        adapter.close()

    selected = select_sustainable_concurrency(points)
    payload = {
        "schema": "HazewaveNvidiaConcurrencySweepReceipt/v1",
        "authority": "HAZEWAVE_HARNESS",
        "experiment_controller": "HAZEWAVE_HARNESS",
        "production_aimd_mutated": False,
        "points": points,
        "sustainable_concurrency": selected,
    }
    receipt = Path(args.receipt or (DEFAULT_EXPERIMENT_ROOT / "concurrency-sweep.json")).expanduser()
    _write_private(receipt, payload)
    print(f"SUSTAINABLE_CONCURRENCY={selected}")
    for point in points:
        print(
            "CONCURRENCY_POINT "
            f"C={point['concurrency']} "
            f"SEMANTIC_SUCCESS_RATE={point['semantic_success_rate']:.4f} "
            f"P95_LATENCY_MS={point['p95_latency_ms']:.1f} "
            f"429_RATE={point['429_rate']:.4f}"
        )
    print(f"CONCURRENCY_SWEEP_RECEIPT={receipt}")
    return 0


def run_model_canary(args) -> int:
    receipt = load_nvidia_admission(args.admission)
    lifecycle = receipt.get("model_lifecycle") or {}
    models = [
        model for model, row in lifecycle.items()
        if isinstance(row, dict) and row.get("stage") == "COST_STATUS_VERIFIED"
    ]
    if args.model:
        models = [args.model]
    api_key = load_nvidia_api_key(args.secret_file)
    rows = []
    with httpx.Client(
        base_url="https://integrate.api.nvidia.com/v1",
        timeout=float(args.timeout),
    ) as client:
        for model in models:
            try:
                response = client.post(
                    "/chat/completions",
                    json={
                        "model": model,
                        "messages": [
                            {
                                "role": "user",
                                "content": "Respond exactly HAZEWAVE_NVIDIA_CANARY_OK",
                            }
                        ],
                        "max_tokens": 64,
                        "stream": False,
                        "temperature": 0.0,
                        "chat_template_kwargs": {"enable_thinking": False},
                    },
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
                content = ""
                if response.status_code == 200:
                    try:
                        content = str(response.json()["choices"][0]["message"]["content"]).strip()
                    except (KeyError, IndexError, TypeError, ValueError):
                        content = ""
                semantic_pass = response.status_code == 200 and content == "HAZEWAVE_NVIDIA_CANARY_OK"
                rows.append(
                    {
                        "model_id": model,
                        "http_status": response.status_code,
                        "semantic_pass": semantic_pass,
                        "stage_before": lifecycle.get(model, {}).get("stage"),
                        "auto_admission": False,
                        "output_sha256": sha256(content.encode("utf-8")).hexdigest(),
                    }
                )
            except httpx.HTTPError:
                rows.append(
                    {
                        "model_id": model,
                        "http_status": None,
                        "semantic_pass": False,
                        "stage_before": lifecycle.get(model, {}).get("stage"),
                        "auto_admission": False,
                        "output_sha256": sha256(b"").hexdigest(),
                    }
                )
    payload = {
        "schema": "HazewaveNvidiaModelCanaryReceipt/v1",
        "authority": "HAZEWAVE_HARNESS",
        "rows": rows,
    }
    receipt_path = Path(args.receipt or (DEFAULT_EXPERIMENT_ROOT / "model-canary.json")).expanduser()
    _write_private(receipt_path, payload)
    for row in rows:
        print(
            f"MODEL={row['model_id']} HTTP={row['http_status']} "
            f"SEMANTIC_PASS={str(row['semantic_pass']).lower()} "
            "AUTO_ADMISSION=false"
        )
    print(f"MODEL_CANARY_RECEIPT={receipt_path}")
    return 0 if rows and all(row["semantic_pass"] for row in rows) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secret-file", default=str(DEFAULT_NVIDIA_SECRET_PATH))
    parser.add_argument("--admission", default=str(DEFAULT_NVIDIA_ADMISSION_PATH))
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument(
        "--optimization-state",
        default=str(DEFAULT_EXPERIMENT_ROOT / "capacity-state.json"),
    )
    parser.add_argument("--seed", type=int, default=20261005)
    parser.add_argument("--receipt")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("guided-json")
    sub.add_parser("parameter-ab")
    reasoning = sub.add_parser("reasoning-sweep")
    reasoning.add_argument("--quality-floor", type=float, default=0.95)
    concurrency = sub.add_parser("concurrency-sweep")
    concurrency.add_argument("--max-concurrency", type=int, default=4)
    model = sub.add_parser("model-canary")
    model.add_argument("--model")
    model.add_argument("--timeout", type=float, default=60.0)

    args = parser.parse_args()
    if args.command == "guided-json":
        return run_guided_json(args)
    if args.command == "parameter-ab":
        return run_parameter_ab(args)
    if args.command == "reasoning-sweep":
        return run_reasoning_sweep(args)
    if args.command == "concurrency-sweep":
        return run_concurrency_sweep(args)
    if args.command == "model-canary":
        return run_model_canary(args)
    raise SystemExit("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
