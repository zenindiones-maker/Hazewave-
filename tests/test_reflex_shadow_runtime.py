from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from jsonschema import Draft202012Validator

from hazewave.colibri import ColibriDecisionResult, ColibriHardwareSnapshot, load_colibri_policy
from hazewave.reflex import govern_reflex_result
from hazewave.reflex_robustness import OrderEnsembleMetrics, RobustReflexVerdict
import hazewave.reflex_shadow_runtime as runtime


def _hardware() -> ColibriHardwareSnapshot:
    return ColibriHardwareSnapshot(
        ram_total_bytes=8_000_000_000,
        ram_available_bytes=5_000_000_000,
        disk_free_bytes=20_000_000_000,
        model_root="/tmp/test-reflex-model",
    )


def _event(**updates) -> dict:
    event = {
        "schema": "HazewaveReflexShadowEvent/v1",
        "task_id": "task-123",
        "requested_domain": "HAZE",
        "data_classification": "INTERNAL_NON_SECRET",
        "state_language": "en",
        "precheck_status": "UNRESOLVED_PERMITTED_AMBIGUITY",
        "decision_key": "domain.route.v1",
        "state": {
            "media_kind": "mixed",
            "requested_operation": "ambiguous cross-media preparation",
        },
    }
    event.update(updates)
    return event


def _verdict():
    result = ColibriDecisionResult(
        model_id="laya",
        answers={
            "route": {
                "type": "choice",
                "choice": "HAZE",
                "probabilities": {"HAZE": 0.90, "WAVE": 0.07, "BRIDGE": 0.03},
                "confidence": 0.85,
            }
        },
        request_sha256="a" * 64,
        response_sha256="b" * 64,
        latency_ms=220.0,
        usage={"cost": 0},
    )
    return govern_reflex_result(
        authorization=runtime._authorization("task-123", "HAZE"),
        result=result,
        question_id="route",
    )





def _robust_verdict():
    base = _verdict()
    ensemble = OrderEnsembleMetrics(
        rotations=3,
        labels=("BRIDGE", "HAZE", "WAVE"),
        per_rotation_winner=("HAZE", "HAZE", "HAZE"),
        winner_agreement=1.0,
        normalized_jsd=0.01,
        aggregate_probabilities=(("BRIDGE", 0.03), ("HAZE", 0.90), ("WAVE", 0.07)),
        aggregate_winner="HAZE",
        aggregate_peak_probability=0.90,
    )
    return RobustReflexVerdict(
        base_verdict=base,
        ensemble=ensemble,
        robust_eligible=True,
        robustness_reasons=(),
        disposition="SHADOW_RECOMMENDATION",
        escalation_target="ESCALATE_9ROUTER_REASON_DEEP",
    )



def test_route_question_encodes_bridge_boundary_without_putting_option_labels_in_instructions() -> None:
    question = runtime._proof_question()
    instructions = question["instructions"]
    criteria = question["criteria"]

    assert "primary responsibility" in instructions.lower()
    assert "final output" in instructions.lower()
    assert all(label not in instructions for label in ("HAZE", "WAVE", "BRIDGE"))

    bridge = criteria["BRIDGE"].lower()
    wave = criteria["WAVE"].lower()
    haze = criteria["HAZE"].lower()

    for term in ("translat", "synchron", "metadata", "authority"):
        assert term in bridge
    assert "primary responsibility" in haze
    assert "primary responsibility" in wave
    assert "cross-domain" in bridge
    rendered = " ".join([instructions, *criteria.values()]).lower()
    assert " does not " not in f" {rendered} "
    assert " not by " not in f" {rendered} "
    assert len(json.dumps(question, ensure_ascii=False, separators=(",", ":"))) <= 650

