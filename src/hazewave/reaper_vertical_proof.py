from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Any, Mapping

from hazewave.audio_qc import AudioQCReport
from hazewave.creative_plane import ExecutionReceiptPayload
from hazewave.reaper_bridge import ReaperProjectSnapshot
from hazewave.runtime_receipts import RuntimeReceiptStore, RuntimeReceiptStoreError


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



def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _audio_qc_from_mapping(payload: Mapping[str, Any]) -> AudioQCReport:
    required = {
        "source_path",
        "source_sha256",
        "codec_name",
        "sample_rate",
        "channels",
        "channel_layout",
        "duration_seconds",
        "integrated_lufs",
        "integrated_threshold_lufs",
        "loudness_range_lu",
        "true_peak_dbfs",
        "sample_peak_dbfs",
        "rms_dbfs",
        "dc_offset",
        "crest_factor_ratio",
        "clipping_detected",
        "technical_flags",
    }
    if not isinstance(payload, Mapping) or required.difference(payload):
        raise VerticalProofError("VERTICAL_PROOF_AUDIO_QC_MALFORMED")
    flags = payload.get("technical_flags")
    if not isinstance(flags, (list, tuple)) or not all(
        isinstance(value, str) for value in flags
    ):
        raise VerticalProofError("VERTICAL_PROOF_AUDIO_QC_MALFORMED")
    try:
        return AudioQCReport(
            source_path=str(payload["source_path"]),
            source_sha256=str(payload["source_sha256"]),
            codec_name=str(payload["codec_name"]),
            sample_rate=int(payload["sample_rate"]),
            channels=int(payload["channels"]),
            channel_layout=str(payload["channel_layout"]),
            duration_seconds=float(payload["duration_seconds"]),
            integrated_lufs=float(payload["integrated_lufs"]),
            integrated_threshold_lufs=float(payload["integrated_threshold_lufs"]),
            loudness_range_lu=float(payload["loudness_range_lu"]),
            true_peak_dbfs=float(payload["true_peak_dbfs"]),
            sample_peak_dbfs=float(payload["sample_peak_dbfs"]),
            rms_dbfs=float(payload["rms_dbfs"]),
            dc_offset=float(payload["dc_offset"]),
            crest_factor_ratio=float(payload["crest_factor_ratio"]),
            clipping_detected=bool(payload["clipping_detected"]),
            technical_flags=tuple(flags),
            delivery_profile=(
                str(payload["delivery_profile"])
                if payload.get("delivery_profile") is not None
                else None
            ),
            artistic_verdict=str(
                payload.get("artistic_verdict") or "NOT_ASSIGNED"
            ),
        )
    except (TypeError, ValueError) as exc:
        raise VerticalProofError("VERTICAL_PROOF_AUDIO_QC_MALFORMED") from exc


