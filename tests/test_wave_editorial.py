from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from hazewave.wave_editorial import (
    ANIMATED_CARTOON,
    ColorMetadata,
    WaveEditorialError,
    WaveEditorialTimeline,
    inspect_media,
)


def _probe_payload() -> dict:
    return {
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": "10.000000",
            "start_time": "0.000000",
            "bit_rate": "2400000",
        },
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "pix_fmt": "yuv420p",
                "r_frame_rate": "30000/1001",
                "avg_frame_rate": "30000/1001",
                "color_range": "tv",
                "color_space": "bt709",
                "color_transfer": "bt709",
                "color_primaries": "bt709",
                "bits_per_raw_sample": "8",
                "duration": "10.000000",
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "48000",
                "channels": 2,
                "channel_layout": "stereo",
                "duration": "10.000000",
            },
        ],
    }


def test_media_inspect_builds_machine_readable_manifest_without_embedding_media(
    tmp_path: Path,
) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video-fixture")

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        assert args[0] == "ffprobe"
        assert "-of" in args
        assert "json" in args
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps(_probe_payload()),
            stderr="",
        )

    manifest = inspect_media(source, runner=runner)

    assert manifest.schema == "MediaManifest/v1"
    assert manifest.source_path == str(source.resolve())
    assert len(manifest.source_sha256) == 64
    assert manifest.private_media_policy == "LOCAL_BY_DEFAULT"
    assert manifest.duration_seconds == pytest.approx(10.0)
    assert manifest.video_stream.codec_name == "h264"
    assert manifest.video_stream.width == 1920
    assert manifest.video_stream.height == 1080
    assert manifest.video_stream.frame_rate.numerator == 30000
    assert manifest.video_stream.frame_rate.denominator == 1001
    assert manifest.video_stream.color.primaries == "bt709"
    assert manifest.video_stream.color.transfer == "bt709"
    assert manifest.video_stream.color.matrix == "bt709"
    assert manifest.video_stream.color.range == "tv"
    assert manifest.video_stream.color.bit_depth == 8
    assert manifest.audio_streams[0].sample_rate == 48000
    assert "media_bytes" not in manifest.to_dict()


def test_media_inspect_fails_closed_on_missing_video_for_wave_video_ingest(
    tmp_path: Path,
) -> None:
    source = tmp_path / "audio-only.m4a"
    source.write_bytes(b"audio")

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        payload = _probe_payload()
        payload["streams"] = [payload["streams"][1]]
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(payload), stderr="")

    with pytest.raises(WaveEditorialError, match="WAVE_VIDEO_STREAM_REQUIRED"):
        inspect_media(source, runner=runner)


def test_color_transform_requires_explicit_consequential_metadata() -> None:
    ambiguous = ColorMetadata(
        primaries="unknown",
        transfer="unknown",
        matrix="unknown",
        range="unknown",
        bit_depth=10,
    )

    with pytest.raises(WaveEditorialError, match="WAVE_COLOR_METADATA_AMBIGUOUS"):
        ambiguous.require_managed_transform()


def test_timeline_contract_is_cartoon_first_and_references_external_media(
    tmp_path: Path,
) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video-fixture")

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args, 0, stdout=json.dumps(_probe_payload()), stderr=""
        )

    manifest = inspect_media(source, runner=runner)
    timeline = WaveEditorialTimeline.create(
        timeline_id="timeline-001",
        name="Cartoon Proof",
        manifest=manifest,
    )

    payload = timeline.to_dict()

    assert payload["schema"] == "WaveEditorialTimeline/v1"
    assert payload["final_video_mode"] == ANIMATED_CARTOON
    assert payload["revision"] == 0
    assert payload["tracks"][0]["kind"] == "VIDEO"
    assert payload["tracks"][0]["clips"][0]["media_reference"]["source_path"] == str(source.resolve())
    assert "media_bytes" not in json.dumps(payload)
    assert payload["otio_compatibility"]["concepts"] == [
        "Timeline",
        "Track",
        "Clip",
        "ExternalReference",
        "TimeRange",
        "Marker",
        "Transition",
    ]
    assert payload["otio_compatibility"]["runtime_adapter"] == "NOT_PROVEN"


def test_cut_is_revision_bound_and_does_not_silently_overwrite_stale_plan(
    tmp_path: Path,
) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video-fixture")

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args, 0, stdout=json.dumps(_probe_payload()), stderr=""
        )

    timeline = WaveEditorialTimeline.create(
        timeline_id="timeline-cut",
        name="Cut",
        manifest=inspect_media(source, runner=runner),
    )

    cut = timeline.cut_clip(
        track_index=0,
        clip_index=0,
        timeline_seconds=4.0,
        expected_revision=0,
    )

    assert cut.revision == 1
    assert len(cut.tracks[0].clips) == 2
    assert cut.tracks[0].clips[0].duration_seconds == pytest.approx(4.0)
    assert cut.tracks[0].clips[1].duration_seconds == pytest.approx(6.0)

    with pytest.raises(WaveEditorialError, match="WAVE_TIMELINE_STALE"):
        cut.trim_clip(
            track_index=0,
            clip_index=1,
            new_in_seconds=0.5,
            new_out_seconds=5.0,
            expected_revision=0,
        )


def test_trim_and_marker_are_deterministic_and_increment_revision(
    tmp_path: Path,
) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video-fixture")

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args, 0, stdout=json.dumps(_probe_payload()), stderr=""
        )

    timeline = WaveEditorialTimeline.create(
        timeline_id="timeline-trim",
        name="Trim",
        manifest=inspect_media(source, runner=runner),
    )
    trimmed = timeline.trim_clip(
        track_index=0,
        clip_index=0,
        new_in_seconds=1.0,
        new_out_seconds=8.5,
        expected_revision=0,
    )
    marked = trimmed.add_marker(
        name="Beat Drop",
        timeline_seconds=2.25,
        expected_revision=1,
    )

    assert trimmed.revision == 1
    assert trimmed.tracks[0].clips[0].source_in_seconds == pytest.approx(1.0)
    assert trimmed.tracks[0].clips[0].duration_seconds == pytest.approx(7.5)
    assert marked.revision == 2
    assert marked.markers[0].name == "Beat Drop"
    assert marked.markers[0].timeline_seconds == pytest.approx(2.25)


def test_timeline_rejects_non_cartoon_mode_without_owner_override(
    tmp_path: Path,
) -> None:
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"video-fixture")

    def runner(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args, 0, stdout=json.dumps(_probe_payload()), stderr=""
        )

    manifest = inspect_media(source, runner=runner)

    with pytest.raises(WaveEditorialError, match="WAVE_FINAL_VIDEO_MODE_POLICY"):
        WaveEditorialTimeline.create(
            timeline_id="timeline-photoreal",
            name="Wrong Mode",
            manifest=manifest,
            final_video_mode="PHOTOREAL",
        )
