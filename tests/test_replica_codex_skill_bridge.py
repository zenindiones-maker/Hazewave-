"""Repo-scoped Codex compatibility and Harness authority checks."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CODEX = ROOT / ".agents" / "skills"
ORIGINAL = ROOT / ".claude" / "skills"
NAMES = (
    "recon", "architect", "design", "build", "backend", "test",
    "diff", "entrepreneur", "brand", "launch", "deploy",
)
SENSITIVE = {"backend", "launch", "deploy"}


@pytest.mark.parametrize("name", NAMES)
def test_codex_discovery_and_claude_origin(name):
    folder = CODEX / f"replica-{name}"
    skill = folder / "SKILL.md"
    assert skill.is_file()
    text = skill.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert f"name: replica-{name}\n" in text
    assert "\ndescription:" in text
    assert "HAZEWAVE_HARNESS" in text
    assert f".claude/skills/replica-{name}/SKILL.md" in text
    assert (ORIGINAL / f"replica-{name}" / "SKILL.md").is_file()
    assert "/replica-" not in text
    assert "$replica-" in text


@pytest.mark.parametrize("name", sorted(SENSITIVE))
def test_sensitive_skills_must_be_explicit(name):
    yaml = (CODEX / f"replica-{name}" / "agents" / "openai.yaml").read_text()
    assert "allow_implicit_invocation: false" in yaml


def test_codex_bridge_never_grants_deploy_power():
    for name in NAMES:
        p = CODEX / f"replica-{name}" / "SKILL.md"
        text = p.read_text()
        assert "No deployment, publication, payments" in text
        assert "Never modify another repository" in text
    assert not (CODEX / ".git").exists()
