#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hazewave.harness import HAZE, WAVE, BRIDGE, HazewaveTask, issue_authorization, route_task
from hazewave.ninerouter import (
    DEFAULT_ADMISSION_RECEIPT_PATH,
    NineRouterExecutionError,
    execute_9router_messages,
    load_9router_admission_receipt,
    rank_9router_models,
)
from hazewave.nvidia import (
    DEFAULT_NVIDIA_ADMISSION_PATH,
    DEFAULT_NVIDIA_MODEL,
    DEFAULT_NVIDIA_SECRET_PATH,
    NvidiaNIMAdapter,
)
from hazewave.nvidia_proof import (
    evaluate_probe_item,
    load_probe_corpus,
    probe_request_options,
    resolve_probe_profile,
)
from hazewave.nvidia_optimization import (
    DEFAULT_NVIDIA_BENCHMARK_CAPACITY_STATE_PATH,
    DEFAULT_NVIDIA_BENCHMARK_LEARNING_PATH,
)
from hazewave.provider_benchmark import summarize_cross_provider_rows
from hazewave.provider_fabric import (
    DEFAULT_PROVIDER_LEARNING_PATH,
    ProviderRoute,
    canonicalize_ninerouter_result,
    record_provider_result,
)
from hazewave.provider_runtime import HazewaveProviderExecutionResult


def _write_private_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    temp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.chmod(0o600)
    os.replace(temp, path)
    path.chmod(0o600)


def _finalize(item: dict, result: HazewaveProviderExecutionResult) -> HazewaveProviderExecutionResult:
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


