// Reproducible Poptart Web Audio -> Hazewave PWA packaging.
// Poptart is AGPL-3.0-only. Preserve upstream license, notices and source.
import fs from 'node:fs';
import path from 'node:path';
import {createHash} from 'node:crypto';
import {deflateSync} from 'node:zlib';
import {fileURLToPath} from 'node:url';

export const UPSTREAM_SHA='1310635d3a306a46544773bfc77720ce123ede75';
const home=path.dirname(fileURLToPath(import.meta.url));
export function injectMobile(html) {
  if (!html.includes('<head>') || !html.includes('</body>') ||
      !html.includes('id="editor"') || !html.includes('id="playBtn"'))
    throw new Error('Upstream HTML shape changed; fail closed');
  if (html.includes('data-hazewave-mobile="v1"')) return html;
  return html.replace('<head>', '<head>\n' +
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">\n' +
    '<meta name="theme-color" content="#11141e">\n' +
    '<link rel="manifest" href="./hz-manifest.webmanifest">\n' +
    '<link rel="stylesheet" href="./hz-mobile.css" data-hazewave-mobile="v1">')
    .replace('</body>', '<script src="./hz-mobile.js" defer></script>\n</body>');
}
export function png(size) {
  const raw=Buffer.alloc(size*(size*4+1));
  for(let y=0;y<size;y++){
    const row=y*(size*4+1);
    for(let x=0;x<size;x++){
      const i=row+1+4*x;
      const wave=size*(.5+Math.sin(x/size*Math.PI*3.5)*.12);
      const highlight=Math.abs(y-wave)<size*.037;
      raw[i]=highlight?105:17;raw[i+1]=highlight?243:20;
      raw[i+2]=highlight?223:30;raw[i+3]=255;
    }
  }
  const table=Array.from({length:256},(_,n)=>{
    let c=n;for(let k=0;k<8;k++)c=c&1?0xedb88320^(c>>>1):c>>>1;return c>>>0;
  });
  const crc=b=>{
    let c=0xffffffff;for(const x of b)c=table[(c^x)&255]^(c>>>8);
    return(c^0xffffffff)>>>0;
  };
  const chunk=(name,payload)=>{
    const type=Buffer.from(name),length=Buffer.alloc(4),tail=Buffer.alloc(4);
    length.writeUInt32BE(payload.length);tail.writeUInt32BE(crc(Buffer.concat([type,payload])));
    return Buffer.concat([length,type,payload,tail]);
  };
  const ihdr=Buffer.alloc(13);
  ihdr.writeUInt32BE(size,0);ihdr.writeUInt32BE(size,4);ihdr[8]=8;ihdr[9]=6;
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]),
    chunk('IHDR',ihdr),chunk('IDAT',deflateSync(raw)),chunk('IEND',Buffer.alloc(0))]);
}
function enumerate(dir,prefix=''){
  const entries=[];
  for(const e of fs.readdirSync(dir,{withFileTypes:true})){
    const relative=path.posix.join(prefix,e.name),absolute=path.join(dir,e.name);
    if(e.isDirectory())entries.push(...enumerate(absolute,relative));
    else if(e.isFile())entries.push({relative,bytes:fs.statSync(absolute).size});
  }
  return entries;
}
// All packaged static modules, WASM devices, samples and HTML documentation
// must be available offline, not just the editor shell. Fail closed instead
// of silently dropping oversized files: an incomplete PWA can appear "ready".
export function precacheEntries(files){
  const result=files.filter(({relative})=>
    relative !== 'hz-sw.js' && relative !== 'hz-provenance.json');
  const oversized=result.find(({bytes})=>bytes>8*1024*1024);
  if(oversized)throw new Error('Offline file exceeds 8 MiB: '+oversized.relative);
  const sum=result.reduce((s,x)=>s+x.bytes,0);
  if(sum>48*1024*1024)throw new Error('Offline precache exceeds 48 MiB');
  return result.map(({relative})=>'./'+relative).sort();
}
export function build(output){
  const dist=path.resolve(output);
  for(const asset of ['index.html','client.js','style.css',
    'web/boot.mjs','pattern-core/index.mjs','web-engine/src/index.mjs'])
    if(!fs.existsSync(path.join(dist,asset)))throw new Error('Missing upstream asset: '+asset);
  const htmlFile=path.join(dist,'index.html');
  fs.writeFileSync(htmlFile,injectMobile(fs.readFileSync(htmlFile,'utf8')));
  for(const file of ['hz-mobile.css','hz-mobile.js','hz-sound-catalog.json'])
    fs.copyFileSync(path.join(home,file),path.join(dist,file));
  for(const size of [192,512])
    fs.writeFileSync(path.join(dist,'hz-icon-'+size+'.png'),png(size));
  const manifest={
    id:'./',name:'Hazewave Music Lab — Poptart',short_name:'HAZE Music',
    start_url:'./',scope:'./',display:'standalone',
    background_color:'#11141e',theme_color:'#11141e',
    icons:[192,512].map(n=>({src:'./hz-icon-'+n+'.png',sizes:n+'x'+n,type:'image/png',purpose:'any'}))
  };
  fs.writeFileSync(path.join(dist,'hz-manifest.webmanifest'),JSON.stringify(manifest,null,2));
  const precache=precacheEntries(enumerate(dist));
  const swTemplate=fs.readFileSync(path.join(home,'hz-sw.template.js'),'utf8');
  // Revision is based on the WHOLE cached bundle, not just HTML/JS: a changed
  // CSS, WASM binary or sample must never reuse an incompatible offline cache.
  const fingerprint=createHash('sha256').update(UPSTREAM_SHA);
  fingerprint.update(swTemplate);
  for(const asset of precache){
    fingerprint.update(asset);
    fingerprint.update(fs.readFileSync(path.join(dist,asset.slice(2))));
  }
  const revision=fingerprint.digest('hex').slice(0,16);
  fs.writeFileSync(path.join(dist,'hz-sw.js'),swTemplate
    .replace('/*HAZE_CACHE_NAME*/',JSON.stringify('hz-poptart-'+revision))
    .replace('/*HAZE_CACHE_LIST*/',JSON.stringify(precache)));
  fs.writeFileSync(path.join(dist,'hz-provenance.json'),JSON.stringify({
    schema:'HazewavePoptartMobileProvenance/v1',upstream:'glossings/poptart',
    upstream_sha:UPSTREAM_SHA,license:'AGPL-3.0-only',revision,
    precache_count:precache.length,offline_acceptance:'PENDING',
    android_human_acceptance:'PENDING'
  },null,2));
  console.log(JSON.stringify({build:'CREATED',dist,revision,precache_count:precache.length}));
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  if(!process.argv[2])throw new Error('Usage: node build.mjs <poptart/dist/web>');
  build(process.argv[2]);
}
