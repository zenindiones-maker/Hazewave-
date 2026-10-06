from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Callable, Mapping

from hazewave.animation_qc import AnimationQCError, analyze_animation_sequence
from hazewave.blender_bridge import (
    BLENDER_EXPECTED_VERSION,
    BlenderBridgeError,
    BlenderSceneSnapshot,
    build_blender_request,
)
from hazewave.harness import WAVE, HazewaveTask, issue_authorization, route_task
from hazewave.video_qc import VideoQCError, analyze_video_qc


_PROOF_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


class CartoonLiveProofError(RuntimeError):
    pass


MediaRunner = Callable[[list[str], float], subprocess.CompletedProcess[str]]


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


def _default_media_runner(
    args: list[str],
    timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args,
            check=False,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise CartoonLiveProofError(
            f"CARTOON_MEDIA_TOOL_MISSING:{args[0]}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise CartoonLiveProofError(
            f"CARTOON_MEDIA_TIMEOUT:{args[0]}"
        ) from exc


def _write_storyboard_panel(
    path: Path,
    *,
    panel_index: int,
    width: int = 640,
    height: int = 360,
) -> None:
    backgrounds = (
        (28, 40, 66),
        (38, 50, 76),
        (48, 60, 86),
    )
    background = backgrounds[(panel_index - 1) % len(backgrounds)]
    pixels = bytearray(background * (width * height))

    center_x = (width // 4) * panel_index
    center_x = max(60, min(width - 60, center_x))
    body_w = 54
    body_h = 118
    top = height // 2 - body_h // 2
    left = center_x - body_w // 2
    ink = (235, 238, 245)

    for y in range(top, min(height, top + body_h)):
        for x in range(max(0, left), min(width, left + body_w)):
            offset = (y * width + x) * 3
            pixels[offset : offset + 3] = bytes(ink)

    floor_y = min(height - 1, top + body_h + 24)
    for y in range(floor_y, min(height, floor_y + 3)):
        for x in range(width):
            offset = (y * width + x) * 3
            pixels[offset : offset + 3] = b"\x8a\x9a\xb8"

    path.write_bytes(
        f"P6\n{width} {height}\n255\n".encode("ascii") + bytes(pixels)
    )


class CartoonLiveProofRunner:
    def __init__(
        self,
        *,
        blender_executor: Any,
        blender_root: Path | str,
        proof_root: Path | str,
        candidate_head: str,
        policy_digest: str,
        runtime_identity: str,
        media_runner: MediaRunner | None = None,
        video_qc_analyzer: Callable[[Path], Any] | None = None,
    ) -> None:
        self.blender_executor = blender_executor
        self.blender_root = Path(blender_root).expanduser().resolve()
        self.proof_root = Path(proof_root).expanduser().resolve()
        self.candidate_head = str(candidate_head or "").strip()
        self.policy_digest = str(policy_digest or "").strip()
        self.runtime_identity = str(runtime_identity or "").strip()
        self.media_runner = media_runner or _default_media_runner
        self.video_qc_analyzer = video_qc_analyzer or analyze_video_qc

        if not self.candidate_head:
            raise CartoonLiveProofError("CARTOON_CANDIDATE_HEAD_REQUIRED")
        if not self.policy_digest:
            raise CartoonLiveProofError("CARTOON_POLICY_DIGEST_REQUIRED")
        if not self.runtime_identity:
            raise CartoonLiveProofError("CARTOON_RUNTIME_IDENTITY_REQUIRED")

    @staticmethod
    def _safe_proof_id(value: str) -> str:
        proof_id = str(value or "").strip()
        if not _PROOF_ID_RE.fullmatch(proof_id):
            raise CartoonLiveProofError("CARTOON_PROOF_ID_INVALID")
        return proof_id

    @staticmethod
    def _authorization(operation: str, task_id: str):
        try:
            return issue_authorization(
                route_task(
                    HazewaveTask(
                        task_id=task_id,
                        goal="Execute bounded cartoon live proof operation",
                        required_capability=operation,
                        requested_domain=WAVE,
                    )
                )
            )
        except (ValueError, PermissionError) as exc:
            raise CartoonLiveProofError(
                f"CARTOON_AUTHORIZATION_FAILED:{operation}"
            ) from exc

    def _request(
        self,
        *,
        operation: str,
        task_id: str,
        request_id: str,
        arguments: Mapping[str, Any],
        expected_scene_identity: str,
        expected_blend_sha256: str,
        seed: int,
        timeout_seconds: float,
    ):
        now = datetime.now(timezone.utc)
        try:
            return build_blender_request(
                authorization=self._authorization(operation, task_id),
                request_id=request_id,
                idempotency_key=request_id,
                operation=operation,
                arguments=arguments,
                expected_blender_version=BLENDER_EXPECTED_VERSION,
                expected_scene_identity=expected_scene_identity,
                expected_blend_sha256=expected_blend_sha256,
                seed=seed,
                issued_at=now,
                deadline=now + timedelta(seconds=timeout_seconds),
            )
        except BlenderBridgeError as exc:
            raise CartoonLiveProofError(
                f"CARTOON_BLENDER_REQUEST_INVALID:{exc}"
            ) from exc

    @staticmethod
    def _artifact_payload(
        path: Path,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        _atomic_write_json(path, payload)
        return {
            **dict(payload),
            "artifact_path": str(path.resolve()),
            "artifact_sha256": _sha256_file(path),
        }

    def _run_media(
        self,
        args: list[str],
        *,
        output: Path,
        timeout_seconds: float,
        code: str,
    ) -> None:
        try:
            completed = self.media_runner(args, timeout_seconds)
        except CartoonLiveProofError:
            raise
        except Exception as exc:
            raise CartoonLiveProofError(f"{code}:RUNNER_FAILED") from exc
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "").strip()
            if len(detail) > 500:
                detail = detail[:500]
            raise CartoonLiveProofError(
                f"{code}:{detail or 'NONZERO_EXIT'}"
            )
        if not output.is_file() or output.stat().st_size <= 0:
            raise CartoonLiveProofError(f"{code}:OUTPUT_MISSING")

    def _video_qc(self, path: Path) -> dict[str, Any]:
        try:
            report = self.video_qc_analyzer(path)
        except (VideoQCError, Exception) as exc:
            if isinstance(exc, CartoonLiveProofError):
                raise
            raise CartoonLiveProofError("CARTOON_VIDEO_QC_FAILED") from exc
        to_dict = getattr(report, "to_dict", None)
        if not callable(to_dict):
            raise CartoonLiveProofError("CARTOON_VIDEO_QC_MALFORMED")
        payload = to_dict()
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "VideoQCReport/v1"
            or payload.get("encode_integrity") != "PASS"
        ):
            raise CartoonLiveProofError("CARTOON_VIDEO_QC_MALFORMED")
        return payload

    def _execute_blender(
        self,
        request: Any,
        *,
        blend_path: Path | None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        try:
            response = self.blender_executor.execute(
                request,
                blend_path=blend_path,
                timeout_seconds=timeout_seconds,
            )
        except BlenderBridgeError as exc:
            raise CartoonLiveProofError(
                f"CARTOON_BLENDER_EXECUTION_FAILED:{request.operation}:{exc}"
            ) from exc
        if not isinstance(response, Mapping) or response.get("status") != "PASS":
            raise CartoonLiveProofError(
                f"CARTOON_BLENDER_EXECUTION_FAILED:{request.operation}"
            )
        result = response.get("result")
        if not isinstance(result, Mapping):
            raise CartoonLiveProofError(
                f"CARTOON_BLENDER_RESULT_MALFORMED:{request.operation}"
            )
        return dict(result)

    def run(
        self,
        *,
        proof_id: str,
        haze_audio: Path | str,
    ) -> dict[str, Any]:
        proof = self._safe_proof_id(proof_id)
        audio = Path(haze_audio).expanduser().resolve()
        if not audio.is_file() or audio.stat().st_size <= 0:
            raise CartoonLiveProofError("CARTOON_HAZE_AUDIO_MISSING")

        proof_dir = self.proof_root / proof
        if proof_dir.exists():
            raise CartoonLiveProofError("CARTOON_PROOF_ALREADY_EXISTS")
        proof_dir.mkdir(parents=True, exist_ok=False)

        panels_dir = proof_dir / "storyboard-panels"
        panels_dir.mkdir()
        panels: list[dict[str, Any]] = []
        panel_intents = (
            "Establish character and environment.",
            "Breakdown pose moves character toward frame center.",
            "Extreme pose resolves the one-shot movement.",
        )
        for index in range(1, 4):
            path = panels_dir / f"panel-{index:03d}.ppm"
            _write_storyboard_panel(path, panel_index=index)
            panels.append(
                {
                    "panel_id": f"panel-{index:03d}",
                    "path": str(path),
                    "sha256": _sha256_file(path),
                    "shot_id": "shot-001",
                    "intent": panel_intents[index - 1],
                }
            )

        character_bible = self._artifact_payload(
            proof_dir / "character-bible.json",
            {
                "schema": "CharacterBible/v1",
                "character_id": "proof-character",
                "name": "Proof Character",
                "silhouette": "compact upright geometric cartoon silhouette",
                "proportions": {
                    "head_body_ratio": "fixture:1:3",
                    "relative_width": "narrow",
                },
                "palette": ["#EBEEF5", "#1C2842"],
                "line_character": "clean dark solid stroke",
                "allowed_deformation": "bounded pose translation only",
                "signature_poses": ["left extreme", "center breakdown", "right extreme"],
            },
        )
        style_bible = self._artifact_payload(
            proof_dir / "style-bible.json",
            {
                "schema": "StyleBible/v1",
                "final_video_mode": "ANIMATED_CARTOON",
                "shape_language": "simple geometric fixture",
                "line_language": "clean solid line",
                "palette": ["#1C2842", "#26324C", "#303C56", "#EBEEF5"],
                "value_structure": "light character on dark background",
                "motion_language": "pose-to-pose",
                "camera_language": "locked orthographic proof camera",
                "frame_cadence": "24fps",
                "compositing_treatment": "Blender EEVEE scene composite",
            },
        )
        storyboard = self._artifact_payload(
            proof_dir / "storyboard.json",
            {
                "schema": "Storyboard/v1",
                "storyboard_id": f"{proof}-storyboard",
                "panel_count": 3,
                "panels": panels,
            },
        )

        animatic_path = proof_dir / "animatic.mp4"
        animatic_args = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-v",
            "error",
            "-y",
            "-framerate",
            "1",
            "-start_number",
            "1",
            "-i",
            str(panels_dir / "panel-%03d.ppm"),
            "-stream_loop",
            "-1",
            "-i",
            str(audio),
            "-t",
            "3.0",
            "-r",
            "24",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-color_range",
            "tv",
            str(animatic_path),
        ]
        self._run_media(
            animatic_args,
            output=animatic_path,
            timeout_seconds=120.0,
            code="CARTOON_ANIMATIC_ENCODE_FAILED",
        )
        animatic_qc = self._video_qc(animatic_path)
        animatic = self._artifact_payload(
            proof_dir / "animatic.json",
            {
                "schema": "Animatic/v1",
                "animatic_id": f"{proof}-animatic",
                "video_path": str(animatic_path),
                "video_sha256": _sha256_file(animatic_path),
                "haze_audio_path": str(audio),
                "haze_audio_sha256": _sha256_file(audio),
                "duration_seconds": 3.0,
                "video_qc": animatic_qc,
            },
        )

        shot = self._artifact_payload(
            proof_dir / "animation-shot.json",
            {
                "schema": "AnimationShot/v1",
                "shot_id": "shot-001",
                "scene_id": "scene-001",
                "duration_frames": 24,
                "fps": 24,
                "aspect_ratio": "16:9",
                "shot_scale": "medium full",
                "camera": "locked orthographic",
                "composition": "character traverses left-center-right",
                "characters": ["proof-character"],
                "poses": {
                    "frame_1": "EXTREME",
                    "frame_12": "BREAKDOWN",
                    "frame_24": "EXTREME",
                },
                "audio_ref": str(audio),
                "background": "ProofBackground",
                "animation_technique": "Grease Pencil pose-to-pose",
                "render_dependencies": ["Blender 5.2.2 LTS"],
            },
        )
        exposure_sheet = self._artifact_payload(
            proof_dir / "exposure-sheet.json",
            {
                "schema": "ExposureSheet/v1",
                "shot_id": "shot-001",
                "fps": 24,
                "frame_start": 1,
                "frame_end": 24,
                "exposures": [
                    {"frame": 1, "type": "EXTREME"},
                    {"frame": 12, "type": "BREAKDOWN"},
                    {"frame": 24, "type": "EXTREME"},
                ],
            },
        )

        seed = 424242
        fixture_request = self._request(
            operation="animation.fixture.create",
            task_id=f"{proof}-fixture",
            request_id=f"{proof}-fixture",
            arguments={"fixture_id": proof},
            expected_scene_identity=proof,
            expected_blend_sha256="0" * 64,
            seed=seed,
            timeout_seconds=120.0,
        )
        fixture_result = self._execute_blender(
            fixture_request,
            blend_path=None,
            timeout_seconds=120.0,
        )
        fixture_value = fixture_result.get("fixture_path")
        snapshot_value = fixture_result.get("snapshot")
        if not isinstance(fixture_value, str) or not isinstance(snapshot_value, Mapping):
            raise CartoonLiveProofError("CARTOON_FIXTURE_RESULT_MALFORMED")
        fixture = Path(fixture_value).expanduser().resolve()
        expected_fixture_root = (self.blender_root / "fixtures").resolve()
        try:
            fixture.relative_to(expected_fixture_root)
        except ValueError as exc:
            raise CartoonLiveProofError("CARTOON_FIXTURE_OUTSIDE_ROOT") from exc
        if not fixture.is_file() or fixture.stat().st_size <= 0:
            raise CartoonLiveProofError("CARTOON_FIXTURE_MISSING")
        try:
            fixture_snapshot = BlenderSceneSnapshot.from_dict(snapshot_value)
        except BlenderBridgeError as exc:
            raise CartoonLiveProofError("CARTOON_FIXTURE_SNAPSHOT_MALFORMED") from exc
        if fixture_snapshot.scene_identity != proof:
            raise CartoonLiveProofError("CARTOON_FIXTURE_IDENTITY_MISMATCH")

        shot_request = self._request(
            operation="animation.shot.build",
            task_id=f"{proof}-shot",
            request_id=f"{proof}-shot",
            arguments={
                "shot_id": "shot-001",
                "frame_start": 1,
                "breakdown_frame": 12,
                "frame_end": 24,
                "character_name": "ProofCharacter",
                "background_name": "ProofBackground",
            },
            expected_scene_identity=proof,
            expected_blend_sha256=fixture_snapshot.blend_sha256,
            seed=seed,
            timeout_seconds=180.0,
        )
        shot_result = self._execute_blender(
            shot_request,
            blend_path=fixture,
            timeout_seconds=180.0,
        )
        shot_snapshot_value = shot_result.get("snapshot")
        if not isinstance(shot_snapshot_value, Mapping):
            raise CartoonLiveProofError("CARTOON_SHOT_SNAPSHOT_MALFORMED")
        try:
            shot_snapshot = BlenderSceneSnapshot.from_dict(shot_snapshot_value)
        except BlenderBridgeError as exc:
            raise CartoonLiveProofError("CARTOON_SHOT_SNAPSHOT_MALFORMED") from exc
        if "ProofCharacter" not in shot_snapshot.grease_pencil_objects:
            raise CartoonLiveProofError("CARTOON_GREASE_PENCIL_OBJECT_MISSING")
        if "HazewaveCamera" not in shot_snapshot.cameras:
            raise CartoonLiveProofError("CARTOON_CAMERA_MISSING")

        render_id = f"{proof}-shot-001-v1"
        render_request = self._request(
            operation="animation.render.frames",
            task_id=f"{proof}-render",
            request_id=f"{proof}-render",
            arguments={
                "render_id": render_id,
                "frame_start": 1,
                "frame_end": 24,
                "format": "PNG",
            },
            expected_scene_identity=proof,
            expected_blend_sha256=shot_snapshot.blend_sha256,
            seed=seed,
            timeout_seconds=900.0,
        )
        render_result = self._execute_blender(
            render_request,
            blend_path=fixture,
            timeout_seconds=900.0,
        )
        frames_value = render_result.get("frames")
        if not isinstance(frames_value, (list, tuple)) or len(frames_value) != 24:
            raise CartoonLiveProofError("CARTOON_FRAME_RESULT_MALFORMED")
        first_path_value = frames_value[0].get("path") if isinstance(frames_value[0], Mapping) else None
        if not isinstance(first_path_value, str):
            raise CartoonLiveProofError("CARTOON_FRAME_RESULT_MALFORMED")
        frame_dir = Path(first_path_value).expanduser().resolve().parent
        expected_frame_root = (self.blender_root / "frames" / render_id).resolve()
        if frame_dir != expected_frame_root:
            raise CartoonLiveProofError("CARTOON_FRAME_ROOT_MISMATCH")

        try:
            animation_qc_before = analyze_animation_sequence(
                frame_dir,
                expected_frame_start=1,
                expected_frame_end=24,
            )
        except AnimationQCError as exc:
            raise CartoonLiveProofError(
                f"CARTOON_ANIMATION_QC_FAILED:{exc}"
            ) from exc

        repair_request = self._request(
            operation="animation.render.frames.repair",
            task_id=f"{proof}-repair",
            request_id=f"{proof}-repair",
            arguments={
                "render_id": render_id,
                "frame_numbers": [12, 13],
                "format": "PNG",
            },
            expected_scene_identity=proof,
            expected_blend_sha256=shot_snapshot.blend_sha256,
            seed=seed,
            timeout_seconds=300.0,
        )
        repair_result = self._execute_blender(
            repair_request,
            blend_path=fixture,
            timeout_seconds=300.0,
        )
        repaired_value = repair_result.get("repaired_frames")
        if not isinstance(repaired_value, (list, tuple)) or len(repaired_value) != 2:
            raise CartoonLiveProofError("CARTOON_REPAIR_RESULT_MALFORMED")
        for item in repaired_value:
            if (
                not isinstance(item, Mapping)
                or item.get("deterministic_match") is not True
                or item.get("previous_sha256") != item.get("new_sha256")
            ):
                raise CartoonLiveProofError("CARTOON_REPAIR_NONDETERMINISTIC")

        try:
            animation_qc_after = analyze_animation_sequence(
                frame_dir,
                expected_frame_start=1,
                expected_frame_end=24,
            )
        except AnimationQCError as exc:
            raise CartoonLiveProofError(
                f"CARTOON_ANIMATION_QC_FAILED:{exc}"
            ) from exc
        if (
            animation_qc_before.sequence_sha256
            != animation_qc_after.sequence_sha256
        ):
            raise CartoonLiveProofError("CARTOON_REPAIR_SEQUENCE_CHANGED")

        final_video_path = proof_dir / "cartoon-proof.mp4"
        final_args = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-v",
            "error",
            "-y",
            "-framerate",
            "24",
            "-start_number",
            "1",
            "-i",
            str(frame_dir / "frame-%04d.png"),
            "-stream_loop",
            "-1",
            "-i",
            str(audio),
            "-t",
            "1.0",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-color_range",
            "tv",
            str(final_video_path),
        ]
        self._run_media(
            final_args,
            output=final_video_path,
            timeout_seconds=300.0,
            code="CARTOON_FINAL_ENCODE_FAILED",
        )
        video_qc = self._video_qc(final_video_path)

        result: dict[str, Any] = {
            "schema": "CartoonLiveProof/v1",
            "status": "PASS",
            "authority": "HAZEWAVE_HARNESS",
            "portfolio_authority": "NONE",
            "candidate_head": self.candidate_head,
            "policy_digest": self.policy_digest,
            "runtime_identity": self.runtime_identity,
            "blender_version": BLENDER_EXPECTED_VERSION,
            "final_video_mode": "ANIMATED_CARTOON",
            "proof_id": proof,
            "character_bible": character_bible,
            "style_bible": style_bible,
            "storyboard": storyboard,
            "animatic": animatic,
            "shot": shot,
            "exposure_sheet": exposure_sheet,
            "blender_fixture": {
                "path": str(fixture),
                "sha256": shot_snapshot.blend_sha256,
            },
            "frame_sequence": {
                "render_id": render_id,
                "root": str(frame_dir),
                "frame_start": 1,
                "frame_end": 24,
                "frame_count": 24,
            },
            "animation_qc": animation_qc_after.to_dict(),
            "repair": {
                "frame_numbers": [12, 13],
                "deterministic_match": True,
                "sequence_sha256_before": animation_qc_before.sequence_sha256,
                "sequence_sha256_after": animation_qc_after.sequence_sha256,
                "receipts": [dict(item) for item in repaired_value],
            },
            "final_video": {
                "path": str(final_video_path),
                "sha256": _sha256_file(final_video_path),
            },
            "video_qc": video_qc,
            "provenance": {
                "haze_audio_path": str(audio),
                "haze_audio_sha256": _sha256_file(audio),
                "seed": seed,
                "blender_operations": [
                    "animation.fixture.create",
                    "animation.shot.build",
                    "animation.render.frames",
                    "animation.render.frames.repair",
                ],
            },
            "human_owner_review": "REQUIRED",
        }
        proof_path = proof_dir / "cartoon-live-proof.json"
        result["proof_path"] = str(proof_path)
        _atomic_write_json(proof_path, result)
        return result
