/** Fail closed: reviewed public distribution contains one artist only. Original files remain unchanged in Git history. */
import {readdir,rm,readFile,rename} from "node:fs/promises";import {fileURLToPath} from "node:url";import {resolve,join} from "node:path";
import {validateArtcraftBundle} from "./artcraft-build-gate.mjs";
const artcraftBundle=validateArtcraftBundle();
const dist=resolve(fileURLToPath(new URL("../dist/",import.meta.url)));
const page=await readFile(join(dist,"index.html"),"utf8");
if(!page.includes('data-experience="indionesbala-only"')||!page.includes('src="/media/artists/indionesbala.jpg"'))throw Error("UNREVIEWED_ARTIST_SCOPE");
if(/(Baazü|Aquaverno|Hemorragia|Barak Ozama|world-switcher|chapter-nav|data-world-stop)/i.test(page))throw Error("FORBIDDEN_ASSET_OR_UI");
const slugs=["aquaverno","baazu","barak-ozama-beats","hemorragia-cosmica"];
for(const slug of slugs){await rm(join(dist,"artists",slug),{recursive:true,force:true});}
// The owner's original named .webp is actually JFIF JPEG. Only the
// build output is renamed: exact original pixels and hash are preserved.
const art=join(dist,"media","artists");
const oldFormat=join(art,"indionesbala.webp");
const correctFormat=join(art,"indionesbala.jpg");
const originalBytes=await readFile(oldFormat);
if(originalBytes.length<4||originalBytes[0]!==0xff||originalBytes[1]!==0xd8||originalBytes[2]!==0xff)
  throw Error("OWNER_INDIONESBALA_JPEG_SIGNATURE_UNEXPECTED");
await rename(oldFormat,correctFormat);
for(const filename of await readdir(art)){if(filename!=="indionesbala.jpg")await rm(join(art,filename),{force:true});}
console.log("INDIONESBALA_PUBLIC_MIME=image/jpeg");
await rm(join(dist,"media","worlds"),{recursive:true,force:true});
await rm(join(dist,"media","hazewave-world.jpg.webp"),{force:true});
for(const slug of slugs){try{await readFile(join(dist,"artists",slug,"index.html"));throw Error("FORBIDDEN_ROUTE_RESURFACED")}catch(e){if(e.code!=="ENOENT")throw e;}}
// Historical interactive proofs remain in the tracked sources and are tested
// in an explicit temporary QA build, never delivered as part of the owner site.
if (process.env.HAZEWAVE_TEST_EXPERIMENTS !== "1") {
  await rm(join(dist,"living-universe-p0"),{recursive:true,force:true});
  await rm(join(dist,"experimental"),{recursive:true,force:true});
  const modules=join(dist,"_astro");
  for(const name of await readdir(modules)) {
    if(/^(?:living-universe-p0|wave-p0-)/.test(name))await rm(join(modules,name),{force:true});
  }
  // Strict allowlist: an unreviewed Astro route or leaked asset fails the
  // build rather than silently returning to the production distribution.
  const actual=[];
  async function walk(dir,prefix=""){
    for(const item of await readdir(dir,{withFileTypes:true})){
      const rel=prefix+item.name;
      if(item.isDirectory())await walk(join(dir,item.name),rel+"/");
      else if(item.isFile())actual.push(rel);
      else throw Error("UNEXPECTED_OUTPUT_TYPE:"+rel);
    }
  }
  await walk(dist);
  const allow=[
    /^index\.html$/,
    /^artists\/indionesbala\/index\.html$/,
    /^media\/artists\/indionesbala\.jpg$/,
    /^media\/hazewave-world\.jpg$/,
    /^_astro\/index\.[^.]+\.css$/,
    /^_astro\/_id_\.[^.]+\.css$/
  ];
  // The validated manifest is the SOLE dynamic file allowlist. A raw workflow
  // artifact or unreviewed site file cannot self-authorize entry into dist.
  const m=artcraftBundle.manifest;
  const approvedArtcraft=new Set([
    "integration_manifest.json",
    ...Object.values(m.artifacts).map(row=>"artcraft/"+row.path),
    ...Object.values(m.evidence).map(row=>"artcraft/"+row.path),
    ...m.motion_frames.map(row=>"artcraft/"+row.path),
    "artcraft/"+m.designcraft_provenance.path,
  ]);
  const missing=[...approvedArtcraft].filter(name=>!actual.includes(name));
  if(missing.length)throw Error("APPROVED_OUTPUT_MISSING:"+missing.join(","));
  const unexpected=actual.filter(name=>!allow.some(re=>re.test(name))&&!approvedArtcraft.has(name));
  if(unexpected.length)throw Error("UNAPPROVED_STATIC_ROUTE_OR_MEDIA:"+unexpected.join(","));
  if(actual.length!==6+approvedArtcraft.size)
    throw Error("APPROVED_OUTPUT_MISSING_OR_EXTRA:"+actual.join(","));
  const staged=JSON.parse(await readFile(join(dist,"integration_manifest.json"),"utf8"));
  if(staged.head_sha!==m.head_sha||staged.run_id!==m.run_id)
    throw Error("DIST_MANIFEST_IDENTITY_MISMATCH");
  console.log("SITE_DIST_ONLY_MANIFEST_WHITELISTED_ART=PASS");
  console.log("PRODUCTION_DIST_ONLY_HAZEWAVE_AND_INDIONESBALA=PASS");
} else {
  console.log("TEMPORARY_EXPERIMENT_QA_BUILD_NOT_FOR_DELIVERY=TRUE");
}
console.log("PUBLIC_ARTIST_SCOPE=INDIONESBALA_ONLY");console.log("OTHER_ARTIST_MEDIA_IN_DIST=ZERO");
