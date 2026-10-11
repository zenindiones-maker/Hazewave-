/** Non-destructive hero optimization; verified original never changes. */
import sharp from "sharp";
import {readFile,writeFile,readdir} from "node:fs/promises";
import {resolve,join} from "node:path";
import {createHash} from "node:crypto";
import {validateArtcraftBundle} from "./artcraft-build-gate.mjs";
const dist=resolve("dist");
const original=await readFile(join(dist,"media/hazewave-world.jpg"));
if(createHash("sha256").update(original).digest("hex")!=="0e89d371159947552a0c1ff5d36e856868680a03756a88d16a2c230dea1764ab")throw Error("HAZEWAVE_MASTER_SHA_DRIFT");
const meta=await sharp(original).metadata();
if(meta.width!==1024||meta.height!==1536)throw Error("HAZEWAVE_MASTER_DIMENSIONS_DRIFT");
for(const width of [440,1024]){
 const output=join(dist,`media/hazewave-hero-${width}.webp`);
 await sharp(original).extract({left:0,top:0,width:1024,height:475}).resize({width}).webp({quality:90,effort:6}).toFile(output);
 const size=(await readFile(output)).length;
 if(size>=original.length*.6)throw Error("HERO_OPTIMIZATION_INEFFECTIVE");
 console.log(`HAZEWAVE_HERO_WEBP_${width}_BYTES=${size}`);
}

const artistOriginal=await readFile(join(dist,"media/artists/indionesbala.jpg"));
const artistSha="e9c4c00ab903cfc583138e333c594fc8c99c9c868c691454f4e17744193246e4";
if(createHash("sha256").update(artistOriginal).digest("hex")!==artistSha)throw Error("OWNER_ARTIST_SHA_DRIFT");
const metaArtist=await sharp(artistOriginal).metadata();
if(metaArtist.width!==1536||metaArtist.height!==643)throw Error("OWNER_ARTIST_DIMENSIONS_DRIFT");
for(const width of [160,400]){
 const path=join(dist,"media/artists/indionesbala-signature-"+width+".webp");
 await sharp(artistOriginal).resize({width}).webp({quality:82,effort:6}).toFile(path);
 const size=(await readFile(path)).length;
 if(size>=artistOriginal.length*.6)throw Error("ARTIST_RESPONSIVE_OPTIMIZATION_INEFFECTIVE");
 console.log("INDIONESBALA_RESPONSIVE_"+width+"_BYTES="+size);
}
const artistOld='src="/media/artists/indionesbala.jpg"';
const artistSrcset='src="/media/artists/indionesbala.jpg" srcset="/media/artists/indionesbala-signature-160.webp 160w, /media/artists/indionesbala-signature-400.webp 400w, /media/artists/indionesbala.jpg 1536w"';
const old='src="/media/hazewave-world.jpg"';
const optimized='src="/media/hazewave-hero-1024.webp" srcset="/media/hazewave-hero-440.webp 440w, /media/hazewave-hero-1024.webp 1024w" sizes="(max-width:700px) 90vw, (max-width:1100px) 69vw, 700px"';
for(const rel of ["index.html","artists/indionesbala/index.html"]){
 const path=join(dist,rel),html=await readFile(path,"utf8");
 if(html.split(old).length!==2)throw Error("HERO_MARKUP_CHANGED:"+rel);

 const sizes=rel==="index.html"?"(max-width:700px) 18vw, 200px":"(max-width:700px) 18vw, (max-width:1200px) 85vw, 850px";
 if(html.split(artistOld).length!==2)throw Error("ARTIST_MARKUP_CHANGED:"+rel);
 await writeFile(path,html.replace(old,optimized).replace(artistOld,artistSrcset+' sizes="'+sizes+'"'));
}
if(process.env.HAZEWAVE_TEST_EXPERIMENTS!=="1"){
 const observed=[];
 async function walk(dir,prefix=""){
  for(const item of await readdir(dir,{withFileTypes:true})){
   const rel=prefix+item.name;
   if(item.isDirectory())await walk(join(dir,item.name),rel+"/");
   else if(item.isFile())observed.push(rel);
   else throw Error("INVALID_DIST_ENTRY:"+rel);
  }
 }
 await walk(dist);
 const approved=[/^index\.html$/,/^artists\/indionesbala\/index\.html$/,/^media\/artists\/indionesbala\.jpg$/,/^media\/artists\/indionesbala-signature-(160|400)\.webp$/,/^media\/hazewave-world\.jpg$/,/^media\/hazewave-hero-(440|1024)\.webp$/,/^_astro\/index\.[^.]+\.css$/,/^_astro\/_id_\.[^.]+\.css$/];
 // Preserve the original ten-file artist/hero distribution baseline. Extend
 // ONLY with entries from the already verified seven-Craft manifest, never
 // with arbitrary generated media, prototypes or folders.
 const manifest=validateArtcraftBundle().manifest;
 const allowArtcraft=new Set([
   "integration_manifest.json",
   ...Object.values(manifest.artifacts).map(x=>"artcraft/"+x.path),
   ...Object.values(manifest.evidence).map(x=>"artcraft/"+x.path),
   ...manifest.motion_frames.map(x=>"artcraft/"+x.path),
   "artcraft/"+manifest.designcraft_provenance.path,
 ]);
 const missing=[...allowArtcraft].filter(x=>!observed.includes(x));
 const unexpected=observed.filter(x=>!approved.some(re=>re.test(x))&&!allowArtcraft.has(x));
 if(missing.length||unexpected.length||observed.length!==10+allowArtcraft.size)
   throw Error("UNAPPROVED_DIST_OUTPUT:"+JSON.stringify({missing,unexpected,count:observed.length}));
 console.log("HAZEWAVE_ARTCRAFT_OPTIMIZED_HERO_MANIFEST_WHITELIST=PASS");
}
console.log("HAZEWAVE_MASTER_PRESERVED_AND_RESPONSIVE_WEBP=PASS");
