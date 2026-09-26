const overlay=document.querySelector('#overlay'),message=document.querySelector('#message'),detail=document.querySelector('#detail'),retry=document.querySelector('#retry'),connection=document.querySelector('#connection');
let rfb=null,busy=false,generation=0;
function showError(text){document.body.dataset.connected='false';overlay.hidden=false;overlay.classList.add('error');message.textContent='Connection not ready';detail.textContent=text;retry.hidden=false;connection.textContent='Reconnection required';}
function frameHasContent(){const c=document.querySelector('#screen canvas');if(!c||c.width<200||c.height<200)return false;const ctx=c.getContext('2d');if(!ctx)return false;const data=ctx.getImageData(0,0,c.width,c.height).data;let visible=0,painted=0;for(let i=0;i<data.length;i+=400){if(data[i+3])visible++;if(Math.min(data[i],data[i+1],data[i+2])<230)painted++;}return visible>100&&painted/visible>.02;}
async function connect(){
  if(busy)return;busy=true;const mine=++generation;
  if(rfb){rfb.disconnect();rfb=null;}
  overlay.hidden=false;overlay.classList.remove('error');retry.hidden=true;message.textContent='Opening application…';detail.textContent='The connection starts automatically. No terminal commands or extra passwords are required.';
  try{
    const started=await fetch('/api/start',{method:'POST',headers:{'X-FlowerMoon-Client':'portal'},signal:AbortSignal.timeout(15000)});if(!started.ok)throw Error('Could not request startup. Reload the page.');
    let data;
    for(let i=0;i<100;i++){
      if(mine!==generation)return;const response=await fetch('/api/status',{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!response.ok)throw Error('The service is not responding.');data=await response.json();message.textContent=data.message;
      if(data.state==='ready')break;if(data.state==='error'||data.state==='stopped')throw Error(data.message);
      await new Promise(resolve=>setTimeout(resolve,1000));
    }
    if(data.state!=='ready')throw Error('Startup is taking longer than usual. Try again.');
    const {default:RFB}=await import('/novnc/core/rfb.js');
    if(mine!==generation)return;
    rfb=new RFB(document.querySelector('#screen'),`${location.protocol==='https:'?'wss':'ws'}://${location.host}/websockify`,{credentials:{password:'vscode'},shared:true});
    rfb.scaleViewport=true;rfb.resizeSession=false;rfb.background='#252527';
    const deadline=setTimeout(()=>{if(mine===generation&&document.body.dataset.connected!=='true'){rfb.disconnect();showError('The connection is taking too long. Try again.');}},30000);
    rfb.addEventListener('securityfailure',()=>{if(mine===generation)showError('The desktop connection was not accepted. Try again.');});
    rfb.addEventListener('disconnect',()=>{if(mine===generation)showError('Connection interrupted. Your project remains in this session.');});
    rfb.addEventListener('connect',async()=>{
      connection.textContent='Displaying application…';
      for(let i=0;i<100;i++){
        if(mine!==generation)return;
        if(frameHasContent()){clearTimeout(deadline);overlay.hidden=true;connection.textContent='Connected';document.body.dataset.connected='true';return;}
        await new Promise(resolve=>setTimeout(resolve,200));
      }
      showError('Connected, but no application image has arrived. Try again.');
    });
  }catch(error){showError(error.message||'Could not open the application.');}
  finally{busy=false;}
}
retry.addEventListener('click',connect);
document.querySelector('#fullscreen').addEventListener('click',()=>{if(!document.fullscreenElement)document.documentElement.requestFullscreen().catch(()=>{});else document.exitFullscreen();});
connect();

async function refreshExports(){
  try{
    const response=await fetch('/api/exports',{cache:'no-store',signal:AbortSignal.timeout(8000)});
    if(!response.ok)return;const files=await response.json(),button=document.querySelector('#download');
    if(files.length){button.href='/exports/'+encodeURIComponent(files[0].name);button.hidden=false;button.title=files[0].name;}
  }catch{}
}
refreshExports();setInterval(refreshExports,3000);
