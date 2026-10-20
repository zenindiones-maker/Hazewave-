from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Callable, Mapping, Sequence

from hazewave.otio_adapter import (
    OTIOAdapterError,
    OTIOInterchangeReceipt,
    materialize_otio,
)
from hazewave.scene_detection import (
    SceneDetectionError,
    SceneDetectionReport,
    detect_scenes,
)
from hazewave.wave_editorial import (
    MediaManifest,
    WaveEditorialError,
    WaveEditorialTimeline,
    inspect_media,
)
from hazewave.wave_render import (
    WaveRenderError,
    WaveRenderReceipt,
    render_wave_timeline,
)


_PROOF_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class WaveLiveProofError(RuntimeError):
    pass


FixtureCreator = Callable[[Path], Path]
MediaInspector = Callable[[Path], MediaManifest]
SceneDetector = Callable[[Path], SceneDetectionReport]
OTIOMaterializer = Callable[..., OTIOInterchangeReceipt]
Renderer = Callable[..., WaveRenderReceipt]


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            json.dump(
                payload,
                handle,
                sort_keys=True,
                indent=2,
                ensure_ascii=False,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name is not None and os.path.exists(temp_name):
            os.unlink(temp_name)


def _default_run(args: list[str], *, timeout: float) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise WaveLiveProofError(f"WAVE_LIVE_TOOL_MISSING:{args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise WaveLiveProofError(f"WAVE_LIVE_TOOL_TIMEOUT:{args[0]}") from exc


def _default_fixture_creator(proof_dir: Path) -> Path:
    output = proof_dir / "fixture-source.mp4"
    args = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "color=c=red:s=640x360:r=24:d=2",
        "-f",
        "lavfi",
        "-i",
        "color=c=blue:s=640x360:r=24:d=2",
        "-f",
        "lavfi",
        "-i",
        "color=c=green:s=640x360:r=24:d=2",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000:duration=6",
        "-filter_complex",
        "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "-map",
        "[v]",
        "-map",
        "3:a:0",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "24",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-colorspace",
        "bt709",
        "-color_range",
        "tv",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-movflags",
        "+faststart",
        str(output),
    ]
    result = _default_run(args, timeout=120.0)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip().replace("\n", " ")
        if len(detail) > 500:
            detail = detail[:500]
        raise WaveLiveProofError(
            f"WAVE_LIVE_FIXTURE_CREATE_FAILED:{detail or 'NONZERO_EXIT'}"
        )
    if not output.is_file() or output.stat().st_size <= 0:
        raise WaveLiveProofError("WAVE_LIVE_FIXTURE_MISSING")
    return output


class WaveLiveProofRunner:
    def __init__(
        self,
        *,
        proof_root: Path | str,
        candidate_head: str,
        policy_digest: str,
        runtime_identity: str,
        fixture_creator: FixtureCreator | None = None,
        media_inspector: MediaInspector | None = None,
        scene_detector: SceneDetector | None = None,
        otio_materializer: OTIOMaterializer | None = None,
        renderer: Renderer | None = None,
    ) -> None:
        self.proof_root = Path(proof_root).expanduser().resolve()
        self.candidate_head = str(candidate_head or "").strip()
        self.policy_digest = str(policy_digest or "").strip()
        self.runtime_identity = str(runtime_identity or "").strip()

        if not _SHA1_RE.fullmatch(self.candidate_head):
            raise WaveLiveProofError("WAVE_LIVE_CANDIDATE_HEAD_INVALID")
        if not _SHA256_RE.fullmatch(self.policy_digest):
            raise WaveLiveProofError("WAVE_LIVE_POLICY_DIGEST_INVALID")
        if not self.runtime_identity:
            raise WaveLiveProofError("WAVE_LIVE_RUNTIME_IDENTITY_REQUIRED")

        self.fixture_creator = fixture_creator or _default_fixture_creator
        self.media_inspector = media_inspector or inspect_media
        self.scene_detector = scene_detector or detect_scenes
        self.otio_materializer = otio_materializer or materialize_otio
        self.renderer = renderer or render_wave_timeline

    @staticmethod
    def _safe_proof_id(value: str) -> str:
        proof_id = str(value or "").strip()
        if not _PROOF_ID_RE.fullmatch(proof_id):
            raise WaveLiveProofError("WAVE_LIVE_PROOF_ID_INVALID")
        return proof_id

    @staticmethod
    def _require_manifest(manifest: MediaManifest, *, code: str) -> MediaManifest:
        if not isinstance(manifest, MediaManifest):
            raise WaveLiveProofError(code)
        manifest.video_stream.color.require_managed_transform()
        return manifest

    @staticmethod
    def _require_scene_report(
        report: SceneDetectionReport,
        *,
        manifest: MediaManifest,
    ) -> SceneDetectionReport:
        if not isinstance(report, SceneDetectionReport):
            raise WaveLiveProofError("WAVE_LIVE_SCENE_REPORT_MALFORMED")
        if report.source_sha256 != manifest.source_sha256:
            raise WaveLiveProofError("WAVE_LIVE_SCENE_SOURCE_HASH_MISMATCH")
        if report.scene_count != len(report.scenes):
            raise WaveLiveProofError("WAVE_LIVE_SCENE_COUNT_MISMATCH")
        if report.scene_count < 2:
            raise WaveLiveProofError("WAVE_LIVE_SCENE_PROOF_INSUFFICIENT")
        return report

    def run(self, *, proof_id: str) -> dict[str, Any]:
        proof = self._safe_proof_id(proof_id)
        proof_dir = self.proof_root / proof
        if proof_dir.exists():
            raise WaveLiveProofError("WAVE_LIVE_PROOF_ALREADY_EXISTS")
        proof_dir.mkdir(parents=True, exist_ok=False)

        try:
            source = Path(self.fixture_creator(proof_dir)).expanduser().resolve()
        except WaveLiveProofError:
            raise
        except Exception as exc:
            raise WaveLiveProofError("WAVE_LIVE_FIXTURE_CREATE_FAILED") from exc

        try:
            source.relative_to(proof_dir)
        except ValueError as exc:
            raise WaveLiveProofError("WAVE_LIVE_FIXTURE_OUTSIDE_PROOF_ROOT") from exc
        if not source.is_file() or source.stat().st_size <= 0:
            raise WaveLiveProofError("WAVE_LIVE_FIXTURE_MISSING")

        try:
            manifest = self._require_manifest(
                self.media_inspector(source),
                code="WAVE_LIVE_MANIFEST_MALFORMED",
            )
        except WaveEditorialError as exc:
            raise WaveLiveProofError(f"WAVE_LIVE_MEDIA_INSPECT_FAILED:{exc}") from exc

        if manifest.source_path != str(source):
            raise WaveLiveProofError("WAVE_LIVE_MANIFEST_SOURCE_MISMATCH")
        if manifest.source_sha256 != _sha256_file(source):
            raise WaveLiveProofError("WAVE_LIVE_MANIFEST_HASH_MISMATCH")

        try:
            scenes = self._require_scene_report(
                self.scene_detector(source),
                manifest=manifest,
            )
        except SceneDetectionError as exc:
            raise WaveLiveProofError(f"WAVE_LIVE_SCENE_DETECT_FAILED:{exc}") from exc

        first_cut = float(scenes.scenes[0].end_seconds)
        if first_cut <= 0 or first_cut >= manifest.duration_seconds:
            raise WaveLiveProofError("WAVE_LIVE_SCENE_CUT_INVALID")

        timeline = WaveEditorialTimeline.create(
            timeline_id=f"{proof}-timeline",
            name="Hazewave WAVE Live Proof",
            manifest=manifest,
        )
        timeline = timeline.cut_clip(
            track_index=0,
            clip_index=0,
            timeline_seconds=first_cut,
            expected_revision=0,
        )

        second_scene = scenes.scenes[1]
        trim_delta = min(
            0.5,
            max(0.1, float(second_scene.duration_seconds) / 4.0),
        )
        trim_start = max(
            timeline.tracks[0].clips[1].source_in_seconds,
            float(second_scene.start_seconds) + trim_delta,
        )
        trim_end = manifest.duration_seconds
        if trim_start >= trim_end:
            raise WaveLiveProofError("WAVE_LIVE_TRIM_RANGE_INVALID")

        timeline = timeline.trim_clip(
            track_index=0,
            clip_index=1,
            new_in_seconds=trim_start,
            new_out_seconds=trim_end,
            expected_revision=1,
        )
        timeline = timeline.add_marker(
            name="Detected Scene Boundary",
            timeline_seconds=first_cut,
            expected_revision=2,
        )

        try:
            otio = self.otio_materializer(
                timeline,
                output_root=proof_dir / "otio",
                artifact_id=f"{proof}-timeline",
                expected_revision=timeline.revision,
            )
        except OTIOAdapterError as exc:
            raise WaveLiveProofError(f"WAVE_LIVE_OTIO_FAILED:{exc}") from exc
        if not isinstance(otio, OTIOInterchangeReceipt):
            raise WaveLiveProofError("WAVE_LIVE_OTIO_RECEIPT_MALFORMED")
        if otio.timeline_revision != timeline.revision:
            raise WaveLiveProofError("WAVE_LIVE_OTIO_REVISION_MISMATCH")

        try:
            render = self.renderer(
                timeline,
                manifests={manifest.source_sha256: manifest},
                output_root=proof_dir / "render",
                render_id=f"{proof}-render",
                expected_revision=timeline.revision,
            )
        except WaveRenderError as exc:
            raise WaveLiveProofError(f"WAVE_LIVE_RENDER_FAILED:{exc}") from exc
        if not isinstance(render, WaveRenderReceipt):
            raise WaveLiveProofError("WAVE_LIVE_RENDER_RECEIPT_MALFORMED")

        output = Path(render.output_path).expanduser().resolve()
        if not output.is_file() or output.stat().st_size <= 0:
            raise WaveLiveProofError("WAVE_LIVE_RENDER_OUTPUT_MISSING")
        if _sha256_file(output) != render.output_sha256:
            raise WaveLiveProofError("WAVE_LIVE_RENDER_OUTPUT_HASH_MISMATCH")

        qc = dict(render.video_qc)
        if (
            qc.get("schema") != "VideoQCReport/v1"
            or qc.get("encode_integrity") != "PASS"
        ):
            raise WaveLiveProofError("WAVE_LIVE_VIDEO_QC_FAILED")

        try:
            output_manifest = self._require_manifest(
                self.media_inspector(output),
                code="WAVE_LIVE_OUTPUT_MANIFEST_MALFORMED",
            )
        except WaveEditorialError as exc:
            raise WaveLiveProofError(
                f"WAVE_LIVE_OUTPUT_INSPECT_FAILED:{exc}"
            ) from exc
        if output_manifest.source_sha256 != render.output_sha256:
            raise WaveLiveProofError("WAVE_LIVE_OUTPUT_MANIFEST_HASH_MISMATCH")

        payload: dict[str, Any] = {
            "schema": "WaveLiveProof/v1",
            "status": "PASS",
            "authority": "HAZEWAVE_HARNESS",
            "portfolio_authority": "NONE",
            "domain": "WAVE",
            "proof_id": proof,
            "candidate_head": self.candidate_head,
            "policy_digest": self.policy_digest,
            "runtime_identity": self.runtime_identity,
            "private_media_policy": "LOCAL_BY_DEFAULT",
            "fixture": {
                "path": str(source),
                "sha256": manifest.source_sha256,
            },
            "manifest": manifest.to_dict(),
            "scene_detection": scenes.to_dict(),
            "timeline": timeline.to_dict(),
            "otio": otio.to_dict(),
            "render": render.to_dict(),
            "video_qc": qc,
            "output_manifest": output_manifest.to_dict(),
            "human_review": "REQUIRED",
        }

        receipt_path = proof_dir / "wave-live-proof.json"
        _atomic_write_json(receipt_path, payload)
        receipt_sha256 = _sha256_file(receipt_path)

        return {
            **payload,
            "receipt_path": str(receipt_path.resolve()),
            "receipt_sha256": receipt_sha256,
        }


def _print_json(payload: Mapping[str, Any]) -> None:
    print(json.dumps(dict(payload), sort_keys=True, indent=2, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hazewave.wave_live_proof")
    parser.add_argument("--proof-root", type=Path, required=True)
    parser.add_argument("--proof-id", required=True)
    parser.add_argument("--candidate-head", required=True)
    parser.add_argument("--policy-digest", required=True)
    parser.add_argument("--runtime-identity", required=True)
    args = parser.parse_args(argv)

    try:
        runner = WaveLiveProofRunner(
            proof_root=args.proof_root,
            candidate_head=args.candidate_head,
            policy_digest=args.policy_digest,
            runtime_identity=args.runtime_identity,
        )
        receipt = runner.run(proof_id=args.proof_id)
    except WaveLiveProofError as exc:
        print(f"WAVE_LIVE_PROOF=FAIL:{exc}")
        return 20

    _print_json(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
