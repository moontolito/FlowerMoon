"""Regression checks for typed-only autocomplete and a bounded overlay."""
import os,time,tempfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from planner_ui import Planner
from address_entry import AddressEntry

def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)

def pump(app,seconds=.9):
    end=time.monotonic()+seconds
    while time.monotonic()<end:app.update();time.sleep(.02)

with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True)
    errors=[];app.report_callback_exception=lambda *args:errors.append(args)
    app.site_location_ready=lambda:None
    app.update()
    entry=[w for w in walk(app) if isinstance(w,AddressEntry)][1]
    entry.online=True
    with patch('places.search',return_value=[]) as query:
        app.dest_name.set('Point selected on map');pump(app)
        assert not query.called and not entry.popup.winfo_ismapped()
    results=[dict(label='Long delivery address '+str(i)+' with many street names and building details, Toronto, Canada',lat=43.65+i/100,lon=-79.38) for i in range(6)]
    with patch('places.search',return_value=results) as query:
        entry.entry.focus_force();app.dest_name.set('Toronto');entry.typed(SimpleNamespace(keysym='o'))
        height=entry.master.winfo_height();pump(app)
        assert query.call_count==1 and entry.popup.winfo_ismapped()
        assert entry.master.winfo_height()==height
        assert entry.popup.winfo_width()<=620
        assert all(entry.list_font.measure(text)<=entry.popup.winfo_width()-28 for text in [entry.listbox.item(i,'text') for i in entry.listbox.get_children()])
        assert all('\n' not in text for text in [entry.listbox.item(i,'text') for i in entry.listbox.get_children()])
        if os.environ.get('FLOWERMOON_UI_ARTIFACTS'):
            from PIL import ImageGrab
            target=Path(os.environ['FLOWERMOON_UI_ARTIFACTS']);target.mkdir(parents=True,exist_ok=True)
            ImageGrab.grab(bbox=(app.winfo_rootx(),app.winfo_rooty(),app.winfo_rootx()+app.winfo_width(),app.winfo_rooty()+app.winfo_height())).save(target/'address-popup.png')
        entry.focus_list();entry.choose();app.update()
        assert app.dest_name.get()==results[0]['label'] and app.dest_coords.get()=='43.6500000, -79.3800000'
        assert not entry.popup.winfo_ismapped()
        app.dest_name.set('Tokyo');entry.typed(SimpleNamespace(keysym='o'));pump(app)
        entry.dismiss();pump(app,.15);assert not entry.popup.winfo_ismapped()
        app.dest_name.set('Paris');old=entry.token;entry.typed(SimpleNamespace(keysym='s'))
        entry.dismiss();entry.results.put((old,'Paris',results,None));pump(app,.2)
        assert not entry.rows and not entry.popup.winfo_ismapped()
    entry.online=False
    app.theme();app.update();app.close();assert not errors,errors
print('PASS: map selection does not search, typed suggestions overlay without resizing, long labels fit, keyboard selection, Escape, stale responses and theme rebuild')
