import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { validateRigReview } from "../scripts/validate-rig-review.mjs";

const manifest=JSON.parse(readFileSync(new URL("../../../docs/prototypes/wave-articulated-rig-v3a/rig-manifest.json",import.meta.url)));
const sha="240077ae46c0b4b0364bbd675b8ac4a3de31e733";
const sequence=[0,.2,.45,.7,1,.45,0];
const expectedPads=[0,2,6,11,12,6,0];
const expectedKnobs=[0,0,4,8,8,4,0];
const expectedSpeakers=[0,0,1,3,4,1,0];
function fixture(width=393,height=852){
  return {
    manifest,reviewedSha:sha,
    video:{streams:[{codec_type:"video",width,height,r_frame_rate:"25/1"}],format:{duration:"7.2"}},
    receipt:{schema:"HazewaveV3APortraitBrowserCapture/v1",reviewedSha:sha,
      viewport:{width,height},route:"/experimental/articulated-rig-v3a.html",
      ownerArtSha256:manifest.source_sha256,detectedPieces:{pads:12,knobs:8,speakers:4},
      sampledStates:sequence.map((p,i)=>({progress:p,activePads:expectedPads[i],
        activeKnobs:expectedKnobs[i],activeSpeakers:expectedSpeakers[i],
        stroke:i===4?1:i===0||i===6?0:Math.min(1,p),
        machineTransform:i===0||i===6?"matrix(1,0,0,1,0,0)":"matrix(1.05,0,0,1.05,-10,20)",
        knobTransform:i===0||i===6?"rotate(0deg)":"rotate(18deg)",
        speakerTransform:i===0||i===6?"scale(1)":"scale(1.02)"})),
      javascriptErrors:[],horizontalOverflow:0,
      videoRecorded:true,videoFileBytes:100000,source:"real_browser",
      claimsProductionApproval:false,
      claimsCinematicTraversal:false
    }};
}
test("V3A unit proof accepts 12/8/4 on true 393x852 portrait but DENIES cinematic acceptance",()=>{
 const r=validateRigReview(fixture());
 assert.equal(r.technicalRigProven,true);
 assert.equal(r.cinematicTraversalProven,false);
 assert.equal(r.productionApproved,false);
 assert.equal(r.reviewedSha,sha);
});
test("second phone portrait 360x800 is also a distinct real capture",()=>{
 const r=validateRigReview(fixture(360,800));
 assert.equal(r.physicalPartsVerified,24);
});
test("owner-uploaded old V1 landscape 960x540 is REJECTED as V3A video",()=>{
 const f=fixture(960,540);
 f.receipt.viewport={width:960,height:540};
 f.receipt.detectedPieces.pads=9;
 assert.throws(()=>validateRigReview(f),/VIDEO_NOT_PHONE_PORTRAIT|V3A_PART_COUNT_MISMATCH/);
});
test("rejects nine pads even in true phone video",()=>{
 const f=fixture();f.receipt.detectedPieces.pads=9;
 assert.throws(()=>validateRigReview(f),/V3A_PART_COUNT_MISMATCH/);
});
test("rejects fake video dimensions, wrong source commit and unlicensed proof claims",()=>{
 const f=fixture();f.video.streams[0].width=360;f.video.streams[0].height=800;
 assert.throws(()=>validateRigReview(f),/VIDEO_RESOLUTION_DOES_NOT_MATCH_BROWSER/);
 const s=fixture();s.receipt.reviewedSha="a".repeat(40);
 assert.throws(()=>validateRigReview(s),/EXACT_SHA_MISMATCH/);
 const t=fixture();t.receipt.claimsCinematicTraversal=true;
 assert.throws(()=>validateRigReview(t),/UNAUTHORIZED_CINEMATIC_OR_PRODUCTION_CLAIM/);
 const u=fixture();u.receipt.claimsProductionApproval=true;
 assert.throws(()=>validateRigReview(u),/UNAUTHORIZED_CINEMATIC_OR_PRODUCTION_CLAIM/);
});
test("rejects fake reversibility and unchanged mechanical transforms",()=>{
 const f=fixture();f.receipt.sampledStates[6].activePads=1;
 assert.throws(()=>validateRigReview(f),/V3A_REVERSE_INCOMPLETE/);
 const g=fixture();for(const s of g.receipt.sampledStates)s.knobTransform="rotate(0deg)";
 assert.throws(()=>validateRigReview(g),/V3A_PHYSICAL_MOTION_MISSING/);
});
test("rejects missing encoded video, old frame rate or short clip",()=>{
 const f=fixture();f.video.streams[0].r_frame_rate="0/0";
 assert.throws(()=>validateRigReview(f),/VIDEO_FPS_INVALID/);
 const g=fixture();g.video.format.duration="0.01";
 assert.throws(()=>validateRigReview(g),/VIDEO_DURATION_TOO_SHORT/);
 const h=fixture();h.receipt.videoFileBytes=0;
 assert.throws(()=>validateRigReview(h),/VIDEO_BYTES_MISSING/);
});
test("requires real source-art hash matching the V3A manifest",()=>{
 const f=fixture();f.receipt.ownerArtSha256="b".repeat(64);
 assert.throws(()=>validateRigReview(f),/OWNER_ART_PROVENANCE_DRIFT/);
});
