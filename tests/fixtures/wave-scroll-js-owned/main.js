(() => {
 const trace=document.getElementById('trace');
 const camera=document.getElementById('camera');
 const rig=document.getElementById('rig');
 const pad=document.getElementById('pad');
 const length=trace.getTotalLength();
 trace.style.strokeDasharray=String(length);
 const clamp=(x)=>Math.max(0,Math.min(1,x));
 function update(){
   const total=Math.max(1,document.documentElement.scrollHeight-innerHeight);
   const progress=clamp(scrollY/total);
   const reveal=clamp(progress/0.4);
   trace.style.strokeDashoffset=String(length*(1-reveal));
   const padActive=progress>=0.3;
   pad.style.fill=padActive?'#f2bdff':'#322343';
   pad.setAttribute('data-active',String(padActive));
   rig.setAttribute('transform',`translate(${(progress*32).toFixed(3)},0)`);
   camera.setAttribute('transform',`translate(${(-progress*68).toFixed(3)},0)`);
   document.body.dataset.scrollProgress=String(progress);
 }
 addEventListener('scroll',update,{passive:true});
 addEventListener('resize',update);
 update();
})();
