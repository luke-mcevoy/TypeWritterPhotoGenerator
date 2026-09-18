// Check every version and amount control in the generated six-photo study.
import assert from 'node:assert/strict';
const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage({viewport:{width:1280,height:960}});
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://127.0.0.1:8008/illustrated/');
  const sections = page.locator('section[data-stem]');
  assert.equal(await sections.count(), 6);
  for (const section of await sections.all()) {
    for (const version of ['before', 'illustrated', 'photo']) {
      await section.locator(`[data-version="${version}"]`).click();
      if (version === 'photo') {
        await section.locator('.full img').evaluate(img => img.decode());
        assert(await section.locator('.color-controls').isHidden());
      } else {
        await page.waitForFunction(stem => !document.querySelector(`section[data-stem="${stem}"] input`).disabled,
          await section.getAttribute('data-stem'));
        for (const amount of [0, 37, 100]) {
          await section.locator('input').fill(String(amount));
          await section.locator('.color-status').filter({hasText:`${amount}% color ready`}).waitFor();
          assert.equal(await section.locator('output').textContent(), `${amount}%`);
          assert(await section.locator('.color-preview').isVisible());
          assert((await section.locator('.download').getAttribute('href')).startsWith('blob:'));
        }
      }
    }
  }
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  assert.deepEqual(errors, []);
  console.log('PASS: six comparisons, 18 versions, 36 amounts/downloads, images, mobile and no JS errors.');
} finally {await browser.close();}
