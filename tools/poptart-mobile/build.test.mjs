import test from 'node:test';
import assert from 'node:assert/strict';
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
