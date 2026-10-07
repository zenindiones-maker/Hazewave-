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

const total = rows.reduce((sum, row) => sum + row.bytes, 0);
const largest = rows[0]?.bytes ?? 0;

console.log("HAZEWAVE_SITE_JS_BUNDLE");
for (const row of rows) console.log(`${row.bytes}\t${row.file}`);
console.log(`TOTAL_JS_BYTES=${total}`);
console.log(`LARGEST_JS_CHUNK_BYTES=${largest}`);

if (largest > 700_000) throw new Error(`LARGEST_JS_CHUNK_BUDGET_EXCEEDED:${largest}`);
if (total > 900_000) throw new Error(`TOTAL_JS_BUDGET_EXCEEDED:${total}`);
