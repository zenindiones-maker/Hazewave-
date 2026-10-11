import { chromium } from '@playwright/test';
import http from 'http'; import fs from 'fs'; import path from 'path';
const root='/workspace/hz/apps/site01-critico'; const types={'.html':'text/html','.css':'text/css','.js':'text/javascript','.webp':'image/webp'};
const srv=http.createServer((q,r)=>{let f=path.join(root,decodeURIComponent(q.url.split('?')[0]));if(f.endsWith('/'))f+='index.html';fs.readFile(f,(e,d)=>{if(e){r.writeHead(404);r.end();return}r.writeHead(200,{'content-type':types[path.extname(f)]||'application/octet-stream'});r.end(d)})}).listen(8099);
const b=await chromium.launch(); const out={};
const vps=[['a15css',{width:412,height:915},2.625],['a15phys',{width:1080,height:2340},1],['a15land',{width:915,height:412},2.625]];
for(const [name,vp,dpr] of vps){ const ctx=await b.newContext({viewport:vp,deviceScaleFactor:dpr,isMobile:true,hasTouch:true}); const p=await ctx.newPage();
 const cdp=await ctx.newCDPSession(p); await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
 const errs=[]; p.on('pageerror',e=>errs.push(String(e)));
 await p.goto('http://127.0.0.1:8099/'); await p.waitForTimeout(800);
 const H=await p.evaluate(()=>document.documentElement.scrollHeight-innerHeight);
 // scrub frames
 const steps=[0,.05,.1,.15,.2,.27,.35,.42,.5,.6,.7,.8,.9,1];
 const states=[];
 for(const [i,f] of steps.entries()){ await p.evaluate(y=>scrollTo(0,y),Math.round(H*f)); await p.waitForTimeout(120);
   states.push(await p.evaluate(()=>[...document.querySelectorAll('.scene')].map(s=>s.dataset.p).join('/')));
   await p.screenshot({path:`/workspace/site01/proto-shots/${name}-${String(i).padStart(2,'0')}.png`}); }
 // reversibility
 await p.evaluate(y=>scrollTo(0,y),Math.round(H*.1)); await p.waitForTimeout(150);
 const back=await p.evaluate(()=>{const s=[...document.querySelectorAll('#s1 .stroke')];return s.filter(e=>parseFloat(e.style.strokeDashoffset)>0.5).length+'/'+s.length+' não desenhados'});
 // perf: continuous scroll with throttled CPU
 await p.evaluate(()=>scrollTo(0,0)); await p.waitForTimeout(300);
 const perf=await p.evaluate(async H=>{const lt=[];new PerformanceObserver(l=>l.getEntries().forEach(e=>lt.push(e.duration))).observe({type:'longtask'});
   const fr=[];let last=performance.now(),y=0;await new Promise(res=>{const f=t=>{fr.push(t-last);last=t;y+=H/300;scrollTo(0,y);if(y<H)requestAnimationFrame(f);else res()};requestAnimationFrame(f)});
   fr.shift();const s=[...fr].sort((a,b)=>a-b);return {frames:fr.length,avgFps:+(1000/(fr.reduce((a,b)=>a+b,0)/fr.length)).toFixed(1),p50:+s[Math.floor(s.length*.5)].toFixed(1),p95:+s[Math.floor(s.length*.95)].toFixed(1),jank_gt33ms:fr.filter(x=>x>33.4).length,longtasks:lt.length,ltMax:Math.max(0,...lt)}},H);
 out[name]={H,states,back,perf,errs}; console.log(name,JSON.stringify(out[name]));
 // reduced motion check
 await ctx.close(); }
const rm=await b.newContext({viewport:{width:412,height:915},reducedMotion:'reduce'}); const p=await rm.newPage(); await p.goto('http://127.0.0.1:8099/'); await p.waitForTimeout(300);
out.reducedMotion=await p.evaluate(()=>[...document.querySelectorAll('#s1 .stroke')].every(e=>parseFloat(e.style.strokeDashoffset)<0.5)); console.log('reducedMotion all drawn at top:',out.reducedMotion);
fs.writeFileSync('/workspace/site01/proto-results.json',JSON.stringify(out,null,1)); await b.close(); srv.close();
