#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from hazewave.harness import HAZE, HazewaveTask, issue_authorization, route_task
from hazewave.nvidia import (
    DEFAULT_NVIDIA_ADMISSION_PATH,
    DEFAULT_NVIDIA_MODEL,
    DEFAULT_NVIDIA_SECRET_PATH,
    FAST_STRUCTURED,
    NvidiaNIMAdapter,
)
from hazewave.nvidia_proof import (
    DEFAULT_NVIDIA_PROOF_RECEIPT,
    audit_nvidia_secret_boundary,
    load_probe_corpus,
    run_nvidia_capability_probes,
    select_probe_items,
)
from hazewave.provider_fabric import DEFAULT_PROVIDER_LEARNING_PATH
from hazewave.nvidia_optimization import (
    DEFAULT_NVIDIA_PROOF_CAPACITY_STATE_PATH,
    DEFAULT_NVIDIA_PROOF_LEARNING_PATH,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secret-file", default=str(DEFAULT_NVIDIA_SECRET_PATH))
    parser.add_argument("--admission", default=str(DEFAULT_NVIDIA_ADMISSION_PATH))
    parser.add_argument(
        "--corpus",
        default=str(ROOT / "config" / "nvidia-capability-eval-v2.json"),
    )
    parser.add_argument("--receipt", default=str(DEFAULT_NVIDIA_PROOF_RECEIPT))
    parser.add_argument(
        "--learning-state",
        default=str(DEFAULT_NVIDIA_PROOF_LEARNING_PATH),
    )
    parser.add_argument(
        "--optimization-state",
        default=str(DEFAULT_NVIDIA_PROOF_CAPACITY_STATE_PATH),
    )
    parser.add_argument("--diagnostic-failures", action="store_true")
    parser.add_argument(
        "--task-id",
        action="append",
        default=[],
        help="Run only the exact representative task id; repeatable.",
    )
    parser.add_argument(
        "--runtime-revision",
        default=os.environ.get("HAZEWAVE_RUNTIME_REVISION", "UNRESOLVED"),
    )
    args = parser.parse_args()

    revision = str(args.runtime_revision or "").strip().lower()
    if (
        len(args.runtime_revision) != 40
        or any(ch not in "0123456789abcdef" for ch in revision)
    ):
        print("NVIDIA_RUNTIME_REVISION_REQUIRED=FAIL")
        print("EXPECTED_FORMAT=40_HEX_COMMIT_SHA")
        return 2
    args.runtime_revision = revision
    print("NVIDIA_RUNTIME_REVISION_REQUIRED=PASS")

    if args.task_id and (
        Path(args.receipt).expanduser()
        == Path(DEFAULT_NVIDIA_PROOF_RECEIPT).expanduser()
    ):
        print("NVIDIA_FILTERED_PROOF_RECEIPT_REQUIRED=FAIL")
        print("REASON=FILTERED_PROOF_MUST_NOT_OVERWRITE_CANONICAL_RECEIPT")
        return 2

    corpus = load_probe_corpus(args.corpus)
    try:
        corpus = select_probe_items(corpus, args.task_id)
    except ValueError as exc:
        print("NVIDIA_PROBE_SELECTION=FAIL")
        print("ERROR=" + str(exc))
        return 2
    print("NVIDIA_PROBE_SELECTION=PASS")
    print("NVIDIA_PROBE_SELECTED_COUNT=" + str(len(corpus.get("items") or [])))

    adapter = NvidiaNIMAdapter(
        secret_path=args.secret_file,
        receipt_path=args.admission,
        optimization_state_path=args.optimization_state,
    )

    smoke_task = HazewaveTask(
        task_id="hazewave-nvidia-strict-smoke",
        goal="strict NVIDIA transport and semantic contract",
        required_capability="reason.general",
        requested_domain=HAZE,
    )
    smoke_auth = issue_authorization(route_task(smoke_task))
    smoke = adapter.execute(
        authorization=smoke_auth,
        model_id=DEFAULT_NVIDIA_MODEL,
        execution_profile=FAST_STRUCTURED,
        messages=[
            {
                "role": "user",
                "content": "Respond with exactly HAZEWAVE_NVIDIA_OK and nothing else.",
            }
        ],
        semantic_validator=lambda content, tool_calls: (
            content == "HAZEWAVE_NVIDIA_OK" and not tool_calls
        ),
    )

    print("NVIDIA_AUTH=" + ("PASS" if smoke.http_status == 200 else "FAIL"))
    print("NVIDIA_MODEL_ACCESS=" + ("PASS" if smoke.http_status == 200 else "FAIL"))
    print(
        "NVIDIA_SEMANTIC_CONTRACT="
        + ("PASS" if smoke.semantic_pass is True else "FAIL")
    )
    print(
        "HAZEWAVE_NVIDIA_STRICT_PROBE="
        + ("PASS" if smoke.status == "PASS" and smoke.semantic_pass else "FAIL")
    )
    if not smoke.successful:
        return 1

    def emit_diagnostic(row):
        print(
            "NVIDIA_CAPABILITY_DIAGNOSTIC "
            f"CAPABILITY={row['capability']} "
            f"PROFILE={row['execution_profile']} "
            f"PROVIDER_STATUS={row['provider_status']} "
            f"FINISH_REASON={row['finish_reason']} "
            f"ERROR_CLASS={row['error_class']} "
            f"EVALUATION_REASON={row['evaluation_reason']} "
            "CONTENT_JSON="
            + json.dumps(row["content"], ensure_ascii=False)
        )

    proof = run_nvidia_capability_probes(
        adapter=adapter,
        corpus=corpus,
        learning_path=args.learning_state,
        receipt_path=args.receipt,
        diagnostic_sink=(
            emit_diagnostic if args.diagnostic_failures else None
        ),
        runtime_revision=args.runtime_revision,
    )
    print("NVIDIA_PROOF_RUNTIME_REVISION=" + args.runtime_revision)
    print("NVIDIA_PROOF_EXECUTED_COUNT=" + str(proof["executed_count"]))
    print("NVIDIA_PROOF_RESUMED_PASS_COUNT=" + str(proof["resumed_pass_count"]))
    for row in proof["results"]:
        print(
            "NVIDIA_CAPABILITY_PROBE "
            f"CAPABILITY={row['capability_id']} "
            f"PROFILE={row['execution_profile']} "
            f"STATUS={row['status']} "
            f"SEMANTIC_PASS={str(row['semantic_pass']).lower()} "
            f"PROMPT_TOKENS={row['prompt_tokens']} "
            f"COMPLETION_TOKENS={row['completion_tokens']} "
            f"REASONING_TOKENS={row['reasoning_tokens']} "
            f"TOTAL_TOKENS={row['total_tokens']} "
            f"LATENCY_MS={row['latency_ms']}"
        )

    audit = audit_nvidia_secret_boundary(
        repo_root=ROOT,
        secret_path=args.secret_file,
    )
    print("NVIDIA_KEY_IN_GIT=" + audit["NVIDIA_KEY_IN_GIT"])
    print("NVIDIA_KEY_IN_WORKTREE=" + audit["NVIDIA_KEY_IN_WORKTREE"])
    print("NVIDIA_KEY_IN_STATE=" + audit["NVIDIA_KEY_IN_STATE"])
    print(
        "NVIDIA_SECRET_BOUNDARY="
        + (
            "PASS"
            if audit["NVIDIA_KEY_IN_GIT"] == "PASS"
            and audit["NVIDIA_KEY_IN_WORKTREE"] == "PASS"
            and audit["NVIDIA_KEY_IN_STATE"] == "PASS"
            else "FAIL"
        )
    )
    print(
        "NVIDIA_CAPABILITY_RUNTIME_PROOF="
        + ("PASS" if proof["all_semantic_pass"] else "FAIL")
    )
    print(f"NVIDIA_PROOF_RECEIPT={Path(args.receipt).expanduser()}")
    adapter.close()
    return 0 if proof["all_semantic_pass"] and all(
        audit[key] == "PASS" for key in ("NVIDIA_KEY_IN_GIT", "NVIDIA_KEY_IN_WORKTREE", "NVIDIA_KEY_IN_STATE")
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
