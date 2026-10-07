import {test,expect} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';

test('browser clicks change the actual Transport sidebar',async({page})=>{
  const report={events:[],pointerMessages:0,keyMessages:0,receivedFrames:0};
  const start=Date.now();
  const record=(event,extra={})=>report.events.push({event,ms:Date.now()-start,...extra});
  page.on('pageerror',error=>record('pageerror',{message:error.message}));
  page.on('websocket',socket=>{
    record('websocket-open');
    socket.on('framesent',frame=>{
      if(Buffer.isBuffer(frame.payload)){
        if(frame.payload[0]===5)report.pointerMessages++;
        if(frame.payload[0]===4)report.keyMessages++;
      }
    });
    socket.on('framereceived',()=>report.receivedFrames++);
    socket.on('close',()=>record('websocket-close'));
    socket.on('socketerror',error=>record('websocket-error',{message:String(error)}));
  });
  await mkdir('../../.artifacts',{recursive:true});
  try{
    await page.goto('/app');
    await expect(page.locator('body')).toHaveAttribute('data-connected','true',{timeout:160000});
    record('connected');
    await page.screenshot({path:'../../.artifacts/input-before.png',fullPage:true});
    const canvas=page.locator('#screen canvas');
    const purpleAt=async x=>canvas.evaluate((c,x)=>{
      const [r,g,b]=c.getContext('2d').getImageData(x,141,1,1).data;
      return r>100&&r<170&&g>35&&g<110&&b>100&&b<180;
    },x);
    const click=async(x,y)=>{
      const box=await canvas.boundingBox();
      const size=await canvas.evaluate(c=>({width:c.width,height:c.height}));
      await page.mouse.click(box.x+x*box.width/size.width,box.y+y*box.height/size.height);
      // Move away so a hover style cannot be mistaken for selection.
      await page.mouse.move(1400,20);
    };
    await click(100,141);
    await expect.poll(()=>purpleAt(65),{timeout:30000,message:'Route tab did not respond'}).toBe(true);
    record('route-selected');
    await click(265,141);
    await expect.poll(()=>purpleAt(205),{timeout:30000,message:'Vehicle tab did not respond'}).toBe(true);
    record('vehicle-selected');
    await page.screenshot({path:'../../.artifacts/input-vehicle.png',fullPage:true});
    await click(100,141);
    await expect.poll(()=>purpleAt(65),{timeout:30000,message:'Route tab did not respond after Vehicle'}).toBe(true);
    record('route-restored');
    expect(report.pointerMessages).toBeGreaterThan(0);
  }finally{
    await page.screenshot({path:'../../.artifacts/input-final.png',fullPage:true}).catch(()=>{});
    await writeFile('../../.artifacts/input-report.json',JSON.stringify(report,null,2));
    console.log(JSON.stringify(report));
  }
});