class ReaperVerticalProofRunner:
    BASELINE_PARAMETERS = {
        "repeat_rate": 0.30,
        "intensity": 0.45,
        "echo_volume": 0.60,
        "mix": 0.50,
    }

    def __init__(
        self,
        *,
        client: Any,
        receipt_store: RuntimeReceiptStore,
        fixture_root: Path | str,
        candidate_head: str,
        policy_digest: str,
        runtime_identity: str,
        tape_echo_version: str,
    ) -> None:
        self.client = client
        self.receipt_store = receipt_store
        self.fixture_root = Path(fixture_root).expanduser().resolve()
        self.candidate_head = str(candidate_head or "").strip()
        self.policy_digest = str(policy_digest or "").strip()
        self.runtime_identity = str(runtime_identity or "").strip()
        self.tape_echo_version = str(tape_echo_version or "").strip()
        if not self.candidate_head:
            raise VerticalProofError("VERTICAL_PROOF_CANDIDATE_HEAD_REQUIRED")
        if not self.policy_digest:
            raise VerticalProofError("VERTICAL_PROOF_POLICY_DIGEST_REQUIRED")
        if not self.runtime_identity:
            raise VerticalProofError("VERTICAL_PROOF_RUNTIME_IDENTITY_REQUIRED")
        if not self.tape_echo_version:
            raise VerticalProofError("VERTICAL_PROOF_PLUGIN_VERSION_REQUIRED")

    @staticmethod
    def _safe_id(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]", "-", str(value or "").strip())
        cleaned = re.sub(r"-+", "-", cleaned).strip("-.")
        if not cleaned:
            raise VerticalProofError("VERTICAL_PROOF_ID_INVALID")
        return cleaned[:80]

    def _source_audio(self, source_audio: Path | str) -> Path:
        source = Path(source_audio).expanduser().resolve()
        try:
            source.relative_to(self.fixture_root)
        except ValueError as exc:
            raise VerticalProofError(
                "VERTICAL_PROOF_SOURCE_OUTSIDE_FIXTURE_ROOT"
            ) from exc
        if not source.is_file():
            raise VerticalProofError("VERTICAL_PROOF_SOURCE_MISSING")
        if source.stat().st_size <= 0:
            raise VerticalProofError("VERTICAL_PROOF_SOURCE_EMPTY")
        return source

    @staticmethod
    def _response_state(
        response: Mapping[str, Any],
        *,
        expected_before: int,
    ) -> tuple[int, int]:
        if response.get("status") != "PASS":
            raise VerticalProofError("VERTICAL_PROOF_OPERATION_NOT_PASS")
        before = response.get("state_before")
        after = response.get("state_after")
        if not isinstance(before, Mapping) or not isinstance(after, Mapping):
            raise VerticalProofError("VERTICAL_PROOF_STATE_MALFORMED")
        try:
            before_count = int(before["project_state_change_count"])
            after_count = int(after["project_state_change_count"])
        except (KeyError, TypeError, ValueError) as exc:
            raise VerticalProofError("VERTICAL_PROOF_STATE_MALFORMED") from exc
        if before_count != expected_before:
            raise VerticalProofError("VERTICAL_PROOF_STATE_CHAIN_BROKEN")
        if after_count < 0:
            raise VerticalProofError("VERTICAL_PROOF_STATE_MALFORMED")
        return before_count, after_count

    def _persist_receipt(
        self,
        *,
        proof_id: str,
        step: int,
        capability: str,
        task_id: str,
        project_identity: str,
        state_before: int,
        state_after: int,
        idempotency_key: str,
        artifact_paths: tuple[Path, ...] = (),
    ) -> str:
        artifact_hashes: list[str] = []
        for path in artifact_paths:
            resolved = path.resolve()
            if not resolved.is_file() or resolved.stat().st_size <= 0:
                raise VerticalProofError("VERTICAL_PROOF_RECEIPT_ARTIFACT_MISSING")
            artifact_hashes.append("sha256:" + _sha256_file(resolved))

        payload = ExecutionReceiptPayload(
            project_id="HAZEWAVE",
            task_id=task_id,
            capability=capability,
            domain="HAZE",
            candidate_head=self.candidate_head,
            policy_digest=self.policy_digest,
            runtime_identity=self.runtime_identity,
            reaper_project_identity=project_identity,
            state_before=state_before,
            state_after=state_after,
            idempotency_key=idempotency_key,
            operation_result="PASS",
            artifact_hashes=tuple(artifact_hashes),
        )
        receipt_id = self._safe_id(
            f"{proof_id}-{step:02d}-{capability.replace('.', '-')}"
        )
        try:
            record = self.receipt_store.sign_and_persist(
                payload,
                receipt_id=receipt_id,
            )
        except RuntimeReceiptStoreError as exc:
            raise VerticalProofError(
                f"VERTICAL_PROOF_RECEIPT_FAILED:{exc}"
            ) from exc
        if not self.receipt_store.verify_persisted(record.receipt_path):
            raise VerticalProofError("VERTICAL_PROOF_RECEIPT_VERIFY_FAILED")
        return str(record.receipt_path.resolve())

    def run(
        self,
        *,
        source_audio: Path | str,
        proof_id: str,
    ) -> dict[str, Any]:
        proof = self._safe_id(proof_id)
        source = self._source_audio(source_audio)
        receipts: list[str] = []
        receipt_step = 0

        initial_snapshot = self.client.snapshot(
            task_id=f"{proof}-snapshot-initial",
            request_id=f"{proof}-snapshot-initial",
            idempotency_key=f"{proof}-snapshot-initial",
        )
        original_project_identity = initial_snapshot.project_identity
        isolated_fixture = False
        fixture_open_receipt: str | None = None

        raw_initial_project = (
            initial_snapshot.project_path or initial_snapshot.project_identity
        )
        initial_inside_fixture_root = False
        if isinstance(raw_initial_project, str) and raw_initial_project.strip():
            try:
                Path(raw_initial_project).expanduser().resolve().relative_to(
                    self.fixture_root
                )
                initial_inside_fixture_root = True
            except ValueError:
                initial_inside_fixture_root = False

        if initial_inside_fixture_root:
            snapshot = initial_snapshot
            fixture = ensure_disposable_fixture(
                snapshot,
                fixture_root=self.fixture_root,
            )
        else:
            fixture_id = proof[:64]
            open_task = f"{proof}-fixture-open"
            open_request = open_task
            open_method = getattr(self.client, "open_fixture", None)

            if callable(open_method):
                opened = open_method(
                    fixture_id=fixture_id,
                    task_id=open_task,
                    request_id=open_request,
                    idempotency_key=open_request,
                )
                if not isinstance(opened, Mapping):
                    raise VerticalProofError(
                        "VERTICAL_PROOF_FIXTURE_OPEN_MALFORMED"
                    )
                fixture_value = opened.get("fixture_project")
                fixture_state_value = opened.get(
                    "fixture_project_state_change_count"
                )
                if (
                    not isinstance(fixture_value, str)
                    or not fixture_value.strip()
                    or not isinstance(fixture_state_value, int)
                    or fixture_state_value < 0
                ):
                    raise VerticalProofError(
                        "VERTICAL_PROOF_FIXTURE_OPEN_MALFORMED"
                    )
                fixture_path_from_open = Path(fixture_value).resolve()
                open_before = initial_snapshot.project_state_change_count
                open_after = fixture_state_value
            else:
                raw_open = self.client.execute_bound_operation(
                    task_id=open_task,
                    request_id=open_request,
                    idempotency_key=open_request,
                    operation="session.fixture.open",
                    arguments={"fixture_id": fixture_id},
                    expected_project_identity=original_project_identity,
                    expected_project_state_change_count=(
                        initial_snapshot.project_state_change_count
                    ),
                )
                open_before, open_after = self._response_state(
                    raw_open,
                    expected_before=initial_snapshot.project_state_change_count,
                )
                open_result = raw_open.get("result")
                if not isinstance(open_result, Mapping):
                    raise VerticalProofError(
                        "VERTICAL_PROOF_FIXTURE_OPEN_MALFORMED"
                    )
                fixture_value = open_result.get("fixture_project")
                if not isinstance(fixture_value, str) or not fixture_value.strip():
                    raise VerticalProofError(
                        "VERTICAL_PROOF_FIXTURE_OPEN_MALFORMED"
                    )
                fixture_path_from_open = Path(fixture_value).resolve()

            expected_fixture_path = (
                self.fixture_root / f"{fixture_id}.rpp"
            ).resolve()
            if fixture_path_from_open != expected_fixture_path:
                raise VerticalProofError(
                    "VERTICAL_PROOF_FIXTURE_OPEN_OUTSIDE_ROOT"
                )

            receipt_step += 1
            fixture_open_receipt = self._persist_receipt(
                proof_id=proof,
                step=receipt_step,
                capability="session.fixture.open",
                task_id=open_task,
                project_identity=original_project_identity,
                state_before=open_before,
                state_after=open_after,
                idempotency_key=open_request,
            )
            receipts.append(fixture_open_receipt)
            isolated_fixture = True

            snapshot = self.client.snapshot(
                task_id=f"{proof}-snapshot-fixture",
                request_id=f"{proof}-snapshot-fixture",
                idempotency_key=f"{proof}-snapshot-fixture",
            )
            fixture = ensure_disposable_fixture(
                snapshot,
                fixture_root=self.fixture_root,
            )
            if fixture != expected_fixture_path:
                raise VerticalProofError(
                    "VERTICAL_PROOF_FIXTURE_IDENTITY_MISMATCH"
                )
            if snapshot.project_state_change_count != open_after:
                raise VerticalProofError(
                    "VERTICAL_PROOF_FIXTURE_STATE_MISMATCH"
                )

        project_identity = snapshot.project_identity
        state = snapshot.project_state_change_count

        def execute(
            *,
            label: str,
            operation: str,
            arguments: Mapping[str, Any],
            artifact_paths: tuple[Path, ...] = (),
            task_id: str | None = None,
            request_id: str | None = None,
        ) -> Mapping[str, Any]:
            nonlocal state, receipt_step
            task = task_id or f"{proof}-{label}"
            request = request_id or f"{proof}-{label}"
            idem = request
            response = self.client.execute_bound_operation(
                task_id=task,
                request_id=request,
                idempotency_key=idem,
                operation=operation,
                arguments=dict(arguments),
                expected_project_identity=project_identity,
                expected_project_state_change_count=state,
            )
            before_count, after_count = self._response_state(
                response,
                expected_before=state,
            )
            receipt_step += 1
            receipts.append(
                self._persist_receipt(
                    proof_id=proof,
                    step=receipt_step,
                    capability=operation,
                    task_id=task,
                    project_identity=project_identity,
                    state_before=before_count,
                    state_after=after_count,
                    idempotency_key=idem,
                    artifact_paths=artifact_paths,
                )
            )
            state = after_count
            return response

        checkpoint_response = execute(
            label="checkpoint",
            operation="session.checkpoint",
            arguments={},
        )
        checkpoint_result = checkpoint_response.get("result")
        if not isinstance(checkpoint_result, Mapping):
            raise VerticalProofError("VERTICAL_PROOF_CHECKPOINT_MALFORMED")
        checkpoint_path = Path(
            str(checkpoint_result.get("checkpoint_path") or "")
        ).expanduser().resolve()
        if not checkpoint_path.is_file() or checkpoint_path.stat().st_size <= 0:
            raise VerticalProofError("VERTICAL_PROOF_CHECKPOINT_MISSING")
        # Checkpoint receipt above has already been created; bind the actual
        # checkpoint artifact in an additional immutable evidence receipt.
        receipt_step += 1
        receipts.append(
            self._persist_receipt(
                proof_id=proof,
                step=receipt_step,
                capability="session.checkpoint",
                task_id=f"{proof}-checkpoint-artifact",
                project_identity=project_identity,
                state_before=state,
                state_after=state,
                idempotency_key=f"{proof}-checkpoint-artifact",
                artifact_paths=(checkpoint_path,),
            )
        )

        source_track_response = execute(
            label="source-track",
            operation="track.create",
            arguments={"name": "Hazewave Proof Source"},
        )
        source_track_result = source_track_response.get("result")
        if not isinstance(source_track_result, Mapping):
            raise VerticalProofError("VERTICAL_PROOF_SOURCE_TRACK_MALFORMED")
        source_track_index = int(source_track_result["track_index"])

        execute(
            label="import",
            operation="audio.import",
            arguments={
                "track_index": source_track_index,
                "source_path": str(source),
                "position": 0.0,
            },
            artifact_paths=(source,),
        )

        bus_response = execute(
            label="bus",
            operation="routing.bus",
            arguments={
                "name": "Hazewave Proof Tape Echo Return",
                "source_track_indices": [],
            },
        )
        bus_result = bus_response.get("result")
        if not isinstance(bus_result, Mapping):
            raise VerticalProofError("VERTICAL_PROOF_BUS_MALFORMED")
        bus_index = int(bus_result["bus_index"])
        bus_guid = str(bus_result.get("bus_guid") or "")
        if not bus_guid:
            raise VerticalProofError("VERTICAL_PROOF_BUS_GUID_MISSING")

        execute(
            label="send",
            operation="routing.send",
            arguments={
                "source_track_index": source_track_index,
                "destination_track_index": bus_index,
                "gain": 1.0,
                "pan": 0.0,
                "mute": 0,
                "mode": 0,
            },
        )

        add_response = execute(
            label="fx-add",
            operation="fx.add",
            arguments={
                "track_index": bus_index,
                "plugin_identity": "VST3: Tape Echo 2",
            },
        )
        add_result = add_response.get("result")
        if not isinstance(add_result, Mapping):
            raise VerticalProofError("VERTICAL_PROOF_FX_ADD_MALFORMED")
        fx_index = int(add_result["fx_index"])

        inventory_response = execute(
            label="fx-inventory",
            operation="fx.inventory",
            arguments={},
        )
        inventory_result = inventory_response.get("result")
        raw_fx = (
            inventory_result.get("fx")
            if isinstance(inventory_result, Mapping)
            else None
        )
        if not isinstance(raw_fx, (list, tuple)):
            raise VerticalProofError("VERTICAL_PROOF_FX_INVENTORY_MALFORMED")
        matching_fx = [
            item
            for item in raw_fx
            if isinstance(item, Mapping)
            and int(item.get("fx_index", -1)) == fx_index
            and (
                str(item.get("track_guid") or "") == bus_guid
                or not str(item.get("track_guid") or "")
            )
            and "tape echo 2" in str(item.get("name") or "").casefold()
        ]
        if len(matching_fx) != 1:
            raise VerticalProofError("VERTICAL_PROOF_TAPE_ECHO_IDENTITY_AMBIGUOUS")
        semantics = discover_tape_echo_2_semantics(matching_fx[0])

        baseline_values: dict[str, float] = {}
        for role in ("repeat_rate", "intensity", "echo_volume", "mix"):
            semantic = semantics.parameters[role]
            target = float(self.BASELINE_PARAMETERS[role])
            if target < semantic.minimum or target > semantic.maximum:
                raise VerticalProofError(
                    f"VERTICAL_PROOF_BASELINE_OUT_OF_RANGE:{role}"
                )
            execute(
                label=f"baseline-{role}",
                operation="fx.parameter.write",
                arguments={
                    "track_index": bus_index,
                    "fx_index": semantics.fx_index,
                    "parameter_index": semantic.index,
                    "expected_parameter_name": semantic.name,
                    "normalized_value": target,
                },
            )
            baseline_values[role] = target

        def render(label: str) -> dict[str, Any]:
            nonlocal state, receipt_step
            task = f"{proof}-{label}"
            request = f"{proof}-{label}"
            audition = self.client.render_preview_bound(
                task_id=task,
                request_id=request,
                idempotency_key=request,
                expected_project_identity=project_identity,
                expected_project_state_change_count=state,
            )
            try:
                before_count = int(audition["state_before"])
                after_count = int(audition["state_after"])
            except (KeyError, TypeError, ValueError) as exc:
                raise VerticalProofError("VERTICAL_PROOF_RENDER_STATE_MALFORMED") from exc
            if before_count != state:
                raise VerticalProofError("VERTICAL_PROOF_STATE_CHAIN_BROKEN")
            artifact = Path(str(audition.get("artifact_path") or "")).resolve()
            if not artifact.is_file() or artifact.stat().st_size <= 0:
                raise VerticalProofError("VERTICAL_PROOF_RENDER_ARTIFACT_MISSING")
            qc_payload = audition.get("audio_qc")
            qc = _audio_qc_from_mapping(qc_payload)
            receipt_step += 1
            receipts.append(
                self._persist_receipt(
                    proof_id=proof,
                    step=receipt_step,
                    capability="render.preview",
                    task_id=task,
                    project_identity=project_identity,
                    state_before=before_count,
                    state_after=after_count,
                    idempotency_key=request,
                    artifact_paths=(artifact,),
                )
            )
            state = after_count
            result = dict(audition)
            result["audio_qc"] = qc.to_dict()
            return result

        render_a = render("render-a")
        qc_a = _audio_qc_from_mapping(render_a["audio_qc"])

        adjustment = select_fixture_adjustment(
            qc_a,
            current_echo_volume=baseline_values["echo_volume"],
            current_intensity=baseline_values["intensity"],
        )
        adjustment_semantic = semantics.parameters[adjustment.parameter_role]
        adjustment_request_id = f"{proof}-adjustment-write"
        execute(
            label="adjustment",
            operation="fx.parameter.write",
            arguments={
                "track_index": bus_index,
                "fx_index": semantics.fx_index,
                "parameter_index": adjustment_semantic.index,
                "expected_parameter_name": adjustment_semantic.name,
                "normalized_value": adjustment.new_normalized_value,
            },
            task_id=f"{proof}-adjustment",
            request_id=adjustment_request_id,
        )

        render_b = render("render-b")
        qc_b = _audio_qc_from_mapping(render_b["audio_qc"])

        expected_undo_description = (
            f"Hazewave: fx.parameter.write [{adjustment_request_id}]"
        )
        rollback_response = execute(
            label="rollback",
            operation="session.rollback",
            arguments={
                "expected_undo_description": expected_undo_description,
            },
        )
        rollback_result = rollback_response.get("result")
        if not isinstance(rollback_result, Mapping):
            raise VerticalProofError("VERTICAL_PROOF_ROLLBACK_MALFORMED")
        if rollback_result.get("undone_description") != expected_undo_description:
            raise VerticalProofError("VERTICAL_PROOF_ROLLBACK_UNDO_MISMATCH")

        read_response = execute(
            label="rollback-readback",
            operation="fx.parameter.read",
            arguments={
                "track_index": bus_index,
                "fx_index": semantics.fx_index,
                "parameter_index": adjustment_semantic.index,
            },
        )
        read_result = read_response.get("result")
        if not isinstance(read_result, Mapping):
            raise VerticalProofError("VERTICAL_PROOF_ROLLBACK_READBACK_MALFORMED")
        if str(read_result.get("name") or "") != adjustment_semantic.name:
            raise VerticalProofError("VERTICAL_PROOF_ROLLBACK_PARAMETER_MISMATCH")
        try:
            restored = float(read_result["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise VerticalProofError(
                "VERTICAL_PROOF_ROLLBACK_READBACK_MALFORMED"
            ) from exc
        expected_restored = baseline_values[adjustment.parameter_role]
        if abs(restored - expected_restored) > 1e-6:
            raise VerticalProofError("VERTICAL_PROOF_ROLLBACK_NOT_RESTORED")

        restored_project_identity = project_identity
        original_project_restored = not isolated_fixture
        fixture_close_receipt: str | None = None

        if isolated_fixture:
            close_task = f"{proof}-fixture-close"
            close_request = close_task
            close_before = state
            close_method = getattr(self.client, "close_fixture", None)
            if callable(close_method):
                closed = close_method(
                    task_id=close_task,
                    request_id=close_request,
                    idempotency_key=close_request,
                )
                if not isinstance(closed, Mapping):
                    raise VerticalProofError(
                        "VERTICAL_PROOF_FIXTURE_CLOSE_MALFORMED"
                    )
                restored_value = closed.get("restored_project_identity")
                restored_state_value = closed.get(
                    "restored_project_state_change_count"
                )
                if (
                    not isinstance(restored_value, str)
                    or not isinstance(restored_state_value, int)
                    or restored_state_value < 0
                ):
                    raise VerticalProofError(
                        "VERTICAL_PROOF_FIXTURE_CLOSE_MALFORMED"
                    )
                restored_project_identity = restored_value
                close_after = restored_state_value
            else:
                raw_close = self.client.execute_bound_operation(
                    task_id=close_task,
                    request_id=close_request,
                    idempotency_key=close_request,
                    operation="session.fixture.close",
                    arguments={},
                    expected_project_identity=project_identity,
                    expected_project_state_change_count=state,
                )
                _, close_after = self._response_state(
                    raw_close,
                    expected_before=state,
                )
                close_result = raw_close.get("result")
                if not isinstance(close_result, Mapping):
                    raise VerticalProofError(
                        "VERTICAL_PROOF_FIXTURE_CLOSE_MALFORMED"
                    )
                restored_value = close_result.get("restored_project_identity")
                if not isinstance(restored_value, str):
                    raise VerticalProofError(
                        "VERTICAL_PROOF_FIXTURE_CLOSE_MALFORMED"
                    )
                restored_project_identity = restored_value

            if restored_project_identity != original_project_identity:
                raise VerticalProofError(
                    "VERTICAL_PROOF_ORIGINAL_PROJECT_NOT_RESTORED"
                )
            receipt_step += 1
            fixture_close_receipt = self._persist_receipt(
                proof_id=proof,
                step=receipt_step,
                capability="session.fixture.close",
                task_id=close_task,
                project_identity=project_identity,
                state_before=close_before,
                state_after=close_after,
                idempotency_key=close_request,
            )
            receipts.append(fixture_close_receipt)
            original_project_restored = True

        return {
            "schema": "ReaperLiveVerticalProof/v1",
            "status": "PASS",
            "authority": "HAZEWAVE_HARNESS",
            "portfolio_authority": "NONE",
            "fixture_project": str(fixture),
            "fixture_session": {
                "isolated": isolated_fixture,
                "original_project_identity": original_project_identity,
                "original_project_restored": original_project_restored,
                "restored_project_identity": restored_project_identity,
                "open_receipt": fixture_open_receipt,
                "close_receipt": fixture_close_receipt,
            },
            "source_audio": str(source),
            "checkpoint_path": str(checkpoint_path),
            "plugin": {
                "name": semantics.name,
                "version": self.tape_echo_version,
                "fx_guid": semantics.fx_guid,
                "fx_index": semantics.fx_index,
                "runtime_parameter_names": {
                    role: semantics.parameters[role].name
                    for role in _CANONICAL_PARAMETER_NAMES
                },
            },
            "baseline": dict(baseline_values),
            "render_a": render_a,
            "adjustment": asdict(adjustment),
            "render_b": render_b,
            "rollback": {
                "proven": True,
                "expected_undo_description": expected_undo_description,
                "restored_parameter_role": adjustment.parameter_role,
                "restored_parameter_name": adjustment_semantic.name,
                "restored_normalized_value": restored,
            },
            "technical_comparison": {
                "render_a_true_peak_dbfs": qc_a.true_peak_dbfs,
                "render_b_true_peak_dbfs": qc_b.true_peak_dbfs,
                "render_a_integrated_lufs": qc_a.integrated_lufs,
                "render_b_integrated_lufs": qc_b.integrated_lufs,
                "artistic_verdict": "HUMAN_REVIEW_REQUIRED",
            },
            "durable_receipts": receipts,
            "human_approval": "REQUIRED",
        }
