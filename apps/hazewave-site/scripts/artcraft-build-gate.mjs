/** HAZEWAVE WAVE — seven real Craft tools, one fail-closed build admission.
 * No app runtime, no owner-private-art access, no publication authority.
 * This gate reads only an external exact-run ArtCraft bundle, and copies
 * precisely its checked media/evidence into Astro's local dist after build.
 */
import {createHash} from "node:crypto";
import {
  copyFileSync, existsSync, lstatSync, mkdirSync, readFileSync, realpathSync,
  statSync, writeFileSync,
} from "node:fs";
import {basename, dirname, isAbsolute, join, relative, resolve, sep} from "node:path";
import {fileURLToPath} from "node:url";

// During Astro prerender Vite relocates bundled modules to dist/.prerender.
// Resolve the source site via immutable, well-known provenance in cwd, rather
// than treating the relocated import.meta.url as an authority for source files.
const moduleSite=resolve(dirname(fileURLToPath(import.meta.url)),"..");
const cwdSite=resolve(process.cwd());
const checkoutSite=resolve(cwdSite,"apps/hazewave-site");
const SITE=[moduleSite,cwdSite,checkoutSite].find(path=>
  existsSync(join(path,"owner-art-provenance.json"))&&
  existsSync(join(path,"astro.config.mjs"))
);
if(!SITE)throw Error("HAZEWAVE_ARTCRAFT_SOURCE_SITE_UNRESOLVED");
const REPO=resolve(SITE,"../..");
const SCHEMA="HazewaveArtCraftSevenLabHandoff/v1";
const ARTIFACTS={
  photocraft:"assets/photocraft.png",
  lightcraft:"assets/lightcraft.png",
  designcraft:"assets/designcraft.pdf",
  pdfcraft:"assets/pdfcraft.png",
  vectorcraft:"assets/vectorcraft.png",
  effectcraft:"assets/sonic-portal-00.png",
  filmcraft:"assets/effectcraft-reference.webm",
};
const EVIDENCE={
  photocraft:"receipts/photocraft.json",
  lightcraft:"receipts/lightcraft.json",
  designcraft:"receipts/designcraft.json",
  pdfcraft:"receipts/pdfcraft.json",
  vectorcraft:"receipts/vectorcraft.json",
  effectcraft:"receipts/effectcraft.json",
  filmcraft:"receipts/filmcraft.txt",
};
const OWNERS={
  hazewave:{
    manifestPath:"media/hazewave-world.jpg",
    sourcePath:"media/hazewave-world.jpg",
    provenancePath:"/media/hazewave-world.jpg",
  },
  indionesbala:{
    manifestPath:"media/artists/indionesbala.jpg",
    sourcePath:"media/artists/indionesbala.webp",
    provenancePath:"/media/artists/indionesbala.webp",
  },
};
const SHA=/^[0-9a-f]{64}$/;
const COMMIT=/^[0-9a-f]{40}$/;
const RUN=/^[0-9]{8,15}$/;

function deny(problem){throw new Error("HAZEWAVE_ARTCRAFT_BUILD_BLOCKED:"+problem);}
function digest(buf){return createHash("sha256").update(buf).digest("hex");}
function exactKeys(input, expected, label){
  if(!input || typeof input!=="object" || Array.isArray(input) ||
     Object.keys(input).sort().join("|")!==Object.keys(expected).sort().join("|"))
    deny(label+"_FIELDS");
}
function within(parent, child){
  const rel=relative(parent,child);
  return rel!==""&&!rel.startsWith(".."+sep)&&rel!==".."&&!isAbsolute(rel);
}
function checkedFile(root, rel, expectedSha){
  if(typeof rel!=="string"||!rel||rel.startsWith("/")||
      rel.includes("\\")||rel.split("/").some(part=>!part||part==="."||part==="..")||
      !SHA.test(expectedSha||""))deny("PATH_OR_SHA_INVALID");
  const full=resolve(root,rel);
  if(!within(root,full))deny("FILE_ESCAPE");
  let current=root;
  for(const part of rel.split("/")){
    current=join(current,part);
    if(!existsSync(current) || lstatSync(current).isSymbolicLink())deny("SYMLINK_OR_MISSING:"+rel);
  }
  if(!statSync(full).isFile())deny("NOT_REGULAR:"+rel);
  const bytes=readFileSync(full);
  if(digest(bytes)!==expectedSha)deny("SHA256_MISMATCH:"+rel);
  return full;
}
function confirmRow(root,row,want,label){
  if(!row||typeof row!=="object"||Object.keys(row).sort().join(",")!=="path,sha256")
    deny(label+"_INVALID");
  if(row.path!==want)deny(label+"_PATH");
  return checkedFile(root,want,row.sha256);
}
function approvedIdentity(manifest){
  const receipt=JSON.parse(readFileSync(join(SITE,"owner-art-provenance.json"),"utf8"));
  const evidence=new Map(receipt.assets.map(x=>[x.asset,x]));
  exactKeys(manifest.identity_assets,OWNERS,"IDENTITY");
  for(const [name,ref] of Object.entries(OWNERS)){
    const row=manifest.identity_assets[name];
    if(row?.path!==ref.manifestPath || row?.sha256!==evidence.get(ref.provenancePath)?.sha256)
      deny("OWNER_ART_NOT_APPROVED:"+name);
    checkedFile(join(SITE,"public"),ref.sourcePath,row.sha256);
  }
}
function bundleParams(args={}){
  const bundle=args.bundle||process.env.HAZEWAVE_ARTCRAFT_BUNDLE;
  const runId=args.runId||process.env.HAZEWAVE_ARTCRAFT_RUN_ID;
  const headSha=args.headSha||process.env.HAZEWAVE_ARTCRAFT_HEAD_SHA;
  if(typeof bundle!=="string"||!bundle||!RUN.test(runId||"")||!COMMIT.test(headSha||""))
    deny("EXPLICIT_BUNDLE_RUN_AND_HEAD_REQUIRED");
  const root=resolve(bundle);
  if(!existsSync(root)||lstatSync(root).isSymbolicLink()||!statSync(root).isDirectory()||
    !within(REPO,root) && !within(root,REPO) && root===REPO)deny("BUNDLE_ROOT_INVALID");
  if(root===REPO||within(REPO,root))deny("BUNDLE_MUST_REMAIN_OUTSIDE_REPO");
  if(realpathSync(root)!==root)deny("BUNDLE_ROOT_SYMLINK_PATH_FORBIDDEN");
  return {root,runId,headSha};
}

