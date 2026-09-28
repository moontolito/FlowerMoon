import tempfile,time,threading
from pathlib import Path
from unittest.mock import patch
from planner_ui import Planner
import annual_deposition as deposition
from site_overview import rows
from value_details import build,plain_text

def pump(app,predicate):
    end=time.monotonic()+5
    while time.monotonic()<end:
        app.update();time.sleep(.02)
        if predicate():return
    raise AssertionError('UI progress timeout')

with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);app.update()
    app.site['corrosivityEnabled']=True;app.site_location_ready=lambda:None
    app.dest_name.set('Progress QA');app.dest_coords.set('45.1,24.1');win=app.open_site();app.update()
    point=dict(lat=45.1,lon=24.1)
    result=dict(deposition.base(point),status='running',completedMonths=0,message='CAMS archive: 0/12 months verified; 2 processing at ADS.',jobs=[dict(month=1,requestId='qa-existing-job',status='running',submittedAt='2026-09-27T09:00:00+00:00',checkedAt='2026-09-27T10:00:00+00:00')])
    app.site['deposition']=result;win.refresh();app.update()
    assert 'ADS processing' in win.overview.item('deposition.dry','values')[1]
    doc=build(app.site,'deposition.dry');assert 'qa-existing-job' in plain_text(doc)
    assert any(url.endswith('/requests') for _,url in doc['links'])
    started=threading.Event();release=threading.Event()
    def pending(*args,**kwargs):started.set();release.wait(3);return result
    app.offline=False
    with patch('cams.enabled',return_value=True),patch('annual_deposition.lookup',side_effect=pending):
        app.refresh_deposition();assert started.wait(1);app.update()
        assert 'ADS processing' in win.overview.item('deposition.dry','values')[1]
        release.set();pump(app,lambda:not app.deposition_inflight)
        assert app.deposition_timer
    error=dict(deposition.base(point),status='unavailable',retryable=True,retryAfterSeconds=120,message='Retry pending',completedMonths=0)
    with patch('cams.enabled',return_value=True),patch('annual_deposition.lookup',return_value=error):
        app.refresh_deposition();pump(app,lambda:not app.deposition_inflight)
        assert app.deposition_timer;assert 'retry' in win.overview.item('deposition.dry','values')[1]
    with patch('cams.enabled',return_value=True),patch('annual_deposition.lookup',return_value=result) as lookup:
        app.refresh_deposition();pump(app,lambda:not app.deposition_inflight)
        lookup.assert_called_once();assert app.site['deposition']['status']=='running'
    app.offline=True;app.close()
print('PASS: real ADS state, request IDs/links, no loading flicker, retry scheduling and recovery')
