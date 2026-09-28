"""Exercise destination changes, queued ADS work, screening and workbook output."""
import json,tempfile,time,threading
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from copy import deepcopy
from planner_ui import Planner
from test_annual import ready,POINT
import annual_deposition as deposition,site_conditions as sc

def pump(app,predicate):
    end=time.monotonic()+5
    while time.monotonic()<end:
        app.update();time.sleep(.02)
        if predicate():return
    raise AssertionError('Deposition UI timeout')

with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);app.update();app.site['corrosivityEnabled']=True;app.site_location_ready=lambda:None
    failures=[];app.report_callback_exception=lambda *args:failures.append(args)
    app.dest_name.set('Test destination');app.dest_coords.set('45.1,24.1')
    win=app.open_site();app.update();app.offline=False
    with patch('cams.enabled',return_value=True),patch('annual_deposition.lookup',return_value=dict(deposition.base(POINT),status='queued',message='CAMS deposition: 30-day request queued.')):
        app.refresh_deposition();pump(app,lambda:not app.deposition_inflight)
        assert app.deposition_timer
        assert '/12 months' in win.overview.item('deposition.dry','values')[1]
        assert sc.get(app.site,'environment.suggestedCorrosivity')['value'] is None
    with patch('cams.enabled',return_value=True),patch('annual_deposition.lookup',return_value=ready()):
        app.refresh_deposition();pump(app,lambda:not app.deposition_inflight)
        assert 'mg/m²/day' in win.overview.item('deposition.dry','values')[2]
        assert 'preliminary' in win.overview.item('environment.suggestedCorrosivity','values')[1]
        assert win.overview.item('environment.suggestedCorrosivity','values')[3]=='ISO 9223:2012 + Copernicus CAMS'
        assert 'DEM' not in win.overview_sources['environment.suggestedCorrosivity']
        assert 'not a certified ISO' in win.overview_sources['environment.suggestedCorrosivity']
        assert len(win.book.tabs())==1
        assert json.loads(app.state.path.read_text())['siteConditions']['corrosionAssessment']['category']
        assert sc.get(app.site,'environment.exteriorCorrosivity')['value']=='Manual / Unknown'
    from excel_export import export_workbook
    delivery=dict(product=deepcopy(app.state.data['product']),vehicle=deepcopy(app.active['vehicle']),loaded=deepcopy(app.active['loaded']),
                  origin=dict(name='Departure',lat=47,lon=26),destination=dict(name='Test destination',**POINT),server='fixture',calculated_at='2026-09-27',
                  quantity=1,return_km=0,position_km=0,notes='',distance_km=100,hours=2,siteConditions=deepcopy(app.site))
    output=Path(folder)/'export.xlsx';export_workbook(output,[delivery],dict(loaded=1,empty=0,fixed=0,markup=0,vat=0))
    with ZipFile(output) as z:
        xml=z.read('xl/worksheets/sheet3.xml').decode()
        assert 'Indicative exterior category' in xml and 'preliminary' in xml and 'not a certified ISO' in xml
        assert 'CAMS forecasts / ADS' in xml and 'Chloride' in xml
    queued=dict(deposition.base(POINT),status='queued',completedMonths=3)
    with patch('cams.enabled',return_value=True),patch('annual_deposition.lookup',return_value=queued):
        app.refresh_deposition(force=True);pump(app,lambda:not app.deposition_inflight)
        assert app.deposition_timer
        app.dest_name.set('New destination');app.dest_coords.set('35,139')
        assert app.deposition_timer is None
        assert app.site['deposition']['status']=='pending'
        assert sc.get(app.site,'environment.suggestedCorrosivity')['value'] is None
    started=threading.Event();release=threading.Event()
    def delayed(*args,**kwargs):started.set();release.wait(3);return ready(dict(lat=35,lon=139))
    with patch('cams.enabled',return_value=True),patch('annual_deposition.lookup',side_effect=delayed):
        app.refresh_deposition();assert started.wait(1)
        app.dest_name.set('Sydney');app.dest_coords.set('-33.9,151.2');release.set()
        pump(app,lambda:not app.deposition_inflight)
        assert app.site['deposition']['status']=='pending'
        assert sc.get(app.site,'environment.suggestedCorrosivity')['value'] is None
    app.offline=True;app.close();assert not failures,failures
print('PASS: 30-day deposition queue, screening provenance, final-class preservation, Excel, destination reset, timer cancellation and stale replies')
