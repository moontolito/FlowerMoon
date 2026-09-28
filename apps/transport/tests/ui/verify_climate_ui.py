"""Climate completion, displayed provenance, persistence and stale-result guard."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from datetime import date
import time,threading,json
from planner_ui import Planner
import climate,site_conditions as sc
from test_climate import fixture,START,END

def pump(app,predicate):
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        app.update()
        if predicate():return
        time.sleep(.02)
    raise AssertionError('Climate completion timeout')

with TemporaryDirectory() as d:
    app=Planner(Path(d)/'state.json',offline=True);app.update();errors=[]
    app.report_callback_exception=lambda *e:errors.append(e)
    app.dest_name.set('Test A');app.dest_coords.set('44,28');window=app.open_site();app.offline=False
    result=climate.summarize(fixture(),START,END)
    with patch('humidity.lookup',side_effect=ValueError('offline fixture')),patch('climate.lookup',return_value=result):
        app.refresh_climate();pump(app,lambda:not app.climate_inflight)
        assert window.overview.item('design','values')[1:3]==('+15 / -9','°C')
        assert window.overview.item('daily','values')[3]=='Open-Meteo Historical / ERA5'
        assert json.loads(app.state.path.read_text(encoding='utf-8'))['siteConditions']['climate']['maximum']==15
    sc.apply_manual(app.site,{'temperature.maxDesign':50})
    started=threading.Event();release=threading.Event()
    def late(*args,**kwargs):started.set();release.wait(2);return result
    with patch('humidity.lookup',side_effect=ValueError('offline fixture')),patch('climate.lookup',side_effect=late):
        app.refresh_climate(force=True);assert started.wait(1)
        app.dest_name.set('Test B');app.dest_coords.set('45,25');release.set()
        pump(app,lambda:not app.climate_inflight)
    assert app.site['climate']['status']=='pending'
    assert sc.get(app.site,'temperature.maxDesign')['value']==50
    assert sc.get(app.site,'temperature.maxDesign')['reviewRequired']
    with patch('humidity.lookup',side_effect=ValueError('offline fixture')),patch('climate.lookup',side_effect=ValueError('test outage')):
        app.refresh_climate();pump(app,lambda:not app.climate_inflight)
    assert 'unavailable' in window.progress.cget('text')
    assert sc.get(app.site,'temperature.maxDailyAverage')['value'] is None
    app.offline=True;app.theme();app.open_site();app.update();app.close();assert not errors,errors
print('PASS: climate UI, auto-save, provenance, stale response, manual preservation, failure fallback, dark theme')
