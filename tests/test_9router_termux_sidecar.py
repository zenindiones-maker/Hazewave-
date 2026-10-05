from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "9router-upstream-v1.json"
INSTALLER = ROOT / "scripts" / "install_hazewave_9router_termux.sh"
CONTROL = ROOT / "scripts" / "hazewave_9router_control.sh"
HAZEWAVE_CONTROL = ROOT / "scripts" / "hazewave_termux_control.sh"


def test_9router_upstream_is_exact_pinned_and_subordinate() -> None:
    payload = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert payload["schema"] == "Hazewave9RouterUpstream/v1"
    assert payload["project_id"] == "HAZEWAVE"
    assert payload["authority"] == "NONE"
    assert payload["project_authority"] == "HAZEWAVE_HARNESS"
    assert payload["repository"] == "decolua/9router"
    assert payload["version"] == "0.5.95"
    assert payload["commit"] == "a99cf57239ff778b61e434c2786009d5ed1c412c"
    assert payload["license"] == "MIT"
    assert payload["bind_host"] == "127.0.0.1"
    assert payload["port"] == 20128
    assert payload["api_base_url"] == "http://127.0.0.1:20128/v1"
    assert payload["paid_fallback"] == "FORBIDDEN"
    assert payload["unknown_cost"] == "DENY"
    assert payload["execution_policy"] == "DISCOVERY_ONLY_UNTIL_ROUTE_ADMISSION"
    assert payload["security_baseline"]["minimum_fixed_version"] == "0.5.2"
    assert payload["security_baseline"]["loopback_only"] is True


def test_9router_termux_runtime_is_managed_by_hazewave() -> None:
    assert INSTALLER.is_file()
    assert CONTROL.is_file()

    installer = INSTALLER.read_text(encoding="utf-8")
    control = CONTROL.read_text(encoding="utf-8")
    root_control = HAZEWAVE_CONTROL.read_text(encoding="utf-8")

    assert "9router@0.5.95" in installer
    assert "a99cf57239ff778b61e434c2786009d5ed1c412c" in installer
    assert "127.0.0.1" in control
    assert "20128" in control
    assert "HAZEWAVE_9ROUTER_AUTHORITY=NONE" in control
    assert "HAZEWAVE_9ROUTER_PAID_FALLBACK=FORBIDDEN" in control
    assert "9router)" in root_control


def test_9router_termux_runtime_uses_pid_metadata_without_proc_cmdline_dependency() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")
    control = CONTROL.read_text(encoding="utf-8")

    assert "--ignore-scripts" in installer
    assert "ensureSqliteRuntime" in installer
    assert "trayRuntime" not in installer

    assert "setsid" not in control
    assert "/proc/$pid/cmdline" not in control
    assert "ownership.meta" in control
    assert "release=" in control
    assert "port=" in control
    assert "HAZEWAVE_9ROUTER_OWNERSHIP=PASS" in control


def test_9router_sqlite_bootstrap_runs_for_existing_pinned_release() -> None:
    installer = INSTALLER.read_text(encoding="utf-8")

    assert "bootstrap_sqlite_runtime()" in installer
    assert installer.index("bootstrap_sqlite_runtime") < installer.rindex("bootstrap_sqlite_runtime")
    assert installer.rindex("bootstrap_sqlite_runtime") > installer.index(
        'test -x "$RELEASE_DIR/node_modules/.bin/9router"'
    )
