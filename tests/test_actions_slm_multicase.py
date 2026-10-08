"""Three genuinely different measured audio faults, three model calls per case."""
from __future__ import annotations
import json
from pathlib import Path
import pytest

from hazewave.actions_slm_multicase import (
    CASE_IDS, MultiCaseError, choice_schema, evaluate_choice, summarize_trials,
    make_multicase_evidence, perform_multicase
)

ROOT=Path(__file__).resolve().parents[1]


def _choice(finding: str, action: str, key: str):
    return {"finding":finding,"action":action,"evidence_keys":[key],
            "requires_human_review":True}


def _trial(case: str, number: int, passed: bool):
    return {"case_id":case,"trial_id":f"trial-{case}-{number}",
            "verifier_result":"PASS" if passed else "FAIL",
            "task_id":f"haze-multi-{case}-{number}",
            "completion_tokens":25,"prompt_tokens":44,
            "elapsed_ms":100.0,"model_response_sha256":"a"*64}


def test_model_schema_allows_all_three_finding_choices_no_answer_encoded():
    schema=choice_schema()
    assert schema["additionalProperties"] is False
    assert set(schema["properties"]["finding"]["enum"]) == {
        "ATTENUATION_DETECTED","SILENCE_DETECTED","CLIPPING_DETECTED","NO_ISSUE_DETECTED"
    }
    assert set(schema["properties"]["action"]["enum"]) == {
        "REVIEW_GAIN_STAGE","RESTORE_SIGNAL_PATH","REDUCE_GAIN_OR_LIMIT","NO_ACTION"
    }
    assert "expected" not in json.dumps(schema).lower()
    assert set(CASE_IDS) == {"gain_loss_12db","silence_1s","clipping_pcm16"}


def test_independent_semantic_oracle_rejects_wrong_action_and_false_pass():
    gain=_choice("ATTENUATION_DETECTED","REVIEW_GAIN_STAGE","attenuation_db")
    silence=_choice("SILENCE_DETECTED","RESTORE_SIGNAL_PATH","silence_duration_s")
    clip=_choice("CLIPPING_DETECTED","REDUCE_GAIN_OR_LIMIT","clipped_sample_fraction")
    assert evaluate_choice("gain_loss_12db",gain)["grade"]=="PASS"
    assert evaluate_choice("silence_1s",silence)["grade"]=="PASS"
    assert evaluate_choice("clipping_pcm16",clip)["grade"]=="PASS"
    for case,right in (("gain_loss_12db",gain),("silence_1s",silence),("clipping_pcm16",clip)):
        wrong=dict(right,action="NO_ACTION")
        assert evaluate_choice(case,wrong)["grade"]=="FAIL"
        wrong=dict(right,requires_human_review=False)
        assert evaluate_choice(case,wrong)["grade"]=="FAIL"
        wrong=dict(right,production_approved=True)
        assert evaluate_choice(case,wrong)["grade"]=="FAIL"


def test_full_cohort_pass_at_k_and_pass_power_k_are_distinct():
    rows=[]
    expected={"gain_loss_12db":[1,1,1],
              "silence_1s":[0,0,1],
              "clipping_pcm16":[0,0,0]}
    for case, seq in expected.items():
        for i,passed in enumerate(seq):
            rows.append(_trial(case,i,bool(passed)))
    out=summarize_trials(rows, expected_repetitions=3)
    assert out["attempts"]==9
    assert out["case_count"]==3
    assert out["pass_at_1"]==pytest.approx(4/9)
    assert out["pass_at_k"]==pytest.approx(2/3)
    assert out["pass_power_k"]==pytest.approx(1/3)
    assert out["all_cases_reliably_passed"] is False
    assert out["professional"] is False
    assert out["promotion_authorized"] is False