export function validateArtcraftBundle(args={}){
  const {root,runId,headSha}=bundleParams(args);
  const manifestPath=join(root,"integration_manifest.json");
  if(!existsSync(manifestPath)||lstatSync(manifestPath).isSymbolicLink())
    deny("INTEGRATION_MANIFEST_MISSING");
  let m;
  try {m=JSON.parse(readFileSync(manifestPath,"utf8"));}catch{deny("INTEGRATION_MANIFEST_INVALID_JSON");}
  if(!m || typeof m!=="object" ||
     m.schema!==SCHEMA||m.repository!=="zenindiones-maker/Hazewave-"||
     m.domain!=="WAVE"||m.authority!=="HAZEWAVE_HARNESS"||
     m.classification!=="PUBLIC"||m.run_id!==runId||m.head_sha!==headSha||
     m.owner_private_media_used!==false||m.production_approved!==false||
     m.publication_attempted!==false||m.site_integration_status!=="LAB_ASSETS_ONLY"||
     m.all_seven_external_clis_executed!==true)deny("MANIFEST_AUTHORITY_STATUS_OR_COMMIT");

  exactKeys(m.artifacts,ARTIFACTS,"ARTIFACTS");
  exactKeys(m.evidence,EVIDENCE,"EVIDENCE");
  const fileMap=new Map();
  for(const [name,rel] of Object.entries(ARTIFACTS)){
    const full=confirmRow(root,m.artifacts[name],rel,"ARTIFACT_"+name);
    fileMap.set(rel,full);
  }
  for(const [name,rel] of Object.entries(EVIDENCE)){
    const full=confirmRow(root,m.evidence[name],rel,"EVIDENCE_"+name);
    fileMap.set(rel,full);
  }
  if(!Array.isArray(m.motion_frames)||m.motion_frames.length!==8)deny("EIGHT_EFFECT_FRAMES_REQUIRED");
  for(let i=0;i<8;i++){
    const rel="assets/sonic-portal-"+String(i).padStart(2,"0")+".png";
    const full=confirmRow(root,m.motion_frames[i],rel,"FRAME_"+i);
    fileMap.set(rel,full);
  }
  const prov=m.designcraft_provenance;
  if(!prov||typeof prov!=="object"||
     Object.keys(prov).sort().join("|")!=="artifact_hash|path|sha256|stage_id"||
     prov.path!=="receipts/designcraft-provenance.json"||
     prov.stage_id!=="artcraft-"+runId+"-designcraft"||
     prov.artifact_hash!==m.artifacts.designcraft.sha256)deny("DESIGNCRAFT_PROVENANCE_MISMATCH");
  const provenanceFile=checkedFile(root,prov.path,prov.sha256);
  fileMap.set(prov.path,provenanceFile);
  const detail=JSON.parse(readFileSync(provenanceFile,"utf8"));
  if(detail.schema!=="HazewaveDesignCraftProvenance/v1" ||
     detail.stage_id!==prov.stage_id||detail.producer!=="designcraft"||
     detail.source_path!=="designcraft-layout.pdf"||
     detail.artifact_hash!==prov.artifact_hash ||
     typeof detail.timestamp!=="string" ||
     !/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$/.test(detail.timestamp) ||
     !Number.isFinite(Date.parse(detail.timestamp)))deny("DESIGNCRAFT_PROVENANCE_RECEIPT_INVALID");
  for(const name of ["photocraft","lightcraft","designcraft","pdfcraft"]){
    const row=JSON.parse(readFileSync(fileMap.get(EVIDENCE[name]),"utf8"));
    if(row.tool!==name||row.schema!=="HazewaveArtCraftExternalRealSmoke/v1" ||
       row.project!=="zenindiones-maker/Hazewave-"||
       row.real_execution!==true||row.authority!=="NONE"||
       row.owner_private_media_used!==false||row.production_approved!==false||
       row.output_sha256!==m.artifacts[name].sha256 ||
       row.admission?.task_id!=="artcraft-"+runId+"-"+name ||
       row.admission?.domain!=="WAVE"||
       row.admission?.authority!=="HAZEWAVE_HARNESS")deny("CRAFT_RECEIPT_INVALID:"+name);
    if(name==="pdfcraft" && (row.upstream_task_id!==prov.stage_id ||
                             row.input_sha256!==prov.artifact_hash))
      deny("PDFCRAFT_DESIGNCRAFT_CHAIN_BROKEN");
    if(name==="lightcraft"&&
       (row.upstream_task_id!=="artcraft-"+runId+"-photocraft"||
        row.input_sha256!==m.artifacts.photocraft.sha256))
       deny("LIGHTCRAFT_PHOTOCRAFT_CHAIN_BROKEN");
  }
  const vector=JSON.parse(readFileSync(fileMap.get(EVIDENCE.vectorcraft),"utf8"));
  if(vector.tool_executed!==true||vector.output_png_sha256!==m.artifacts.vectorcraft.sha256||
     vector.production_approved!==false)deny("VECTORCRAFT_NOT_VERIFIED");
  const fx=JSON.parse(readFileSync(fileMap.get(EVIDENCE.effectcraft),"utf8"));
  if(fx.real_effectcraft_render!==true||fx.filmcraft_probe_executed!==true||
     fx.effectcraft_video_sha256!==m.artifacts.filmcraft.sha256||
     fx.production_approved!==false||fx.owner_private_media_used!==false)
    deny("EFFECTCRAFT_FILMCRAFT_NOT_VERIFIED");
  approvedIdentity(m);
  return {root,manifest:m,files:fileMap};
}

