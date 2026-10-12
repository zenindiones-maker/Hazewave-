from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


# Upstream documents this clone URL. GitHub redirects it to deepbeepmeep/WanGP.
WAN2GP_REPOSITORY = "https://github.com/deepbeepmeep/Wan2GP.git"
WAN2GP_PINNED_REF = "57d57dc753edcd5472e6768809420fdda4d835b6"
DEFAULT_RUNTIME_DIR = Path(".hazewave/runtime/Wan2GP")
DEFAULT_SERVER_PORT = 7860

# Official manual install blocks from the Wan2GP README.
# Wan 2.1 / 2.2, LTX-2.5 and the 14B finetunes are checkpoints this app
# downloads itself. They are not separate Git repositories.
TORCH_PROFILES: dict[str, tuple[str, tuple[str, ...]]] = {
    "rtx": (
        "https://download.pytorch.org/whl/cu130",
        ("torch==2.10.0", "torchvision==0.25.0", "torchaudio==2.10.0"),
    ),
    "gtx10": (
        "https://download.pytorch.org/whl/cu128",
        ("torch==2.7.1", "torchvision==0.22.1", "torchaudio==2.7.1"),
    ),
}


class Wan2GPError(RuntimeError):
    """Raised when the Wan2GP runtime cannot be installed or launched."""


@dataclass(frozen=True)
class Wan2GPInstallResult:
    runtime_dir: Path
    upstream_ref: str
    gpu_profile: str
    dependencies_installed: bool


@dataclass(frozen=True)
class Wan2GPStatus:
    runtime_dir: Path
    installed: bool
    upstream_ref: str | None
    expected_ref: str
    dependencies_installed: bool


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    process = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if process.returncode != 0:
        details = process.stderr.strip() or process.stdout.strip()
        raise Wan2GPError(
            f"Command failed ({process.returncode}): {' '.join(command)}\n{details}"
        )
    return process


def _runtime_python(runtime: Path) -> Path:
    folder = "Scripts" if os.name == "nt" else "bin"
    name = "python.exe" if os.name == "nt" else "python"
    return runtime / ".venv" / folder / name


def dependency_commands(python: Path, gpu_profile: str) -> list[list[str]]:
    """Exact pip commands from the upstream Wan2GP manual install."""

    try:
        index_url, packages = TORCH_PROFILES[gpu_profile]
    except KeyError as exc:
        choices = ", ".join(TORCH_PROFILES)
        raise Wan2GPError(f"gpu profile must be one of: {choices}") from exc
    return [
        [str(python), "-m", "pip", "install", "--upgrade", "pip"],
        [str(python), "-m", "pip", "install", *packages, "--index-url", index_url],
        [str(python), "-m", "pip", "install", "-r", "requirements.txt"],
    ]


def _ensure_venv(runtime: Path) -> Path:
    python = _runtime_python(runtime)
    if not python.is_file():
        _run([sys.executable, "-m", "venv", str(runtime / ".venv")], cwd=runtime)
    if not python.is_file():
        raise Wan2GPError(f"Could not create the Wan2GP virtualenv in {runtime / '.venv'}")
    return python


def install_runtime(
    runtime_dir: str | Path = DEFAULT_RUNTIME_DIR,
    *,
    upstream_ref: str = WAN2GP_PINNED_REF,
    gpu_profile: str = "rtx",
    install_deps: bool = True,
) -> Wan2GPInstallResult:
    """Clone the pinned Wan2GP checkout outside the Hazewave Git tree."""

    if gpu_profile not in TORCH_PROFILES:
        choices = ", ".join(TORCH_PROFILES)
        raise Wan2GPError(f"gpu profile must be one of: {choices}")
    if shutil.which("git") is None:
        raise Wan2GPError("git is required to install Wan2GP.")

    target = Path(runtime_dir).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        if not (target / ".git").is_dir():
            raise Wan2GPError(
                f"Runtime path already exists but is not a Git checkout: {target}"
            )
        dirty = _run(["git", "status", "--porcelain"], cwd=target).stdout.strip()
        if dirty:
            raise Wan2GPError(
                f"Wan2GP runtime has local changes; refusing to overwrite: {target}"
            )
        _run(["git", "fetch", "--depth", "1", "origin", upstream_ref], cwd=target)
    else:
        _run(
            ["git", "clone", "--filter=blob:none", WAN2GP_REPOSITORY, str(target)]
        )

    _run(["git", "checkout", "--detach", upstream_ref], cwd=target)
    resolved_ref = _run(["git", "rev-parse", "HEAD"], cwd=target).stdout.strip()
    if resolved_ref != upstream_ref:
        raise Wan2GPError(
            f"Wan2GP ref mismatch: expected {upstream_ref}, got {resolved_ref}"
        )
    if not (target / "wgp.py").is_file():
        raise Wan2GPError(f"Wan2GP checkout is missing wgp.py: {target}")

    if install_deps:
        python = _ensure_venv(target)
        for command in dependency_commands(python, gpu_profile):
            _run(command, cwd=target)

    return Wan2GPInstallResult(
        runtime_dir=target,
        upstream_ref=resolved_ref,
        gpu_profile=gpu_profile,
        dependencies_installed=install_deps,
    )


