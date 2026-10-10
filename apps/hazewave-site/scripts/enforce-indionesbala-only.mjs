/** Fail closed: reviewed public distribution contains one artist only. Original files remain unchanged in Git history. */
import {readdir,rm,readFile} from "node:fs/promises";import {fileURLToPath} from "node:url";import {resolve,join} from "node:path";
const dist=resolve(fileURLToPath(new URL("../dist/",import.meta.url)));
const page=await readFile(join(dist,"index.html"),"utf8");
if(!page.includes('data-experience="indionesbala-only"')||!page.includes('src="/media/artists/indionesbala.webp"'))throw Error("UNREVIEWED_ARTIST_SCOPE");
if(/(Baazü|Aquaverno|Hemorragia|Barak Ozama|world-switcher|chapter-nav|data-world-stop)/i.test(page))throw Error("FORBIDDEN_ASSET_OR_UI");
const slugs=["aquaverno","baazu","barak-ozama-beats","hemorragia-cosmica"];
for(const slug of slugs){await rm(join(dist,"artists",slug),{recursive:true,force:true});}
const art=join(dist,"media","artists");for(const filename of await readdir(art)){if(!filename.startsWith("indionesbala."))await rm(join(art,filename),{force:true});}
await rm(join(dist,"media","worlds"),{recursive:true,force:true});
await rm(join(dist,"media","hazewave-world.jpg.webp"),{force:true});
for(const slug of slugs){try{await readFile(join(dist,"artists",slug,"index.html"));throw Error("FORBIDDEN_ROUTE_RESURFACED")}catch(e){if(e.code!=="ENOENT")throw e;}}
console.log("PUBLIC_ARTIST_SCOPE=INDIONESBALA_ONLY");console.log("OTHER_ARTIST_MEDIA_IN_DIST=ZERO");
