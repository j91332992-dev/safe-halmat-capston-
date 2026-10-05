// Run after build with Playwright available on NODE_PATH. All API data is mocked.
const {chromium} = require('playwright');
const {createServer} = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const dist = path.resolve(__dirname, '../dist');
const server = createServer((req, res) => {
  const file = path.join(dist, req.url.split('?')[0] === '/' ? 'index.html' : req.url.split('?')[0]);
  const target = fs.existsSync(file) && fs.statSync(file).isFile() ? file : path.join(dist, 'index.html');
  res.setHeader('Content-Type', target.endsWith('.js') ? 'text/javascript' : target.endsWith('.css') ? 'text/css' : 'text/html');
  res.end(fs.readFileSync(target));
});
const worker = {worker_id:'test-worker',worker_name:'테스트 작업자',worker_role:'general_worker',notes:'',helmet_id:'test-helmet',x:2,y:3,confidence:.95,current_zone:null,risk_score:0,risk_level:'정상',risk_reasons:[],decision:null,ppe:{},hazards:{},emergency:false,updated_at:new Date().toISOString()};
const snapshot = {site:{site_id:'test',name:'테스트 현장',width:10,height:10},workers:[worker],devices:[{device_id:'test-av',worker_id:'test-worker',device_type:'assistant_device',online:true,battery:82,component_status:{},last_seen:new Date().toISOString()}],anchors:[],obstacles:[],zones:[],events:[{event_id:'notice',severity:'warning',status:'open',message:'장비 점검 필요',event_type:'TEST',worker_id:'test-worker',details:{},created_at:new Date().toISOString()}],evacuation:{incident:null,routes:{}}};
(async () => {
  let browser;
  try {
    await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
    browser = await chromium.launch({headless:true, channel:'msedge'});
    for (const [width,height,touch] of [[375,812,true],[390,844,true],[820,1180,true],[1180,820,true],[1440,900,false]]) {
      const context = await browser.newContext({viewport:{width,height},hasTouch:touch,isMobile:touch});
      await context.addInitScript(() => sessionStorage.setItem('hanmir_admin_session','mock-only'));
      await context.route('**/api/**', route => route.fulfill({json:route.request().url().includes('/snapshot') ? snapshot : route.request().url().includes('/history') ? [] : {username:'test',role:'admin'}}));
      const page = await context.newPage();
      const errors=[];
      page.on('pageerror', e=>errors.push(e.message));
      await page.goto(`http://127.0.0.1:${server.address().port}/dashboard`);
      await page.locator(touch ? '.ops-home' : '.desktop-dashboard').waitFor({state:'visible'});
      assert.equal(await page.locator('.ops-home').isVisible(),touch);
      assert.equal(await page.locator('.desktop-dashboard').isVisible(),!touch);
      if(touch) {
        assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`Overflow at ${width}`);
        const headers = await page.locator('.ops-card > header > h3').evaluateAll(elements => elements.map(element => {
          const style = getComputedStyle(element);
          return {text: element.textContent?.trim(), height: element.getBoundingClientRect().height, lineHeight: Number.parseFloat(style.lineHeight)};
        }));
        for (const header of headers) assert(header.height <= header.lineHeight * 1.6, `Wrapped card title: ${header.text} at ${width}`);
        if (process.env.UI_SCREENSHOT_DIR) await page.screenshot({path:path.join(process.env.UI_SCREENSHOT_DIR, `hanmir-dashboard-${width}.png`)});
        await page.locator('.ops-notification-strip').click();
        const box=await page.locator('.ops-alert-sheet').boundingBox();
        assert(box.x>=0 && box.x+box.width<=width,`Modal clipped at ${width}`);
        await page.locator('.ops-alert-sheet > header button').click();
        await page.locator('.bottom-tab').last().click();
        await page.locator('.ops-menu-group summary').first().click();
        assert(await page.locator('.ops-menu-group[open] .drawer-nav-item').count()===3);
      }
      assert.deepEqual(errors,[]);
      if (process.env.UI_SCREENSHOT_DIR) await page.screenshot({path:path.join(process.env.UI_SCREENSHOT_DIR, `hanmir-${width}.png`)});
      console.log(`PASS ${width}x${height} ${touch?'touch':'desktop'}: layout, navigation, runtime`);
      await context.close();
    }
  } finally { if(browser) await browser.close(); server.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
