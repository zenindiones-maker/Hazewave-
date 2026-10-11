// Budget A15: rolagem de ponta a ponta, CPU 4×, mediana de 5 execuções por viewport.
import { chromium } from '@playwright/test';
const VPS={a15css:{viewport:{width:412,height:915},deviceScaleFactor:2.625,isMobile:true,hasTouch:true},a15phys:{viewport:{width:1080,height:2340},deviceScaleFactor:1},a15land:{viewport:{width:915,height:412},deviceScaleFactor:2.625,isMobile:true,hasTouch:true}};
const b=await chromium.launch(); const med=a=>[...a].sort((x,y)=>x-y)[a.length>>1]; const out={};
for(const [name,vp] of Object.entries(VPS).filter(([n])=>n===(process.env.ONLY||n))){ const runs=[];
 for(let i=0;i<5;i++){ const ctx=await b.newContext(vp); const p=await ctx.newPage();
  await p.goto('http://127.0.0.1:8096/'); await p.waitForFunction(()=>document.documentElement.dataset.ready); await p.waitForTimeout(800);
  const cdp=await ctx.newCDPSession(p); await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
  runs.push(await p.evaluate(async()=>{let lt=0,ltMax=0;new PerformanceObserver(l=>l.getEntries().forEach(e=>{lt++;ltMax=Math.max(ltMax,e.duration)})).observe({type:'longtask'});
   const H=document.documentElement.scrollHeight-innerHeight;const fr=[];let last=performance.now(),y=0;await new Promise(res=>{const f=t=>{fr.push(t-last);last=t;y+=H/700;scrollTo(0,y);if(y<H)requestAnimationFrame(f);else res()};requestAnimationFrame(f)});fr.shift();
   const s=[...fr].sort((a,b)=>a-b);return {p95:+s[Math.floor(s.length*.95)].toFixed(1),jank:fr.filter(x=>x>20).length,lt,ltMax:Math.round(ltMax)}}));
  await ctx.close(); }
 out[name]={p95_median:med(runs.map(r=>r.p95)),jank_median:med(runs.map(r=>r.jank)),longtasks_max:Math.max(...runs.map(r=>r.lt)),runs:runs.map(r=>r.p95+'/'+r.jank)}; console.log(name,JSON.stringify(out[name])); }
await b.close();
