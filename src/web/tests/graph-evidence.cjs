// Real synthetic analysis and real Cytoscape canvas; no paid provider calls.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH || undefined,args:['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    await page.goto(process.argv[2], {waitUntil:'networkidle'});
    await page.waitForFunction(()=>typeof window.cytoscape === 'function');
    await page.locator('[data-investigation-toggle]').first().click();
    await page.selectOption('#source','synthetic_coordinated');
    await page.click('#investigate-button');
    await page.locator('#investigation-overlay').waitFor({state:'hidden'});
    await page.waitForFunction(()=>graph && graph.nodes().length === 12);
    async function geometry() {
      return page.evaluate(()=>({zoom:graph.zoom(), width:graph.width(),height:graph.height(),
        boxes:graph.nodes().map(n=>({id:n.id(),...n.renderedBoundingBox()})),
        nodeSize:graph.nodes()[0].renderedWidth(),
        overflow:document.documentElement.scrollWidth > innerWidth,
        evidenceOverflow:document.querySelector('#evidence-feed').scrollWidth > document.querySelector('#evidence-feed').clientWidth+1}));
    }
    async function checkFit() {
      const g=await geometry();
      assert(g.zoom<=1 && g.nodeSize<=24.1, JSON.stringify(g));
      assert(g.nodeSize>=16,'Fitting the graph made its nodes and labels unreadable');
      assert(!g.overflow && !g.evidenceOverflow,'Page or evidence panel overflows');
      for (const b of g.boxes) assert(b.x1>=0 && b.y1>=0 && b.x2<=g.width+1 && b.y2<=g.height+1,`Clipped node ${b.id}`);
      assert(await page.evaluate(()=>graph.nodes().every(n=>n.style('label') === '')), 'Actor labels must be hidden by default');
    }
    await checkFit();
    await page.locator('#graph').scrollIntoViewIfNeeded();
    const tooltip=page.locator('.graph-actor-tooltip');
    assert(!await tooltip.isVisible());
    const nodePoint = await page.evaluate(()=>{
      const p=graph.nodes()[0].renderedPosition(), r=document.querySelector('#graph').getBoundingClientRect();
      return {x:p.x+r.left,y:p.y+r.top};
    });
    await page.mouse.move(nodePoint.x,nodePoint.y);
    await tooltip.waitFor({state:'visible'});
    assert.equal(await tooltip.textContent(),'demo:coordinated-01');
    await page.mouse.move(0,0);
    await tooltip.waitFor({state:'hidden'});
    await page.mouse.click(nodePoint.x,nodePoint.y);
    assert.match(await page.locator('#graph-detail').textContent(),/demo:coordinated-01/);
    const headings=await page.locator('.evidence-card h3').allTextContents();
    assert.equal(headings.length,16);
    assert.equal(new Set(headings).size,16,'Different relationships have indistinguishable headings');
    assert(headings.every(h=>h.includes(' ↔ ')));
    const first=page.locator('.evidence-card').first();
    assert.match(await first.textContent(),/demo:coordinated-01 ↔ demo:coordinated-02/);
    assert.equal(await first.locator('a').count(),2,'Show a source from each actor');
    await first.getByRole('button',{name:'Inspect relationship'}).click();
    assert.match(await page.locator('#graph-detail').textContent(),/demo:coordinated-01 ↔ demo:coordinated-02/);
    await page.click('#graph-zoom-in');
    await page.click('#graph-reset');
    await checkFit();
    await page.locator('#graph-section').scrollIntoViewIfNeeded();
    await page.screenshot({path:'/tmp/noise-graph-fixed-desktop.png'});
    await page.setViewportSize({width:390,height:844});
    await page.waitForTimeout(400);
    await checkFit();
    await page.locator('#graph-section').scrollIntoViewIfNeeded();
    await page.screenshot({path:'/tmp/noise-graph-fixed-mobile.png'});
    // Sparse layouts use the real CoSE engine too; a tiny component cannot blow up.
    await page.evaluate(()=>renderGraph({nodes:[{id:'a'},{id:'b'}],edges:[{id:'a-b',source:'a',target:'b',weight:2,repeated:true}]}));
    await page.waitForTimeout(300);
    await checkFit();
    // Observed actors also stay unlabeled; long hover text wraps inside mobile bounds.
    const longId='observed:'+'long-actor-id-'.repeat(12);
    await page.evaluate(id=>renderGraph({nodes:[{id}],edges:[]}),longId);
    await page.waitForTimeout(300);
    await page.locator('#graph').scrollIntoViewIfNeeded();
    assert(await page.evaluate(()=>graph.nodes()[0].style('label') === ''));
    const observedPoint=await page.evaluate(()=>{
      const p=graph.nodes()[0].renderedPosition(),r=document.querySelector('#graph').getBoundingClientRect();
      return {x:p.x+r.left,y:p.y+r.top};
    });
    await page.mouse.move(observedPoint.x,observedPoint.y);
    await tooltip.waitFor({state:'visible'});
    assert.equal(await tooltip.textContent(),longId);
    const tipBounds=await tooltip.boundingBox(), graphBounds=await page.locator('#graph').boundingBox();
    assert(tipBounds.x>=graphBounds.x && tipBounds.x+tipBounds.width<=graphBounds.x+graphBounds.width);
    assert(tipBounds.y>=graphBounds.y && tipBounds.y+tipBounds.height<=graphBounds.y+graphBounds.height);
    await page.mouse.click(observedPoint.x,observedPoint.y);
    assert((await page.locator('#graph-detail').textContent()).includes(longId));
    // Empty report clears selections and disconnects the previous resize observer.
    await page.evaluate(()=>{latestEvents=[]; renderReport({nodes:[],edges:[],evidence:[],clusters:[],statistics:{},status:'insufficient_data'},{});});
    assert.match(await page.locator('#graph-detail').textContent(),/Select a node or relationship/);
    assert.match(await page.locator('#graph').textContent(),/no graphable actor/);
    assert.deepEqual(errors,[]);
    console.log('Graph and evidence checks passed: fit, hidden labels, hover, resize, pair provenance, inspect, reset, empty state.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
