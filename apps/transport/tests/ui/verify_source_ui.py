"""UI provenance from real downloaded samples, isolated from saved projects."""
import json,tempfile,time
from pathlib import Path
from planner_ui import Planner
import climate,humidity,site_conditions as sc
from site_environment import service,standards

record=json.loads((Path(__file__).resolve().parents[1]/'fixtures'/'source-live-report.json').read_text(encoding='utf-8'))[0]
with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);app.update()
    app.dest_name.set('Constanța');app.dest_coords.set('44.18,28.63')
    if app.site_timer:app.after_cancel(app.site_timer);app.site_timer=None
    climate.apply(app.site,record['temperature']);humidity.apply(app.site,record['humidity'])
    sc.automatic(app.site,'environment.siteAltitudeM',record['elevation']['values'][0],record['elevation']['source'],'VERIFY')
    app.site['elevationAnalysis']=record['elevation']
    service.apply_context(app.site,service.context(record['coordinates']))
    sc.apply_zoning(app.site,standards.lookup(record['coordinates'],record['elevation']['values'][0]))
    win=app.open_site();win.geometry('1260x870+20+20');app.update()
    assert 'Open-Meteo' in win.overview_sources['humidity.summary']
    assert 'Copernicus' in win.overview_sources['environment.siteAltitudeM']
    humidity_values=win.overview.item('humidity.summary','values')[1].removesuffix(' %').split(' / ')
    assert humidity_values[0]=='100' and humidity_values[2]=='30'
    assert len(humidity_values)==3
    assert 'NASA' not in win.progress.cget('text')
    win.sources();app.update()
    for child in win.winfo_children():
        if child.winfo_class()=='Toplevel':child.destroy()
    import sys
    if '--capture' in sys.argv:
        from PIL import ImageGrab
        for mode in ('light','dark'):
            if app.mode!=mode:app.theme();win=app.open_site();win.geometry('1260x870+20+20')
            win.attributes('-topmost',True);win.overview.see('humidity.summary')
            for _ in range(5):app.update();time.sleep(.15)
            ImageGrab.grab(bbox=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())).save('sources-'+mode+'.png')
    app.close()
print('PASS: actual Open-Meteo and GLO-90 provenance displayed, hourly RH labels, Sources dialog')
