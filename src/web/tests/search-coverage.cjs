// Run with Playwright available in NODE_PATH and optional CHROME_PATH.
// Collection responses are mocked; these checks never spend provider credits.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
(async () => {
  const browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_PATH || undefined, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    let collection;
    let status = 200;
    await page.route('**/api/collect/**', route => route.fulfill({status, json: status === 200 ? collection : {detail: 'Sources are unavailable.', collection}}));
    await page.route('**/api/sources', async route => {
      const response = await route.fetch();
      const data = await response.json();
      data.sources.find(item => item.id === 'context').available = true;
      await route.fulfill({json: data});
    });
    await page.goto(process.argv[2] || 'http://127.0.0.1:18001', {waitUntil: 'domcontentloaded'});
    const names = ['Bluesky', 'Hacker News', 'BBC News — World', 'The Guardian — World', 'Al Jazeera'];
    const ids = ['bluesky', 'hackernews', 'bbc', 'guardian', 'aljazeera'];
    const query = '<img src=x onerror=alert(1)> rare phrase';
    const empty = {source: 'all_public_sources', query, requested_limit: 10, events: [], search_completed_at: new Date().toISOString(), limitations: [],
      sources: names.map((name, i) => ({id: ids[i], name, url: 'https://example.org/', scope: 'Bounded source search.', status: 'ok', available_events: 0, returned_events: 0}))};
    async function run(source) {
      await page.locator('[data-investigation-toggle]').first().click();
      await page.selectOption('#source', source);
      await page.fill('#investigation', query);
      await page.click('#investigate-button');
      await page.locator('#investigation-overlay').waitFor({state: 'hidden'});
    }
    collection = structuredClone(empty);
    collection.sources[0] = {...collection.sources[0], status: 'error', available_events: null, error: 'Source timed out.'};
    await run('all');
    assert.equal(await page.locator('#search-source-list li').count(), 5);
    assert.match(await page.locator('#verdict-summary').textContent(), /1 of 5 sources/);
    assert.equal(await page.locator('#search-source-list').getByText('No usable matches', {exact: true}).count(), 4);
    assert.equal(await page.locator('#search-source-list').getByText('Unavailable · search not completed', {exact: true}).count(), 1);
    assert.match(await page.locator('#search-query-summary').textContent(), /<img src=x/);
    assert.equal(await page.locator('#search-coverage img').count(), 0);
    const downloadPromise = page.waitForEvent('download');
    await page.click('#export-button');
    const download = await downloadPromise;
    const exported = JSON.parse(fs.readFileSync(await download.path(), 'utf8'));
    assert.equal(exported.report.collection.sources.length, 5);
    assert.equal(exported.report.collection.query, query);

    collection = {...structuredClone(empty), source: 'bbc_rss', sources: [empty.sources[2]]};
    await run('bbc');
    assert.equal(await page.locator('#search-source-list li').count(), 1);
    assert.match(await page.locator('#search-source-list').textContent(), /BBC News/);
    assert.doesNotMatch(await page.locator('#search-source-list').textContent(), /Bluesky/);

    collection = {...structuredClone(empty), source: 'context_news', cached: true, credits_consumed: 0, sources: [
      {id: 'context', name: 'Context.dev news index', status: 'ok', available_events: 0, returned_events: 0, scope: 'English articles from the last 7 days.'}]};
    await run('context');
    assert.match(await page.locator('#search-query-summary').textContent(), /Cached results/);
    assert.match(await page.locator('#search-source-list').textContent(), /Context.dev news index/);

    status = 502;
    collection = {...structuredClone(empty), sources: empty.sources.map(row => ({...row, status: 'error', available_events: null, error: 'Source timed out.'}))};
    await run('all');
    assert.equal(await page.locator('#verdict-title').textContent(), 'Search could not be completed');
    assert.equal(await page.locator('#search-source-list').getByText('Unavailable · search not completed', {exact: true}).count(), 5);
    assert.equal(await page.locator('#search-source-list').getByText('No usable matches', {exact: true}).count(), 0);

    await run('synthetic_benign');
    assert.equal(await page.locator('#search-coverage-title').textContent(), 'Data source');
    assert.equal(await page.locator('#search-source-list li').count(), 0);
    assert.match(await page.locator('#search-query-summary').textContent(), /No live search was performed/);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({cases: ['partial failure with zero matches', 'export trace', 'single source empty', 'cached Context empty', 'all sources failed', 'offline data'], browser_errors: errors}));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
