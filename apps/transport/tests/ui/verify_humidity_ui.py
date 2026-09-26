import tempfile,time,threading,json,sys
from pathlib import Path
from unittest.mock import patch
from planner_ui import Planner
import humidity,site_conditions as sc,zoning
from test_humidity import fixture,START,END
from site_environment import service

def pump(app,predicate):
    deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        app.update();time.sleep(.02)
        if predicate():return
    raise AssertionError('Humidity completion timeout')

with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);app.update();errors=[]
    # This script isolates humidity callbacks; the destination scheduler is
    # exercised separately by verify_automatic_site.py.
    app.site_location_ready=lambda:None
    app.report_callback_exception=lambda *args:errors.append(args)
    app.dest_name.set('Constanța — verificare UI');app.dest_coords.set('44.18,28.63')
    win=app.open_site();app.offline=False
    result=humidity.summarize(fixture(),START,END)
    with patch('humidity.lookup',return_value=result):
        app.refresh_humidity();pump(app,lambda:not app.humidity_inflight)
    assert win.overview.item('humidity.maximum','values')[1]=='90 %'
    assert 'De verificat' in win.overview.item('humidity.maximum','values')[3]
    assert json.loads(app.state.path.read_text(encoding='utf-8'))['siteConditions']['humidity']['mean']['value']==200/3
    win.vars['humidity.mean'].set('55');assert win.save()
    with patch('humidity.lookup',return_value=result):
        app.refresh_humidity(force=True);pump(app,lambda:not app.humidity_inflight)
    assert sc.get(app.site,'humidity.mean')['value']==55
    started=threading.Event();release=threading.Event()
    def late(*args,**kwargs):started.set();release.wait(2);return result
    with patch('humidity.lookup',side_effect=late):
        app.refresh_humidity(force=True);assert started.wait(1)
        app.dest_name.set('Tokyo');app.dest_coords.set('35.68,139.69');release.set();pump(app,lambda:not app.humidity_inflight)
    assert app.site['humidityAnalysis']['status']=='pending'
    assert sc.get(app.site,'humidity.maximum')['value'] is None
    assert sc.get(app.site,'humidity.mean')['reviewRequired']
    with patch('humidity.lookup',side_effect=ValueError('offline fixture')):
        app.refresh_humidity();pump(app,lambda:not app.humidity_inflight)
    assert app.site['humidityAnalysis']['status']=='unavailable'
    app.offline=True
    if '--capture' in sys.argv:
        from PIL import ImageGrab
        app.dest_name.set('Constanța — verificare UI');app.dest_coords.set('44.18,28.63')
        if app.site_timer:app.after_cancel(app.site_timer);app.site_timer=None
        sc.get(app.site,'humidity.mean')['manualOverride']=False
        sc.automatic(app.site,'environment.siteAltitudeM',1200,'UI fixture altitude','VERIFY')
        real=json.loads((Path(__file__).resolve().parents[1]/'fixtures'/'source-live-report.json').read_text(encoding='utf-8'))[0]['humidity'];humidity.apply(app.site,real)
        sc.apply_zoning(app.site,zoning.lookup(dict(lat=44.18,lon=28.63),1200))
        service.apply_context(app.site,service.context(dict(lat=44.18,lon=28.63)))
        for mode,anchor in [('light','humidity.minimum'),('dark','wind.qb')]:
            if app.mode!=mode:app.theme();win=app.open_site()
            win.refresh();win.geometry('1250x850+20+20');win.attributes('-topmost',True)
            app.update();win.overview.see(anchor)
            for _ in range(10):app.update();time.sleep(.1)
            ImageGrab.grab(bbox=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())).save('humidity-'+mode+'.png')
    app.close();assert not errors,errors
print('PASS: humidity auto-load, observations, save/manual preservation, stale response rejection and failure state')
