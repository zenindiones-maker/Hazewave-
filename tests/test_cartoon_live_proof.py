from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import struct
import subprocess

import pytest

from hazewave.cartoon_live_proof import (
    CartoonLiveProofError,
    CartoonLiveProofRunner,
)


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _png(width: int, height: int, marker: bytes) -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (
        signature
        + struct.pack(">I", len(ihdr))
        + b"IHDR"
        + ihdr
        + b"\x00\x00\x00\x00"
        + marker
    )


def _snapshot(path: Path, digest: str) -> dict:
    return {
        "schema": "BlenderSceneSnapshot/v1",
        "blender_version": "5.2.2",
        "blend_path": str(path),
        "blend_sha256": digest,
        "scene_identity": "cartoon-proof-001",
        "frame_start": 1,
        "frame_end": 24,
        "fps": 24.0,
        "resolution_x": 1920,
        "resolution_y": 1080,
        "resolution_percentage": 100,
        "render_engine": "BLENDER_EEVEE_NEXT",
        "view_transform": "AgX",
        "look": "Medium High Contrast",
        "display_device": "sRGB",
        "objects": [],
        "grease_pencil_objects": [],
        "cameras": [],
        "dependencies": [],
    }


class FakeBlenderExecutor:
    def __init__(self, root: Path, *, repair_matches: bool = True) -> None:
        self.root = root
        self.repair_matches = repair_matches
        self.operations: list[str] = []

    def execute(
        self,
        request,
        *,
        blend_path=None,
        timeout_seconds=300.0,
        runner=None,
    ):
        self.operations.append(request.operation)
        operation = request.operation

        if operation == "animation.fixture.create":
            fixture = self.root / "fixtures" / "cartoon-proof-001.blend"
            fixture.parent.mkdir(parents=True, exist_ok=True)
            fixture.write_bytes(b"fixture")
            digest = _sha(fixture)
            snapshot = _snapshot(fixture, digest)
            return {
                "status": "PASS",
                "result": {
                    "fixture_path": str(fixture),
                    "snapshot": snapshot,
                },
            }

        assert blend_path is not None
        blend = Path(blend_path)

        if operation == "animation.shot.build":
            blend.write_bytes(b"shot-built")
            digest = _sha(blend)
            snapshot = _snapshot(blend, digest)
            snapshot["grease_pencil_objects"] = ["ProofCharacter"]
            snapshot["cameras"] = ["HazewaveCamera"]
            return {
                "status": "PASS",
                "result": {
                    "shot_id": "shot-001",
                    "character_object": "ProofCharacter",
                    "background_object": "ProofBackground",
                    "camera_object": "HazewaveCamera",
                    "keyframes": [1, 12, 24],
                    "keyframe_types": ["EXTREME", "BREAKDOWN", "EXTREME"],
                    "snapshot": snapshot,
                },
            }

        if operation == "animation.render.frames":
            render_id = request.arguments["render_id"]
            root = self.root / "frames" / render_id
            root.mkdir(parents=True, exist_ok=False)
            frames = []
            for number in range(
                request.arguments["frame_start"],
                request.arguments["frame_end"] + 1,
            ):
                path = root / f"frame-{number:04d}.png"
                path.write_bytes(
                    _png(1920, 1080, marker=str(number).encode("ascii"))
                )
                frames.append(
                    {
                        "frame_number": number,
                        "path": str(path),
                        "sha256": _sha(path),
                        "size_bytes": path.stat().st_size,
                    }
                )
            return {
                "status": "PASS",
                "result": {
                    "render_id": render_id,
                    "format": "PNG",
                    "frame_start": request.arguments["frame_start"],
                    "frame_end": request.arguments["frame_end"],
                    "frame_count": len(frames),
                    "frames": frames,
                },
            }

        if operation == "animation.render.frames.repair":
            root = self.root / "frames" / request.arguments["render_id"]
            repaired = []
            for number in request.arguments["frame_numbers"]:
                path = root / f"frame-{number:04d}.png"
                previous = _sha(path)
                new = previous if self.repair_matches else "0" * 64
                repaired.append(
                    {
                        "frame_number": number,
                        "path": str(path),
                        "previous_sha256": previous,
                        "new_sha256": new,
                        "deterministic_match": self.repair_matches,
                    }
                )
            return {
                "status": "PASS",
                "result": {
                    "render_id": request.arguments["render_id"],
                    "format": "PNG",
                    "frame_numbers": request.arguments["frame_numbers"],
                    "repaired_frames": repaired,
                },
            }

        raise AssertionError(operation)


@dataclass
class FakeVideoQC:
    output_path: str

    def to_dict(self) -> dict:
        return {
            "schema": "VideoQCReport/v1",
            "output_path": self.output_path,
            "output_sha256": "a" * 64,
            "encode_integrity": "PASS",
            "technical_flags": [],
            "artistic_verdict": "NOT_ASSIGNED",
        }


