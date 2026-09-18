// Run against a disposable local app only: the test creates one local post.
import assert from 'node:assert/strict';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.argv[2] || 'http://127.0.0.1:5012';
assert.equal(new URL(base).hostname, '127.0.0.1');
const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage({viewport:{width:1280,height:960}});
  page.setDefaultTimeout(60000);
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.request.post(`${base}/signup`,{form:{username:`crop_${Date.now()}`,display_name:'Local crop test',password:'local-test-password'}});
  await page.goto(`${base}/studio`);
  const fixture = await page.evaluate(()=>{
    const c=document.createElement('canvas');c.width=600;c.height=400;
    const ctx=c.getContext('2d');ctx.fillStyle='#da2424';ctx.fillRect(0,0,300,400);
    ctx.fillStyle='#235ccb';ctx.fillRect(300,0,300,400);
    return c.toDataURL('image/png').split(',')[1];
  });
  await page.evaluate(()=>{
    window.cropUploads=[];
    const realFetch=window.fetch;
    window.fetch=async (url,options)=>{
      if (options?.body instanceof FormData && options.body.has('image')) {
        const file=options.body.get('image');const bitmap=await createImageBitmap(file);
        window.cropUploads.push({url,width:bitmap.width,height:bitmap.height,name:file.name});
        bitmap.close();
      }
      return realFetch(url,options);
    };
  });
  const upload=()=>page.locator('#file-input').setInputFiles({name:'two-colors.png',mimeType:'image/png',buffer:Buffer.from(fixture,'base64')});
  const ready=()=>page.waitForFunction(()=>!document.querySelector('#apply-crop-btn').disabled);
  await upload();await ready();
  assert.equal(await page.evaluate(()=>window.cropUploads.length),0,'upload waits for framing');
  await page.locator('#skip-crop-btn').click();
  assert.equal(await page.evaluate(()=>window.cropUploads.length),0,'cancel submits nothing');
  await upload();await ready();
  await page.locator('#crop-ratio').selectOption('1');
  const square=await page.locator('#crop-image').evaluate(img=>img.cropper.getData(true));
  assert.ok(Math.abs(square.width-square.height)<=1);
  await page.locator('#reset-crop-btn').click();
  const reset=await page.locator('#crop-image').evaluate(img=>img.cropper.getData(true));
  assert.equal(reset.width,600);assert.equal(reset.height,400);
  // Select only the blue half, then drag the selection with the real UI.
  await page.locator('#crop-image').evaluate(img=>img.cropper.setData({x:300,y:0,width:300,height:400}));
  const face=await page.locator('.cropper-face').boundingBox();
  await page.mouse.move(face.x+face.width/2,face.y+face.height/2);
  await page.mouse.down();await page.mouse.move(face.x+face.width/2-25,face.y+face.height/2,{steps:4});await page.mouse.up();
  assert.ok((await page.locator('#crop-image').evaluate(img=>img.cropper.getData())).x<300);
  await page.locator('#crop-image').evaluate(img=>img.cropper.setData({x:300,y:0,width:300,height:400}));
  const converted=page.waitForResponse(r=>r.url().endsWith('/convert')&&r.ok());
  await page.locator('#apply-crop-btn').click();await converted;
  await page.waitForFunction(()=>document.querySelector('#live-text').textContent==='Live');
  let uploads=await page.evaluate(()=>window.cropUploads);
  assert.equal(uploads[0].width,300);assert.equal(uploads[0].height,400);
  // Reopening starts from the original, with the current selection retained.
  await page.locator('#crop-btn').click();await ready();
  assert.equal(await page.locator('#crop-image').evaluate(img=>img.cropper.getImageData().naturalWidth),600);
  assert.equal((await page.locator('#crop-image').evaluate(img=>img.cropper.getData(true))).width,300);
  await page.keyboard.press('Escape');
  assert.ok(await page.locator('#crop-section').isHidden());
  const download=page.waitForEvent('download');
  await page.locator('#download-image-btn').click();
  assert.equal(await (await download).failure(),null);
  await page.locator('#post-btn').click();
  const posted=page.waitForResponse(r=>r.url().endsWith('/api/posts')&&r.request().method()==='POST');
  await page.locator('#confirm-post-btn').click();
  const result=await posted;assert.equal(result.status(),200);const data=await result.json();
  uploads=await page.evaluate(()=>window.cropUploads);
  assert.ok(uploads.some(u=>u.url==='/api/posts'));
  for(const u of uploads){assert.equal(u.width,300);assert.equal(u.height,400);}
  const sourceResponse=await page.request.get(new URL(data.post.source_url,base).href);
  const pixels=await page.evaluate(async encoded=>{
    const img=new Image();img.src='data:image/jpeg;base64,'+encoded;await img.decode();
    const c=document.createElement('canvas');c.width=img.naturalWidth;c.height=img.naturalHeight;
    const ctx=c.getContext('2d');ctx.drawImage(img,0,0);
    return {width:c.width,height:c.height,rgb:[...ctx.getImageData(c.width/2,c.height/2,1,1).data]};
  },(await sourceResponse.body()).toString('base64'));
  assert.equal(pixels.width,300);assert.equal(pixels.height,400);assert.ok(pixels.rgb[2]>pixels.rgb[0]*2);
  await page.goto(`${base}/studio`);
  await page.setViewportSize({width:390,height:844});
  await upload();await ready();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  await page.screenshot({path:'/private/tmp/carriage-crop-mobile.jpg',fullPage:true});
  const full=page.waitForResponse(r=>r.url().endsWith('/convert')&&r.ok());
  await page.locator('#use-full-image-btn').click();await full;
  await page.waitForFunction(()=>document.querySelector('#live-text').textContent==='Live');
  const fullSize=await page.locator('#original-image').evaluate(img=>[img.naturalWidth,img.naturalHeight]);
  assert.deepEqual(fullSize,[600,400]);
  assert.deepEqual(errors,[]);
  console.log('PASS: crop before rendering, cancel, presets, reset, dragging, original retained, crop used by preview/export/post, stored blue-half source, full image, mobile and no JS errors.');
} finally {await browser.close();}
