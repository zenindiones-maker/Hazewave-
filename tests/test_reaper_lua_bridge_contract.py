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


def test_lua_bridge_rejects_expired_request_before_dispatch() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert "deadline_epoch_seconds" in text
    assert "issued_at_epoch_seconds" in text
    assert "REAPER_REQUEST_DEADLINE_EXCEEDED" in text
    assert "os.time() > request.deadline_epoch_seconds" in text


def test_lua_bridge_has_non_destructive_checkpoint_and_guarded_rollback() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert 'handlers["session.checkpoint"]' in text
    assert 'handlers["session.rollback"]' in text
    assert "reaper.Main_SaveProjectEx" in text
    assert "checkpoint_root" in text
    assert "expected_undo_description" in text
    assert "reaper.Undo_CanUndo2" in text
    assert "REAPER_ROLLBACK_UNDO_MISMATCH" in text
    assert "special_operations" in text
    assert '["session.rollback"] = true' in text


def test_lua_bridge_render_preview_is_bounded_verified_and_restores_settings() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert 'handlers["render.preview"]' in text
    assert "render_root" in text
    assert "RENDER_FILE" in text
    assert "RENDER_PATTERN" in text
    assert "RENDER_FORMAT" in text
    assert '"evaw"' in text
    assert "reaper.kbd_getTextFromCmd" in text
    assert "REAPER_RENDER_ACTION_IDENTITY_MISMATCH" in text
    assert "reaper.Main_OnCommandEx" in text
    assert "42230" in text
    assert "restore_render_settings" in text
    assert "REAPER_RENDER_OUTPUT_MISSING" in text
    assert "REAPER_RENDER_OUTPUT_EMPTY" in text
    assert '["render.preview"] = true' in text
