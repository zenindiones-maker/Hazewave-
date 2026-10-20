from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import math
from pathlib import Path
import struct
import subprocess
from typing import Callable, Final, Sequence

from hazewave.audio_qc import AudioQCError, AudioQCReport, analyze_audio_qc


FEATURE_METHOD: Final = "LOCAL_PCM_HEURISTIC_V1"
DEFAULT_ANALYSIS_SAMPLE_RATE: Final = 12000


class ReferenceProfileError(RuntimeError):
    pass


@dataclass(frozen=True)
class DecodedPCM:
    sample_rate: int
    channels: int
    frames: tuple[tuple[float, ...], ...]
    schema: str = "DecodedPCM/v1"


@dataclass(frozen=True)
class ReferenceProfile:
    source_path: str
    source_sha256: str
    authorization: str
    integrated_lufs: float
    loudness_range_lu: float
    true_peak_dbfs: float
    crest_factor_ratio: float
    low_energy_ratio: float
    mid_energy_ratio: float
    high_energy_ratio: float
    stereo_correlation: float
    stereo_side_energy_ratio: float
    transient_density_per_second: float
    section_energy_dbfs: tuple[float, ...]
    analysis_sample_rate: int
    feature_method: str = FEATURE_METHOD
    reconstructs_reference_content: bool = False
    artistic_verdict: str = "NOT_ASSIGNED"
    authority: str = "NONE"
    grants_execution_authority: bool = False
    schema: str = "ReferenceProfile/v1"

    def to_dict(self) -> dict[str, object]:
        value = asdict(self)
        value["section_energy_dbfs"] = list(self.section_energy_dbfs)
        return value


AudioQCAnalyzer = Callable[[Path], AudioQCReport]
PCMDecoder = Callable[[Path], DecodedPCM]


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_pcm_decoder(path: Path) -> DecodedPCM:
    args = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-v",
        "error",
        "-i",
        str(path),
        "-map",
        "0:a:0",
        "-ac",
        "2",
        "-ar",
        str(DEFAULT_ANALYSIS_SAMPLE_RATE),
        "-f",
        "s16le",
        "pipe:1",
    ]
    try:
        result = subprocess.run(
            args,
            check=False,
            capture_output=True,
            timeout=300,
        )
    except FileNotFoundError as exc:
        raise ReferenceProfileError("REFERENCE_PCM_DECODER_MISSING") from exc
    except subprocess.TimeoutExpired as exc:
        raise ReferenceProfileError("REFERENCE_PCM_DECODER_TIMEOUT") from exc

    if result.returncode != 0:
        raise ReferenceProfileError("REFERENCE_PCM_DECODE_FAILED")
    raw = result.stdout
    if not raw or len(raw) % 4 != 0:
        raise ReferenceProfileError("REFERENCE_PCM_MALFORMED")

    frames: list[tuple[float, float]] = []
    scale = 32768.0
    for left, right in struct.iter_unpack("<hh", raw):
        frames.append((left / scale, right / scale))
    if not frames:
        raise ReferenceProfileError("REFERENCE_PCM_EMPTY")
    return DecodedPCM(
        sample_rate=DEFAULT_ANALYSIS_SAMPLE_RATE,
        channels=2,
        frames=tuple(frames),
    )


def _validate_pcm(pcm: DecodedPCM) -> DecodedPCM:
    if (
        not isinstance(pcm, DecodedPCM)
        or pcm.sample_rate <= 0
        or pcm.channels not in {1, 2}
        or not pcm.frames
    ):
        raise ReferenceProfileError("REFERENCE_PCM_MALFORMED")
    for frame in pcm.frames:
        if not isinstance(frame, tuple) or len(frame) != pcm.channels:
            raise ReferenceProfileError("REFERENCE_PCM_MALFORMED")
        for sample in frame:
            if not isinstance(sample, (int, float)) or not math.isfinite(float(sample)):
                raise ReferenceProfileError("REFERENCE_PCM_MALFORMED")
    return pcm


def _mono_samples(pcm: DecodedPCM) -> list[float]:
    if pcm.channels == 1:
        return [float(frame[0]) for frame in pcm.frames]
    return [
        (float(frame[0]) + float(frame[1])) * 0.5
        for frame in pcm.frames
    ]


def _one_pole_alpha(cutoff_hz: float, sample_rate: int) -> float:
    return 1.0 - math.exp(-2.0 * math.pi * cutoff_hz / float(sample_rate))


def _spectral_ratios(samples: Sequence[float], sample_rate: int) -> tuple[float, float, float]:
    if not samples:
        raise ReferenceProfileError("REFERENCE_PCM_EMPTY")

    nyquist = sample_rate * 0.5
    low_cut = min(250.0, sample_rate * 0.10)
    high_cut = min(4000.0, sample_rate * 0.40)
    if high_cut <= low_cut:
        high_cut = min(nyquist * 0.90, low_cut * 2.0)
    if high_cut <= low_cut or low_cut <= 0:
        raise ReferenceProfileError("REFERENCE_PCM_SAMPLE_RATE_UNSUPPORTED")

    low_alpha = _one_pole_alpha(low_cut, sample_rate)
    high_alpha = _one_pole_alpha(high_cut, sample_rate)
    low_state = 0.0
    high_state = 0.0
    low_energy = 0.0
    mid_energy = 0.0
    high_energy = 0.0

    for sample in samples:
        x = float(sample)
        low_state += low_alpha * (x - low_state)
        high_state += high_alpha * (x - high_state)
        low = low_state
        mid = high_state - low_state
        high = x - high_state
        low_energy += low * low
        mid_energy += mid * mid
        high_energy += high * high

    total = low_energy + mid_energy + high_energy
    if total <= 1e-20:
        raise ReferenceProfileError("REFERENCE_PCM_SILENT")
    return (
        low_energy / total,
        mid_energy / total,
        high_energy / total,
    )


