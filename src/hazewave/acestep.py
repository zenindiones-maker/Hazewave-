from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import httpx


ACESTEP_REPOSITORY = "https://github.com/ace-step/ACE-Step-1.5.git"
ACESTEP_PINNED_REF = "ca1e85fe9430179831e6bc6be790c332190a3866"
ACESTEP_DEFAULT_MODEL_REPO = "ACE-Step/Ace-Step1.5"
DEFAULT_API_URL = "http://127.0.0.1:8001"
DEFAULT_RUNTIME_DIR = Path(".hazewave/runtime/ACE-Step-1.5")


class AceStepError(RuntimeError):
    """Raised when the ACE-Step runtime or API cannot complete an operation."""


@dataclass(frozen=True)
class AceStepInstallResult:
    runtime_dir: Path
    upstream_ref: str
    models_prefetched: bool


@dataclass(frozen=True)
class AceStepGenerationResult:
    task_id: str
    output_path: Path
    mode: str
    prompt: str


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
        raise AceStepError(
            f"Command failed ({process.returncode}): {' '.join(command)}\n{details}"
        )
    return process


def install_runtime(
    runtime_dir: str | Path = DEFAULT_RUNTIME_DIR,
    *,
    upstream_ref: str = ACESTEP_PINNED_REF,
    prefetch_models: bool = False,
    model_repo: str = ACESTEP_DEFAULT_MODEL_REPO,
) -> AceStepInstallResult:
    """Install the pinned ACE-Step runtime outside the Hazewave Git tree."""

    if shutil.which("git") is None:
        raise AceStepError("git is required to install ACE-Step.")
    if shutil.which("uv") is None:
        raise AceStepError(
            "uv is required. Install it first from https://docs.astral.sh/uv/."
        )

    target = Path(runtime_dir).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists():
        if not (target / ".git").is_dir():
            raise AceStepError(
                f"Runtime path already exists but is not a Git checkout: {target}"
            )
        dirty = _run(["git", "status", "--porcelain"], cwd=target).stdout.strip()
        if dirty:
            raise AceStepError(
                f"ACE-Step runtime has local changes; refusing to overwrite: {target}"
            )
        _run(["git", "fetch", "--depth", "1", "origin", upstream_ref], cwd=target)
    else:
        _run(["git", "clone", "--filter=blob:none", ACESTEP_REPOSITORY, str(target)])

    _run(["git", "checkout", "--detach", upstream_ref], cwd=target)
    resolved_ref = _run(["git", "rev-parse", "HEAD"], cwd=target).stdout.strip()
    if resolved_ref != upstream_ref:
        raise AceStepError(
            f"ACE-Step ref mismatch: expected {upstream_ref}, got {resolved_ref}"
        )

    _run(["uv", "sync"], cwd=target)

    if prefetch_models:
        code = (
            "from huggingface_hub import snapshot_download; "
            f"snapshot_download({model_repo!r})"
        )
        _run(["uv", "run", "python", "-c", code], cwd=target)

    return AceStepInstallResult(
        runtime_dir=target,
        upstream_ref=resolved_ref,
        models_prefetched=prefetch_models,
    )


