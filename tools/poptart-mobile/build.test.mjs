import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname,join} from 'node:path';
import {injectMobile,precacheEntries,png,UPSTREAM_SHA} from './build.mjs';
const fixture='<html><head></head><body><textarea id="editor"></textarea><button id="playBtn"></button></body></html>';
test('mobile injection is idempotent and preserves the audio editor',()=>{
  const once=injectMobile(fixture);
  assert.match(once,/viewport-fit=cover/);assert.match(once,/hz-mobile.js/);
  assert.match(once,/id="editor"/);assert.equal(injectMobile(once),once);
});
test('upstream drift fails closed',()=>{
  assert.throws(()=>injectMobile('<html><head></head><body></body></html>'),/shape changed/);
});
test('full offline bundle includes WASM, docs, editor helpers and audio data',()=>{
  assert.deepEqual(precacheEntries([
    {relative:'web-engine/devices/Plaits.wasm',bytes:185310},
    {relative:'docs/start.html',bytes:5000},
    {relative:'api-docs.js',bytes:40000},
    {relative:'osc-engine/sample-map-core.mjs',bytes:51000},
    {relative:'web-engine/packs/pt_kit/kick.wav',bytes:1000},
    {relative:'index.html',bytes:100},
    {relative:'hz-sw.js',bytes:100},
    {relative:'hz-provenance.json',bytes:100}
  ]),['./api-docs.js','./docs/start.html','./index.html',
    './osc-engine/sample-map-core.mjs','./web-engine/devices/Plaits.wasm',
    './web-engine/packs/pt_kit/kick.wav']);
});
test('oversized or excessive offline package fails closed',()=>{
  assert.throws(()=>precacheEntries([{relative:'huge.wasm',bytes:9*1024*1024}]),/8 MiB/);
  assert.throws(()=>precacheEntries(Array.from({length:7},(_,i)=>({relative:i+'.wasm',bytes:8*1024*1024}))),/48 MiB/);
});
test('PWA icons are real PNG images',()=>{
  for(const n of [192,512]){const b=png(n);
    assert.equal(b.subarray(1,4).toString(),'PNG');
    assert.equal(b.readUInt32BE(16),n);assert.equal(b.readUInt32BE(20),n);
  }
});
test('upstream pin exact',()=>assert.match(UPSTREAM_SHA,/^[0-9a-f]{40}$/));

test('offline service worker trusts browser secure contexts including 127.0.0.1',()=>{
  const mobile=readFileSync(join(dirname(fileURLToPath(import.meta.url)),'hz-mobile.js'),'utf8');
  assert.match(mobile,/serviceWorker' in navigator && W\.isSecureContext/);
  assert.doesNotMatch(mobile,/location\.hostname === 'localhost'/);
  assert.match(mobile,/HAZE_OFFLINE_SERVICE_WORKER_FAILED/);
});

test('touch piano roll exposes individual MIDI pitches, transposition and real upstream instruments',()=>{
  const source=readFileSync(join(dirname(fileURLToPath(import.meta.url)),'hz-mobile.js'),'utf8');
  assert.match(source,/midi\.v2/);
  assert.match(source,/hz-note-grid/);
  assert.match(source,/noteName\(n\)/);
  assert.match(source,/note\("/);
  assert.match(source,/shiftPitch\(12 \* \(next - mix\.octave\)\)/);
  assert.match(source,/hz-synth/);
  for(const synth of ['Wavetable','FM','Plaits','Braids','Rings','Elements'])
    assert.ok(source.includes("'" + synth + "'"), synth);
  assert.match(source,/HazewavePoptartMobileBackup\/v2/);
  assert.match(source,/HazewavePoptartMobileBackup\/v1/);
});

test('pinned official sound catalog preserves all indexed sounds and licensing',()=>{
  const catalog=JSON.parse(readFileSync(join(dirname(fileURLToPath(import.meta.url)),
    'hz-sound-catalog.json'),'utf8'));
  assert.equal(catalog.schema,'HazewavePoptartSoundCatalog/v1');
  assert.equal(catalog.origin_commit,'6e19b90a4f07a1c863fc1272a41800934d7c6530');
  assert.equal(catalog.packs.length,15);
  assert.equal(catalog.packs.reduce((n,p)=>n+p.files.length,0),182);
  assert.equal(catalog.local_packs.reduce((n,p)=>n+p.files.length,0),13);
  assert.equal(new Set(catalog.packs.map(p=>p.id)).size,15);
  assert.ok(catalog.packs.every(p=>p.files.every((f,i)=>
    f.number===i&&f.license==='CC0-1.0'&&!f.file.includes('..'))));
});
