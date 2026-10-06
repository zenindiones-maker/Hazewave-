from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import math
from pathlib import Path
from typing import Callable, Sequence

from hazewave.audio_qc import AudioQCError, AudioQCReport, analyze_audio_qc
from hazewave.reference_profile import (
    DecodedPCM,
    ReferenceProfileError,
    _default_pcm_decoder,
    _mono_samples,
    _spectral_ratios,
    _stereo_features,
    _transient_density,
    _validate_pcm,
)


class AudioAnalysisError(RuntimeError):
    pass


@dataclass(frozen=True)
class AudioSectionEstimate:
    section_id: str
    start_seconds: float
    end_seconds: float
    confidence: float
    label: str
    schema: str = "AudioSectionEstimate/v1"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class MusicAnalysisResult:
    engine: str
    engine_version: str
    tempo_bpm: float
    tempo_confidence: float
    beat_positions_seconds: tuple[float, ...]
    onset_positions_seconds: tuple[float, ...]
    onset_rate_per_second: float
    key: str
    scale: str
    key_strength: float
    sections: tuple[AudioSectionEstimate, ...] = ()
    structure_method: str = "NOT_AVAILABLE"
    schema: str = "MusicAnalysisResult/v1"


@dataclass(frozen=True)
class ProfessionalAudioAnalysisReport:
    source_path: str
    source_sha256: str
    integrated_lufs: float
    momentary_max_lufs: float | None
    short_term_max_lufs: float | None
    loudness_range_lu: float
    true_peak_dbfs: float
    crest_factor_ratio: float
    stereo_correlation: float
    stereo_side_energy_ratio: float
    stereo_balance_db: float
    low_energy_ratio: float
    mid_energy_ratio: float
    high_energy_ratio: float
    transient_density_per_second: float
    tempo_bpm: float
    tempo_confidence: float
    beat_positions_seconds: tuple[float, ...]
    beat_count: int
    onset_positions_seconds: tuple[float, ...]
    onset_count: int
    onset_rate_per_second: float
    key: str
    scale: str
    key_strength: float
    sections: tuple[AudioSectionEstimate, ...]
    structure_status: str
    rejected_section_count: int
    structure_method: str
    analysis_engine: str
    analysis_engine_version: str
    analysis_sample_rate: int
    private_media_policy: str = "LOCAL_ONLY"
    artistic_verdict: str = "NOT_ASSIGNED"
    authority: str = "NONE"
    grants_execution_authority: bool = False
    schema: str = "ProfessionalAudioAnalysisReport/v1"

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["beat_positions_seconds"] = list(self.beat_positions_seconds)
        value["onset_positions_seconds"] = list(self.onset_positions_seconds)
        value["sections"] = [item.to_dict() for item in self.sections]
        return value


AudioQCAnalyzer = Callable[[Path], AudioQCReport]
PCMDecoder = Callable[[Path], DecodedPCM]
MusicAnalyzer = Callable[[Path], MusicAnalysisResult]


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_essentia():
    try:
        import essentia
        import essentia.standard as standard
    except ImportError as exc:
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_ESSENTIA_RUNTIME_MISSING"
        ) from exc
    version = str(getattr(essentia, "__version__", "") or "").strip()
    if not version:
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_ENGINE_VERSION_REQUIRED"
        )
    return essentia, standard


def _default_music_analyzer(path: Path) -> MusicAnalysisResult:
    _, standard = _load_essentia()
    try:
        audio = standard.MonoLoader(
            filename=str(path),
            sampleRate=44100,
        )()
        if len(audio) == 0:
            raise AudioAnalysisError("AUDIO_ANALYSIS_ESSENTIA_EMPTY_AUDIO")

        bpm, beats, confidence, _, _ = standard.RhythmExtractor2013(
            method="multifeature",
            minTempo=40,
            maxTempo=208,
        )(audio)
        onsets, onset_rate = standard.OnsetRate()(audio)
        key, scale, key_strength = standard.KeyExtractor(
            sampleRate=44100,
        )(audio)

        essentia, _ = _load_essentia()
        version = str(getattr(essentia, "__version__", "") or "").strip()
    except AudioAnalysisError:
        raise
    except Exception as exc:
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_ESSENTIA_EXECUTION_FAILED"
        ) from exc

    return MusicAnalysisResult(
        engine="Essentia",
        engine_version=version,
        tempo_bpm=float(bpm),
        tempo_confidence=float(confidence),
        beat_positions_seconds=tuple(float(value) for value in beats),
        onset_positions_seconds=tuple(float(value) for value in onsets),
        onset_rate_per_second=float(onset_rate),
        key=str(key),
        scale=str(scale),
        key_strength=float(key_strength),
        sections=(),
        structure_method="NOT_AVAILABLE",
    )


