from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Final, Mapping


FREE_COST_CLASSES: Final[frozenset[str]] = frozenset(
    {"FREE_OPEN_SOURCE", "FREEWARE_NO_PAYMENT"}
)
NATIVE_LINUX_FORMATS: Final[frozenset[str]] = frozenset(
    {"VST3", "CLAP", "LV2", "JSFX"}
)
QUALIFICATION_STATUSES: Final[frozenset[str]] = frozenset(
    {
        "DISCOVERED",
        "COMPATIBLE",
        "RUNTIME_PROVEN",
        "PRODUCTION_APPROVED",
        "QUARANTINED",
        "DEPRECATED",
    }
)
MANDATORY_RUNTIME_CHECKS: Final[tuple[str, ...]] = (
    "official_source_provenance",
    "download_digest_verified",
    "license_cost_verified",
    "linux_x86_64_compatible",
    "reaper_discovery",
    "instantiation",
    "save_reload_recall",
    "parameter_enumeration",
    "parameter_automation",
    "preset_recall",
    "mono_behavior",
    "stereo_behavior",
    "sample_rate_behavior",
    "offline_render",
    "latency_pdc",
    "cpu_memory_measured",
    "crash_isolation",
    "silence_behavior",
    "denormal_behavior",
    "oversampling_behavior",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PluginLabError(RuntimeError):
    pass


@dataclass(frozen=True)
class PluginDescriptor:
    plugin_id: str
    name: str
    vendor: str
    format: str
    version: str
    platform: str
    architecture: str
    cost_class: str
    license_id: str
    source_url: str
    download_sha256: str
    schema: str = "PluginDescriptor/v1"

    def __post_init__(self) -> None:
        for field_name in (
            "plugin_id",
            "name",
            "vendor",
            "format",
            "version",
            "platform",
            "architecture",
            "cost_class",
            "license_id",
            "source_url",
        ):
            if not str(getattr(self, field_name) or "").strip():
                raise PluginLabError(f"PLUGIN_DESCRIPTOR_FIELD_REQUIRED:{field_name}")
        if not _SHA256_RE.fullmatch(self.download_sha256):
            raise PluginLabError("PLUGIN_DESCRIPTOR_SHA256_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PluginSemanticParameter:
    index: int
    display_name: str
    semantic_role: str
    normalized_min: float
    normalized_max: float
    schema: str = "PluginSemanticParameter/v1"

    def __post_init__(self) -> None:
        if self.index < 0:
            raise PluginLabError("PLUGIN_PARAMETER_INDEX_INVALID")
        if not self.display_name.strip() or not self.semantic_role.strip():
            raise PluginLabError("PLUGIN_PARAMETER_IDENTITY_REQUIRED")
        if not 0.0 <= self.normalized_min <= self.normalized_max <= 1.0:
            raise PluginLabError("PLUGIN_PARAMETER_RANGE_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PluginSemanticProfile:
    plugin_id: str
    plugin_version: str
    parameters: tuple[PluginSemanticParameter, ...]
    presets: tuple[str, ...]
    role_tags: tuple[str, ...]
    schema: str = "PluginSemanticProfile/v1"

    def __post_init__(self) -> None:
        if not self.plugin_id.strip() or not self.plugin_version.strip():
            raise PluginLabError("PLUGIN_SEMANTIC_IDENTITY_REQUIRED")
        indices = [item.index for item in self.parameters]
        if len(indices) != len(set(indices)):
            raise PluginLabError("PLUGIN_SEMANTIC_DUPLICATE_PARAMETER_INDEX")
        roles = [item.semantic_role for item in self.parameters]
        if len(roles) != len(set(roles)):
            raise PluginLabError("PLUGIN_SEMANTIC_DUPLICATE_ROLE")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["parameters"] = [item.to_dict() for item in self.parameters]
        value["presets"] = list(self.presets)
        value["role_tags"] = list(self.role_tags)
        return value


@dataclass(frozen=True)
class PluginBenchmark:
    plugin_id: str
    plugin_version: str
    sample_rate: int
    block_size: int
    cpu_percent: float
    memory_mb: float
    latency_samples: int
    pdc_reported_samples: int
    offline_render_realtime_ratio: float
    schema: str = "PluginBenchmark/v1"

    def __post_init__(self) -> None:
        if not self.plugin_id.strip() or not self.plugin_version.strip():
            raise PluginLabError("PLUGIN_BENCHMARK_IDENTITY_REQUIRED")
        if self.sample_rate <= 0 or self.block_size <= 0:
            raise PluginLabError("PLUGIN_BENCHMARK_AUDIO_CONFIG_INVALID")
        if (
            self.cpu_percent < 0
            or self.memory_mb < 0
            or self.latency_samples < 0
            or self.pdc_reported_samples < 0
            or self.offline_render_realtime_ratio <= 0
        ):
            raise PluginLabError("PLUGIN_BENCHMARK_METRIC_INVALID")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PluginRoleProfile:
    plugin_id: str
    plugin_version: str
    roles: tuple[str, ...]
    character_tags: tuple[str, ...]
    transparent: bool
    tempo_sync: bool
    stereo: bool
    automation_quality: str
    schema: str = "PluginRoleProfile/v1"

    def __post_init__(self) -> None:
        if not self.plugin_id.strip() or not self.plugin_version.strip():
            raise PluginLabError("PLUGIN_ROLE_IDENTITY_REQUIRED")
        if not self.roles or not all(str(role).strip() for role in self.roles):
            raise PluginLabError("PLUGIN_ROLE_REQUIRED")
        if not self.automation_quality.strip():
            raise PluginLabError("PLUGIN_AUTOMATION_QUALITY_REQUIRED")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["roles"] = list(self.roles)
        value["character_tags"] = list(self.character_tags)
        return value


@dataclass(frozen=True)
class PluginQualificationReceipt:
    plugin_id: str
    plugin_version: str
    status: str
    runtime_identity: str
    reaper_version: str
    evidence_digest: str
    checks: Mapping[str, bool]
    failed_checks: tuple[str, ...]
    runtime_proven: bool
    production_approved: bool
    free_plugin_policy: str
    native_linux_plugin_policy: str
    schema: str = "PluginQualificationReceipt/v1"

    def __post_init__(self) -> None:
        if self.status not in QUALIFICATION_STATUSES:
            raise PluginLabError("PLUGIN_QUALIFICATION_STATUS_INVALID")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["checks"] = dict(self.checks)
        value["failed_checks"] = list(self.failed_checks)
        return value


@dataclass(frozen=True)
class ProductionBrief:
    capability: str
    required_role: str
    desired_character_tags: tuple[str, ...]
    prefer_transparent: bool
    max_cpu_percent: float
    max_latency_samples: int
    schema: str = "ProductionBrief/v1"

    def __post_init__(self) -> None:
        if not self.capability.strip() or not self.required_role.strip():
            raise PluginLabError("PLUGIN_SELECTION_BRIEF_INVALID")
        if self.max_cpu_percent < 0 or self.max_latency_samples < 0:
            raise PluginLabError("PLUGIN_SELECTION_BUDGET_INVALID")


@dataclass(frozen=True)
class ToolSelectionDecision:
    capability: str
    required_role: str
    selected_plugin_id: str
    selected_plugin_version: str
    candidate_plugin_ids: tuple[str, ...]
    desired_character_tags: tuple[str, ...]
    matched_character_tags: tuple[str, ...]
    cpu_percent: float
    latency_samples: int
    reason: str
    production_approved_only: bool = True
    schema: str = "ToolSelectionDecision/v1"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["candidate_plugin_ids"] = list(self.candidate_plugin_ids)
        value["desired_character_tags"] = list(self.desired_character_tags)
        value["matched_character_tags"] = list(self.matched_character_tags)
        return value


class PluginQualificationLab:
    def __init__(self) -> None:
        self._descriptors: dict[str, PluginDescriptor] = {}
        self._semantics: dict[str, PluginSemanticProfile] = {}
        self._roles: dict[str, PluginRoleProfile] = {}
        self._benchmarks: dict[str, PluginBenchmark] = {}
        self._qualifications: dict[str, PluginQualificationReceipt] = {}

    def register(self, descriptor: PluginDescriptor) -> None:
        current = self._descriptors.get(descriptor.plugin_id)
        self._descriptors[descriptor.plugin_id] = descriptor
        if current is not None and current.version != descriptor.version:
            self._semantics.pop(descriptor.plugin_id, None)
            self._roles.pop(descriptor.plugin_id, None)
            self._benchmarks.pop(descriptor.plugin_id, None)
            self._qualifications.pop(descriptor.plugin_id, None)

    def _descriptor(self, plugin_id: str, plugin_version: str) -> PluginDescriptor:
        descriptor = self._descriptors.get(plugin_id)
        if descriptor is None:
            raise PluginLabError(f"PLUGIN_NOT_REGISTERED:{plugin_id}")
        if descriptor.version != plugin_version:
            raise PluginLabError("PLUGIN_VERSION_MISMATCH")
        return descriptor

    def bind_semantics(self, profile: PluginSemanticProfile) -> None:
        self._descriptor(profile.plugin_id, profile.plugin_version)
        self._semantics[profile.plugin_id] = profile
        self._qualifications.pop(profile.plugin_id, None)

    def bind_role_profile(self, profile: PluginRoleProfile) -> None:
        self._descriptor(profile.plugin_id, profile.plugin_version)
        self._roles[profile.plugin_id] = profile
        self._qualifications.pop(profile.plugin_id, None)

    def bind_benchmark(self, benchmark: PluginBenchmark) -> None:
        self._descriptor(benchmark.plugin_id, benchmark.plugin_version)
        self._benchmarks[benchmark.plugin_id] = benchmark
        self._qualifications.pop(benchmark.plugin_id, None)

    @staticmethod
    def _free_policy(descriptor: PluginDescriptor) -> bool:
        return descriptor.cost_class in FREE_COST_CLASSES

    @staticmethod
    def _native_policy(descriptor: PluginDescriptor) -> bool:
        return (
            descriptor.platform.casefold() == "linux"
            and descriptor.architecture.casefold() in {"x86_64", "amd64"}
            and descriptor.format.upper() in NATIVE_LINUX_FORMATS
        )

    def qualify_runtime(
        self,
        *,
        plugin_id: str,
        plugin_version: str,
        checks: Mapping[str, bool],
        runtime_identity: str,
        reaper_version: str,
        evidence_digest: str,
    ) -> PluginQualificationReceipt:
        descriptor = self._descriptor(plugin_id, plugin_version)
        if not isinstance(checks, Mapping):
            raise PluginLabError("PLUGIN_QUALIFICATION_CHECKS_INVALID")
        if not str(runtime_identity or "").strip():
            raise PluginLabError("PLUGIN_QUALIFICATION_RUNTIME_REQUIRED")
        if not str(reaper_version or "").strip():
            raise PluginLabError("PLUGIN_QUALIFICATION_REAPER_VERSION_REQUIRED")
        if not _SHA256_RE.fullmatch(str(evidence_digest or "")):
            raise PluginLabError("PLUGIN_QUALIFICATION_EVIDENCE_DIGEST_INVALID")

        normalized_checks: dict[str, bool] = {}
        for key in MANDATORY_RUNTIME_CHECKS:
            value = checks.get(key, False)
            if not isinstance(value, bool):
                raise PluginLabError(f"PLUGIN_QUALIFICATION_CHECK_INVALID:{key}")
            normalized_checks[key] = value

        failed = tuple(
            key for key in MANDATORY_RUNTIME_CHECKS if not normalized_checks[key]
        )
        runtime_proven = not failed
        free_policy = self._free_policy(descriptor)
        native_policy = self._native_policy(descriptor)
        profiles_bound = (
            plugin_id in self._semantics
            and plugin_id in self._roles
            and plugin_id in self._benchmarks
        )

        if not free_policy or not native_policy:
            status = "QUARANTINED"
            approved = False
        elif runtime_proven and profiles_bound:
            status = "PRODUCTION_APPROVED"
            approved = True
        elif runtime_proven:
            status = "RUNTIME_PROVEN"
            approved = False
        else:
            status = "COMPATIBLE"
            approved = False

        receipt = PluginQualificationReceipt(
            plugin_id=plugin_id,
            plugin_version=plugin_version,
            status=status,
            runtime_identity=str(runtime_identity).strip(),
            reaper_version=str(reaper_version).strip(),
            evidence_digest=str(evidence_digest),
            checks=normalized_checks,
            failed_checks=failed,
            runtime_proven=runtime_proven,
            production_approved=approved,
            free_plugin_policy="PASS" if free_policy else "FAIL",
            native_linux_plugin_policy="PASS" if native_policy else "FAIL",
        )
        self._qualifications[plugin_id] = receipt
        return receipt

    def production_eligible(self, plugin_id: str) -> bool:
        descriptor = self._descriptors.get(plugin_id)
        qualification = self._qualifications.get(plugin_id)
        semantics = self._semantics.get(plugin_id)
        roles = self._roles.get(plugin_id)
        benchmark = self._benchmarks.get(plugin_id)
        if None in (descriptor, qualification, semantics, roles, benchmark):
            return False
        assert descriptor is not None
        assert qualification is not None
        assert semantics is not None
        assert roles is not None
        assert benchmark is not None
        return (
            qualification.production_approved
            and qualification.status == "PRODUCTION_APPROVED"
            and qualification.plugin_version == descriptor.version
            and semantics.plugin_version == descriptor.version
            and roles.plugin_version == descriptor.version
            and benchmark.plugin_version == descriptor.version
            and self._free_policy(descriptor)
            and self._native_policy(descriptor)
        )

    def registry_snapshot(self) -> dict[str, Any]:
        plugins: list[dict[str, Any]] = []
        for plugin_id in sorted(self._descriptors):
            descriptor = self._descriptors[plugin_id]
            semantic = self._semantics.get(plugin_id)
            role = self._roles.get(plugin_id)
            benchmark = self._benchmarks.get(plugin_id)
            qualification = self._qualifications.get(plugin_id)
            plugins.append(
                {
                    **descriptor.to_dict(),
                    "semantic_profile": (
                        semantic.to_dict()
                        if semantic is not None
                        and semantic.plugin_version == descriptor.version
                        else None
                    ),
                    "role_profile": (
                        role.to_dict()
                        if role is not None
                        and role.plugin_version == descriptor.version
                        else None
                    ),
                    "benchmark": (
                        benchmark.to_dict()
                        if benchmark is not None
                        and benchmark.plugin_version == descriptor.version
                        else None
                    ),
                    "qualification": (
                        qualification.to_dict()
                        if qualification is not None
                        and qualification.plugin_version == descriptor.version
                        else None
                    ),
                }
            )
        return {
            "schema": "PluginRegistry/v1",
            "authority": "NONE",
            "grants_execution_authority": False,
            "production_policy": {
                "free_cost_classes": sorted(FREE_COST_CLASSES),
                "native_linux_formats": sorted(NATIVE_LINUX_FORMATS),
                "paid_fallback": "FORBIDDEN",
                "unknown_cost": "DENY",
            },
            "plugins": plugins,
        }

    def select_tool(self, brief: ProductionBrief) -> ToolSelectionDecision:
        candidates: list[tuple[float, str, PluginDescriptor, PluginRoleProfile, PluginBenchmark]] = []
        desired = {tag.casefold() for tag in brief.desired_character_tags}

        for plugin_id, descriptor in self._descriptors.items():
            if not self.production_eligible(plugin_id):
                continue
            role = self._roles[plugin_id]
            benchmark = self._benchmarks[plugin_id]
            if brief.required_role not in role.roles:
                continue
            if benchmark.cpu_percent > brief.max_cpu_percent:
                continue
            if benchmark.latency_samples > brief.max_latency_samples:
                continue

            tags = {tag.casefold() for tag in role.character_tags}
            matched_count = len(desired.intersection(tags))
            score = float(matched_count * 20)
            if role.transparent == brief.prefer_transparent:
                score += 10.0
            if role.tempo_sync:
                score += 2.0
            if role.stereo:
                score += 1.0
            score += max(0.0, brief.max_cpu_percent - benchmark.cpu_percent) * 0.01
            candidates.append((score, plugin_id, descriptor, role, benchmark))

        if not candidates:
            raise PluginLabError("PLUGIN_SELECTION_NO_ELIGIBLE_CANDIDATE")

        candidates.sort(key=lambda item: (-item[0], item[1]))
        _, plugin_id, descriptor, role, benchmark = candidates[0]
        desired_original = tuple(brief.desired_character_tags)
        role_tags_by_casefold = {
            tag.casefold(): tag for tag in role.character_tags
        }
        matched = tuple(
            role_tags_by_casefold[tag.casefold()]
            for tag in desired_original
            if tag.casefold() in role_tags_by_casefold
        )

        return ToolSelectionDecision(
            capability=brief.capability,
            required_role=brief.required_role,
            selected_plugin_id=plugin_id,
            selected_plugin_version=descriptor.version,
            candidate_plugin_ids=tuple(item[1] for item in candidates),
            desired_character_tags=desired_original,
            matched_character_tags=matched,
            cpu_percent=benchmark.cpu_percent,
            latency_samples=benchmark.latency_samples,
            reason=(
                "Selected only from PRODUCTION_APPROVED zero-cost native Linux "
                "plugins after role, character, CPU, latency, transparency, "
                "tempo-sync and stereo constraints."
            ),
        )
