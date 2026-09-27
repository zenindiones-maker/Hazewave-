from pathlib import Path

import pytest

from hazewave import separation


def test_find_single_stem(tmp_path: Path) -> None:
    stem = tmp_path / "htdemucs" / "track" / "no_vocals.wav"
    stem.parent.mkdir(parents=True)
    stem.write_bytes(b"audio")

    assert separation._find_single_stem(tmp_path, "no_vocals.wav") == stem


def test_find_single_stem_fails_closed_when_missing(tmp_path: Path) -> None:
    with pytest.raises(separation.SeparationError, match="found 0"):
        separation._find_single_stem(tmp_path, "vocals.wav")


def test_separate_track_exports_instrumental_and_vocals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "song.mp3"
    source.write_bytes(b"input")

    monkeypatch.setattr(separation, "_check_runtime", lambda: None)

    def fake_run_demucs(source_path: Path, work_dir: Path, model: str) -> None:
        stem_dir = work_dir / model / source_path.stem
        stem_dir.mkdir(parents=True)
        (stem_dir / "vocals.wav").write_bytes(b"vocals")
        (stem_dir / "no_vocals.wav").write_bytes(b"instrumental")

    monkeypatch.setattr(separation, "_run_demucs", fake_run_demucs)

    result = separation.separate_track(
        source,
        output_dir=tmp_path / "out",
        model="htdemucs",
        output_format="wav",
    )

    assert result.instrumental.read_bytes() == b"instrumental"
    assert result.vocals is not None
    assert result.vocals.read_bytes() == b"vocals"


def test_instrumental_only_does_not_export_vocals(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "song.mp3"
    source.write_bytes(b"input")

    monkeypatch.setattr(separation, "_check_runtime", lambda: None)

    def fake_run_demucs(source_path: Path, work_dir: Path, model: str) -> None:
        stem_dir = work_dir / model / source_path.stem
        stem_dir.mkdir(parents=True)
        (stem_dir / "vocals.wav").write_bytes(b"vocals")
        (stem_dir / "no_vocals.wav").write_bytes(b"instrumental")

    monkeypatch.setattr(separation, "_run_demucs", fake_run_demucs)

    result = separation.separate_track(
        source,
        output_dir=tmp_path / "out",
        instrumental_only=True,
    )

    assert result.instrumental.exists()
    assert result.vocals is None
