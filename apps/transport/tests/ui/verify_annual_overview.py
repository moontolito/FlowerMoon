"""Native UI and opt-in job lifecycle; provider calls are mocked, never submitted."""
import os,tempfile,json
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from planner_ui import Planner
from test_annual import ready,POINT
import site_conditions as sc
from site_overview import CORROSIVITY_GROUP as GROUP
from PIL import ImageGrab

out=Path(os.environ.get('FLOWERMOON_UI_ARTIFACTS','artifacts'));out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);app.update()
    app.site_location_ready=lambda:None
    app.dest_name.set('Annual assessment UI test, Romania');app.dest_coords.set('45.1,24.1')
    win=app.open_site();app.update()
    errors=[];app.report_callback_exception=lambda kind,value,tb:errors.append((kind.__name__,str(value)))
    assert not hasattr(win,'metrics') and len(win.book.tabs())==1
    assert win.overview['columns']==('field','value','unit','source','meaning','status')
    assert win.overview.item(GROUP,'values')[1].startswith('Disabled')
    assert not win.overview.get_children(GROUP)
    assert win.overview.get_children('seismic.national')
    win.toggle_group('seismic.national');app.update()
    assert win.overview.item('seismic.national','open')
    dialog=win.value_details('seismic.pga');app.update()
    assert 'GEM Global Seismic Hazard Map 2023.1' in dialog.area.get('1.0','end');dialog.destroy()
    settings=app.settings();app.update()
    assert not settings.vars['corrosivityEnabled'].get()
    assert 'Application settings'==settings.title();settings.destroy()
    # Even with online access allowed, disabled corrosivity submits no ADS jobs.
    app.offline=False
    with patch('cams.enabled',return_value=True),patch('cams.lookup') as air,patch('annual_deposition.lookup') as dep,patch('app.threading.Thread') as thread:
        app.refresh_air_quality(force=True);app.refresh_deposition(force=True)
        air.assert_not_called();dep.assert_not_called();thread.assert_not_called()
    # Enabling creates exactly the two provider workers. Disable rejects their
    # queued result callbacks and cancels their subsequent polling.
    def launch(target,**kwargs):return SimpleNamespace(start=target)
    with patch('cams.enabled',return_value=True),patch('cams.lookup',return_value={'status':'queued'}) as air,patch('annual_deposition.lookup',return_value={'status':'queued'}) as dep,patch('app.threading.Thread',side_effect=launch):
        app.set_corrosivity_enabled(True)
        assert air.call_count==1 and dep.call_count==1
        app.set_corrosivity_enabled(False)
        while not app.site_jobs.empty():
            done,result,_=app.site_jobs.get_nowait();done(result)
        assert app.cams_timer is None and app.deposition_timer is None
        assert app.site['corrosionAssessment']['status']=='disabled'
        assert not json.loads(app.state.path.read_text())['siteConditions']['corrosivityEnabled']
    app.offline=True
    app.set_corrosivity_enabled(True)
    app.site['deposition']=ready();sc.recommendation(app.site);win.refresh();app.update()
    assert 'annual estimate' in win.overview.item(GROUP,'values')[1]
    win.toggle_group(GROUP);app.update();assert win.overview.get_children(GROUP)
    win.refresh();app.update();assert win.overview.item(GROUP,'open')
    dialog=win.value_details(GROUP);app.update()
    text=dialog.area.get('1.0','end')
    assert '2920 or 2928' in text and '30-day CAMS' not in text and 'first-year loss' in text
    assert 'SO₂ term' in text;dialog.destroy()
    for mode in ('light','dark'):
        if app.mode!=mode:app.theme();win=app.open_site();app.update()
        for width,height in [(1320,800),(1080,650)]:
            win.geometry(f'{width}x{height}+20+20');win.attributes('-topmost',True);win.update()
            if win.overview.winfo_height()<=230:
                ImageGrab.grab(bbox=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())).save(out/'small-layout.png')
            assert win.overview.winfo_height()>180,(mode,width,height,win.overview.winfo_height())
            assert win.value_button.winfo_ismapped()
        win.geometry('1320x800+20+20');win.update()
        win.overview.yview_moveto(0);app.update()
        ImageGrab.grab(bbox=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())).save(out/f'annual-overview-{mode}.png')
    app.close();assert not errors,errors
print('PASS: annual opt-in lifecycle, settings, disclosure, details, export metadata, light/dark layouts')
