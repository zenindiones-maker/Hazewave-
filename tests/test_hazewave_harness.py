from __future__ import annotations

import pytest

from hazewave.harness import (
    BRIDGE,
    HAZE,
    WAVE,
    HazewaveTask,
    classify_capability_domain,
    issue_authorization,
    route_task,
    validate_authorization,
)


def test_capability_domains_are_explicit_and_project_native() -> None:
    assert classify_capability_domain("audio.generate") == HAZE
    assert classify_capability_domain("audio.separate") == HAZE
    assert classify_capability_domain("visual.render") == WAVE
    assert classify_capability_domain("visual.site") == WAVE
    assert classify_capability_domain("bridge.haze_to_wave") == BRIDGE


def test_harness_routes_by_required_capability_not_worker_name() -> None:
    task = HazewaveTask(
        task_id="task-001",
        goal="Generate an instrumental",
        required_capability="audio.generate",
        requested_domain=HAZE,
    )

    decision = route_task(task)

    assert decision.authority == "HAZEWAVE_HARNESS"
    assert decision.project_id == "HAZEWAVE"
    assert decision.task_id == task.task_id
    assert decision.selected_domain == HAZE
    assert decision.selected_capability == "audio.generate"


def test_harness_rejects_cross_domain_task_confusion() -> None:
    task = HazewaveTask(
        task_id="task-002",
        goal="Render a site",
        required_capability="visual.site",
        requested_domain=HAZE,
    )

    with pytest.raises(PermissionError, match="DOMAIN_CAPABILITY_MISMATCH"):
        route_task(task)


def test_authorization_is_bound_to_project_task_and_capability() -> None:
    task = HazewaveTask(
        task_id="task-003",
        goal="Map audio state to visuals",
        required_capability="bridge.haze_to_wave",
        requested_domain=BRIDGE,
    )
    decision = route_task(task)
    authorization = issue_authorization(decision)

    validated = validate_authorization(
        authorization,
        expected_task_id="task-003",
        expected_capability="bridge.haze_to_wave",
    )

    assert validated.project_id == "HAZEWAVE"
    assert validated.authority == "HAZEWAVE_HARNESS"


def test_authorization_rejects_capability_escalation() -> None:
    task = HazewaveTask(
        task_id="task-004",
        goal="Separate stems",
        required_capability="audio.separate",
        requested_domain=HAZE,
    )
    authorization = issue_authorization(route_task(task))

    with pytest.raises(PermissionError, match="AUTHORIZATION_CAPABILITY_MISMATCH"):
        validate_authorization(
            authorization,
            expected_task_id="task-004",
            expected_capability="visual.render",
        )


@pytest.mark.parametrize("domain", [HAZE, WAVE, BRIDGE])
def test_cross_domain_reasoning_capability_preserves_requested_domain(domain: str) -> None:
    decision = route_task(
        HazewaveTask(
            task_id=f"reason-{domain.lower()}",
            goal="Reason inside the selected Hazewave domain",
            required_capability="reason.general",
            requested_domain=domain,
        )
    )

    assert decision.selected_domain == domain
    assert decision.selected_capability == "reason.general"


@pytest.mark.parametrize(
    ("capability", "domain"),
    [
        ("reason.deep", HAZE),
        ("reason.fusion", WAVE),
        ("code.generate", WAVE),
        ("code.review", HAZE),
        ("embedding.create", BRIDGE),
    ],
)
def test_provider_meta_capabilities_are_domain_bound_at_authorization_time(
    capability: str,
    domain: str,
) -> None:
    authorization = issue_authorization(
        route_task(
            HazewaveTask(
                task_id=f"meta-{capability}-{domain}",
                goal="Bound provider meta capability",
                required_capability=capability,
                requested_domain=domain,
            )
        )
    )

    assert authorization.domain == domain
    assert authorization.capability_id == capability


def test_new_modality_capabilities_remain_domain_specific() -> None:
    assert classify_capability_domain("audio.transcribe") == HAZE
    assert classify_capability_domain("visual.analyze") == WAVE
    assert classify_capability_domain("visual.storyboard") == WAVE
    assert classify_capability_domain("bridge.semantic_translation") == BRIDGE

    with pytest.raises(PermissionError, match="DOMAIN_CAPABILITY_MISMATCH"):
        route_task(
            HazewaveTask(
                task_id="wrong-transcription-domain",
                goal="Transcribe audio",
                required_capability="audio.transcribe",
                requested_domain=WAVE,
            )
        )
