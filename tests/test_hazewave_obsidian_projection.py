from __future__ import annotations

import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "hazewave_obsidian_projection.sh"


def test_obsidian_projection_copies_brain_without_deleting_human_notes(tmp_path: Path) -> None:
    target = tmp_path / "vault" / "Hazewave"
    target.mkdir(parents=True)
    human_note = target / "60-Human-Review" / "Owner-Note.md"
    human_note.parent.mkdir(parents=True)
    human_note.write_text("keep me\n", encoding="utf-8")

    env = os.environ.copy()
    env["HAZEWAVE_OBSIDIAN_ROOT"] = str(target)

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "HAZEWAVE_OBSIDIAN_PROJECTION=PASS" in result.stdout
    assert (target / "00-Brain" / "Hazewave-Brain.md").is_file()
    assert human_note.read_text(encoding="utf-8") == "keep me\n"


def test_obsidian_projection_rejects_symlink_target(tmp_path: Path) -> None:
    real_target = tmp_path / "real"
    real_target.mkdir()
    linked_target = tmp_path / "linked"
    linked_target.symlink_to(real_target, target_is_directory=True)

    env = os.environ.copy()
    env["HAZEWAVE_OBSIDIAN_ROOT"] = str(linked_target)

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "HAZEWAVE_OBSIDIAN_TARGET_SYMLINK_FORBIDDEN" in result.stderr