def _stereo_features(pcm: DecodedPCM) -> tuple[float, float]:
    if pcm.channels == 1:
        return 1.0, 0.0

    left_energy = 0.0
    right_energy = 0.0
    cross = 0.0
    mid_energy = 0.0
    side_energy = 0.0
    for frame in pcm.frames:
        left = float(frame[0])
        right = float(frame[1])
        left_energy += left * left
        right_energy += right * right
        cross += left * right
        mid = (left + right) * 0.5
        side = (left - right) * 0.5
        mid_energy += mid * mid
        side_energy += side * side

    denominator = math.sqrt(left_energy * right_energy)
    correlation = cross / denominator if denominator > 1e-20 else 1.0
    correlation = max(-1.0, min(1.0, correlation))
    side_ratio = side_energy / (mid_energy + side_energy) if (mid_energy + side_energy) > 1e-20 else 0.0
    return correlation, side_ratio


def _rms_dbfs(samples: Sequence[float]) -> float:
    if not samples:
        return -120.0
    mean_square = sum(float(value) * float(value) for value in samples) / len(samples)
    if mean_square <= 1e-20:
        return -120.0
    return 20.0 * math.log10(math.sqrt(mean_square))


def _section_energy(samples: Sequence[float], section_count: int) -> tuple[float, ...]:
    if section_count < 1 or section_count > 128:
        raise ReferenceProfileError("REFERENCE_SECTION_COUNT_INVALID")
    if section_count > len(samples):
        raise ReferenceProfileError("REFERENCE_SECTION_COUNT_INVALID")

    values: list[float] = []
    total = len(samples)
    for index in range(section_count):
        start = (index * total) // section_count
        end = ((index + 1) * total) // section_count
        values.append(_rms_dbfs(samples[start:end]))
    return tuple(values)


def _transient_density(samples: Sequence[float], sample_rate: int) -> float:
    block_size = max(1, int(sample_rate * 0.010))
    levels: list[float] = []
    for start in range(0, len(samples), block_size):
        block = samples[start : start + block_size]
        if len(block) < max(1, block_size // 2):
            continue
        levels.append(_rms_dbfs(block))

    transient_count = 0
    previous: float | None = None
    for level in levels:
        if previous is not None and level > -40.0 and level - previous >= 6.0:
            transient_count += 1
        previous = level

    duration = len(samples) / float(sample_rate)
    return transient_count / duration if duration > 0 else 0.0


def build_reference_profile(
    source: Path | str,
    *,
    authorized: bool,
    audio_qc_analyzer: AudioQCAnalyzer | None = None,
    pcm_decoder: PCMDecoder | None = None,
    section_count: int = 8,
) -> ReferenceProfile:
    path = Path(source).expanduser().resolve()
    if not authorized:
        raise ReferenceProfileError("REFERENCE_NOT_AUTHORIZED")
    if not path.is_file():
        raise ReferenceProfileError("REFERENCE_SOURCE_NOT_FOUND")
    if path.stat().st_size <= 0:
        raise ReferenceProfileError("REFERENCE_SOURCE_EMPTY")
    if not isinstance(section_count, int) or not 1 <= section_count <= 128:
        raise ReferenceProfileError("REFERENCE_SECTION_COUNT_INVALID")

    source_hash = _sha256_file(path)
    analyze = audio_qc_analyzer or analyze_audio_qc
    try:
        qc = analyze(path)
    except AudioQCError as exc:
        raise ReferenceProfileError("REFERENCE_AUDIO_QC_FAILED") from exc
    except ReferenceProfileError:
        raise
    except Exception as exc:
        raise ReferenceProfileError("REFERENCE_AUDIO_QC_FAILED") from exc

    if not isinstance(qc, AudioQCReport):
        raise ReferenceProfileError("REFERENCE_AUDIO_QC_MALFORMED")
    if qc.source_sha256 != source_hash:
        raise ReferenceProfileError("REFERENCE_AUDIO_QC_SOURCE_HASH_MISMATCH")

    decode = pcm_decoder or _default_pcm_decoder
    try:
        pcm = _validate_pcm(decode(path))
    except ReferenceProfileError:
        raise
    except Exception as exc:
        raise ReferenceProfileError("REFERENCE_PCM_DECODE_FAILED") from exc

    mono = _mono_samples(pcm)
    low, mid, high = _spectral_ratios(mono, pcm.sample_rate)
    correlation, side_ratio = _stereo_features(pcm)
    sections = _section_energy(mono, section_count)
    transients = _transient_density(mono, pcm.sample_rate)

    return ReferenceProfile(
        source_path=str(path),
        source_sha256=source_hash,
        authorization="AUTHORIZED",
        integrated_lufs=qc.integrated_lufs,
        loudness_range_lu=qc.loudness_range_lu,
        true_peak_dbfs=qc.true_peak_dbfs,
        crest_factor_ratio=qc.crest_factor_ratio,
        low_energy_ratio=low,
        mid_energy_ratio=mid,
        high_energy_ratio=high,
        stereo_correlation=correlation,
        stereo_side_energy_ratio=side_ratio,
        transient_density_per_second=transients,
        section_energy_dbfs=sections,
        analysis_sample_rate=pcm.sample_rate,
    )