def _row(item: dict, result: HazewaveProviderExecutionResult) -> dict:
    return {
        "capability": item["capability"],
        "task_family": item.get("task_family", "generic"),
        "complexity": item.get("complexity", "UNSPECIFIED"),
        "provider": result.provider,
        "model_id": result.model_id,
        "profile": result.execution_profile,
        "semantic_pass": result.semantic_pass,
        "quality_score": result.quality_score,
        "latency_ms": result.latency_ms,
        "total_tokens": result.total_tokens,
        "reasoning_tokens": result.reasoning_tokens,
        "fallback_count": 0,
        "error_class": result.error_class,
        "output_sha256": sha256(result.content.encode("utf-8")).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--secret-file", default=str(DEFAULT_NVIDIA_SECRET_PATH))
    parser.add_argument("--nvidia-admission", default=str(DEFAULT_NVIDIA_ADMISSION_PATH))
    parser.add_argument("--9router-receipt", default=str(DEFAULT_ADMISSION_RECEIPT_PATH))
    parser.add_argument(
        "--corpus",
        default=str(ROOT / "config" / "nvidia-capability-eval-v2.json"),
    )
    parser.add_argument(
        "--learning-state",
        default=str(DEFAULT_NVIDIA_BENCHMARK_LEARNING_PATH),
    )
    parser.add_argument(
        "--optimization-state",
        default=str(DEFAULT_NVIDIA_BENCHMARK_CAPACITY_STATE_PATH),
    )
    parser.add_argument(
        "--receipt",
        default=str(
            Path.home()
            / ".local/state/hazewave/providers/cross-provider-benchmark-v1.json"
        ),
    )
    args = parser.parse_args()
    if args.samples < 2 or args.samples > 10:
        raise SystemExit("samples must be between 2 and 10")

    corpus = load_probe_corpus(args.corpus)
    nvidia = NvidiaNIMAdapter(
        secret_path=args.secret_file,
        receipt_path=args.nvidia_admission,
        optimization_state_path=args.optimization_state,
    )
    router_receipt = load_9router_admission_receipt(args.__dict__["9router_receipt"])
    if router_receipt is None:
        raise SystemExit("9Router admission receipt missing")

    domain_map = {"HAZE": HAZE, "WAVE": WAVE, "BRIDGE": BRIDGE}
    rows: list[dict] = []

    for item in corpus["items"]:
        task = HazewaveTask(
            task_id=str(item["id"]),
            goal=str(item["prompt"]),
            required_capability=str(item["capability"]),
            requested_domain=domain_map[str(item.get("domain") or "HAZE")],
        )
        authorization = issue_authorization(route_task(task))
        router_models = rank_9router_models(
            authorization=authorization,
            receipt=router_receipt,
        )
        if not router_models:
            raise SystemExit(
                f"no 9Router hard-eligible model for {item['capability']}"
            )
        router_model = router_models[0]

        for sample in range(args.samples):
            try:
                router_raw = execute_9router_messages(
                    authorization=authorization,
                    model_id=router_model,
                    messages=[{"role": "user", "content": str(item["prompt"])}],
                    receipt=router_receipt,
                    max_fallbacks=1,
                )
                latency = 0
                if router_raw.attempt_trace:
                    latency = int(router_raw.attempt_trace[-1].get("latency_ms") or 0)
                router_result = canonicalize_ninerouter_result(
                    result=router_raw,
                    capability_id=authorization.capability_id,
                    latency_ms=latency,
                )
            except NineRouterExecutionError:
                router_result = HazewaveProviderExecutionResult(
                    provider="9router",
                    provider_gateway="9router",
                    model_id=router_model,
                    execution_profile="DEFAULT",
                    capability_id=authorization.capability_id,
                    status="FAIL",
                    content="",
                    finish_reason=None,
                    prompt_tokens=None,
                    completion_tokens=None,
                    reasoning_tokens=None,
                    total_tokens=None,
                    latency_ms=0,
                    tool_calls=(),
                    error_class="NINEROUTER_EXECUTION_FAILURE",
                    http_status=None,
                    retry_after_seconds=None,
                    cost_class="ZERO_COST_VERIFIED",
                    semantic_pass=False,
                )
            router_final = _finalize(item, router_result)
            router_route = ProviderRoute(
                provider="9router",
                model_id=router_model,
                execution_profile="DEFAULT",
                capability_id=authorization.capability_id,
                cost_class="ZERO_COST_VERIFIED",
                task_family=str(item.get("task_family") or "generic"),
                complexity=str(item.get("complexity") or "UNSPECIFIED"),
                reasoning_budget=0,
            )
            record_provider_result(
                path=args.learning_state,
                route=router_route,
                result=router_final,
                fallback_used=False,
            )
            rows.append(_row(item, router_final))

            nvidia_profile = resolve_probe_profile(item)
            nvidia_options = probe_request_options(item)
            nvidia_raw = nvidia.execute(
                authorization=authorization,
                model_id=DEFAULT_NVIDIA_MODEL,
                execution_profile=nvidia_profile,
                messages=[{"role": "user", "content": str(item["prompt"])}],
                **nvidia_options,
            )
            nvidia_final = _finalize(item, nvidia_raw)
            nvidia_route = ProviderRoute(
                provider="nvidia",
                model_id=DEFAULT_NVIDIA_MODEL,
                execution_profile=nvidia_profile,
                capability_id=authorization.capability_id,
                cost_class=nvidia_final.cost_class,
                task_family=str(item.get("task_family") or "generic"),
                complexity=str(item.get("complexity") or "UNSPECIFIED"),
                reasoning_budget=int(
                    nvidia_options.get("reasoning_budget") or 0
                ),
            )
            record_provider_result(
                path=args.learning_state,
                route=nvidia_route,
                result=nvidia_final,
                fallback_used=False,
            )
            rows.append(_row(item, nvidia_final))

    summary = summarize_cross_provider_rows(rows)
    receipt = {
        "schema": "HazewaveCrossProviderBenchmarkReceipt/v2",
        "project_id": "HAZEWAVE",
        "authority": "HAZEWAVE_HARNESS",
        "samples_per_route": args.samples,
        "rows": rows,
        "summary": summary,
    }
    _write_private_json(Path(args.receipt).expanduser(), receipt)

    for capability, report in summary["capabilities"].items():
        print(f"CAPABILITY={capability}")
        for index, route in enumerate(report["ranking"], start=1):
            print(
                f"RANK={index} PROVIDER={route['provider']} "
                f"MODEL={route['model_id']} PROFILE={route['execution_profile']} "
                f"SEMANTIC_SUCCESS_RATE={route['semantic_success_rate']:.4f} "
                f"QUALITY_SCORE={route['quality_score']:.4f} "
                f"P50_LATENCY_MS={route['p50_latency_ms']:.1f} "
                f"P95_LATENCY_MS={route['p95_latency_ms']:.1f} "
                f"TOKENS_PER_SUCCESS={route['tokens_per_successful_task']:.2f} "
                f"REASONING_TOKENS_PER_SUCCESS={route['reasoning_tokens_per_success']:.2f} "
                f"EMPTY_RATE={route['empty_rate']:.4f} "
                f"RATE_LIMIT_RATE={route['rate_limit_rate']:.4f} "
                f"USEFUL_WORK_SCORE={route['useful_work_score']:.6f}"
            )
    print(f"CROSS_PROVIDER_BENCHMARK_RECEIPT={Path(args.receipt).expanduser()}")
    nvidia.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
