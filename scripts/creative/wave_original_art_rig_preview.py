"""Offline browser preview of original Hazewave hand-painted physical pad pieces."""
import json
from html import escape
from pathlib import Path


def build_preview(root: Path) -> Path:
    root = Path(root)
    data = json.loads((root / "pilot-manifest.json").read_text(encoding="utf-8"))
    if data.get("schema") != "HazewaveWaveRigPilot/v1" or data.get("production_approved") is not False:
        raise ValueError("PILOT_SCOPE_DENIED")
    ids = {f"p{r}{c}" for r in range(3) for c in range(3)} | {"encoder_right"}
    if len(data["pieces"]) != 10 or {x["id"] for x in data["pieces"]} != ids:
        raise ValueError("TEN_INDEPENDENT_PIECES_REQUIRED")
    layers = []
    for item in data["pieces"]:
        file = item["path"]
        if file != item["id"] + ".png":
            raise ValueError("UNEXPECTED_ART_PATH")
        x, y = item["x"] * 100 / 1448, item["y"] * 100 / 1086
        w, h = item["width"] * 100 / 1448, item["height"] * 100 / 1086
        layers.append(
            f'<img class="piece" id="{escape(item["id"])}" alt="" src="{escape(file)}" '
            f'style="left:{x:.6f}%;top:{y:.6f}%;width:{w:.6f}%;height:{h:.6f}%">'
        )
    html = r"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HAZEWAVE — WAVE original art physical rig</title>
