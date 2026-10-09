"""Independent behavior/pixel test with Chromium. No external networking, no fake CSS-only assertions."""
from __future__ import annotations
from pathlib import Path
import json, numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).parent
PAGE=(ROOT/'HAZEWAVE_TRAVESSIA_V4_PRIVADA_ABRIR.html').read_text('utf8')
OUT=ROOT/'proof'
results=[]
with sync_playwright() as pw:
  browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--disable-dev-shm-usage','--no-sandbox'])
  for w,h in [(393,852),(360,800),(1280,800)]:
    page=browser.new_page(viewport={'width':w,'height':h},device_scale_factor=1)
    errors=[];req=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('request',lambda r:req.append(r.url))
    page.route('**/*',lambda route:route.abort())
    page.set_content(PAGE,wait_until='load',timeout=45000)
    page.wait_for_function('window.__HAZEWAVE_TRAVERSAL_V4?.ready===true',timeout=30000)
    seq=[0,.12,.34,.48,.61,.76,.91,1,.61,.34,0]
    frames={};measure=[]
    for i,p in enumerate(seq):
      page.evaluate('(p)=>window.scrollTo(0,(document.querySelector("#journey").offsetHeight-innerHeight)*p)',p)
      page.wait_for_function('(p)=>Math.abs(window.__HAZEWAVE_TRAVERSAL_V4.progress-p)<.002',arg=p,timeout=15000)
      value=page.evaluate('({...window.__HAZEWAVE_TRAVERSAL_V4})')
      measure.append(value)
      if i in (0,2,4,5,6,7,10):
        path=OUT/f'validated-{w}x{h}-step{i:02d}.png'
        page.screenshot(path=str(path),animations='disabled')
        frames[i]=path
    a=measure
    assert a[0]['mountedPieces']==24 and a[0]['activePads']==0
    assert a[7]['activePads']==12 and a[7]['activeKnobs']==8 and a[7]['activeSpeakers']==4
    assert a[4]['mechanicalSplitPx']>60 and a[5]['fogSeparationPx']>=w*1.5
    assert a[5]['portalRadiusPct']>60 and a[6]['hubOpacity']>.8
    assert a[7]['secondIllustratedRegionVisible'] is True
    assert a[7]['cameraTravelPx']>a[0]['cameraTravelPx']
    assert a[7]['traceDrawn']==1 and a[0]['traceDrawn']==0
    assert a[-1]['progress']==0 and a[-1]['activePads']==0 and a[-1]['activeKnobs']==0 and a[-1]['activeSpeakers']==0
    assert a[-1]['portalRadiusPct']==0 and a[-1]['fogSeparationPx']==0 and a[-1]['mechanicalSplitPx']==0
    assert page.evaluate('document.documentElement.scrollWidth-innerWidth')<=1
    assert not errors,errors
    assert not req,req
    def pxchange(i,j):
      x=np.asarray(Image.open(frames[i]).convert('RGB')).astype(np.int16)
      y=np.asarray(Image.open(frames[j]).convert('RGB')).astype(np.int16)
      return round(float(np.abs(x-y).mean()),3)
    diffs={"start_vs_machine":pxchange(0,4),"machine_vs_portal":pxchange(4,5),"portal_vs_arrival":pxchange(5,7),"start_vs_end":pxchange(0,7),"start_vs_reset":pxchange(0,10)}
    assert min(diffs['start_vs_machine'],diffs['machine_vs_portal'],diffs['portal_vs_arrival'])>15,diffs
    assert diffs['start_vs_reset']<2,diffs
    results.append({'viewport':[w,h],'sourceSha':a[0]['sourceV3A'],'realChromium':True,'requestCount':len(req),'javascriptErrors':errors,'rigPartCount':24,'diffMeanRGB':diffs,'states':[{'progress':s['progress'],'phase':s['phase'],'pads':s['activePads'],'splitPx':s['mechanicalSplitPx'],'fogSeparationPx':s['fogSeparationPx'],'portalRadiusPct':s['portalRadiusPct'],'hubOpacity':s['hubOpacity'],'cameraTravelPx':s['cameraTravelPx']} for s in measure],'cinematicHumanApproval':False,'productionApproved':False})
    print('V4_REAL_CHROMIUM=PASS',w,h,diffs,flush=True)
    page.close()
  browser.close()
(OUT/'V4_REAL_BROWSER_QA.json').write_text(json.dumps(results,indent=2,ensure_ascii=False))
