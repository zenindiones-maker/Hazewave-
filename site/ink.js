(()=>{const ps=[...document.querySelectorAll('.ink')],intro=document.querySelector('.intro');
const L=ps.map(p=>{const l=p.getTotalLength();p.style.strokeDasharray=l;return l});
if(matchMedia('(prefers-reduced-motion: reduce)').matches){ps.forEach(p=>p.style.strokeDashoffset=0);return}
let q=0;const draw=()=>{q=0;const r=intro.getBoundingClientRect(),t=Math.min(1,Math.max(0,-r.top/Math.max(1,r.height-innerHeight)));
document.documentElement.dataset.ink=t.toFixed(3);ps.forEach((p,i)=>p.style.strokeDashoffset=L[i]*(1-t))};
addEventListener('scroll',()=>{if(!q)q=requestAnimationFrame(draw)},{passive:true});addEventListener('resize',draw);draw()})();
