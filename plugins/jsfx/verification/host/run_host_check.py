import json, os, time, wave, reapy
from reapy import reascript_api as RPR
T = "/home/vscode/.local/share/hazewave/fyahreaper-test/plugins-v1"; os.makedirs(T, exist_ok=True)
SR = 48000
import shutil; src = T + "/tone_1k_-6dBFS.wav"; shutil.copy("/tmp/hz/tone_1k_-6dBFS.wav", src)
out = {"before_project": RPR.GetProjectName(0, "", 512)[1]}
before_proj = RPR.EnumProjects(-1, "", 0)[0]
RPR.Main_OnCommand(40859, 0)  # new project tab
proj = RPR.EnumProjects(-1, "", 0)[0]
RPR.SetCurrentBPM(0, 120, False)
RPR.InsertTrackAtIndex(0, False); tr = RPR.GetTrack(0, 0)
RPR.SetOnlyTrackSelected(tr); RPR.SetEditCurPos(0, False, False)
RPR.InsertMedia(src, 0)
res = {}
for name, settings in [("JS:Hazewave/Hazewave FyahComp FET.jsfx", {0: 12.0, 3: 200, 4: 300, 6: 30, 7: 100}),
                       ("JS:Hazewave/Hazewave FyahTape.jsfx", {0: 6.0, 2: 1, 3: 50, 4: 0, 5: -100, 6: 100})]:
    idx = RPR.TrackFX_AddByName(tr, name, False, -1)
    info = {"index": idx}
    if idx >= 0:
        n = RPR.TrackFX_GetNumParams(tr, idx); info["num_params"] = n
        info["params"] = [RPR.TrackFX_GetParamName(tr, idx, p, "", 256)[4] for p in range(n)]
        for p, v in settings.items(): RPR.TrackFX_SetParam(tr, idx, p, v)
        info["set"] = {p: RPR.TrackFX_GetParam(tr, idx, p, 0, 0)[0] for p in settings}
    res[name] = info
out["fx"] = res
RPR.Main_SaveProjectEx(proj, T + "/plugins-host-test.rpp", 0)
for k, v in [("RENDER_FILE", T), ("RENDER_PATTERN", "render_out"), ("RENDER_FORMAT", "ZXZhdxgAAQ==")]:
    RPR.GetSetProjectInfo_String(proj, k, v, True)
RPR.GetSetProjectInfo(proj, "RENDER_SRATE", SR, True); RPR.GetSetProjectInfo(proj, "RENDER_CHANNELS", 2, True)
RPR.GetSetProjectInfo(proj, "RENDER_BOUNDSFLAG", 1, True); RPR.GetSetProjectInfo(proj, "RENDER_SETTINGS", 0, True)
RPR.GetSetProjectInfo(proj, "RENDER_TAILFLAG", 0, True)
RPR.Main_SaveProjectEx(proj, T + "/plugins-host-test.rpp", 0)
RPR.Main_OnCommand(42230, 0)  # render w/ last settings, auto-close
time.sleep(3)
out["render_exists"] = os.path.exists(T + "/render_out.wav")
# close our tab without saving prompt
RPR.Main_OnCommand(40026, 0)  # save
RPR.Main_OnCommand(40860, 0)  # close current project tab
RPR.SelectProjectInstance(before_proj)
out["after_project"] = RPR.GetProjectName(0, "", 512)[1]
json.dump(out, open(T + "/host_result.json", "w"), indent=1); print(json.dumps(out, indent=1))
