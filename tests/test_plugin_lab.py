from __future__ import annotations

from dataclasses import replace

import pytest

from hazewave.plugin_lab import (
    PluginBenchmark,
    PluginDescriptor,
    PluginLabError,
    PluginQualificationLab,
    PluginRoleProfile,
    PluginSemanticParameter,
    PluginSemanticProfile,
    ProductionBrief,
)


def _descriptor(
    *,
    plugin_id: str = "tape-echo-2",
    version: str = "1.0.8",
    cost_class: str = "FREEWARE_NO_PAYMENT",
    format: str = "VST3",
) -> PluginDescriptor:
    return PluginDescriptor(
        plugin_id=plugin_id,
        name="Tape Echo 2",
        vendor="Steinberg Media Technologies GmbH",
        format=format,
        version=version,
        platform="linux",
        architecture="x86_64",
        cost_class=cost_class,
        license_id="FREEWARE",
        source_url="https://example.invalid/tape-echo-2",
        download_sha256="a" * 64,
    )


def _semantic(plugin_id: str = "tape-echo-2", version: str = "1.0.8") -> PluginSemanticProfile:
    return PluginSemanticProfile(
        plugin_id=plugin_id,
        plugin_version=version,
        parameters=(
            PluginSemanticParameter(
                index=0,
                display_name="Mix",
                semantic_role="mix",
                normalized_min=0.0,
                normalized_max=1.0,
            ),
            PluginSemanticParameter(
                index=1,
                display_name="Feedback",
                semantic_role="feedback",
                normalized_min=0.0,
                normalized_max=0.82,
            ),
        ),
        presets=("Default",),
        role_tags=("delay", "dub_delay", "colored"),
    )


def _role(plugin_id: str = "tape-echo-2", version: str = "1.0.8") -> PluginRoleProfile:
    return PluginRoleProfile(
        plugin_id=plugin_id,
        plugin_version=version,
        roles=("delay", "dub_delay"),
        character_tags=("warm", "colored", "feedback-performance"),
        transparent=False,
        tempo_sync=True,
        stereo=True,
        automation_quality="GOOD",
    )


def _benchmark(plugin_id: str = "tape-echo-2", version: str = "1.0.8") -> PluginBenchmark:
    return PluginBenchmark(
        plugin_id=plugin_id,
        plugin_version=version,
        sample_rate=48000,
        block_size=512,
        cpu_percent=3.2,
        memory_mb=84.0,
        latency_samples=0,
        pdc_reported_samples=0,
        offline_render_realtime_ratio=8.5,
    )


def _all_runtime_checks() -> dict[str, bool]:
    return {
        "official_source_provenance": True,
        "download_digest_verified": True,
        "license_cost_verified": True,
        "linux_x86_64_compatible": True,
        "reaper_discovery": True,
        "instantiation": True,
        "save_reload_recall": True,
        "parameter_enumeration": True,
        "parameter_automation": True,
        "preset_recall": True,
        "mono_behavior": True,
        "stereo_behavior": True,
        "sample_rate_behavior": True,
        "offline_render": True,
        "latency_pdc": True,
        "cpu_memory_measured": True,
        "crash_isolation": True,
        "silence_behavior": True,
        "denormal_behavior": True,
        "oversampling_behavior": True,
    }


def test_plugin_lab_materializes_version_bound_registry_and_qualification_receipt() -> None:
    lab = PluginQualificationLab()
    descriptor = _descriptor()
    lab.register(descriptor)
    lab.bind_semantics(_semantic())
    lab.bind_role_profile(_role())
    lab.bind_benchmark(_benchmark())

    receipt = lab.qualify_runtime(
        plugin_id=descriptor.plugin_id,
        plugin_version=descriptor.version,
        checks=_all_runtime_checks(),
        runtime_identity="codespace:fixture",
        reaper_version="7.82",
        evidence_digest="b" * 64,
    )

    assert lab.registry_snapshot()["schema"] == "PluginRegistry/v1"
    assert receipt.schema == "PluginQualificationReceipt/v1"
    assert receipt.status == "PRODUCTION_APPROVED"
    assert receipt.plugin_id == "tape-echo-2"
    assert receipt.plugin_version == "1.0.8"
    assert receipt.runtime_proven is True
    assert receipt.production_approved is True
    assert receipt.free_plugin_policy == "PASS"
    assert receipt.native_linux_plugin_policy == "PASS"


@pytest.mark.parametrize("cost_class", ["PAID", "UNKNOWN_COST", "FREEMIUM"])
def test_plugin_lab_never_production_approves_paid_or_uncertain_cost(cost_class: str) -> None:
    lab = PluginQualificationLab()
    descriptor = _descriptor(cost_class=cost_class)
    lab.register(descriptor)
    lab.bind_semantics(_semantic())
    lab.bind_role_profile(_role())
    lab.bind_benchmark(_benchmark())

    receipt = lab.qualify_runtime(
        plugin_id=descriptor.plugin_id,
        plugin_version=descriptor.version,
        checks=_all_runtime_checks(),
        runtime_identity="codespace:fixture",
        reaper_version="7.82",
        evidence_digest="b" * 64,
    )

    assert receipt.production_approved is False
    assert receipt.status == "QUARANTINED"
    assert receipt.free_plugin_policy == "FAIL"


def test_plugin_lab_never_production_approves_non_native_format() -> None:
    lab = PluginQualificationLab()
    descriptor = _descriptor(format="WIN_VST3")
    lab.register(descriptor)
    lab.bind_semantics(_semantic())
    lab.bind_role_profile(_role())
    lab.bind_benchmark(_benchmark())

    receipt = lab.qualify_runtime(
        plugin_id=descriptor.plugin_id,
        plugin_version=descriptor.version,
        checks=_all_runtime_checks(),
        runtime_identity="codespace:fixture",
        reaper_version="7.82",
        evidence_digest="c" * 64,
    )

    assert receipt.production_approved is False
    assert receipt.native_linux_plugin_policy == "FAIL"
    assert receipt.status == "QUARANTINED"


