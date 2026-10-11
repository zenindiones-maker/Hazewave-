"""TDD contracts for the Hazewave-native sample-note mapper.

All fixtures are original generated PCM signals, not third-party media.
"""
from __future__ import annotations

from array import array
import hashlib
import json
import math
import struct
import wave

import pytest

from hazewave.harness import HazewaveTask, harness_status, issue_authorization, route_task
from hazewave.sample_note_map import analyze_sample, transcribe_to_midi


def tone_wav(path, notes=(440.0,), seconds=0.6, rate=16000, amplitude=0.27):
    count = round(seconds * rate)
    samples = array("h")
    for i in range(count):
        sample = sum(
            amplitude * math.sin(2.0 * math.pi * note * i / rate) for note in notes
        )
        samples.append(int(max(-0.999, min(0.999, sample)) * 32767))
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(samples.tobytes())
    return path


def authorize(capability="audio.sample_to_midi", domain="HAZE", task_id="note-map-tests"):
    return issue_authorization(route_task(HazewaveTask(
        task_id=task_id, goal="Map public synthetic test audio to editable MIDI",
        required_capability=capability, requested_domain=domain,
    )))


def test_haze_only_capability_is_registered():
    assert "audio.sample_to_midi" in harness_status()["capabilities"]
    authorize()
    with pytest.raises(PermissionError, match="DOMAIN_CAPABILITY_MISMATCH"):
        authorize(domain="WAVE")


def test_valid_a4_sample_has_note_map(tmp_path):
    path = tone_wav(tmp_path / "a4.wav")
    result = analyze_sample(path)
    assert result["schema"] == "HazewaveSampleNoteMap/v1"
    assert result["method"] == "bounded_windowed_fft_heuristic"
    assert result["source"]["sample_rate"] == 16000
    assert result["source"]["duration_seconds"] == pytest.approx(0.6)
    a4 = [n for n in result["notes"] if n["midi_note"] == 69]
    assert a4, result["notes"]
    assert a4[0]["start_seconds"] < 0.25
    assert a4[0]["end_seconds"] > 0.35
    assert "polyphonic_transcription_not_guaranteed" in result["limitations"]


def test_two_tones_produce_two_editable_pitches(tmp_path):
    path = tone_wav(tmp_path / "chord.wav", notes=(261.625565, 329.627557), seconds=0.8)
    notes = analyze_sample(path)["notes"]
    pitches = {n["midi_note"] for n in notes}
    assert {60, 64}.issubset(pitches), notes


def test_real_midi_bytes_receipt_and_inspect_before_export(tmp_path):
    source = tone_wav(tmp_path / "source.wav")
    target = tmp_path / "export.mid"
    output = transcribe_to_midi(
        source, target, authorization=authorize(), task_id="note-map-tests",
    )
    raw = target.read_bytes()
    assert raw.startswith(b"MThd\x00\x00\x00\x06\x00\x00")
    assert b"MTrk" in raw
    assert b"\x90\x45" in raw  # note-on, pitch 69 A4
    assert b"\x80\x45" in raw  # note-off
    receipt = output["receipt"]
    assert receipt["authority"] == "HAZEWAVE_HARNESS"
    assert receipt["status"] == "EXECUTED_HAZE_LOCAL"
    assert receipt["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert receipt["midi_sha256"] == hashlib.sha256(raw).hexdigest()
    assert receipt["cost_usd"] == 0
    assert receipt["publication_attempted"] is False
    assert receipt["origin_kind"] == "ORIGINAL_STDLIB_IMPLEMENTATION"
    assert output["result"]["notes"]


def test_bad_input_and_empty_are_rejected(tmp_path):
    corrupt = tmp_path / "invalid.wav"
    corrupt.write_bytes(b"RIFFgarbage")
    with pytest.raises(ValueError):
        analyze_sample(corrupt)
    silent = tmp_path / "silent.wav"
    tone_wav(silent, notes=(), seconds=0.4)
    assert analyze_sample(silent)["notes"] == []
    empty = tmp_path / "empty.wav"
    empty.write_bytes(b"")
    with pytest.raises(ValueError):
        analyze_sample(empty)


def test_denies_invalid_authorization_and_does_not_write(tmp_path):
    source = tone_wav(tmp_path / "source.wav")
    target = tmp_path / "forbidden.mid"
    with pytest.raises(PermissionError, match="AUTHORIZATION_CAPABILITY_MISMATCH"):
        transcribe_to_midi(
            source, target, authorization=authorize("audio.analyze"),
            task_id="note-map-tests",
        )
    assert not target.exists()


def test_denies_oversize_and_symlink(tmp_path):
    target = tmp_path / "too-large.wav"
    target.write_bytes(b"RIFF" + b"x" * (10 * 1024 * 1024 + 1))
    with pytest.raises(ValueError, match="INPUT_SIZE_OUT_OF_BOUNDS"):
        analyze_sample(target)
    original = tone_wav(tmp_path / "real.wav")
    link = tmp_path / "link.wav"
    link.symlink_to(original)
    with pytest.raises(ValueError, match="INPUT_MUST_BE_REGULAR_FILE"):
        analyze_sample(link)


def test_existing_hazewave_cli_exposes_notes_and_exports(tmp_path):
    import subprocess
    import sys
    source = tone_wav(tmp_path / "cli.wav")
    output = tmp_path / "cli.mid"
    proc = subprocess.run(
        [sys.executable, "-m", "hazewave.cli", "notes", str(source),
         "--out", str(output), "--task-id", "haze-cli-notes"],
        capture_output=True, text=True, timeout=20,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["receipt"]["status"] == "EXECUTED_HAZE_LOCAL"
    assert output.read_bytes().startswith(b"MThd")
