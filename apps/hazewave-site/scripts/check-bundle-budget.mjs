import { readdir, stat } from "node:fs/promises";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const rootPath = fileURLToPath(new URL("../dist/", import.meta.url));
const jsFiles = [];
async function walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) await walk(path);
    else if (entry.name.endsWith(".js")) jsFiles.push(path);
  }
}
await walk(rootPath);
const rows=[];
for(const file of jsFiles) {
  const info=await stat(file);
  rows.push({file:relative(rootPath,file),bytes:info.size});
}
rows.sort((a,b)=>b.bytes-a.bytes);

// Do NOT relax the existing site budgets to admit the P0 prototype.
// Only explicitly named renderer route/vendor chunks enter the independent
// P0-only experimental budget, and the full site budget remains bounded.
const OPTIONAL_HIGH_TIER=/HighTierAtmosphere\.[^.]+\.js$/;
const OPTIONAL_LIVING_P0=/(?:wave-p0-pixi-v8|wave-p0-gsap|living-universe-p0)\.[^.]+\.js$/;
const p0Rows=rows.filter(r=>OPTIONAL_LIVING_P0.test(r.file));
const optionalRows=rows.filter(r=>OPTIONAL_HIGH_TIER.test(r.file));
const coreRows=rows.filter(r=>!OPTIONAL_HIGH_TIER.test(r.file)&&!OPTIONAL_LIVING_P0.test(r.file));

const sum=a=>a.reduce((n,row)=>n+row.bytes,0);
const total=sum(rows),coreTotal=sum(coreRows),optionalTotal=sum(optionalRows),p0Total=sum(p0Rows);
const largest=a=>a[0]?.bytes??0;

console.log("HAZEWAVE_SITE_JS_BUNDLE");
for(const row of rows){
  const tier=OPTIONAL_HIGH_TIER.test(row.file)?"OPTIONAL_HIGH_TIER":OPTIONAL_LIVING_P0.test(row.file)?"EXPERIMENTAL_P0":"CORE";
  console.log(row.bytes+"\t"+tier+"\t"+row.file);
}
console.log("CORE_JS_BYTES="+coreTotal);
console.log("CORE_LARGEST_CHUNK_BYTES="+largest(coreRows));
console.log("OPTIONAL_HIGH_TIER_JS_BYTES="+optionalTotal);
console.log("OPTIONAL_HIGH_TIER_LARGEST_CHUNK_BYTES="+largest(optionalRows));
console.log("EXPERIMENTAL_P0_JS_BYTES="+p0Total);
console.log("EXPERIMENTAL_P0_LARGEST_CHUNK_BYTES="+largest(p0Rows));
console.log("TOTAL_JS_BYTES="+total);

if(largest(coreRows)>180_000)throw new Error("CORE_LARGEST_JS_CHUNK_BUDGET_EXCEEDED:"+largest(coreRows));
if(coreTotal>220_000)throw new Error("CORE_JS_BUDGET_EXCEEDED:"+coreTotal);
if(largest(optionalRows)>160_000)throw new Error("OPTIONAL_HIGH_TIER_CHUNK_BUDGET_EXCEEDED:"+largest(optionalRows));
if(optionalTotal>180_000)throw new Error("OPTIONAL_HIGH_TIER_JS_BUDGET_EXCEEDED:"+optionalTotal);
if(!p0Rows.length)throw new Error("EXPERIMENTAL_P0_CHUNKS_NOT_ISOLATED");
if(largest(p0Rows)>525_000)throw new Error("EXPERIMENTAL_P0_LARGEST_CHUNK_BUDGET_EXCEEDED:"+largest(p0Rows));
if(p0Total>750_000)throw new Error("EXPERIMENTAL_P0_BUDGET_EXCEEDED:"+p0Total);
if(total>1_000_000)throw new Error("TOTAL_JS_BUDGET_EXCEEDED:"+total);
