/**
 * Fail-closed evidence classification: a V3A component demonstration
 * cannot be promoted to cinematic world acceptance by tests or video titles.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";

const EXPECTED_ROUTE="/experimental/articulated-rig-v3a.html";
const REQUIRED_PROGRESS=[0,.2,.45,.7,1,.45,0];
const SHA=/^[a-f0-9]{40}$/;
const HASH=/^[a-f0-9]{64}$/;
const fail=label=>{ throw new Error(label); };
const close=(a,b,tolerance=.025)=>Math.abs(a-b)<=tolerance;

function safeString(value){return typeof value==="string"?value:"";}

export function validateRigReview({manifest,reviewedSha,video,receipt}){
 if(!SHA.test(reviewedSha))fail("REVIEWED_SHA_REQUIRED");
 if(manifest?.schema!=="HazewaveArticulatedRig/v1" ||
   !HASH.test(manifest.source_sha256))fail("V3A_MANIFEST_UNQUALIFIED");
 const pieces=manifest.pieces;
 if(!Array.isArray(pieces))fail("V3A_MANIFEST_PIECES_MISSING");
 const types={pad:0,knob:0,speaker:0};
 const seen=new Set();
 for(const p of pieces){
   if(!(p.type in types) || seen.has(p.id) || !p.file ||
      typeof p.activation!=="number")fail("V3A_MANIFEST_PART_INVALID");
   seen.add(p.id);types[p.type]++;
 }
 if(types.pad!==12 || types.knob!==8 || types.speaker!==4 ||
    pieces.length!==24)fail("V3A_MANIFEST_PART_COUNT_MISMATCH");
 if(receipt?.schema!=="HazewaveV3APortraitBrowserCapture/v1" ||
    receipt.route!==EXPECTED_ROUTE ||
    receipt.reviewedSha!==reviewedSha)fail("EXACT_SHA_MISMATCH");
 if(receipt.ownerArtSha256!==manifest.source_sha256)
   fail("OWNER_ART_PROVENANCE_DRIFT");
 if(receipt.claimsProductionApproval!==false ||
    receipt.claimsCinematicTraversal!==false)
   fail("UNAUTHORIZED_CINEMATIC_OR_PRODUCTION_CLAIM");
 if(receipt.source!=="real_browser" || receipt.videoRecorded!==true)
   fail("ACTUAL_BROWSER_VIDEO_REQUIRED");
 const vw=receipt.viewport?.width,vh=receipt.viewport?.height;
 if(!((vw===393 && vh===852)||(vw===360 && vh===800)))
   fail("VIDEO_NOT_PHONE_PORTRAIT");
 if(receipt.detectedPieces?.pads!==12 ||
    receipt.detectedPieces?.knobs!==8 ||
    receipt.detectedPieces?.speakers!==4)
   fail("V3A_PART_COUNT_MISMATCH");
 if(!Array.isArray(receipt.javascriptErrors) ||
    receipt.javascriptErrors.length!==0 ||
    receipt.horizontalOverflow>1)fail("V3A_BROWSER_ERRORS_OR_OVERFLOW");
 if(!Number.isInteger(receipt.videoFileBytes) ||
    receipt.videoFileBytes<1000)fail("VIDEO_BYTES_MISSING");
 const streams=video?.streams;
 if(!Array.isArray(streams)||streams.length===0)
   fail("VIDEO_STREAM_NOT_FOUND");
 const track=streams.find(s=>s.codec_type==="video") || streams[0];
 if(track.width!==vw||track.height!==vh)
   fail("VIDEO_RESOLUTION_DOES_NOT_MATCH_BROWSER");
 const fr=safeString(track.r_frame_rate).split("/");
 const fps=fr.length===2?Number(fr[0])/Number(fr[1]):Number(fr[0]);
 if(!Number.isFinite(fps)||fps<10||fps>120)
   fail("VIDEO_FPS_INVALID");
 const duration=Number(video?.format?.duration);
 if(!Number.isFinite(duration)||duration<2)
   fail("VIDEO_DURATION_TOO_SHORT");
 const samples=receipt.sampledStates;
 if(!Array.isArray(samples)||samples.length!==REQUIRED_PROGRESS.length)
   fail("V3A_SAMPLE_SERIES_INVALID");
 for(let i=0;i<samples.length;i++){
   const s=samples[i];
   if(!close(s.progress,REQUIRED_PROGRESS[i]))
     fail("V3A_SAMPLE_PROGRESS_INCORRECT");
   for(const prop of ["activePads","activeKnobs","activeSpeakers"]){
     if(!Number.isInteger(s[prop])||s[prop]<0)
       fail("V3A_SAMPLE_COUNTER_INVALID");
   }
   if(typeof s.machineTransform!=="string" ||
      typeof s.knobTransform!=="string" ||
      typeof s.speakerTransform!=="string")
     fail("V3A_MECHANICAL_STATE_NOT_RECORDED");
 }
 const start=samples[0],end=samples[4],last=samples[6];
 if(start.activePads!==0||start.activeKnobs!==0||
    start.activeSpeakers!==0 || !close(start.stroke,0))
   fail("V3A_START_POSE_INVALID");
 if(last.activePads!==0||last.activeKnobs!==0||
    last.activeSpeakers!==0 || !close(last.stroke,0))
   fail("V3A_REVERSE_INCOMPLETE");
 if(end.activePads!==12||end.activeKnobs!==8||
    end.activeSpeakers!==4||end.stroke<.98)
   fail("V3A_END_POSE_INVALID");
 if(samples[3].activePads<8||samples[3].activeKnobs<4)
   fail("V3A_MID_POSE_INVALID");
 if(new Set(samples.map(s=>s.machineTransform)).size<2 ||
    new Set(samples.map(s=>s.knobTransform)).size<2 ||
    new Set(samples.map(s=>s.speakerTransform)).size<2)
   fail("V3A_PHYSICAL_MOTION_MISSING");
 if(!close(samples[0].stroke,samples[6].stroke))
   fail("V3A_STROKE_REVERSE_MISSING");
 return {
   schema:"HazewaveV3AReviewedPortraitVideo/v1",
   reviewedSha,
   manifestSourceSha256:manifest.source_sha256,
   videoResolution:[vw,vh],
   encodedVideoFps:fps,
   encodedVideoDurationSeconds:duration,
   physicalPartsVerified:24,
   pads:12,knobs:8,speakers:4,
   technicalRigProven:true,
   cinematicTraversalProven:false,
   secondIllustratedRegionProven:false,
   productionApproved:false,
   ownerCreativeApproval:false,
   verdict:"UNIT_RIG_PROOF_ONLY_CINEMATIC_GATE_BLOCKED",
   evidenceKind:"ACTUAL_PORTRAIT_BROWSER_VIDEO_WITH_EXACT_SHA"
 };
}

function main(){
 const args=process.argv.slice(2);
 if(args.length!==8 ||
    args[0]!=="--manifest"||args[2]!=="--receipt"||
    args[4]!=="--video"||args[6]!=="--output")
    fail("USAGE_REQUIRE_MANIFEST_RECEIPT_VIDEO_OUTPUT");
 const manifestBytes=readFileSync(args[1]);
 const receiptBytes=readFileSync(args[3]);
 if(manifestBytes.length>300000||receiptBytes.length>200000)
   fail("INPUT_TOO_LARGE");
 const manifest=JSON.parse(manifestBytes.toString("utf8"));
 const receipt=JSON.parse(receiptBytes.toString("utf8"));
 const currentSha=execFileSync("git",["rev-parse","HEAD"],{encoding:"utf8"}).trim();
 if(!SHA.test(currentSha)||receipt.reviewedSha!==currentSha)
   fail("SOURCE_COMMIT_NOT_EXACTLY_CHECKED_OUT");
 const videoFile=readFileSync(args[5]);
 const video=JSON.parse(execFileSync("ffprobe",[
   "-v","error","-show_entries","stream=codec_type,width,height,r_frame_rate:format=duration",
   "-of","json",args[5]
 ],{encoding:"utf8",timeout:15000}));
 receipt.videoFileBytes=videoFile.length;
 const proof=validateRigReview({manifest,reviewedSha:currentSha,video,receipt});
 proof.videoSha256=createHash("sha256").update(videoFile).digest("hex");
 writeFileSync(args[7],JSON.stringify(proof,null,2)+"\n",{flag:"wx",mode:0o600});
 console.log("V3A_EXACT_HEAD_SHA="+currentSha);
 console.log("V3A_ACTUAL_PORTRAIT_MEDIA=PASS_"+proof.videoResolution.join("x"));
 console.log("V3A_PADS=12_V3A_KNOBS=8_V3A_SPEAKERS=4");
 console.log("V3A_CINEMATIC_ACCEPTANCE=BLOCKED_NOT_PROVEN");
}
if(process.argv[1] && import.meta.url===new URL("file://"+process.argv[1]).href){
 try{main()}catch(e){console.error("V3A_VIDEO_PROOF=BLOCKED:"+e.message);process.exitCode=20}
}
