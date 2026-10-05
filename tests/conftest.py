from __future__ import annotations

import pytest

from tests.freellmapi_policy_fixture import install_synthetic_provider_registry


@pytest.fixture(autouse=True)
def _freellmapi_transport_policy_fixture(request, monkeypatch):
    """Keep adapter tests independent from the production provider allowlist."""

    if request.node.path.name in {
        "test_freellmapi_governed_fabric.py",
        "test_freellmapi_account_attestation.py",
    }:
        return None
    return install_synthetic_provider_registry(monkeypatch)