def _finite(value: object, *, code: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise AudioAnalysisError(code) from exc
    if not math.isfinite(result):
        raise AudioAnalysisError(code)
    return result


def _validate_event_timeline(
    values: Sequence[float],
    *,
    duration_seconds: float,
) -> tuple[float, ...]:
    normalized: list[float] = []
    previous = -1.0
    for raw in values:
        value = _finite(raw, code="AUDIO_ANALYSIS_EVENT_TIMELINE_INVALID")
        if value < 0 or value > duration_seconds + 0.100001:
            raise AudioAnalysisError(
                "AUDIO_ANALYSIS_EVENT_TIMELINE_INVALID"
            )
        if value < previous:
            raise AudioAnalysisError(
                "AUDIO_ANALYSIS_EVENT_TIMELINE_INVALID"
            )
        normalized.append(value)
        previous = value
    return tuple(normalized)


def _stereo_balance_db(pcm: DecodedPCM) -> float:
    if pcm.channels == 1:
        return 0.0
    left = sum(float(frame[0]) ** 2 for frame in pcm.frames)
    right = sum(float(frame[1]) ** 2 for frame in pcm.frames)
    epsilon = 1e-20
    if left <= epsilon and right <= epsilon:
        return 0.0
    if right <= epsilon:
        return 120.0
    if left <= epsilon:
        return -120.0
    return 10.0 * math.log10(left / right)


def _validate_music_result(
    result: MusicAnalysisResult,
    *,
    duration_seconds: float,
) -> tuple[
    MusicAnalysisResult,
    tuple[float, ...],
    tuple[float, ...],
]:
    if not isinstance(result, MusicAnalysisResult):
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_MUSIC_RESULT_MALFORMED"
        )
    if not str(result.engine or "").strip():
        raise AudioAnalysisError("AUDIO_ANALYSIS_ENGINE_REQUIRED")
    if not str(result.engine_version or "").strip():
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_ENGINE_VERSION_REQUIRED"
        )
    tempo = _finite(
        result.tempo_bpm,
        code="AUDIO_ANALYSIS_TEMPO_INVALID",
    )
    confidence = _finite(
        result.tempo_confidence,
        code="AUDIO_ANALYSIS_TEMPO_CONFIDENCE_INVALID",
    )
    onset_rate = _finite(
        result.onset_rate_per_second,
        code="AUDIO_ANALYSIS_ONSET_RATE_INVALID",
    )
    strength = _finite(
        result.key_strength,
        code="AUDIO_ANALYSIS_KEY_STRENGTH_INVALID",
    )
    if tempo <= 0 or tempo > 400:
        raise AudioAnalysisError("AUDIO_ANALYSIS_TEMPO_INVALID")
    if confidence < 0:
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_TEMPO_CONFIDENCE_INVALID"
        )
    if onset_rate < 0:
        raise AudioAnalysisError("AUDIO_ANALYSIS_ONSET_RATE_INVALID")
    if not 0.0 <= strength <= 1.0:
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_KEY_STRENGTH_INVALID"
        )
    if not str(result.key or "").strip() or not str(result.scale or "").strip():
        raise AudioAnalysisError("AUDIO_ANALYSIS_KEY_INVALID")

    beats = _validate_event_timeline(
        result.beat_positions_seconds,
        duration_seconds=duration_seconds,
    )
    onsets = _validate_event_timeline(
        result.onset_positions_seconds,
        duration_seconds=duration_seconds,
    )
    return result, beats, onsets


def _filter_sections(
    sections: Sequence[AudioSectionEstimate],
    *,
    duration_seconds: float,
    confidence_threshold: float,
) -> tuple[
    tuple[AudioSectionEstimate, ...],
    int,
    str,
]:
    if not sections:
        return (), 0, "NOT_AVAILABLE"

    accepted: list[AudioSectionEstimate] = []
    rejected = 0
    previous_end = -1.0
    for section in sections:
        if not isinstance(section, AudioSectionEstimate):
            raise AudioAnalysisError(
                "AUDIO_ANALYSIS_SECTION_MALFORMED"
            )
        start = _finite(
            section.start_seconds,
            code="AUDIO_ANALYSIS_SECTION_MALFORMED",
        )
        end = _finite(
            section.end_seconds,
            code="AUDIO_ANALYSIS_SECTION_MALFORMED",
        )
        confidence = _finite(
            section.confidence,
            code="AUDIO_ANALYSIS_SECTION_MALFORMED",
        )
        if (
            not str(section.section_id or "").strip()
            or start < 0
            or end <= start
            or end > duration_seconds + 0.100001
            or start < previous_end
            or not 0.0 <= confidence <= 1.0
        ):
            raise AudioAnalysisError(
                "AUDIO_ANALYSIS_SECTION_MALFORMED"
            )
        previous_end = end
        if confidence >= confidence_threshold:
            accepted.append(section)
        else:
            rejected += 1

    if accepted:
        return tuple(accepted), rejected, "AVAILABLE"
    return (), rejected, "LOW_CONFIDENCE"


