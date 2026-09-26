const status = document.querySelector('#status');
async function refresh(){
  try{const response=await fetch('/api/status',{cache:'no-store'});if(!response.ok)throw Error();const data=await response.json();status.textContent=data.message;status.classList.toggle('ready',data.state==='ready');document.querySelector('#session').textContent=data.session==='local'?'':`Session: ${data.session}`;}
  catch{status.textContent='Reconnecting…';status.classList.remove('ready');}
}
refresh();setInterval(refresh,3000);
