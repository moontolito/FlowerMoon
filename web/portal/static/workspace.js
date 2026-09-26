const overlay=document.querySelector('#overlay'),message=document.querySelector('#message'),detail=document.querySelector('#detail'),retry=document.querySelector('#retry'),connection=document.querySelector('#connection');
let rfb=null,busy=false,generation=0;
function showError(text){document.body.dataset.connected='false';overlay.hidden=false;overlay.classList.add('error');message.textContent='Conexiunea nu este pregătită';detail.textContent=text;retry.hidden=false;connection.textContent='Reconectare necesară';}
function frameHasContent(){const c=document.querySelector('#screen canvas');if(!c||c.width<200||c.height<200)return false;const ctx=c.getContext('2d');if(!ctx)return false;const data=ctx.getImageData(0,0,c.width,c.height).data;let visible=0,painted=0;for(let i=0;i<data.length;i+=400){if(data[i+3])visible++;if(Math.min(data[i],data[i+1],data[i+2])<230)painted++;}return visible>100&&painted/visible>.02;}
async function connect(){
  if(busy)return;busy=true;const mine=++generation;
  if(rfb){rfb.disconnect();rfb=null;}
  overlay.hidden=false;overlay.classList.remove('error');retry.hidden=true;message.textContent='Deschidem aplicația…';detail.textContent='Conexiunea se pregătește automat. Nu este nevoie de comenzi sau parole suplimentare.';
  try{
    const started=await fetch('/api/start',{method:'POST',headers:{'X-FlowerMoon-Client':'portal'},signal:AbortSignal.timeout(15000)});if(!started.ok)throw Error('Pornirea nu a putut fi solicitată. Reîncarcă pagina.');
    let data;
    for(let i=0;i<100;i++){
      if(mine!==generation)return;const response=await fetch('/api/status',{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!response.ok)throw Error('Serviciul nu răspunde momentan.');data=await response.json();message.textContent=data.message;
      if(data.state==='ready')break;if(data.state==='error'||data.state==='stopped')throw Error(data.message);
      await new Promise(resolve=>setTimeout(resolve,1000));
    }
    if(data.state!=='ready')throw Error('Pregătirea durează mai mult decât de obicei. Încearcă din nou.');
    const {default:RFB}=await import('/novnc/core/rfb.js');
    if(mine!==generation)return;
    rfb=new RFB(document.querySelector('#screen'),`${location.protocol==='https:'?'wss':'ws'}://${location.host}/websockify`,{credentials:{password:'vscode'},shared:true});
    rfb.scaleViewport=true;rfb.resizeSession=false;rfb.background='#252527';
    const deadline=setTimeout(()=>{if(mine===generation&&document.body.dataset.connected!=='true'){rfb.disconnect();showError('Conexiunea durează prea mult. Încearcă din nou.');}},30000);
    rfb.addEventListener('securityfailure',()=>{if(mine===generation)showError('Conexiunea desktopului nu a fost acceptată. Încearcă din nou.');});
    rfb.addEventListener('disconnect',()=>{if(mine===generation)showError('Conexiunea a fost întreruptă. Proiectul rămâne în această sesiune.');});
    rfb.addEventListener('connect',async()=>{
      connection.textContent='Se afișează aplicația…';
      for(let i=0;i<100;i++){
        if(mine!==generation)return;
        if(frameHasContent()){clearTimeout(deadline);overlay.hidden=true;connection.textContent='Conectat';document.body.dataset.connected='true';return;}
        await new Promise(resolve=>setTimeout(resolve,200));
      }
      showError('Desktopul este conectat, dar imaginea aplicației nu a sosit. Încearcă din nou.');
    });
  }catch(error){showError(error.message||'Nu am putut deschide aplicația.');}
  finally{busy=false;}
}
retry.addEventListener('click',connect);
document.querySelector('#fullscreen').addEventListener('click',()=>{if(!document.fullscreenElement)document.documentElement.requestFullscreen().catch(()=>{});else document.exitFullscreen();});
connect();
