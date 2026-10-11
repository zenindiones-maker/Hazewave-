"""CI-only: inspect the app WebView via DevTools (debug build) — canvas size and noVNC status."""
import asyncio, json, sys, urllib.request, websockets
JS = """JSON.stringify({w:innerWidth,h:innerHeight,dpr:devicePixelRatio,
 canvases:[...document.querySelectorAll('canvas')].map(c=>({w:c.width,h:c.height,cw:c.clientWidth,ch:c.clientHeight,vis:getComputedStyle(c).visibility,disp:getComputedStyle(c).display})),
 box:['noVNC_container','noVNC_screen'].map(i=>{var e=document.getElementById(i);return e?[i,e.clientWidth,e.clientHeight]:[i,null]}),
 status:(document.getElementById('noVNC_status')||{}).textContent,
 connected:document.documentElement.classList.contains('noVNC_connected'),
 bodyClass:document.documentElement.className})"""
async def main():
    pages = json.load(urllib.request.urlopen('http://127.0.0.1:9222/json'))
    page = [p for p in pages if 'vnc.html' in p.get('url','')][0]
    async with websockets.connect(page['webSocketDebuggerUrl'], max_size=None) as ws:
        await ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression':JS,'returnByValue':True}}))
        print(json.loads(await ws.recv())['result']['result']['value'])
asyncio.run(main())
