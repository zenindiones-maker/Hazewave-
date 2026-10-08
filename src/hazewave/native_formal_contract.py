"""SMT cross-check of bounded *mathematical* specifications and generated C.

The independently authored owner-fixture spec is NOT automatically recovered
from Ghidra, the binary, or the observed oracle. Z3 proves/refutes equality
of two symbolic math expressions on the admitted finite integer range only.
The ELF is separately executed against all these inputs by native synthesis.
"""
from __future__ import annotations

import copy
from typing import Any

class FormalContractError(ValueError):
    pass

def _validate_hypothesis(raw: dict[str,Any]) -> dict[str,Any]:
    if not isinstance(raw,dict) or raw.get("grammar")!="PIECEWISE_LINEAR_QUADRATIC_LINEAR":
        raise FormalContractError("FORMAL_GRAMMAR_NOT_ADMITTED")
    breaks=raw.get("breakpoints")
    parts=raw.get("polynomials")
    if (not isinstance(breaks,list) or len(breaks)!=2
            or any(type(v)!=int for v in breaks)
            or not (-999<=breaks[0]<breaks[1]<=1000)):
        raise FormalContractError("FORMAL_BREAKPOINTS_INVALID")
    if not isinstance(parts,list) or len(parts)!=3:
        raise FormalContractError("FORMAL_POLYNOMIALS_INVALID")
    for i,poly in enumerate(parts):
        if not isinstance(poly,dict) or set(poly)!={"a","b","c"}:
            raise FormalContractError("FORMAL_POLYNOMIALS_INVALID")
        if any(type(v)!=int or abs(v)>100_000 for v in poly.values()):
            raise FormalContractError("FORMAL_COEFFICIENT_NOT_ADMITTED")
        if i!=1 and poly["a"]!=0:
            raise FormalContractError("FORMAL_LINEAR_REGION_INVALID")
    return copy.deepcopy(raw)

def verify_bounded_piecewise_contract(hypothesis:dict[str,Any],*,timeout_ms:int=3000)->dict[str,Any]:
    if type(timeout_ms)!=int or not 100<=timeout_ms<=20000:
        raise FormalContractError("FORMAL_SOLVER_BUDGET_INVALID")
    h=_validate_hypothesis(hypothesis)
    try:
        import z3
    except ImportError as exc:
        raise FormalContractError("FORMAL_SOLVER_NOT_INSTALLED") from exc
    x=z3.Int("owned_fixture_integer_input")
    # Hand-authored independent contract, NOT a decompilation.
    specification=z3.If(x < -7,3*x-11,z3.If(x<=9,x*x+5,7*x-2))
    def poly(p:dict[str,int]):
        return p["a"]*x*x+p["b"]*x+p["c"]
    left,right=h["breakpoints"]
    candidate=z3.If(x<left,poly(h["polynomials"][0]),
                    z3.If(x<right,poly(h["polynomials"][1]),poly(h["polynomials"][2])))
    solver=z3.Solver()
    solver.set(timeout=timeout_ms)
    solver.add(x>=-1000,x<=1000,specification!=candidate)
    outcome=solver.check()
    if outcome==z3.unknown:
        raise FormalContractError("FORMAL_SOLVER_UNKNOWN:"+solver.reason_unknown()[:80])
    proof={
        "schema":"HazewaveBoundedFormalContract/v1",
        "harness_authority":"HAZEWAVE_HARNESS",
        "solver":"Z3",
        "specification_origin":"INDEPENDENT_HAND_AUTHORED_FIXTURE_CONTRACT",
        "range":[-1000,1000],
        "integers_in_domain":2001,
        "mathematical_arithmetic":"UNBOUNDED_Z3_INTS_C_ORACLE_64BIT_CHECKED_SEPARATELY",
        "binary_equivalence_proven":False,
        "beyond_domain_proven":False,
        "general_binary_source_recovery_proven":False,
        "owner_agent_connected":False,
        "production_approved":False,
        "counterexample":None,
    }
    if outcome==z3.unsat:
        proof["result"]="UNSAT_NO_COUNTEREXAMPLE_WITHIN_SPEC"
        return proof
    if outcome!=z3.sat:
        raise FormalContractError("FORMAL_SOLVER_INVALID_RESULT")
    model=solver.model()
    n=model.eval(x,model_completion=True).as_long()
    expected=model.eval(specification,model_completion=True).as_long()
    observed=model.eval(candidate,model_completion=True).as_long()
    if expected==observed or not -1000<=n<=1000:
        raise FormalContractError("FORMAL_MODEL_NOT_VALIDATED")
    proof["result"]="SAT_COUNTEREXAMPLE"
    proof["counterexample"]={"x":n,"spec_value":expected,"candidate_value":observed}
    return proof
