/** WAVE / Site 01
 * Native SVG real stroke paint; GSAP ScrollTrigger is only the scroll clock.
 * The path geometry is newly authored WAVE scene direction, not a claim that
 * the artist's brush strokes have been reconstructed from a raster image.
 * No timers, fake interaction, auto-playing media, WebGL or publication.
 */
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";

type InkPath = {
  key: string;
  element: SVGPathElement;
  length: number;
  start: number;
  end: number;
};
type PublicSiteState = {
  ready: boolean;
  progress: number;
  chapter: number;
  paintedLength: number;
  activePaths: number;
  dispose: () => void;
};
declare global {
  interface Window {
    __HAZEWAVE_SITE_01?: PublicSiteState;
  }
}
const clamp01=(v:number)=>Math.max(0,Math.min(1,v));
const segment=(p:number,start:number,end:number)=>clamp01((p-start)/(end-start));
const smooth=(p:number)=>p*p*(3-2*p);
const chapterCuts=[0,.12,.29,.42,.59,.76,.91] as const;
const chapterStates=["silence","signal","interference","resistance","fog","resonance","arrival"] as const;

export function mountSite01Ink(): void {
  const journey=document.getElementById("ink-journey");
  const stage=document.getElementById("ink-stage");
  const engine=document.getElementById("ink-story-engine");
  const seed=document.getElementById("ink-seed");
  const caption=document.getElementById("ink-caption");
  const verses=Array.from(document.querySelectorAll<HTMLElement>("[data-ink-chapter]"));
  const brushPaths=Array.from(document.querySelectorAll<SVGPathElement>("path[data-ink-stroke]"));

  if (!journey||!stage||!engine||!seed||!caption||verses.length!==7||brushPaths.length!==16) {
    throw new Error("HAZEWAVE_SITE01_REAL_INK_CONTRACT_MISSING");
  }
  // Captured immutable non-null references remain valid in nested callbacks.
  // This keeps TypeScript strictNullChecks enabled with no unsafe non-null casts.
  const stageRoot=stage;
  const seedNode=seed;
  const captionNode=caption;
  const keys=new Set<string>();
  const paths:InkPath[]=brushPaths.map(element=>{
    const key=element.dataset.inkStroke;
    const start=Number(element.dataset.start),end=Number(element.dataset.end);
    const length=element.getTotalLength();
    if(!key||keys.has(key)||!Number.isFinite(length)||length<=0||
       !Number.isFinite(start)||!Number.isFinite(end)||start<0||end>1||end<=start){
      throw new Error("HAZEWAVE_SITE01_STROKE_GEOMETRY_INVALID:"+key);
    }
    keys.add(key);
    // Browser-calculated path lengths reflect each actual authored Bézier path.
    // Hide the ENTIRE stroke initially; parallax and generic fades are not paint.
    element.style.strokeDasharray=String(length)+" "+String(length+2);
    element.style.strokeDashoffset=String(length);
    return {key,element,length,start,end};
  });
  const essential=["origin","interference","nebula","owner-mask","signature"];
  if(!essential.every(key=>keys.has(key)))throw new Error("HAZEWAVE_SITE01_CAUSAL_STROKES_MISSING");

  window.__HAZEWAVE_SITE_01?.dispose();
  gsap.registerPlugin(ScrollTrigger);
  const reduced=matchMedia("(prefers-reduced-motion: reduce)");
  document.documentElement.dataset.reducedMotion=String(reduced.matches);
  let previousChapter=-1;
  const state:PublicSiteState={
    ready:false,progress:0,chapter:0,paintedLength:0,activePaths:0,
    dispose:()=>{},
  };
  window.__HAZEWAVE_SITE_01=state;

  function paint(raw:number):void {
    const p=clamp01(raw);
    let activePaths=0;
    let paintedLength=0;
    for(const item of paths){
      // LINEAR draw distance makes actual finger/scroll movement the brush.
      const completion=segment(p,item.start,item.end);
      const offset=item.length*(1-completion);
      item.element.style.strokeDashoffset=String(Math.max(0,offset));
      if(completion>0)activePaths++;
      paintedLength+=item.length*completion;
    }
    seedNode.style.opacity=String(smooth(segment(p,.006,.045)));
    const brand=segment(p,.69,.92);
    stageRoot.style.setProperty("--brand-visibility",String(brand>.008?1:0));
    stageRoot.style.setProperty("--brand-clip",String((1-brand)*100)+"%");
    stageRoot.style.setProperty("--signature-clip",String((1-segment(p,.91,.98))*100)+"%");
    // The CTA is outside the sticky stage. Put its reveal variable on body
    // so the final real destination becomes visually actionable.
    document.body.style.setProperty("--arrival",String(segment(p,.92,.99)));
    // Camera is SUBORDINATE to drawing. Reduced motion removes it entirely.
    if(!reduced.matches){
      stageRoot.style.setProperty("--camera-z",String(1+.065*smooth(segment(p,.26,.76))));
      stageRoot.style.setProperty("--camera-y",String(-26*smooth(segment(p,.39,.84)))+"px");
    } else {
      stageRoot.style.setProperty("--camera-z","1");
      stageRoot.style.setProperty("--camera-y","0px");
    }
    let chapter=0;
    for(let index=1;index<chapterCuts.length;index++){
      if(p>=chapterCuts[index])chapter=index;
    }
    if(chapter!==previousChapter){
      captionNode.textContent=verses[chapter]?.dataset.verse ?? "";
      previousChapter=chapter;
    }
    document.body.dataset.inkProgress=p.toFixed(4);
    document.body.dataset.inkState=chapterStates[chapter];
    document.body.dataset.inkActiveStrokes=String(activePaths);
    state.progress=p;
    state.chapter=chapter;
    state.activePaths=activePaths;
    state.paintedLength=paintedLength;
    state.ready=true;
  }

  // The scroll is the single source of truth. No independent animation clock:
  // jumping to 75% and then directly to 0 restores every stroke exactly.
  const trigger=ScrollTrigger.create({
    id:"HAZEWAVE_SITE01_BRUSH",
    trigger:journey,
    start:"top top",
    end:"bottom bottom",
    invalidateOnRefresh:true,
    onUpdate:self=>paint(self.progress),
    onRefresh:self=>paint(self.progress),
  });
  state.dispose=()=>{
    trigger.kill();
    if(window.__HAZEWAVE_SITE_01===state)delete window.__HAZEWAVE_SITE_01;
  };
  paint(trigger.progress);
  ScrollTrigger.refresh();
}
