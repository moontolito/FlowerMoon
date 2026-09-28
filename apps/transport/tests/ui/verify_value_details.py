"""Real Tk interaction checks using isolated state and offline fixtures."""
import tempfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from planner_ui import Planner
from test_annual import ready,POINT
import annual_corrosion as corrosion

with tempfile.TemporaryDirectory() as folder:
    app=Planner(Path(folder)/'state.json',offline=True);app.update()
    app.site['corrosivityEnabled']=True;app.site_location_ready=lambda:None
    errors=[];app.report_callback_exception=lambda *args:errors.append(args)
    app.dest_name.set('QA destination');app.dest_coords.set('45.1,24.1')
    app.site.update(destinationAddress='QA destination',destinationCoordinates='45.1,24.1')
    app.site['deposition']=ready();app.site['corrosionAssessment']=corrosion.evaluate(app.site['deposition'],POINT)
    win=app.open_site();win.lift();win.focus_force();app.update()
    assert len(win.book.tabs())==1
    win.overview.selection_set('section_air');app.update()
    assert win.value_button.instate(['!disabled']);section_dialog=win.value_details();assert section_dialog;section_dialog.destroy()
    win.overview.selection_set('environment.suggestedCorrosivity');win.overview.see('environment.suggestedCorrosivity');app.update()
    win.overview.yview_scroll(4,'units');app.update()
    assert win.value_button.instate(['!disabled'])
    box=win.overview.bbox('environment.suggestedCorrosivity','#2');x,y,w,h=box
    assert win.overview.bind('<Double-1>')
    click_x=x+w//2
    assert win.overview.identify_region(click_x,y+h//2)=='cell', (box,win.overview.identify_region(click_x,y+h//2))
    # Send two real click sequences to exercise the actual Double-1 binding.
    for stamp in (1000,1100):
        win.overview.event_generate('<ButtonPress-1>',x=click_x,y=y+h//2,time=stamp)
        win.overview.event_generate('<ButtonRelease-1>',x=click_x,y=y+h//2,time=stamp+30)
    app.update();dialog=win.value_window
    assert 'Calculation for this destination' in dialog.area.get('1.0','end')
    assert dialog.area.cget('state')=='disabled'
    with patch('value_details_ui.webbrowser.open_new_tab') as browser:
        tag=next(iter(dialog.links));ranges=dialog.area.tag_ranges(tag);dialog.area.see(ranges[0]);app.update()
        lx,ly,lw,lh=dialog.area.bbox(ranges[0]);dialog.area.event_generate('<Motion>',x=lx+4,y=ly+4);app.update()
        dialog.area.event_generate('<Button-1>',x=lx+4,y=ly+4);app.update()
        browser.assert_called_once_with(dialog.links[tag])
    dialog.copy_button.invoke();assert 'Stored category:' in dialog.clipboard_get()
    dialog.destroy();app.update()
    win.overview.focus_force();win.overview.event_generate('<Return>');app.update()
    assert win.value_window.winfo_exists();win.value_window.destroy()
    # Header clicks must not reopen stale selected-row details.
    old=win.value_window;win.open_value_at_pointer(SimpleNamespace(x=10,y=5));assert win.value_window is old
    app.site['destinationAddress']='New QA destination';win.refresh()
    dialog=win.value_details('design');assert 'New QA destination' in dialog.area.get('1.0','end');dialog.destroy()
    for mode in ('light','dark'):
        if app.mode!=mode:app.theme();win=app.open_site()
        dialog=win.value_details('corrosion.rate')
        for size in ('900x740','620x420'):
            dialog.geometry(size);app.update()
            assert dialog.area.winfo_height()>100
            assert dialog.copy_button.winfo_viewable()
            assert dialog.area.cget('bg')==app.c['surface']
            dialog.area.yview_moveto(1);app.update();assert dialog.area.yview()[1]>.99
        dialog.destroy()
    all_sources=win.sources();app.update();assert all_sources.links;all_sources.destroy()
    app.close();assert not errors,errors
print('PASS: double click, Enter, section/header exclusion, clickable provider links, copy, snapshot destination, light/dark, compact layout and sources viewer')
