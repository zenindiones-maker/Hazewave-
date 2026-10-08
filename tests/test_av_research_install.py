from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "codespaces" / "install-av-research-open-tools.sh"


def test_av_research_install_is_opt_in_with_three_profiles() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    for token in ('--preflight', '--core', '--music', 'AV_RESEARCH_INSTALL=NOT_ATTEMPTED',
                  'AV_RESEARCH_INSTALL=PASS', 'HAZEWAVE_ACCEPT_AGPL3'):
        assert token in script
    assert 'pillow==12.3.0' in script
    assert 'scenedetect-headless==0.7.1' in script
    assert 'opentimelineio==0.18.1' in script
    assert 'librosa==1.0.0' in script
    assert 'essentia==2.1b6.dev1389' in script
    assert 'av-research-venv' in script
    assert 'pip install' in script


def test_av_research_install_cannot_touch_stock_or_add_paid_capacity() -> None:
    script = SCRIPT.read_text(encoding="utf-8")
    for banned in ("gh codespace create", "apt install", "sudo ", "docker run",
                   "hazewave-reflex serve-stop", "pip install --user",
                   "git reset", "git switch", "git push", "@latest"):
        assert banned not in script
    assert 'python3 -m venv' in script
    assert 'pip install --no-input --disable-pip-version-check --no-cache-dir --only-binary=:all:' in script


def test_av_research_install_syntax() -> None:
    r = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
