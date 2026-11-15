// Real synthetic analysis and real Cytoscape canvas; no paid provider calls.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH || undefined,args:['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport:{width:1440,height:1000}});
    const errors=[]; page.on('pageerror',e=>errors.push(e.message));
    await page.goto(process.argv[2], {waitUntil:'networkidle'});
    for (const filename of ['app.js','providers.js','styles.css']) {
      const url=await page.locator(`[src*="/static/${filename}"], [href*="/static/${filename}"]`).evaluate(el=>el.src || el.href);
      assert.match(url,/\?v=[a-f0-9]{16}$/, 'Dashboard must bypass old cached assets');
    }
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
    assert.equal(await tooltip.locator('.graph-tooltip-title').textContent(),'demo:coordinated-01');
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
    // A real pointer must focus only the actor's connections and preview edges.
    await page.evaluate(()=>{
      window.savedReport=latestReport;
      latestReport={nodes:['a','b','c','d'].map(id=>({id,event_count:3,platforms:['hackernews']})),
        edges:[{id:'a-b',source:'a',target:'b',weight:2,repeated:true,evidence_assessment:'supported'},
               {id:'c-d',source:'c',target:'d',weight:3,repeated:true}],
        clusters:[{nodes:['a','b']},{nodes:['c','d']}]};
      renderClusters(latestReport); renderGraph(latestReport);
      graph.nodes().positions(n=>({x:{a:100,b:300,c:100,d:300}[n.id()],y:['a','b'].includes(n.id())?100:260}));
      fitGraph();
    });
    await page.waitForTimeout(300);
    async function point(id,edge=false) {
      return page.evaluate(({id,edge})=>{
        const el=graph.getElementById(id),p=edge?el.renderedMidpoint():el.renderedPosition();
        const r=document.querySelector('#graph').getBoundingClientRect();
        return {x:r.left+p.x,y:r.top+p.y};
      },{id,edge});
    }
    await page.evaluate(()=>graph.$id('c-d').select());
    const a=await point('a');
    await page.mouse.move(a.x,a.y);
    await tooltip.waitFor({state:'visible'});
    assert.match(await tooltip.locator('.graph-tooltip-subtitle').textContent(),/3 records/);
    assert(await page.evaluate(()=>graph.$id('a-b').hasClass('highlighted') && graph.$id('b').hasClass('neighbor') && graph.$id('c').hasClass('dimmed') && graph.$id('c-d').hasClass('dimmed')));
    assert.equal(await page.evaluate(()=>Number(graph.$id('c-d').style('opacity'))),0.06,'Previously selected edge should dim too');
    await page.mouse.move(0,0);
    assert(await page.evaluate(()=>graph.$('.hovered, .neighbor, .highlighted, .dimmed').length===0));
    const ab=await point('a-b',true);
    await page.mouse.move(ab.x,ab.y);
    await tooltip.waitFor({state:'visible'});
    assert.equal(await tooltip.locator('.graph-tooltip-title').textContent(),'a ↔ b');
    assert.match(await tooltip.locator('.graph-tooltip-subtitle').textContent(),/2 shared-URL groups/);
    assert(await page.evaluate(()=>graph.$id('a-b').hasClass('hovered') && graph.$id('a').hasClass('neighbor') && graph.$id('c-d').hasClass('dimmed')));
    await page.screenshot({path:'/tmp/noise-edge-hover.png'});
    await page.mouse.click(ab.x,ab.y);
    assert.match(await page.locator('#graph-detail').textContent(),/a ↔ b/);
    await page.mouse.move(0,0);
    assert(await page.locator('#cluster-filter').isVisible());
    await page.selectOption('#cluster-filter','cluster-1');
    assert.deepEqual(await page.evaluate(()=>graph.nodes().map(n=>n.id()).sort()),['c','d']);
    await page.selectOption('#cluster-filter','all');
    assert.equal(await page.evaluate(()=>graph.nodes().length),4);
    await page.evaluate(()=>{latestReport=window.savedReport; renderClusters(latestReport);renderGraph(latestReport);});
    // Reproduce the screenshot's isolated grey actors, including actual hover styling.
    await page.evaluate(()=>renderGraph({nodes:Array.from({length:30},(_,i)=>({id:`hackernews:observed-actor-${i}`})),edges:[]}));
    await page.waitForTimeout(300);
    await checkFit();
    await page.locator('#graph').scrollIntoViewIfNeeded();
    const greyPoint=await page.evaluate(()=>{
      const p=graph.nodes()[12].renderedPosition(),r=document.querySelector('#graph').getBoundingClientRect();
      return {x:p.x+r.left,y:p.y+r.top};
    });
    assert(await page.evaluate(()=>graph.nodes().every(n=>n.style('label') === '')));
    await page.mouse.move(greyPoint.x,greyPoint.y);
    await tooltip.waitFor({state:'visible'});
    assert.equal(await tooltip.locator('.graph-tooltip-title').textContent(),'hackernews:observed-actor-12');
    const tipStyle=await tooltip.evaluate(el=>({position:getComputedStyle(el).position,fontSize:getComputedStyle(el).fontSize}));
    assert.deepEqual(tipStyle,{position:'absolute',fontSize:'12px'});
    await page.screenshot({path:'/tmp/noise-observed-hover.png'});
    await page.mouse.move(0,0);
    await tooltip.waitFor({state:'hidden'});
    await page.evaluate(()=>renderGraph(latestReport));
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
    assert.equal(await tooltip.locator('.graph-tooltip-title').textContent(),longId);
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
    console.log('Graph and evidence checks passed: fit, hidden labels, node/edge hover and focus, cluster filter, resize, pair provenance, inspect, reset, empty state.');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
