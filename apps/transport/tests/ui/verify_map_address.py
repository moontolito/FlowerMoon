"""Real Tk map-click address enrichment and late-response safety."""
import tempfile,time,threading,json
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch
from planner_ui import Planner
from test_annual import ready,POINT
import site_conditions as sc

def pump(app,predicate):
    end=time.monotonic()+5
    while time.monotonic()<end:
        app.update();time.sleep(.02)
        if predicate():return
    raise AssertionError('Address lookup timeout')

with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);app.update()
    app.site['corrosivityEnabled']=True;app.site_location_ready=lambda:None
    errors=[];app.report_callback_exception=lambda *a:errors.append(a)
    response=dict(status='ready',label='10 Test Street, Sydney, Australia',source='Photon / OpenStreetMap',sourceUrl='https://github.com/komoot/photon',detail='Nearby mapped address')
    # Simulate an online map click while unrelated network providers remain off.
    with patch('places.reverse',return_value=response) as lookup:
        app.offline=False;app.pick(-33.859,151.21);app.offline=True
        selected=app.dest_coords.get();token=app.site_token;generation=app.generation
        app.site['deposition']=ready();before=deepcopy(app.site['deposition'])
        app.route_results=[{'name':'Existing route'}]
        app.route_context={'origin':{'name':'Departure'},'destination':{'name':'Point selected on map'}}
        pump(app,lambda:app.dest_name.get()==response['label'])
        self_record=app.site['destinationAddressLookup']
        assert lookup.call_count==1 and self_record['status']=='ready'
        assert app.dest_coords.get()==selected and app.site['destinationCoordinates']==selected
        assert app.site['deposition']==before and app.site_token==token and app.generation==generation
        assert app.route_results and app.route_context['destination']['name']==response['label']
        assert json.loads(app.state.path.read_text())['siteConditions']['destinationAddress']==response['label']
    app.route_context=None;app.route_results=[]
    with patch('places.reverse',return_value=dict(response,label='Departure street')):
        app.pick_mode.set('Departure');app.offline=False;app.pick(47.1,26.1);app.offline=True
        selected=app.origin_coords.get();pump(app,lambda:app.origin_name.get()=='Departure street')
        assert app.origin_coords.get()==selected and app.site['departureAddress']=='Departure street'
    # Two rapid clicks issue one lookup for the latest point.
    with patch('places.reverse',return_value=dict(response,label='Latest point')) as lookup:
        app.pick_mode.set('Destination');app.offline=False;app.pick(45.1,24.1);app.pick(46.1,25.1);app.offline=True
        pump(app,lambda:app.dest_name.get()=='Latest point');lookup.assert_called_once_with(46.1,25.1)
    # A late lookup must not overwrite a typed address or selected newer point.
    entered=threading.Event();release=threading.Event();finished=threading.Event()
    def slow(*args):entered.set();release.wait(3);finished.set();return response
    with patch('places.reverse',side_effect=slow):
        app.offline=False;app.pick(44.1,23.1);app.offline=True;pump(app,entered.is_set)
        app.select_address('destination',dict(label='User chosen address',lat=35.6,lon=139.7))
        release.set();pump(app,lambda:finished.is_set() and app.site_jobs.empty())
        assert app.dest_name.get()=='User chosen address' and app.dest_coords.get()=='35.6000000, 139.7000000'
    with patch('places.reverse',side_effect=ValueError('offline')):
        app.offline=False;app.pick(12,13);app.offline=True
        pump(app,lambda:app.site.get('destinationAddressLookup',{}).get('status')=='unavailable')
        assert app.dest_coords.get()=='12.0000000, 13.0000000'
    # Enrichment while a CAMS request is running must accept the same-point result.
    app.dest_name.set('Point selected on map');app.dest_coords.set('45.1,24.1')
    result=ready();release.clear();entered.clear()
    def cams_work(*args,**kwargs):entered.set();release.wait(3);return result
    with patch('cams.enabled',return_value=True),patch('annual_deposition.lookup',side_effect=cams_work):
        app.offline=False;app.refresh_deposition();assert entered.wait(1)
        app.apply_map_address('destination','Resolved name for same point');release.set()
        pump(app,lambda:not app.deposition_inflight)
        assert app.site['deposition']['status']=='ready'
    app.offline=True;app.close();assert not errors,errors
print('PASS: destination/departure addresses, exact coordinates, route/data preservation, debounce, stale results, failure, persistence and in-flight CAMS result')
