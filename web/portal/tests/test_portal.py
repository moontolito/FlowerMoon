"""Portal contract: startup, private files, origin checks, and failure visibility."""
import asyncio,json,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from aiohttp.test_utils import AioHTTPTestCase

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server

class FakeDesktop:
    def __init__(self):self.starts=0;self.state='starting';self.closed=False
    async def start(self):self.starts+=1
    async def close(self):self.closed=True
    def ready(self):return self.state=='ready'
    def status(self):return dict(state=self.state,message='Test status')

class PortalTests(AioHTTPTestCase):
    async def get_application(self):
        self.desktop=FakeDesktop()
        return server.create_app(desktop=self.desktop)

    async def test_entry_points_and_static_resources(self):
        for path,expected in [('/',b'Deschide aplica'),('/app',b'workspace.js'),('/logo.png',b'PNG'),('/nesting',b'<html'),('/static/style.css',b'--primary')]:
            response=await self.client.get(path)
            self.assertEqual(response.status,200,path)
            self.assertIn(expected,(await response.read()),path)

    async def test_start_requires_same_origin_and_client_header(self):
        response=await self.client.post('/api/start')
        self.assertEqual(response.status,403)
        response=await self.client.post('/api/start',headers={'Origin':'https://unrelated.example','X-FlowerMoon-Client':'portal'})
        self.assertEqual(response.status,403)
        origin=str(self.server.make_url('/')).rstrip('/')
        response=await self.client.post('/api/start',headers={'Origin':origin,'X-FlowerMoon-Client':'portal'})
        self.assertEqual(response.status,200)
        self.assertEqual(self.desktop.starts,2) # lifecycle plus button

    async def test_forwarded_origin(self):
        response=await self.client.post('/api/start',headers={'Origin':'https://example-8000.app.github.dev','X-Forwarded-Host':'example-8000.app.github.dev','X-FlowerMoon-Client':'portal'})
        self.assertEqual(response.status,200)

    async def test_failure_is_visible_and_not_cached(self):
        self.desktop.state='error'
        response=await self.client.get('/api/status')
        self.assertEqual((await response.json())['state'],'error')
        self.assertEqual(response.headers['Cache-Control'],'no-store')

    async def test_private_files_not_exposed(self):
        for path in ['/apps/transport/data/planning.json','/.git/config','/.runtime/portal.log','/server.py','/static/../server.py']:
            response=await self.client.get(path)
            self.assertEqual(response.status,404,path)

    async def test_socket_not_open_before_desktop_ready(self):
        origin=str(self.server.make_url('/')).rstrip('/')
        response=await self.client.get('/websockify',headers={'Origin':origin})
        self.assertEqual(response.status,503)

class DesktopTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_start_creates_one_worker(self):
        desktop=server.Desktop();calls=[];release=asyncio.Event()
        async def launch():calls.append(1);await release.wait()
        desktop.launch=launch
        await asyncio.gather(*(desktop.start() for _ in range(10)))
        await asyncio.sleep(0)
        self.assertEqual(len(calls),1)
        release.set();await desktop.task;await desktop.close()

    async def test_ready_requires_live_matching_heartbeat(self):
        with tempfile.TemporaryDirectory() as folder,patch.object(server,'APP',Path(folder)):
            (Path(folder)/'data').mkdir()
            target=Path(folder)/'data'/'hosted-status.json'
            desktop=server.Desktop()
            desktop.process=type('Process',(),{'pid':42,'returncode':None})()
            data=dict(pid=42,updatedAt=time.time(),visible=True,widgets=5)
            target.write_text(json.dumps(data));self.assertTrue(desktop.ready())
            for changes in [dict(pid=43),dict(updatedAt=time.time()-20),dict(visible=False),dict(widgets=0)]:
                target.write_text(json.dumps(dict(data,**changes)));self.assertFalse(desktop.ready())
            desktop.process.returncode=1;desktop.state='ready'
            self.assertEqual(desktop.status()['state'],'stopped')

if __name__=='__main__':unittest.main()
