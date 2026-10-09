/* The visual master is owner supplied. One deterministic scroll state + a separate ambient clock.
 * Every one of the 24 exported art sprites is independently mounted and animated.
 * Native sticky scrolling avoids touch hijack and allows reverse by design.
 */
(async()=>{
'use strict';
const manifest=window.__rigManifest || await fetch('rig-manifest.json').then(r=>{if(!r.ok)throw Error('Manifest unavailable');return r.json();});
const root=document.getElementById('machine'); const scrollArea=document.getElementById('journey');
const stage=document.getElementById('stage');const bar=document.getElementById('progress');
const image=(url,cls)=>{let img=document.createElement('img');img.className='machine-layer rig-part '+cls;img.src=url;img.decoding='async';img.alt='';img.draggable=false;return img};
const parts=manifest.pieces.map(spec=>{
 const node=image(spec.file,'rig-'+spec.type);node.dataset.rigId=spec.id;
 node.style.left=spec.x+'px';node.style.top=spec.y+'px';node.width=spec.width;node.height=spec.height;
 root.appendChild(node);
 let on=null;
 if(spec.type==='pad'){
   on=image(spec.energizedFile || spec.file.replace('.webp','_energized.webp'),'pad-energized');on.dataset.padId=spec.id;
   on.style.left=spec.x+'px';on.style.top=spec.y+'px';on.width=spec.width;on.height=spec.height;
   root.appendChild(on);
 }
 return {spec,node,on};
});
const trace=document.getElementById('soundpath'),core=document.getElementById('soundcore');
const len=trace.getTotalLength();for(const t of [trace,core]){t.style.strokeDasharray=String(len);t.style.strokeDashoffset=String(len);}
const fog=[...document.querySelectorAll('.fog')],background=document.getElementById('background');
const chapter=document.getElementById('chapterName'),num=document.getElementById('chapterNo'); const story=document.querySelector('.journey-top');
const reduced=matchMedia('(prefers-reduced-motion: reduce)');
const clamp=x=>Math.max(0,Math.min(1,x));
const smooth=(a,b,x)=>{let u=clamp((x-a)/(b-a));return u*u*(3-2*u)};
const labels=['SINAL ADORMECIDO','A INTERFERÊNCIA NASCE','CIRCUITOS ATIVADOS','MÁQUINAS ARTICULADAS','ESTAÇÃO DESPERTA'];
let state={progress:0,activePads:0,activeKnobs:0,activeSpeakers:0,stroke:0,ambient:0,mounted:parts.length,ready:true,phase:0};
window.__HAZEWAVE_RIG_V3=state;
let clock0=performance.now(),last=clock0,needsScroll=true,progress=0;
function getProgress(){let top=scrollArea.getBoundingClientRect().top+scrollY;let span=scrollArea.offsetHeight-innerHeight;return clamp((scrollY-top)/Math.max(1,span));}
function render(now){
 const dt=Math.min((now-last)/1000,.05);last=now;
 const time=reduced.matches?0:(now-clock0)/1000;
 if(needsScroll){progress=getProgress();needsScroll=false;}
 const p=progress;
 story.style.opacity=(1-smooth(.04,.30,p)).toFixed(3);
 // Use actual artwork dimensions; portrait mobile fills viewport width enough to see physical pad motion.
 const vw=innerWidth,vh=innerHeight;
 const baseline=Math.min((vw<800?vw*1.65:vw*.8)/1448,(vh*(vw<800?.72:1.1))/1086);
 const pose=smooth(.06,.96,p);
 const scale=baseline*(.96+.22*pose);
 const panX=(p-.5)*(-vw*.12);
 const panY=(p-.5)*(vh*.05)+(reduced.matches?0:Math.sin(time*.6)*2);
 root.style.transform=`translate3d(${panX}px,${panY}px,0) translate(-50%,-50%) scale(${scale})`;
 // The scene is centered relative to parent left=50%,top=50%.
 let activePads=0,activeKnobs=0,activeSpeakers=0;
 for(const {spec,node,on} of parts){
   const alive=smooth(spec.activation-.075,spec.activation+.085,p);
   const breathing=reduced.matches?0:Math.sin(time*2.7+spec.activation*30)*.014;
   if(spec.type==='pad'){
     let press=alive*(1.5+2*clamp(1-Math.abs((p-spec.activation)*7)));
     node.style.transform=`translate3d(0,${press.toFixed(3)}px,0)`;
     if(on){on.style.transform=node.style.transform;on.style.opacity=(alive*.95+breathing*alive).toFixed(3)}
     if(alive>.5)activePads++;
   } else if(spec.type==='knob'){
     // Rotate original illustrated cap around its center, not a synthetic shape.
     let angle=alive*((spec.x%2?1:-1)*18);
     node.style.transform=`rotate(${angle.toFixed(2)}deg)`;
     node.style.filter=`brightness(${(1+alive*.10).toFixed(3)})`;
     if(alive>.5)activeKnobs++;
   } else {
     let pulse=alive*(.013+(reduced.matches?0:Math.sin(time*5.1+spec.x)*.009));
     node.style.transform=`scale(${(1+pulse).toFixed(4)})`;
     if(alive>.5)activeSpeakers++;
   }
 }
 const stroke=smooth(.08,.9,p);
 for(const t of [trace,core]) t.style.strokeDashoffset=String(len*(1-stroke));
 background.style.transform=`scale(${(1.17+p*.15).toFixed(3)}) translate3d(${(-p*1.5).toFixed(2)}%,${(p*1.8).toFixed(2)}%,0)`;
 for(let i=0;i<fog.length;i++){
   const move=reduced.matches?0:Math.sin(time*(.18+i*.11)+i)*12;
   fog[i].style.transform=`translate3d(${(move+p*(i===2?32:-23)).toFixed(1)}px,${(p*(i===2?-60:15)).toFixed(1)}px,0)`;
   fog[i].style.opacity=(.17+smooth(.04,.28,p)*.14+(i===2?.13:0)).toFixed(3);
 }
 bar.style.width=(100*p).toFixed(2)+'%';
 const idx=p<.16?0:p<.36?1:p<.62?2:p<.84?3:4;
 chapter.textContent=labels[idx];num.textContent=String(idx+1).padStart(2,'0')+' — ';
 Object.assign(state,{progress:p,activePads,activeKnobs,activeSpeakers,stroke,phase:idx,ambient:time});
 requestAnimationFrame(render);
}
window.addEventListener('scroll',()=>{needsScroll=true},{passive:true});
window.addEventListener('resize',()=>{needsScroll=true},{passive:true});
requestAnimationFrame(render);
})();