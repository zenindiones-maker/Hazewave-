from __future__ import annotations

from dataclasses import replace

import pytest

from hazewave.creative_plane import (
    ExecutionReceiptPayload,
    PluginDescriptor,
    PluginQualification,
    PluginRegistry,
    ProducerDecision,
    ProducerLoop,
    RuntimeReceiptSigner,
)


def test_receipt_attestation_binds_exact_execution_fields_and_detects_tamper() -> None:
    signer = RuntimeReceiptSigner(b"runtime-only-test-key-32-bytes-long!")
    payload = ExecutionReceiptPayload(
        project_id="HAZEWAVE",
        task_id="task-1",
        capability="mix.delay",
        domain="HAZE",
        candidate_head="abc123",
        policy_digest="policy123",
        runtime_identity="codespace-fixture",
        reaper_project_identity="/tmp/fixture.rpp",
        state_before=11,
        state_after=12,
        idempotency_key="idem-1",
        operation_result="PASS",
        artifact_hashes=("sha256:a", "sha256:b"),
    )

    receipt = signer.sign(payload)

    assert receipt.schema == "HazewaveExecutionReceipt/v1"
    assert receipt.attestation == "HMAC_SHA256_RUNTIME_KEY"
    assert signer.verify(receipt) is True
    assert signer.verify(replace(receipt, operation_result="FAIL")) is False


def test_receipt_signer_rejects_weak_or_absent_runtime_key() -> None:
    with pytest.raises(ValueError, match="RUNTIME_ATTESTATION_KEY_TOO_SHORT"):
        RuntimeReceiptSigner(b"short")


def test_free_plugin_policy_requires_runtime_proven_native_linux_production_approval() -> None:
    registry = PluginRegistry()
    plugin = PluginDescriptor(
        plugin_id="tape-echo-2",
        name="Tape Echo 2",
        vendor="unknown",
        format="VST3",
        version="1.0.8",
        platform="linux",
        architecture="x86_64",
        cost_class="FREEWARE_NO_PAYMENT",
        roles=("delay", "dub_delay"),
    )

    registry.register(plugin)
    registry.qualify(
        PluginQualification(
            plugin_id=plugin.plugin_id,
            plugin_version=plugin.version,
            status="PRODUCTION_APPROVED",
            runtime_proven=True,
            reaper_discovered=True,
            instantiation_passed=True,
            save_reload_recall_passed=True,
            parameter_enumeration_passed=True,
            offline_render_passed=True,
        )
    )

    assert registry.production_eligible("tape-echo-2") is True


@pytest.mark.parametrize("cost_class", ["PAID", "UNKNOWN_COST", "FREEMIUM"])
def test_plugin_policy_fails_closed_for_nonzero_or_uncertain_cost(cost_class: str) -> None:
    registry = PluginRegistry()
    plugin = PluginDescriptor(
        plugin_id=f"plugin-{cost_class.lower()}",
        name="Fixture",
        vendor="Fixture",
        format="VST3",
        version="1",
        platform="linux",
        architecture="x86_64",
        cost_class=cost_class,
        roles=("delay",),
    )
    registry.register(plugin)
    registry.qualify(
        PluginQualification(
            plugin_id=plugin.plugin_id,
            plugin_version=plugin.version,
            status="PRODUCTION_APPROVED",
            runtime_proven=True,
            reaper_discovered=True,
            instantiation_passed=True,
            save_reload_recall_passed=True,
            parameter_enumeration_passed=True,
            offline_render_passed=True,
        )
    )

    assert registry.production_eligible(plugin.plugin_id) is False


def test_plugin_update_invalidates_version_bound_qualification() -> None:
    registry = PluginRegistry()
    registry.register(
        PluginDescriptor(
            plugin_id="echo",
            name="Echo",
            vendor="Fixture",
            format="VST3",
            version="1.0",
            platform="linux",
            architecture="x86_64",
            cost_class="FREE_OPEN_SOURCE",
            roles=("delay",),
        )
    )
    registry.qualify(
        PluginQualification(
            plugin_id="echo",
            plugin_version="1.0",
            status="PRODUCTION_APPROVED",
            runtime_proven=True,
            reaper_discovered=True,
            instantiation_passed=True,
            save_reload_recall_passed=True,
            parameter_enumeration_passed=True,
            offline_render_passed=True,
        )
    )
    registry.register(
        PluginDescriptor(
            plugin_id="echo",
            name="Echo",
            vendor="Fixture",
            format="VST3",
            version="1.1",
            platform="linux",
            architecture="x86_64",
            cost_class="FREE_OPEN_SOURCE",
            roles=("delay",),
        )
    )

    assert registry.production_eligible("echo") is False


def test_producer_loop_has_bounded_iterations_and_refuses_unchanged_failed_retry() -> None:
    loop = ProducerLoop(max_iterations=3)
    first = loop.record(
        mutation_fingerprint="same",
        decision=ProducerDecision.REVISE,
        technical_pass=False,
        evidence_digest="e1",
    )

    assert first.iteration == 1
    with pytest.raises(RuntimeError, match="UNCHANGED_FAILED_MUTATION_RETRY_FORBIDDEN"):
        loop.record(
            mutation_fingerprint="same",
            decision=ProducerDecision.REVISE,
            technical_pass=False,
            evidence_digest="e1",
        )


def test_producer_loop_stops_at_iteration_budget() -> None:
    loop = ProducerLoop(max_iterations=2)
    loop.record(
        mutation_fingerprint="a",
        decision=ProducerDecision.REVISE,
        technical_pass=False,
        evidence_digest="e1",
    )
    loop.record(
        mutation_fingerprint="b",
        decision=ProducerDecision.REVISE,
        technical_pass=False,
        evidence_digest="e2",
    )

    with pytest.raises(RuntimeError, match="PRODUCER_ITERATION_BUDGET_EXHAUSTED"):
        loop.record(
            mutation_fingerprint="c",
            decision=ProducerDecision.REVISE,
            technical_pass=False,
            evidence_digest="e3",
        )
