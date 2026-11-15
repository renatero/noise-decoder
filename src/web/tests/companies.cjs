// Automatic start, polling, dataset race, grounding display and lock; no paid calls.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH || undefined,args:['--no-sandbox']});
  try {
    const page = await browser.newPage();
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    let starts=0, polls=0, bodies=[];
    const job = (id,synthetic) => ({id,status:'running',created_at:Date.now()/1000,synthetic,message:'Company detection running',notice:'Experimental; scores unchanged.',coverage:{records_submitted:1,total_records:1,detection_characters_per_record:1000,review_characters_per_record:2000,detection_truncated_records:0,max_companies:2},stages:[],companies:[]});
    await page.route('**/api/settings', route=>route.fulfill({json:{providers:[{id:'openrouter',name:'OpenRouter',enabled:true,key_configured:true,model:'~typesafe/jev-latest',base_url:'https://openrouter.ai/api'}]}}));
    await page.route('**/api/experimental/companies', route=>{
      assert.equal(route.request().headers()['x-noise-operator'],'test-token');
      const body=route.request().postDataJSON(); bodies.push(body); starts++;
      return route.fulfill({status:202,json:job(String(starts),body.synthetic)});
    });
    await page.route('**/api/experimental/companies/*', route=>{
      polls++; const result=job('1',true); result.status='completed';result.message='Company research finished';
      result.companies=[{name:'<img src=x onerror=alert(1)>',id:'original:1',quote:'Example Ltd received a government research grant.',probability:.98}];
      result.stages=[{stage:'Cala.ai check',status:'skipped',message:'Synthetic company: external ownership lookup skipped.'}];
      return route.fulfill({json:result});
    });
    await page.goto(process.argv[2],{waitUntil:'domcontentloaded'});
    await page.evaluate(()=>{latestEvents=[{id:'original:1',text:'Example Ltd received a government research grant.'}];latestReport={synthetic:true};document.dispatchEvent(new Event('noise:report'));});
    assert.equal(starts,0);
    await page.click('#settings-button');await page.fill('#operator-token','test-token');await page.locator('#settings-unlock button').click();
    await page.waitForFunction(()=>document.querySelector('#company-status').textContent.includes('completed'));
    assert.equal(starts,1);assert.equal(bodies[0].synthetic,true);assert(polls>0);
    assert.match(await page.locator('#company-result').textContent(),/external ownership lookup skipped/);
    assert.equal(await page.locator('#company-result img').count(),0);
    assert.equal(await page.evaluate(()=>localStorage.length),0);
    await page.click('#settings-close');
    const download=page.waitForEvent('download');await page.click('#company-export');await download;
    // New dataset automatically starts its own job, then lock invalidates polling.
    await page.evaluate(()=>{latestReport={synthetic:false};document.dispatchEvent(new Event('noise:report'));});
    await page.waitForFunction(()=>document.querySelector('#company-status').textContent.includes('running'));
    assert.equal(starts,2);assert.equal(bodies[1].synthetic,false);
    await page.click('#settings-button');await page.click('#settings-lock');
    const pollsAtLock=polls;await page.waitForTimeout(2300);assert.equal(polls,pollsAtLock);
    assert.match(await page.locator('#company-status').textContent(),/Locked/);
    assert.deepEqual(errors,[]);
    console.log('Automatic company browser checks passed: unlock/start, polling, provenance, XSS, export, new dataset, lock.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
