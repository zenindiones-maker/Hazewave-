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

const rows = [];
for (const file of jsFiles) {
  const info = await stat(file);
  rows.push({ file: relative(rootPath, file), bytes: info.size });
}
rows.sort((a, b) => b.bytes - a.bytes);

const OPTIONAL_HIGH_TIER = /HighTierAtmosphere\.[^.]+\.js$/;
const optionalRows = rows.filter((row) => OPTIONAL_HIGH_TIER.test(row.file));
const coreRows = rows.filter((row) => !OPTIONAL_HIGH_TIER.test(row.file));

const total = rows.reduce((sum, row) => sum + row.bytes, 0);
const coreTotal = coreRows.reduce((sum, row) => sum + row.bytes, 0);
const optionalTotal = optionalRows.reduce((sum, row) => sum + row.bytes, 0);
const largestCore = coreRows[0]?.bytes ?? 0;
const largestOptional = optionalRows[0]?.bytes ?? 0;

console.log("HAZEWAVE_SITE_JS_BUNDLE");
for (const row of rows) {
  const tier = OPTIONAL_HIGH_TIER.test(row.file) ? "OPTIONAL_HIGH_TIER" : "CORE";
  console.log(`${row.bytes}\t${tier}\t${row.file}`);
}

console.log(`CORE_JS_BYTES=${coreTotal}`);
console.log(`CORE_LARGEST_CHUNK_BYTES=${largestCore}`);
console.log(`OPTIONAL_HIGH_TIER_JS_BYTES=${optionalTotal}`);
console.log(`OPTIONAL_HIGH_TIER_LARGEST_CHUNK_BYTES=${largestOptional}`);
console.log(`TOTAL_JS_BYTES=${total}`);

if (largestCore > 180_000) {
  throw new Error(`CORE_LARGEST_JS_CHUNK_BUDGET_EXCEEDED:${largestCore}`);
}
if (coreTotal > 220_000) {
  throw new Error(`CORE_JS_BUDGET_EXCEEDED:${coreTotal}`);
}
if (largestOptional > 160_000) {
  throw new Error(`OPTIONAL_HIGH_TIER_CHUNK_BUDGET_EXCEEDED:${largestOptional}`);
}
if (optionalTotal > 180_000) {
  throw new Error(`OPTIONAL_HIGH_TIER_JS_BUDGET_EXCEEDED:${optionalTotal}`);
}
if (total > 400_000) {
  throw new Error(`TOTAL_JS_BUDGET_EXCEEDED:${total}`);
}