<style>
*{box-sizing:border-box}html{overflow-x:hidden;scroll-behavior:auto}
body{margin:0;min-height:550vh;overflow-x:hidden;background:radial-gradient(ellipse,#1b0e39,#050614 75%);font-family:system-ui,sans-serif;color:#dfb9ff}
.stage{position:fixed;inset:0;display:grid;place-items:center;overflow:hidden}
.art{position:relative;width:min(94vw,calc(85vh * 1.333333),1100px);aspect-ratio:1448/1086;isolation:isolate}
.art img{object-fit:fill;pointer-events:none;user-select:none}
.fog{position:absolute;width:130%;height:100%;top:3%;left:-16%;z-index:-1;opacity:.46}
.cover,.wave{position:absolute;inset:0;width:100%;height:100%}
#clean{z-index:1}#original{z-index:3}.piece{position:absolute;z-index:4;opacity:0;transform-origin:50% 65%}
.wave{z-index:5;pointer-events:none;overflow:visible;mix-blend-mode:screen}
#signal{stroke:#c463ff;stroke-width:9;stroke-linecap:round;filter:drop-shadow(0 0 6px #7b21d3)}
#head{fill:#e8b6ff}
.label{position:fixed;left:4vw;top:4vh;font-size:11px;font-weight:bold;letter-spacing:.09em;text-shadow:0 1px 8px black}
.label strong{display:block;font-size:17px;color:white;letter-spacing:.2em}
.status{position:fixed;left:4vw;bottom:17px;color:#caa7e9;font-size:11px}
.progress{position:fixed;left:0;bottom:0;height:3px;width:0;background:linear-gradient(90deg,#a236ff,#ff9752)}
@media(max-width:600px){.art{width:96vw}.label,.status{font-size:9px}}
@media(prefers-reduced-motion:reduce){.piece,.cover,.fog,.wave{transition:none!important}}
</style></head><body>
<main class="stage"><div class="art">
<img class="fog" id="fog" alt="" src="fog-original.png">
<img class="cover" id="clean" alt="" src="controller-cleanplate-EXPERIMENTAL.png">
<img class="cover" id="original" alt="" src="controller-original.png">
%%PIECES%%
<svg class="wave" viewBox="0 0 1448 1086" role="img" aria-label="O traço se desenha no scroll e ativa os pads">
<path id="signal" fill="none" d="M 82 634 C 180 640 186 510 318 480 C 431 460 460 510 584 417 C 633 360 688 374 723 388 C 775 405 822 371 834 389 C 899 414 939 437 961 465"/>
<circle id="head" cx="0" cy="0" r="8" opacity="0"/></svg>
</div></main>
<div class="label"><strong>HAZEWAVE</strong>WAVE / PILOTO ORIGINAL<br>ANIMAÇÃO AINDA NÃO APROVADA</div>
<div class="status" id="status">ROLAGEM 0% · CLEANPLATE EXPERIMENTAL</div>
<div class="progress" id="progress"></div>
<script>
(()=>{"use strict";
const clamp=x=>Math.max(0,Math.min(1,x));
const smooth=(a,b,x)=>{const t=clamp((x-a)/(b-a));return t*t*(3-2*t)};
const pads=["p00","p01","p02","p10","p11","p12","p20","p21","p22"].map(id=>document.getElementById(id));
const knob=document.getElementById("encoder_right"),original=document.getElementById("original"),fog=document.getElementById("fog");
const line=document.getElementById("signal"),head=document.getElementById("head");
const length=line.getTotalLength();line.style.strokeDasharray=String(length);
function pose(value){
 const p=clamp(value),ready=smooth(.04,.20,p);original.style.opacity=String(1-ready);
 let active=0;
 pads.forEach((pad,i)=>{
  const e=smooth(.19+i*.067,.28+i*.067,p);
  const dx=2*e*Math.sin(i*2.3),dy=-17*e*(1+(i%3)*.14);
  pad.style.opacity=String(ready);
  pad.style.transform="translate("+dx.toFixed(3)+"px,"+dy.toFixed(3)+"px) rotate("+(e*(i%2===0?-1.35:1.2)).toFixed(3)+"deg)";
  pad.style.filter=e>.01?"drop-shadow(0 0 "+Math.round(12*e)+"px rgba(224,109,255,"+(.6*e).toFixed(3)+"))":"none";
  pad.dataset.energy=e.toFixed(4);if(e>.55)active++;
 });
 knob.style.opacity=String(ready);
 knob.style.transform="rotate("+(18*smooth(.38,.77,p)).toFixed(3)+"deg)";
 fog.style.transform="translate("+(-15*p).toFixed(3)+"px,"+(22*p).toFixed(3)+"px)";
 const drawn=smooth(0,.35,p);
 line.style.strokeDashoffset=String(length*(1-drawn));
 line.style.opacity=String(smooth(.005,.09,p));
 const point=line.getPointAtLength(length*drawn);
 head.setAttribute("cx",String(point.x));head.setAttribute("cy",String(point.y));
 head.setAttribute("opacity",drawn>.02&&drawn<.99?"1":"0");
 document.getElementById("progress").style.width=(100*p).toFixed(2)+"%";
 document.getElementById("status").textContent="ROLAGEM "+(100*p).toFixed(0)+"% · PADS ATIVOS "+active+"/9 · CLEANPLATE EXPERIMENTAL";
 document.body.dataset.waveProgress=p.toFixed(5);
 document.body.dataset.activePads=String(active);
}
function update(){pose(scrollY/Math.max(1,document.documentElement.scrollHeight-innerHeight))}
addEventListener("scroll",update,{passive:true});addEventListener("resize",update);
window.__wavePoseForTest=pose;update();
})();
</script></body></html>"""
    path = root / "preview.html"
    if path.exists():
        raise ValueError("PREVIEW_EXISTS_WIP_PRESERVED")
    path.write_text(html.replace("%%PIECES%%", "\n".join(layers)), encoding="utf-8")
    return path


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("usage: wave_original_art_rig_preview.py PRIVATE_OUTPUT_DIR")
    print("WAVE_RIG_PILOT_PREVIEW=" + str(build_preview(Path(sys.argv[1]))))
    print("WAVE_PRODUCTION_APPROVED=FALSE")
