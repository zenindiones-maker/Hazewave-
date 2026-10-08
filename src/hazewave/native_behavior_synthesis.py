"""Bounded black-box behavioral program synthesis on ONE owned executable.

Template identification uses only observed executable input/output; no source
or Ghidra pseudocode is read by the inference function. The compiler emits a
candidate and exhaustively checks the *explicit finite domain* [-1000,1000].
Never equate this with arbitrary binary decompilation or universal equivalence.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any

from hazewave.harness import HazewaveTask, issue_authorization, route_task, validate_authorization

_ROOT = Path(__file__).resolve().parents[2]
_OWNED_SOURCE = _ROOT / "tests/fixtures/native-owned-reconstruction/original.c"
_DOMAIN = (-1000, 1000)


class SynthesisError(RuntimeError):
    pass


def _expect(condition: bool, reason: str) -> None:
    if not condition:
        raise SynthesisError(reason)


def _poly(a: int, b: int, c: int, x: int) -> int:
    return a*x*x+b*x+c


def infer_linear_quadratic_linear(outputs: dict[int, int]) -> dict[str, Any]:
    """Fit a deliberately LIMITED three-region grammar, no source-code access.

    The first region is affine, the second quadratic and the third affine.
    Breakpoints are inferred from oracle values. Unknown shapes fail closed.
    """
    low, high = _DOMAIN
    if (type(outputs) is not dict or len(outputs) != high-low+1
            or set(outputs) != set(range(low,high+1))
            or any(type(v) is not int or abs(v) > 10_000_000 for v in outputs.values())):
        raise SynthesisError("ORACLE_INPUT_DOMAIN_INVALID")
    xs = range(low,high+1)
    l_b = outputs[low+1] - outputs[low]
    l_c = outputs[low] - l_b*low
    middle = None
    for x in range(low+2,high+1):
        if outputs[x] != l_b*x+l_c:
            middle = x
            break
    _expect(middle is not None and middle-low >= 5 and middle+8 < high,
            "GRAMMAR_CANNOT_EXPLAIN_ORACLE")
    # Quadratic from 3 exact consecutive observations.
    x0 = middle
    y0,y1,y2 = (outputs[x0+i] for i in range(3))
    second = y2-2*y1+y0
    _expect(second % 2 == 0, "GRAMMAR_CANNOT_EXPLAIN_ORACLE")
    m_a = second//2
    m_b = (y1-y0)-m_a*(2*x0+1)
    m_c = y0-m_a*x0*x0-m_b*x0
    _expect(m_a != 0,"GRAMMAR_CANNOT_EXPLAIN_ORACLE")
    right = None
    for x in range(middle+3,high+1):
        if outputs[x] != _poly(m_a,m_b,m_c,x):
            right=x
            break
    _expect(right is not None and right-middle >= 6 and high-right>=5,
            "GRAMMAR_CANNOT_EXPLAIN_ORACLE")
    r_b=outputs[right+1]-outputs[right]
    r_c=outputs[right]-r_b*right
    _expect(all(outputs[x] == _poly(0,l_b,l_c,x) for x in range(low,middle))
        and all(outputs[x] == _poly(m_a,m_b,m_c,x) for x in range(middle,right))
        and all(outputs[x] == _poly(0,r_b,r_c,x) for x in range(right,high+1)),
        "GRAMMAR_CANNOT_EXPLAIN_ORACLE")
    return {
        "grammar": "PIECEWISE_LINEAR_QUADRATIC_LINEAR",
        "breakpoints": [middle,right],
        "polynomials":[
            {"a":0,"b":l_b,"c":l_c},
            {"a":m_a,"b":m_b,"c":m_c},
            {"a":0,"b":r_b,"c":r_c},
        ],
    }


def _generate_c(hypothesis: dict[str,Any]) -> str:
    first,second=hypothesis["breakpoints"]
    pieces=hypothesis["polynomials"]
    def fmt(p: dict[str,int]) -> str:
        a,b,c = (p[k] for k in ("a","b","c"))
        return f"(({a}LL)*(x)*(x) + ({b}LL)*(x) + ({c}LL))"
    return (
        "/* AUTO-SYNTHESIZED FROM SOURCE-OWNED ELF INPUT/OUTPUT ONLY. */\n"
        "#include <errno.h>\n#include <stdio.h>\n#include <stdlib.h>\n"
        "static long reconstructed(long x) {\n"
        f"  if (x < ({first}L)) return (long){fmt(pieces[0])};\n"
        f"  if (x < ({second}L)) return (long){fmt(pieces[1])};\n"
        f"  return (long){fmt(pieces[2])};\n"
        "}\n"
        "int main(int argc,char **argv) {\n"
        "  if(argc!=2) return 64;\n"
        "  errno=0; char *end=0; long x=strtol(argv[1],&end,10);\n"
        "  if(errno||!end||*end||x < -1000||x > 1000) return 65;\n"
        "  printf(\"%ld\\n\", reconstructed(x)); return 0;\n}\n"
    )


def _execute(args: list[str], timeout: float = 30.) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, capture_output=True, text=True, check=False, timeout=timeout,
                              env={"PATH":os.getenv("PATH","/usr/bin"),"LANG":"C","HOME":str(Path.home())})
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SynthesisError("COMPILER_OR_ORACLE_UNAVAILABLE") from exc


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_oracle(binary: Path, n: int) -> int:
    proc = _execute([str(binary),str(n)],timeout=3)
    if proc.returncode != 0 or proc.stderr.strip():
        raise SynthesisError("ORACLE_PROCESS_FAILED")
    out=proc.stdout.strip()
    if not re.fullmatch(r"-?[0-9]{1,9}",out):
        raise SynthesisError("ORACLE_INVALID_OUTPUT")
    return int(out)


def _compile(cc: str, source: Path, target: Path) -> None:
    result=_execute([cc,"-std=c11","-O0","-g","-fno-inline","-Wall","-Wextra","-Werror",
                     "-o",str(target),str(source)],timeout=45)
    if result.returncode != 0 or not target.is_file():
        raise SynthesisError("COMPILER_NONZERO")


def _secure_write(path: Path, payload: bytes) -> None:
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as writer:
        writer.write(payload)
        writer.flush()
        os.fsync(writer.fileno())


def synthesize_owned_native_fixture(*,state_root:Path,compiler:str="cc") -> dict[str,Any]:
    """Compiles one approved local source fixture then synthesizes from binary I/O.

    The synthesis never reads, imports or copies the original source file. The
    outer fixture driver compiles it because the original binary is ours.
    """
    if Path(compiler).name not in {"cc","gcc","clang"} or shutil.which(compiler) is None:
        raise SynthesisError("COMPILER_NOT_ADMITTED")
    root=Path(state_root).expanduser()
    if (root.resolve(strict=False).is_relative_to(_ROOT.resolve()) or root.is_symlink()
            or root.exists() or root.parent.is_symlink()):
        raise SynthesisError("PRIVATE_OUTPUT_ROOT_NOT_ADMITTED")
    task=HazewaveTask(task_id="owned-auto-synthesis-v1",
        goal="Source-owned native I/O reconstruction within explicit finite domain",
        required_capability="research.visual.inspect",requested_domain="WAVE")
    auth=validate_authorization(issue_authorization(route_task(task)),
        expected_task_id=task.task_id,expected_capability=task.required_capability)
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix="hazewave-native-io-synthesis-") as work:
        workdir=Path(work)
        oracle=workdir/"original.elf"
        _compile(compiler,_OWNED_SOURCE,oracle)
        oracle_sha=_digest(oracle.read_bytes())
        # The entire inference sees only oracle OUTPUTS. Never original .c.
        samples={x:_run_oracle(oracle,x) for x in range(_DOMAIN[0],_DOMAIN[1]+1)}
        hypo=infer_linear_quadratic_linear(samples)
        generated=_generate_c(hypo)
        candidate_source=workdir/"candidate.c"
        candidate_source.write_text(generated)
        built=workdir/"candidate.elf"
        _compile(compiler,candidate_source,built)
        built_sha=_digest(built.read_bytes())
        first_mismatch=None
        observed_hash=hashlib.sha256()
        for x,reference in samples.items():
            actual=_run_oracle(built,x)
            observed_hash.update(f"{x},{reference},{actual};".encode())
            if actual != reference and first_mismatch is None:
                first_mismatch={"x":x,"oracle":reference,"candidate":actual}
        if first_mismatch is not None:
            raise SynthesisError("AUTOGENERATED_CANDIDATE_BEHAVIOR_MISMATCH")
    root.mkdir(parents=True,mode=0o700)
    root.chmod(0o700)
    _secure_write(root/"reconstructed.c",generated.encode())
    report={
        "schema":"HazewaveOwnedAutomaticNativeSynthesis/v1",
        "harness_authority":auth.authority,
        "harness_authorization_id":auth.authorization_id,
        "grammatical_hypothesis":hypo,
        "oracle_elf_sha256":oracle_sha,
        "generated_elf_sha256":built_sha,
        "generated_C_sha256":_digest(generated.encode()),
        "observed_input_output_sha256":observed_hash.hexdigest(),
        "behavioral_status":"EXHAUSTIVE_WITHIN_EXPLICIT_FINITE_DOMAIN",
        "domain":list(_DOMAIN),
        "inputs_checked":len(samples),
        "oracle_binary_executed":True,
        "original_C_used_for_synthesis":False,
        "automatic_candidate_generation":True,
        "reconstructed_program_compiled_and_executed":True,
        "outside_domain_equivalence_proven":False,
        "general_binary_decompilation_proven":False,
        "ghidra_guided_synthesis_proven":False,
        "owner_agent_mcp_connected":False,
        "codespace_runtime_proven":False,
        "production_approved":False,
        "elapsed_ms":round((time.monotonic()-started)*1000,2),
    }
    _secure_write(root/("synthesis-receipt-"+datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")+".json"),
                  (json.dumps(report,sort_keys=True)+"\n").encode())
    report["receipt_sha256"]=_digest(next(root.glob("synthesis-receipt-*.json")).read_bytes())
    return report


def main(argv:list[str]|None=None)->int:
    p=argparse.ArgumentParser(description="First-party executable I/O to bounded C synthesis")
    p.add_argument("--state-root",type=Path,required=True)
    p.add_argument("--compiler",default="cc")
    args=p.parse_args(argv)
    try:
        result=synthesize_owned_native_fixture(state_root=args.state_root,compiler=args.compiler)
    except (SynthesisError,OSError) as exc:
        print("HAZEWAVE_NATIVE_SYNTHESIS=BLOCKED:"+str(exc),file=sys.stderr)
        return 20
    print("HAZEWAVE_NATIVE_SYNTHESIS=PASS_FINITE_DOMAIN")
    print(json.dumps(result,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
