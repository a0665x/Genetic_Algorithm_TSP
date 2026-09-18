// Optional real-browser verification. Start python app.py first.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
  fs.mkdirSync('test-artifacts',{recursive:true});
  const browser=await chromium.launch({headless:true});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1100}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(process.env.DISPATCH_URL||'http://127.0.0.1:8000');
    await page.waitForSelector('#ordersBody tr');
    assert.equal(await page.locator('#ordersBody tr').count(),10);
    await page.screenshot({path:'test-artifacts/initial.png',fullPage:true});
    await page.click('#addOrder');assert.equal(await page.locator('#ordersBody tr').count(),11);
    await page.locator('.remove-order').last().click();
    await page.fill('#generations','20');await page.locator('#generations').press('Tab');
    await page.click('#run');
    await page.waitForFunction(()=>!document.querySelector('#exportResult').disabled,null,{timeout:90000});
    assert.equal(await page.locator('.world-card').count(),4);
    assert.equal(await page.locator('#scheduleTable tbody tr').count(),10);
    await page.locator('.world-card').nth(1).click();
    assert.match(await page.locator('#metricWorld').textContent(),/2/);
    await page.click('#play');await page.waitForTimeout(350);await page.click('#play');
    await page.locator('[data-tab="time_matrix"]').click();
    assert.equal(await page.locator('#matrixContent tbody tr').count(),11);
    await page.screenshot({path:'test-artifacts/result.png',fullPage:true});
    await page.locator('#ordersBody input').first().fill('Edited order');
    await page.locator('#ordersBody input').first().press('Tab');
    assert.equal(await page.locator('#exportResult').isDisabled(),true);
    assert.equal(await page.locator('#metricDistance').textContent(),'—');
    // UI rejects an obstacle click without adding an order.
    const before=await page.locator('#ordersBody tr').count();
    const box=await page.locator('#mapCanvas').boundingBox();
    await page.mouse.click(box.x+1,box.y+1);
    assert.equal(await page.locator('#ordersBody tr').count(),before);
    // Uploaded image must reset coordinates and require a fresh start.
    await page.setInputFiles('#upload','data/map/restaurant.png');
    await page.waitForFunction(()=>document.querySelector('#ordersBody').children.length===0);
    assert.match(await page.locator('#message').textContent(),/地圖已載入/);
    await page.locator('[data-mode="start"]').click();
    const uploaded=await page.locator('#mapCanvas').boundingBox();
    await page.mouse.click(uploaded.x+22.5/240*uploaded.width,uploaded.y+145.5/160*uploaded.height);
    await page.locator('[data-mode="order"]').click();
    await page.mouse.click(uploaded.x+70.5/240*uploaded.width,uploaded.y+35.5/160*uploaded.height);
    assert.equal(await page.locator('#ordersBody tr').count(),1);
    await page.uncheck('#sower');await page.click('#run');
    await page.waitForFunction(()=>!document.querySelector('#exportResult').disabled,null,{timeout:90000});
    assert.equal(await page.locator('.world-card').count(),1);
    await page.setViewportSize({width:390,height:844});
    await page.screenshot({path:'test-artifacts/mobile.png',fullPage:true});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+2),true);
    assert.deepEqual(errors,[]);
    console.log('Browser smoke tests passed. Screenshots: test-artifacts/');
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
