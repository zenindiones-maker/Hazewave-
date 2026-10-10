/** Non-destructive hero optimization; verified original never changes. */
import sharp from "sharp";
import {readFile,writeFile,readdir} from "node:fs/promises";
import {resolve,join} from "node:path";
import {createHash} from "node:crypto";
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
const old='src="/media/hazewave-world.jpg"';
const optimized='src="/media/hazewave-hero-1024.webp" srcset="/media/hazewave-hero-440.webp 440w, /media/hazewave-hero-1024.webp 1024w" sizes="(max-width:700px) 90vw, (max-width:1100px) 69vw, 700px"';
for(const rel of ["index.html","artists/indionesbala/index.html"]){
 const path=join(dist,rel),html=await readFile(path,"utf8");
 if(html.split(old).length!==2)throw Error("HERO_MARKUP_CHANGED:"+rel);
 await writeFile(path,html.replace(old,optimized));
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
 const approved=[/^index\.html$/,/^artists\/indionesbala\/index\.html$/,/^media\/artists\/indionesbala\.jpg$/,/^media\/hazewave-world\.jpg$/,/^media\/hazewave-hero-(440|1024)\.webp$/,/^_astro\/index\.[^.]+\.css$/,/^_astro\/_id_\.[^.]+\.css$/];
 if(observed.length!==8||observed.some(x=>!approved.some(re=>re.test(x))))throw Error("UNAPPROVED_DIST_OUTPUT:"+observed.join(","));
}
console.log("HAZEWAVE_MASTER_PRESERVED_AND_RESPONSIVE_WEBP=PASS");
