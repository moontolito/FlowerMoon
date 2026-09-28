"""New workflow: suggestions, destination sources, boundary clearing, direct export."""
import json,tempfile,time,os,sys
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile
import xml.etree.ElementTree as ET
from planner_ui import Planner
from address_entry import AddressEntry
import climate,humidity,site_conditions as sc

def walk(widget):
    for child in widget.winfo_children():
        yield child;yield from walk(child)

def pump(app,predicate):
    until=time.monotonic()+4
    while time.monotonic()<until:
        app.update();time.sleep(.02)
        if predicate():return
    raise AssertionError('UI operation did not complete')

with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);app.update();errors=[]
    app.report_callback_exception=lambda *args:errors.append(args)
    app.site_location_ready=lambda:None
    entries=[w for w in walk(app) if isinstance(w,AddressEntry)]
    assert len(entries)==2
    suggestion=dict(label='Constanta, Romania',lat=44.18,lon=28.63,source='Photon / OpenStreetMap')
    destination=entries[1];destination.online=True
    with patch('places.search',return_value=[suggestion]):
        destination.entry.focus_force();app.dest_name.set('Constanta');destination.typed();pump(app,lambda:bool(destination.rows))
        destination.focus_list();destination.choose();app.update()
    assert app.dest_coords.get()=='44.1800000, 28.6300000'
    destination.results.put((destination.token-1,'Old address',[dict(suggestion,label='Wrong')],None))
    pump(app,lambda:destination.results.empty());assert not destination.rows
    record=json.loads((Path(__file__).resolve().parents[1]/'fixtures'/'source-live-report.json').read_text(encoding='utf-8'))[0]
    climate.apply(app.site,record['temperature']);humidity.apply(app.site,record['humidity'])
    sc.automatic(app.site,'environment.siteAltitudeM',24,'Copernicus DEM GLO-90','VERIFY')
    boundary=dict(status='ready',name='Boundary test fixture',source='geoBoundaries gbOpen',geometry=dict(type='Polygon',coordinates=[[[28.5,44.0],[28.8,44.0],[28.8,44.3],[28.5,44.3],[28.5,44.0]]]))
    app.site['administrativeRegion']=boundary;app.map.set_region(boundary);app.map.draw()
    assert app.map.find_withtag('delivery-region')
    win=app.open_site();app.update()
    assert tuple(win.overview['columns'])==('field','value','unit','source','meaning','status')
    assert win.overview.item('humidity.summary','values')[3]=='Open-Meteo Historical / ERA5'
    assert 'destination' in win.overview.item('humidity.summary','values')[4]
    assert '44.1800000, 28.6300000' in win.summary.cget('text')
    assert win.overview.item('environment.siteAltitudeM','values')[3]=='Copernicus DEM GLO-90 (2021)'
    assert win.overview.item('environment.siteAltitudeM','values')[1:3]==('24','m')
    artifacts=Path(os.environ.get('FLOWERMOON_UI_ARTIFACTS',str(Path(tempfile.gettempdir())/'flowermoon-test-evidence')));artifacts.mkdir(parents=True,exist_ok=True)
    if os.environ.get('CI') or '--capture' in sys.argv:
        from PIL import ImageGrab
        win.geometry('1260x870+20+20');win.attributes('-topmost',True);app.update()
        ImageGrab.grab(bbox=(win.winfo_rootx(),win.winfo_rooty(),win.winfo_rootx()+win.winfo_width(),win.winfo_rooty()+win.winfo_height())).save(artifacts/'site-environment-english.png')
    win.destroy()
    app.route_context=dict(product=deepcopy(app.state.data['product']),vehicle=deepcopy(app.active['vehicle']),loaded=deepcopy(app.active['loaded']),origin=dict(name='Departure',lat=47.85,lon=26.75),destination=dict(name=suggestion['label'],lat=44.18,lon=28.63),server='https://valhalla.example',calculated_at='2026-09-26T00:00:00Z')
    app.route_results=[dict(name='Option 1',distance_km=435,hours=8,geometry=dict(type='LineString',coordinates=[[26.75,47.85],[28.63,44.18]]))]
    app.route_tree.insert('','end',iid='0',values=('Option 1',435,8));app.route_tree.selection_set('0');app.update()
    form=app.export_transport();app.update()
    form.vars['loaded'].set('2');form.vars['return_km'].set('0');form.vars['fixed'].set('0');form.vars['markup'].set('0');form.vars['vat'].set('0')
    exported=Path(folder)/'transport.xlsx'
    with patch('transport_export.filedialog.asksaveasfilename',return_value=str(exported)):form.submit()
    assert exported.exists();assert len(app.state.data['deliveries'])==0
    ns={'x':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(exported) as z:
        workbook=ET.fromstring(z.read('xl/workbook.xml'));assert [s.attrib['name'] for s in workbook.find('x:sheets',ns)]==['Transport','Routes','Site & Environment']
        site=z.read('xl/worksheets/sheet3.xml').decode();assert 'Constanta, Romania' in site and 'Open-Meteo Historical / ERA5' in site and '44.1800000' in site
        assert 'Humidity · Max / Mean / Min' in site and 'Delivery terms' not in site
        assert 'Maximum hourly relative humidity</t>' not in site
        calc=ET.fromstring(z.read('xl/worksheets/sheet1.xml'));assert float(calc.find('.//x:c[@r="L13"]/x:v',ns).text)==870
        assert 'Rute!' not in z.read('xl/worksheets/sheet1.xml').decode()
    app.dest_name.set('Other city');app.update();assert app.map.region is None and 'administrativeRegion' not in app.site
    destination.online=False;app.close();assert not errors,errors
print('PASS: autocomplete selection/stale results, destination sources, region overlay/clearing and direct Excel with site provenance')
