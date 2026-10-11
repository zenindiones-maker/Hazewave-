import json
from reapy import reascript_api as R
T="/home/vscode/.local/share/hazewave/fyahreaper-test/plugins-v1"
out={"tabs_before":[R.EnumProjects(i,"",512)[2] for i in range(5) if R.EnumProjects(i,"",512)[0]]}
mine=R.EnumProjects(-1,"",512)[0]; first=R.EnumProjects(0,"",512)[0]
tr=R.GetTrack(0,0); fx=[]
for f in range(R.TrackFX_GetCount(tr)):
    n=R.TrackFX_GetNumParams(tr,f)
    fx.append({"name":R.TrackFX_GetFXName(tr,f,"",256)[3],"num_params":n,
      "params":[R.TrackFX_GetParamName(tr,f,p,"",256)[4] for p in range(n)],
      "values":[round(R.TrackFX_GetParam(tr,f,p,0,0)[0],3) for p in range(n)]})
out["fx"]=fx; out["ntracks"]=R.CountTracks(0)
if mine!=first:
    R.Main_openProject("noprompt:"+T+"/plugins-host-test.rpp")
    R.Main_OnCommand(40860,0)
R.SelectProjectInstance(first)
out["tabs_after"]=[R.EnumProjects(i,"",512)[2] for i in range(5) if R.EnumProjects(i,"",512)[0]]
json.dump(out,open(T+"/host_result.json","w"),indent=1); print(json.dumps(out,indent=1))
