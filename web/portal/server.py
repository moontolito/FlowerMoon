"""Private Codespaces entry point: landing page, managed app and same-origin VNC."""
import asyncio,json,logging,os,sys,time
from pathlib import Path
from urllib.parse import urlsplit
from aiohttp import web,ClientSession,ClientTimeout,WSMsgType

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
APP=ROOT/'apps'/'transport'
RUNTIME=ROOT/'.runtime'
log=logging.getLogger('flowermoon')
PORTAL_VERSION='2026-10-07.1'

class Desktop:
    def __init__(self):
        self.process=None;self.task=None;self.state='starting';self.message='Preparing the application…';self.lock=asyncio.Lock()
        self.output=None

    async def start(self):
        async with self.lock:
            if self.task and not self.task.done():return
            if self.process and self.process.returncode is None:return
            self.state='starting';self.message='Preparing the application…'
            self.task=asyncio.create_task(self.launch())

    async def launch(self):
        try:
            for attempt in range(60):
                probe=await asyncio.create_subprocess_exec('xdpyinfo','-display',':1',stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
                try:code=await asyncio.wait_for(probe.wait(),3)
                except asyncio.TimeoutError:
                    probe.kill();await probe.wait();code=1
                if code==0:break
                await asyncio.sleep(1)
            else:raise RuntimeError('Display unavailable')
            RUNTIME.mkdir(exist_ok=True)
            if self.output:self.output.close()
            self.output=(RUNTIME/'transport.log').open('a',encoding='utf-8')
            env=dict(os.environ,DISPLAY=':1',PYTHONUNBUFFERED='1',PYTHONUTF8='1')
            self.process=await asyncio.create_subprocess_exec(sys.executable,'-B',str(APP/'hosted.py'),cwd=APP,env=env,stdout=self.output,stderr=asyncio.subprocess.STDOUT)
            log.info('Transport started with pid %s using %s',self.process.pid,sys.executable)
            for attempt in range(90):
                if self.process.returncode is not None:raise RuntimeError('App exited during startup')
                if self.ready():
                    self.state='ready';self.message='Ready to use';return
                await asyncio.sleep(1)
            raise RuntimeError('UI did not become ready')
        except asyncio.CancelledError:raise
        except Exception:
            log.exception('Transport startup failed')
            if self.process and self.process.returncode is None:
                await self.stop_process()
            self.state='error';self.message='Application could not start. Select Try again.'

    def ready(self):
        if not self.process or self.process.returncode is not None:return False
        try:
            data=json.loads((APP/'data'/'hosted-status.json').read_text())
            return data['pid']==self.process.pid and data['visible'] and data['widgets']>0 and time.time()-data['updatedAt']<8
        except (OSError,ValueError,KeyError):return False

    def status(self):
        if self.state=='ready' and not self.ready():
            if self.process and self.process.returncode is not None:
                self.state='stopped';self.message='Application closed. You can open it again.'
            else:return dict(state='starting',message='Waiting for the application…')
        return dict(state=self.state,message=self.message)

    async def close(self):
        if self.task and not self.task.done():
            self.task.cancel()
            await asyncio.gather(self.task,return_exceptions=True)
        await self.stop_process()
        if self.output:self.output.close()

    async def stop_process(self):
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:await asyncio.wait_for(self.process.wait(),8)
            except asyncio.TimeoutError:self.process.kill();await self.process.wait()

def same_origin(request):
    origin=request.headers.get('Origin')
    if not origin:return False
    try:
        parsed=urlsplit(origin)
        port=parsed.port
    except ValueError:return False
    if parsed.scheme not in ('http','https') or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:return False
    codespace=os.environ.get('CODESPACE_NAME','')
    domain=os.environ.get('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN','app.github.dev')
    public_host=f'{codespace}-8000.{domain}'
    expected=request.headers.get('X-Forwarded-Host',request.host).split(',')[0].strip()
    if codespace:
        if origin==f'https://{public_host}':return True
        # The Codespaces tunnel also rewrites Origin to the internal service,
        # while retaining the public Host or X-Forwarded-Host. Accept only our
        # own port and a request addressed to this session or its loopback.
        local_hosts={'localhost','127.0.0.1','[::1]','localhost:8000','127.0.0.1:8000','[::1]:8000'}
        if parsed.hostname in ('localhost','127.0.0.1','::1') and port in (None,8000):
            return request.host in local_hosts|{public_host} and expected in local_hosts|{public_host}
    return parsed.netloc==expected

def rejected_origin(request):
    # Record routing metadata only; never cookies, tokens, or all request headers.
    raw=request.headers.get('Origin','')
    try:
        parsed=urlsplit(raw)
        origin=f'{parsed.scheme}://{parsed.hostname or "missing"}:{parsed.port or "default"}'
    except ValueError:origin='invalid'
    details=dict(origin=origin,host=request.host[:250],forwardedHost=request.headers.get('X-Forwarded-Host','')[:250],portalVersion=PORTAL_VERSION)
    log.warning('Portal origin rejected: %s',json.dumps(details))
    return details

async def index(request):return web.FileResponse(HERE/'static'/'index.html')
async def workspace(request):return web.FileResponse(HERE/'static'/'workspace.html')
async def logo(request):return web.FileResponse(APP/'assets'/'FlowerMoonLogo.png')
async def nesting(request):return web.FileResponse(ROOT/'apps'/'nesting'/'index.html')

async def exports(request):
    folder=APP/'data'/'exports'
    files=sorted((p for p in folder.glob('*.xlsx') if not p.is_symlink() and p.is_file()),key=lambda p:p.stat().st_mtime,reverse=True)[:20]
    return web.json_response([{'name':p.name,'url':'/exports/'+p.name} for p in files],headers={'Cache-Control':'no-store'})

async def download(request):
    folder=(APP/'data'/'exports').resolve();name=request.match_info['name'];path=folder/name
    if path.is_symlink() or path.resolve().parent!=folder or path.suffix!='.xlsx' or not path.is_file():raise web.HTTPNotFound()
    return web.FileResponse(path,headers={'Content-Disposition':'attachment; filename="'+path.name.replace('"','')+'"','Cache-Control':'no-store'})

async def status(request):
    data=request.app['desktop'].status()
    data['session']=os.environ.get('CODESPACE_NAME','local')
    data['portalVersion']=PORTAL_VERSION
    return web.json_response(data,headers={'Cache-Control':'no-store'})

async def start(request):
    if not same_origin(request):
        return web.json_response(dict(code='origin_mismatch',message='The application address was not accepted. Update the Codespace and restart it, then reopen port 8000.',diagnostics=rejected_origin(request)),status=403,headers={'Cache-Control':'no-store'})
    if request.headers.get('X-FlowerMoon-Client')!='portal':raise web.HTTPForbidden()
    await request.app['desktop'].start()
    return await status(request)

async def websocket(request):
    if not same_origin(request):
        rejected_origin(request)
        raise web.HTTPForbidden()
    if not request.app['desktop'].ready():raise web.HTTPServiceUnavailable(text='App is starting')
    session=request.app['session']
    try:upstream=await session.ws_connect('http://127.0.0.1:6080/websockify',max_msg_size=32*1024*1024)
    except Exception:raise web.HTTPServiceUnavailable(text='Desktop connection is starting') from None
    client=web.WebSocketResponse(max_msg_size=32*1024*1024,heartbeat=30)
    await client.prepare(request)
    async def relay(source,target):
        async for message in source:
            if message.type==WSMsgType.BINARY:await target.send_bytes(message.data)
            elif message.type==WSMsgType.TEXT:await target.send_str(message.data)
            elif message.type in (WSMsgType.CLOSE,WSMsgType.CLOSED,WSMsgType.ERROR):break
    tasks=[asyncio.create_task(relay(client,upstream)),asyncio.create_task(relay(upstream,client))]
    try:await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        await upstream.close();await client.close()
    return client

async def lifecycle(app):
    app['session']=ClientSession(timeout=ClientTimeout(total=None,sock_connect=10))
    await app['desktop'].start()
    yield
    await app['desktop'].close();await app['session'].close()

def create_app(novnc_path=None,desktop=None):
    app=web.Application(client_max_size=1024)
    app['desktop']=desktop or Desktop()
    app.cleanup_ctx.append(lifecycle)
    app.router.add_get('/',index);app.router.add_get('/app',workspace)
    app.router.add_get('/logo.png',logo);app.router.add_get('/nesting',nesting)
    app.router.add_get('/api/status',status);app.router.add_post('/api/start',start)
    app.router.add_get('/api/exports',exports);app.router.add_get('/exports/{name}',download)
    app.router.add_get('/websockify',websocket)
    app.router.add_static('/static',HERE/'static',show_index=False)
    novnc_path=novnc_path or next(Path('/usr/local/novnc').glob('noVNC-*'),None)
    if novnc_path:app.router.add_static('/novnc',novnc_path,show_index=False)
    return app

if __name__=='__main__':
    import fcntl
    RUNTIME.mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    with (RUNTIME/'portal.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise SystemExit('FlowerMoon portal is already running.')
        web.run_app(create_app(),host='0.0.0.0',port=8000,access_log=None)
