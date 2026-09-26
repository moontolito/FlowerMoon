"""One destination action fills the project sheet without field selections."""
import tempfile,time,threading,json
from pathlib import Path
from unittest.mock import patch
from planner_ui import Planner
import site_conditions as sc
from site_environment import standards as zoning

def pump(app,predicate,seconds=6):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        app.update()
        if predicate():return
        time.sleep(.03)
    raise AssertionError('Timed out waiting for automatic results')

with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'state.json';app=Planner(path,offline=True);app.update();errors=[]
    app.report_callback_exception=lambda *args:errors.append(args)
    def source(server,destination,geometry=None):
        return dict(siteAltitude=80,altitude=(950 if geometry else 80,'Test route maximum' if geometry else 'Test destination'),marine=('Unknown','No mapped coastline'),zoning=zoning.lookup(destination,80))
    response=[dict(name='Automatic',distance_km=435,hours=8,geometry={'type':'LineString','coordinates':[[26.75,47.85],[26.10,44.42]]})]
    app.offline=False
    with patch('humidity.lookup',side_effect=ValueError('offline fixture')),patch('climate.lookup',side_effect=ValueError('offline fixture')),patch('site_sources.lookup',side_effect=source),patch('routing.route',return_value=response) as route,patch('planner_ui.messagebox.askyesno',side_effect=AssertionError('Unexpected confirmation')):
        app.dest_name.set('Bucuresti');app.dest_coords.set('44.4268,26.1025')
        pump(app,lambda:sc.get(app.site,'transport.maxAltitudeM')['value']==950)
        assert not app.accept.get(),'Preliminary route must not approve vehicle'
        assert sc.get(app.site,'transport.distanceKm')['value']==435
        assert sc.get(app.site,'seismic.ag')['value']==.3
        assert sc.get(app.site,'seismic.tc')['value']==1.6
        assert sc.get(app.site,'snow.sk')['value']==2
        assert sc.get(app.site,'wind.qb')['value']==.5
        assert app.site_window.winfo_exists()
        assert 'humidity.maximum' in app.site_window.overview.get_children()
        assert 'section_structural' in app.site_window.overview.get_children()
        assert route.call_count==1
        assert json.loads(path.read_text(encoding='utf-8'))['siteConditions']['seismic']['ag']['value']==.3
        sc.apply_manual(app.site,{'wind.qb':.9})
        # Inland checkpoint: the previous port-edge point falls outside the
        # generalized country polygon and now correctly yields unknown country.
        app.dest_name.set('Constanta');app.dest_coords.set('44.18,28.63')
        pump(app,lambda:sc.get(app.site,'seismic.ag')['value']==.2 and sc.get(app.site,'transport.maxAltitudeM')['value']==950)
        assert sc.get(app.site,'wind.qb')['value']==.9 and sc.get(app.site,'wind.qb')['reviewRequired']
        assert sc.get(app.site,'snow.sk')['value']==1.5
        # A late result for the old destination must not overwrite new data.
        app.site_cache.clear();started=threading.Event();release=threading.Event()
        def late(*args):started.set();release.wait(3);return dict(altitude=(1234,'old destination'))
        with patch('site_sources.lookup',side_effect=late):
            app.refresh_site_sources(force=True);assert started.wait(1)
            app.dest_name.set('New destination');release.set()
            pump(app,lambda:not app.site_inflight)
            app.update();assert sc.get(app.site,'transport.maxAltitudeM')['value'] is None
        app.offline=True
    app.close();assert not errors,errors
print('PASS: destination-only trigger, no confirmation, automatic route and zoning, overview, auto-save, overrides, stale response')
