import {test,expect} from '@playwright/test';
import {mkdir} from 'node:fs/promises';

test('one button opens the real app; refresh reconnects; landing fits small screens',async({page,request})=>{
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await mkdir('../../.artifacts',{recursive:true});
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'FlowerMoon Transport',exact:true})).toBeVisible();
  await page.screenshot({path:'../../.artifacts/portal-home.png',fullPage:true});
  await page.getByRole('link',{name:'Deschide aplicația'}).click();
  await expect(page.locator('body')).toHaveAttribute('data-connected','true',{timeout:150000});
  await expect(page.locator('#overlay')).toBeHidden();
  await expect(page.locator('#screen canvas')).toBeVisible();
  expect((await (await request.get('/api/status')).json()).state).toBe('ready');
  await page.screenshot({path:'../../.artifacts/portal-transport.png',fullPage:true});
  await page.reload();
  await expect(page.locator('body')).toHaveAttribute('data-connected','true',{timeout:30000});
  await page.getByRole('link',{name:'Înapoi'}).click();
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:'../../.artifacts/portal-mobile.png',fullPage:true});
  await page.getByRole('link',{name:'Deschide Nesting'}).click();
  await expect(page).toHaveURL(/\/nesting$/);
  expect(errors).toEqual([]);
});

test('connection failure shows a retry control instead of a blank page',async({page})=>{
  await page.route('**/api/status',route=>route.fulfill({json:{state:'error',message:'Test connection failure'}}));
  await page.goto('/app');
  await expect(page.locator('#detail')).toHaveText('Test connection failure');
  await expect(page.getByRole('button',{name:'Încearcă din nou'})).toBeVisible();
  await page.unroute('**/api/status');
  await page.getByRole('button',{name:'Încearcă din nou'}).click();
  await expect(page.locator('body')).toHaveAttribute('data-connected','true',{timeout:30000});
});
