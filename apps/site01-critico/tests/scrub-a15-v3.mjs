import { chromium } from '@playwright/test';
import http from 'http'; import fs from 'fs'; import path from 'path';
const root=process.env.ROOT||'/workspace/hz/apps/site01-critico'; const OUT=process.env.OUT||'/workspace/site01/proto3-shots';
const types={'.html':'text/html','.css':'text/css','.js':'text/javascript','.webp':'image/webp','.json':'application/json','.woff2':'font/woff2'};
const srv=http.createServer((q,r)=>{let f=path.join(root,decodeURIComponent(q.url.split('?')[0]));if(f.endsWith('/'))f+='index.html';fs.readFile(f,(e,d)=>{if(e){r.writeHead(404);r.end();return}r.writeHead(200,{'content-type':types[path.extname(f)]||'application/octet-stream','cache-control':'no-store'});r.end(d)})}).listen(8099);
const b=await chromium.launch(); const out={};
const vps=[['a15css',{width:412,height:915},2.625],['a15phys',{width:1080,height:2340},1],['a15land',{width:915,height:412},2.625]];
for(const [name,vp,dpr] of vps){ const ctx=await b.newContext({viewport:vp,deviceScaleFactor:dpr,isMobile:true,hasTouch:true}); const p=await ctx.newPage();
 const errs=[]; p.on('pageerror',e=>errs.push(String(e))); p.on('console',m=>{if(m.type()==='error')errs.push(m.text())});
 await p.goto('http://127.0.0.1:8099/'); await p.waitForFunction(()=>document.documentElement.dataset.ready); await p.waitForTimeout(600);
 const J=await p.evaluate(()=>{const j=document.getElementById('journey');return {top:j.offsetTop,len:j.offsetHeight-innerHeight}});
 const keys=[0,.05,.1,.16,.3,.45,.52,.58,.66,.76,.83,.9,1];
 for(const [i,k] of keys.entries()){ await p.evaluate(y=>scrollTo(0,y),Math.round(J.top+J.len*k)); await p.waitForTimeout(160); await p.screenshot({path:`${OUT}/${name}-j${String(i).padStart(2,'0')}.png`}); }
 // overlap check: card vs island bbox at end
 const overlap=await p.evaluate(()=>{const c=document.getElementById('card').getBoundingClientRect(),i=document.querySelector('.island').getBoundingClientRect();const ov=(a1,a2,b1,b2)=>Math.max(0,Math.min(a2,b2)-Math.max(a1,b1));return Math.round(ov(c.top,c.bottom,i.top+i.height*.08,i.bottom-i.height*.08)*ov(c.left,c.right,i.left+i.width*.08,i.right-i.width*.08))});
 const secIds=['reaper','plugins','merch','apoie']; const secY={};
 for(const id of secIds){ secY[id]=await p.evaluate(id=>{const s=document.getElementById(id);return s.offsetTop+s.offsetHeight*.55-innerHeight},id); await p.evaluate(y=>scrollTo(0,y),Math.round(secY[id])); await p.waitForTimeout(160); await p.screenshot({path:`${OUT}/${name}-s-${id}.png`}); }
 // reversibility
 await p.evaluate(y=>scrollTo(0,y),Math.round(J.top+J.len*.66)); await p.waitForTimeout(200);
 const back=await p.evaluate(()=>{const c=document.querySelector('.island canvas');const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=16)if(d[i]>0)n++;return 'ink px amostrados='+n+'; flat='+getComputedStyle(document.querySelector('.island img')).opacity});
 await p.evaluate(()=>scrollTo(0,0)); await p.waitForTimeout(300);
 const cdp=await ctx.newCDPSession(p); await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
 const perf=await p.evaluate(async H=>{const lt=[];new PerformanceObserver(l=>l.getEntries().forEach(e=>lt.push(e.duration))).observe({type:'longtask'});
   const fr=[];let last=performance.now(),y=0;await new Promise(res=>{const f=t=>{fr.push(t-last);last=t;y+=H/420;scrollTo(0,y);if(y<H)requestAnimationFrame(f);else res()};requestAnimationFrame(f)});
   fr.shift();const s=[...fr].sort((a,b)=>a-b);return {frames:fr.length,avgFps:+(1000/(fr.reduce((a,b)=>a+b,0)/fr.length)).toFixed(1),p50:+s[Math.floor(s.length*.5)].toFixed(1),p95:+s[Math.floor(s.length*.95)].toFixed(1),jank_gt33ms:fr.filter(x=>x>33.4).length,longtasks:lt.length,ltMax:Math.max(0,...lt)}},await p.evaluate(()=>document.documentElement.scrollHeight-innerHeight));
 const hscroll=await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
 out[name]={overlap,back,perf,hscroll,errs}; console.log(name,JSON.stringify(out[name]));
 await ctx.close(); }
const rm=await b.newContext({viewport:{width:412,height:915},reducedMotion:'reduce'}); const p=await rm.newPage(); await p.goto('http://127.0.0.1:8099/'); await p.waitForFunction(()=>document.documentElement.dataset.ready); await p.waitForTimeout(300);
out.reducedMotion=await p.evaluate(()=>{const c=document.querySelector('.island canvas');const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=16)if(d[i]>0)n++;return n}); console.log('reducedMotion drawn:',out.reducedMotion);
fs.writeFileSync(OUT+'/../proto3-results.json',JSON.stringify(out,null,1)); await b.close(); srv.close();
