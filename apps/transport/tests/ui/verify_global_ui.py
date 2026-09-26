"""Destination-only workflow remains usable even without a connected road route."""
import tempfile,time,json,sys
from pathlib import Path
from unittest.mock import patch
from planner_ui import Planner
import climate,site_sources,site_conditions as sc
from site_environment import service,standards,geography
from test_climate import fixture,START,END

with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);app.update();errors=[]
    app.report_callback_exception=lambda *args:errors.append(args)
    def source(server,destination,geometry=None):
        return dict(locationContext=service.context(destination),coastalDistance=geography.coast(destination),zoning=standards.lookup(destination))
    result=climate.summarize(fixture(),START,END)
    app.offline=False
    # Route failure must not require a dismissible dialog to obtain site data.
    with patch('humidity.lookup',side_effect=ValueError('offline fixture')),patch('climate.lookup',return_value=result),patch('site_sources.lookup',side_effect=source),patch('routing.route',side_effect=ValueError('No connected road route')),patch('planner_ui.messagebox.showerror',side_effect=AssertionError('Automatic route failure must not block the site workflow')):
        app.dest_name.set('Tokyo, Japan');app.dest_coords.set('35.6762,139.6503')
        deadline=time.monotonic()+9
        while time.monotonic()<deadline:
            app.update();time.sleep(.03)
            if app.site.get('climate',{}).get('status')=='ready' and 'coastalDistance' in app.site and not app.busy:break
        win=app.open_site();app.update()
        assert app.site['locationContext']['geography']['code']=='JP'
        assert sc.get(app.site,'temperature.maxDesign')['value']==15
        assert not app.route_context
        assert app.site['routeLookup']['status']=='unavailable'
        assert sc.get(app.site,'seismic.ag')['value'] is None
        assert 'P100' not in win.overview.item('seismic.ag','values')[0]
        assert win.overview.item('seismic.ag','values')[2]=='No source for this region'
        assert win.overview.item('country','values')[1]=='Japan'
        assert 'Japan' in win.structural_context.cget('text')
        assert 'coastalDistance' in json.loads(app.state.path.read_text(encoding='utf-8'))['siteConditions']
        app.offline=True
        if '--capture' in sys.argv:
            from PIL import ImageGrab
            for mode in ('light','dark'):
                if app.mode!=mode:app.theme();win=app.open_site()
                win.geometry('1120x820+30+30');win.attributes('-topmost',True)
                win.overview.see('country')
                for _ in range(10):app.update();time.sleep(.1)
                ImageGrab.grab(bbox=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())).save('global-'+mode+'.png')
    app.close();assert not errors,errors
print('PASS: automatic Japanese site/climate without road route, no RO code labels, persistence')
