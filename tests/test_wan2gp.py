from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hazewave.cli import build_parser
from hazewave.wan2gp import (
    WAN2GP_PINNED_REF,
    WAN2GP_REPOSITORY,
    Wan2GPError,
    dependency_commands,
    install_runtime,
    process_command,
    process_queue,
    runtime_status,
    serve_command,
)


def test_dependency_commands_match_upstream_readme() -> None:
    python = Path("/runtime/.venv/bin/python")
    rtx = dependency_commands(python, "rtx")
    gtx = dependency_commands(python, "gtx10")

    assert rtx[1] == [
        str(python),
        "-m",
        "pip",
        "install",
        "torch==2.10.0",
        "torchvision==0.25.0",
        "torchaudio==2.10.0",
        "--index-url",
        "https://download.pytorch.org/whl/cu130",
    ]
    assert gtx[1][-2:] == [
        "--index-url",
        "https://download.pytorch.org/whl/cu128",
    ]
    assert "torch==2.7.1" in gtx[1]
    assert rtx[2][-2:] == ["-r", "requirements.txt"]
    assert gtx[2][-2:] == ["-r", "requirements.txt"]


def test_install_clones_the_exact_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = tmp_path / "Wan2GP"
    calls: list[list[str]] = []

    def fake_run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        stdout = ""
        if command[:2] == ["git", "rev-parse"]:
            stdout = WAN2GP_PINNED_REF + "\n"
        if command[:2] == ["git", "checkout"]:
            runtime.mkdir(parents=True, exist_ok=True)
            (runtime / "wgp.py").write_text("print('wgp')\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr("hazewave.wan2gp._run", fake_run)
    result = install_runtime(runtime, install_deps=False)

    assert calls[0][:4] == [
        "git",
        "clone",
        "--filter=blob:none",
        WAN2GP_REPOSITORY,
    ]
    assert calls[0][4] == str(runtime.resolve())
    assert calls[1] == ["git", "checkout", "--detach", WAN2GP_PINNED_REF]
    assert result.upstream_ref == WAN2GP_PINNED_REF
    assert result.dependencies_installed is False


def test_install_refuses_dirty_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = tmp_path / "Wan2GP"
    runtime.mkdir()
    (runtime / ".git").mkdir()

    def fake_run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        assert command[:3] == ["git", "status", "--porcelain"]
        return subprocess.CompletedProcess(command, 0, " M wgp.py\n", "")

    monkeypatch.setattr("hazewave.wan2gp._run", fake_run)
    with pytest.raises(Wan2GPError, match="local changes"):
        install_runtime(runtime, install_deps=False)


def test_install_rejects_ref_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"checkout": False}

    def fake_run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        stdout = "deadbeef\n" if command[:2] == ["git", "rev-parse"] else ""
        if command[:2] == ["git", "checkout"]:
            calls["checkout"] = True
            target = tmp_path / "Wan2GP"
            target.mkdir(parents=True, exist_ok=True)
            (target / "wgp.py").write_text("x\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, stdout, "")

    monkeypatch.setattr("hazewave.wan2gp._run", fake_run)
    with pytest.raises(Wan2GPError, match="ref mismatch"):
        install_runtime(tmp_path / "Wan2GP", install_deps=False)
    assert calls["checkout"] is True


def test_status_reports_missing_runtime(tmp_path: Path) -> None:
    status = runtime_status(tmp_path / "missing")
    assert status.installed is False
    assert status.upstream_ref is None
    assert status.expected_ref == WAN2GP_PINNED_REF
    assert status.dependencies_installed is False


def test_serve_and_process_commands_match_upstream_flags() -> None:
    python = Path("/runtime/.venv/bin/python")
    assert serve_command(
        python,
        port=7860,
        listen=True,
        open_browser=True,
        memory_profile="4",
        attention="sdpa",
    ) == [
        str(python),
        "wgp.py",
        "--server-port",
        "7860",
        "--listen",
        "--open-browser",
        "--profile",
        "4",
        "--attention",
        "sdpa",
    ]
    assert process_command(
        python,
        Path("/tmp/lote.zip"),
        output_dir=Path("output/wan2gp"),
        dry_run=True,
    ) == [
        str(python),
        "wgp.py",
        "--process",
        "/tmp/lote.zip",
        "--output-dir",
        "output/wan2gp",
        "--dry-run",
    ]


def test_cli_exposes_the_pinned_install() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["wan2gp", "install", "--gpu", "gtx10", "--skip-deps"]
    )
    assert args.command == "wan2gp"
    assert args.wan_command == "install"
    assert args.gpu == "gtx10"
    assert args.skip_deps is True
    assert args.runtime_dir == ".hazewave/runtime/Wan2GP"

    process_args = parser.parse_args(["wan2gp", "process", "lote.zip", "--dry-run"])
    assert process_args.queue == "lote.zip"
    assert process_args.output_dir == "output/wan2gp"
    assert process_args.dry_run is True


def test_process_requires_an_existing_queue(tmp_path: Path) -> None:
    with pytest.raises(Wan2GPError, match="does not exist"):
        process_queue(tmp_path / "lote.zip", runtime_dir=tmp_path / "Wan2GP")
