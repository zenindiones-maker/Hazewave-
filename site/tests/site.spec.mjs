import { test, expect } from '@playwright/test';
const vps=[['a15-portrait',1080,2340],['a15-landscape',2340,1080],['p412',412,915]];
for (const [n,w,h] of vps) test(`render ${n}`, async ({ page }) => {
  await page.setViewportSize({width:w,height:h});
  await page.goto('/');
  await page.evaluate(()=>scrollTo(0,0)); await page.waitForTimeout(200);
  const a=Number(await page.evaluate(()=>document.documentElement.dataset.ink));
  await page.evaluate(()=>scrollTo(0,innerHeight*1.2)); await page.waitForTimeout(300);
  const b=Number(await page.evaluate(()=>document.documentElement.dataset.ink));
  expect(b).toBeGreaterThan(a);
  await page.evaluate(()=>scrollTo(0,0)); await page.waitForTimeout(300);
  expect(Number(await page.evaluate(()=>document.documentElement.dataset.ink))).toBeLessThan(b);
  const hz=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth); expect(hz).toBe(true);
  await page.screenshot({path:`shots/${n}-top.png`});
  for (const id of ['nucleo','downloads','apoie']) { await page.locator('#'+id).scrollIntoViewIfNeeded(); await page.waitForTimeout(150); await page.screenshot({path:`shots/${n}-${id}.png`}); }
});
test('placeholders marked', async ({ page }) => {
  await page.goto('/');
  const t=await page.locator('#apoie').innerText();
  expect(t).toContain('PROVISÓRIO');
  expect(await page.locator('#downloads a').count()).toBe(0);
});
