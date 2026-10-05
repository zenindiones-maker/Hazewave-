from __future__ import annotations

import json
from pathlib import Path

from hazewave.nvidia_proof import (
    evaluate_probe_item,
    load_probe_corpus,
    scan_paths_for_secret,
    probe_request_options,
    run_nvidia_capability_probes,
)
from hazewave.provider_runtime import HazewaveProviderExecutionResult


def _result(content: str) -> HazewaveProviderExecutionResult:
    return HazewaveProviderExecutionResult(
        provider="nvidia",
        model_id="nvidia/nemotron-3.5-lightning-30b-a3b",
        execution_profile="FAST_STRUCTURED",
        capability_id="reason.general",
        status="PASS",
        content=content,
        finish_reason="stop",
        prompt_tokens=10,
        completion_tokens=5,
        reasoning_tokens=None,
        total_tokens=15,
        latency_ms=100,
        tool_calls=(),
        error_class=None,
        http_status=200,
        retry_after_seconds=None,
        cost_class="FREE_DEVELOPMENT_ENDPOINT",
        semantic_pass=True,
    )


def test_capability_corpus_has_four_semantic_non_echo_probes() -> None:
    root = Path(__file__).resolve().parents[1]
    corpus = load_probe_corpus(root / "config" / "nvidia-capability-eval-v1.json")
    items = corpus["items"]
    assert {item["capability"] for item in items} == {
        "reason.general", "reason.deep", "code.generate", "code.review"
    }
    assert {item["execution_profile"] for item in items} >= {
        "FAST_STRUCTURED", "DEEP_REASONING"
    }
    assert all(item["evaluation"]["kind"] != "EXACT_LITERAL_ONLY" for item in items)


def test_json_semantic_evaluator_requires_expected_structure() -> None:
    item = {
        "evaluation": {
            "kind": "JSON_SUBSET",
            "expected": {
                "429": "RATE_LIMITED",
                "retry_storm": False,
            },
        }
    }
    good = evaluate_probe_item(
        item,
        _result('{"429":"RATE_LIMITED","retry_storm":false,"extra":"ok"}'),
    )
    bad = evaluate_probe_item(
        item,
        _result('{"429":"PASS","retry_storm":true}'),
    )
    assert good.semantic_pass is True
    assert good.quality_score == 1.0
    assert bad.semantic_pass is False


def test_code_ast_evaluator_checks_structure_without_executing_model_code() -> None:
    item = {
        "evaluation": {
            "kind": "PYTHON_AST",
            "function_name": "clamp_retry_after",
            "required_names": ["min", "max", "int"],
            "required_constants": [0, 3600],
        }
    }
    good = evaluate_probe_item(
        item,
        _result(
            "def clamp_retry_after(seconds):\n"
            "    return min(3600, max(0, int(seconds)))\n"
        ),
    )
    bad = evaluate_probe_item(
        item,
        _result("def clamp_retry_after(seconds):\n    return seconds\n"),
    )
    assert good.semantic_pass is True
    assert good.quality_score == 1.0
    assert bad.semantic_pass is False


def test_secret_scanner_detects_exact_secret_without_returning_secret(tmp_path: Path) -> None:
    secret = "nvapi-runtime-secret-sentinel"
    clean = tmp_path / "clean.txt"
    leak = tmp_path / "leak.json"
    clean.write_text("safe", encoding="utf-8")
    leak.write_text(f'{{"Authorization":"Bearer {secret}"}}', encoding="utf-8")

    result = scan_paths_for_secret(
        secret=secret,
        paths=[clean, leak],
        root=tmp_path,
    )
    serialized = json.dumps(result)
    assert result["leak_count"] == 1
    assert result["paths"] == ["leak.json"]
    assert secret not in serialized


def test_json_probe_requests_provider_json_mode() -> None:
    item = {
        "capability": "reason.deep",
        "execution_profile": "DEEP_REASONING",
        "evaluation": {"kind": "JSON_SUBSET", "expected": {"ok": True}},
    }
    options = probe_request_options(item)
    assert options["response_format"] == {"type": "json_object"}
    assert options["max_tokens"] == 4096


def test_code_review_probe_requests_2048_tokens_without_json_mode() -> None:
    item = {
        "capability": "code.review",
        "execution_profile": "FAST_STRUCTURED",
        "evaluation": {"kind": "KEYWORD_GROUPS", "groups": [["bug"]]},
    }
    options = probe_request_options(item)
    assert options["max_tokens"] == 2048
    assert "response_format" not in options


def test_failed_probe_diagnostics_are_sanitized_and_never_persist_raw_content(
    tmp_path: Path,
) -> None:
    class StubAdapter:
        def execute(self, **kwargs):
            return _result(
                'not json; diagnostic token nvapi-runtime-secret-sentinel'
            )

    corpus = {
        "items": [
            {
                "id": "diag-1",
                "capability": "reason.general",
                "domain": "HAZE",
                "execution_profile": "FAST_STRUCTURED",
                "task_family": "diag",
                "prompt": "return json",
                "evaluation": {
                    "kind": "JSON_SUBSET",
                    "expected": {"ok": True},
                },
            }
        ]
    }
    diagnostics = []
    receipt_path = tmp_path / "proof.json"
    learning_path = tmp_path / "learning.json"

    proof = run_nvidia_capability_probes(
        adapter=StubAdapter(),
        corpus=corpus,
        learning_path=learning_path,
        receipt_path=receipt_path,
        now="2026-10-05T16:00:00+00:00",
        diagnostic_sink=diagnostics.append,
    )

    assert proof["all_semantic_pass"] is False
    assert len(diagnostics) == 1
    assert diagnostics[0]["evaluation_reason"] == "JSON_INVALID"
    assert "nvapi-" not in diagnostics[0]["content"]
    assert "[REDACTED]" in diagnostics[0]["content"]

    persisted = receipt_path.read_text(encoding="utf-8")
    assert "not json" not in persisted
    assert "nvapi-runtime-secret-sentinel" not in persisted
