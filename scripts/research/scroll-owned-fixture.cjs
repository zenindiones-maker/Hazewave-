#!/usr/bin/env node
"use strict";
// Browser observation of exactly one owned, inline SVG fixture. No public URLs,
// no uploads, no remote browser sessions and no global MCP registrations.
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

const sha = value => crypto.createHash("sha256").update(value).digest("hex");
const POSITIONS = [0, 0.15, 0.4, 0.7, 0.95, 1.0, 0.4, 0];
const PROFILES = [
  { name: "mobile393", width: 393, height: 852 },
  { name: "mobile360", width: 360, height: 800 },
  { name: "desktop", width: 1280, height: 720 },
];

function writeExclusive(file, bytes) {
  fs.writeFileSync(file, bytes, { flag: "wx", mode: 0o600 });
}

async function main() {
  if (process.argv.length !== 4) throw new Error("OUTPUT_ROOT_AND_OWNED_FIXTURE_REQUIRED");
  const root = path.resolve(process.argv[2]);
  const fixture = path.resolve(process.argv[3]);
  const expected = path.resolve(process.cwd(), "tests/fixtures/wave-scroll-owned.html");
  if (fixture !== expected || fs.lstatSync(fixture).isSymbolicLink())
    throw new Error("ONLY_REPOSITORY_OWNED_FIXTURE_ADMITTED");
  const source = fs.readFileSync(fixture);
  if (source.length > 250_000) throw new Error("FIXTURE_TOO_LARGE");
  const html = source.toString("utf8");
  fs.mkdirSync(root, { recursive: true, mode: 0o700 });

  const browser = await chromium.launch({ headless: true });
  try {
    for (const profile of PROFILES) {
      const captureDir = path.join(root, profile.name);
      fs.mkdirSync(captureDir, { mode: 0o700 });
      const context = await browser.newContext({
        viewport: {width: profile.width, height: profile.height},
        deviceScaleFactor: 1,
        serviceWorkers: "block",
        reducedMotion: "reduce",
        colorScheme: "dark",
        javaScriptEnabled: true,
      });
      let networkRequests = 0;
      await context.route("**/*", async route => {
        networkRequests++;
        await route.abort("blockedbyclient");
      });
      const page = await context.newPage();
      try {
        await page.setContent(html, {waitUntil: "load"});
        await page.waitForFunction(() =>
          document.querySelector("#trace") &&
          document.querySelector("#trace").getTotalLength() > 1 &&
          document.body.dataset.scrollProgress !== undefined);
        const samples = [];
        for (let index=0; index<POSITIONS.length; index++) {
          const target=POSITIONS[index];
          await page.evaluate(async (target) => {
            const max = document.documentElement.scrollHeight - window.innerHeight;
            window.scrollTo({top: max*target, behavior: "instant"});
            await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
          }, target);
          const state = await page.evaluate(() => {
            const trace=document.querySelector("#trace");
            const rig=document.querySelector("#rig");
            const camera=document.querySelector("#camera");
            const pad=document.querySelector("#pad");
            const length=trace.getTotalLength();
            const offset=Number.parseFloat(getComputedStyle(trace).strokeDashoffset);
            const numericTransform=node=>{
              const m=(node.getAttribute("transform")||"").match(/^translate\((-?\d+(?:\.\d+)?),0\)$/);
              if (!m) throw new Error("RIG_TRANSFORM_NOT_OBSERVED");
              return Number(m[1]);
            };
            return {
              progress: Number(document.body.dataset.scrollProgress),
              stroke_reveal: Math.max(0,Math.min(1,1-offset/length)),
              pad_active: pad.getAttribute("data-active")==="true",
              rig_translate_x: numericTransform(rig),
              camera_translate_x: numericTransform(camera)
            };
          });
          const fileName=`${String(index).padStart(2,"0")}.png`;
          const png=await page.screenshot({type:"png",animations:"disabled"});
          writeExclusive(path.join(captureDir, fileName), png);
          samples.push({target, ...state, frame_name:fileName, frame_sha256:sha(png)});
        }
        const report = {
          schema:"HazewaveOwnedScrollBrowserCapture/v1",
          fixture_scope:"LOCAL_FIRST_PARTY_ONLY",
          fixture_sha256:sha(source),
          browser:"chromium",
          browser_version:browser.version(),
          viewport:{width:profile.width,height:profile.height},
          samples,
          network_request_count:networkRequests,
          external_sites_analyzed:false
        };
        writeExclusive(path.join(captureDir,"browser-capture.json"),
          Buffer.from(JSON.stringify(report,null,2)+"\n","utf8"));
        console.log(`WAVE_SCROLL_CAPTURE_${profile.name}=COMPLETE_FRAMES_${samples.length}`);
      } finally {
        await context.close();
      }
    }
  } finally {
    await browser.close();
  }
}
main().catch(error=>{console.error("WAVE_SCROLL_CAPTURE=BLOCKED:",error.message);process.exitCode=20;});
