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
test('precache filters oversized assets',()=>{
  assert.deepEqual(precacheEntries([
    {relative:'index.html',bytes:100},
    {relative:'web/boot.mjs',bytes:400},
    {relative:'web-engine/packs/pt_kit/kick.wav',bytes:1000},
    {relative:'web-engine/packs/pt_kit/oversize.wav',bytes:9000000},
    {relative:'web-engine/devices/plugin.wasm',bytes:4000}
  ]),['./index.html','./web/boot.mjs','./web-engine/packs/pt_kit/kick.wav']);
});
test('PWA icons are real PNG images',()=>{
  for(const n of [192,512]){const b=png(n);
    assert.equal(b.subarray(1,4).toString(),'PNG');
    assert.equal(b.readUInt32BE(16),n);assert.equal(b.readUInt32BE(20),n);
  }
});
test('upstream pin exact',()=>assert.match(UPSTREAM_SHA,/^[0-9a-f]{40}$/));
