"""All first- and third-party GitHub Action executions are immutable SHA pinned."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
USE=re.compile(r"^\s*-\s*uses:\s*(\S+)", re.MULTILINE)
SHA=re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")

def test_all_workflows_use_verified_immutable_action_commit_ids():
    flows=sorted((ROOT/".github/workflows").glob("*.yml"))
    assert len(flows)==6
    seen=[]
    for path in flows:
        source=path.read_text(encoding="utf8")
        actions=USE.findall(source)
        assert actions, str(path)
        for action in actions:
            assert SHA.fullmatch(action), f"{path}: {action}"
        seen.extend(actions)
    assert len(seen)>=15
    for action in ["actions/checkout","actions/setup-node","actions/setup-python",
                   "actions/upload-artifact","astral-sh/setup-uv"]:
        assert any(entry.startswith(action+"@") for entry in seen), action
