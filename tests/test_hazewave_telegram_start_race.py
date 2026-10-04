from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_persistence_starts_gateway_before_supervisor_to_avoid_dual_restart_race() -> None:
    script = (
        ROOT / "scripts" / "install_hazewave_telegram_persistence.sh"
    ).read_text(encoding="utf-8")

    gateway_start = script.index('bash "$CONTROL" start')
    supervisor_start = script.index('nohup bash "$SUPERVISOR"')

    assert gateway_start < supervisor_start


def test_gateway_mutations_are_serialized_by_project_local_lock() -> None:
    control = (
        ROOT / "scripts" / "hazewave_telegram_control.sh"
    ).read_text(encoding="utf-8")

    assert "gateway-control.lock" in control
    assert "acquire_gateway_control_lock" in control
    assert "release_gateway_control_lock" in control
