"""Offline integration check against real Tk widgets and the actual Excel exporter."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from app import App,Form

with tempfile.TemporaryDirectory() as folder:
    app=App(Path(folder)/'state.json',offline=True)
    errors=[]
    app.report_callback_exception=lambda *args:errors.append(args)
    app.update();app.find_vehicle();app.update()
    assert app.active['loaded']['weight']==25
    app.accept.set(True);app.theme();app.update()
    assert app.accept.get(),'Theme change must preserve confirmation'
    app.navigate(2);app.update()
    app.dest_name.set('Timișoara');app.dest_coords.set('45.7555076,21.247397')
    response=[dict(name='Varianta 1',distance_km=677,hours=12,geometry=dict(type='LineString',coordinates=[[26.759334,47.8528263],[21.247397,45.7555076]]))]
    app.start_job=lambda work,done:done(work())
    with patch('routing.route',return_value=response):app.calculate_route()
    app.update();assert len(app.route_results)==1
    app.navigate(1);app.update();assert app.accept.get()
    app.navigate(2);app.update();assert len(app.route_results)==1
    app.transfer();app.update()
    form=next(w for w in app.winfo_children() if isinstance(w,Form))
    form.submit();app.update()
    assert len(app.state.data['deliveries'])==1
    app.sheet();app.update()
    for w in list(app.winfo_children()):
        if w.winfo_toplevel()==w and w!=app:w.destroy()
    app.dest_coords.set('45.76,21.25');assert not app.route_results
    app.navigate(1);app.product_vars['length'].set('19');app.find_vehicle();app.update()
    assert app.active is None
    app.geometry('1120x700');app.theme();app.update()
    app.close();assert not errors,errors
print('PASS: recommendation, confirmation, theme, routing, transfer, sheet, invalidation, shutdown')