def _media_runner(args: list[str], timeout_seconds: float):
    output = Path(args[-1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"encoded-media")
    return subprocess.CompletedProcess(args, 0, stdout="", stderr="")


def test_cartoon_live_proof_materializes_professional_fixture_and_closed_loop(
    tmp_path: Path,
) -> None:
    blender_root = tmp_path / "blender"
    proof_root = tmp_path / "proofs"
    audio = tmp_path / "haze.wav"
    audio.write_bytes(b"RIFF-haze-audio")
    executor = FakeBlenderExecutor(blender_root)

    runner = CartoonLiveProofRunner(
        blender_executor=executor,
        blender_root=blender_root,
        proof_root=proof_root,
        candidate_head="candidate-sha",
        policy_digest="policy-sha",
        runtime_identity="codespace:fixture",
        media_runner=_media_runner,
        video_qc_analyzer=lambda path: FakeVideoQC(str(path)),
    )

    result = runner.run(
        proof_id="cartoon-proof-001",
        haze_audio=audio,
    )

    assert result["schema"] == "CartoonLiveProof/v1"
    assert result["status"] == "PASS"
    assert result["authority"] == "HAZEWAVE_HARNESS"
    assert result["portfolio_authority"] == "NONE"
    assert result["final_video_mode"] == "ANIMATED_CARTOON"
    assert result["character_bible"]["schema"] == "CharacterBible/v1"
    assert result["style_bible"]["schema"] == "StyleBible/v1"
    assert result["storyboard"]["schema"] == "Storyboard/v1"
    assert len(result["storyboard"]["panels"]) == 3
    assert result["animatic"]["schema"] == "Animatic/v1"
    assert result["shot"]["schema"] == "AnimationShot/v1"
    assert result["exposure_sheet"]["schema"] == "ExposureSheet/v1"
    assert result["animation_qc"]["schema"] == "AnimationQCReport/v1"
    assert result["animation_qc"]["technical_status"] == "PASS"
    assert result["repair"]["deterministic_match"] is True
    assert result["video_qc"]["schema"] == "VideoQCReport/v1"
    assert result["video_qc"]["encode_integrity"] == "PASS"
    assert result["human_owner_review"] == "REQUIRED"
    assert Path(result["final_video"]["path"]).is_file()
    assert Path(result["proof_path"]).is_file()

    assert executor.operations == [
        "animation.fixture.create",
        "animation.shot.build",
        "animation.render.frames",
        "animation.render.frames.repair",
    ]


def test_cartoon_live_proof_rejects_nondeterministic_subset_rerender(
    tmp_path: Path,
) -> None:
    blender_root = tmp_path / "blender"
    audio = tmp_path / "haze.wav"
    audio.write_bytes(b"RIFF-haze")
    executor = FakeBlenderExecutor(blender_root, repair_matches=False)
    runner = CartoonLiveProofRunner(
        blender_executor=executor,
        blender_root=blender_root,
        proof_root=tmp_path / "proofs",
        candidate_head="candidate-sha",
        policy_digest="policy-sha",
        runtime_identity="codespace:fixture",
        media_runner=_media_runner,
        video_qc_analyzer=lambda path: FakeVideoQC(str(path)),
    )

    with pytest.raises(
        CartoonLiveProofError,
        match="CARTOON_REPAIR_NONDETERMINISTIC",
    ):
        runner.run(
            proof_id="cartoon-proof-001",
            haze_audio=audio,
        )


def test_cartoon_live_proof_requires_existing_haze_audio_before_blender(
    tmp_path: Path,
) -> None:
    executor = FakeBlenderExecutor(tmp_path / "blender")
    runner = CartoonLiveProofRunner(
        blender_executor=executor,
        blender_root=tmp_path / "blender",
        proof_root=tmp_path / "proofs",
        candidate_head="candidate-sha",
        policy_digest="policy-sha",
        runtime_identity="codespace:fixture",
        media_runner=_media_runner,
        video_qc_analyzer=lambda path: FakeVideoQC(str(path)),
    )

    with pytest.raises(CartoonLiveProofError, match="CARTOON_HAZE_AUDIO_MISSING"):
        runner.run(
            proof_id="cartoon-proof-001",
            haze_audio=tmp_path / "missing.wav",
        )

    assert executor.operations == []


def test_cartoon_live_proof_refuses_existing_proof_directory(tmp_path: Path) -> None:
    proof_root = tmp_path / "proofs"
    (proof_root / "cartoon-proof-001").mkdir(parents=True)
    audio = tmp_path / "haze.wav"
    audio.write_bytes(b"RIFF-haze")
    executor = FakeBlenderExecutor(tmp_path / "blender")
    runner = CartoonLiveProofRunner(
        blender_executor=executor,
        blender_root=tmp_path / "blender",
        proof_root=proof_root,
        candidate_head="candidate-sha",
        policy_digest="policy-sha",
        runtime_identity="codespace:fixture",
        media_runner=_media_runner,
        video_qc_analyzer=lambda path: FakeVideoQC(str(path)),
    )

    with pytest.raises(CartoonLiveProofError, match="CARTOON_PROOF_ALREADY_EXISTS"):
        runner.run(
            proof_id="cartoon-proof-001",
            haze_audio=audio,
        )
