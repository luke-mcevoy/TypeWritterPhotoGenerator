// Read-only checks for the local scene audit and shadow candidate viewers.
// PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs node experiments/scene-browser.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.argv[2] || 'http://127.0.0.1:8008';
const scenes = JSON.parse(await fs.readFile(new URL('./scene_validation.json', import.meta.url)));
const browser = await chromium.launch({headless: true});
const errors = [];
let selections = 0, amounts = 0;
try {
  const page = await browser.newPage({viewport: {width: 1280, height: 900}});
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => { if (response.status() >= 400 && !response.url().endsWith('favicon.ico')) errors.push(`${response.status()} ${response.url()}`); });
  await page.goto(`${base}/nature-buildings/`);
  assert.equal(await page.locator('article:visible').count(), 12);
  for (const [group, count] of [['Nature',7],['Buildings',5],['all',12]]) {
    await page.locator(`[data-filter="${group}"]`).click();
    assert.equal(await page.locator('article:visible').count(), count);
  }
  assert.equal((await page.request.get(`${base}/nature-buildings/report.md`)).status(), 200);
  const galleries = [
    {folder: 'nature-buildings', ids: scenes.map(s=>s.id), versions: ['before','vibrant']},
    {folder: 'shadow-coverage', ids: ['post30','post31',...scenes.map(s=>s.id)], versions: ['before','candidate']}
  ];
  for (const gallery of galleries) {
    for (const id of gallery.ids) {
      await page.goto(`${base}/${gallery.folder}/${id}.html`);
      for (const version of gallery.versions) {
        await page.locator(`[data-version="${version}"]`).click();
        await page.waitForFunction(() => !document.querySelector('input[type="range"]').disabled && document.querySelector('.color-status').textContent.endsWith('color ready'));
        const endpoints = await page.evaluate(async version => {
          const stem = document.querySelector('section[data-stem]').dataset.stem;
          window.checkEndpoints = await Promise.all(['none','full'].map(async suffix => {
            const img = new Image(); img.src = `${stem}-${version}-${suffix}.png`; await img.decode();
            const c = document.createElement('canvas'); c.width = img.naturalWidth; c.height = img.naturalHeight;
            const ctx = c.getContext('2d'); ctx.drawImage(img,0,0);
            return ctx.getImageData(0,0,c.width,c.height).data;
          }));
          return window.checkEndpoints[0].length;
        }, version);
        assert.ok(endpoints > 100000);
        for (const amount of [0,40,70,100]) {
          await page.locator('input[type="range"]').evaluate((slider,value) => {slider.value=String(value);slider.dispatchEvent(new Event('input',{bubbles:true}));},amount);
          await page.waitForFunction(amount => document.querySelector('.color-status').textContent === `${amount}% color ready`,amount);
          const delta = await page.evaluate(amount => {
            const c = document.querySelector('.color-preview');
            const got = c.getContext('2d').getImageData(0,0,c.width,c.height).data;
            const [mono,full] = window.checkEndpoints;
            let max=0;
            for (let i=0;i<got.length;i+=101) max=Math.max(max,Math.abs(got[i]-Math.round(mono[i]*(1-amount/100)+full[i]*amount/100)));
            return max;
          },amount);
          assert.equal(delta,0,`${id}/${version}/${amount}`);
          assert.match(await page.locator('.download').getAttribute('href'),/^blob:/);
          amounts++;
        }
        selections++;
      }
      await page.locator('[data-version="photo"]').click();
      await page.waitForFunction(()=>{const i=document.querySelector('.full img');return i.complete && i.naturalWidth>0 && !i.hidden;});
      assert.ok(await page.locator('.color-controls').isHidden());
      console.log(`PASS ${gallery.folder}/${id}`);
    }
  }
  await page.setViewportSize({width:390,height:844});
  for (const url of ['nature-buildings/','nature-buildings/sandstone-desert.html','shadow-coverage/','shadow-coverage/post31.html']) {
    await page.goto(`${base}/${url}`);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth),url);
  }
  await page.locator('input[type="range"]').evaluate(slider=>{slider.value='70';slider.dispatchEvent(new Event('input',{bubbles:true}));});
  await page.waitForFunction(()=>document.querySelector('.color-status').textContent==='70% color ready');
  await page.screenshot({path:'/private/tmp/carriage-shadow-mobile.jpg',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({pages:26,selections,amounts,mobile:4,errors}));
} finally {
  await browser.close();
}
