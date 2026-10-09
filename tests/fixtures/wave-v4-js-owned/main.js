/* First-party WAVE causal scroll model; exact source shared with the experimental browser rig.
 * Never grants Harness execution authority. */
(function(scope){
 'use strict';
 const clamp=x=>Math.max(0,Math.min(1,x));
 const smooth=(a,b,x)=>{const u=clamp((x-a)/(b-a));return u*u*(3-2*u)};
 function evaluateFrame(p,t,activations){
  if(!Number.isFinite(p)||!Number.isFinite(t)||!Array.isArray(activations))throw Error('WAVE_V4_INPUT_INVALID');
  const u=clamp(p);
  const awaken=smooth(.04,.22,u),approach=smooth(.2,.50,u),traverse=smooth(.48,.70,u),arrival=smooth(.66,.94,u);
  const hardware=smooth(0,1,clamp((u-.23)/.39));
  const values=activations.map(a=>smooth(a-.060,a+.062,clamp((u-.23)/.39)));
  return Object.freeze({progress:u,awaken,approach,traverse,arrival,hardware,
   wave:smooth(.03,.92,u),circuit:smooth(.25,.63,u),parts:Object.freeze(values),
   activeCount:values.filter(x=>x>.5).length,idleDrift:Math.sin(t*.31)*9});
 }
 scope.HAZEWAVE_V4_MODEL=Object.freeze({evaluateFrame,clamp,smooth});
})(typeof window!=='undefined'?window:globalThis);
