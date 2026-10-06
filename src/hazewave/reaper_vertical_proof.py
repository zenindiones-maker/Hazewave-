from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping

from hazewave.audio_qc import AudioQCReport
from hazewave.reaper_bridge import ReaperProjectSnapshot


class VerticalProofError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeParameterSemantic:
    index: int
    name: str
    value: float
    minimum: float
    maximum: float
    schema: str = "RuntimeParameterSemantic/v1"


@dataclass(frozen=True)
class TapeEcho2Semantics:
    fx_guid: str
    fx_index: int
    name: str
    parameters: Mapping[str, RuntimeParameterSemantic]
    source_version: str = "1.0.8"
    binding: str = "RUNTIME_NAME_DISCOVERY_REQUIRED"
    schema: str = "PluginSemanticProfile/v1"


@dataclass(frozen=True)
class FixtureAnalysisAdjustment:
    parameter_role: str
    new_normalized_value: float
    reason: str
    evidence: Mapping[str, float | bool]
    scope: str = "FIXTURE_ONLY"
    schema: str = "FixtureAnalysisAdjustment/v1"


_CANONICAL_PARAMETER_NAMES = {
    "repeat_rate": "repeat rate",
    "intensity": "intensity",
    "echo_volume": "echo volume",
    "mix": "mix",
}


def _normalize_name(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().casefold())


def ensure_disposable_fixture(
    snapshot: ReaperProjectSnapshot,
    *,
    fixture_root: Path | str,
) -> Path:
    root = Path(fixture_root).expanduser().resolve()
    raw_project = snapshot.project_path or snapshot.project_identity
    if not isinstance(raw_project, str) or not raw_project.strip():
        raise VerticalProofError("VERTICAL_PROOF_PROJECT_PATH_MISSING")

    project = Path(raw_project).expanduser().resolve()
    try:
        project.relative_to(root)
    except ValueError as exc:
        raise VerticalProofError(
            "VERTICAL_PROOF_PROJECT_OUTSIDE_FIXTURE_ROOT"
        ) from exc

    if project.suffix.casefold() != ".rpp":
        raise VerticalProofError("VERTICAL_PROOF_PROJECT_NOT_RPP")
    if not project.is_file():
        raise VerticalProofError("VERTICAL_PROOF_FIXTURE_MISSING")
    if snapshot.dirty:
        raise VerticalProofError("VERTICAL_PROOF_FIXTURE_DIRTY")
    if snapshot.project_identity not in {str(project), str(project.resolve())}:
        raise VerticalProofError("VERTICAL_PROOF_FIXTURE_IDENTITY_MISMATCH")
    return project


def _coerce_runtime_parameter(
    item: Mapping[str, Any],
) -> RuntimeParameterSemantic:
    try:
        index = int(item["index"])
        name = str(item["name"]).strip()
        value = float(item["value"])
        minimum = float(item["min"])
        maximum = float(item["max"])
    except (KeyError, TypeError, ValueError) as exc:
        raise VerticalProofError("TAPE_ECHO_2_PARAMETER_MALFORMED") from exc
    if index < 0 or not name or maximum <= minimum:
        raise VerticalProofError("TAPE_ECHO_2_PARAMETER_MALFORMED")
    if value < minimum or value > maximum:
        raise VerticalProofError("TAPE_ECHO_2_PARAMETER_VALUE_OUT_OF_RANGE")
    return RuntimeParameterSemantic(
        index=index,
        name=name,
        value=value,
        minimum=minimum,
        maximum=maximum,
    )


def discover_tape_echo_2_semantics(
    fx: Mapping[str, Any],
) -> TapeEcho2Semantics:
    if not isinstance(fx, Mapping):
        raise VerticalProofError("TAPE_ECHO_2_FX_MALFORMED")
    name = str(fx.get("name") or "").strip()
    if "tape echo 2" not in name.casefold():
        raise VerticalProofError("TAPE_ECHO_2_IDENTITY_MISMATCH")
    fx_guid = str(fx.get("fx_guid") or "").strip()
    if not fx_guid:
        raise VerticalProofError("TAPE_ECHO_2_GUID_MISSING")
    try:
        fx_index = int(fx["fx_index"])
    except (KeyError, TypeError, ValueError) as exc:
        raise VerticalProofError("TAPE_ECHO_2_FX_INDEX_MALFORMED") from exc
    if fx_index < 0:
        raise VerticalProofError("TAPE_ECHO_2_FX_INDEX_MALFORMED")

    raw_parameters = fx.get("parameters")
    if not isinstance(raw_parameters, (list, tuple)):
        raise VerticalProofError("TAPE_ECHO_2_PARAMETERS_MALFORMED")

    discovered: dict[str, RuntimeParameterSemantic] = {}
    for item in raw_parameters:
        if not isinstance(item, Mapping):
            raise VerticalProofError("TAPE_ECHO_2_PARAMETER_MALFORMED")
        parameter = _coerce_runtime_parameter(item)
        normalized = _normalize_name(parameter.name)
        for role, canonical_name in _CANONICAL_PARAMETER_NAMES.items():
            if normalized == canonical_name:
                if role in discovered:
                    raise VerticalProofError(
                        f"TAPE_ECHO_2_PARAMETER_AMBIGUOUS:{role}"
                    )
                discovered[role] = parameter

    for role in _CANONICAL_PARAMETER_NAMES:
        if role not in discovered:
            raise VerticalProofError(f"TAPE_ECHO_2_PARAMETER_MISSING:{role}")

    return TapeEcho2Semantics(
        fx_guid=fx_guid,
        fx_index=fx_index,
        name=name,
        parameters=discovered,
    )


def _bounded(value: float, *, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def select_fixture_adjustment(
    report: AudioQCReport,
    *,
    current_echo_volume: float,
    current_intensity: float,
) -> FixtureAnalysisAdjustment:
    echo_volume = _bounded(float(current_echo_volume), lower=0.0, upper=1.0)
    intensity = _bounded(float(current_intensity), lower=0.0, upper=1.0)

    if report.clipping_detected or report.true_peak_dbfs >= -1.0:
        new_value = _bounded(echo_volume - 0.10, lower=0.20, upper=0.80)
        if new_value == echo_volume:
            new_value = _bounded(echo_volume - 0.05, lower=0.0, upper=0.80)
        return FixtureAnalysisAdjustment(
            parameter_role="echo_volume",
            new_normalized_value=round(new_value, 6),
            reason="TRUE_PEAK_HEADROOM",
            evidence={
                "true_peak_dbfs": report.true_peak_dbfs,
                "clipping_detected": report.clipping_detected,
            },
        )

    if intensity < 0.55:
        new_value = min(0.55, intensity + 0.05)
    else:
        new_value = max(0.40, intensity - 0.05)
    return FixtureAnalysisAdjustment(
        parameter_role="intensity",
        new_normalized_value=round(new_value, 6),
        reason="SAFE_FIXTURE_CONTRAST",
        evidence={
            "true_peak_dbfs": report.true_peak_dbfs,
            "clipping_detected": report.clipping_detected,
        },
    )
