from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hazewave.wave_editorial import (
    AudioStream,
    ColorMetadata,
    MediaManifest,
    RationalRate,
    VideoStream,
    WaveEditorialTimeline,
)
from hazewave.wave_render import WaveRenderError, render_wave_timeline


def _manifest(source: Path, *, ambiguous_color: bool = False) -> MediaManifest:
    color = ColorMetadata(
        primaries="unknown" if ambiguous_color else "bt709",
        transfer="unknown" if ambiguous_color else "bt709",
        matrix="bt709",
        range="tv",
        bit_depth=8,
    )
    return MediaManifest(
        source_path=str(source.resolve()),
        source_sha256="a" * 64,
        container_format="mov,mp4,m4a,3gp,3g2,mj2",
        duration_seconds=10.0,
        start_time_seconds=0.0,
        bit_rate=1_000_000,
        video_stream=VideoStream(
            index=0,
            codec_name="h264",
            width=1920,
            height=1080,
            pixel_format="yuv420p",
            frame_rate=RationalRate(30000, 1001),
            duration_seconds=10.0,
            color=color,
        ),
        audio_streams=(
            AudioStream(
                index=1,
                codec_name="aac",
                sample_rate=48000,
                channels=2,
                channel_layout="stereo",
                duration_seconds=10.0,
            ),
        ),
    )


def _qc_payload() -> dict:
    return {
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": "7.000000",
        },
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "avg_frame_rate": "30000/1001",
                "color_range": "tv",
                "color_space": "bt709",
                "color_transfer": "bt709",
                "color_primaries": "bt709",
                "bits_per_raw_sample": "8",
                "duration": "7.000000",
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
                "channel_layout": "stereo",
                "duration": "7.000000",
            },
        ],
    }


def test_wave_render_conforms_cut_timeline_and_runs_video_qc(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source-video")
    manifest = _manifest(source)
    timeline = WaveEditorialTimeline.create(
        timeline_id="wave-001",
        name="Fixture",
        manifest=manifest,
    )
    timeline = timeline.cut_clip(
        track_index=0,
        clip_index=0,
        timeline_seconds=3.0,
        expected_revision=0,
    )
    timeline = timeline.trim_clip(
        track_index=0,
        clip_index=1,
        new_in_seconds=5.0,
        new_out_seconds=9.0,
        expected_revision=1,
    )

    calls: list[list[str]] = []

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        if args[0] == "ffmpeg":
            output = Path(args[-1])
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"encoded-output")
            return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
        if args[0] == "ffprobe":
            return subprocess.CompletedProcess(
                args, 0, stdout=json.dumps(_qc_payload()), stderr=""
            )
        raise AssertionError(args)

    receipt = render_wave_timeline(
        timeline,
        manifests={manifest.source_sha256: manifest},
        output_root=tmp_path / "render-root",
        render_id="render-001",
        expected_revision=2,
        runner=runner,
    )

    assert receipt.schema == "WaveRenderReceipt/v1"
    assert receipt.timeline_id == "wave-001"
    assert receipt.timeline_revision == 2
    assert receipt.output_path.startswith(str((tmp_path / "render-root").resolve()))
    assert Path(receipt.output_path).is_file()
    assert len(receipt.output_sha256) == 64
    assert receipt.video_qc["schema"] == "VideoQCReport/v1"
    assert receipt.video_qc["encode_integrity"] == "PASS"
    assert receipt.artistic_verdict == "NOT_ASSIGNED"

    ffmpeg = calls[0]
    assert ffmpeg[0] == "ffmpeg"
    assert "-filter_complex" in ffmpeg
    graph = ffmpeg[ffmpeg.index("-filter_complex") + 1]
    assert "trim=start=0.000000:duration=3.000000" in graph
    assert "trim=start=5.000000:duration=4.000000" in graph
    assert "atrim=start=0.000000:duration=3.000000" in graph
    assert "atrim=start=5.000000:duration=4.000000" in graph
    assert "concat=n=2:v=1:a=1" in graph
    assert "-color_primaries" in ffmpeg
    assert "bt709" in ffmpeg
    assert calls[1][0] == "ffprobe"


def test_wave_render_fails_closed_on_stale_timeline_revision(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    manifest = _manifest(source)
    timeline = WaveEditorialTimeline.create(
        timeline_id="wave-001",
        name="Fixture",
        manifest=manifest,
    )

    with pytest.raises(WaveRenderError, match="WAVE_RENDER_TIMELINE_STALE"):
        render_wave_timeline(
            timeline,
            manifests={manifest.source_sha256: manifest},
            output_root=tmp_path / "render-root",
            render_id="render-001",
            expected_revision=99,
            runner=lambda args: (_ for _ in ()).throw(AssertionError(args)),
        )


def test_wave_render_fails_closed_on_ambiguous_color_metadata(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    manifest = _manifest(source, ambiguous_color=True)
    timeline = WaveEditorialTimeline.create(
        timeline_id="wave-001",
        name="Fixture",
        manifest=manifest,
    )

    with pytest.raises(WaveRenderError, match="WAVE_RENDER_COLOR_METADATA_AMBIGUOUS"):
        render_wave_timeline(
            timeline,
            manifests={manifest.source_sha256: manifest},
            output_root=tmp_path / "render-root",
            render_id="render-001",
            expected_revision=0,
            runner=lambda args: (_ for _ in ()).throw(AssertionError(args)),
        )


def test_wave_render_rejects_caller_path_traversal_in_render_id(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    manifest = _manifest(source)
    timeline = WaveEditorialTimeline.create(
        timeline_id="wave-001",
        name="Fixture",
        manifest=manifest,
    )

    with pytest.raises(WaveRenderError, match="WAVE_RENDER_ID_INVALID"):
        render_wave_timeline(
            timeline,
            manifests={manifest.source_sha256: manifest},
            output_root=tmp_path / "render-root",
            render_id="../escape",
            expected_revision=0,
            runner=lambda args: (_ for _ in ()).throw(AssertionError(args)),
        )


def test_wave_render_requires_manifest_hash_match(tmp_path: Path) -> None:
    source = tmp_path / "source.mp4"
    source.write_bytes(b"source")
    manifest = _manifest(source)
    timeline = WaveEditorialTimeline.create(
        timeline_id="wave-001",
        name="Fixture",
        manifest=manifest,
    )

    with pytest.raises(WaveRenderError, match="WAVE_RENDER_MANIFEST_NOT_BOUND"):
        render_wave_timeline(
            timeline,
            manifests={},
            output_root=tmp_path / "render-root",
            render_id="render-001",
            expected_revision=0,
            runner=lambda args: (_ for _ in ()).throw(AssertionError(args)),
        )
