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


def test_9router_free_probe_is_bounded_reversible_and_free_only() -> None:
    probe = ROOT / "scripts" / "hazewave_9router_free_probe.sh"
    assert probe.is_file()
    text = probe.read_text(encoding="utf-8")

    assert "opencode.ai/zen/v1/models" in text
    assert "big-pickle" in text
    assert 'endsWith("-free")' in text
    assert "deepseek-v4-flash-free" in text
    assert "requireApiKey" in text
    assert "finally" in text
    assert "127.0.0.1:20128" in text
    assert "max_tokens" in text
    assert "HAZEWAVE_9ROUTER_FREE_PROBE=PASS" in text

    control = CONTROL.read_text(encoding="utf-8")
    assert "probe-free)" in control
    assert "catalog)" in control


def test_9router_free_probe_derives_cli_token_from_server_owned_files() -> None:
    probe = (ROOT / "scripts" / "hazewave_9router_free_probe.sh").read_text(encoding="utf-8")
    control = CONTROL.read_text(encoding="utf-8")

    assert "machine-id" in probe
    assert "auth/cli-secret" in probe
    assert "9r-cli-auth" in probe
    assert "x-9r-cli-token" in probe
    assert "src/cli/api/client.js" not in probe
    assert 'DATA_DIR="$RUNTIME_HOME/.9router"' in control


def test_9router_cli_auth_material_is_preseeded_before_server_and_probe() -> None:
    control = CONTROL.read_text(encoding="utf-8")
    probe = (ROOT / "scripts" / "hazewave_9router_free_probe.sh").read_text(encoding="utf-8")

    assert "ensure_cli_auth_material()" in control
    assert "machine-id" in control
    assert "auth/cli-secret" in control
    assert "chmod 600" in control
    assert "HAZEWAVE_9ROUTER_CLI_AUTH_CREATED=" in control
    assert control.index("ensure_cli_auth_material") < control.index('nohup node "$entry"')

    assert 'ensure-auth)' in control
    assert '"$CONTROL" ensure-auth' in probe
    assert '"$CONTROL" restart' in probe
    assert "HAZEWAVE_9ROUTER_CLI_AUTH_CREATED=1" in probe
