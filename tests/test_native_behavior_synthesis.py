"""Regression tests for bounded automatic behavioral synthesis FROM binary I/O only.

RED first: require a generated C implementation without reading the original C
source in the synthesizer, exhaustive finite-domain verification and fail-closed
on a target outside the admitted grammar.
"""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import shutil
import pytest

from hazewave.native_behavior_synthesis import (
    SynthesisError, infer_linear_quadratic_linear,
    synthesize_owned_native_fixture,
)

ROOT = Path(__file__).resolve().parents[1]
OWNED = ROOT / "tests" / "fixtures" / "native-owned-reconstruction"

def _cc():
    if shutil.which("cc") is None:
        pytest.skip("no available C compiler")
    return "cc"


def test_inference_from_three_segments_without_original_source():
    # Split points are discovered from oracle outputs, not given to the synth.
    outputs={}
    for x in range(-1000,1001):
        outputs[x] = 3*x-11 if x < -7 else (x*x+5 if x <= 9 else 7*x-2)
    hypothesis=infer_linear_quadratic_linear(outputs)
    assert hypothesis["breakpoints"]==[-7,10]
    assert hypothesis["polynomials"]==[
        {"a":0,"b":3,"c":-11},
        {"a":1,"b":0,"c":5},
        {"a":0,"b":7,"c":-2},
    ]
    assert hypothesis["grammar"]=="PIECEWISE_LINEAR_QUADRATIC_LINEAR"


def test_real_binary_to_auto_generated_C_and_full_domain_behavior(tmp_path):
    report=synthesize_owned_native_fixture(
        state_root=tmp_path/"research", compiler=_cc()
    )
    assert report["oracle_binary_executed"] is True
    assert report["automatic_candidate_generation"] is True
    assert report["original_C_used_for_synthesis"] is False
    assert report["reconstructed_program_compiled_and_executed"] is True
    assert report["domain"]==[-1000,1000]
    assert report["inputs_checked"]==2001
    assert report["behavioral_status"]=="EXHAUSTIVE_WITHIN_EXPLICIT_FINITE_DOMAIN"
    assert report["outside_domain_equivalence_proven"] is False
    assert report["general_binary_decompilation_proven"] is False
    assert report["ghidra_guided_synthesis_proven"] is False
    assert report["owner_agent_mcp_connected"] is False
    assert report["production_approved"] is False
    candidate=tmp_path/"research"/"reconstructed.c"
    assert candidate.is_file()
    assert "static long reconstructed" in candidate.read_text()
    assert "3L * x" not in candidate.read_text() # generated C form is derived
    assert candidate.stat().st_mode & 0o077 == 0
    receipts=list((tmp_path/"research").glob("synthesis-receipt-*.json"))
    assert len(receipts)==1
    assert receipts[0].stat().st_mode & 0o077 == 0
    assert json.loads(receipts[0].read_text())["behavioral_status"]==report["behavioral_status"]


def test_wrong_oracle_behavior_outside_grammar_is_rejected():
    # A quadratic/linear/linear template cannot explain a center with
    # persistent non-polynomial period-7 oscillation.
    samples={}
    for x in range(-1000,1001):
        samples[x]=3*x-11 if x < -7 else (x*x+5+(x%7) if x <= 9 else 7*x-2)
    with pytest.raises(SynthesisError, match="GRAMMAR_CANNOT_EXPLAIN_ORACLE"):
        infer_linear_quadratic_linear(samples)


def test_tampered_oracle_table_is_rejected_and_no_false_PASS():
    samples={x:(3*x-11 if x < -7 else (x*x+5 if x<=9 else 7*x-2))
             for x in range(-1000,1001)}
    samples[0]+=1
    with pytest.raises(SynthesisError, match="GRAMMAR_CANNOT_EXPLAIN_ORACLE"):
        infer_linear_quadratic_linear(samples)


def test_unbounded_and_missing_oracle_inputs_are_denied():
    with pytest.raises(SynthesisError):
        infer_linear_quadratic_linear({0:1})
    with pytest.raises(SynthesisError):
        infer_linear_quadratic_linear({x:x for x in range(-1000,1002)})


def test_no_second_codespace_or_production_promotion_in_synthesis():
    import inspect
    import hazewave.native_behavior_synthesis as m
    s=inspect.getsource(m)
    assert "gh codespace create" not in s
    assert "git push" not in s
    assert "shell=True" not in s
    assert "ghidra_guided_synthesis_proven" in s
    assert "owner_agent_mcp_connected" in s
