"""All first- and third-party GitHub Action executions are immutable SHA pinned."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
USE=re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)", re.MULTILINE)
SHA=re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")

def test_all_workflows_use_verified_immutable_action_commit_ids():
    flows=sorted((ROOT/".github/workflows").glob("*.yml"))
    expected={
        "acestep-runtime-smoke.yml",
        "ci.yml",
        "fetch-htdemucs.yml",
        "wave-effectcraft-filmcraft-portal-proof.yml",
        "wave-site-ci.yml",
        "wave-vectorcraft-real-cli-proof.yml",
        "wave-artcraft-four-real-bridge.yml",
        "wave-artcraft-seven-integrated-proof.yml",
    }
    assert {flow.name for flow in flows}==expected
    seen=[]
    for path in flows:
        source=path.read_text(encoding="utf8")
        actions=USE.findall(source)
        assert actions, str(path)
        for action in actions:
            local_reusable = {
                "./.github/workflows/wave-artcraft-four-real-bridge.yml",
                "./.github/workflows/wave-vectorcraft-real-cli-proof.yml",
                "./.github/workflows/wave-effectcraft-filmcraft-portal-proof.yml",
            }
            is_same_commit_local = (
                path.name == "wave-artcraft-seven-integrated-proof.yml"
                and action in local_reusable
            )
            assert SHA.fullmatch(action) or is_same_commit_local, f"{path}: {action}"
        seen.extend(actions)
    assert len(seen)>=15
    for action in ["actions/checkout","actions/setup-node","actions/setup-python",
                   "actions/upload-artifact","astral-sh/setup-uv"]:
        assert any(entry.startswith(action+"@") for entry in seen), action
