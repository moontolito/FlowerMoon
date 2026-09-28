import {test,expect} from '@playwright/test';
import {mkdir,writeFile,readFile,unlink} from 'node:fs/promises';

test('one button opens the real app; refresh reconnects; landing fits small screens',async({page,request})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await mkdir('../../.artifacts',{recursive:true});
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'FlowerMoon Transport',exact:true})).toBeVisible();
  await page.screenshot({path:'../../.artifacts/portal-home.png',fullPage:true});
  await page.getByRole('link',{name:'Open application'}).click();
  await expect(page.locator('body')).toHaveAttribute('data-connected','true',{timeout:150000});
  await expect(page.locator('#overlay')).toBeHidden();
  await expect(page.locator('#screen canvas')).toBeVisible();
  expect((await (await request.get('/api/status')).json()).state).toBe('ready');
  await page.screenshot({path:'../../.artifacts/portal-transport.png',fullPage:true});
  await page.reload();
  await expect(page.locator('body')).toHaveAttribute('data-connected','true',{timeout:30000});
  await page.getByRole('link',{name:'Back'}).click();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'../../.artifacts/portal-mobile.png',fullPage:true});
  await page.getByRole('link',{name:'Open Nesting'}).click();
  await expect(page).toHaveURL(/\/nesting$/);
  expect(errors).toEqual([]);
});

test('connection failure shows a retry control instead of a blank page',async({page})=>{
  await page.route('**/api/status',route=>route.fulfill({json:{state:'error',message:'Test connection failure'}}));
  await page.goto('/app');
  await expect(page.locator('#detail')).toHaveText('Test connection failure');
  await expect(page.getByRole('button',{name:'Try again'})).toBeVisible();
  await page.unroute('**/api/status');
  await page.getByRole('button',{name:'Try again'}).click();
  await expect(page.locator('body')).toHaveAttribute('data-connected','true',{timeout:30000});
});

test('startup rejection explains recovery and retry reconnects',async({page})=>{
  const message='The application address was not accepted. Update the Codespace and restart it, then reopen port 8000.';
  await page.route('**/api/start',route=>route.fulfill({status:403,json:{code:'origin_mismatch',message}}));
  await page.goto('/app');
  await expect(page.locator('#detail')).toHaveText(message);
  await expect(page.getByRole('button',{name:'Try again'})).toBeVisible();
  await page.unroute('**/api/start');
  await page.getByRole('button',{name:'Try again'}).click();
  await expect(page.locator('body')).toHaveAttribute('data-connected','true',{timeout:30000});
});

test('completed exports can be downloaded from the browser toolbar',async({page})=>{
  const folder='../../apps/transport/data/exports',name='browser-download-test.xlsx';
  const bytes=Buffer.from('FlowerMoon download transport fixture');
  await mkdir(folder,{recursive:true});await writeFile(`${folder}/${name}`,bytes);
  try{
    await page.goto('/app');
    const button=page.getByRole('link',{name:'Download Excel'});
    await expect(button).toBeVisible({timeout:15000});
    const pending=page.waitForEvent('download');await button.click();const download=await pending;
    expect(download.suggestedFilename()).toBe(name);
    expect(await readFile(await download.path())).toEqual(bytes);
  }finally{await unlink(`${folder}/${name}`);}
});