def test_event_schema_matches_representative_event() -> None:
    root = Path(__file__).resolve().parents[1]
    schema = json.loads((root / "schemas/reflex-shadow-event-v1.schema.json").read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(_event())


@pytest.mark.parametrize(
    "event,reason",
    [
        (_event(data_classification="CREDENTIAL"), "DATA_CLASS_FORBIDDEN"),
        (_event(data_classification="PRIVATE_MEDIA"), "DATA_CLASS_FORBIDDEN"),
        (_event(state_language="pt-br"), "LANGUAGE_NOT_QUALIFIED"),
        (_event(precheck_status="PASSED"), "DETERMINISTIC_PRECHECK_REQUIRED"),
        (_event(requested_domain="UNKNOWN"), "DOMAIN_INVALID"),
    ],
)
def test_event_admission_fails_closed(event: dict, reason: str) -> None:
    with pytest.raises(runtime.ShadowRuntimeError, match=reason):
        runtime._validate_event(event)


def test_doctor_checks_existing_codespace_and_exact_remote_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "worktree"
    source = tmp_path / "source"
    model = tmp_path / "model"
    for path in (repo, source, model / "encoder", model / "tokenizer", source / "c"):
        path.mkdir(parents=True, exist_ok=True)
    for directory in (repo, source):
        (directory / ".git").mkdir()
    (source / "c/laya").write_bytes(b"binary")
    (model / "model.safetensors").write_bytes(b"test-checkpoint")
    for p in (model / "rl_agent_config.json", model / "encoder/config.json",
              model / "tokenizer/tokenizer.json"):
        p.write_text("{}")
    original_policy = load_colibri_policy()
    policy = json.loads(json.dumps(original_policy))
    policy["models"][0]["primary_weight_sha256"] = sha256(b"test-checkpoint").hexdigest()
    monkeypatch.setattr(runtime, "load_colibri_policy", lambda: policy)
    head = "e" * 40

    def get_head(path: Path):
        return head if path == repo else policy["upstream"]["source_commit"]

    monkeypatch.setattr(runtime, "_git_head", get_head)

    def fake_git(argv, **kwargs):
        if "rev-parse" in argv:
            return SimpleNamespace(stdout=head + "\n", returncode=0)
        if "--is-ancestor" in argv:
            return SimpleNamespace(stdout="", returncode=0)
        if "--porcelain" in argv:
            return SimpleNamespace(stdout="", returncode=0)
        raise AssertionError(f"unexpected_git_command:{argv}")

    monkeypatch.setattr(runtime.subprocess, "run", fake_git)

    good = runtime.verify_runtime_material(
        repository_root=repo, source_root=source, model_root=model,
        codespace=runtime.EXPECTED_CODESPACE, hardware=_hardware(),
    )
    assert good["status"] == "READY_FOR_LIVE_PROBE"
    assert good["worktree_head_match"] is True
    assert good["real_inference_proven"] is False
    assert good["codespaces_quota_verified"] is False

    wrong_codespace = runtime.verify_runtime_material(
        repository_root=repo, source_root=source, model_root=model,
        codespace="another-codespace", hardware=_hardware(),
    )
    assert wrong_codespace["status"] == "BLOCKED"


def test_shadow_observe_is_private_and_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_executor(**kwargs):
        calls.append(kwargs)
        return _robust_verdict()

    monkeypatch.setattr(runtime, "execute_robust_reflex_route", fake_executor)
    event = _event()
    first = runtime._observe(
        event=event, secret="s" * 32, hardware=_hardware(),
        audit={"status": "READY_FOR_LIVE_PROBE"}, state_root=tmp_path,
    )
    second = runtime._observe(
        event=event, secret="s" * 32, hardware=_hardware(),
        audit={"status": "READY_FOR_LIVE_PROBE"}, state_root=tmp_path,
    )
    assert first["status"] == "OBSERVED_ROBUST_SHADOW_ONLY"
    assert first["rotation_count"] == 3
    assert first["winner_agreement"] == 1.0
    assert first["robust_eligible"] is True
    assert first["replayed"] is False and second["replayed"] is True
    assert len(calls) == 1
    assert first["ground_truth_available"] is False
    assert first["grants_execution_authority"] is False
    stored = Path(first["receipt_path"]).read_text()
    assert "ambiguous cross-media preparation" not in stored
    assert '"raw_state":' not in stored
    assert not (tmp_path / "outcomes-v1.jsonl").exists()


def test_real_label_is_separate_from_model_prediction_and_bound_to_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime, "execute_robust_reflex_route", lambda **kwargs: _robust_verdict())
    event = _event(ground_truth={
        "actual_label": "WAVE",
        "label_source": "RUNTIME_QC",
        "label_evidence_digest": "d" * 64,
    })
    result = runtime._observe(
        event=event, secret="s" * 32, hardware=_hardware(),
        audit={"status": "READY_FOR_LIVE_PROBE"}, state_root=tmp_path,
    )
    assert result["ground_truth_available"] is True
    report = runtime._report(tmp_path)
    assert report["status"] == "EVIDENCE_ONLY"
    assert report["total_labeled_outcomes"] == 1
    metrics = report["cohorts"][0]["metrics"]
    assert metrics["accuracy"] == 0
    assert metrics["actual_accept_count"] == 0
    assert metrics["shadow_coverage"] == 1
    assert metrics["selective_risk_if_activated"] == 1


def test_secret_permissions_and_symlink_are_rejected(tmp_path: Path) -> None:
    key = tmp_path / "key"
    key.write_text("v" * 40)
    key.chmod(0o644)
    with pytest.raises(runtime.ShadowRuntimeError, match="PERMISSIONS_UNSAFE"):
        runtime._read_secret(key)
    key.chmod(0o600)
    assert runtime._read_secret(key) == "v" * 40
    link = tmp_path / "alias"
    link.symlink_to(key)
    with pytest.raises(runtime.ShadowRuntimeError, match="MISSING_OR_SYMLINK"):
        runtime._read_secret(link)


def test_existing_receipt_is_not_silently_overwritten(tmp_path: Path) -> None:
    receipt = tmp_path / "fixed.json"
    runtime._atomic_receipt(receipt, {"status": "FIRST"})
    with pytest.raises(runtime.ShadowRuntimeError, match="ALREADY_EXISTS"):
        runtime._atomic_receipt(receipt, {"status": "SECOND"})
    assert json.loads(receipt.read_text())["status"] == "FIRST"


def test_report_with_no_label_evidence_does_not_claim_success(tmp_path: Path) -> None:
    report = runtime._report(tmp_path)
    assert report["status"] == "NO_LABELED_OUTCOMES"
    assert report["total_labeled_outcomes"] == 0
    assert report["production_calibrated"] is False