def test_incomplete_replayed_and_invented_cohorts_fail_closed():
    rows=[_trial(c,i,True) for c in CASE_IDS for i in range(3)]
    assert summarize_trials(rows,expected_repetitions=3)["pass_power_k"]==1
    with pytest.raises(MultiCaseError,match="INCOMPLETE_COHORT"):
        summarize_trials(rows[:-1],expected_repetitions=3)
    with pytest.raises(MultiCaseError,match="TRIAL_REPLAY"):
        summarize_trials([*rows[:-1],rows[0]],expected_repetitions=3)
    corrupt=dict(rows[0],verifier_result="PROFESSIONAL")
    with pytest.raises(MultiCaseError,match="INVALID_TRIAL"):
        summarize_trials([corrupt,*rows[1:]],expected_repetitions=3)


def test_actual_ffmpeg_fixture_evidence_has_positive_and_negative_controls(tmp_path:Path):
    cases=make_multicase_evidence(tmp_path)
    assert set(cases)==set(CASE_IDS)
    gain=cases["gain_loss_12db"]
    assert gain["attenuation_db"]==pytest.approx(12,abs=.3)
    assert gain["negative_control_pass"] is True
    silence=cases["silence_1s"]
    assert silence["silence_duration_s"]>=.8
    assert silence["reference_has_silence"] is False
    assert silence["negative_control_pass"] is True
    clipping=cases["clipping_pcm16"]
    assert clipping["clipped_sample_fraction"]>.025
    assert clipping["reference_clipped_sample_fraction"]<.005
    assert clipping["negative_control_pass"] is True
    assert all(len(v["source_sha256"])==64 and len(v["processed_sha256"])==64 for v in cases.values())


def test_model_proposals_from_fake_transport_never_claim_live_execution(tmp_path:Path):
    cases={c:{"negative_control_pass":True,"source_sha256":"a"*64,
              "processed_sha256":"b"*64,
              "attenuation_db":12,"silence_duration_s":1,
              "clipped_sample_fraction":.1} for c in CASE_IDS}
    truths={
      "gain_loss_12db":_choice("ATTENUATION_DETECTED","REVIEW_GAIN_STAGE","attenuation_db"),
      "silence_1s":_choice("SILENCE_DETECTED","RESTORE_SIGNAL_PATH","silence_duration_s"),
      "clipping_pcm16":_choice("CLIPPING_DETECTED","REDUCE_GAIN_OR_LIMIT","clipped_sample_fraction")
    }
    def fake(prompt,model,payload):
        case=next(c for c in CASE_IDS if f"case_id={c}" in prompt)
        assert "tools" not in payload
        return {"model":model,"choices":[{"finish_reason":"stop","message":{
          "role":"assistant","content":json.dumps(truths[case])}}],
          "usage":{"prompt_tokens":33,"completion_tokens":29,"total_tokens":62}}
    report=perform_multicase(cases,model="hazewave-qwen3-0.6b",
                             model_caller=fake,repetitions=3)
    assert report["cohort"]["attempts"]==9
    assert report["cohort"]["pass_at_1"]==1
    assert report["live_model_execution_proven"] is False
    assert report["transport_provenance"]=="INJECTED_TEST_DOUBLE"
    assert report["professional_audio"] is False


def test_new_actions_workflow_never_runs_in_a15_or_alters_colibri():
    wf=(ROOT/".github/workflows/hazewave-slm-actions-multicase-v1.yml").read_text()
    assert "work/haze-actions-multicase-reliability-v1" in wf
    assert "github.event.repository.private == false" in wf
    assert "runs-on: ubuntu-latest" in wf
    assert "timeout-minutes: 15" in wf
    assert "hazewave.actions_slm_multicase --prove" in wf
    assert "--repetitions 3" in wf
    assert "A15_INFERENCE=FORBIDDEN" in wf
    assert "b0638f08417a2d3c8652760462eb5407c6e30173cf9608ad0820757a281eea0e" in wf
    for bad in ("gh codespace start","gh codespace create","ollama pull","git push --force"):
        assert bad not in wf
