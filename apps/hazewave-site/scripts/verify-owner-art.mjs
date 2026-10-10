import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const provenance = JSON.parse(readFileSync(resolve(root, "owner-art-provenance.json"), "utf8"));
const useDist = process.argv.includes("--dist");
const base = useDist ? resolve(root, "dist") : resolve(root, "public");

let failed = false;
// The source retains historical originals intact; the production dist contains
// only the approved Hazewave master artwork and sole Indionesbala artist.
const allowedDistAssets = new Set([
  "/media/hazewave-world.jpg",
  "/media/artists/indionesbala.webp",
]);
if (useDist && !provenance.assets.some((asset) => !allowedDistAssets.has(asset.asset))) {
  throw new Error("DIST_SCOPE_PROVENANCE_UNEXPECTED");
}
for (const asset of provenance.assets.filter((asset) => !useDist || allowedDistAssets.has(asset.asset))) {
  const rel = String(asset.asset).replace(/^\//, "");
  const buf = readFileSync(resolve(base, rel));
  const sha = createHash("sha256").update(buf).digest("hex");
  const intact = sha === asset.sha256 && buf.byteLength === asset.bytes;
  if (!intact) {
    failed = true;
    console.error(
      `OWNER_ART_BYTE_DRIFT ${asset.asset} expected=${asset.sha256}:${asset.bytes} actual=${sha}:${buf.byteLength}`,
    );
  } else {
    console.log(`OWNER_ART_INTACT ${useDist ? "dist" : "public"} ${asset.asset} ${sha}`);
  }
}

if (failed) process.exit(1);
