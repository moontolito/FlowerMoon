"""Real local raster + native widgets, saved-state and export; no network."""
import tempfile,time,ctypes,json,os
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
from planner_ui import Planner
from domain import evaluate
from excel_export import export_workbook
from PIL import ImageGrab
import gem_hazard

out=Path(os.environ.get('FLOWERMOON_UI_ARTIFACTS','artifacts'));out.mkdir(parents=True,exist_ok=True)
def capture(win,name):
    win.update()
    ImageGrab.grab(window=ctypes.windll.user32.GetAncestor(win.winfo_id(),2)).save(out/name)

with tempfile.TemporaryDirectory() as folder,patch('urllib.request.urlopen',side_effect=AssertionError('No network allowed')):
    app=Planner(Path(folder)/'state.json',offline=True);app.update();errors=[]
    app.report_callback_exception=lambda kind,value,tb:errors.append((kind.__name__,str(value)))
    app.site_location_ready=lambda:None
    app.dest_name.set('Bucharest, Romania');app.dest_coords.set('44.4268,26.1025');app.update()
    assert abs(app.site['seismicHazard']['value']-.3229623135362622)<1e-12
    win=app.open_site();app.update()
    values=win.overview.item('seismic.pga','values')
    assert values[1:3]==('0.323','g'),values
    assert values[3]=='GEM · Hazard Map 2023.1'
    assert win.overview.item('seismic.interpretation','values')[1]=='Very high'
    assert not win.overview.exists('seismic.hazardReference')
    assert win.overview_meanings['seismic.pga']==gem_hazard.PGA_MEANING
    assert win.overview.exists('seismic.ag') and win.overview.exists('seismic.tc')
    dialog=win.value_details('seismic.pga');app.update()
    text=dialog.area.get('1.0','end')
    for phrase in ['475','Vs30','Cell centre','SHA-256','CC BY-NC-SA','not an on-site measurement']:
        assert phrase in text,phrase
    dialog.destroy();win.geometry('1320x800+20+20');app.update()
    win.overview.see('seismic.interpretation');win.overview.selection_set('seismic.pga');app.update()
    capture(win,'gem-overview.png');win.destroy();app.site_window=None
    app.hazard_visible=True;app.build();app.update()
    app.map.lat=46;app.map.lon=20;app.map.zoom=5;app.map.draw();app.update()
    assert app.map.find_withtag('seismic-hazard')
    assert app.map.find_withtag('seismic-legend')
    assert not app.map.hazard_error
    legend_text=' '.join(str(app.map.itemcget(item,'text')) for item in app.map.find_all() if app.map.type(item)=='text')
    assert all(name in legend_text for name in gem_hazard.PGA_LEVELS)
    capture(app,'gem-map.png')
    app.geometry('1000x700');app.update();app.map.draw();app.update()
    assert app.map.find_withtag('seismic-hazard')
    capture(app,'gem-map-compact.png')
    app.map.set_hazard(False);app.map.draw();assert not app.map.find_withtag('seismic-hazard')
    app.theme();app.update();assert app.map.hazard_visible
    app.map.draw();capture(app,'gem-map-dark.png')
    # Export reads the saved snapshot instead of querying an external service.
    row=dict(product=app.state.data['product'],vehicle=app.active['vehicle'],loaded=app.active['loaded'],quantity=1,
             distance_km=100,return_km=0,position_km=0,hours=2,origin=dict(name='A',lat=47,lon=26),
             destination=dict(name='Bucharest',lat=44.4268,lon=26.1025),server=app.state.data['server'],
             calculated_at='2026-09-27',siteConditions=app.site)
    export_workbook(out/'gem-export.xlsx',[row],dict(loaded=1,empty=0,fixed=0,markup=0,vat=0))
    with ZipFile(out/'gem-export.xlsx') as z:
        exported=z.read('xl/worksheets/sheet3.xml').decode()
        assert '0.323 g' in exported and '475' in exported and 'SHA-256' in exported
        assert 'Very high' in exported and gem_hazard.PGA_MEANING in exported
        assert 'PGA hazard reference' not in exported
    app.state.save()
    saved=json.loads(app.state.path.read_text(encoding='utf-8'))
    assert saved['siteConditions']['seismicHazard']['value']==app.site['seismicHazard']['value']
    app.dest_name.set('Pacific Ocean');app.dest_coords.set('0,-140');app.update()
    assert app.site['seismicHazard']['status']=='no_data'
    win=app.open_site();app.update();assert win.overview.item('seismic.pga','values')[1]=='Not available'
    assert win.overview.item('seismic.interpretation','values')[1]=='Not available'
    app.dest_name.set('London');app.dest_coords.set('51.5074,-0.1278');app.update()
    assert .008<app.site['seismicHazard']['value']<.009
    assert win.overview.item('seismic.pga','values')[1]=='0.008'
    assert win.overview.item('seismic.interpretation','values')[1]=='Very low'
    app.dest_name.set('Not selected');app.update();assert 'seismicHazard' not in app.site
    assert win.overview.item('seismic.pga','values')[1]=='Not available'
    app.close();assert not errors,errors
print('PASS: local PGA, destination updates, NoData, original national parameters, source details, light/dark layer, compact layout, state and Excel. No network.')
