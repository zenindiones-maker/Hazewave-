import {test,expect} from "@playwright/test";
import {createHash} from "node:crypto";
import {readFileSync} from "node:fs";
import {resolve} from "node:path";
import {fileURLToPath} from "node:url";

const root=resolve(fileURLToPath(new URL("../dist",import.meta.url)));
const sha=(bytes:Buffer)=>createHash("sha256").update(bytes).digest("hex");

test("all seven REAL ArtCraft outputs are served ONLY from one SHA-bound integration_manifest.json", async({page,request})=>{
 const errors:string[]=[];
 page.on("pageerror",error=>errors.push(error.message));
 const response=await page.goto("/");
 expect(response?.status()).toBe(200);
 const online=await (await request.get("/integration_manifest.json")).json();
 const local=JSON.parse(readFileSync(resolve(root,"integration_manifest.json"),"utf8"));
 expect(online).toEqual(local);
 expect(local.schema).toBe("HazewaveArtCraftSevenLabHandoff/v1");
 expect(local.owner_private_media_used).toBe(false);
 expect(local.production_approved).toBe(false);
 expect(local.site_integration_status).toBe("LAB_ASSETS_ONLY");
 expect(Object.keys(local.artifacts).sort()).toEqual(
   ["photocraft","lightcraft","designcraft","pdfcraft","vectorcraft","effectcraft","filmcraft"].sort()
 );
 const chain=page.locator("#artcraft-chain");
 await expect(chain).toHaveAttribute("data-artcraft-validated","seven");
 await expect(chain).toHaveAttribute("data-artcraft-run",local.run_id);
 await expect(chain).toHaveAttribute("data-artcraft-sha",local.head_sha);
 await expect(chain).toHaveAttribute("data-provenance-id",local.designcraft_provenance.stage_id);
 await expect(chain).toHaveAttribute("data-designcraft-pdf","/artcraft/assets/designcraft.pdf");
 await expect(chain).toHaveAttribute("data-filmcraft-qc","/artcraft/assets/effectcraft-reference.webm");
 for(const [name,entry] of Object.entries(local.artifacts) as [string,{path:string;sha256:string}][]){
   const localPath=resolve(root,"artcraft",entry.path);
   expect(sha(readFileSync(localPath)),name).toBe(entry.sha256);
   const remote=await request.get("/artcraft/"+entry.path);
   expect(remote.status(),name).toBe(200);
   expect(sha(await remote.body()),name).toBe(entry.sha256);
 }
 for(const frame of local.motion_frames){
   expect(sha(readFileSync(resolve(root,"artcraft",frame.path)))).toBe(frame.sha256);
 }
 await expect(page.locator("img")).toHaveCount(2);
 expect(errors).toEqual([]);
});

test("real EffectCraft pixels change with scroll while provenance-gated Craft layers stay mounted",async({page},info)=>{
 await page.goto("/");
 const path=page.locator("#craft-motion");
 const chain=page.locator("#artcraft-chain");
 const motion=()=>path.evaluate(e=>getComputedStyle(e).backgroundImage);
 const scroll=async(p:number)=>{
   await page.evaluate(target=>{
     const journey=document.getElementById("journey")!;
     window.scrollTo({top:(journey.offsetHeight-innerHeight)*target,behavior:"instant"});
   },p);
   await expect.poll(()=>page.evaluate(()=>Number(document.body.dataset.storyProgress)),{timeout:8000})
     .toBeGreaterThan(p-.015);
 };
 await scroll(.20);
 const initial=await motion();
 await scroll(.70);
 const middle=await motion();
 await expect(chain).toHaveAttribute("data-artcraft-validated","seven");
 expect(middle).not.toBe(initial);
 expect(middle).toContain("/artcraft/assets/sonic-portal-");
 expect(await chain.evaluate(e=>getComputedStyle(e.querySelector(".craft-motion")!).opacity)).not.toBe("0");
 await page.screenshot({path:info.outputPath("seven-craft-manifest-real-scroll.png"),animations:"disabled"});
 await scroll(.20);
 expect(await motion()).toBe(initial);
});
