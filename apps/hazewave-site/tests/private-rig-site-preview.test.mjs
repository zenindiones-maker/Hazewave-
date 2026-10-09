import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, readFile, readdir, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createHash } from "node:crypto";
import { validateRigKit, buildPrivateSite } from "../scripts/private-rig-site-preview.mjs";

const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9bve60sAAAAASUVORK5CYII=", "base64");
const sha = x => createHash("sha256").update(x).digest("hex");
const names = [...Array.from({ length: 9 }, (_, i) => "p" + Math.floor(i / 3) + (i % 3)), "encoder_right"];

async function setup() {
  const root = await mkdtemp(join(tmpdir(), "hz-rig-site-test-"));
  const dist = join(root, "astro-dist");
  const kit = join(root, "private-kit");
  await mkdir(join(dist, "artists", "indionesbala"), { recursive: true });
  await mkdir(kit);
  await writeFile(join(dist, "index.html"), '<!doctype html><html><head></head><body><a href="/artists/indionesbala/">Artista</a></body></html>');
  await writeFile(join(dist, "artists", "indionesbala", "index.html"), "<!doctype html><title>Indionesbala</title>");
  for (const file of ["controller-original.png", "fog-original.png", "controller-cleanplate-EXPERIMENTAL.png", ...names.map(n => n + ".png")]) {
    await writeFile(join(kit, file), PNG);
  }
  const parts = names.map((id, i) => ({ id, path: id + ".png", sha256: sha(PNG), x: 10 + i * 2, y: 15, width: 2, height: 2 }));
  const manifest = {
    schema: "HazewaveWaveRigPilot/v1",
    authority: "NONE",
    production_approved: false,
    source_art_sha256: sha(PNG),
    fog_art_sha256: sha(PNG),
    individual_art_pieces: 10,
    pieces: parts
  };
  await writeFile(join(kit, "pilot-manifest.json"), JSON.stringify(manifest));
  await writeFile(join(kit, "preview.html"), '<!doctype html><html><head></head><body><div id="scene"><img id="original" src="controller-original.png"><img id="fog" src="fog-original.png"><img id="clean" src="controller-cleanplate-EXPERIMENTAL.png"></div><script>window.__wavePoseForTest = () => {};</script></body></html>');
  return { root, dist, kit, manifest, out: join(root, "private-site") };
}

test("requires exact ten independently named painted pieces", async () => {
  const { kit, manifest } = await setup();
  assert.equal((await validateRigKit(kit, { controller: sha(PNG), fog: sha(PNG) })).pieces, 10);
  manifest.pieces.pop();
  await writeFile(join(kit, "pilot-manifest.json"), JSON.stringify(manifest));
  await assert.rejects(validateRigKit(kit, { controller: sha(PNG), fog: sha(PNG) }), /EXPECTED_TEN_PARTS/);
});

test("builds isolated site with art only OUTSIDE Astro dist", async () => {
  const { dist, kit, out } = await setup();
  const report = await buildPrivateSite({ dist, kit, out, hashes: { controller: sha(PNG), fog: sha(PNG) } });
  assert.equal(report.schema, "HazewavePrivateRigSiteIntegration/v1");
  assert.equal(report.private_preview_only, true);
  assert.equal(report.codespace_attested, false);
  assert.equal(report.production_approved, false);
  assert.equal(report.visual_quality_approved, false);
  assert.match(await readFile(join(out, "index.html"), "utf8"), /wave-rig-lab/);
  assert.match(await readFile(join(out, "wave-rig-lab", "index.html"), "utf8"), /noindex,nofollow/);
  assert.deepEqual((await readdir(dist)).sort(), ["artists", "index.html"]);
  await assert.rejects(buildPrivateSite({ dist, kit, out, hashes: { controller: sha(PNG), fog: sha(PNG) } }), /OUTPUT_ALREADY_EXISTS/);
});

test("forbids forged controller source hashes and production authorization", async () => {
  const { kit, manifest } = await setup();
  await assert.rejects(validateRigKit(kit, { controller: "a".repeat(64), fog: sha(PNG) }), /SOURCE_SHA_DRIFT/);
  manifest.production_approved = true;
  await writeFile(join(kit, "pilot-manifest.json"), JSON.stringify(manifest));
  await assert.rejects(validateRigKit(kit, { controller: sha(PNG), fog: sha(PNG) }), /UNAUTHORIZED_PRODUCTION_CLAIM/);
});

test("rejects source mutation, symlinks, or in-repo source directories", async () => {
  const { root, kit, manifest } = await setup();
  await writeFile(join(kit, "p00.png"), Buffer.from("tampered"));
  await assert.rejects(validateRigKit(kit, { controller: sha(PNG), fog: sha(PNG) }), /PIECE_HASH_DRIFT/);
  await writeFile(join(kit, "p00.png"), PNG);
  await symlink(join(root, "missing"), join(kit, "bad-link"));
  manifest.pieces[0].path = "bad-link";
  await writeFile(join(kit, "pilot-manifest.json"), JSON.stringify(manifest));
  await assert.rejects(validateRigKit(kit, { controller: sha(PNG), fog: sha(PNG) }), /PIECE_PATH_UNAUTHORIZED/);
});

test("block missing Astro build and reject unsafe HTML markup", async () => {
  const { root, kit, manifest, out } = await setup();
  await writeFile(join(kit, "preview.html"), '<script src="https://outside.example/spy.js"></script>');
  await assert.rejects(buildPrivateSite({ dist: join(root, "missing"), kit, out, hashes: { controller: sha(PNG), fog: sha(PNG) } }), /ASTRO_BUILD_REQUIRED/);
  const dist = join(root, "astro-dist");
  await assert.rejects(buildPrivateSite({ dist, kit, out, hashes: { controller: sha(PNG), fog: sha(PNG) } }), /UNTRUSTED_PREVIEW_HTML/);
});

test("built-in script cannot create a second Codespace, install or publish", async () => {
  const content = await readFile(new URL("../scripts/private-rig-site-preview.mjs", import.meta.url), "utf8");
  for (const banned of ["gh codespace create", "npm install", "npm publish", "git push", "git reset --hard", "chmod 777", "hazewave-reflex serve-stop", "codex mcp add"]) {
    assert.ok(!content.includes(banned));
  }
});
