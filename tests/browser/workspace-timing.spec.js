import {test,expect} from '@playwright/test';

// Control desktop events while running the actual portal script in Chromium.
async function prepare(page){
  await page.clock.install();
  await page.route('**/api/start',route=>route.fulfill({json:{state:'ready'}}));
  await page.route('**/api/status',route=>route.fulfill({json:{state:'ready',message:'Ready to use'}}));
  await page.route('**/api/exports',route=>route.fulfill({json:[]}));
  await page.route('**/novnc/core/rfb.js',route=>route.fulfill({contentType:'application/javascript',body:`
    export default class RFB extends EventTarget {
      constructor(target){
        super();window.testDesktop=this;
        this.canvas=document.createElement('canvas');
        this.canvas.width=400;this.canvas.height=300;target.append(this.canvas);
      }
      paint(){const ctx=this.canvas.getContext('2d');ctx.fillStyle='#885099';ctx.fillRect(0,0,400,300);}
      disconnect(){this.dispatchEvent(new Event('disconnect'));}
    }
  `}));
  await page.goto('/app');
  await page.waitForFunction(()=>Boolean(window.testDesktop));
}

test('slow handshake and first image can arrive after the old deadlines',async({page})=>{
  await prepare(page);
  await page.clock.fastForward(35000);
  await expect(page.locator('#retry')).toBeHidden();
  await page.evaluate(()=>window.testDesktop.dispatchEvent(new Event('connect')));
  await page.clock.fastForward(25000);
  await expect(page.locator('#retry')).toBeHidden();
  await page.evaluate(()=>window.testDesktop.paint());
  await page.clock.fastForward(250);
  await expect(page.locator('body')).toHaveAttribute('data-connected','true');
  await page.clock.fastForward(120000);
  await expect(page.locator('#overlay')).toBeHidden();
});

test('stalled connection keeps its timeout reason when disconnect fires',async({page})=>{
  await prepare(page);
  await page.clock.fastForward(120001);
  await expect(page.locator('#detail')).toHaveText('The application image did not arrive within two minutes. Try again.');
  await expect(page.locator('#retry')).toBeVisible();
});

test('security failure keeps its reason and a late frame cannot hide the error',async({page})=>{
  await prepare(page);
  await page.evaluate(()=>window.testDesktop.dispatchEvent(new Event('connect')));
  await page.evaluate(()=>window.testDesktop.dispatchEvent(new Event('securityfailure')));
  await page.evaluate(()=>window.testDesktop.paint());
  await page.clock.fastForward(121000);
  await expect(page.locator('#detail')).toHaveText('The desktop connection was not accepted. Try again.');
  await expect(page.locator('#overlay')).toBeVisible();
  await expect(page.locator('body')).toHaveAttribute('data-connected','false');
});
