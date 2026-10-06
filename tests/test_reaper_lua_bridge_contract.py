from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "scripts" / "reaper" / "hazewave_reaper_bridge.lua"


def test_lua_bridge_is_project_owned_file_ipc_without_network_or_eval() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert "HAZEWAVE_REAPER_BRIDGE_DIR" in text
    assert "reaper.EnumerateFiles" in text
    assert "request_id" in text
    assert "heartbeat.json" in text
    assert "os.rename" in text
    for forbidden in ("socket.", "http.", "load(", "loadstring(", "os.execute("):
        assert forbidden not in text


def test_lua_bridge_uses_optimistic_concurrency_and_native_undo() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert "reaper.GetProjectStateChangeCount" in text
    assert "REAPER_STATE_STALE" in text
    assert "reaper.Undo_BeginBlock2" in text
    assert "reaper.Undo_EndBlock2" in text
    assert "reaper.Undo_DoUndo2" in text


def test_lua_bridge_dispatch_is_static_and_bounded_for_first_vertical_slice() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    for operation in (
        '["session.inspect"]',
        '["track.create"]',
        '["audio.import"]',
        '["routing.bus"]',
        '["routing.send"]',
        '["fx.inventory"]',
        '["fx.add"]',
        '["fx.parameter.read"]',
        '["fx.parameter.write"]',
    ):
        assert operation in text

    assert "handlers[request.operation]" in text
    assert "REAPER_OPERATION_NOT_ALLOWLISTED" in text