def serve_runtime(
    runtime_dir: str | Path = DEFAULT_RUNTIME_DIR,
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> int:
    """Start the official ACE-Step REST API in the foreground."""

    target = Path(runtime_dir).expanduser().resolve()
    if not (target / ".git").is_dir():
        raise AceStepError(
            f"ACE-Step runtime is not installed at {target}. Run 'hazewave acestep install'."
        )
    if shutil.which("uv") is None:
        raise AceStepError("uv is required to run ACE-Step.")

    env = os.environ.copy()
    if model:
        env["ACESTEP_CONFIG_PATH"] = model
    if api_key:
        env["ACESTEP_API_KEY"] = api_key

    process = subprocess.run(
        ["uv", "run", "acestep-api"],
        cwd=target,
        env=env,
        check=False,
    )
    return int(process.returncode)


class AceStepClient:
    """Client for the official ACE-Step asynchronous REST API."""

    def __init__(
        self,
        base_url: str = DEFAULT_API_URL,
        *,
        api_key: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "AceStepClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @staticmethod
    def _unwrap(response: httpx.Response) -> Any:
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise AceStepError("ACE-Step returned a non-object response.")
        if payload.get("code") != 200:
            raise AceStepError(str(payload.get("error") or "ACE-Step API error"))
        return payload.get("data")

    def health(self) -> bool:
        response = self._client.get("health")
        return response.status_code == 200

    def submit_instrumental(
        self,
        prompt: str,
        *,
        audio_path: str | Path | None = None,
        mode: str = "reference",
        cover_strength: float = 0.8,
        duration: float | None = None,
        bpm: int | None = None,
        key_scale: str | None = None,
        time_signature: str | None = None,
        audio_format: str = "wav",
        model: str | None = None,
        thinking: bool = True,
    ) -> str:
        if not prompt.strip():
            raise AceStepError("A non-empty music prompt is required.")
        if mode not in {"text", "reference", "cover"}:
            raise AceStepError("mode must be one of: text, reference, cover")
        if not 0.0 <= cover_strength <= 1.0:
            raise AceStepError("cover_strength must be between 0.0 and 1.0.")
        if audio_format not in {"wav", "wav32", "flac", "mp3", "opus", "aac"}:
            raise AceStepError(f"Unsupported ACE-Step audio format: {audio_format}")

        source: Path | None = None
        if mode in {"reference", "cover"}:
            if audio_path is None:
                raise AceStepError(f"mode={mode} requires an audio file.")
            source = Path(audio_path).expanduser().resolve()
            if not source.is_file():
                raise AceStepError(f"Reference audio does not exist: {source}")

        strict_prompt = (
            prompt.strip()
            + ". Instrumental only. No vocals, no singing, no choir, no spoken words."
        )
        data: dict[str, str] = {
            "prompt": strict_prompt,
            "lyrics": "[Instrumental]",
            "audio_format": audio_format,
            "batch_size": "1",
            "thinking": str(bool(thinking)).lower(),
            "task_type": "cover" if mode == "cover" else "text2music",
        }
        if mode == "cover":
            data["audio_cover_strength"] = str(float(cover_strength))
        if duration is not None:
            data["audio_duration"] = str(float(duration))
        if bpm is not None:
            data["bpm"] = str(int(bpm))
        if key_scale:
            data["key_scale"] = key_scale
        if time_signature:
            data["time_signature"] = time_signature
        if model:
            data["model"] = model

        files: dict[str, tuple[str, Any, str]] = {}
        handle = None
        try:
            if source is not None:
                handle = source.open("rb")
                field = "src_audio" if mode == "cover" else "reference_audio"
                files[field] = (source.name, handle, "application/octet-stream")

            response = self._client.post("release_task", data=data, files=files or None)
            result = self._unwrap(response)
        finally:
            if handle is not None:
                handle.close()

        if not isinstance(result, dict) or not result.get("task_id"):
            raise AceStepError("ACE-Step did not return a task_id.")
        return str(result["task_id"])

    def query_task(self, task_id: str) -> dict[str, Any]:
        response = self._client.post(
            "query_result",
            json={"task_id_list": [task_id]},
        )
        data = self._unwrap(response)
        if not isinstance(data, list) or not data:
            raise AceStepError(f"ACE-Step returned no status for task {task_id}.")
        item = data[0]
        if not isinstance(item, dict):
            raise AceStepError("ACE-Step returned an invalid task status object.")
        return item

    def wait_for_task(
        self,
        task_id: str,
        *,
        timeout_seconds: float = 1800.0,
        poll_seconds: float = 3.0,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout_seconds
        while True:
            item = self.query_task(task_id)
            status = int(item.get("status", 0))
            if status == 1:
                return item
            if status == 2:
                raise AceStepError(
                    str(item.get("error") or f"ACE-Step task failed: {task_id}")
                )
            if time.monotonic() >= deadline:
                raise AceStepError(f"Timed out waiting for ACE-Step task {task_id}.")
            time.sleep(poll_seconds)

    @staticmethod
    def _first_audio_url(task: dict[str, Any]) -> str:
        result = task.get("result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError as exc:
                raise AceStepError("ACE-Step returned malformed result JSON.") from exc

        if isinstance(result, dict):
            result = [result]
        if not isinstance(result, list) or not result:
            raise AceStepError("ACE-Step task succeeded without audio results.")

        first = result[0]
        if not isinstance(first, dict) or not first.get("file"):
            raise AceStepError("ACE-Step result is missing the audio file URL.")
        return str(first["file"])

    def download_result(
        self,
        task: dict[str, Any],
        destination: str | Path,
    ) -> Path:
        target = Path(destination).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        relative_url = self._first_audio_url(task)
        url = urljoin(self.base_url, relative_url)
        with self._client.stream("GET", url) as response:
            response.raise_for_status()
            with target.open("wb") as output:
                for chunk in response.iter_bytes():
                    output.write(chunk)
        return target

    def generate_instrumental(
        self,
        prompt: str,
        *,
        destination: str | Path,
        audio_path: str | Path | None = None,
        mode: str = "reference",
        cover_strength: float = 0.8,
        duration: float | None = None,
        bpm: int | None = None,
        key_scale: str | None = None,
        time_signature: str | None = None,
        audio_format: str = "wav",
        model: str | None = None,
        thinking: bool = True,
        timeout_seconds: float = 1800.0,
    ) -> AceStepGenerationResult:
        task_id = self.submit_instrumental(
            prompt,
            audio_path=audio_path,
            mode=mode,
            cover_strength=cover_strength,
            duration=duration,
            bpm=bpm,
            key_scale=key_scale,
            time_signature=time_signature,
            audio_format=audio_format,
            model=model,
            thinking=thinking,
        )
        task = self.wait_for_task(task_id, timeout_seconds=timeout_seconds)
        output_path = self.download_result(task, destination)
        return AceStepGenerationResult(
            task_id=task_id,
            output_path=output_path,
            mode=mode,
            prompt=prompt,
        )
