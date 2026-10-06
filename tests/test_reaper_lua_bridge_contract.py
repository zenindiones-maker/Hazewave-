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


def test_lua_bridge_fixture_session_uses_isolated_project_tab_and_owned_root() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert 'handlers["session.fixture.open"]' in text
    assert 'handlers["session.fixture.close"]' in text
    assert "fixture_root" in text
    assert "40859" in text
    assert "40860" in text
    assert "reaper.kbd_getTextFromCmd" in text
    assert "REAPER_FIXTURE_NEW_TAB_ACTION_MISMATCH" in text
    assert "REAPER_FIXTURE_CLOSE_TAB_ACTION_MISMATCH" in text
    assert "reaper.Main_SaveProjectEx" in text
    assert "reaper.Main_SaveProject" in text
    assert "fixture_session" in text
    assert "context_switch_operations" in text
    assert '["session.fixture.open"] = true' in text
    assert '["session.fixture.close"] = true' in text


def test_lua_bridge_professional_editing_primitives_use_reascript_state_apis() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert 'handlers["arrangement.marker"]' in text
    assert 'handlers["arrangement.region"]' in text
    assert "reaper.AddProjectMarker2" in text

    assert 'handlers["audio.split"]' in text
    assert "reaper.SplitMediaItem" in text
    assert 'handlers["audio.trim"]' in text
    assert "reaper.SetMediaItemPosition" in text
    assert "reaper.SetMediaItemLength" in text
    assert '"D_STARTOFFS"' in text
    assert 'handlers["audio.fade"]' in text
    assert '"D_FADEINLEN"' in text
    assert '"D_FADEOUTLEN"' in text
    assert 'handlers["audio.align"]' in text
    assert 'handlers["audio.time_stretch"]' in text
    assert '"D_PLAYRATE"' in text
    assert '"B_PPITCH"' in text
    assert 'handlers["audio.pitch"]' in text
    assert '"D_PITCH"' in text


def test_lua_bridge_professional_track_and_fx_primitives_are_explicit() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert 'handlers["track.configure"]' in text
    assert 'handlers["track.folder"]' in text
    assert "reaper.SetMediaTrackInfo_Value" in text
    assert '"D_VOL"' in text
    assert '"D_PAN"' in text
    assert '"D_WIDTH"' in text
    assert '"I_NCHAN"' in text
    assert '"I_FOLDERDEPTH"' in text

    assert 'handlers["fx.remove"]' in text
    assert "reaper.TrackFX_Delete" in text
    assert 'handlers["fx.bypass"]' in text
    assert "reaper.TrackFX_SetEnabled" in text
    assert 'handlers["fx.preset"]' in text
    assert "reaper.TrackFX_SetPreset" in text
    assert 'handlers["fx.automation"]' in text
    assert "reaper.GetFXEnvelope" in text
    assert "reaper.InsertEnvelopePointEx" in text
    assert "reaper.Envelope_SortPointsEx" in text


def test_lua_bridge_master_and_stem_render_modes_are_project_owned() -> None:
    text = BRIDGE.read_text(encoding="utf-8")

    assert 'handlers["render.master"]' in text
    assert 'handlers["render.stems"]' in text
    assert "RENDER_SETTINGS_MASTER = 0" in text
    assert "RENDER_SETTINGS_STEMS_ONLY = 2" in text
    assert "collect_render_artifacts" in text
    assert "capture_track_selection" in text
    assert "restore_track_selection" in text
    assert '["render.master"] = true' in text
    assert '["render.stems"] = true' in text
