"""CAMS worker integration, automatic queue refresh, stale results and exports."""
import json,tempfile,time,threading
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from planner_ui import Planner
from site_overview import rows
import cams,site_conditions as sc
from test_cams import fixture,POINT

def pump(app,predicate):
    until=time.monotonic()+5
    while time.monotonic()<until:
        app.update();time.sleep(.02)
        if predicate():return
    raise AssertionError('CAMS UI update timed out')

with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);app.update()
    app.site['corrosivityEnabled']=True;app.site_location_ready=lambda:None
    errors=[];app.report_callback_exception=lambda *args:errors.append(args)
    app.dest_name.set('Constanta, Romania');app.dest_coords.set('44.18,28.63');win=app.open_site();app.update()
    result=cams.parse_download(fixture(Path(folder)/'fixture.nc'),POINT)
    result.update(cams.base_result(cams.request_for(POINT)));result['status']='ready';result=cams.for_point(result,POINT)
    app.offline=False
    with patch('cams.enabled',return_value=True),patch('cams.lookup',return_value=dict(cams.base_result(cams.request_for(POINT)),status='queued')):
        app.refresh_air_quality();pump(app,lambda:not app.cams_inflight)
        assert app.cams_timer and 'Loading' in win.overview.item('airQuality.so2','values')[1]
    with patch('cams.enabled',return_value=True),patch('cams.lookup',return_value=result):
        app.refresh_air_quality();pump(app,lambda:not app.cams_inflight)
        assert 'µg/kg' in win.overview.item('airQuality.so2','values')[2]
        assert win.overview.item('airQuality.so2','values')[3]==cams.SOURCE
        assert len(win.book.tabs())==1
        assert json.loads(app.state.path.read_text(encoding='utf-8'))['siteConditions']['airQuality']['status']=='ready'
    from excel_export import export_workbook
    from copy import deepcopy
    delivery=dict(product=deepcopy(app.state.data['product']),vehicle=deepcopy(app.active['vehicle']),loaded=deepcopy(app.active['loaded']),
                  origin=dict(name='Departure',lat=47,lon=26),destination=dict(name='Constanta',**POINT),server='fixture',calculated_at='2026-09-27',
                  quantity=1,return_km=0,position_km=0,notes='',distance_km=100,hours=2,siteConditions=deepcopy(app.site))
    target=Path(folder)/'export.xlsx';export_workbook(target,[delivery],dict(loaded=1,empty=0,fixed=0,markup=0,vat=0))
    with ZipFile(target) as z:
        text=z.read('xl/worksheets/sheet3.xml').decode()
        assert 'SO₂' in text and cams.SOURCE in text and 'µg/kg' in text and '44.25' in text
    with patch('cams.enabled',return_value=True),patch('cams.lookup',side_effect=cams.CamsError('licence','Accept the CAMS EAC4 monthly dataset licence.')):
        app.refresh_air_quality(force=True);pump(app,lambda:not app.cams_inflight)
        assert win.overview.item('airQuality.so2','values')[1]=='Licence required'
    started=threading.Event();release=threading.Event()
    def delayed(*args,**kwargs):started.set();release.wait(3);return result
    with patch('cams.enabled',return_value=True),patch('cams.lookup',side_effect=delayed):
        app.refresh_air_quality(force=True);assert started.wait(1)
        app.dest_name.set('Tokyo');app.dest_coords.set('35.6,139.7');release.set()
        pump(app,lambda:not app.cams_inflight)
        assert app.site['airQuality']['status']=='pending'
        assert win.overview.item('airQuality.so2','values')[1]=='Not available'
    app.offline=True;app.close();assert not errors,errors
print('PASS: CAMS background queue, successful values/provenance, Excel export, licence state, destination reset and stale-result rejection')