export function verifiedSiteAssets(args={}){
  const {manifest}=validateArtcraftBundle(args);
  const asset=(tool)=>"/artcraft/"+manifest.artifacts[tool].path;
  return {
    manifest,
    media:Object.fromEntries(Object.keys(ARTIFACTS).map(tool=>[tool,asset(tool)])),
    frames:manifest.motion_frames.map(row=>"/artcraft/"+row.path),
    identities:Object.fromEntries(Object.keys(OWNERS).map(key=>[key,"/"+manifest.identity_assets[key].path])),
  };
}
export function stageVerifiedArtcraftDist(dir,args={}){
  const {root,manifest,files}=validateArtcraftBundle(args);
  const target=resolve(dir);
  if(!existsSync(target)||!statSync(target).isDirectory())deny("ASTRO_OUTPUT_MISSING");
  for(const [rel,original] of files.entries()){
    const dest=resolve(target,"artcraft",rel);
    if(!within(target,dest))deny("ASTRO_OUTPUT_PATH_ESCAPE");
    mkdirSync(dirname(dest),{recursive:true});
    if(existsSync(dest))deny("ASTRO_OUTPUT_OVERWRITE_DENIED:"+rel);
    copyFileSync(original,dest);
    if(digest(readFileSync(dest))!==digest(readFileSync(original)))deny("OUTPUT_COPY_CORRUPTED:"+rel);
  }
  const dst=join(target,"integration_manifest.json");
  if(existsSync(dst))deny("MANIFEST_ALREADY_IN_ASTRO_DIST");
  copyFileSync(join(root,"integration_manifest.json"),dst);
  if(JSON.parse(readFileSync(dst,"utf8")).head_sha!==manifest.head_sha)
    deny("ASTRO_MANIFEST_CHANGED");
  console.log("HAZEWAVE_ASTRO_SEVEN_CRAFT_ARTIFACTS_SHA_VERIFIED=PASS");
}

export function artcraftBuildIntegration(){
  return {name:"hazewave-seven-artcraft-gate",hooks:{
    "astro:build:start"(){
      validateArtcraftBundle();
      console.log("HAZEWAVE_ASTRO_MANIFEST_REQUIRED_AT_BUILD_START=PASS");
    },
    "astro:build:done"({dir}){
      stageVerifiedArtcraftDist(fileURLToPath(dir));
    },
  }};
}

if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const [command,...rest]=process.argv.slice(2);
  const args={};
  for(let i=0;i<rest.length;i+=2){
    if(!["--bundle","--run-id","--head-sha"].includes(rest[i])||!rest[i+1])
      deny("CLI_SYNTAX");
    args[{"--bundle":"bundle","--run-id":"runId","--head-sha":"headSha"}[rest[i]]]=rest[i+1];
  }
  if(command!=="verify")deny("CLI_COMMAND_REQUIRED");
  validateArtcraftBundle(args);
  console.log("HAZEWAVE_SITE_SEVEN_ARTCRAFT_MANIFEST=VERIFIED");
  console.log("HAZEWAVE_SITE_PRODUCTION_APPROVED=FALSE");
}
