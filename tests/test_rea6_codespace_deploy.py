from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "codespaces" / "deploy-rea6-existing-codespace.sh"
HEAD = "31ec021cf5c2e9c8d204a777dafdce6fa29bd6a3"


def test_rea6_codespace_deployer_is_explicit_and_identity_pinned() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    assert "hazewave-zero-cost-4jxp45676rq6279xx" in script
    assert HEAD in script
    assert "zenindiones-maker/Hazewave-" in script
    assert 'CODESPACE_NAME' in script
    assert '"$(git rev-parse HEAD)"' in script
    assert 'git status --porcelain' in script
    assert "git remote get-url origin" in script
    assert 'INSTALL=NOT_ATTEMPTED' in script
    assert '"--install"' in script
    assert 'install-reverse-engineering-foundation.sh --preflight' in script
    assert "reverse-engineering-doctor.sh" in script


def test_rea6_codespace_deployer_does_not_create_machine_or_touch_stock() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    forbidden = (
        "gh codespace create", "git switch", "git checkout", "git reset",
        "git push", "git merge", "rm -rf", "hazewave-reflex serve-stop",
        "sudo gh", "docker run",
    )
    assert not any(fragment in script for fragment in forbidden)


def test_rea6_codespace_deployer_has_valid_shell_syntax() -> None:
    check = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
