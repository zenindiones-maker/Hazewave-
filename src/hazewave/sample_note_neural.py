"""Optional licensed polyphonic inference for Hazewave HAZE.

Spotify Basic Pitch 0.4.0 (Apache-2.0), explicitly requested; no
silent heuristic fallback, no external I/O, no bundled proprietary weights.
"""
from __future__ import annotations

from contextlib import redirect_stdout
from hashlib import sha256
from importlib import metadata
from pathlib import Path
import io
import json
import os
import sys
import tempfile
import time

from hazewave.harness import (
    HazewaveAuthorization, HazewaveTask, issue_authorization, route_task,
    validate_authorization,
)
from hazewave.re_inspectors import run_inspection
from hazewave.sample_note_map import _pcm_data, _canonical, CAPABILITY


def transcribe_polyphonic(
    wav_file: str | Path, midi_output: str | Path, *,
    authorization: HazewaveAuthorization, task_id: str,
) -> dict:
    """Read-only source + local authorized MIDI output, fail-closed."""
    began = time.perf_counter()
    validate_authorization(
        authorization, expected_task_id=task_id, expected_capability=CAPABILITY
    )
    if authorization.domain != "HAZE":
        raise PermissionError("HAZE_ONLY_CAPABILITY")
    expected = issue_authorization(route_task(HazewaveTask(
        task_id=task_id, goal="Authorized Basic Pitch audio-to-MIDI",
        required_capability=CAPABILITY, requested_domain="HAZE",
    )))
    if expected.authorization_id != authorization.authorization_id:
        raise PermissionError("AUTHORIZATION_ID_MISMATCH")
    source = Path(wav_file)
    dest = Path(midi_output)
    if dest.suffix.lower() != ".mid" or dest.exists() or dest.is_symlink():
        raise ValueError("MIDI_OUTPUT_MUST_BE_NEW_MID_FILE")
    if not dest.parent.is_dir() or dest.parent.is_symlink():
        raise ValueError("INVALID_DESTINATION_DIRECTORY")
    # Bounds checks: same PCM16 WAV, duration, symlink, and ownership gate as v1.
    _, rate, source_sha, size = _pcm_data(source)
    inspector_auth = issue_authorization(route_task(HazewaveTask(
        task_id=task_id, goal="Inspect WAV prior to model execution",
        required_capability="codec_stream_analyzer", requested_domain="HAZE",
    )))
    inspector = run_inspection(
        "codec_stream_analyzer", source,
        task_id=task_id, authorization=inspector_auth,
    )
    if inspector["result"]["codec"] != "PCM" or inspector["receipt"]["source_sha256"] != source_sha:
        raise ValueError("SOURCE_INSPECTION_MISMATCH")
    try:
        version = metadata.version("basic-pitch")
    except metadata.PackageNotFoundError as exc:
        raise ValueError("BASIC_PITCH_NOT_INSTALLED_INSTALL_EXPLICITLY") from exc
    if version != "0.4.0":
        raise ValueError(f"BASIC_PITCH_VERSION_NOT_ADMITTED:{version}")
    try:
        from basic_pitch.inference import predict
    except (ImportError, RuntimeError) as exc:
        raise ValueError("BASIC_PITCH_MODEL_UNAVAILABLE") from exc
    # Basic Pitch prints to stdout, but machine-readable CLI stdout is JSON.
    with redirect_stdout(sys.stderr):
        _, midi_obj, note_events = predict(str(source))
    notes = []
    for start, end, pitch, amplitude, bends in note_events:
        start, end, pitch = float(start), float(end), int(pitch)
        if not (0 <= pitch <= 127 and 0 <= start < end <= 21):
            raise ValueError("MODEL_RETURNED_INVALID_NOTES")
        notes.append({
            "midi_note": pitch, "start_seconds": round(start, 5),
            "end_seconds": round(end, 5),
            "velocity": min(127, max(1, round(float(amplitude) * 127))),
            "pitch_bends": list(bends or [])[:4000],
        })
    notes.sort(key=lambda x: (x["start_seconds"], x["midi_note"]))
    result = {
        "schema": "HazewaveSampleNoteMap/v1",
        "engine": "spotify-basic-pitch",
        "engine_version": version,
        "license": "Apache-2.0",
        "source": {"format": "WAV_PCM16", "sample_rate": rate,
                   "file_size": size, "sha256": source_sha},
        "notes": notes,
        "limitations": ["not_guaranteed_on_full_mixes", "musical_qa_required",
                        "offline_model_not_trained_by_hazewave"],
    }
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".hazewave-neural-", suffix=".mid", dir=dest.parent, delete=False
        ) as tmp:
            tmp_name = tmp.name
        midi_obj.write(tmp_name)
        contents = Path(tmp_name).read_bytes()
        if not contents.startswith(b"MThd"):
            raise ValueError("INVALID_MODEL_MIDI_OUTPUT")
        if sha256(source.read_bytes()).hexdigest() != source_sha:
            raise ValueError("SOURCE_CHANGED_BEFORE_EXPORT")
        # Atomic no-clobber (hard link fails when target already exists).
        os.link(tmp_name, dest)
    finally:
        if tmp_name is not None:
            Path(tmp_name).unlink(missing_ok=True)
    midi_hash = sha256(contents).hexdigest()
    receipt = {
        "schema": "HazewaveNeuralTranscriptionReceipt/v1",
        "authority": "HAZEWAVE_HARNESS",
        "authorization_id": authorization.authorization_id,
        "task_id": task_id, "capability": CAPABILITY,
        "engine": "spotify/basic-pitch", "engine_version": version,
        "license": "Apache-2.0",
        "status": "EXECUTED_HAZE_LOCAL",
        "source_sha256": source_sha,
        "inspector_result_sha256": inspector["receipt"]["result_sha256"],
        "map_sha256": sha256(_canonical(result)).hexdigest(),
        "midi_sha256": midi_hash,
        "note_count": len(notes), "cost_usd": 0,
        "publication_attempted": False,
        "elapsed_ms": round((time.perf_counter() - began) * 1000, 3),
    }
    return {"result": result, "receipt": receipt}
