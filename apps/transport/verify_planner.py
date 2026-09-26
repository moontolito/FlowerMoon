"""Real-widget regression check; temporary planning data, no network calls."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from planner_ui import Planner,Form

with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);errors=[]
    app.report_callback_exception=lambda *args:errors.append(args)
    app.update();assert app.active['loaded']['height']==4.2
    assert not app.results_panel.winfo_ismapped()
    app.set_panel('vehicle');app.update()
    assert float(app.slider_vars['weight'].get())==25
    app.slider_vars['height'].set('4.5');app.apply_sliders();app.update()
    assert app.active['loaded']['height']==4.5
    app.slider_vars['height'].set('3')
    try:app.apply_sliders();raise AssertionError('Undersized envelope accepted')
    except ValueError:pass
    app.select_preset('example-2');app.update();assert float(app.slider_vars['height'].get())==4.2
    app.select_preset('example-1');assert app.active is None
    app.choose_recommended();app.set_panel('route');app.update()
    app.dest_name.set('Test');app.dest_coords.set('45.7555076,21.247397')
    response=[dict(name='Varianta 1',distance_km=677,hours=12,geometry=dict(type='LineString',coordinates=[[26.759334,47.8528263],[21.247397,45.7555076]]))]
    app.offline=False
    with patch('site_sources.lookup',return_value={}),patch('routing.route',return_value=response),patch('planner_ui.messagebox.askyesno',return_value=True):
        app.calculate_route()
        import time
        for _ in range(30):
            app.update();time.sleep(.02)
            if app.route_results:break
    assert app.route_results and app.results_panel.winfo_ismapped()
    app.transfer();app.update();form=next(w for w in app.winfo_children() if isinstance(w,Form));form.submit();app.offline=True;app.update()
    assert len(app.state.data['deliveries'])==1
    app.dest_name.set('Changed');assert not app.dest_coords.get() and not app.route_results
    app.theme();app.geometry('1000x700');app.update()
    assert app.calculate_button.winfo_rooty()+app.calculate_button.winfo_height()<app.winfo_rooty()+app.winfo_height()
    import sys
    if '--preview' in sys.argv:
        app.title('FlowerMoon · UI review');app.set_panel('vehicle');app.after(60000,app.close);app.mainloop()
    else:app.close()
    assert not errors,errors
print('PASS: presets, sliders, invalid sizing, route response, Excel transfer, stale address, dark theme, minimum size')