def runtime_status(runtime_dir: str | Path = DEFAULT_RUNTIME_DIR) -> Wan2GPStatus:
    target = Path(runtime_dir).expanduser().resolve()
    installed = (target / ".git").is_dir() and (target / "wgp.py").is_file()
    upstream_ref = None
    if installed and shutil.which("git") is not None:
        upstream_ref = _run(["git", "rev-parse", "HEAD"], cwd=target).stdout.strip()
    return Wan2GPStatus(
        runtime_dir=target,
        installed=installed,
        upstream_ref=upstream_ref,
        expected_ref=WAN2GP_PINNED_REF,
        dependencies_installed=_runtime_python(target).is_file(),
    )


def _require_runtime(runtime_dir: str | Path) -> tuple[Path, Path]:
    target = Path(runtime_dir).expanduser().resolve()
    if not (target / "wgp.py").is_file():
        raise Wan2GPError(
            f"Wan2GP runtime is not installed at {target}. Run 'hazewave wan2gp install'."
        )
    python = _runtime_python(target)
    if not python.is_file():
        raise Wan2GPError(
            "Wan2GP dependencies are not installed. "
            "Run 'hazewave wan2gp install' without --skip-deps."
        )
    return target, python


def serve_command(
    python: Path,
    *,
    port: int = DEFAULT_SERVER_PORT,
    listen: bool = False,
    share: bool = False,
    open_browser: bool = False,
    memory_profile: str | None = None,
    attention: str | None = None,
) -> list[str]:
    command = [str(python), "wgp.py", "--server-port", str(int(port))]
    if listen:
        command.append("--listen")
    if share:
        command.append("--share")
    if open_browser:
        command.append("--open-browser")
    if memory_profile:
        command.extend(["--profile", memory_profile])
    if attention:
        command.extend(["--attention", attention])
    return command


def process_command(
    python: Path,
    queue_file: str | Path,
    *,
    output_dir: str | Path | None = None,
    dry_run: bool = False,
) -> list[str]:
    command = [str(python), "wgp.py", "--process", str(queue_file)]
    if output_dir:
        command.extend(["--output-dir", str(output_dir)])
    if dry_run:
        command.append("--dry-run")
    return command


def serve_runtime(
    runtime_dir: str | Path = DEFAULT_RUNTIME_DIR,
    *,
    port: int = DEFAULT_SERVER_PORT,
    listen: bool = False,
    share: bool = False,
    open_browser: bool = False,
    memory_profile: str | None = None,
    attention: str | None = None,
) -> int:
    """Start the official Wan2GP web UI (python wgp.py) in the foreground."""

    target, python = _require_runtime(runtime_dir)
    command = serve_command(
        python,
        port=port,
        listen=listen,
        share=share,
        open_browser=open_browser,
        memory_profile=memory_profile,
        attention=attention,
    )
    process = subprocess.run(command, cwd=target, check=False)
    return int(process.returncode)


def process_queue(
    queue_file: str | Path,
    runtime_dir: str | Path = DEFAULT_RUNTIME_DIR,
    *,
    output_dir: str | Path | None = None,
    dry_run: bool = False,
) -> int:
    """Run a saved Wan2GP queue headless, the overnight batch mode."""

    source = Path(queue_file).expanduser().resolve()
    if not source.is_file():
        raise Wan2GPError(f"Queue file does not exist: {source}")
    target, python = _require_runtime(runtime_dir)
    destination = (
        Path(output_dir).expanduser().resolve() if output_dir is not None else None
    )
    command = process_command(
        python,
        source,
        output_dir=destination,
        dry_run=dry_run,
    )
    process = subprocess.run(command, cwd=target, check=False)
    return int(process.returncode)
