"""Harness-governed WAVE admission for external ArtCraft workers.

This is a pure policy and routing boundary. It NEVER launches executables,
installs apps, opens control ports, reads owner art, publishes, or authorizes
private-media processing. The real execution boundary remains the exact-sha
GitHub Actions offline container and the existing Hazewave Harness.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Final

from .harness import (
    AUTHORITY, PROJECT_ID, WAVE, HazewaveTask, issue_authorization, route_task
)

# ArtCraft programs are subordinate workers for EXISTING Harness capabilities.
# This module cannot expand src/hazewave/harness.py or establish a second authority.
_TOOL_TO_CAPABILITY: Final[dict[str, str]] = {
    "photocraft": "visual.image",
    "lightcraft": "visual.image",
    "vectorcraft": "visual.image",
    "effectcraft": "visual.animate",
    "filmcraft": "visual.video",
    "designcraft": "visual.storyboard",
    "pdfcraft": "visual.analyze",
}
_BOUNDARY: Final = "PUBLIC_SYNTHETIC_OFFLINE"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{3,95}$")


@dataclass(frozen=True)
class ArtCraftHarnessAdmission:
    schema: str
    task_id: str
    tool: str
    project_id: str
    domain: str
    capability_id: str
    data_classification: str
    execution_boundary: str
    authorization_id: str
    authority: str


def admit_artcraft(
    *, task_id: str, tool: str, data_classification: str,
    requested_domain: str
) -> ArtCraftHarnessAdmission:
    """Admit only bounded public offline tasks through the canonical Harness.

    A deterministic authorization ID is a *routing correlation receipt*, not
    an anti-forgery capability token. Sandboxing, workflow permissions and
    private-media exclusions remain mandatory for the execution process.
    """
    if not isinstance(task_id, str) or not _ID.fullmatch(task_id):
        raise ValueError("WAVE_ARTCRAFT_TASK_ID_REQUIRED")
    if tool not in _TOOL_TO_CAPABILITY:
        raise ValueError("WAVE_ARTCRAFT_UNAPPROVED_WORKER")
    if data_classification != "PUBLIC":
        raise PermissionError("WAVE_ARTCRAFT_PRIVATE_MEDIA_NOT_ADMITTED")
    if requested_domain != WAVE:
        raise PermissionError("WAVE_ARTCRAFT_DOMAIN_MISMATCH")
    capability = _TOOL_TO_CAPABILITY[tool]
    decision = route_task(HazewaveTask(
        task_id=task_id,
        goal="Validate offline public-media ArtCraft capability: " + tool,
        required_capability=capability,
        requested_domain=WAVE,
    ))
    authorization = issue_authorization(decision)
    return ArtCraftHarnessAdmission(
        schema="HazewaveArtCraftHarnessAdmission/v1",
        task_id=task_id,
        tool=tool,
        project_id=PROJECT_ID,
        domain=decision.selected_domain,
        capability_id=decision.selected_capability,
        data_classification=data_classification,
        execution_boundary=_BOUNDARY,
        authorization_id=authorization.authorization_id,
        authority=authorization.authority,
    )


def verify_admission(
    receipt: ArtCraftHarnessAdmission, *, expected_tool: str,
    expected_task_id: str
) -> ArtCraftHarnessAdmission:
    """Reject mutated diagnostic receipts; not a substitute for runner trust."""
    expected = admit_artcraft(
        task_id=expected_task_id, tool=expected_tool,
        data_classification="PUBLIC", requested_domain=WAVE,
    )
    if not isinstance(receipt, ArtCraftHarnessAdmission) or receipt != expected:
        raise PermissionError("WAVE_ARTCRAFT_HARNESS_ADMISSION_MISMATCH")
    if receipt.authority != AUTHORITY or receipt.project_id != PROJECT_ID:
        raise PermissionError("WAVE_ARTCRAFT_EXTERNAL_AUTHORITY_DENIED")
    return receipt
