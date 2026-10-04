from __future__ import annotations

from pathlib import Path

from hazewave.telegram_gateway import GatewayPaths, _load_pairing_code


def test_pairing_code_rotation_is_observed_without_gateway_restart(tmp_path: Path) -> None:
    paths = GatewayPaths(
        config_root=tmp_path / "config",
        state_root=tmp_path / "state",
    )
    paths.config_root.mkdir(parents=True)

    paths.pairing_code_file.write_text("OLD-CODE\n", encoding="utf-8")
    assert _load_pairing_code(paths) == "OLD-CODE"

    paths.pairing_code_file.write_text("NEW-CODE\n", encoding="utf-8")
    assert _load_pairing_code(paths) == "NEW-CODE"

    paths.pairing_code_file.unlink()
    assert _load_pairing_code(paths) == ""