def analyze_professional_audio(
    source: Path | str,
    *,
    audio_qc_analyzer: AudioQCAnalyzer | None = None,
    pcm_decoder: PCMDecoder | None = None,
    music_analyzer: MusicAnalyzer | None = None,
    structure_confidence_threshold: float = 0.70,
) -> ProfessionalAudioAnalysisReport:
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise AudioAnalysisError("AUDIO_ANALYSIS_SOURCE_NOT_FOUND")
    if path.stat().st_size <= 0:
        raise AudioAnalysisError("AUDIO_ANALYSIS_SOURCE_EMPTY")
    if not 0.0 <= structure_confidence_threshold <= 1.0:
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_STRUCTURE_THRESHOLD_INVALID"
        )

    source_hash = _sha256_file(path)
    analyze_qc = audio_qc_analyzer or analyze_audio_qc
    try:
        qc = analyze_qc(path)
    except AudioQCError as exc:
        raise AudioAnalysisError("AUDIO_ANALYSIS_QC_FAILED") from exc
    except AudioAnalysisError:
        raise
    except Exception as exc:
        raise AudioAnalysisError("AUDIO_ANALYSIS_QC_FAILED") from exc

    if not isinstance(qc, AudioQCReport):
        raise AudioAnalysisError("AUDIO_ANALYSIS_QC_MALFORMED")
    if qc.source_sha256 != source_hash:
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_QC_SOURCE_HASH_MISMATCH"
        )

    decode = pcm_decoder or _default_pcm_decoder
    try:
        pcm = _validate_pcm(decode(path))
    except ReferenceProfileError as exc:
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_PCM_FAILED"
        ) from exc
    except AudioAnalysisError:
        raise
    except Exception as exc:
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_PCM_FAILED"
        ) from exc

    mono = _mono_samples(pcm)
    try:
        low, mid, high = _spectral_ratios(mono, pcm.sample_rate)
        correlation, side_ratio = _stereo_features(pcm)
        transient_density = _transient_density(
            mono,
            pcm.sample_rate,
        )
    except ReferenceProfileError as exc:
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_PCM_FEATURES_FAILED"
        ) from exc
    balance_db = _stereo_balance_db(pcm)

    analyze_music = music_analyzer or _default_music_analyzer
    try:
        raw_music = analyze_music(path)
    except AudioAnalysisError:
        raise
    except Exception as exc:
        raise AudioAnalysisError(
            "AUDIO_ANALYSIS_MUSIC_BACKEND_FAILED"
        ) from exc

    music, beats, onsets = _validate_music_result(
        raw_music,
        duration_seconds=qc.duration_seconds,
    )
    sections, rejected_sections, structure_status = _filter_sections(
        music.sections,
        duration_seconds=qc.duration_seconds,
        confidence_threshold=structure_confidence_threshold,
    )

    return ProfessionalAudioAnalysisReport(
        source_path=str(path),
        source_sha256=source_hash,
        integrated_lufs=qc.integrated_lufs,
        momentary_max_lufs=qc.momentary_max_lufs,
        short_term_max_lufs=qc.short_term_max_lufs,
        loudness_range_lu=qc.loudness_range_lu,
        true_peak_dbfs=qc.true_peak_dbfs,
        crest_factor_ratio=qc.crest_factor_ratio,
        stereo_correlation=correlation,
        stereo_side_energy_ratio=side_ratio,
        stereo_balance_db=balance_db,
        low_energy_ratio=low,
        mid_energy_ratio=mid,
        high_energy_ratio=high,
        transient_density_per_second=transient_density,
        tempo_bpm=music.tempo_bpm,
        tempo_confidence=music.tempo_confidence,
        beat_positions_seconds=beats,
        beat_count=len(beats),
        onset_positions_seconds=onsets,
        onset_count=len(onsets),
        onset_rate_per_second=music.onset_rate_per_second,
        key=music.key,
        scale=music.scale,
        key_strength=music.key_strength,
        sections=sections,
        structure_status=structure_status,
        rejected_section_count=rejected_sections,
        structure_method=music.structure_method,
        analysis_engine=music.engine,
        analysis_engine_version=music.engine_version,
        analysis_sample_rate=pcm.sample_rate,
    )
