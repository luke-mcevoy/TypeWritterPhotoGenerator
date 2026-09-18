// PLAYWRIGHT_MODULE=/path/to/playwright/index.mjs node tests/studio-browser.mjs [base URL]
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.argv[2] || 'http://127.0.0.1:5010';
const local = new URL(base).hostname === '127.0.0.1';
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1360, height: 1000 } });
  page.setDefaultTimeout(90000);
  const errors = [];
  page.on('pageerror', error => errors.push(String(error)));
  const conversions = [];
  let lastPreview;
  page.on('request', request => {
    if (new URL(request.url()).pathname === '/convert') conversions.push(request);
  });
  page.on('response', async response => {
    if (new URL(response.url()).pathname === '/convert' && response.ok()) {
      const data = await response.json().catch(() => null);
      if (data?.color_endpoints?.length) lastPreview = data;
    }
  });
  assert.equal((await page.goto(`${base}/studio`)).status(), 200);
  assert.equal(await page.locator('#drawing-style').inputValue(), 'vibrant');
  assert.equal(await page.locator('#color-amount-slider').inputValue(), '70');
  await page.locator('#file-input').setInputFiles('output/algorithm-comparison/refined/study-1-photo.jpg');
  await page.locator('#use-full-image-btn').click();
  await page.waitForFunction(() => {
    const overlay = document.querySelector('#stage-progress');
    const pct = document.querySelector('#live-pct');
    return overlay && !overlay.hidden && pct && /\d+%/.test(pct.textContent || '');
  });
  await page.waitForFunction(() => document.querySelector('#live-text').textContent === 'Live');
  const chooseIllustration = async () => {
    const converted = page.waitForResponse(response => new URL(response.url()).pathname === '/convert' && response.ok());
    await page.locator('#drawing-style').selectOption('illustrated');
    await converted;
    await page.waitForFunction(() => document.querySelector('#live-text').textContent === 'Live');
  };
  await chooseIllustration();
  assert(await page.locator('#stage-progress').evaluate(el => el.hidden));
  assert(lastPreview);
  console.log('Initial typed illustration preview loaded.');
  const checkColor = async amount => {
    const before = conversions.length;
    const result = await page.evaluate(async ({ amount, endpoints }) => {
      const slider = document.querySelector('#color-amount-slider');
      slider.value = amount;
      slider.dispatchEvent(new Event('input', { bubbles: true }));
      const pixels = async src => {
        const picture = new Image(); picture.src = src; await picture.decode();
        const canvas = document.createElement('canvas');
        canvas.width = picture.naturalWidth; canvas.height = picture.naturalHeight;
        const context = canvas.getContext('2d'); context.drawImage(picture, 0, 0);
        return context.getImageData(0, 0, canvas.width, canvas.height).data;
      };
      const [mono, full, actual] = await Promise.all([
        pixels(endpoints[0]), pixels(endpoints[1]), pixels(document.querySelector('#glyph-image').src),
      ]);
      let error = 0;
      for (let i = 0; i < actual.length; i++) {
        error = Math.max(error, Math.abs(actual[i] - Math.round(mono[i]*(1-amount/100) + full[i]*amount/100)));
      }
      return { error, label: document.querySelector('#color-amount-value').value,
        sameSides: document.querySelector('#glyph-image').src === document.querySelector('#side-glyph').src };
    }, { amount, endpoints: lastPreview.color_endpoints });
    assert(result.error <= 1, `color blend error ${result.error}`);
    assert.equal(result.label, `${amount}%`);
    assert(result.sameSides);
    assert.equal(conversions.length, before, 'color dragging should not request another render');
  };
  for (const amount of [0, 37, 100, 23]) await checkColor(amount);
  await page.screenshot({ path: '/private/tmp/carriage-studio-deploy.jpg', fullPage: true });
  const downloadPromise = page.waitForEvent('download');
  const printResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/convert'
    && response.ok());
  await page.locator('#download-image-btn').click();
  const download = await downloadPromise;
  assert.equal(download.suggestedFilename(), 'typewriter-drawing.png');
  assert.equal(await download.failure(), null);
  const printed = await (await printResponse).json();
  assert.equal(printed.color_amount, .23);
  assert.equal(printed.drawing_style, 'illustrated');
  assert(printed.dimensions.img_width > lastPreview.dimensions.img_width);
  await checkColor(37);
  console.log('Illustration upload, instant color, matching side-by-side and PNG download passed.');

  // Shadow fill lives inside More; open it before testing its visibility.
  await page.locator('details.more').evaluate(el => { el.open = true; });
  for (const style of ['monochrome', 'original', 'ribbon', 'refined', 'vibrant', 'illustrated']) {
    const ready = page.waitForResponse(response => new URL(response.url()).pathname === '/convert'
      && response.ok());
    await page.locator('#drawing-style').selectOption(style);
    const response = await ready;
    const data = await response.json();
    assert.equal(data.drawing_style, style);
    await page.waitForFunction(() => document.querySelector('#live-text').textContent === 'Live');
    assert.equal(await page.locator('#color-controls').isVisible(), ['ribbon', 'refined', 'vibrant', 'illustrated'].includes(style));
    assert.equal(await page.locator('#shadow-fill-slider').isVisible(), ['illustrated', 'vibrant'].includes(style));
    if (data.color_endpoints.length) await checkColor(37);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.screenshot({ path: '/private/tmp/carriage-studio-mobile.jpg', fullPage: true });
  assert.deepEqual(errors, []);
  console.log('All drawing styles, retained color, mobile width and browser error checks passed.');

  // Posts are exercised only against the disposable local container.
  if (local) {
    const username = `smoke_${Date.now()}`;
    const signup = await page.request.post(`${base}/signup`, { form: {
      username, display_name: 'Local smoke test', password: 'local-test-password',
    } });
    assert(signup.ok());
    await page.reload();
    assert(await page.evaluate(() => window.CARRIAGE.signedIn));
    await page.locator('#file-input').setInputFiles('output/algorithm-comparison/refined/study-2-photo.jpg');
    await page.locator('#use-full-image-btn').click();
    await page.waitForFunction(() => document.querySelector('#live-text').textContent === 'Live');
    await chooseIllustration();
    await checkColor(37);
    await page.locator('#post-btn').click();
    await page.locator('#post-caption').fill('37% color smoke test');
    await page.evaluate(() => {
      const originalFetch = window.fetch;
      window.fetch = (url, options) => {
        if (url === '/api/posts' && options?.body instanceof FormData) {
          window.postedSettings = {
            color: options.body.get('color_amount'), style: options.body.get('drawing_style'),
          };
        }
        return originalFetch(url, options);
      };
    });
    const postedResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/posts' && response.request().method() === 'POST');
    await page.locator('#confirm-post-btn').click();
    await page.waitForFunction(() => {
      const el = document.querySelector('#post-progress');
      const pct = document.querySelector('#post-progress-pct');
      return el && !el.hidden && pct && /\d+%/.test(pct.textContent || '');
    });
    const posted = await postedResponse;
    assert.equal(posted.status(), 200, await posted.text());
    assert.deepEqual(await page.evaluate(() => window.postedSettings), { color: '0.37', style: 'illustrated' });
    const data = await posted.json();
    await page.waitForURL(`${base}${data.post.url}`);
    assert.equal((await page.request.get(`${base}${data.post.image_url}`)).status(), 200);
    console.log('Signed-in posting at 37% and persisted image passed on the disposable local app.');
  }
} finally {
  await browser.close();
}
