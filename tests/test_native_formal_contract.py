"""Independently check the synthesized hypothesis against a bounded owned SPEC.

A real ELF oracle and REA/Ghidra observations are separate proofs. Z3 does not
read/understand the binary: it checks a human-authored mathematical reference
vs the automatically inferred piecewise polynomial candidate.
"""
from __future__ import annotations

import pytest

from hazewave.native_behavior_synthesis import infer_linear_quadratic_linear
from hazewave.native_formal_contract import (
    FormalContractError,
    verify_bounded_piecewise_contract,
)

def reference() -> dict[int,int]:
    return {x: (3*x-11 if x < -7 else (x*x+5 if x <= 9 else 7*x-2))
            for x in range(-1000,1001)}

def derived():
    return infer_linear_quadratic_linear(reference())


def test_formal_proof_is_unsat_for_correct_generated_hypothesis():
    actual=verify_bounded_piecewise_contract(derived())
    assert actual["solver"]=="Z3"
    assert actual["result"]=="UNSAT_NO_COUNTEREXAMPLE_WITHIN_SPEC"
    assert actual["integers_in_domain"]==2001
    assert actual["specification_origin"]=="INDEPENDENT_HAND_AUTHORED_FIXTURE_CONTRACT"
    assert actual["binary_equivalence_proven"] is False
    assert actual["beyond_domain_proven"] is False
    assert actual["owner_agent_connected"] is False

@pytest.mark.parametrize("edit",[
    lambda h: h["polynomials"][0].update(b=4),
    lambda h: h["polynomials"][1].update(c=6),
    lambda h: h["polynomials"][2].update(b=8),
    lambda h: h["breakpoints"].__setitem__(0,-6),
])
def test_formal_proof_discovers_and_validates_counterexamples(edit):
    hypo=derived()
    edit(hypo)
    result=verify_bounded_piecewise_contract(hypo)
    assert result["result"]=="SAT_COUNTEREXAMPLE"
    assert isinstance(result["counterexample"]["x"],int)
    assert -1000 <= result["counterexample"]["x"] <= 1000
    assert result["counterexample"]["spec_value"] != result["counterexample"]["candidate_value"]
    assert result["production_approved"] is False

def test_cannot_swap_solver_contract_or_use_untrusted_arbitrary_polynomial():
    bad=derived()
    bad["polynomials"][2]["a"]=10**19
    with pytest.raises(FormalContractError,match="FORMAL_COEFFICIENT_NOT_ADMITTED"):
        verify_bounded_piecewise_contract(bad)
    bad=derived()
    bad["breakpoints"]=[-7,-7]
    with pytest.raises(FormalContractError):
        verify_bounded_piecewise_contract(bad)

def test_proof_is_solver_dependent_not_a_handwritten_comparison():
    import inspect
    import hazewave.native_formal_contract as m
    body=inspect.getsource(m)
    assert "z3.Solver" in body
    assert "z3.If" in body
    assert "unsat" in body
    assert "timeout" in body
