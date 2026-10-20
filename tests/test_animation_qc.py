from __future__ import annotations

import struct
from pathlib import Path

import pytest

from hazewave.animation_qc import (
    AnimationQCError,
    analyze_animation_sequence,
)


def _png(width: int, height: int, *, color_type: int = 6, marker: bytes = b"") -> bytes:
    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(
        ">IIBBBBB",
        width,
        height,
        8,
        color_type,
        0,
        0,
        0,
    )
    return signature + struct.pack(">I", len(ihdr)) + b"IHDR" + ihdr + b"\x00\x00\x00\x00" + marker


def test_animation_qc_validates_contiguous_png_sequence(tmp_path: Path) -> None:
    root = tmp_path / "frames"
    root.mkdir()
    for number in range(1, 5):
        (root / f"frame-{number:04d}.png").write_bytes(
            _png(1920, 1080, marker=str(number).encode())
        )

    report = analyze_animation_sequence(
        root,
        expected_frame_start=1,
        expected_frame_end=4,
    )

    assert report.schema == "AnimationQCReport/v1"
    assert report.frame_start == 1
    assert report.frame_end == 4
    assert report.frame_count == 4
    assert report.width == 1920
    assert report.height == 1080
    assert report.bit_depth == 8
    assert report.alpha_channel_present is True
    assert report.missing_frames == ()
    assert report.empty_frames == ()
    assert len(report.sequence_sha256) == 64
    assert all(len(item.sha256) == 64 for item in report.frames)
    assert report.technical_status == "PASS"
    assert report.creative_verdict == "HUMAN_REVIEW_REQUIRED"


def test_animation_qc_fails_closed_on_missing_frame(tmp_path: Path) -> None:
    root = tmp_path / "frames"
    root.mkdir()
    (root / "frame-0001.png").write_bytes(_png(640, 360))
    (root / "frame-0003.png").write_bytes(_png(640, 360))

    with pytest.raises(AnimationQCError, match="ANIMATION_QC_FRAME_SEQUENCE_GAP"):
        analyze_animation_sequence(
            root,
            expected_frame_start=1,
            expected_frame_end=3,
        )


def test_animation_qc_fails_closed_on_resolution_drift(tmp_path: Path) -> None:
    root = tmp_path / "frames"
    root.mkdir()
    (root / "frame-0001.png").write_bytes(_png(640, 360))
    (root / "frame-0002.png").write_bytes(_png(1280, 720))

    with pytest.raises(AnimationQCError, match="ANIMATION_QC_RESOLUTION_DRIFT"):
        analyze_animation_sequence(
            root,
            expected_frame_start=1,
            expected_frame_end=2,
        )


def test_animation_qc_fails_closed_on_non_png_bytes(tmp_path: Path) -> None:
    root = tmp_path / "frames"
    root.mkdir()
    (root / "frame-0001.png").write_bytes(b"not-a-png")

    with pytest.raises(AnimationQCError, match="ANIMATION_QC_PNG_INVALID"):
        analyze_animation_sequence(
            root,
            expected_frame_start=1,
            expected_frame_end=1,
        )


def test_animation_qc_reports_alpha_consistently(tmp_path: Path) -> None:
    root = tmp_path / "frames"
    root.mkdir()
    (root / "frame-0001.png").write_bytes(_png(640, 360, color_type=2))
    (root / "frame-0002.png").write_bytes(_png(640, 360, color_type=2))

    report = analyze_animation_sequence(
        root,
        expected_frame_start=1,
        expected_frame_end=2,
    )

    assert report.alpha_channel_present is False


def test_animation_qc_rejects_mixed_alpha_mode(tmp_path: Path) -> None:
    root = tmp_path / "frames"
    root.mkdir()
    (root / "frame-0001.png").write_bytes(_png(640, 360, color_type=6))
    (root / "frame-0002.png").write_bytes(_png(640, 360, color_type=2))

    with pytest.raises(AnimationQCError, match="ANIMATION_QC_ALPHA_MODE_DRIFT"):
        analyze_animation_sequence(
            root,
            expected_frame_start=1,
            expected_frame_end=2,
        )