def test_plugin_lab_missing_runtime_gate_cannot_be_promoted() -> None:
    lab = PluginQualificationLab()
    lab.register(_descriptor())
    lab.bind_semantics(_semantic())
    lab.bind_role_profile(_role())
    lab.bind_benchmark(_benchmark())
    checks = _all_runtime_checks()
    checks["offline_render"] = False

    receipt = lab.qualify_runtime(
        plugin_id="tape-echo-2",
        plugin_version="1.0.8",
        checks=checks,
        runtime_identity="codespace:fixture",
        reaper_version="7.82",
        evidence_digest="d" * 64,
    )

    assert receipt.status == "COMPATIBLE"
    assert receipt.runtime_proven is False
    assert receipt.production_approved is False
    assert "offline_render" in receipt.failed_checks


def test_plugin_update_invalidates_semantics_benchmark_role_and_approval() -> None:
    lab = PluginQualificationLab()
    lab.register(_descriptor())
    lab.bind_semantics(_semantic())
    lab.bind_role_profile(_role())
    lab.bind_benchmark(_benchmark())
    lab.qualify_runtime(
        plugin_id="tape-echo-2",
        plugin_version="1.0.8",
        checks=_all_runtime_checks(),
        runtime_identity="codespace:fixture",
        reaper_version="7.82",
        evidence_digest="e" * 64,
    )

    lab.register(replace(_descriptor(), version="1.0.9"))

    snapshot = lab.registry_snapshot()
    item = snapshot["plugins"][0]
    assert item["version"] == "1.0.9"
    assert item["semantic_profile"] is None
    assert item["benchmark"] is None
    assert item["role_profile"] is None
    assert item["qualification"] is None
    assert lab.production_eligible("tape-echo-2") is False


def test_tool_selection_is_brief_specific_and_only_uses_production_approved_plugins() -> None:
    lab = PluginQualificationLab()

    colored = _descriptor(plugin_id="colored-delay")
    clean = replace(
        _descriptor(plugin_id="clean-delay"),
        name="Clean Delay",
        vendor="Fixture",
        download_sha256="f" * 64,
    )
    for descriptor, role, benchmark in (
        (
            colored,
            PluginRoleProfile(
                plugin_id="colored-delay",
                plugin_version="1.0.8",
                roles=("delay",),
                character_tags=("warm", "colored"),
                transparent=False,
                tempo_sync=True,
                stereo=True,
                automation_quality="GOOD",
            ),
            PluginBenchmark(
                plugin_id="colored-delay",
                plugin_version="1.0.8",
                sample_rate=48000,
                block_size=512,
                cpu_percent=4.0,
                memory_mb=90.0,
                latency_samples=0,
                pdc_reported_samples=0,
                offline_render_realtime_ratio=7.0,
            ),
        ),
        (
            clean,
            PluginRoleProfile(
                plugin_id="clean-delay",
                plugin_version="1.0.8",
                roles=("delay",),
                character_tags=("clean", "transparent"),
                transparent=True,
                tempo_sync=True,
                stereo=True,
                automation_quality="GOOD",
            ),
            PluginBenchmark(
                plugin_id="clean-delay",
                plugin_version="1.0.8",
                sample_rate=48000,
                block_size=512,
                cpu_percent=1.5,
                memory_mb=55.0,
                latency_samples=0,
                pdc_reported_samples=0,
                offline_render_realtime_ratio=12.0,
            ),
        ),
    ):
        lab.register(descriptor)
        lab.bind_semantics(
            PluginSemanticProfile(
                plugin_id=descriptor.plugin_id,
                plugin_version=descriptor.version,
                parameters=(),
                presets=(),
                role_tags=("delay",),
            )
        )
        lab.bind_role_profile(role)
        lab.bind_benchmark(benchmark)
        lab.qualify_runtime(
            plugin_id=descriptor.plugin_id,
            plugin_version=descriptor.version,
            checks=_all_runtime_checks(),
            runtime_identity="codespace:fixture",
            reaper_version="7.82",
            evidence_digest=("1" if descriptor.plugin_id == "colored-delay" else "2") * 64,
        )

    warm = lab.select_tool(
        ProductionBrief(
            capability="mix.delay",
            required_role="delay",
            desired_character_tags=("warm", "colored"),
            prefer_transparent=False,
            max_cpu_percent=5.0,
            max_latency_samples=64,
        )
    )
    transparent = lab.select_tool(
        ProductionBrief(
            capability="mix.delay",
            required_role="delay",
            desired_character_tags=("clean", "transparent"),
            prefer_transparent=True,
            max_cpu_percent=5.0,
            max_latency_samples=64,
        )
    )

    assert warm.schema == "ToolSelectionDecision/v1"
    assert warm.selected_plugin_id == "colored-delay"
    assert transparent.selected_plugin_id == "clean-delay"
    assert warm.selected_plugin_id != transparent.selected_plugin_id
    assert warm.production_approved_only is True
    assert transparent.production_approved_only is True


def test_tool_selection_fails_closed_when_no_approved_candidate_matches_budget() -> None:
    lab = PluginQualificationLab()

    with pytest.raises(PluginLabError, match="PLUGIN_SELECTION_NO_ELIGIBLE_CANDIDATE"):
        lab.select_tool(
            ProductionBrief(
                capability="mix.delay",
                required_role="delay",
                desired_character_tags=("warm",),
                prefer_transparent=False,
                max_cpu_percent=2.0,
                max_latency_samples=0,
            )
        )
