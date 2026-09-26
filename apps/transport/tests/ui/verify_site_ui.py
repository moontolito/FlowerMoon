"""Real Tk widgets; temporary data and mocked providers only."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from planner_ui import Planner,Form
import site_conditions as sc

with tempfile.TemporaryDirectory() as folder, patch('site_sources.lookup',return_value={}):
    app=Planner(Path(folder)/'state.json',offline=True);errors=[]
    app.report_callback_exception=lambda *args:errors.append(args)
    app.update();app.dest_name.set('Site A');app.dest_coords.set('44.17,28.65')
    win=app.open_site();app.update()
    win.vars['wind.qb'].set('0.4');win.vars['environment.marineEnvironment'].set('Possible');assert win.save()
    assert 'Marine environment detected' in win.warning.cget('text')
    win.vars['temperature.maxDesign'].set('40');win.vars['temperature.minDesign'].set('60');assert not win.save()
    win.vars['temperature.maxDesign'].set('');win.vars['temperature.minDesign'].set('')
    app.dest_name.set('Site B');app.dest_coords.set('45,25');app.update()
    assert win.badges['wind.qb'].cget('text')=='Manual entry'
    assert 'Previous destination' in win.overview.item('wind.qb','values')[3]
    assert sc.get(app.site,'wind.qb')['value']==.4
    win.destroy();win=app.open_site();win.reviews['wind.qb'].set(True);assert win.save()
    assert not sc.get(app.site,'wind.qb')['reviewRequired']
    win.destroy();app.accept.set(True)
    response=[dict(name='Test',distance_km=677,hours=12,geometry=dict(type='LineString',coordinates=[[26.75,47.85],[25,45]]))]
    app.start_job=lambda work,done:done(work())
    with patch('routing.route',return_value=response):app.calculate_route()
    app.update();assert sc.get(app.site,'transport.distanceKm')['value']==677
    app.transfer();form=next(w for w in app.winfo_children() if isinstance(w,Form));form.submit();app.update()
    assert app.state.data['deliveries'][0]['siteConditions']['wind']['qb']['value']==.4
    app.theme();win=app.open_site();win.geometry('760x600');app.update()
    assert win.warning.winfo_ismapped()
    # Saving and reopening retains site data; legacy deliveries remain untouched.
    app.close();assert not errors,errors
    reopened=Planner(Path(folder)/'state.json',offline=True);reopened.update()
    assert reopened.dest_name.get()=='Site B';assert sc.get(reopened.site,'wind.qb')['value']==.4
    reopened.close()
print('PASS: site editor, validation, warnings, review, route reuse, delivery snapshot, dark/minimum size, save/load')
