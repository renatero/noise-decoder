// Browser coverage with mocked provider responses; no paid calls.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH || undefined, args:['--no-sandbox']});
  try {
    const page = await browser.newPage();
    const errors = []; page.on('pageerror', err => errors.push(err.message));
    let saved, reviewBody;
    const providers = ['context','cala','featherless','verda'].map(id => ({id,name:id,key_configured:id==='context',enabled:id==='context',model:id==='featherless'?'Qwen/Qwen2.5-7B-Instruct':'',base_url:id==='verda'?'https://inference.verda.com/v1':''}));
    await page.route('**/api/settings', route => route.fulfill({json:{providers}}));
    await page.route('**/api/settings/*', route => {
      saved=route.request().postDataJSON();
      assert.equal(route.request().headers()['x-noise-operator'], 'operator-test-token');
      return route.fulfill({json:{...providers[2], key_configured:true}});
    });
    await page.route('**/api/experimental/review', route => {
      reviewBody=route.request().postDataJSON();
      return route.fulfill({json:{provider:reviewBody.provider,entity:reviewBody.entity,created_at:new Date().toISOString(),model:'Qwen/Qwen2.5-7B-Instruct',synthetic:reviewBody.synthetic,kind:'review',notice:'Experimental review; check original sources.',relevance:'uncertain',records_reviewed:reviewBody.events.length,discarded_findings:1,findings:[{claim:'<img src=x onerror=alert(1)> a source reports a grant',category:'government_funding',evidence:[{id:'test:1',quote:'A source reports a research grant.',source_url:'https://example.org/article'}]}]}});
    });
    await page.goto(process.argv[2] || 'http://127.0.0.1:18001', {waitUntil:'domcontentloaded'});
    await page.fill('#review-entity','Example Labs');
    await page.click('#review-button');
    await page.waitForFunction(() => document.querySelector('#review-status').textContent.includes('unlock'));
    await page.click('#settings-button');
    assert.equal(await page.locator('#settings-dialog').isVisible(), true);
    await page.fill('#operator-token','operator-test-token');
    await page.locator('#settings-unlock button').click();
    await page.locator('[data-provider="featherless"]').waitFor();
    assert.equal(await page.inputValue('#operator-token'), '');
    assert.equal(await page.locator('[data-provider]').count(), 4);
    const feather = page.locator('[data-provider="featherless"]');
    await feather.locator('input[type="password"]').fill('secret-test-key');
    await feather.locator('input[type="checkbox"]').first().check();
    await feather.locator('button[type="submit"]').click();
    await feather.locator('[data-key-status]').filter({hasText:'API key saved'}).waitFor();
    assert.equal(saved.api_key, 'secret-test-key');
    assert.equal(saved.enabled,true);
    assert.equal(await feather.locator('input[type="password"]').inputValue(), '');
    assert.doesNotMatch(await page.locator('body').textContent(), /secret-test-key|operator-test-token/);
    assert.equal(await page.evaluate(() => localStorage.length),0);
    await page.click('#settings-close');
    await page.locator('[data-investigation-toggle]').first().click();
    await page.selectOption('#source','synthetic_coordinated');
    await page.click('#investigate-button');
    await page.locator('#investigation-overlay').waitFor({state:'hidden'});
    await page.selectOption('#review-provider','featherless');
    await page.click('#review-button');
    await page.waitForFunction(() => document.querySelector('#review-status').textContent.includes('Completed'));
    assert(reviewBody.events.length > 0 && reviewBody.events.length <=20);
    assert.equal(reviewBody.synthetic,true);
    assert.equal(await page.locator('#review-result img').count(),0);
    assert.match(await page.locator('#review-result').textContent(),/Synthetic input/);
    const downloadPromise=page.waitForEvent('download'); await page.click('#review-export');
    const downloaded=JSON.parse(fs.readFileSync(await (await downloadPromise).path(),'utf8'));
    assert.equal(downloaded.provider,'featherless'); assert.equal(downloaded.findings.length,1);
    await page.click('#settings-button'); await page.click('#settings-lock');
    assert.equal(await page.locator('[data-provider]').count(),0);
    await page.click('#settings-close'); await page.click('#review-button');
    await page.waitForFunction(() => document.querySelector('#review-status').textContent.includes('unlock'));
    await page.setViewportSize({width:390,height:844}); await page.click('#settings-button');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true);
    await page.screenshot({path:'/tmp/noise-provider-settings.png',fullPage:true});
    assert.deepEqual(errors,[]);
    console.log('Provider browser checks passed: unlock, key save, no storage/leaks, synthetic review, evidence/XSS, export, lock, mobile.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
